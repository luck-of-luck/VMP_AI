from __future__ import annotations

from typing import Any

from pymongo.errors import (
    AutoReconnect,
    ConnectionFailure,
    OperationFailure,
)
from pymongo.operations import SearchIndexModel

from ...errors import GuidanceError, QueryValidationError
from ._common import _is_search_unavailable, _search_guidance


class MongoWriteMixin:
    """MongoAdapter write operations."""

    async def search_index_write(
        self, database: str, obj: str, action: str, name: str, definition: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """create/update/drop one Atlas search index; builds are asynchronous on the server side."""
        collection = self._db(database)[obj]
        try:
            if action == "create":
                if not isinstance(definition, dict) or not definition:
                    raise QueryValidationError(
                        "create requires 'definition' (Atlas index definition: 'fields' for vectorSearch, "
                        "'mappings' for search)"
                    )
                spec = dict(definition)
                index_type = spec.pop("type", "vectorSearch" if "fields" in spec else "search")
                created = await collection.create_search_index(
                    SearchIndexModel(definition=spec, name=name, type=index_type)
                )
                return {
                    "applied": True,
                    "action": "create",
                    "index": created,
                    "type": index_type,
                    "note": "Search index builds are asynchronous; poll db_schema_search_indexes until queryable",
                }
            if action == "update":
                if not isinstance(definition, dict) or not definition:
                    raise QueryValidationError("update requires 'definition' (the full new index definition)")
                spec = dict(definition)
                spec.pop("type", None)
                await collection.update_search_index(name, spec)
                return {"applied": True, "action": "update", "index": name}
            if action == "drop":
                await collection.drop_search_index(name)
                return {"applied": True, "action": "drop", "index": name}
        except OperationFailure as exc:
            if _is_search_unavailable(exc):
                raise _search_guidance(exc, "Managing Atlas search indexes") from None
            raise
        raise QueryValidationError(f"Unknown action '{action}' (supported: create, update, drop)")

    async def cluster_action(self, action: str, seconds: int | None = None) -> dict[str, Any]:
        """step_down/freeze on a replica set member; the command names come from a fixed map only."""
        client = self._get_client()
        if action == "step_down":
            secs = seconds if seconds is not None else 60
            try:
                await client.admin.command({"replSetStepDown": secs})
            except (AutoReconnect, ConnectionFailure):
                pass  # the primary drops connections while stepping down — that is the success path
            except OperationFailure as exc:
                if exc.code == 76:  # NoReplicationEnabled
                    raise GuidanceError(
                        "This mongod is standalone; step_down applies to a replica set primary"
                    ) from None
                raise
            return {
                "action": "step_down",
                "seconds": secs,
                "success": True,
                "note": "Primary stepped down; the replica set will elect a new primary",
            }
        if action == "freeze":
            if seconds is None:
                raise QueryValidationError(
                    "freeze requires 'seconds' (how long the member must not seek election; 0 unfreezes)"
                )
            try:
                await client.admin.command({"replSetFreeze": seconds})
            except OperationFailure as exc:
                if exc.code == 76:
                    raise GuidanceError("This mongod is standalone; freeze applies to a replica set member") from None
                raise
            return {"action": "freeze", "seconds": seconds, "success": True}
        raise GuidanceError(f"MongoDB supports cluster actions 'step_down' and 'freeze', got '{action}'")

    async def write(
        self,
        query: Any,
        params: list[Any] | None,
        *,
        dry_run: bool = False,
        expected_max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Dispatch one write op to the insert/modify/DDL handler; the pre-count keeps dry_run non-destructive."""
        db = self._db(query.get("database"))
        collection = db[query["collection"]]
        operation = query["operation"]
        if operation in ("insertOne", "insertMany"):
            return await self._write_insert(collection, operation, query, dry_run)
        if operation in ("updateOne", "updateMany", "replaceOne", "deleteOne", "deleteMany"):
            return await self._write_modify(collection, operation, query, dry_run, expected_max_rows)
        return await self._write_ddl(db, collection, operation, query, dry_run)

    async def _write_insert(self, collection: Any, operation: str, query: Any, dry_run: bool) -> dict[str, Any]:
        """insertOne/insertMany: validate the documents, then insert (or report the count on dry_run)."""
        documents = query.get("documents") or ([query["document"]] if query.get("document") else None)
        if not documents or not all(isinstance(d, dict) for d in documents):
            raise QueryValidationError(f"{operation} requires 'documents' (list of objects) or 'document'")
        if dry_run:
            return {"applied": False, "dry_run": True, "would_affect": len(documents)}
        result = await collection.insert_many(documents)
        return {"applied": True, "affected": len(result.inserted_ids)}

    async def _write_modify(
        self, collection: Any, operation: str, query: Any, dry_run: bool, expected_max_rows: int | None
    ) -> dict[str, Any]:
        """update*/replaceOne/delete*: pre-count for the dry_run/expected_max_rows barrier, then apply."""
        if "filter" not in query:
            raise QueryValidationError(f"{operation} requires an explicit 'filter' (use {{}} to target all)")
        match_filter = query["filter"]
        matched = await collection.count_documents(match_filter, maxTimeMS=self._timeout_ms)
        would_affect = min(matched, 1) if operation.endswith("One") else matched
        if expected_max_rows is not None and would_affect > expected_max_rows:
            return {
                "applied": False,
                "affected": would_affect,
                "aborted": f"would affect {would_affect} documents, above expected_max_rows={expected_max_rows}",
            }
        if dry_run:
            return {"applied": False, "dry_run": True, "would_affect": would_affect}
        if operation == "updateOne":
            result = await collection.update_one(match_filter, query["update"], upsert=query.get("upsert", False))
            affected = result.modified_count
        elif operation == "updateMany":
            result = await collection.update_many(match_filter, query["update"], upsert=query.get("upsert", False))
            affected = result.modified_count
        elif operation == "replaceOne":
            result = await collection.replace_one(match_filter, query["replacement"], upsert=query.get("upsert", False))
            affected = result.modified_count
        elif operation == "deleteOne":
            affected = (await collection.delete_one(match_filter)).deleted_count
        else:
            affected = (await collection.delete_many(match_filter)).deleted_count
        return {"applied": True, "affected": affected}

    async def _write_ddl(self, db: Any, collection: Any, operation: str, query: Any, dry_run: bool) -> dict[str, Any]:
        """Index/collection DDL: dry_run is a generic no-op note, since these cannot be rolled back."""
        if dry_run:
            return {"applied": False, "dry_run": True, "note": f"{operation} would run against '{db.name}'"}
        if operation == "createIndex":
            keys = query.get("keys")
            if not isinstance(keys, dict) or not keys:
                raise QueryValidationError("createIndex requires 'keys' (e.g. {\"field\": 1})")
            name = await collection.create_index(list(keys.items()), **query.get("options", {}))
            return {"applied": True, "index": name}
        if operation == "dropIndex":
            await collection.drop_index(query["name"])
            return {"applied": True, "dropped_index": query["name"]}
        if operation == "createCollection":
            await db.create_collection(query["collection"], **query.get("options", {}))
            return {"applied": True, "created": query["collection"]}
        if operation == "dropCollection":
            await db.drop_collection(query["collection"])
            return {"applied": True, "dropped": query["collection"]}
        if operation == "renameCollection":
            target = query.get("to")
            if not target:
                raise QueryValidationError("renameCollection requires 'to'")
            await collection.rename(target)
            return {"applied": True, "renamed": f"{query['collection']} -> {target}"}
        raise QueryValidationError(f"Unhandled write operation '{operation}'")

    async def kill(self, target_id: str, *, force: bool = False) -> dict[str, Any]:
        """killOp by numeric opid, falling back to the string form used on sharded clusters."""
        try:
            opid: Any = int(target_id)
        except ValueError:
            opid = target_id  # sharded clusters use string opids like "shard01:123"
        await self._get_client().admin.command({"killOp": 1, "op": opid})
        return {"target": opid, "action": "killOp", "success": True}

    async def maintain(self, database: str, obj: str, action: str | None = None) -> dict[str, Any]:
        if action not in (None, "compact"):
            raise QueryValidationError(f"MongoDB supports action 'compact', got '{action}'")
        try:
            result = await self._db(database).command({"compact": obj})
        except OperationFailure as exc:
            raise GuidanceError(
                f"compact failed ({exc.details.get('errmsg', exc)}). Requires the compact privilege on the collection."
            ) from None
        return {"maintained": f"{database}.{obj}", "action": "compact", "result": {"ok": result.get("ok")}}
