class McpDatabaseError(Exception):
    """Base class for user-facing tool errors."""


class ConfigError(McpDatabaseError):
    """The connection configuration (env vars / parsed fields) is invalid or incomplete."""


class UnknownConnectionError(McpDatabaseError):
    """The requested 'conn' name is not in the registry; the message lists the configured ones."""

    def __init__(self, name: str, known: list[str]) -> None:
        available = ", ".join(sorted(known)) or "none"
        super().__init__(f"Unknown connection '{name}'. Configured connections: {available}")


class AccessDeniedError(McpDatabaseError):
    """The connection's access mode, database_modes or write_ops forbids this tool call."""


class QueryValidationError(McpDatabaseError):
    """The query or argument failed validation and was rejected before touching the database."""


class UnsupportedOperationError(McpDatabaseError):
    """The operation exists but this engine cannot perform it."""


class GuidanceError(McpDatabaseError):
    """The target database lacks something this tool needs; the message explains how to enable it."""
