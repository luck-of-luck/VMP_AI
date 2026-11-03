from __future__ import annotations

import contextlib
from typing import Any, ClassVar
from urllib.parse import unquote, urlsplit

import aiomysql
from pymysql.err import OperationalError

from ..base import SQLAdapter
from .perf import MyPerfMixin
from .read import MyReadMixin
from .schema import MySchemaMixin
from .write import MyWriteMixin


class MySQLAdapter(MySchemaMixin, MyReadMixin, MyPerfMixin, MyWriteMixin, SQLAdapter):
    """MySQL over aiomysql. max_execution_time only bounds SELECTs, so a cancelled write closes its connection."""

    _pool: Any = None

    _DIALECT = "mysql"

    CAPABILITIES = frozenset({"column_stats", "planner_analyze"})

    _SHOW_REPLICAS = "SHOW REPLICAS"

    _SEARCH_OBJECTS_SQL = """
        SELECT table_schema AS `database`, table_name AS name,
               IF(table_type = 'VIEW', 'view', 'table') AS kind
        FROM information_schema.tables
        WHERE table_name LIKE %s AND table_schema NOT IN ('mysql', 'information_schema',
            'performance_schema', 'sys')
        ORDER BY 1, 2 LIMIT 100
    """

    _SEARCH_COLUMNS_SQL = """
        SELECT table_schema AS `database`, table_name AS `table`, column_name AS `column`,
               column_type AS type
        FROM information_schema.columns
        WHERE column_name LIKE %s AND table_schema NOT IN ('mysql', 'information_schema',
            'performance_schema', 'sys')
        ORDER BY 1, 2 LIMIT 200
    """

    def _dsn(self) -> dict[str, Any]:
        """Split the URI into aiomysql connect arguments, unquoting credentials."""
        parts = urlsplit(self.config.resolved_uri())
        return {
            "host": parts.hostname or "localhost",
            "port": parts.port or 3306,
            "user": unquote(parts.username or "root"),
            "password": unquote(parts.password or ""),
            "db": parts.path.lstrip("/") or None,
            "program_name": f"mcp-database/{self.config.name}",
            "connect_timeout": self.config.connect_timeout_s,
        }

    async def _ensure_pool(self) -> Any:
        """Open the lazy connection pool (max 2, autocommit off) on first use."""
        if self._pool is None:
            self._pool = await aiomysql.create_pool(
                minsize=0, maxsize=self.config.pool_size, autocommit=False, pool_recycle=3600, **self._dsn()
            )
        return self._pool

    async def close(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            pool.close()
            await pool.wait_closed()

    @property
    def _lock_timeout_s(self) -> int:
        """Lock waits get half the statement budget (capped at lock_timeout_max_s): failing fast beats queueing."""
        return max(1, min(self.config.query_timeout_s // 2, self.config.lock_timeout_max_s))

    def _timeout_statement(self) -> str:
        """Per-session read budget; MariaDB overrides with max_statement_time (seconds)."""
        return f"SET SESSION max_execution_time = {self.config.query_timeout_s * 1000}"

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        """Lost/gone-away connections only (errno 2006/2013); SQL errors and timeouts are not retried."""
        return isinstance(exc, OperationalError) and bool(exc.args) and exc.args[0] in (2006, 2013)

    async def _fetch_once(
        self,
        query: str,
        params: Any = None,
        *,
        limit: int | None = None,
        readonly: bool = True,
    ) -> list[dict[str, Any]]:
        """One statement with the time budget set; the session characteristic and a finally-rollback keep
        pooled connections clean even on error paths (a pending next-transaction flag would leak)."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            try:
                async with conn.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute(self._timeout_statement())
                    if readonly:
                        await cursor.execute("SET SESSION TRANSACTION READ ONLY")
                    else:
                        await cursor.execute("SET SESSION TRANSACTION READ WRITE")
                        await cursor.execute(
                            f"SET SESSION lock_wait_timeout = {self._lock_timeout_s}, "
                            f"innodb_lock_wait_timeout = {self._lock_timeout_s}"
                        )
                    await cursor.execute(query, params)
                    rows = await cursor.fetchall() if limit is None else await cursor.fetchmany(limit + 1)
                return list(rows)
            except OperationalError as exc:
                if self._is_transient(exc):
                    conn.close()
                raise
            finally:
                if not conn.closed:
                    with contextlib.suppress(Exception):
                        await conn.rollback()

    async def ping(self) -> None:
        await self._fetch("SELECT 1")

    _USERS_SELECT = "SELECT user, host, plugin, account_locked, password_expired FROM mysql.user"

    _STATUS_ALIASES: ClassVar[dict[str, str]] = {}
