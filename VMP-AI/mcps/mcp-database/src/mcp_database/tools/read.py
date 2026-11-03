from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from .. import guard
from ..errors import QueryValidationError
from ..formatter import build_result, effective_row_limit, json_default, mask_rows
from ..guard import ToolClass
from ..helpers import mongo_query
from ..helpers import vector as vector_helpers
from .context import ToolContext
from .params import (
    SAFE,
    Conn,
    Database,
    ExportFormat,
    ExportPath,
    NumCandidates,
    ObjectName,
    Query,
    RowLimit,
    SampleN,
    SearchColumn,
    SearchFilter,
    SearchIndexName,
    TextQuery,
    TsLanguage,
    Vector,
    VectorColumn,
    VectorMetric,
)


def register(mcp: FastMCP, ctx: ToolContext) -> None:
    """Register the db_read_* tools (validated, bounded, read-only data access)."""
    _register_read_data(mcp, ctx)
    _register_read_search(mcp, ctx)
    _register_read_export(mcp, ctx)


def _register_read_data(mcp: FastMCP, ctx: ToolContext) -> None:
    """Row-oriented reads: arbitrary validated queries and table sampling."""

    @mcp.tool(annotations=SAFE)
    async def db_read_query(
        conn: Conn,
        query: Query,
        params: list[Any] | None = None,
        row_limit: RowLimit = None,
    ) -> dict[str, Any]:
        """Run a read-only query. SQL string (SELECT/UNION/VALUES) for postgres/mysql; for mongodb a JSON
        object: {"collection", "operation": find|aggregate|countDocuments|distinct|listIndexes, ...}.
        Validated fail-closed as read-only on every connection, including read_write ones."""
        cfg = ctx.cfg_of(conn)
        limit = effective_row_limit(row_limit, cfg.row_limit, cap=cfg.hard_row_cap)
        parsed = ctx.validated_read(cfg, query, ToolClass.READ)
        # For an unparameterized SQL SELECT with no LIMIT, bound the work at the database. Fetch limit+1
        # so build_result still detects "there is more". Parameterized reads are left untouched.
        if cfg.type not in ("mongodb", "redis") and not params:
            parsed = guard.apply_read_limit(parsed, cfg.type, limit + 1)
        started = time.perf_counter()
        rows = await ctx.run(cfg, ctx.adapter_of(cfg).read(parsed, params, limit))
        return build_result(
            rows,
            row_limit=limit,
            redact_fields=cfg.redact_fields,
            redact_patterns=cfg.redact_patterns,
            max_bytes=cfg.max_response_bytes,
            cap=cfg.hard_row_cap,
            execution_ms=(time.perf_counter() - started) * 1000,
            compact=cfg.compact,
        )

    @mcp.tool(annotations=SAFE)
    async def db_read_sample(conn: Conn, database: Database, object: ObjectName, n: SampleN = 10) -> dict[str, Any]:
        """Fetch up to n sample rows/documents from a table or collection."""
        cfg = ctx.cfg_of(conn)
        limit = effective_row_limit(n, cfg.row_limit, cap=cfg.hard_row_cap)
        guard.ensure_tool_allowed(cfg, ToolClass.READ, database)
        rows = await ctx.run(cfg, ctx.adapter_of(cfg).sample(database, object, limit))
        return build_result(
            rows,
            row_limit=limit,
            redact_fields=cfg.redact_fields,
            redact_patterns=cfg.redact_patterns,
            max_bytes=cfg.max_response_bytes,
            cap=cfg.hard_row_cap,
            compact=cfg.compact,
        )


def _register_read_search(mcp: FastMCP, ctx: ToolContext) -> None:
    """Search and bulk export: vector similarity, text search and row export."""

    @mcp.tool(annotations=SAFE)
    async def db_read_vector_search(
        conn: Conn,
        database: Database,
        object: ObjectName,
        column: VectorColumn,
        vector: Vector,
        metric: VectorMetric = "cosine",
        row_limit: RowLimit = None,
        filter: SearchFilter = None,
        index: SearchIndexName = None,
        num_candidates: NumCandidates = None,
    ) -> dict[str, Any]:
        """K-nearest-neighbor similarity search over a vector column/field. PostgreSQL uses pgvector
        (metric: cosine | l2 | inner_product | l1); MongoDB uses Atlas $vectorSearch (index required;
        the metric is baked into the index). The vector is a pre-computed embedding; MySQL is unsupported."""
        cfg = ctx.cfg_of(conn)
        values = vector_helpers.ensure_vector(vector)
        vector_helpers.ensure_metric(metric)
        limit = effective_row_limit(row_limit, cfg.row_limit, cap=cfg.hard_row_cap)
        if cfg.type == "mongodb":
            if filter:
                mongo_query.scan_for_forbidden_operators(filter)
            flt = filter
            candidates = vector_helpers.clamp_candidates(
                num_candidates, limit, min_c=cfg.vector_min_candidates, max_c=cfg.vector_max_candidates
            )
        else:
            flt = vector_helpers.ensure_scalar_filter(filter)
            candidates = num_candidates
        guard.ensure_tool_allowed(cfg, ToolClass.READ, database)
        started = time.perf_counter()
        rows = await ctx.run(
            cfg,
            ctx.adapter_of(cfg).vector_search(database, object, column, values, metric, limit, flt, index, candidates),
        )
        return build_result(
            rows,
            row_limit=limit,
            redact_fields=cfg.redact_fields,
            redact_patterns=cfg.redact_patterns,
            max_bytes=cfg.max_response_bytes,
            cap=cfg.hard_row_cap,
            execution_ms=(time.perf_counter() - started) * 1000,
            compact=cfg.compact,
        )

    @mcp.tool(annotations=SAFE)
    async def db_read_text_search(
        conn: Conn,
        database: Database,
        object: ObjectName,
        query: TextQuery,
        column: SearchColumn = None,
        index: SearchIndexName = None,
        row_limit: RowLimit = None,
        filter: SearchFilter = None,
        language: TsLanguage = None,
    ) -> dict[str, Any]:
        """Relevance-ranked full-text search: PostgreSQL FTS (websearch_to_tsquery), MySQL FULLTEXT
        (MATCH ... AGAINST) or MongoDB Atlas $search. The phrase is literal text, never a pattern;
        SQL engines require 'column', MongoDB searches all indexed fields when it is omitted."""
        cfg = ctx.cfg_of(conn)
        if not query.strip():
            raise QueryValidationError("'query' must be a non-empty text phrase")
        limit = effective_row_limit(row_limit, cfg.row_limit, cap=cfg.hard_row_cap)
        if cfg.type == "mongodb":
            if filter:
                mongo_query.scan_for_forbidden_operators(filter)
            flt = filter
        else:
            flt = vector_helpers.ensure_scalar_filter(filter)
        guard.ensure_tool_allowed(cfg, ToolClass.READ, database)
        started = time.perf_counter()
        rows = await ctx.run(
            cfg,
            ctx.adapter_of(cfg).text_search(
                database, object, query, column=column, index=index, limit=limit, flt=flt, language=language
            ),
        )
        return build_result(
            rows,
            row_limit=limit,
            redact_fields=cfg.redact_fields,
            redact_patterns=cfg.redact_patterns,
            max_bytes=cfg.max_response_bytes,
            cap=cfg.hard_row_cap,
            execution_ms=(time.perf_counter() - started) * 1000,
            compact=cfg.compact,
        )


def _register_read_export(mcp: FastMCP, ctx: ToolContext) -> None:
    """Bulk export of a read-only query result to a local file."""

    @mcp.tool(annotations=SAFE)
    async def db_read_export(
        conn: Conn, query: Query, path: ExportPath, format: ExportFormat = "json"
    ) -> dict[str, Any]:
        """Run a read-only query and write the result to a local file (json or csv). Bypasses the
        conversation row limit but caps at export_max_rows (EXPORT_MAX_ROWS, default 100000);
        truncated=true in the result means the cap was hit. Every export is audit-logged."""
        cfg = ctx.cfg_of(conn)
        if format not in ("json", "csv"):
            raise QueryValidationError(f"format must be 'json' or 'csv', got {format!r}")
        parsed = ctx.validated_read(cfg, query, ToolClass.READ)
        shape = guard.read_audit_shape(cfg.type, parsed)
        cap = cfg.export_max_rows
        if cfg.type not in ("mongodb", "redis"):
            parsed = guard.apply_read_limit(parsed, cfg.type, cap + 1)
        target = Path(path).expanduser()

        async def export() -> dict[str, Any]:
            """Fetch up to cap+1 rows, mask, write the json/csv file, and report whether the cap was hit."""
            rows = await ctx.adapter_of(cfg).read(parsed, None, cap)
            truncated = len(rows) > cap
            rows = mask_rows(rows[:cap], cfg.redact_fields, cfg.redact_patterns)
            target.parent.mkdir(parents=True, exist_ok=True)
            if format == "json":
                target.write_text(
                    json.dumps(rows, default=json_default, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            else:
                fieldnames = sorted({key for row in rows for key in row})
                with target.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(
                            {
                                k: json.dumps(v, default=json_default) if isinstance(v, dict | list) else v
                                for k, v in row.items()
                            }
                        )
            return {"path": str(target), "row_count": len(rows), "truncated": truncated, "format": format}

        return await ctx.run_audited(
            cfg, "db_read_export", shape, export(), detail={"path": str(target), "format": format}
        )
