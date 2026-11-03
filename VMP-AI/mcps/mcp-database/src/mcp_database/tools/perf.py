from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import guard
from ..errors import McpDatabaseError, QueryValidationError
from ..formatter import effective_row_limit, mask_column_stats
from ..guard import ToolClass
from ..helpers import tls_probe
from .context import ToolContext
from .params import (
    SAFE,
    AnalyzeFlag,
    ColumnFilter,
    Conn,
    Database,
    DatabaseFilter,
    HypotheticalIndexes,
    ObjectFilter,
    ObjectName,
    Query,
    SortBy,
)
from .perf_summary import (
    _summarize_cluster,
    _summarize_config,
    _summarize_diagnosis,
    _summarize_indexes,
    _summarize_storage,
    _summarize_tls,
    _summarize_vector,
)


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    """Register the db_perf_* tools (plans, load, replication and server diagnostics)."""
    _register_perf_load(mcp, ctx)
    _register_perf_diagnostics(mcp, ctx)
    _register_perf_config(mcp, ctx)


def _register_perf_load(mcp: FastMCP, ctx: ToolContext) -> None:
    """Plan inspection and live-load tools: explain, top queries, active ops, locks, index/table/column stats."""

    @mcp.tool(annotations=SAFE)
    async def db_perf_explain(
        conn: Conn, query: Query, analyze: AnalyzeFlag = False, hypothetical_indexes: HypotheticalIndexes = None
    ) -> dict[str, Any]:
        """Execution plan (EXPLAIN FORMAT JSON / MongoDB explain). analyze=true runs the query for real
        timings and is only accepted for read queries. hypothetical_indexes simulates CREATE INDEX
        statements before planning (PostgreSQL with hypopg) without ever creating them."""
        cfg = ctx.cfg_of(conn)
        parsed = ctx.validated_read(cfg, query, ToolClass.PERF)
        return await ctx.run(
            cfg, ctx.adapter_of(cfg).explain(parsed, analyze=analyze, hypothetical_indexes=hypothetical_indexes)
        )

    @mcp.tool(annotations=SAFE)
    async def db_perf_top_queries(
        conn: Conn, sort_by: SortBy = "total_time", limit: int = 20, database: DatabaseFilter = None
    ) -> dict[str, Any]:
        """Most expensive queries: pg_stat_statements (PG), performance_schema digests (MySQL),
        profiler/system.profile (MongoDB). Errors explain how to enable the source when missing."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF, database)
        limit = effective_row_limit(limit, 20, cap=cfg.hard_row_cap)
        return {"top_queries": await ctx.run(cfg, ctx.adapter_of(cfg).top_queries(sort_by, min(limit, 200), database))}

    @mcp.tool(annotations=SAFE)
    async def db_perf_active_ops(conn: Conn, min_duration_ms: int = 0) -> dict[str, Any]:
        """What is running right now: pg_stat_activity / PROCESSLIST / currentOp, with durations."""
        cfg = ctx.cfg_of(conn)
        if not isinstance(min_duration_ms, int) or isinstance(min_duration_ms, bool) or min_duration_ms < 0:
            raise QueryValidationError(f"min_duration_ms must be a non-negative integer, got {min_duration_ms!r}")
        guard.ensure_tool_allowed(cfg, ToolClass.PERF)
        return {"active_ops": await ctx.run(cfg, ctx.adapter_of(cfg).active_ops(min_duration_ms))}

    @mcp.tool(annotations=SAFE)
    async def db_perf_blocking(conn: Conn) -> dict[str, Any]:
        """Lock waits and blocking chains: who blocks whom, for how long."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF)
        return {"blocking": await ctx.run(cfg, ctx.adapter_of(cfg).blocking())}

    @mcp.tool(annotations=SAFE)
    async def db_perf_index_stats(conn: Conn, database: DatabaseFilter = None) -> dict[str, Any]:
        """Index usage: unused/redundant/invalid indexes and their sizes."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF, database)
        return await ctx.run(cfg, ctx.adapter_of(cfg).index_stats(database))

    @mcp.tool(annotations=SAFE)
    async def db_perf_table_stats(conn: Conn, database: DatabaseFilter = None) -> dict[str, Any]:
        """Per-table/collection access stats: seq vs index scans, dead rows, fragmentation, sizes."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF, database)
        return ctx.with_cap_note(
            {"table_stats": await ctx.run(cfg, ctx.adapter_of(cfg).table_stats(database))}, table_stats=100
        )

    @mcp.tool(annotations=SAFE)
    async def db_perf_column_stats(
        conn: Conn, database: Database, object: ObjectName, column: ColumnFilter = None
    ) -> dict[str, Any]:
        """Planner statistics per column: null fraction, distinct count, correlation and most-common values
        (PostgreSQL pg_stats), index cardinality and histograms (MySQL). Value lists are masked according to
        the connection's redact_fields. MongoDB has no planner statistics and returns guidance instead."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF, database)
        rows = await ctx.run(cfg, ctx.adapter_of(cfg).column_stats(database, object, column))
        return {"columns": mask_column_stats(rows, cfg.redact_fields, cfg.redact_patterns)}


def _register_perf_diagnostics(mcp: FastMCP, ctx: ToolContext) -> None:
    """Aggregate diagnostics: one-shot triage, vector stats, cluster, health, storage and TLS."""

    @mcp.tool(annotations=SAFE)
    async def db_perf_diagnose(conn: Conn) -> dict[str, Any]:
        """One-shot performance triage: runs health, active operations, lock waits and top queries in one call,
        then summarizes findings and suggests next tools. Feature-gated sections that need an extension or
        privilege are reported as unavailable instead of failing the whole diagnosis."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF)
        adapter = ctx.adapter_of(cfg)

        async def section(coro: Any) -> Any:
            try:
                return await ctx.run(cfg, coro)
            except McpDatabaseError as exc:
                return {"unavailable": str(exc)}

        sections = {
            "health": await section(adapter.health()),
            "active_ops": await section(adapter.active_ops(0)),
            "blocking": await section(adapter.blocking()),
            "top_queries": await section(adapter.top_queries("total_time", 5)),
        }
        findings, next_steps = _summarize_diagnosis(sections)
        return {"connection": cfg.name, "sections": sections, "findings": findings, "next": next_steps}

    @mcp.tool(annotations=SAFE)
    async def db_perf_vector_stats(
        conn: Conn, database: DatabaseFilter = None, object: ObjectFilter = None
    ) -> dict[str, Any]:
        """Vector search quality diagnostics: pgvector columns/indexes with build parameters and session
        GUCs (PostgreSQL) or Atlas vectorSearch indexes with build status (MongoDB), summarized into
        findings and suggested next tools. Engines without vector search return guidance instead."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF, database)
        sections = await ctx.run(cfg, ctx.adapter_of(cfg).vector_stats(database, object))
        findings, next_steps = _summarize_vector(sections)
        return {"connection": cfg.name, "sections": sections, "findings": findings, "next": next_steps}

    @mcp.tool(annotations=SAFE)
    async def db_perf_cluster(conn: Conn) -> dict[str, Any]:
        """Cluster triage: replication topology, per-member lag and server health in one call, summarized
        into findings (lagging or broken replicas, missing primary, saturation) and suggested next tools.
        Sections that need a missing privilege are reported as unavailable instead of failing the call."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF)
        adapter = ctx.adapter_of(cfg)

        async def section(coro: Any) -> Any:
            try:
                return await ctx.run(cfg, coro)
            except McpDatabaseError as exc:
                return {"unavailable": str(exc)}

        sections = {
            "replication": await section(adapter.replication()),
            "health": await section(adapter.health()),
        }
        findings, next_steps = _summarize_cluster(sections)
        return {"connection": cfg.name, "sections": sections, "findings": findings, "next": next_steps}

    @mcp.tool(annotations=SAFE)
    async def db_perf_health(conn: Conn) -> dict[str, Any]:
        """Overall health: connection saturation, cache/buffer hit ratio, largest objects, vacuum/cache state."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF)
        return await ctx.run(cfg, ctx.adapter_of(cfg).health())

    @mcp.tool(annotations=SAFE)
    async def db_perf_storage(conn: Conn, database: DatabaseFilter = None) -> dict[str, Any]:
        """Storage triage: sizes, write-ahead/binary logs, oplog window, temp/dead-tuple pressure and (where
        the engine exposes it) filesystem usage — summarized into findings (near-full disk/memory, short
        oplog, bloat) and next tools. What is visible is what the protocol reports; no host/PVC access."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF, database)
        sections = await ctx.run(cfg, ctx.adapter_of(cfg).storage(database))
        findings, next_steps = _summarize_storage(cfg.type, sections)
        return {"connection": cfg.name, "sections": sections, "findings": findings, "next": next_steps}

    @mcp.tool(annotations=SAFE)
    async def db_perf_tls(conn: Conn) -> dict[str, Any]:
        """TLS/certificate triage: whether the server offers TLS, the negotiated protocol/cipher and the
        certificate's issuer and days-until-expiry — from a credential-free handshake, so it works before
        auth. Findings warn on soon-to-expire certs and unexpected plaintext. MySQL/SQLite return guidance."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF)
        section = await ctx.run(cfg, tls_probe.probe_tls(cfg.resolved_uri(), timeout_s=cfg.query_timeout_s))
        findings, next_steps = _summarize_tls(section)
        return {"connection": cfg.name, "tls": section, "findings": findings, "next": next_steps}


def _register_perf_config(mcp: FastMCP, ctx: ToolContext) -> None:
    """Configuration and SRE tools: config check, index advisor, replication, settings and logs."""

    @mcp.tool(annotations=SAFE)
    async def db_perf_config_check(conn: Conn) -> dict[str, Any]:
        """Configuration-vs-workload triage: cache/buffer sizing, connection headroom, eviction and
        persistence policy, autovacuum/checkpoint pressure — summarized into findings and next tools.
        Heuristics, not prescriptions: every finding names the signal behind it."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF)
        sections = await ctx.run(cfg, ctx.adapter_of(cfg).config_signals())
        findings, next_steps = _summarize_config(cfg.type, sections)
        return {"connection": cfg.name, "sections": sections, "findings": findings, "next": next_steps}

    @mcp.tool(annotations=SAFE)
    async def db_perf_index_advisor(conn: Conn, database: DatabaseFilter = None) -> dict[str, Any]:
        """Missing-index triage: unindexed foreign keys with a suggested CREATE INDEX (PostgreSQL),
        full-table-scan statements (MySQL) or collection scans (MongoDB), summarized into findings and next
        tools. On PostgreSQL, validate a suggestion with db_perf_explain hypothetical_indexes before creating."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF, database)
        sections = await ctx.run(cfg, ctx.adapter_of(cfg).index_signals(database))
        findings, next_steps = _summarize_indexes(cfg.type, sections)
        return {"connection": cfg.name, "sections": sections, "findings": findings, "next": next_steps}

    @mcp.tool(annotations=SAFE)
    async def db_perf_replication(conn: Conn) -> dict[str, Any]:
        """Cluster/replication state: replica lag (PG/MySQL), replica set members and shards (MongoDB)."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF)
        return await ctx.run(cfg, ctx.adapter_of(cfg).replication())

    @mcp.tool(annotations=SAFE)
    async def db_perf_settings(conn: Conn, pattern: str | None = None) -> dict[str, Any]:
        """Server configuration: non-default and key tuning parameters, optionally filtered by pattern."""
        cfg = ctx.cfg_of(conn)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF)
        return ctx.with_cap_note({"settings": await ctx.run(cfg, ctx.adapter_of(cfg).settings(pattern))}, settings=100)

    @mcp.tool(annotations=SAFE)
    async def db_perf_logs(conn: Conn, limit: int = 100, level: str | None = None) -> dict[str, Any]:
        """Recent server log entries (getLog / performance_schema.error_log / pg_read_file when permitted)."""
        cfg = ctx.cfg_of(conn)
        limit = effective_row_limit(limit, 100, cap=cfg.hard_row_cap)
        guard.ensure_tool_allowed(cfg, ToolClass.PERF)
        return {"logs": await ctx.run(cfg, ctx.adapter_of(cfg).logs(limit, level))}
