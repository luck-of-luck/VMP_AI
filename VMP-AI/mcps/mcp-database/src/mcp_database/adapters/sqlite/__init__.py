from __future__ import annotations

from typing import Any

import aiosqlite

from ...errors import ConfigError, QueryValidationError
from ..base import SQLAdapter
from .perf import SqlitePerfMixin
from .read import SqliteReadMixin
from .schema import SqliteSchemaMixin
from .write import SqliteWriteMixin


class SQLiteAdapter(SqliteSchemaMixin, SqliteReadMixin, SqlitePerfMixin, SqliteWriteMixin, SQLAdapter):
    """SQLite over aiosqlite, one short-lived connection per operation.

    Reads open the file with `mode=ro`, so a read cannot write even past validation; writes get a
    busy_timeout (the lock-timeout analog). Server-only surfaces (accounts, processes, replication,
    logs) answer with GuidanceError.
    """

    _DIALECT = "sqlite"

    CAPABILITIES = frozenset({"transactional_ddl"})

    _SEARCH_OBJECTS_SQL = """
        SELECT 'main' AS "database", name, type AS kind FROM sqlite_master
        WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%'
          AND name LIKE ? ESCAPE '\\' ORDER BY name LIMIT 100
    """

    _SEARCH_COLUMNS_SQL = """
        SELECT 'main' AS "database", m.name AS "table", p.name AS "column", p.type
        FROM sqlite_master m JOIN pragma_table_info(m.name) p
        WHERE m.type IN ('table', 'view') AND m.name NOT LIKE 'sqlite_%'
          AND p.name LIKE ? ESCAPE '\\' ORDER BY m.name, p.cid LIMIT 200
    """

    @property
    def _path(self) -> str:
        raw = self.config.resolved_uri().partition("://")[2]
        path = "/" + raw.lstrip("/") if raw.startswith("//") else raw.lstrip("/")
        if not path or ":memory:" in path:
            raise ConfigError(
                f"Connection '{self.config.name}': sqlite URIs must point at a file "
                "(sqlite:///relative.db or sqlite:////absolute.db); :memory: cannot be shared across connections"
            )
        return path

    @property
    def _busy_timeout_s(self) -> int:
        return max(1, min(self.config.query_timeout_s // 2, self.config.lock_timeout_max_s))

    async def _fetch_once(
        self,
        query: str,
        params: Any = None,
        *,
        limit: int | None = None,
        readonly: bool = True,
    ) -> list[dict[str, Any]]:
        """One statement on a fresh connection; readonly uses the mode=ro file URI."""
        target = f"file:{self._path}?mode=ro" if readonly else self._path
        async with aiosqlite.connect(target, uri=readonly, timeout=self._busy_timeout_s) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params or [])
            rows = await cursor.fetchall() if limit is None else await cursor.fetchmany(limit + 1)
            return [dict(row) for row in rows]

    async def ping(self) -> None:
        await self._fetch("SELECT 1")

    async def _ensure_schema(self, database: str) -> str:
        names = [row["database"] for row in await self.list_databases()]
        if database not in names:
            raise QueryValidationError(f"Database '{database}' not found (attached: {', '.join(names)})")
        return database
