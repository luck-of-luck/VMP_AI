from __future__ import annotations

from typing import Any

from pymysql.err import MySQLError

from ...errors import GuidanceError, QueryValidationError
from ._common import _ident, _qualified


class MyReadMixin:
    """MySQLAdapter read operations."""

    async def sample(self, database: str, obj: str, n: int) -> list[dict[str, Any]]:
        return await self._fetch(f"SELECT * FROM {_qualified(database, obj)} LIMIT {int(n)}")

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
        """FULLTEXT natural-language search ranked by MATCH score; the phrase and filters are binds."""
        if not column:
            raise QueryValidationError("MySQL text search requires 'column' (a FULLTEXT-indexed column)")
        if index is not None:
            raise QueryValidationError("'index' is an Atlas Search parameter; MySQL searches a column")
        if language is not None:
            raise QueryValidationError("'language' is a PostgreSQL text-search parameter; MySQL has no regconfig")
        match = f"MATCH ({_ident(column)}) AGAINST (%s IN NATURAL LANGUAGE MODE)"
        where_extra = ""
        params: list[Any] = [query, query]
        if flt:
            where_extra = "".join(f" AND {_ident(key)} = %s" for key in flt)
            params += list(flt.values())
        statement = (
            f"SELECT *, {match} AS score FROM {_qualified(database, obj)} "
            f"WHERE {match}{where_extra} ORDER BY score DESC LIMIT {int(limit)}"
        )
        try:
            return await self._fetch(statement, params)
        except MySQLError as exc:
            if exc.args and exc.args[0] in (1191, 1214):
                raise GuidanceError(
                    f"No FULLTEXT index covers column '{column}' on {database}.{obj}. "
                    "Create one with db_write_search_index action=create"
                ) from None
            raise
