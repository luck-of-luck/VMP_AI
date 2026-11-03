"""Custom exceptions for ast-grep MCP server."""

from typing import List, Optional

from ast_grep_mcp.constants import DisplayDefaults


class AstGrepError(Exception):
    """Base exception for all ast-grep MCP server errors."""

    pass


class AstGrepNotFoundError(AstGrepError):
    """Raised when ast-grep binary is not found in PATH."""

    def __init__(self, message: str = "ast-grep command not found") -> None:
        super().__init__(
            f"{message}\n\n"
            "Please install ast-grep:\n"
            "  - macOS: brew install ast-grep\n"
            "  - Linux: cargo install ast-grep --locked\n"
            "  - npm: npm install -g @ast-grep/cli\n"
            "  - See: https://ast-grep.github.io/guide/quick-start.html#installation"
        )


class InvalidYAMLError(AstGrepError):
    """Raised when YAML rule is invalid or malformed."""

    def __init__(self, message: str, yaml_content: Optional[str] = None) -> None:
        error_msg = f"Invalid YAML rule: {message}\n\n"
        error_msg += "YAML rules must include:\n"
        error_msg += "  - id: unique identifier\n"
        error_msg += "  - language: target language\n"
        error_msg += "  - rule: search pattern or conditions\n\n"
        error_msg += "Example:\n"
        error_msg += "  id: find-console-log\n"
        error_msg += "  language: javascript\n"
        error_msg += "  rule:\n"
        error_msg += "    pattern: console.log($$$)\n"
        if yaml_content:
            error_msg += f"\n\nProvided YAML:\n{yaml_content[: DisplayDefaults.ERROR_OUTPUT_PREVIEW_LENGTH]}"
        super().__init__(error_msg)


class ConfigurationError(AstGrepError):
    """Raised when configuration file is invalid."""

    def __init__(self, config_path: str, message: str) -> None:
        super().__init__(
            f"Configuration error in '{config_path}': {message}\n\nSee: https://ast-grep.github.io/guide/project/project-config.html"
        )


class AstGrepExecutionError(AstGrepError):
    """Raised when ast-grep command execution fails."""

    def __init__(self, command: List[str], returncode: int, stderr: str) -> None:
        error_msg = f"ast-grep command failed with exit code {returncode}\n\n"
        error_msg += f"Command: {' '.join(command)}\n\n"
        if stderr:
            error_msg += f"Error output:\n{stderr}\n\n"
        error_msg += "Common issues:\n"
        error_msg += "  - Invalid pattern syntax\n"
        error_msg += "  - Unsupported language\n"
        error_msg += "  - File path does not exist\n"
        error_msg += "  - YAML rule missing required fields\n"
        super().__init__(error_msg)


class NoMatchesError(AstGrepError):
    """Raised when no matches are found (for test_match_code_rule only)."""

    def __init__(self, message: str = "No matches found") -> None:
        super().__init__(
            f"{message}\n\n"
            "The pattern did not match any code.\n"
            "Check your pattern syntax and ensure it correctly matches the target code structure."
        )
