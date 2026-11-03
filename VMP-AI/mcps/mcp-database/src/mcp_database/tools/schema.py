from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import guard
from ..config import WRITE_OPS
from ..errors import QueryValidationError
from ..formatter import sanitize_error
from ..guard import ToolClass
from .context import ToolContext
from .params import SAFE, Conn, Database, DatabaseFilter, ObjectFilter, ObjectName, SearchPattern


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    """Register the db_schema_* tools (structure inspection, never data)."""
    _register_schema_structure(mcp, ctx)
    _register_schema_detail(mcp, ctx)
    _register_schema_lookup(mcp, ctx)


def _register_schema_structure(mcp: FastMCP, ctx: ToolContext) -> None:
    """Top-level structure listing: connections, databases and objects."""

    @mcp.tool(annotations=SAFE)
    async def db_schema_connections() -> dict[str, Any]:
        """List configured connections: name, database type, access mode and reachability."""
        connections = []
        for cfg in ctx.registry.values():
            item: dict[str, Any] = {"name": cfg.name, "type": cfg.type, "access_mode": cfg.access_mode}
            item["capabilities"] = ctx.adapter_of(cfg).capabilities()
            if cfg.write_ops != WRITE_OPS:
                item["write_ops"] = sorted(cfg.write_ops)
            if cfg.database_modes:
                item["database_modes"] = cfg.database_modes
            if cfg.redact_fields:
                item["redact_fields"] = list(cfg.redact_fields)
            if cfg.redact_patterns:
                item["redact_patterns"] = list(cfg.redact_patterns)
            try:
                await asyncio.wait_for(ctx.adapter_of(cfg).ping(), timeout=cfg.connect_timeout_s)
                item["status"] = "ok"
            except Exception as exc:
                item["status"] = "unreachable"
                item["error"] = sanitize_error(str(exc) or type(exc).__name__)
            connections.append(item)
        return {"connections": connections}

    @mcp.tool(annotations=SAFE)
    async def db_schema_databases(conn: Conn) -> dict[str, Any]:
        """List databases (MySQL/MongoDB) or schemas (PostgreSQL) visible on a connection."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.SCHEMA)
        return {"databases": await ctx.run(cfg, ctx.adapter_of(cfg).list_databases())}

    @mcp.tool(annotations=SAFE)
    async def db_schema_objects(conn: Conn, database: Database, object_type: str | None = None) -> dict[str, Any]:
        """List tables/views/indexes (SQL) or collections/views (MongoDB) in a database, with sizes."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.SCHEMA, database)
        return {"objects": await ctx.run(cfg, ctx.adapter_of(cfg).list_objects(database, object_type))}


def _register_schema_detail(mcp: FastMCP, ctx: ToolContext) -> None:
    """Per-object detail: search indexes, describe and DDL."""

    @mcp.tool(annotations=SAFE)
    async def db_schema_search_indexes(
        conn: Conn, database: DatabaseFilter = None, object: ObjectFilter = None
    ) -> dict[str, Any]:
        """List vector and full-text search indexes with their definitions: pgvector hnsw/ivfflat and
        tsvector indexes (PostgreSQL), FULLTEXT indexes (MySQL), Atlas search/vectorSearch indexes with
        build status and queryable flag (MongoDB)."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.SCHEMA, database)
        return await ctx.run(cfg, ctx.adapter_of(cfg).search_indexes(database, object))

    @mcp.tool(annotations=SAFE)
    async def db_schema_describe(conn: Conn, database: Database, object: ObjectName) -> dict[str, Any]:
        """Describe one object: columns/constraints/indexes (SQL) or sampled fields/indexes/stats (MongoDB)."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.SCHEMA, database)
        sample = cfg.mode_for(database) != "monitor"
        return await ctx.run(cfg, ctx.adapter_of(cfg).describe_object(database, object, sample=sample))

    @mcp.tool(annotations=SAFE)
    async def db_schema_ddl(conn: Conn, database: Database, object: ObjectName) -> dict[str, Any]:
        """Get the creation DDL of an object (CREATE TABLE / createCollection + createIndexes)."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.SCHEMA, database)
        return await ctx.run(cfg, ctx.adapter_of(cfg).get_ddl(database, object))


def _register_schema_lookup(mcp: FastMCP, ctx: ToolContext) -> None:
    """Search and access inspection: name search, relationships, users and grants."""

    @mcp.tool(annotations=SAFE)
    async def db_schema_search(conn: Conn, pattern: SearchPattern, scope: str | None = None) -> dict[str, Any]:
        """Search objects and columns by name pattern across the connection. scope: objects|columns."""
        cfg = ctx.cfg_of(conn)
        if not pattern or not pattern.strip():
            raise QueryValidationError("pattern must be a non-empty string")
        if scope not in (None, "objects", "columns"):
            raise QueryValidationError(f"scope must be 'objects' or 'columns', got {scope!r}")
        guard.ensure_tool_allowed(cfg, ToolClass.SCHEMA)
        return ctx.with_cap_note(
            await ctx.run(cfg, ctx.adapter_of(cfg).search(pattern.strip(), scope)), objects=100, columns=200
        )

    @mcp.tool(annotations=SAFE)
    async def db_schema_relationships(conn: Conn, database: Database, object: ObjectFilter = None) -> dict[str, Any]:
        """Foreign-key graph of a database or object (PostgreSQL/MySQL; MongoDB returns an empty list)."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.SCHEMA, database)
        return await ctx.run(cfg, ctx.adapter_of(cfg).relationships(database, object))

    @mcp.tool(annotations=SAFE)
    async def db_schema_users(conn: Conn, user: str | None = None) -> dict[str, Any]:
        """List database users/roles and their attributes. Never returns password hashes."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.SCHEMA)
        return {"users": await ctx.run(cfg, ctx.adapter_of(cfg).users(user))}

    @mcp.tool(annotations=SAFE)
    async def db_schema_grants(conn: Conn, user: str | None = None, object: ObjectFilter = None) -> dict[str, Any]:
        """Effective permissions: what a user can do, or who can access an object."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.SCHEMA)
        return {"grants": await ctx.run(cfg, ctx.adapter_of(cfg).grants(user, object))}
