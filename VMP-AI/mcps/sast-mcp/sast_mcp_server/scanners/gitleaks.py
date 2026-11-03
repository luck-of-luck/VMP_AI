"""Gitleaks scanner integration for deep secret scanning in git history."""

import asyncio
import json
import logging
import os
import tempfile
from typing import Any

from sast_mcp_server.models import ConfidenceLevel, Finding, SeverityLevel
from sast_mcp_server.scanners.base import BaseScanner

logger = logging.getLogger(__name__)


class GitleaksScanner(BaseScanner):
    """Scanner implementation for Gitleaks.

    Gitleaks is a SAST tool for detecting and preventing hardcoded secrets like passwords,
    api keys, and tokens in git repos.
    """

    name = "gitleaks"
    version_command = ["gitleaks", "version"]

    async def check_dependency(self) -> None:
        """Check if gitleaks is installed and available in the system PATH."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "gitleaks", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError("Gitleaks is not installed or accessible.")
        except FileNotFoundError as err:
            raise RuntimeError("Gitleaks is not installed or accessible.") from err

    async def scan(
        self,
        target_path: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        modified_files: set[str] | None = None,
        timeout: int = 300,
    ) -> list[Finding]:
        """Run Gitleaks on the target path and parse the results.

        Args:
            target_path: Directory or file to scan.
            min_severity: Not applicable to secrets (all are considered CRITICAL/HIGH).
            min_confidence: Not strictly applicable for gitleaks, defaults used.
            modified_files: If provided, runs `gitleaks protect` on staged changes.
                            Otherwise runs `gitleaks detect` on the git history.
            timeout: Command timeout in seconds.

        Returns:
            List of parsed findings.
        """
        # Gitleaks requires a report file to output JSON
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
            report_path = tf.name

        try:
            # Determine scan mode
            is_git_repo = os.path.exists(os.path.join(target_path, ".git"))

            if is_git_repo and modified_files is not None:
                # If modified files are provided, we ideally want to check only those.
                # `gitleaks protect --staged` is used for pre-commit.
                # For MCP, we usually just run a directory scan (no-git) on modified files,
                # but Gitleaks works best with git context. We'll run a no-git scan if
                # we just want to scan specific files quickly.
                cmd = [
                    "gitleaks",
                    "detect",
                    "--no-git",
                    "--report-format", "json",
                    "--report-path", report_path,
                    "--source", target_path,
                ]
            else:
                # Full scan of history if it's a git repo, otherwise no-git directory scan
                git_flag = [] if is_git_repo else ["--no-git"]
                cmd = [
                    "gitleaks",
                    "detect",
                    "--report-format", "json",
                    "--report-path", report_path,
                    "--source", target_path,
                ] + git_flag

            logger.info("Running Gitleaks: %s", " ".join(cmd))

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
                raise RuntimeError("Gitleaks scan timed out.") from err

            report_missing = (
                not os.path.exists(report_path) or os.path.getsize(report_path) == 0
            )
            if proc.returncode not in (0, 1) and report_missing:
                stderr_text = stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"Gitleaks failed: {stderr_text}")

            if report_missing:
                return []

            with open(report_path, encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    logger.warning("Gitleaks produced invalid JSON output")
                    return []

            # Gitleaks output is a list of dictionaries, or empty list
            if not isinstance(data, list):
                return []

            findings = []
            for item in data:
                finding = self._parse_finding(item)

                # Filter by modified files if applicable
                if modified_files:
                    abs_file = os.path.abspath(os.path.join(target_path, finding.file))
                    if not any(abs_file.endswith(mf) for mf in modified_files):
                        continue

                findings.append(finding)

            # All secrets are critical, so we don't need to filter by min_severity
            # unless min_severity was somehow set higher than CRITICAL (impossible)
            return findings

        finally:
            if os.path.exists(report_path):
                os.remove(report_path)

    def _parse_finding(self, item: dict[str, Any]) -> Finding:
        """Parse a single Gitleaks finding into the standard Finding model."""

        # Leaked secrets are always CRITICAL
        severity = SeverityLevel.CRITICAL
        confidence = ConfidenceLevel.HIGH

        file_path = item.get("File", "")
        start_line = item.get("StartLine", 1)
        end_line = item.get("EndLine", start_line)
        rule_id = item.get("RuleID", "hardcoded-secret")
        description = item.get("Description", "A hardcoded secret was found.")
        secret = item.get("Secret", "")
        commit = item.get("Commit", "")
        author = item.get("Author", "")
        date = item.get("Date", "")

        message = f"{description}"
        if commit:
            message += f" Found in commit {commit[:8]} by {author} on {date}."

        title = f"Leaked Secret: {rule_id}"
        context = f"Secret match: {secret[:5]}*** (truncated for safety)"

        finding = Finding(
            scanner=self.name,
            title=title,
            message=message,
            file=file_path,
            line_start=start_line,
            line_end=end_line,
            severity=severity,
            confidence=confidence,
            context=context,
            finding_hash=self.generate_hash(file_path, title, context),
        )

        return finding
