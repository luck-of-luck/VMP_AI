"""njsscan scanner integration for JavaScript/Node.js SAST analysis."""

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

# njsscan severity mapping from its internal metadata
_NJSSCAN_SEVERITY_MAP = {
    "ERROR": "HIGH",
    "WARNING": "MEDIUM",
    "INFO": "LOW",
}


class NjsscanScanner(BaseScanner):
    """Scanner integration for njsscan (Node.js/JavaScript SAST)."""

    name = "njsscan"
    version_command = ["njsscan", "--version"]

    async def check_dependency(self) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "njsscan", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    "njsscan is not installed. Install it with: pip install njsscan"
                )
        except FileNotFoundError as err:
            raise RuntimeError(
                "njsscan binary not found on PATH. "
                "Install it with: pip install njsscan"
            ) from err

    async def scan(
        self,
        target_path: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        modified_files: set[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> list[Finding]:
        cmd = ["njsscan", target_path, "--json"]
        logger.info("Running njsscan: %s", " ".join(cmd))

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
                f"njsscan timed out after {timeout}s. "
                "Try scanning a smaller directory or increasing SAST_MCP_TIMEOUT."
            ) from err

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if stderr_text:
            logger.warning("njsscan stderr: %s", stderr_text)

        try:
            report = json.loads(stdout.decode("utf-8"))
        except json.JSONDecodeError as err:
            error_detail = stderr_text or "No output received from njsscan."
            raise RuntimeError(
                f"njsscan produced invalid JSON output. Details: {error_detail}"
            ) from err

        results: list[Finding] = []

        # njsscan groups findings under category keys like 'nodejs', 'templates', etc.
        for _category_key, rules in report.items():
            if not isinstance(rules, dict):
                continue

            for rule_name, findings in rules.items():
                if not isinstance(findings, list):
                    continue

                for result in findings:
                    # FIX: Parse actual severity from njsscan metadata
                    raw_severity = result.get("metadata", {}).get(
                        "severity", result.get("severity", "WARNING")
                    )
                    severity = _NJSSCAN_SEVERITY_MAP.get(
                        raw_severity.upper(), raw_severity.upper()
                    )

                    raw_confidence = result.get("metadata", {}).get(
                        "confidence", "MEDIUM"
                    )
                    confidence = raw_confidence.upper()

                    if not meets_severity_threshold(severity, min_severity):
                        continue
                    if not meets_confidence_threshold(confidence, min_confidence):
                        continue

                    # FIX: Process ALL files in the finding, not just [0]
                    files_in_finding = result.get("files", [])
                    if not files_in_finding:
                        continue

                    for file_entry in files_in_finding:
                        file_path = file_entry.get("file_path", "")
                        if not file_path:
                            continue

                        if modified_files is not None and not any(
                            file_path.endswith(mf) for mf in modified_files
                        ):
                            continue

                        line_start = file_entry.get(
                            "match_position", {}
                        ).get("line_start", result.get("line", 0))

                        context_code, ctx_start, ctx_end = get_function_context(
                            file_path, line_start
                        )

                        description = result.get("metadata", {}).get(
                            "description",
                            result.get("description", "Vulnerability found by njsscan"),
                        )

                        # Normalize to valid enum values
                        if severity not in SeverityLevel.__members__:
                            severity = "HIGH"
                        if confidence not in ConfidenceLevel.__members__:
                            confidence = "MEDIUM"

                        results.append(
                            Finding(
                                scanner="njsscan",
                                title=rule_name,
                                message=description,
                                file=file_path,
                                line_start=ctx_start,
                                line_end=ctx_end,
                                severity=SeverityLevel(severity),
                                confidence=ConfidenceLevel(confidence),
                                context=context_code,
                                language="javascript",
                                finding_hash=self.generate_hash(
                                    file_path, rule_name, context_code
                                ),
                            )
                        )

        logger.info("njsscan scan complete: %d findings", len(results))
        return results
