"""Anchore Grype integration — SCA for directories, images, and SBOMs."""

import asyncio
import json
import logging

from sast_mcp_server.models import (
    ConfidenceLevel,
    Finding,
    SeverityLevel,
    meets_severity_threshold,
)
from sast_mcp_server.scanners.base import DEFAULT_TIMEOUT, BaseScanner

logger = logging.getLogger(__name__)

# Grype severity vocabulary → our SeverityLevel.
_GRYPE_SEVERITY_MAP = {
    "CRITICAL": SeverityLevel.CRITICAL,
    "HIGH": SeverityLevel.HIGH,
    "MEDIUM": SeverityLevel.MEDIUM,
    "LOW": SeverityLevel.LOW,
    "NEGLIGIBLE": SeverityLevel.LOW,
    "UNKNOWN": SeverityLevel.LOW,
}


class GrypeScanner(BaseScanner):
    """Scanner integration for Anchore Grype.

    Grype scans container images, filesystems, and SBOMs for known
    vulnerabilities, complementing Trivy/OSV with a second vulnerability
    database. ``scan()`` runs against a directory; ``scan_image()`` against a
    container image reference.
    """

    name = "grype"
    version_command = ["grype", "version"]

    async def check_dependency(self) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "grype", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    "Grype is not installed. Install it from: "
                    "https://github.com/anchore/grype#installation"
                )
        except FileNotFoundError as err:
            raise RuntimeError(
                "Grype binary not found on PATH. Install it from: "
                "https://github.com/anchore/grype#installation"
            ) from err

    async def _run_grype(self, source: str, timeout: int) -> dict:
        """Run grype against a source spec (e.g. ``dir:.`` or an image ref)."""
        cmd = ["grype", source, "-o", "json"]
        logger.info("Running Grype: %s", " ".join(cmd))
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError as err:
            proc.kill()
            raise RuntimeError(f"Grype scan timed out after {timeout}s.") from err

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            logger.debug("Grype stderr: %s", stderr_text[:500])
        try:
            data = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as err:
            detail = stderr_text[:200] or "No output received from Grype."
            raise RuntimeError(f"Grype produced invalid JSON. Details: {detail}") from err
        return data if isinstance(data, dict) else {}

    def _findings_from_report(
        self,
        report: dict,
        min_severity: str,
        modified_files: set[str] | None,
    ) -> list[Finding]:
        results: list[Finding] = []
        for match in report.get("matches", []) or []:
            finding = self._parse_match(match, min_severity, modified_files)
            if finding is not None:
                results.append(finding)
        return results

    async def scan(
        self,
        target_path: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        modified_files: set[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> list[Finding]:
        report = await self._run_grype(f"dir:{target_path}", timeout)
        results = self._findings_from_report(report, min_severity, modified_files)
        logger.info("Grype scan complete: %d findings", len(results))
        return results

    async def scan_image(
        self,
        image_ref: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> list[Finding]:
        """Scan a container image reference for known vulnerabilities."""
        report = await self._run_grype(image_ref, timeout)
        results = self._findings_from_report(report, min_severity, None)
        logger.info("Grype image scan complete: %d findings", len(results))
        return results

    def _parse_match(
        self,
        match: dict,
        min_severity: str,
        modified_files: set[str] | None,
    ) -> Finding | None:
        vuln = match.get("vulnerability", {})
        artifact = match.get("artifact", {})

        severity = _GRYPE_SEVERITY_MAP.get(
            str(vuln.get("severity", "UNKNOWN")).upper(), SeverityLevel.LOW
        )
        if not meets_severity_threshold(severity.value, min_severity):
            return None

        locations = artifact.get("locations") or []
        source_file = locations[0].get("path", "") if locations else ""
        if modified_files is not None and not any(
            source_file.endswith(mf) for mf in modified_files
        ):
            return None

        vuln_id = str(vuln.get("id") or "UNKNOWN")
        pkg_name = str(artifact.get("name") or "unknown")
        pkg_version = str(artifact.get("version") or "?")
        title = f"{vuln_id} ({pkg_name})"

        fix = vuln.get("fix") or {}
        fixed_versions = fix.get("versions") or []
        fixed_label = fixed_versions[0] if fixed_versions else "N/A"
        remediation = (
            f"Upgrade {pkg_name} to {fixed_versions[0]} or later."
            if fixed_versions
            else ""
        )

        cvss_score, cvss_vector = self._extract_cvss(vuln)
        references = [u for u in (vuln.get("urls") or []) if isinstance(u, str)]
        data_source = vuln.get("dataSource")
        if isinstance(data_source, str) and data_source and data_source not in references:
            references.insert(0, data_source)

        return Finding(
            scanner=self.name,
            title=title,
            message=str(vuln.get("description") or f"Vulnerability in {pkg_name}"),
            file=source_file or pkg_name,
            line_start=1,
            line_end=1,
            severity=severity,
            confidence=ConfidenceLevel.HIGH,
            context=f"Package: {pkg_name}@{pkg_version} (fix: {fixed_label})",
            language=str(artifact.get("language") or ""),
            finding_hash=self.generate_hash(source_file or pkg_name, title, pkg_name),
            cvss_score=cvss_score,
            cvss_vector=cvss_vector,
            references=references,
            remediation=remediation,
        )

    @staticmethod
    def _extract_cvss(vuln: dict) -> tuple[float | None, str]:
        """Pull the first CVSS base score + vector from a Grype vulnerability."""
        for entry in vuln.get("cvss", []) or []:
            metrics = entry.get("metrics", {}) if isinstance(entry, dict) else {}
            score = metrics.get("baseScore")
            vector = entry.get("vector", "") if isinstance(entry, dict) else ""
            if isinstance(score, (int, float)):
                return float(score), str(vector or "")
        return None, ""
