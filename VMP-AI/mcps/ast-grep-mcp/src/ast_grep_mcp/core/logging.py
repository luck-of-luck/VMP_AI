"""Logging configuration for ast-grep MCP server."""

import logging
import sys
from typing import Any, List, Optional

import structlog

_log_file_handle: Optional[Any] = None


def configure_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Configure structured logging with JSON output.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for logging (stderr by default)
    """
    # Convert log level string to int
    level_mapping = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    numeric_level = level_mapping.get(log_level.upper(), logging.INFO)

    # Configure processors for structured logging
    processors: List[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]

    # Configure structlog
    global _log_file_handle
    if log_file is not None:
        if _log_file_handle is not None:
            _log_file_handle.close()
        _log_file_handle = open(log_file, "a")  # noqa: SIM115
    log_sink = _log_file_handle if log_file is not None else sys.stderr
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        context_class=dict,
        logger_factory=structlog.WriteLoggerFactory(file=log_sink),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically module or tool name)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)
