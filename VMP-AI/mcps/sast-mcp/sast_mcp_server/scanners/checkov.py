"""Checkov scanner integration for Infrastructure-as-Code policy scanning."""

import asyncio
import json
import logging

from sast_mcp_server.enrichment.ast_context import get_function_context
from sast_mcp_server.models import (
    ConfidenceLevel,
    Finding,
    SeverityLevel,
    meets_confidence_threshold,
    meets_severity_threshold,
)
from sast_mcp_server.scanners.base import DEFAULT_TIMEOUT, BaseScanner

logger = logging.getLogger(__name__)

# IaC file extension → language name
_CHECKOV_LANGUAGE_MAP = {
    ".tf": "terraform",
    ".tfvars": "terraform",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".template": "cloudformation",
    ".bicep": "bicep",
}


class CheckovScanner(BaseScanner):
    """Scanner integration for Checkov (Infrastructure-as-Code policy scanner).

    Checkov scans infrastructure-as-code files for security misconfigurations
    with 1000+ built-in policies covering Terraform, Kubernetes, Docker,
    CloudFormation, Azure ARM, Helm, and more.
    """

    name = "checkov"
    version_command = ["checkov", "--version"]

    async def check_dependency(self) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "checkov", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    "Checkov is not installed. Install it with: pip install checkov"
                )
        except FileNotFoundError as err:
            raise RuntimeError(
                "Checkov binary not found on PATH. "
                "Install it with: pip install checkov"
            ) from err

    async def scan(
        self,
        target_path: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        modified_files: set[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> list[Finding]:
        cmd = [
            "checkov",
            "-d", target_path,
            "-o", "json",
            "--quiet",
            "--compact",
        ]
        logger.info("Running Checkov: %s", " ".join(cmd))

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
                f"Checkov scan timed out after {timeout}s. "
                "Try scanning a smaller directory or increasing SAST_MCP_TIMEOUT."
            ) from err

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            logger.debug("Checkov stderr: %s", stderr_text[:500])

        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        if not stdout_text:
            error_detail = stderr_text[:200] or "No output received from Checkov."
            raise RuntimeError(
                f"Checkov produced no output. Details: {error_detail}"
            )

        try:
            report = json.loads(stdout_text)
        except json.JSONDecodeError as err:
            error_detail = stderr_text[:200] or "Invalid output from Checkov."
            raise RuntimeError(
                f"Checkov produced invalid JSON output. Details: {error_detail}"
            ) from err

        results: list[Finding] = []

        # Checkov can return a list (multiple check types) or a single dict
        check_results = report if isinstance(report, list) else [report]

        for check_block in check_results:
            if not isinstance(check_block, dict):
                continue

            failed_checks = check_block.get("results", {}).get("failed_checks", [])

            for check in failed_checks:
                finding = self._parse_check(
                    check, min_severity, min_confidence, modified_files
                )
                if finding is not None:
                    results.append(finding)

        logger.info("Checkov scan complete: %d findings", len(results))
        return results

    def _parse_check(
        self,
        check: dict,
        min_severity: str,
        min_confidence: str,
        modified_files: set[str] | None,
    ) -> Finding | None:
        """Parse a single Checkov failed check into a Finding."""
        # Checkov severity: CRITICAL, HIGH, MEDIUM, LOW (or missing)
        severity = check.get("severity", "MEDIUM")
        if severity is None:
            severity = "MEDIUM"
        severity = severity.upper()

        if severity not in SeverityLevel.__members__:
            severity = "MEDIUM"

        if not meets_severity_threshold(severity, min_severity):
            return None
        # Checkov checks are deterministic (policy-based)
        if not meets_confidence_threshold("HIGH", min_confidence):
            return None

        file_path = check.get("file_path", "")
        # Checkov prepends '/' to relative paths — normalize
        if file_path.startswith("/"):
            file_path = file_path[1:]

        if modified_files is not None and not any(
            file_path.endswith(mf) for mf in modified_files
        ):
            return None

        check_id = str(check.get("check_id") or "")
        check_name = str(check.get("check_name") or check.get("name") or "Unknown")
        title = f"{check_id}: {check_name}" if check_id else check_name

        # Line range
        file_line_range = check.get("file_line_range", [1, 1])
        if isinstance(file_line_range, list) and len(file_line_range) >= 2:
            line_start = file_line_range[0]
        else:
            line_start = 1

        # Get code context
        context_code, ctx_start, ctx_end = get_function_context(
            file_path, line_start
        )

        guideline = str(check.get("guideline") or "")
        message = check_name
        if guideline:
            message += f" | Guide: {guideline}"

        resource = str(check.get("resource") or "")
        if resource:
            message += f" | Resource: {resource}"

        return Finding(
            scanner="checkov",
            title=title,
            message=message,
            file=file_path,
            line_start=ctx_start,
            line_end=ctx_end,
            severity=SeverityLevel(severity),
            confidence=ConfidenceLevel.HIGH,
            context=context_code,
            language=self._detect_language(file_path),
            finding_hash=self.generate_hash(file_path, title, context_code),
            references=[guideline] if guideline else [],
            remediation=(
                f"See remediation guidance: {guideline}" if guideline else ""
            ),
        )

    @staticmethod
    def _detect_language(file_path: str) -> str:
        """Infer language/framework from file extension for IaC files."""
        basename = file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()

        if basename == "dockerfile" or basename.endswith(".dockerfile"):
            return "docker"
        if "docker-compose" in basename:
            return "docker"
        if basename.endswith(".tf") or basename.endswith(".tfvars"):
            return "terraform"
        if basename.endswith((".yaml", ".yml")):
            return "yaml"
        if basename.endswith(".json"):
            return "json"
        if basename.endswith(".bicep"):
            return "bicep"
        if basename.endswith(".template"):
            return "cloudformation"

        for ext, lang in _CHECKOV_LANGUAGE_MAP.items():
            if file_path.endswith(ext):
                return lang
        return ""
