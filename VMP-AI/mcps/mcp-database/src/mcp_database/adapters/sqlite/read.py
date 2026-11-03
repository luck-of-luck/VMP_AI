from __future__ import annotations

from typing import Any

from ...errors import GuidanceError, QueryValidationError
from ._common import _ident


class SqliteReadMixin:
    """SQLiteAdapter read operations."""

    async def sample(self, database: str, obj: str, n: int) -> list[dict[str, Any]]:
        schema = await self._ensure_schema(database)
        return await self._fetch(f"SELECT * FROM {_ident(schema)}.{_ident(obj)} ORDER BY random() LIMIT {int(n)}")

    async def _fts5_table(self, schema: str, obj: str) -> None:
        rows = await self._fetch(f"SELECT sql FROM {_ident(schema)}.sqlite_master WHERE name = ?", (obj,))
        if not rows or "fts5" not in (rows[0]["sql"] or "").lower():
            raise GuidanceError(
                f"'{obj}' is not an FTS5 table. Create one with: "
                "CREATE VIRTUAL TABLE name USING fts5(column, ...); and INSERT the rows to index"
            )

    async def text_search(
        self,
        database: str,
        obj: str,
        query: str,
        *,
        column: str | None = None,
        index: str | None = None,
        limit: int,
        flt: dict[str, Any] | None = None,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        if index is not None:
            raise QueryValidationError("'index' is an Atlas Search parameter; SQLite searches an FTS5 table")
        if language is not None:
            raise QueryValidationError("'language' is a PostgreSQL regconfig; SQLite FTS5 has no language argument")
        if flt:
            raise QueryValidationError("SQLite text_search takes no filter; add conditions via db_read_query")
        schema = await self._ensure_schema(database)
        await self._fts5_table(schema, obj)
        phrase = '"' + query.replace('"', '""') + '"'
        if column is not None:
            columns = await self._fetch(f"PRAGMA {_ident(schema)}.table_info({_ident(obj)})")
            if column not in [col["name"] for col in columns]:
                raise QueryValidationError(f"Column '{column}' not found in '{database}.{obj}'")
            phrase = f"{column}: {phrase}"
        return await self._fetch(
            f"SELECT *, rank FROM {_ident(schema)}.{_ident(obj)} "
            f"WHERE {_ident(obj)} MATCH ? ORDER BY rank LIMIT {int(limit)}",
            (phrase,),
        )
