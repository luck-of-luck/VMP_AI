from __future__ import annotations

import sqlite3
from typing import Any

from ...errors import GuidanceError, QueryValidationError


class SqlitePerfMixin:
    """SQLiteAdapter perf operations."""

    async def explain(
        self, query: Any, *, analyze: bool = False, hypothetical_indexes: list[str] | None = None
    ) -> dict[str, Any]:
        if hypothetical_indexes:
            raise GuidanceError("Hypothetical indexes require PostgreSQL with HypoPG")
        if analyze:
            raise QueryValidationError("SQLite has no EXPLAIN ANALYZE; use explain without analyze")
        rows = await self._fetch(f"EXPLAIN QUERY PLAN {query}")
        return {"plan": rows}

    async def top_queries(self, sort_by: str, limit: int, database: str | None = None) -> list[dict[str, Any]]:
        raise GuidanceError("SQLite keeps no query statistics; profile in the embedding application")

    async def active_ops(self, min_duration_ms: int = 0) -> list[dict[str, Any]]:
        raise GuidanceError("SQLite is in-process: there are no server sessions to list")

    async def blocking(self) -> list[dict[str, Any]]:
        raise GuidanceError("SQLite locks the whole file; there is no per-session blocking view")

    async def _stat1(self, where: str) -> list[dict[str, Any]]:
        try:
            return await self._fetch(f'SELECT tbl AS "table", idx AS "index", stat FROM sqlite_stat1 {where}')
        except sqlite3.OperationalError as exc:
            raise GuidanceError(f"No planner statistics yet ({exc}). Run: ANALYZE; (db_admin_analyze)") from None

    async def index_stats(self, database: str | None = None) -> dict[str, Any]:
        rows = await self._stat1("WHERE idx IS NOT NULL ORDER BY tbl")
        return {"indexes": rows, "unused": []}

    async def table_stats(self, database: str | None = None) -> list[dict[str, Any]]:
        rows = await self._stat1("ORDER BY tbl")
        approx: dict[str, int] = {}
        for row in rows:
            approx.setdefault(row["table"], int(str(row["stat"]).split()[0]))
        return [{"table": table, "approx_rows": count} for table, count in approx.items()]

    async def health(self) -> dict[str, Any]:
        page_count = (await self._fetch("PRAGMA page_count"))[0]["page_count"]
        page_size = (await self._fetch("PRAGMA page_size"))[0]["page_size"]
        freelist = (await self._fetch("PRAGMA freelist_count"))[0]["freelist_count"]
        journal = (await self._fetch("PRAGMA journal_mode"))[0]["journal_mode"]
        check = (await self._fetch("PRAGMA quick_check(1)"))[0]["quick_check"]
        return {
            "file": self._path,
            "size_bytes": page_count * page_size,
            "freelist_pages": freelist,
            "journal_mode": journal,
            "quick_check": check,
        }

    async def replication(self) -> dict[str, Any]:
        raise GuidanceError("SQLite has no replication; copy the file or use a replicated engine")

    async def settings(self, pattern: str | None = None) -> list[dict[str, Any]]:
        names = (
            "journal_mode", "synchronous", "cache_size", "page_size", "busy_timeout",
            "foreign_keys", "auto_vacuum", "wal_autocheckpoint", "temp_store", "user_version",
        )  # fmt: skip
        rows = []
        for name in names:
            if pattern and pattern.lower() not in name:
                continue
            value = await self._fetch(f"PRAGMA {name}")
            rows.append({"name": name, "value": next(iter(value[0].values())) if value else None})
        return rows

    async def logs(self, limit: int = 100, level: str | None = None) -> list[dict[str, Any]]:
        raise GuidanceError("SQLite has no server log; errors surface in the embedding application")

    async def storage(self, database: str | None = None) -> dict[str, Any]:
        """Raw storage sections: file size, freelist waste and per-table page usage."""
        page_count = (await self._fetch("PRAGMA page_count"))[0]["page_count"]
        page_size = (await self._fetch("PRAGMA page_size"))[0]["page_size"]
        freelist = (await self._fetch("PRAGMA freelist_count"))[0]["freelist_count"]
        return {
            "file": {
                "path": self._path,
                "bytes": page_count * page_size,
                "pages": page_count,
                "freelist_pages": freelist,
                "freelist_ratio": round(freelist / page_count, 4) if page_count else 0,
            }
        }

    async def config_signals(self) -> dict[str, Any]:
        """Raw configuration signals: journal mode, synchronous level, cache size and file size."""
        journal = (await self._fetch("PRAGMA journal_mode"))[0]["journal_mode"]
        synchronous = (await self._fetch("PRAGMA synchronous"))[0]["synchronous"]
        cache_size = (await self._fetch("PRAGMA cache_size"))[0]["cache_size"]
        page_count = (await self._fetch("PRAGMA page_count"))[0]["page_count"]
        page_size = (await self._fetch("PRAGMA page_size"))[0]["page_size"]
        return {
            "journal_mode": journal,
            "synchronous": synchronous,
            "cache_size": cache_size,
            "file_bytes": page_count * page_size,
        }

    async def index_signals(self, database: str | None = None) -> dict[str, Any]:
        """Raw index-gap signals: large tables (per sqlite_stat1) with no secondary index."""
        stats = await self._stat1("ORDER BY tbl")
        rows_by_table: dict[str, int] = {}
        indexed: set[str] = set()
        for row in stats:
            rows_by_table.setdefault(row["table"], int(str(row["stat"]).split()[0]))
            if row["index"]:
                indexed.add(row["table"])
        unindexed = [
            {"table": table, "approx_rows": count}
            for table, count in rows_by_table.items()
            if table not in indexed and count > 1000
        ]
        return {"unindexed_tables": sorted(unindexed, key=lambda row: -row["approx_rows"])}
