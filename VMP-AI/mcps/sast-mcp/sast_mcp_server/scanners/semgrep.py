"""Semgrep scanner integration for multi-language SAST analysis."""

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

# Semgrep severity mapping (semgrep uses INFO, WARNING, ERROR)
_SEMGREP_SEVERITY_MAP = {
    "INFO": "LOW",
    "WARNING": "MEDIUM",
    "ERROR": "HIGH",
}


class SemgrepScanner(BaseScanner):
    """Scanner integration for Semgrep (multi-language SAST with rule packs).

    Semgrep is the most widely-used open-source SAST tool. It supports
    30+ languages and has a large community rule registry.
    """

    name = "semgrep"
    version_command = ["semgrep", "--version"]

    async def check_dependency(self) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "semgrep", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    "Semgrep is not installed. Install it with: pip install semgrep  "
                    "or see https://semgrep.dev/docs/getting-started/"
                )
        except FileNotFoundError as err:
            raise RuntimeError(
                "Semgrep binary not found on PATH. "
                "Install it with: pip install semgrep  "
                "or see https://semgrep.dev/docs/getting-started/"
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
            "semgrep", "scan",
            "--json",
            "--config", "auto",  # Use recommended rules
            "--no-git-ignore",   # Scan everything in the target
            target_path,
        ]
        logger.info("Running Semgrep: %s", " ".join(cmd))

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
                f"Semgrep scan timed out after {timeout}s. "
                "Try scanning a smaller directory or increasing SAST_MCP_TIMEOUT."
            ) from err

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            # Semgrep often writes progress info to stderr — log at debug level
            logger.debug("Semgrep stderr: %s", stderr_text[:500])

        try:
            report = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as err:
            error_detail = stderr_text[:200] or "No output received from Semgrep."
            raise RuntimeError(
                f"Semgrep produced invalid JSON output. Details: {error_detail}"
            ) from err

        results: list[Finding] = []

        for result in report.get("results", []):
            # Semgrep severity: INFO, WARNING, ERROR → map to our levels
            raw_severity = result.get("extra", {}).get("severity", "WARNING")
            severity = _SEMGREP_SEVERITY_MAP.get(
                raw_severity.upper(), raw_severity.upper()
            )

            # Semgrep doesn't have explicit confidence; derive from metadata
            metadata = result.get("extra", {}).get("metadata", {})
            raw_confidence = metadata.get("confidence", "MEDIUM").upper()

            if not meets_severity_threshold(severity, min_severity):
                continue
            if not meets_confidence_threshold(raw_confidence, min_confidence):
                continue

            file_path = result.get("path", "")
            if modified_files is not None and not any(
                file_path.endswith(mf) for mf in modified_files
            ):
                continue

            line_start = result.get("start", {}).get("line", 0)
            result.get("end", {}).get("line", line_start)

            context_code, ctx_start, ctx_end = get_function_context(
                file_path, line_start
            )

            # Extract rule info
            rule_id = result.get("check_id", "unknown")
            message = result.get("extra", {}).get("message", "")
            language = self._detect_language(file_path)

            # Enterprise metadata from Semgrep rule metadata
            cwe = join_values(metadata.get("cwe"))
            owasp = join_values(metadata.get("owasp"))
            references = to_str_list(metadata.get("references"))

            # Normalize to valid enums
            if severity not in SeverityLevel.__members__:
                severity = "MEDIUM"
            if raw_confidence not in ConfidenceLevel.__members__:
                raw_confidence = "MEDIUM"

            results.append(
                Finding(
                    scanner="semgrep",
                    title=rule_id,
                    message=message,
                    file=file_path,
                    line_start=ctx_start,
                    line_end=ctx_end,
                    severity=SeverityLevel(severity),
                    confidence=ConfidenceLevel(raw_confidence),
                    context=context_code,
                    language=language,
                    finding_hash=self.generate_hash(file_path, rule_id, context_code),
                    cwe=cwe,
                    owasp_category=owasp,
                    references=references,
                )
            )

        logger.info("Semgrep scan complete: %d findings", len(results))
        return results

    @staticmethod
    def _detect_language(file_path: str) -> str:
        """Infer language from file extension."""
        ext_map = {
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
            ".scala": "scala",
        }
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return ""
