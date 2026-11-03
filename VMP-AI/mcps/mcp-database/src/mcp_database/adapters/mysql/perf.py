from __future__ import annotations

from typing import Any

from pymysql.err import MySQLError

from ...errors import GuidanceError, QueryValidationError

_TOP_QUERY_SORTS = {
    "total_time": "sum_timer_wait",
    "mean_time": "avg_timer_wait",
    "calls": "count_star",
    "rows": "sum_rows_examined",
}


class MyPerfMixin:
    """MySQLAdapter perf operations."""

    async def explain(
        self, query: Any, *, analyze: bool = False, hypothetical_indexes: list[str] | None = None
    ) -> dict[str, Any]:
        if hypothetical_indexes:
            raise GuidanceError("hypothetical indexes require PostgreSQL with the hypopg extension")
        prefix = "EXPLAIN ANALYZE" if analyze else "EXPLAIN FORMAT=JSON"
        rows = await self._fetch(f"{prefix} {query}")
        return {"plan": rows}

    async def top_queries(self, sort_by: str, limit: int, database: str | None = None) -> list[dict[str, Any]]:
        order = _TOP_QUERY_SORTS.get(sort_by)
        if order is None:
            raise QueryValidationError(f"Invalid sort_by '{sort_by}' (expected: {', '.join(_TOP_QUERY_SORTS)})")
        query = f"""
            SELECT LEFT(digest_text, 500) AS query, schema_name AS `database`, count_star AS calls,
                   ROUND(sum_timer_wait / 1e9, 1) AS total_ms, ROUND(avg_timer_wait / 1e9, 2) AS mean_ms,
                   sum_rows_examined AS rows_examined, sum_rows_sent AS rows_sent,
                   sum_no_index_used AS no_index_used
            FROM performance_schema.events_statements_summary_by_digest
            WHERE digest_text IS NOT NULL AND (%s IS NULL OR schema_name = %s)
            ORDER BY {order} DESC LIMIT %s
        """
        try:
            return await self._fetch(query, (database, database, limit))
        except MySQLError as exc:
            raise GuidanceError(
                f"Cannot read performance_schema ({exc}). Ensure performance_schema=ON and the user can SELECT it."
            ) from None

    async def active_ops(self, min_duration_ms: int = 0) -> list[dict[str, Any]]:
        return await self._fetch(
            """
            SELECT p.id AS pid, p.user, p.db AS `database`, p.command, p.state,
                   p.time * 1000 AS duration_ms,
                   TIMESTAMPDIFF(SECOND, t.trx_started, NOW()) * 1000 AS trx_age_ms,
                   LEFT(p.info, 500) AS query
            FROM information_schema.processlist p
            LEFT JOIN information_schema.innodb_trx t ON t.trx_mysql_thread_id = p.id
            WHERE p.command <> 'Sleep' AND p.id <> CONNECTION_ID() AND p.time * 1000 >= %s
            ORDER BY p.time DESC
            """,
            (min_duration_ms,),
        )

    async def blocking(self) -> list[dict[str, Any]]:
        try:
            return await self._fetch(
                """
                SELECT waiting_pid AS blocked_pid, LEFT(waiting_query, 300) AS blocked_query,
                       wait_age_secs * 1000 AS blocked_for_ms,
                       blocking_pid, LEFT(blocking_query, 300) AS blocking_query,
                       locked_table, locked_type
                FROM sys.innodb_lock_waits
                """
            )
        except MySQLError as exc:
            raise GuidanceError(
                f"Cannot read sys.innodb_lock_waits ({exc}). Requires MySQL 5.7+ with the sys schema "
                "and the PROCESS privilege."
            ) from None

    async def index_stats(self, database: str | None = None) -> dict[str, Any]:
        try:
            unused_query = (
                "SELECT object_schema AS `database`, object_name AS `table`, index_name FROM sys.schema_unused_indexes"
            )
            redundant_query = """
                SELECT table_schema AS `database`, table_name AS `table`,
                       redundant_index_name, dominant_index_name
                FROM sys.schema_redundant_indexes
            """
            params: list[Any] = []
            if database:
                unused_query += " WHERE object_schema = %s"
                redundant_query += " WHERE table_schema = %s"
                params = [database]
            return {
                "unused": await self._fetch(unused_query, params or None),
                "redundant": await self._fetch(redundant_query, params or None),
            }
        except MySQLError as exc:
            raise GuidanceError(f"Cannot read the sys schema ({exc}). Requires MySQL 5.7+.") from None

    async def column_stats(self, database: str, obj: str, column: str | None = None) -> list[dict[str, Any]]:
        """Index cardinality plus histogram (when built) per column; masking happens at the tool layer."""
        query = """
            SELECT c.column_name AS `column`, s.cardinality,
                   cs.histogram->>'$."number-of-buckets-specified"' AS histogram_buckets,
                   cs.histogram AS histogram
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT table_schema, table_name, column_name, MAX(cardinality) AS cardinality
                FROM information_schema.statistics GROUP BY table_schema, table_name, column_name
            ) s ON s.table_schema = c.table_schema AND s.table_name = c.table_name
               AND s.column_name = c.column_name
            LEFT JOIN information_schema.column_statistics cs
                ON cs.schema_name = c.table_schema AND cs.table_name = c.table_name
               AND cs.column_name = c.column_name
            WHERE c.table_schema = %s AND c.table_name = %s
        """
        params: list[Any] = [database, obj]
        if column:
            query += " AND c.column_name = %s"
            params.append(column)
        rows = await self._fetch(query + " ORDER BY c.column_name", params)
        if not rows:
            raise QueryValidationError(
                f"No statistics for '{database}.{obj}'{f' column {column!r}' if column else ''} — check the name; "
                "histograms require ANALYZE TABLE ... UPDATE HISTOGRAM"
            )
        return rows

    async def table_stats(self, database: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT table_schema AS `database`, table_name AS `table`, engine,
                   COALESCE(table_rows, 0) AS approx_rows,
                   COALESCE(data_length, 0) AS data_bytes, COALESCE(index_length, 0) AS index_bytes,
                   COALESCE(data_free, 0) AS fragmented_bytes
            FROM information_schema.tables
            WHERE table_type = 'BASE TABLE'
              AND table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
        """
        params: list[Any] = []
        if database:
            query += " AND table_schema = %s"
            params.append(database)
        return await self._fetch(query + " ORDER BY data_length + index_length DESC LIMIT 100", params or None)

    async def health(self) -> dict[str, Any]:
        status_rows = await self._fetch(
            """
            SHOW GLOBAL STATUS WHERE Variable_name IN
            ('Threads_connected', 'Threads_running', 'Uptime',
             'Innodb_buffer_pool_read_requests', 'Innodb_buffer_pool_reads', 'Slow_queries')
            """
        )
        status = {row["Variable_name"]: row["Value"] for row in status_rows}
        limits = await self._fetch("SELECT @@max_connections AS max_connections, @@version AS version")
        requests = int(status.get("Innodb_buffer_pool_read_requests", 0) or 0)
        misses = int(status.get("Innodb_buffer_pool_reads", 0) or 0)
        hit_pct = round(100.0 * (1 - misses / requests), 2) if requests else None
        largest = await self.table_stats()
        return {
            "version": limits[0]["version"],
            "connections": {
                "used": int(status.get("Threads_connected", 0)),
                "running": int(status.get("Threads_running", 0)),
                "max": limits[0]["max_connections"],
            },
            "buffer_pool_hit_pct": hit_pct,
            "slow_queries": int(status.get("Slow_queries", 0)),
            "uptime_s": int(status.get("Uptime", 0)),
            "largest_tables": largest[:10],
        }

    async def replication(self) -> dict[str, Any]:
        replica_status = await self._fetch("SHOW REPLICA STATUS")
        if replica_status:
            keys = (
                "Source_Host",
                "Replica_IO_Running",
                "Replica_SQL_Running",
                "Seconds_Behind_Source",
                "Last_Error",
            )
            return {
                "role": "replica",
                "status": [
                    {k: row.get(k, row.get(self._STATUS_ALIASES.get(k, k))) for k in keys} for row in replica_status
                ],
            }
        replicas = await self._fetch(self._SHOW_REPLICAS)
        return {
            "role": "source" if replicas else "standalone",
            "replicas": replicas,
            "note": None if replicas else "This server is not replicating and has no connected replicas",
        }

    async def settings(self, pattern: str | None = None) -> list[dict[str, Any]]:
        if pattern:
            return await self._fetch("SHOW GLOBAL VARIABLES LIKE %s", (f"%{pattern}%",))
        return await self._fetch(
            """
            SHOW GLOBAL VARIABLES WHERE Variable_name IN
            ('max_connections', 'innodb_buffer_pool_size', 'innodb_log_file_size', 'max_execution_time',
             'tmp_table_size', 'sort_buffer_size', 'join_buffer_size', 'slow_query_log', 'long_query_time',
             'sync_binlog', 'innodb_flush_log_at_trx_commit')
            """
        )

    async def logs(self, limit: int = 100, level: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT logged AS ts, prio AS level, error_code, subsystem, LEFT(data, 500) AS message
            FROM performance_schema.error_log
        """
        params: list[Any] = []
        if level:
            query += " WHERE prio = %s"
            params.append(level.capitalize())
        query += " ORDER BY logged DESC LIMIT %s"
        params.append(limit)
        try:
            return await self._fetch(query, params)
        except MySQLError as exc:
            raise GuidanceError(f"Cannot read performance_schema.error_log ({exc}). Requires MySQL 8.0.22+.") from None

    async def storage(self, database: str | None = None) -> dict[str, Any]:
        """Raw storage sections: schema sizes, binary logs and on-disk temp table pressure."""
        sections: dict[str, Any] = {}
        sections["schemas"] = await self._fetch(
            """
            SELECT table_schema AS `database`,
                   COALESCE(SUM(data_length + index_length), 0) AS bytes
            FROM information_schema.tables
            WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
            GROUP BY table_schema ORDER BY 2 DESC
            """
        )
        try:
            logs = await self._fetch("SHOW BINARY LOGS")
            sections["binary_logs"] = {
                "count": len(logs),
                "bytes": sum(int(row.get("File_size", 0) or 0) for row in logs),
            }
        except MySQLError as exc:
            sections["binary_logs"] = {"unavailable": str(exc)}
        tmp = await self._fetch(
            "SHOW GLOBAL STATUS WHERE Variable_name IN ('Created_tmp_tables', 'Created_tmp_disk_tables')"
        )
        sections["temp_tables"] = {row["Variable_name"]: int(row["Value"]) for row in tmp}
        return sections

    async def config_signals(self) -> dict[str, Any]:
        """Raw configuration-vs-workload signals: buffer pool vs data, temp pressure, connections, caches."""
        data = await self._fetch(
            """
            SELECT COALESCE(SUM(data_length + index_length), 0) AS bytes FROM information_schema.tables
            WHERE table_schema NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
            """
        )
        variables = await self._fetch(
            "SHOW GLOBAL VARIABLES WHERE Variable_name IN "
            "('innodb_buffer_pool_size', 'max_connections', 'table_open_cache', 'sync_binlog')"
        )
        status = await self._fetch(
            "SHOW GLOBAL STATUS WHERE Variable_name IN "
            "('Threads_connected', 'Created_tmp_tables', 'Created_tmp_disk_tables', "
            "'Table_open_cache_misses', 'Table_open_cache_hits')"
        )
        return {
            "data_bytes": int(data[0]["bytes"]) if data else 0,
            "variables": {row["Variable_name"]: row["Value"] for row in variables},
            "status": {row["Variable_name"]: int(row["Value"]) for row in status},
        }

    async def index_signals(self, database: str | None = None) -> dict[str, Any]:
        """Raw index-gap signals from the sys schema: full-table-scan statements and tables."""
        try:
            statements = await self._fetch(
                """
                SELECT query, db, exec_count, no_index_used_count
                FROM sys.statements_with_full_table_scans
                WHERE db NOT IN ('mysql', 'information_schema', 'performance_schema', 'sys')
                ORDER BY no_index_used_count DESC LIMIT 10
                """
            )
            tables = await self._fetch(
                "SELECT object_schema, object_name, rows_full_scanned "
                "FROM sys.schema_tables_with_full_table_scans ORDER BY rows_full_scanned DESC LIMIT 10"
            )
        except MySQLError as exc:
            raise GuidanceError(
                f"Cannot read the sys schema ({exc}). Requires MySQL 5.7+ with performance_schema=ON."
            ) from None
        return {"full_scan_statements": statements, "full_scan_tables": tables}
