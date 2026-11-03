"""Shared context managers for MCP tool error handling, timing, and Sentry capture."""

import time
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Generator

import sentry_sdk

from ast_grep_mcp.constants import DisplayDefaults, FormattingDefaults
from ast_grep_mcp.core.logging import get_logger


@dataclass
class ToolRun:
    """Handle yielded by tool_context; collects extra fields for the completion log."""

    start_time: float
    completion_fields: dict[str, Any] = field(default_factory=dict)

    def add_completion_fields(self, **fields: Any) -> None:
        """Attach result-derived fields to the automatic tool_completed log."""
        self.completion_fields.update(fields)


def _handle_tool_error(tool_name: str, start_time: float, e: Exception, sentry_extras: dict[str, Any], *, logger: Any = None) -> None:
    """Log error and capture to Sentry for a failed tool invocation."""
    execution_time = time.time() - start_time
    if logger is None:
        logger = get_logger(f"tool.{tool_name}")
    logger.error(
        "tool_failed",
        tool=tool_name,
        status="failed",
        execution_time_seconds=round(execution_time, FormattingDefaults.ROUNDING_PRECISION),
        error=str(e)[: DisplayDefaults.ERROR_OUTPUT_PREVIEW_LENGTH],
    )
    sentry_sdk.capture_exception(
        e,
        extras={
            "tool": tool_name,
            **sentry_extras,
            "execution_time_seconds": round(execution_time, FormattingDefaults.ROUNDING_PRECISION),
        },
    )


def _log_tool_completed(tool_name: str, run: ToolRun) -> None:
    """Log the tool_completed event with execution time and collected fields."""
    get_logger(f"tool.{tool_name}").info(
        "tool_completed",
        tool=tool_name,
        status="success",
        execution_time_seconds=round(time.time() - run.start_time, FormattingDefaults.ROUNDING_PRECISION),
        **run.completion_fields,
    )


@contextmanager
def tool_context(tool_name: str, **sentry_extras: Any) -> Generator[ToolRun, None, None]:
    """Context manager for tool error handling, timing, and Sentry capture.

    On success: logs tool_completed with execution_time_seconds plus any fields
    the caller attached via the yielded ToolRun.
    On exception: logs error, captures to Sentry, and re-raises.

    Usage::

        with tool_context("my_tool", project_folder=folder) as run:
            result = do_work()
            run.add_completion_fields(items_found=len(result))
            return result
    """
    run = ToolRun(start_time=time.time())
    try:
        yield run
    except Exception as e:
        _handle_tool_error(tool_name, run.start_time, e, sentry_extras)
        raise
    _log_tool_completed(tool_name, run)


@asynccontextmanager
async def async_tool_context(tool_name: str, **sentry_extras: Any) -> AsyncGenerator[ToolRun, None]:
    """Async context manager for tool error handling, timing, and Sentry capture.

    Identical to tool_context but for use with ``async with``.

    Usage::

        async with async_tool_context("my_tool", type_name=name) as run:
            result = await do_async_work()
            run.add_completion_fields(items_found=len(result))
            return result
    """
    run = ToolRun(start_time=time.time())
    try:
        yield run
    except Exception as e:
        _handle_tool_error(tool_name, run.start_time, e, sentry_extras)
        raise
    _log_tool_completed(tool_name, run)
