from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .audit import AuditLogger
from .config import ConnectionConfig
from .tools import TOOL_MODULES, ToolContext

_INSTRUCTIONS = """Multi-database MCP server for PostgreSQL, MySQL and MongoDB.
Tools take 'conn', the name of a configured connection (list them with db_schema_connections).
Tool prefixes encode risk: db_schema_/db_read_/db_perf_ never write to the database; db_write_/db_admin_ do.
SQL connections take SQL strings; MongoDB connections take JSON objects like
{"collection": "users", "operation": "find", "filter": {...}}."""


def build_server(
    registry: dict[str, ConnectionConfig],
    *,
    audit: AuditLogger | None = None,
    enabled_tools: frozenset[str] | None = None,
) -> FastMCP:
    """Assemble the FastMCP app: shared ToolContext, tool modules, and a lifespan that closes the pools.

    enabled_tools (from TOOLS/DISABLE_TOOLS) restricts which tools are registered; None registers all.
    """
    ctx = ToolContext(registry=registry, audit=audit or AuditLogger())

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[None]:
        """Close every adapter pool when the server session shuts down; adapters reopen lazily."""
        try:
            yield None
        finally:
            await ctx.close_all()

    mcp = FastMCP("mcp-database", instructions=_INSTRUCTIONS, lifespan=lifespan)
    if enabled_tools is not None:
        _restrict_registration(mcp, enabled_tools)
    for module in TOOL_MODULES:
        module.register(mcp, ctx)
    return mcp


def _restrict_registration(mcp: FastMCP, enabled: frozenset[str]) -> None:
    """Wrap mcp.tool so a tool whose function name is not in `enabled` is skipped, never registered."""
    original = mcp.tool

    def tool(*args, **kwargs):  # type: ignore[no-untyped-def]
        decorator = original(*args, **kwargs)

        def register_if_enabled(fn):  # type: ignore[no-untyped-def]
            return decorator(fn) if fn.__name__ in enabled else fn

        return register_if_enabled

    mcp.tool = tool  # type: ignore[method-assign]
