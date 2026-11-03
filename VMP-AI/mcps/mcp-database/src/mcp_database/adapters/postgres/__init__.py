from __future__ import annotations

from typing import Any, ClassVar

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from ..base import SQLAdapter
from .perf import PgPerfMixin
from .read import PgReadMixin
from .schema import PgSchemaMixin
from .write import PgWriteMixin


class PostgresAdapter(PgSchemaMixin, PgReadMixin, PgPerfMixin, PgWriteMixin, SQLAdapter):
    """PostgreSQL over psycopg3: transactional reads (READ ONLY + statement_timeout) and DDL dry-run support."""

    _pool: AsyncConnectionPool | None = None

    _DIALECT = "postgres"

    CAPABILITIES = frozenset(
        {
            "hypothetical_indexes",
            "column_stats",
            "planner_analyze",
            "transactional_ddl",
            "server_side_sampling",
            "vector_search",
        }
    )

    _SEARCH_OBJECTS_SQL = """
        SELECT n.nspname AS schema, c.relname AS name, c.relkind::text AS kind
        FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relname ILIKE %s AND n.nspname NOT LIKE 'pg\\_%%' AND n.nspname <> 'information_schema'
        ORDER BY 1, 2 LIMIT 100
    """

    _SEARCH_COLUMNS_SQL = """
        SELECT table_schema AS schema, table_name AS "table", column_name AS "column", data_type AS type
        FROM information_schema.columns
        WHERE column_name ILIKE %s AND table_schema NOT LIKE 'pg\\_%%' AND table_schema <> 'information_schema'
        ORDER BY 1, 2 LIMIT 200
    """

    async def _ensure_pool(self) -> AsyncConnectionPool:
        """Open the lazy connection pool (max 2) on first use."""
        if self._pool is None:
            self._pool = AsyncConnectionPool(
                self.config.resolved_uri(),
                min_size=0,
                max_size=self.config.pool_size,
                open=False,
                check=AsyncConnectionPool.check_connection,
                kwargs={
                    "row_factory": dict_row,
                    "application_name": f"mcp-database/{self.config.name}",
                    "connect_timeout": self.config.connect_timeout_s,
                },
            )
            await self._pool.open(wait=False)
        return self._pool

    async def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            await pool.close()

    @property
    def _lock_timeout_ms(self) -> int:
        """Lock waits get half the statement budget (capped at lock_timeout_max_s): failing fast beats queueing."""
        return min(self.config.query_timeout_s * 500, self.config.lock_timeout_max_s * 1000)

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        """Connection-level failures only: no sqlstate (client-side) or class 08; excludes cancels/timeouts."""
        if not isinstance(exc, psycopg.OperationalError):
            return False
        return exc.sqlstate is None or exc.sqlstate.startswith("08")

    async def _fetch_once(
        self,
        query: str | sql.Composable,
        params: Any = None,
        *,
        limit: int | None = None,
        readonly: bool = True,
    ) -> list[dict[str, Any]]:
        """One statement per transaction; readonly sets READ ONLY and every run gets a local statement_timeout."""
        pool = await self._ensure_pool()
        async with pool.connection() as conn:
            async with conn.transaction():
                if readonly:
                    await conn.execute("SET TRANSACTION READ ONLY")
                else:
                    await conn.execute(
                        sql.SQL("SET LOCAL lock_timeout = {}").format(sql.Literal(self._lock_timeout_ms))
                    )
                await conn.execute(
                    sql.SQL("SET LOCAL statement_timeout = {}").format(sql.Literal(self.config.query_timeout_s * 1000))
                )
                cursor = await conn.execute(query, params)
                if cursor.description is None:
                    return []
                if limit is None:
                    return await cursor.fetchall()
                return await cursor.fetchmany(limit + 1)

    async def ping(self) -> None:
        await self._fetch("SELECT 1")

    _SEARCH_INDEXES_SQL = """
        SELECT n.nspname AS schema, t.relname AS "table", c.relname AS index, am.amname AS method,
               a.attname AS column, CASE WHEN a.atttypmod > 0 THEN a.atttypmod END AS dimensions,
               pg_get_indexdef(i.indexrelid) AS definition, i.indisvalid AS valid,
               pg_relation_size(i.indexrelid) AS index_bytes, c.reloptions AS options
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_class t ON t.oid = i.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN pg_am am ON am.oid = c.relam
        LEFT JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = i.indkey[0]
        WHERE (%s::text IS NULL OR n.nspname = %s) AND (%s::text IS NULL OR t.relname = %s)
    """

    _REPLICA_ACTIONS: ClassVar[dict[str, str]] = {
        "pause_replay": "SELECT pg_wal_replay_pause()",
        "resume_replay": "SELECT pg_wal_replay_resume()",
    }
