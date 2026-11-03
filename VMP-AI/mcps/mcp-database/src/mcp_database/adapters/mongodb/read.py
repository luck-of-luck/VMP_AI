from __future__ import annotations

from typing import Any

from pymongo.errors import (
    OperationFailure,
)

from ...errors import QueryValidationError
from ._common import _is_search_unavailable, _search_guidance


class MongoReadMixin:
    """MongoAdapter read operations."""

    async def read(self, query: Any, params: list[Any] | None, limit: int | None) -> list[dict[str, Any]]:
        db = self._db(query.get("database"))
        collection = db[query["collection"]]
        operation = query["operation"]
        fetch = (limit + 1) if limit else None

        if operation == "find":
            cursor = collection.find(query.get("filter") or {}, query.get("projection")).max_time_ms(self._timeout_ms)
            if sort := query.get("sort"):
                cursor = cursor.sort(list(sort.items()))
            if fetch:
                cursor = cursor.limit(fetch)
            return await cursor.to_list(length=fetch)
        if operation == "aggregate":
            cursor = await collection.aggregate(query["pipeline"], maxTimeMS=self._timeout_ms)
            return await cursor.to_list(length=fetch)
        if operation == "countDocuments":
            count = await collection.count_documents(query.get("filter") or {}, maxTimeMS=self._timeout_ms)
            return [{"count": count}]
        if operation == "estimatedDocumentCount":
            return [{"count": await collection.estimated_document_count(maxTimeMS=self._timeout_ms)}]
        if operation == "distinct":
            values = await collection.distinct(query["key"], query.get("filter") or {}, maxTimeMS=self._timeout_ms)
            return [{"value": v} for v in values]
        if operation == "listIndexes":
            return [{"name": name, **spec} for name, spec in (await collection.index_information()).items()]
        raise QueryValidationError(f"Unhandled read operation '{operation}'")

    async def sample(self, database: str, obj: str, n: int) -> list[dict[str, Any]]:
        cursor = await self._db(database)[obj].aggregate([{"$sample": {"size": n}}], maxTimeMS=self._timeout_ms)
        return await cursor.to_list(length=n)

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
        """$vectorSearch with the score surfaced and the vector field projected out of the results."""
        if not index:
            raise QueryValidationError("MongoDB $vectorSearch requires 'index' (the Atlas Vector Search index name)")
        stage: dict[str, Any] = {
            "index": index,
            "path": column,
            "queryVector": vector,
            "numCandidates": num_candidates or max(limit * 10, 100),
            "limit": limit,
        }
        if flt:
            stage["filter"] = flt
        pipeline = [
            {"$vectorSearch": stage},
            {"$addFields": {"_score": {"$meta": "vectorSearchScore"}}},
            {"$project": {column: 0}},
        ]
        collection = self._db(database)[obj]
        try:
            cursor = await collection.aggregate(pipeline, maxTimeMS=self._timeout_ms)
            return await cursor.to_list(length=limit)
        except OperationFailure as exc:
            if _is_search_unavailable(exc):
                raise _search_guidance(exc, "$vectorSearch") from None
            raise

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
        """Atlas $search text query over one field (or all fields), score surfaced, optional post-filter."""
        if language is not None:
            raise QueryValidationError(
                "'language' is a PostgreSQL text-search parameter; Atlas analyzers are per-index"
            )
        stage = {
            "index": index or "default",
            "text": {"query": query, "path": column or {"wildcard": "*"}},
        }
        pipeline: list[dict[str, Any]] = [{"$search": stage}]
        if flt:
            pipeline.append({"$match": flt})
        pipeline += [{"$limit": limit}, {"$addFields": {"_score": {"$meta": "searchScore"}}}]
        collection = self._db(database)[obj]
        try:
            cursor = await collection.aggregate(pipeline, maxTimeMS=self._timeout_ms)
            return await cursor.to_list(length=limit)
        except OperationFailure as exc:
            if _is_search_unavailable(exc):
                raise _search_guidance(exc, "$search") from None
            raise
