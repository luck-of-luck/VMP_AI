"""Bearer scanner integration for multi-language SAST analysis."""

import asyncio
import json
import logging

from sast_mcp_server.enrichment.ast_context import get_function_context
from sast_mcp_server.models import (
    ConfidenceLevel,
    DataFlowStep,
    Finding,
    SeverityLevel,
    meets_confidence_threshold,
    meets_severity_threshold,
)
from sast_mcp_server.scanners.base import DEFAULT_TIMEOUT, BaseScanner

logger = logging.getLogger(__name__)


class BearerScanner(BaseScanner):
    """Scanner integration for Bearer (multi-language SAST)."""

    name = "bearer"
    version_command = ["bearer", "version"]

    async def check_dependency(self) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "bearer", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    "Bearer is not installed. "
                    "Install it from: https://docs.bearer.com/installation/"
                )
        except FileNotFoundError as err:
            raise RuntimeError(
                "Bearer binary not found on PATH. "
                "Install it from: https://docs.bearer.com/installation/"
            ) from err

    async def scan(
        self,
        target_path: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        modified_files: set[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> list[Finding]:
        cmd = ["bearer", "scan", target_path, "--format", "json", "--quiet"]
        logger.info("Running Bearer: %s", " ".join(cmd))

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
                f"Bearer scan timed out after {timeout}s. "
                "Try scanning a smaller directory or increasing SAST_MCP_TIMEOUT."
            ) from err

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            logger.warning("Bearer stderr: %s", stderr_text)

        try:
            report = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as err:
            error_detail = stderr_text or "No output received from Bearer."
            raise RuntimeError(
                f"Bearer produced invalid JSON output. Details: {error_detail}"
            ) from err

        results: list[Finding] = []

        # Bearer may report findings under different keys depending on version
        findings_list = report.get("findings", report.get("vulnerabilities", []))

        for result in findings_list:
            severity = result.get("severity", "LOW").upper()
            # FIX: Parse actual confidence from Bearer output instead of hardcoding
            confidence = result.get("confidence", result.get("confidence_level", "MEDIUM")).upper()

            if not meets_severity_threshold(severity, min_severity):
                continue
            if not meets_confidence_threshold(confidence, min_confidence):
                continue

            file_path = result.get("file", result.get("filename", ""))
            if modified_files is not None and not any(
                file_path.endswith(mf) for mf in modified_files
            ):
                continue

            line_start = result.get("line", result.get("line_number", 0))
            context_code, ctx_start, ctx_end = get_function_context(
                file_path, line_start
            )

            # Parse data flow trace
            data_flow: list[DataFlowStep] = []
            for flow in result.get("data_flow", []):
                data_flow.append(
                    DataFlowStep(
                        file=flow.get("file", ""),
                        line=flow.get("line", 0),
                        code_snippet=flow.get("code_snippet", "").strip(),
                    )
                )

            title = result.get("title", result.get("rule_id", "Unknown"))
            # Detect language from file extension
            language = self._detect_language(file_path)

            # Normalize confidence to valid enum
            if confidence not in ConfidenceLevel.__members__:
                confidence = "MEDIUM"

            results.append(
                Finding(
                    scanner="bearer",
                    title=title,
                    message=result.get("description", result.get("message", "")),
                    file=file_path,
                    line_start=ctx_start,
                    line_end=ctx_end,
                    severity=SeverityLevel(severity)
                    if severity in SeverityLevel.__members__
                    else SeverityLevel.LOW,
                    confidence=ConfidenceLevel(confidence),
                    context=context_code,
                    language=language,
                    finding_hash=self.generate_hash(file_path, title, context_code),
                    data_flow=data_flow,
                )
            )

        logger.info("Bearer scan complete: %d findings", len(results))
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
        }
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return ""
