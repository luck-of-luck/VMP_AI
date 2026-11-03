"""Bandit scanner integration for Python SAST analysis."""

import asyncio
import json
import logging
import sys

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


class BanditScanner(BaseScanner):
    """Scanner integration for Bandit (Python security linter)."""

    name = "bandit"
    version_command = [sys.executable, "-m", "bandit", "--version"]

    async def check_dependency(self) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "bandit", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    "Bandit is not installed. Install it with: pip install bandit"
                )
        except FileNotFoundError as err:
            raise RuntimeError(
                "Python executable not found. Ensure Python is installed and on PATH."
            ) from err

    async def scan(
        self,
        target_path: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        modified_files: set[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> list[Finding]:
        # -q suppresses bandit's progress/metric log lines, which on some
        # platforms (e.g. Linux) are emitted to stdout and would otherwise
        # corrupt the JSON document we parse below.
        cmd = [sys.executable, "-m", "bandit", "-r", target_path, "-f", "json", "-q"]
        logger.info("Running Bandit: %s", " ".join(cmd))

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
                f"Bandit scan timed out after {timeout}s. "
                "Try scanning a smaller directory or increasing SAST_MCP_TIMEOUT."
            ) from err

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            logger.warning("Bandit stderr: %s", stderr_text)

        try:
            report = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as err:
            error_detail = stderr_text or "No output received from Bandit."
            raise RuntimeError(
                f"Bandit produced invalid JSON output. Details: {error_detail}"
            ) from err

        results: list[Finding] = []
        for result in report.get("results", []):
            severity = result.get("issue_severity", "LOW").upper()
            confidence = result.get("issue_confidence", "LOW").upper()

            if not meets_severity_threshold(severity, min_severity):
                continue
            if not meets_confidence_threshold(confidence, min_confidence):
                continue

            file_path = result.get("filename", "")
            if modified_files is not None and not any(
                file_path.endswith(mf) for mf in modified_files
            ):
                continue

            line_start = result.get("line_number", 0)
            context_code, ctx_start, ctx_end = get_function_context(
                file_path, line_start
            )

            title = result.get("test_name", "Unknown")

            # Bandit reports CWE as {"id": 89, "link": "..."} and a more_info URL.
            cwe = ""
            references = []
            issue_cwe = result.get("issue_cwe")
            if isinstance(issue_cwe, dict):
                cwe_id = issue_cwe.get("id")
                if cwe_id is not None:
                    cwe = f"CWE-{cwe_id}"
                if issue_cwe.get("link"):
                    references.append(issue_cwe["link"])
            if result.get("more_info"):
                references.append(result["more_info"])

            results.append(
                Finding(
                    scanner="bandit",
                    title=title,
                    message=result.get("issue_text", ""),
                    file=file_path,
                    line_start=ctx_start,
                    line_end=ctx_end,
                    severity=SeverityLevel(severity)
                    if severity in SeverityLevel.__members__
                    else SeverityLevel.LOW,
                    confidence=ConfidenceLevel(confidence)
                    if confidence in ConfidenceLevel.__members__
                    else ConfidenceLevel.LOW,
                    context=context_code,
                    language="python",
                    finding_hash=self.generate_hash(file_path, title, context_code),
                    cwe=cwe,
                    references=references,
                )
            )

        logger.info("Bandit scan complete: %d findings", len(results))
        return results
