"""OSV-Scanner integration for Software Composition Analysis (SCA)."""

import asyncio
import json
import logging
import os
from typing import Any

from sast_mcp_server.enrichment.metadata import join_values
from sast_mcp_server.models import ConfidenceLevel, Finding, SeverityLevel, meets_severity_threshold
from sast_mcp_server.scanners.base import BaseScanner

logger = logging.getLogger(__name__)


class OsvScanner(BaseScanner):
    """Scanner implementation for Google's OSV-Scanner.

    Checks dependencies against the Open Source Vulnerabilities (OSV) database.
    Supports parsing lockfiles, SBOMs, and git directories.
    """

    name = "osv-scanner"
    version_command = ["osv-scanner", "--version"]

    async def check_dependency(self) -> None:
        """Check if osv-scanner is installed and available in the system PATH."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "osv-scanner", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError("OSV-Scanner is not installed or accessible.")
        except FileNotFoundError as err:
            raise RuntimeError("OSV-Scanner is not installed or accessible.") from err

    async def scan(
        self,
        target_path: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        modified_files: set[str] | None = None,
        timeout: int = 300,
    ) -> list[Finding]:
        """Run OSV-Scanner on the target path and parse the results."""
        cmd = [
            "osv-scanner",
            "--json",
            "-r", target_path,
        ]

        logger.info("Running OSV-Scanner: %s", " ".join(cmd))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError as err:
            proc.kill()
            raise RuntimeError("OSV-Scanner timed out.") from err

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # OSV-scanner returns 0 if no vulns, 1 if vulns found, other codes for errors
        if proc.returncode not in (0, 1) and not stdout.strip():
            raise RuntimeError(f"OSV-Scanner failed with code {proc.returncode}: {stderr}")

        if not stdout.strip():
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.warning("OSV-Scanner produced invalid JSON output")
            return []

        findings = []

        # OSV-Scanner JSON structure:
        #   {"results": [{"source": {"path": ...},
        #                 "packages": [{"package": {"name": ...},
        #                               "vulnerabilities": [...]}]}]}
        results = data.get("results", [])
        if not results:
            return []

        for result in results:
            source_file = result.get("source", {}).get("path", target_path)
            # Make source file relative to target path if possible
            if source_file.startswith(target_path):
                source_file = os.path.relpath(source_file, target_path)

            # Skip if file filtering is applied
            if modified_files and not any(source_file.endswith(mf) for mf in modified_files):
                continue

            packages = result.get("packages", [])
            for pkg in packages:
                pkg_name = pkg.get("package", {}).get("name", "unknown")
                pkg_version = pkg.get("package", {}).get("version", "unknown")

                vulns = pkg.get("vulnerabilities", [])
                for vuln in vulns:
                    finding = self._parse_vuln(vuln, source_file, pkg_name, pkg_version)
                    if meets_severity_threshold(finding.severity.value, min_severity):
                        findings.append(finding)

        return findings

    # Qualitative severity strings used by OSV/GHSA `database_specific.severity`.
    _OSV_SEVERITY_MAP = {
        "CRITICAL": SeverityLevel.CRITICAL,
        "HIGH": SeverityLevel.HIGH,
        "MODERATE": SeverityLevel.MEDIUM,
        "MEDIUM": SeverityLevel.MEDIUM,
        "LOW": SeverityLevel.LOW,
    }

    def _parse_vuln(
        self,
        vuln: dict[str, Any],
        source_file: str,
        pkg_name: str,
        pkg_version: str,
    ) -> Finding:
        """Parse a single OSV vulnerability into the Finding model."""
        vuln_id = vuln.get("id", "UNKNOWN-CVE")
        summary = vuln.get("summary", f"Vulnerability in {pkg_name}")
        severity = self._derive_severity(vuln)

        # If there are aliases (e.g. CVE ids), surface them in the context
        aliases = vuln.get("aliases", [])
        alias_str = f" ({', '.join(aliases)})" if aliases else ""

        context = (
            f"Package: {pkg_name}@{pkg_version}\n"
            f"Vulnerability ID: {vuln_id}{alias_str}\n"
            f"Reference: https://osv.dev/vulnerability/{vuln_id}"
        )

        title = f"{vuln_id} in {pkg_name}"

        finding = Finding(
            scanner=self.name,
            title=title,
            message=summary,
            file=source_file,
            line_start=1,  # OSV-scanner doesn't give line numbers for lockfiles usually
            line_end=1,
            severity=severity,
            confidence=ConfidenceLevel.HIGH,  # OSV matches are generally high confidence
            context=context,
            finding_hash=self.generate_hash(source_file, title, context),
            cwe=join_values(vuln.get("database_specific", {}).get("cwe_ids")),
            cvss_vector=self._extract_cvss_vector(vuln),
            references=self._extract_references(vuln, vuln_id, aliases),
            remediation=self._extract_remediation(vuln, pkg_name),
        )

        return finding

    @staticmethod
    def _extract_cvss_vector(vuln: dict[str, Any]) -> str:
        """Return the first CVSS vector string from the OSV ``severity`` array."""
        for entry in vuln.get("severity", []):
            score = entry.get("score", "")
            if isinstance(score, str) and score.upper().startswith("CVSS"):
                return score
        return ""

    @staticmethod
    def _extract_references(
        vuln: dict[str, Any], vuln_id: str, aliases: list[str]
    ) -> list[str]:
        """Collect advisory/CVE reference URLs for the vulnerability."""
        refs = [f"https://osv.dev/vulnerability/{vuln_id}"]
        for ref in vuln.get("references", []):
            url = ref.get("url") if isinstance(ref, dict) else None
            if url:
                refs.append(url)
        # Surface CVE aliases as nvd.nist.gov links for quick lookup.
        for alias in aliases:
            if alias.upper().startswith("CVE-"):
                refs.append(f"https://nvd.nist.gov/vuln/detail/{alias}")
        # De-duplicate while preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for r in refs:
            if r not in seen:
                seen.add(r)
                unique.append(r)
        return unique

    @staticmethod
    def _extract_remediation(vuln: dict[str, Any], pkg_name: str) -> str:
        """Build an upgrade hint from the first fixed version in the advisory."""
        for affected in vuln.get("affected", []):
            for rng in affected.get("ranges", []):
                for event in rng.get("events", []):
                    fixed = event.get("fixed")
                    if fixed:
                        return f"Upgrade {pkg_name} to {fixed} or later."
        return ""

    def _derive_severity(self, vuln: dict[str, Any]) -> SeverityLevel:
        """Derive a severity level for an OSV vulnerability.

        Prefers the qualitative ``database_specific.severity`` string published
        by sources such as the GitHub Advisory Database. OSV's ``severity``
        array only carries CVSS *vector* strings (not numeric scores), so we do
        not attempt to recompute a base score here. When no qualitative rating
        is available we default to HIGH, since unrated supply-chain advisories
        should not be silently downgraded.
        """
        rating = vuln.get("database_specific", {}).get("severity")
        if isinstance(rating, str):
            mapped = self._OSV_SEVERITY_MAP.get(rating.strip().upper())
            if mapped is not None:
                return mapped
        return SeverityLevel.HIGH
