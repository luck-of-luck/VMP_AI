"""Console logger utility for scripts and tests.

This module provides a simple abstraction over print() statements that allows
for consistent logging across CLI tools, scripts, and test utilities while
maintaining compatibility with existing code.

IMPORTANT: This module intentionally uses print() statements rather than
the logging module because it's designed specifically for console output
in CLI tools and scripts. The print() calls here are the correct implementation,
not a code smell. This is a console output utility, not a logging utility.

Usage:
    from ast_grep_mcp.utils.console_logger import console

    # Basic output (replaces print())
    console.log("Processing files...")

    # With formatting
    console.log(f"Found {count} matches")

    # Error output
    console.error("Failed to process file")

    # Success messages
    console.success("Migration complete!")

    # JSON output
    console.json({"result": "data"})

    # Control verbosity
    console.set_quiet(True)  # Suppress normal output
    console.set_verbose(True)  # Show debug messages
"""

import json
import sys
from typing import Any, Dict, Optional

from ast_grep_mcp.constants import FormattingDefaults


class ConsoleLogger:
    """Simple console logger for scripts and CLI tools.

    Provides a print() replacement with better control over output,
    while maintaining the simplicity needed for CLI tools and scripts.
    """

    def __init__(self, quiet: bool = False, verbose: bool = False) -> None:
        """Initialize console logger.

        Args:
            quiet: If True, suppress normal log output
            verbose: If True, show debug messages
        """
        self.quiet = quiet
        self.verbose = verbose

    def set_quiet(self, quiet: bool) -> None:
        """Set quiet mode (suppress normal output).

        Args:
            quiet: If True, suppress normal log output
        """
        self.quiet = quiet

    def set_verbose(self, verbose: bool) -> None:
        """Set verbose mode (show debug messages).

        Args:
            verbose: If True, show debug messages
        """
        self.verbose = verbose

    def log(self, message: str = "", **kwargs: Any) -> None:
        """Output a normal log message.

        Equivalent to print() but respects quiet mode.

        Args:
            message: Message to output
            **kwargs: Additional arguments passed to print()
        """
        if not self.quiet:
            print(message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Output an info message.

        Alias for log() for semantic clarity.

        Args:
            message: Message to output
            **kwargs: Additional arguments passed to print()
        """
        self.log(message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Output a debug message.

        Only shown when verbose mode is enabled.

        Args:
            message: Debug message to output
            **kwargs: Additional arguments passed to print()
        """
        if self.verbose:
            print(f"[DEBUG] {message}", **kwargs)

    def success(self, message: str, **kwargs: Any) -> None:
        """Output a success message.

        Args:
            message: Success message to output
            **kwargs: Additional arguments passed to print()
        """
        if not self.quiet:
            print(f"✓ {message}", **kwargs)

    def _log_to_stderr(self, prefix: str, message: str, **kwargs: Any) -> None:
        """Output a prefixed message to stderr. Always shown regardless of quiet mode.

        Note:
            ``file=sys.stderr`` is passed explicitly to ``print``. If a caller
            also passes ``file=`` via ``**kwargs`` a ``TypeError`` will be raised
            (duplicate keyword argument). Callers must not include ``file`` in
            kwargs. This is a pre-existing limitation, not a regression.
        """
        print(f"{prefix}: {message}", file=sys.stderr, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Output an error message to stderr.

        Always shown regardless of quiet mode.

        Args:
            message: Error message to output
            **kwargs: Additional arguments passed to print()
        """
        self._log_to_stderr("ERROR", message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Output a warning message to stderr.

        Always shown regardless of quiet mode.

        Args:
            message: Warning message to output
            **kwargs: Additional arguments passed to print()
        """
        self._log_to_stderr("WARNING", message, **kwargs)

    def json(self, data: Dict[str, Any], indent: Optional[int] = 2, **kwargs: Any) -> None:
        """Output data as JSON.

        Useful for programmatic consumption of script output.

        Args:
            data: Data to serialize as JSON
            indent: JSON indentation level (default: 2)
            **kwargs: Additional arguments passed to print()
        """
        if not self.quiet:
            print(json.dumps(data, indent=indent), **kwargs)

    def separator(self, char: str = "=", length: int = FormattingDefaults.SEPARATOR_LENGTH, **kwargs: Any) -> None:
        """Output a separator line.

        Args:
            char: Character to use for separator
            length: Length of separator line
            **kwargs: Additional arguments passed to print()
        """
        if not self.quiet:
            print(char * length, **kwargs)

    def header(self, message: str, **kwargs: Any) -> None:
        """Output a header with separator lines.

        Args:
            message: Header message
            **kwargs: Additional arguments passed to print()
        """
        if not self.quiet:
            self.separator()
            print(message, **kwargs)
            self.separator()

    def blank(self, count: int = 1) -> None:
        """Output blank lines.

        Args:
            count: Number of blank lines to output
        """
        if not self.quiet:
            for _ in range(count):
                print()


# Global console logger instance
console = ConsoleLogger()


# Convenience functions for backward compatibility
def log(message: str = "", **kwargs: Any) -> None:
    """Output a log message. Wrapper around console.log()."""
    console.log(message, **kwargs)


def error(message: str, **kwargs: Any) -> None:
    """Output an error message. Wrapper around console.error()."""
    console.error(message, **kwargs)


def success(message: str, **kwargs: Any) -> None:
    """Output a success message. Wrapper around console.success()."""
    console.success(message, **kwargs)
