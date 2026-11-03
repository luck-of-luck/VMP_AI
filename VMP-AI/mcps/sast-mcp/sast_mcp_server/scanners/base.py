"""Base scanner abstract class with shared utilities."""

import asyncio
import hashlib
import logging
import re
from abc import ABC, abstractmethod
from typing import ClassVar

from sast_mcp_server.models import Finding

logger = logging.getLogger(__name__)

# Default subprocess timeout in seconds (overridable via SAST_MCP_TIMEOUT env var)
DEFAULT_TIMEOUT = 300

_VERSION_RE = re.compile(r"\d+\.\d+(?:\.\d+)?")


class BaseScanner(ABC):
    """Abstract base class for all SAST scanner integrations.

    Subclasses MUST set the ``name`` class attribute to their registry key
    (e.g. ``"bandit"``). It is used both as the ``Finding.scanner`` value and
    by callers that persist results keyed by scanner name.
    """

    #: Registry key / display name for this scanner. Overridden by subclasses.
    name: ClassVar[str] = ""

    #: Command that prints the tool version (e.g. ``["semgrep", "--version"]``).
    #: Subclasses set this to enable :meth:`get_version`.
    version_command: ClassVar[list[str] | None] = None

    async def get_version(self) -> str | None:
        """Return the installed scanner version, or None if undetectable.

        Best-effort: runs ``version_command`` and extracts the first
        version-like token. Never raises — returns None on any failure.
        """
        if not self.version_command:
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                *self.version_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
        except (FileNotFoundError, OSError, asyncio.TimeoutError):
            return None
        text = out.decode("utf-8", errors="replace").strip()
        if not text:
            return None
        match = _VERSION_RE.search(text)
        return match.group(0) if match else text.splitlines()[0][:40]

    @abstractmethod
    async def check_dependency(self) -> None:
        """Verify the scanner binary is available.

        Raises:
            RuntimeError: If the scanner binary is not installed or not accessible.
        """

    @abstractmethod
    async def scan(
        self,
        target_path: str,
        min_severity: str = "LOW",
        min_confidence: str = "LOW",
        modified_files: set[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> list[Finding]:
        """Run the scan and return enriched findings.

        Args:
            target_path: Absolute path to the directory or file to scan.
            min_severity: Minimum severity threshold (LOW, MEDIUM, HIGH, CRITICAL).
            min_confidence: Minimum confidence threshold (LOW, MEDIUM, HIGH).
            modified_files: If set, only include findings in these files.
            timeout: Subprocess timeout in seconds.

        Returns:
            List of Finding objects.
        """

    @staticmethod
    def generate_hash(file_path: str, title: str, code_snippet: str = "") -> str:
        """Generate a stable finding hash that is resilient to line-number changes.

        Uses file_path + rule title + a hash of the code context, so minor
        reformatting won't change the hash but moving the vulnerable code to
        a completely different location will.
        """
        # Normalize: strip whitespace from snippet to resist formatting changes
        normalized_snippet = "".join(code_snippet.split()) if code_snippet else ""
        payload = f"{file_path}:{title}:{normalized_snippet}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
