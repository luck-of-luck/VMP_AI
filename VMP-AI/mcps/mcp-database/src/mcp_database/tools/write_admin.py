from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import guard
from ..errors import GuidanceError, QueryValidationError
from ..guard import ToolClass
from .context import ToolContext
from .params import (
    DESTRUCTIVE,
    MAINTENANCE,
    ClusterAction,
    ClusterSeconds,
    Conn,
    Database,
    DryRun,
    ExpectedMaxRows,
    IndexAction,
    IndexDefinition,
    IndexName,
    ObjectFilter,
    ObjectName,
    TargetId,
    WriteQuery,
)


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    """Register the destructive db_write_/db_admin_ tools (mode-gated and audit-logged)."""
    _register_write(mcp, ctx)
    _register_admin(mcp, ctx)


def _register_write(mcp: FastMCP, ctx: ToolContext) -> None:
    """Data and index mutations plus cluster actions: write query, search index, cluster."""

    @mcp.tool(annotations=DESTRUCTIVE)
    async def db_write_query(
        conn: Conn,
        query: WriteQuery,
        params: list[Any] | None = None,
        dry_run: DryRun = False,
        expected_max_rows: ExpectedMaxRows = None,
    ) -> dict[str, Any]:
        """Run DML/DDL (SQL) or a MongoDB write operation (insertMany, updateMany, deleteMany, createIndex...).
        Requires a read_write connection. dry_run=true executes and rolls back, reporting the impact
        (rejected for MySQL DDL, which commits implicitly and cannot be rolled back).
        expected_max_rows aborts with rollback if the write would affect more rows. An UPDATE/DELETE with
        no WHERE (or a MongoDB updateMany/deleteMany with an empty filter) is rejected unless you pass
        dry_run=true or expected_max_rows to confirm you mean to affect every row."""
        cfg = ctx.cfg_of(conn)
        if expected_max_rows is not None and (
            isinstance(expected_max_rows, bool) or not isinstance(expected_max_rows, int) or expected_max_rows < 0
        ):
            raise QueryValidationError(f"expected_max_rows must be a non-negative integer, got {expected_max_rows!r}")
        parsed, op, audit_shape = ctx.write_context(cfg, query, expected_max_rows=expected_max_rows, dry_run=dry_run)
        if dry_run and op == "ddl" and cfg.type == "mysql":
            raise GuidanceError(
                "MySQL commits DDL implicitly, so dry_run cannot roll it back and would report "
                "'not applied' for a change that already happened. Run without dry_run, or rehearse "
                "the statement on a disposable database."
            )
        result = await ctx.run_audited(
            cfg,
            "db_write_query",
            audit_shape,
            ctx.adapter_of(cfg).write(parsed, params, dry_run=dry_run, expected_max_rows=expected_max_rows),
            dry_run=dry_run,
        )
        return {**result, "operation": op}

    @mcp.tool(annotations=DESTRUCTIVE)
    async def db_write_search_index(
        conn: Conn,
        database: Database,
        object: ObjectName,
        action: IndexAction,
        name: IndexName,
        definition: IndexDefinition = None,
    ) -> dict[str, Any]:
        """Create, update or drop a vector/full-text search index: pgvector hnsw/ivfflat (PostgreSQL),
        FULLTEXT (MySQL) or Atlas search/vectorSearch (MongoDB, builds asynchronously). Gated as DDL
        (read_write connection with 'ddl' in write_ops) and audit-logged."""
        cfg = ctx.cfg_of(conn)
        if action not in ("create", "update", "drop"):
            raise QueryValidationError(f"Unknown action '{action}' (supported: create, update, drop)")
        if not name or not name.strip():
            raise QueryValidationError("'name' must be a non-empty index name")
        guard.ensure_tool_allowed(cfg, ToolClass.WRITE, database)
        guard.ensure_write_op_allowed(cfg, "ddl")
        return await ctx.run_audited(
            cfg,
            "db_write_search_index",
            {"database": database, "object": object, "action": action, "name": name, "definition": definition},
            ctx.adapter_of(cfg).search_index_write(database, object, action, name, definition),
        )

    @mcp.tool(annotations=MAINTENANCE)
    async def db_admin_cluster(conn: Conn, action: ClusterAction, seconds: ClusterSeconds = None) -> dict[str, Any]:
        """Run one cluster/replication action: promote (PostgreSQL replica), start_replica/stop_replica
        (MySQL), step_down/freeze (MongoDB replica set). Actions outside the engine's set return guidance.
        Requires a read_write connection; every call is audit-logged."""
        cfg = ctx.cfg_of(conn)
        known = ("promote", "pause_replay", "resume_replay", "start_replica", "stop_replica", "step_down", "freeze")
        if action not in known:
            raise QueryValidationError(f"Unknown action '{action}' (supported: {', '.join(known)})")
        if seconds is not None and (
            isinstance(seconds, bool) or not isinstance(seconds, int) or not 0 <= seconds <= 86400
        ):
            raise QueryValidationError(f"'seconds' must be an integer between 0 and 86400, got {seconds!r}")
        guard.ensure_tool_allowed(cfg, ToolClass.ADMIN)
        return await ctx.run_audited(
            cfg,
            "db_admin_cluster",
            {"action": action, "seconds": seconds},
            ctx.adapter_of(cfg).cluster_action(action, seconds),
        )


def _register_admin(mcp: FastMCP, ctx: ToolContext) -> None:
    """Operational admin: kill operations, analyze and maintenance."""

    @mcp.tool(annotations=MAINTENANCE)
    async def db_admin_kill(conn: Conn, target_id: TargetId, force: bool = False) -> dict[str, Any]:
        """Cancel (default) or terminate (force=true) a running operation by pid/thread id/opid.
        Requires a read_write connection."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.ADMIN)
        return await ctx.run_audited(
            cfg,
            "db_admin_kill",
            {"target_id": target_id, "force": force},
            ctx.adapter_of(cfg).kill(target_id, force=force),
        )

    @mcp.tool(annotations=MAINTENANCE)
    async def db_admin_analyze(conn: Conn, database: Database, object: ObjectFilter = None) -> dict[str, Any]:
        """Refresh planner statistics: ANALYZE (PG) / ANALYZE TABLE (MySQL). MongoDB has no equivalent.
        Requires a read_write connection."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.ADMIN, database)
        return await ctx.run_audited(
            cfg,
            "db_admin_analyze",
            {"database": database, "object": object},
            ctx.adapter_of(cfg).analyze(database, object),
        )

    @mcp.tool(annotations=MAINTENANCE)
    async def db_admin_maintain(
        conn: Conn, database: Database, object: ObjectName, action: str | None = None
    ) -> dict[str, Any]:
        """Physical maintenance to reclaim space: VACUUM (PG), OPTIMIZE TABLE (MySQL), compact (MongoDB).
        May take locks; requires a read_write connection."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.ADMIN, database)
        return await ctx.run_audited(
            cfg,
            "db_admin_maintain",
            {"database": database, "object": object, "action": action},
            ctx.adapter_of(cfg).maintain(database, object, action),
        )
