"""Trivy scanner integration for vulnerability, secret, and IaC scanning."""

import asyncio
import json
import logging

from sast_mcp_server.enrichment.ast_context import get_function_context
from sast_mcp_server.enrichment.metadata import join_values, to_str_list
from sast_mcp_server.models import (
    ConfidenceLevel,
    Finding,
    SeverityLevel,
    meets_confidence_threshold,
    meets_severity_threshold,
)
from sast_mcp_server.scanners.base import DEFAULT_TIMEOUT, BaseScanner

logger = logging.getLogger(__name__)

# Trivy severity mapping — Trivy uses CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN
_TRIVY_SEVERITY_MAP = {
    "CRITICAL": "CRITICAL",
    "HIGH": "HIGH",
    "MEDIUM": "MEDIUM",
    "LOW": "LOW",
    "UNKNOWN": "LOW",
}

# Language detection for IaC and config files
_IAC_LANGUAGE_MAP = {
    ".tf": "terraform",
    ".tfvars": "terraform",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    "Dockerfile": "docker",
    ".dockerfile": "docker",
    "docker-compose": "docker",
}

# Standard language detection for source files
_SOURCE_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".rb": "ruby",
    ".java": "java",
    ".go": "go",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".rs": "rust",
    ".kt": "kotlin",
    ".swift": "swift",
}


class TrivyScanner(BaseScanner):
    """Scanner integration for Trivy (vulnerabilities, secrets, IaC misconfigurations).

    Trivy is a comprehensive security scanner that covers:
    - Dependency vulnerabilities (SCA) from lock files and manifests
    - Hardcoded secrets (API keys, tokens, passwords)
    - Infrastructure-as-Code misconfigurations (Terraform, K8s, Docker, etc.)
    """

    name = "trivy"
    version_command = ["trivy", "--version"]

    async def check_dependency(self) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "trivy", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    "Trivy is not installed. "
                    "Install it from: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
                )
        except FileNotFoundError as err:
            raise RuntimeError(
                "Trivy binary not found on PATH. "
                "Install it from: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
            ) from err

    async def _run_trivy(self, cmd: list[str], timeout: int) -> dict:
        """Run a Trivy command and return its parsed JSON report."""
        logger.info("Running Trivy: %s", " ".join(cmd))
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
            raise RuntimeError(
                f"Trivy scan timed out after {timeout}s. "
                "Try a smaller target or increasing SAST_MCP_TIMEOUT."
            ) from err

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            # Trivy writes progress info to stderr
            logger.debug("Trivy stderr: %s", stderr_text[:500])

        try:
            data = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as err:
            error_detail = stderr_text[:200] or "No output received from Trivy."
            raise RuntimeError(
                f"Trivy produced invalid JSON output. Details: {error_detail}"
            ) from err
        return data if isinstance(data, dict) else {}

    def _findings_from_report(
        self,
        report: dict,
        min_severity: str,
        min_confidence: str,
        modified_files: set[str] | None,
    ) -> list[Finding]:
        """Convert a Trivy JSON report into Finding objects."""
        results: list[Finding] = []

        for target_result in report.get("Results", []):
            target_file = target_result.get("Target", "")

            # --- Parse Vulnerabilities (SCA) ---
            for vuln in target_result.get("Vulnerabilities", []) or []:
                finding = self._parse_vulnerability(
                    vuln, target_file, min_severity, min_confidence, modified_files
                )
                if finding is not None:
                    results.append(finding)

            # --- Parse Secrets ---
            for secret in target_result.get("Secrets", []) or []:
                finding = self._parse_secret(
                    secret, target_file, min_severity, min_confidence, modified_files
                )
                if finding is not None:
                    results.append(finding)

            # --- Parse Misconfigurations (IaC) ---
            for misconfig in target_result.get("Misconfigurations", []) or []:
                finding = self._parse_misconfiguration(
                    misconfig, target_file, min_severity, min_confidence, modified_files
                )
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
        cmd = [
            "trivy", "fs",
            "--format", "json",
            "--scanners", "vuln,secret,misconfig",
            target_path,
        ]
        report = await self._run_trivy(cmd, timeout)
        results = self._findings_from_report(
            report, min_severity, min_confidence, modified_files
        )
        logger.info("Trivy scan complete: %d findings", len(results))
        return results

    async def scan_image(
        self,
        image_ref: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> list[Finding]:
        """Scan a container image reference for vulnerabilities and secrets."""
        cmd = [
            "trivy", "image",
            "--format", "json",
            "--scanners", "vuln,secret",
            image_ref,
        ]
        report = await self._run_trivy(cmd, timeout)
        results = self._findings_from_report(report, min_severity, min_confidence, None)
        logger.info("Trivy image scan complete: %d findings", len(results))
        return results

    def _parse_vulnerability(
        self,
        vuln: dict,
        target_file: str,
        min_severity: str,
        min_confidence: str,
        modified_files: set[str] | None,
    ) -> Finding | None:
        """Parse a Trivy vulnerability (SCA) finding."""
        severity = _TRIVY_SEVERITY_MAP.get(
            vuln.get("Severity", "UNKNOWN").upper(), "LOW"
        )

        if not meets_severity_threshold(severity, min_severity):
            return None
        if not meets_confidence_threshold("MEDIUM", min_confidence):
            return None

        if modified_files is not None and not any(
            target_file.endswith(mf) for mf in modified_files
        ):
            return None

        vuln_id = str(vuln.get("VulnerabilityID") or "Unknown")
        pkg_name = str(vuln.get("PkgName") or "unknown")
        title = f"{vuln_id} ({pkg_name})"
        installed = str(vuln.get("InstalledVersion") or "?")
        fixed = str(vuln.get("FixedVersion") or "N/A")
        message = str(vuln.get("Title") or vuln.get("Description") or "")
        if installed != "?" or fixed != "N/A":
            message += f" [Installed: {installed}, Fixed: {fixed}]"

        cvss_score, cvss_vector = self._extract_cvss(vuln)
        references = to_str_list(vuln.get("References"))
        primary_url = vuln.get("PrimaryURL")
        if primary_url and primary_url not in references:
            references.insert(0, primary_url)
        remediation = (
            f"Upgrade {pkg_name} to {fixed} or later."
            if fixed and fixed != "N/A"
            else ""
        )

        return Finding(
            scanner="trivy",
            title=title,
            message=message,
            file=target_file,
            line_start=1,
            line_end=1,
            severity=SeverityLevel(severity)
            if severity in SeverityLevel.__members__
            else SeverityLevel.LOW,
            confidence=ConfidenceLevel.MEDIUM,
            context=f"Package: {pkg_name}@{installed} (fix: {fixed})",
            language=self._detect_language(target_file),
            finding_hash=self.generate_hash(target_file, title, pkg_name),
            cwe=join_values(vuln.get("CweIDs")),
            cvss_score=cvss_score,
            cvss_vector=cvss_vector,
            references=references,
            remediation=remediation,
        )

    def _parse_secret(
        self,
        secret: dict,
        target_file: str,
        min_severity: str,
        min_confidence: str,
        modified_files: set[str] | None,
    ) -> Finding | None:
        """Parse a Trivy secret detection finding."""
        severity = _TRIVY_SEVERITY_MAP.get(
            secret.get("Severity", "HIGH").upper(), "HIGH"
        )

        if not meets_severity_threshold(severity, min_severity):
            return None
        # Secrets have high confidence by nature
        if not meets_confidence_threshold("HIGH", min_confidence):
            return None

        if modified_files is not None and not any(
            target_file.endswith(mf) for mf in modified_files
        ):
            return None

        title = str(secret.get("Title") or secret.get("RuleID") or "Secret Detected")
        line_start = secret.get("StartLine", 1)
        match_text = str(secret.get("Match") or "")

        context_code, ctx_start, ctx_end = get_function_context(
            target_file, line_start
        )

        return Finding(
            scanner="trivy",
            title=title,
            message=str(secret.get("Title") or "Hardcoded secret detected in source code"),
            file=target_file,
            line_start=ctx_start,
            line_end=ctx_end,
            severity=SeverityLevel(severity)
            if severity in SeverityLevel.__members__
            else SeverityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH,
            context=context_code,
            language=self._detect_language(target_file),
            finding_hash=self.generate_hash(target_file, title, match_text),
        )

    def _parse_misconfiguration(
        self,
        misconfig: dict,
        target_file: str,
        min_severity: str,
        min_confidence: str,
        modified_files: set[str] | None,
    ) -> Finding | None:
        """Parse a Trivy IaC misconfiguration finding."""
        severity = _TRIVY_SEVERITY_MAP.get(
            misconfig.get("Severity", "MEDIUM").upper(), "MEDIUM"
        )

        if not meets_severity_threshold(severity, min_severity):
            return None
        if not meets_confidence_threshold("HIGH", min_confidence):
            return None

        if modified_files is not None and not any(
            target_file.endswith(mf) for mf in modified_files
        ):
            return None

        title = str(misconfig.get("Title") or misconfig.get("ID") or "Misconfiguration")
        check_id = str(misconfig.get("ID") or "")
        message = str(misconfig.get("Description") or misconfig.get("Message") or "")
        resolution = str(misconfig.get("Resolution") or "")
        if resolution:
            message += f" Resolution: {resolution}"

        # IaC findings often have a CauseMetadata with line info
        cause = misconfig.get("CauseMetadata", {})
        line_start = cause.get("StartLine", 1)
        line_end = cause.get("EndLine", line_start)
        code_snippet = cause.get("Code", {}).get("Lines", [])

        if code_snippet and isinstance(code_snippet, list):
            context = "\n".join(
                line.get("Content", "") for line in code_snippet
                if isinstance(line, dict)
            )
        else:
            context_code, ctx_start, ctx_end = get_function_context(
                target_file, line_start
            )
            context = context_code
            line_start = ctx_start
            line_end = ctx_end

        return Finding(
            scanner="trivy",
            title=f"{check_id}: {title}" if check_id else title,
            message=message,
            file=target_file,
            line_start=line_start,
            line_end=line_end,
            severity=SeverityLevel(severity)
            if severity in SeverityLevel.__members__
            else SeverityLevel.MEDIUM,
            confidence=ConfidenceLevel.HIGH,
            context=context,
            language=self._detect_language(target_file),
            finding_hash=self.generate_hash(target_file, title, context),
            references=to_str_list(misconfig.get("References")),
            remediation=resolution,
        )

    @staticmethod
    def _extract_cvss(vuln: dict) -> tuple[float | None, str]:
        """Pull a CVSS v3 score + vector from Trivy's per-source CVSS map.

        Prefers the NVD source, then falls back to whichever source provides a
        v3 score/vector first.
        """
        cvss_map = vuln.get("CVSS")
        if not isinstance(cvss_map, dict):
            return None, ""
        ordered = []
        if "nvd" in cvss_map:
            ordered.append(cvss_map["nvd"])
        ordered.extend(v for k, v in cvss_map.items() if k != "nvd")

        score: float | None = None
        vector = ""
        for entry in ordered:
            if not isinstance(entry, dict):
                continue
            if score is None and isinstance(entry.get("V3Score"), (int, float)):
                score = float(entry["V3Score"])
            if not vector and isinstance(entry.get("V3Vector"), str):
                vector = entry["V3Vector"]
            if score is not None and vector:
                break
        return score, vector

    @staticmethod
    def _detect_language(file_path: str) -> str:
        """Infer language from file extension, supporting IaC files."""
        # Check IaC-specific patterns first
        basename = file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if basename.lower().startswith("dockerfile"):
            return "docker"
        if "docker-compose" in basename.lower():
            return "docker"

        for ext, lang in _IAC_LANGUAGE_MAP.items():
            if file_path.endswith(ext):
                return lang
        for ext, lang in _SOURCE_LANGUAGE_MAP.items():
            if file_path.endswith(ext):
                return lang
        return ""
