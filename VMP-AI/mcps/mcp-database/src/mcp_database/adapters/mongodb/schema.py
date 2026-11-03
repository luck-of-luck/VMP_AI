from __future__ import annotations

from typing import Any

from pymongo.errors import (
    OperationFailure,
    PyMongoError,
)

from ...errors import GuidanceError, QueryValidationError
from ...formatter import type_placeholder
from ._common import _is_search_unavailable, _search_guidance

_INTERNAL_DBS = {"admin", "local", "config"}


class MongoSchemaMixin:
    """MongoAdapter schema operations."""

    async def list_databases(self) -> list[dict[str, Any]]:
        cursor = await self._get_client().list_databases()
        return [
            {"database": d["name"], "size_bytes": d.get("sizeOnDisk"), "empty": d.get("empty")} async for d in cursor
        ]

    async def list_objects(self, database: str, object_type: str | None = None) -> list[dict[str, Any]]:
        if object_type not in (None, "collection", "view", "table"):
            raise QueryValidationError(f"Unknown object_type '{object_type}' (expected: collection, view)")
        db = self._db(database)
        results = []
        cursor = await db.list_collections()
        async for info in cursor:
            kind = "view" if info.get("type") == "view" else "collection"
            if object_type in ("collection", "table") and kind != "collection":
                continue
            if object_type == "view" and kind != "view":
                continue
            item: dict[str, Any] = {"name": info["name"], "type": kind}
            if kind == "collection" and not info["name"].startswith("system."):
                try:
                    item["approx_rows"] = await db[info["name"]].estimated_document_count(maxTimeMS=self._timeout_ms)
                except PyMongoError:
                    item["approx_rows"] = None
            results.append(item)
        return sorted(results, key=lambda r: r["name"])

    async def describe_object(self, database: str, obj: str, *, sample: bool = True) -> dict[str, Any]:
        db = self._db(database)
        cursor = await db.list_collections(filter={"name": obj})
        if not await cursor.to_list(length=1):
            raise QueryValidationError(f"Collection '{database}.{obj}' not found")
        result: dict[str, Any] = {"indexes": [], "fields": []}
        try:
            result["indexes"] = [{"name": name, **spec} for name, spec in (await db[obj].index_information()).items()]
        except PyMongoError as exc:
            result["indexes_error"] = str(exc)
        try:
            stats = await db.command({"collStats": obj})
            result["stats"] = {
                "count": stats.get("count"),
                "size_bytes": stats.get("size"),
                "avg_doc_bytes": stats.get("avgObjSize"),
                "total_index_bytes": stats.get("totalIndexSize"),
            }
        except PyMongoError:
            result["stats"] = None
        if sample:
            cursor = await db[obj].aggregate([{"$sample": {"size": 50}}], maxTimeMS=self._timeout_ms)
            docs = await cursor.to_list(length=50)
            fields: dict[str, set[str]] = {}
            for doc in docs:
                for key, value in doc.items():
                    fields.setdefault(key, set()).add(type_placeholder(value))
            result["fields"] = [{"name": key, "types": sorted(types)} for key, types in sorted(fields.items())]
            result["sampled_docs"] = len(docs)
        else:
            result["note"] = "Field sampling skipped (monitor mode reads no data)"
        return result

    async def get_ddl(self, database: str, obj: str) -> dict[str, Any]:
        db = self._db(database)
        cursor = await db.list_collections(filter={"name": obj})
        infos = await cursor.to_list(length=1)
        if not infos:
            raise QueryValidationError(f"Collection '{database}.{obj}' not found")
        info = infos[0]
        commands: list[dict[str, Any]] = [{"create": obj, **info.get("options", {})}]
        indexes = await db[obj].index_information()
        specs = [
            {"name": name, "key": dict(spec["key"]), **{k: v for k, v in spec.items() if k != "key"}}
            for name, spec in indexes.items()
            if name != "_id_"
        ]
        if specs:
            commands.append({"createIndexes": obj, "indexes": specs})
        return {"commands": commands}

    async def search(self, pattern: str, scope: str | None = None) -> dict[str, Any]:
        lowered = pattern.lower()
        matches = []
        for entry in await self.list_databases():
            name = entry["database"]
            if name in _INTERNAL_DBS:
                continue
            cursor = await self._get_client()[name].list_collections()
            async for info in cursor:
                if lowered in info["name"].lower():
                    matches.append({"database": name, "name": info["name"], "type": info.get("type", "collection")})
        return {"objects": matches, "note": "Field names are not searched; use db_schema_describe on a collection"}

    async def relationships(self, database: str, obj: str | None = None) -> dict[str, Any]:
        return {"relationships": [], "note": "MongoDB has no foreign keys; relationships are application-level"}

    async def users(self, user: str | None = None) -> list[dict[str, Any]]:
        client = self._get_client()
        command: dict[str, Any] = {"usersInfo": user or {"forAllDBs": True}}
        try:
            info = await client.admin.command(command)
        except OperationFailure as exc:
            raise GuidanceError(
                f"Cannot list users ({exc.details.get('errmsg', exc)}). Requires the viewUser or userAdmin role."
            ) from None
        return [{"user": u["user"], "database": u["db"], "roles": u.get("roles", [])} for u in info.get("users", [])]

    async def grants(self, user: str | None = None, obj: str | None = None) -> list[dict[str, Any]]:
        client = self._get_client()
        command: dict[str, Any] = {
            "usersInfo": user or {"forAllDBs": True},
            "showPrivileges": True,
        }
        try:
            info = await client.admin.command(command)
        except OperationFailure as exc:
            raise GuidanceError(
                f"Cannot inspect privileges ({exc.details.get('errmsg', exc)}). Requires the viewUser role."
            ) from None
        grants = []
        for u in info.get("users", []):
            privileges = u.get("inheritedPrivileges", [])
            if obj:
                privileges = [p for p in privileges if p.get("resource", {}).get("collection") == obj]
            grants.append(
                {"user": u["user"], "database": u["db"], "roles": u.get("roles", []), "privileges": privileges}
            )
        return grants

    async def search_indexes(self, database: str | None = None, obj: str | None = None) -> dict[str, Any]:
        """Atlas search/vectorSearch indexes per collection with status, queryable flag and definition."""
        db = self._db(database)
        if obj:
            names = [obj]
        else:
            cursor = await db.list_collections(filter={"type": "collection"})
            names = sorted([info["name"] async for info in cursor if not info["name"].startswith("system.")])
        indexes = []
        for name in names:
            try:
                index_cursor = await db[name].list_search_indexes()
                entries = await index_cursor.to_list(length=100)
            except OperationFailure as exc:
                if _is_search_unavailable(exc):
                    raise _search_guidance(exc, "Listing Atlas search indexes") from None
                raise
            for entry in entries:
                definition = entry.get("latestDefinition") or {}
                indexes.append(
                    {
                        "collection": name,
                        "index": entry.get("name"),
                        "type": entry.get("type", "search"),
                        "status": entry.get("status"),
                        "queryable": entry.get("queryable"),
                        "definition": definition,
                    }
                )
        return {"indexes": indexes}
