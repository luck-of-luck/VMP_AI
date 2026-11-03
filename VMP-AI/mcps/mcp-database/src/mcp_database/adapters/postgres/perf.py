from __future__ import annotations

import contextlib
from typing import Any

import psycopg
from psycopg import sql

from ...errors import GuidanceError, QueryValidationError

_TOP_QUERY_SORTS = {
    "total_time": "total_exec_time",
    "mean_time": "mean_exec_time",
    "calls": "calls",
    "rows": "rows",
}


class PgPerfMixin:
    """PostgresAdapter perf operations."""

    async def explain(
        self, query: Any, *, analyze: bool = False, hypothetical_indexes: list[str] | None = None
    ) -> dict[str, Any]:
        if hypothetical_indexes:
            return await self._explain_hypothetical(query, hypothetical_indexes, analyze=analyze)
        options = "ANALYZE, BUFFERS, FORMAT JSON" if analyze else "FORMAT JSON"
        rows = await self._fetch(f"EXPLAIN ({options}) {query}")
        plan = rows[0]["QUERY PLAN"] if rows else None
        return self._with_cost(plan)

    def _with_cost(self, plan: Any) -> dict[str, Any]:
        """Surface the planner's total cost, warning when it exceeds the connection's max_plan_cost."""
        result: dict[str, Any] = {"plan": plan}
        try:
            total_cost = plan[0]["Plan"]["Total Cost"]
        except (TypeError, KeyError, IndexError):
            return result
        result["estimated_cost"] = total_cost
        cap = self.config.max_plan_cost
        if cap is not None and total_cost > cap:
            result["cost_warning"] = f"estimated cost {total_cost} exceeds max_plan_cost {cap}"
        return result

    async def _explain_hypothetical(self, query: Any, index_ddls: list[str], *, analyze: bool) -> dict[str, Any]:
        """Plan with HypoPG session-local indexes: created, explained and reset on a single connection."""
        if analyze:
            raise QueryValidationError(
                "hypothetical indexes only affect planning; analyze=true would execute without them"
            )
        installed = await self._fetch("SELECT 1 FROM pg_extension WHERE extname = 'hypopg'")
        if not installed:
            raise GuidanceError("hypopg is not installed. Run: CREATE EXTENSION hypopg; (requires the hypopg package)")
        pool = await self._ensure_pool()
        async with pool.connection() as conn:
            try:
                await conn.execute(
                    sql.SQL("SET statement_timeout = {}").format(sql.Literal(self.config.query_timeout_s * 1000))
                )
                for ddl in index_ddls:
                    await conn.execute("SELECT hypopg_create_index(%s)", (ddl,))
                cursor = await conn.execute(f"EXPLAIN (FORMAT JSON) {query}")
                rows = await cursor.fetchall()
            finally:
                with contextlib.suppress(Exception):
                    await conn.execute("SELECT hypopg_reset()")
                with contextlib.suppress(Exception):
                    await conn.execute("RESET statement_timeout")
                await conn.rollback()
        return {"plan": rows[0]["QUERY PLAN"] if rows else None, "hypothetical_indexes": list(index_ddls)}

    async def top_queries(self, sort_by: str, limit: int, database: str | None = None) -> list[dict[str, Any]]:
        order = _TOP_QUERY_SORTS.get(sort_by)
        if order is None:
            raise QueryValidationError(f"Invalid sort_by '{sort_by}' (expected: {', '.join(_TOP_QUERY_SORTS)})")
        installed = await self._fetch("SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'")
        if not installed:
            raise GuidanceError(
                "pg_stat_statements is not installed. Run: CREATE EXTENSION pg_stat_statements; "
                "(requires shared_preload_libraries='pg_stat_statements' in postgresql.conf and a server restart)"
            )
        query = f"""
            SELECT left(s.query, 500) AS query, s.calls, s.rows,
                   round(s.total_exec_time::numeric, 1) AS total_ms,
                   round(s.mean_exec_time::numeric, 2) AS mean_ms,
                   s.shared_blks_hit, s.shared_blks_read,
                   s.temp_blks_written, s.wal_bytes
            FROM pg_stat_statements s
            JOIN pg_database d ON d.oid = s.dbid
            WHERE (%s::text IS NULL OR d.datname = %s)
            ORDER BY s.{order} DESC LIMIT %s
        """
        return await self._fetch(query, (database, database, limit))

    async def active_ops(self, min_duration_ms: int = 0) -> list[dict[str, Any]]:
        return await self._fetch(
            """
            SELECT pid, usename AS "user", datname AS database, state, wait_event_type, wait_event,
                   round(extract(epoch FROM (now() - query_start)) * 1000)::bigint AS duration_ms,
                   round(extract(epoch FROM (now() - xact_start)) * 1000)::bigint AS xact_age_ms,
                   left(query, 500) AS query
            FROM pg_stat_activity
            WHERE state <> 'idle' AND pid <> pg_backend_pid() AND query_start IS NOT NULL
              AND (now() - query_start) >= make_interval(secs => %s / 1000.0)
            ORDER BY query_start
            """,
            (min_duration_ms,),
        )

    async def blocking(self) -> list[dict[str, Any]]:
        return await self._fetch(
            """
            SELECT blocked.pid AS blocked_pid, blocked.usename AS blocked_user,
                   left(blocked.query, 300) AS blocked_query,
                   round(extract(epoch FROM (now() - blocked.query_start)) * 1000)::bigint AS blocked_for_ms,
                   blocking.pid AS blocking_pid, blocking.usename AS blocking_user,
                   left(blocking.query, 300) AS blocking_query
            FROM pg_stat_activity blocked
            JOIN LATERAL unnest(pg_blocking_pids(blocked.pid)) AS b(pid) ON true
            JOIN pg_stat_activity blocking ON blocking.pid = b.pid
            ORDER BY blocked_for_ms DESC
            """
        )

    async def index_stats(self, database: str | None = None) -> dict[str, Any]:
        query = """
            SELECT s.schemaname AS schema, s.relname AS "table", s.indexrelname AS index,
                   s.idx_scan AS scans, pg_relation_size(s.indexrelid) AS index_bytes,
                   NOT i.indisvalid AS invalid, i.indisunique AS "unique"
            FROM pg_stat_user_indexes s
            JOIN pg_index i ON i.indexrelid = s.indexrelid
        """
        params: list[Any] = []
        if database:
            query += " WHERE s.schemaname = %s"
            params.append(database)
        rows = await self._fetch(query + " ORDER BY s.idx_scan, pg_relation_size(s.indexrelid) DESC", params)
        return {
            "indexes": rows,
            "unused": [r for r in rows if r["scans"] == 0 and not r["unique"]],
            "invalid": [r for r in rows if r["invalid"]],
        }

    async def column_stats(self, database: str, obj: str, column: str | None = None) -> list[dict[str, Any]]:
        """pg_stats per column: what the planner believes about the data (masking happens at the tool layer)."""
        query = """
            SELECT attname AS column, null_frac, n_distinct, correlation,
                   most_common_vals::text AS most_common_vals, most_common_freqs
            FROM pg_stats
            WHERE schemaname = %s AND tablename = %s
        """
        params: list[Any] = [database, obj]
        if column:
            query += " AND attname = %s"
            params.append(column)
        rows = await self._fetch(query + " ORDER BY attname", params)
        if not rows:
            raise QueryValidationError(
                f"No planner statistics for '{database}.{obj}'"
                f"{f' column {column!r}' if column else ''} — check the name, or run db_admin_analyze first"
            )
        return rows

    async def table_stats(self, database: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT schemaname AS schema, relname AS "table", seq_scan, idx_scan,
                   n_live_tup AS live_rows, n_dead_tup AS dead_rows,
                   last_vacuum::text, last_autovacuum::text, last_analyze::text, last_autoanalyze::text,
                   pg_total_relation_size(relid) AS total_bytes
            FROM pg_stat_user_tables
        """
        params: list[Any] = []
        if database:
            query += " WHERE schemaname = %s"
            params.append(database)
        return await self._fetch(query + " ORDER BY pg_total_relation_size(relid) DESC LIMIT 100", params)

    async def health(self) -> dict[str, Any]:
        connections = await self._fetch(
            """
            SELECT count(*) AS used,
                   (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') AS max
            FROM pg_stat_activity
            """
        )
        cache = await self._fetch(
            """
            SELECT round(100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0), 2) AS cache_hit_pct
            FROM pg_stat_database
            """
        )
        largest = await self._fetch(
            """
            SELECT n.nspname AS schema, c.relname AS name, pg_total_relation_size(c.oid) AS total_bytes
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'p', 'm') AND n.nspname NOT LIKE 'pg\\_%' AND n.nspname <> 'information_schema'
            ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 10
            """
        )
        dead = await self._fetch(
            """
            SELECT schemaname AS schema, relname AS "table", n_dead_tup AS dead_rows
            FROM pg_stat_user_tables WHERE n_dead_tup > 0 ORDER BY n_dead_tup DESC LIMIT 10
            """
        )
        return {
            "connections": connections[0] if connections else {},
            "cache_hit_pct": cache[0]["cache_hit_pct"] if cache else None,
            "largest_tables": largest,
            "most_dead_rows": dead,
        }

    async def replication(self) -> dict[str, Any]:
        in_recovery = (await self._fetch("SELECT pg_is_in_recovery() AS in_recovery"))[0]["in_recovery"]
        result: dict[str, Any] = {"role": "replica" if in_recovery else "primary"}
        if in_recovery:
            result["receiver"] = await self._fetch("SELECT status, sender_host, sender_port FROM pg_stat_wal_receiver")
            age = await self._fetch(
                "SELECT round(extract(epoch FROM (now() - pg_last_xact_replay_timestamp())))::bigint AS replay_age_s"
            )
            result["replay_age_s"] = age[0]["replay_age_s"] if age else None
            paused = await self._fetch("SELECT pg_is_wal_replay_paused() AS paused")
            result["replay_paused"] = bool(paused[0]["paused"]) if paused else None
        else:
            replicas = await self._fetch(
                """
                SELECT client_addr::text, application_name, state, sync_state,
                       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)::bigint AS replay_lag_bytes,
                       write_lag::text, flush_lag::text, replay_lag::text
                FROM pg_stat_replication
                """
            )
            result["replicas"] = replicas
            if not replicas:
                result["note"] = "No replicas connected; this server is a standalone primary"
        return result

    async def settings(self, pattern: str | None = None) -> list[dict[str, Any]]:
        if pattern:
            return await self._fetch(
                "SELECT name, setting, unit, source, short_desc FROM pg_settings WHERE name ILIKE %s ORDER BY name",
                (f"%{pattern}%",),
            )
        return await self._fetch(
            """
            SELECT name, setting, unit, source, short_desc
            FROM pg_settings
            WHERE source NOT IN ('default', 'override')
               OR name IN ('shared_buffers', 'work_mem', 'effective_cache_size', 'max_connections',
                           'maintenance_work_mem', 'wal_level', 'max_wal_size', 'autovacuum', 'random_page_cost')
            ORDER BY name
            """
        )

    async def logs(self, limit: int = 100, level: str | None = None) -> list[dict[str, Any]]:
        try:
            rows = await self._fetch("SELECT pg_current_logfile() AS logfile")
            logfile = rows[0]["logfile"] if rows else None
            if not logfile:
                raise GuidanceError(
                    "logging_collector is off, so server logs are not readable via SQL. "
                    "Enable logging_collector in postgresql.conf or read the log file on the host."
                )
            size = (await self._fetch("SELECT size FROM pg_stat_file(%s)", (logfile,)))[0]["size"]
            offset = max(0, size - 64 * 1024)
            content = (await self._fetch("SELECT pg_read_file(%s, %s, %s) AS chunk", (logfile, offset, 64 * 1024)))[0][
                "chunk"
            ]
        except psycopg.Error as exc:
            raise GuidanceError(
                f"Cannot read the server log via SQL ({exc}). This requires the pg_read_server_files role or superuser."
            ) from None
        lines = [line for line in content.splitlines() if line.strip()]
        if level:
            lines = [line for line in lines if level.upper() in line.upper()]
        return [{"line": line} for line in lines[-limit:]]

    async def vector_stats(self, database: str | None = None, obj: str | None = None) -> dict[str, Any]:
        """Raw pgvector tuning sections: columns, indexes, session GUCs, row counts and in-flight builds."""
        version = await self._pgvector_version()
        columns = await self._fetch(
            """
            SELECT n.nspname AS schema, c.relname AS "table", a.attname AS column,
                   CASE WHEN a.atttypmod > 0 THEN a.atttypmod END AS dimensions,
                   greatest(c.reltuples, 0)::bigint AS approx_rows
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_type ty ON ty.oid = a.atttypid
            WHERE ty.typname = 'vector' AND NOT a.attisdropped AND c.relkind IN ('r', 'p', 'm')
              AND (%s::text IS NULL OR n.nspname = %s) AND (%s::text IS NULL OR c.relname = %s)
            ORDER BY 1, 2, 3
            """,
            (database, database, obj, obj),
        )
        indexes = [row for row in (await self.search_indexes(database, obj))["indexes"] if row["type"] == "vector"]
        settings = await self._fetch(
            """
            SELECT current_setting('hnsw.ef_search', true) AS "hnsw.ef_search",
                   current_setting('ivfflat.probes', true) AS "ivfflat.probes"
            """
        )
        builds = await self._fetch(
            """
            SELECT pid, relid::regclass::text AS "table", index_relid::regclass::text AS index,
                   command, phase, blocks_done, blocks_total, tuples_done, tuples_total
            FROM pg_stat_progress_create_index
            """
        )
        return {
            "extension": {"name": "vector", "version": version},
            "vector_columns": columns,
            "vector_indexes": indexes,
            "settings": settings[0] if settings else {},
            "index_builds": builds,
        }

    async def storage(self, database: str | None = None) -> dict[str, Any]:
        """Raw storage sections: database sizes, top relations, WAL, temp usage and dead tuples."""
        sections: dict[str, Any] = {}
        sections["databases"] = await self._fetch(
            "SELECT datname AS database, pg_database_size(datname) AS bytes "
            "FROM pg_database WHERE NOT datistemplate ORDER BY 2 DESC"
        )
        sections["top_relations"] = await self._fetch(
            """
            SELECT n.nspname AS schema, c.relname AS relation, c.relkind AS kind,
                   pg_total_relation_size(c.oid) AS total_bytes
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'p', 'm', 'i') AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 20
            """
        )
        try:
            wal = await self._fetch("SELECT count(*) AS files, COALESCE(sum(size), 0) AS bytes FROM pg_ls_waldir()")
            sections["wal"] = wal[0] if wal else {}
        except psycopg.Error as exc:
            sections["wal"] = {"unavailable": f"pg_ls_waldir requires pg_monitor ({exc})"}
        temp = await self._fetch(
            "SELECT COALESCE(sum(temp_files), 0) AS temp_files, COALESCE(sum(temp_bytes), 0) AS temp_bytes "
            "FROM pg_stat_database"
        )
        sections["temp"] = temp[0] if temp else {}
        sections["dead_tuples"] = await self._fetch(
            """
            SELECT schemaname AS schema, relname AS relation, n_live_tup, n_dead_tup
            FROM pg_stat_user_tables WHERE n_dead_tup > 0 ORDER BY n_dead_tup DESC LIMIT 10
            """
        )
        return sections

    async def config_signals(self) -> dict[str, Any]:
        """Raw configuration-vs-workload signals: cache ratio, connections, autovacuum, checkpoints, WAL."""
        hit = await self._fetch(
            "SELECT COALESCE(sum(blks_hit), 0) AS hits, COALESCE(sum(blks_read), 0) AS reads FROM pg_stat_database"
        )
        connections = await self._fetch(
            "SELECT count(*) AS current, current_setting('max_connections')::int AS max FROM pg_stat_activity"
        )
        autovacuum = await self._fetch(
            """
            SELECT count(*) AS behind FROM pg_stat_user_tables
            WHERE n_live_tup > 1000 AND n_dead_tup > 0.2 * n_live_tup
            """
        )
        try:
            checkpoints = await self._fetch(
                "SELECT num_timed AS timed, num_requested AS requested FROM pg_stat_checkpointer"
            )
        except psycopg.Error:
            checkpoints = await self._fetch(
                "SELECT checkpoints_timed AS timed, checkpoints_req AS requested FROM pg_stat_bgwriter"
            )
        settings = await self._fetch(
            """
            SELECT name, setting FROM pg_settings
            WHERE name IN ('shared_buffers', 'work_mem', 'wal_level', 'max_wal_senders', 'autovacuum')
            """
        )
        replicas = await self._fetch("SELECT count(*) AS streaming FROM pg_stat_replication")
        return {
            "cache": hit[0] if hit else {},
            "connections": connections[0] if connections else {},
            "autovacuum_behind_tables": autovacuum[0]["behind"] if autovacuum else 0,
            "checkpoints": checkpoints[0] if checkpoints else {},
            "settings": {row["name"]: row["setting"] for row in settings},
            "replicas_streaming": replicas[0]["streaming"] if replicas else 0,
        }

    async def index_signals(self, database: str | None = None) -> dict[str, Any]:
        """Raw index-gap signals: unindexed foreign keys (with a suggested DDL) and seq-scan-heavy tables."""
        unindexed_fks = await self._fetch(
            """
            SELECT n.nspname AS schema, src.relname AS "table", con.conname AS constraint,
                   array_to_string(ARRAY(
                       SELECT a.attname FROM unnest(con.conkey) AS k(attnum)
                       JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
                   ), ', ') AS columns
            FROM pg_constraint con
            JOIN pg_class src ON src.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = src.relnamespace
            WHERE con.contype = 'f' AND NOT EXISTS (
                SELECT 1 FROM pg_index i
                WHERE i.indrelid = con.conrelid AND i.indkey::int2[] @> con.conkey
            )
            ORDER BY 1, 2
            """
        )
        for row in unindexed_fks:
            row["suggested"] = (
                f'CREATE INDEX ON "{row["schema"]}"."{row["table"]}" '
                f"({', '.join(part.strip() for part in row['columns'].split(','))})"
            )
        seq_heavy = await self._fetch(
            """
            SELECT schemaname AS schema, relname AS "table", seq_scan, idx_scan, n_live_tup
            FROM pg_stat_user_tables
            WHERE seq_scan > 100 AND n_live_tup > 10000 AND seq_scan > COALESCE(idx_scan, 0)
            ORDER BY seq_scan DESC LIMIT 10
            """
        )
        return {"unindexed_foreign_keys": unindexed_fks, "seq_scan_heavy": seq_heavy}
