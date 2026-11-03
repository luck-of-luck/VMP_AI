"""CodeQL scanner integration for deep semantic SAST analysis.

CodeQL performs two-step analysis:
1. Build a relational database from source code
2. Run security queries against the database, outputting SARIF

This provides deep data-flow and taint-tracking analysis that finds
vulnerabilities pattern-matchers miss.
"""

import asyncio
import json
import logging
import os
import tempfile

from sast_mcp_server.models import (
    Finding,
    meets_confidence_threshold,
    meets_severity_threshold,
)
from sast_mcp_server.scanners.base import BaseScanner

logger = logging.getLogger(__name__)

# CodeQL SARIF level → our SeverityLevel
_CODEQL_LEVEL_MAP = {
    "error": "HIGH",
    "warning": "MEDIUM",
    "note": "LOW",
    "none": "LOW",
}

# File extensions → CodeQL language identifiers
_CODEQL_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "javascript",  # CodeQL uses 'javascript' for both
    ".jsx": "javascript",
    ".tsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".c": "cpp",
    ".cpp": "cpp",
    ".h": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
}

# Display language names (for the Finding.language field)
_DISPLAY_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rb": "ruby",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
}

# CodeQL database creation timeout — typically slower than scanning
_CODEQL_DB_TIMEOUT = 600


class CodeQLScanner(BaseScanner):
    """Scanner integration for CodeQL (deep semantic SAST by GitHub).

    CodeQL builds a relational database from source code, then runs
    security queries with deep data-flow and taint-tracking analysis.
    It finds complex injection chains and cross-function vulnerabilities
    that pattern-based scanners miss.
    """

    name = "codeql"
    version_command = ["codeql", "version", "--format=terse"]

    async def check_dependency(self) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "codeql", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(
                    "CodeQL CLI is not installed. "
                    "Download it from: https://github.com/github/codeql-cli-binaries/releases"
                )
        except FileNotFoundError as err:
            raise RuntimeError(
                "CodeQL binary not found on PATH. "
                "Download it from: https://github.com/github/codeql-cli-binaries/releases"
            ) from err

    async def scan(
        self,
        target_path: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        modified_files: set[str] | None = None,
        timeout: int = _CODEQL_DB_TIMEOUT,
    ) -> list[Finding]:
        # Step 1: Detect primary language
        language = self._detect_codeql_language(target_path)
        if not language:
            raise RuntimeError(
                f"Could not detect a CodeQL-supported language in '{target_path}'. "
                f"Supported languages: {', '.join(sorted(set(_CODEQL_LANGUAGE_MAP.values())))}"
            )
        logger.info("CodeQL detected primary language: %s", language)

        # Step 2: Create or reuse database
        db_path = os.path.join(target_path, ".sast-mcp-codeql-db")
        if not os.path.isdir(db_path):
            await self._create_database(target_path, db_path, language, timeout)
        else:
            logger.info("Reusing cached CodeQL database at %s", db_path)

        # Step 3: Run analysis → SARIF output
        sarif_data = await self._analyze_database(db_path, language, timeout)

        # Step 4: Parse SARIF into Finding objects
        results = self._parse_sarif(
            sarif_data, target_path, min_severity, min_confidence, modified_files
        )

        logger.info("CodeQL scan complete: %d findings", len(results))
        return results

    async def _create_database(
        self, source_root: str, db_path: str, language: str, timeout: int
    ) -> None:
        """Create a CodeQL database from source code."""
        cmd = [
            "codeql", "database", "create",
            db_path,
            f"--language={language}",
            f"--source-root={source_root}",
            "--overwrite",
        ]
        logger.info("Creating CodeQL database: %s", " ".join(cmd))

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
                f"CodeQL database creation timed out after {timeout}s. "
                "This is expected for very large codebases. "
                "Increase SAST_MCP_TIMEOUT or scan a smaller directory."
            ) from err

        stderr_text = stderr.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            raise RuntimeError(
                f"CodeQL database creation failed (exit {proc.returncode}). "
                f"Details: {stderr_text[:500]}"
            )

        logger.info("CodeQL database created at %s", db_path)

    async def _analyze_database(
        self, db_path: str, language: str, timeout: int
    ) -> dict:
        """Run CodeQL analysis on a database and return SARIF data."""
        # Create a temp file for SARIF output
        sarif_fd, sarif_path = tempfile.mkstemp(suffix=".sarif", prefix="codeql-")
        os.close(sarif_fd)

        try:
            # Use the default security query suite for the language
            query_suite = (
                f"codeql/{language}-queries:codeql-suites/"
                f"{language}-security-extended.qls"
            )

            cmd = [
                "codeql", "database", "analyze",
                db_path,
                query_suite,
                "--format=sarif-latest",
                f"--output={sarif_path}",
            ]
            logger.info("Running CodeQL analysis: %s", " ".join(cmd))

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
                    f"CodeQL analysis timed out after {timeout}s. "
                    "Try increasing SAST_MCP_TIMEOUT."
                ) from err

            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                raise RuntimeError(
                    f"CodeQL analysis failed (exit {proc.returncode}). "
                    f"Details: {stderr_text[:500]}"
                )

            # Read the SARIF output
            with open(sarif_path, encoding="utf-8") as f:
                sarif_data: dict = json.load(f)

            return sarif_data

        finally:
            # Clean up temp SARIF file
            if os.path.exists(sarif_path):
                os.unlink(sarif_path)

    def _parse_sarif(
        self,
        sarif_data: dict,
        source_root: str,
        min_severity: str,
        min_confidence: str,
        modified_files: set[str] | None,
    ) -> list[Finding]:
        """Parse SARIF 2.1.0 output into Finding objects."""
        from sast_mcp_server.sarif import parse_sarif

        findings = parse_sarif(sarif_data, "codeql")

        # Apply severity/confidence filters and modified_files filter
        filtered: list[Finding] = []
        for f in findings:
            if not meets_severity_threshold(f.severity.value, min_severity):
                continue
            if not meets_confidence_threshold(f.confidence.value, min_confidence):
                continue

            if modified_files is not None and not any(
                f.file.endswith(mf) for mf in modified_files
            ):
                continue

            filtered.append(f)

        return filtered

    @staticmethod
    def _detect_codeql_language(target_path: str) -> str | None:
        """Auto-detect the primary CodeQL-supported language in a directory.

        Counts file extensions and returns the CodeQL language identifier
        for the most common supported language found.
        """
        if not os.path.isdir(target_path):
            # Single file — detect from extension
            for ext, lang in _CODEQL_LANGUAGE_MAP.items():
                if target_path.endswith(ext):
                    return lang
            return None

        ext_counts: dict[str, int] = {}
        for root, _dirs, files in os.walk(target_path):
            # Skip hidden directories, node_modules, and the CodeQL DB itself
            if any(
                part.startswith(".") or part == "node_modules"
                for part in root.replace("\\", "/").split("/")
            ):
                continue

            for filename in files:
                _, ext = os.path.splitext(filename)
                if ext in _CODEQL_LANGUAGE_MAP:
                    lang = _CODEQL_LANGUAGE_MAP[ext]
                    ext_counts[lang] = ext_counts.get(lang, 0) + 1

        if not ext_counts:
            return None

        # Return the most common language
        return max(ext_counts, key=lambda k: ext_counts[k])
