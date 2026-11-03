from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg import sql

from ...errors import GuidanceError, QueryValidationError
from ._common import _VECTOR_OPERATORS, _qualified


class PgReadMixin:
    """PostgresAdapter read operations."""

    async def sample(self, database: str, obj: str, n: int) -> list[dict[str, Any]]:
        """n rows via TABLESAMPLE (random pages, representative on big tables); LIMIT fallback for views."""
        try:
            rows = await self._fetch(
                sql.SQL("SELECT * FROM {} TABLESAMPLE SYSTEM (1) LIMIT {}").format(
                    _qualified(database, obj), sql.Literal(n)
                )
            )
        except psycopg.errors.FeatureNotSupported:
            rows = []
        if len(rows) >= n:
            return rows
        statement = sql.SQL("SELECT * FROM {} LIMIT {}").format(_qualified(database, obj), sql.Literal(n))
        return await self._fetch(statement)

    async def _pgvector_version(self) -> str:
        """The installed pgvector version; GuidanceError with the enabling command when absent."""
        rows = await self._fetch("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        if not rows:
            raise GuidanceError(
                "pgvector is not installed. Run: CREATE EXTENSION vector; (requires the pgvector package)"
            )
        return rows[0]["extversion"]

    async def _column_names(self, database: str, obj: str) -> list[str]:
        """Ordered column names of one table/view; raises 'not found' when the object has none."""
        rows = await self._fetch(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position
            """,
            (database, obj),
        )
        if not rows:
            raise QueryValidationError(f"Object '{database}.{obj}' not found")
        return [row["column_name"] for row in rows]

    @staticmethod
    def _filter_clause(flt: dict[str, Any] | None) -> tuple[sql.Composable, list[Any]]:
        """Equality filters as `AND "col" = %s` fragments with their bind values."""
        if not flt:
            return sql.SQL(""), []
        parts = [sql.SQL(" AND {} = %s").format(sql.Identifier(key)) for key in flt]
        return sql.Composed(parts), list(flt.values())

    async def vector_search(
        self,
        database: str,
        obj: str,
        column: str,
        vector: list[float],
        metric: str,
        limit: int,
        flt: dict[str, Any] | None = None,
        index: str | None = None,
        num_candidates: int | None = None,
    ) -> list[dict[str, Any]]:
        """KNN over a pgvector column: operator from an internal metric map, vector and filters as binds."""
        if index is not None or num_candidates is not None:
            raise QueryValidationError("'index' and 'num_candidates' are MongoDB $vectorSearch parameters")
        operator = _VECTOR_OPERATORS.get(metric)
        if operator is None:
            raise QueryValidationError(f"Unknown metric '{metric}' (supported: {', '.join(sorted(_VECTOR_OPERATORS))})")
        await self._pgvector_version()
        names = await self._column_names(database, obj)
        if column not in names:
            raise QueryValidationError(f"Column '{column}' not found in '{database}.{obj}'")
        projected = [sql.Identifier(name) for name in names if name != column]
        distance = sql.SQL("{} {} %s::vector AS distance").format(sql.Identifier(column), sql.SQL(operator))
        where, filter_params = self._filter_clause(flt)
        statement = sql.SQL("SELECT {} FROM {} WHERE true{} ORDER BY distance LIMIT {}").format(
            sql.SQL(", ").join([*projected, distance]),
            _qualified(database, obj),
            where,
            sql.Literal(limit),
        )
        return await self._fetch(statement, [json.dumps(vector), *filter_params])

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
        """Native full-text search ranked by ts_rank; the regconfig and the phrase are binds, never SQL."""
        if not column:
            raise QueryValidationError("PostgreSQL text search requires 'column' (the text column to search)")
        if index is not None:
            raise QueryValidationError("'index' is an Atlas Search parameter; PostgreSQL searches a column")
        names = await self._column_names(database, obj)
        if column not in names:
            raise QueryValidationError(f"Column '{column}' not found in '{database}.{obj}'")
        match = sql.SQL("to_tsvector(%s::regconfig, {col}) @@ websearch_to_tsquery(%s::regconfig, %s)").format(
            col=sql.Identifier(column)
        )
        where, filter_params = self._filter_clause(flt)
        statement = sql.SQL(
            "SELECT *, ts_rank(to_tsvector(%s::regconfig, {col}), websearch_to_tsquery(%s::regconfig, %s)) AS rank "
            "FROM {tbl} WHERE {match}{where} ORDER BY rank DESC LIMIT {lim}"
        ).format(
            col=sql.Identifier(column),
            tbl=_qualified(database, obj),
            match=match,
            where=where,
            lim=sql.Literal(limit),
        )
        regconfig = language or "simple"
        params = [regconfig, regconfig, query, regconfig, regconfig, query, *filter_params]
        return await self._fetch(statement, params)
