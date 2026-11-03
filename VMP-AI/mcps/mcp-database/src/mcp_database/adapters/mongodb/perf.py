from __future__ import annotations

from typing import Any

from pymongo.errors import (
    OperationFailure,
    PyMongoError,
)

from ...errors import GuidanceError, QueryValidationError


class MongoPerfMixin:
    """MongoAdapter perf operations."""

    async def explain(
        self, query: Any, *, analyze: bool = False, hypothetical_indexes: list[str] | None = None
    ) -> dict[str, Any]:
        if hypothetical_indexes:
            raise GuidanceError("hypothetical indexes require PostgreSQL with the hypopg extension")
        db = self._db(query.get("database"))
        operation = query["operation"]
        if operation == "find":
            inner: dict[str, Any] = {"find": query["collection"], "filter": query.get("filter") or {}}
        elif operation == "aggregate":
            inner = {"aggregate": query["collection"], "pipeline": query["pipeline"], "cursor": {}}
        elif operation == "countDocuments":
            inner = {"count": query["collection"], "query": query.get("filter") or {}}
        else:
            raise QueryValidationError(f"explain supports find, aggregate and countDocuments, got '{operation}'")
        verbosity = "executionStats" if analyze else "queryPlanner"
        plan = await db.command({"explain": inner, "verbosity": verbosity})
        plan.pop("$clusterTime", None)
        plan.pop("operationTime", None)
        return {"plan": plan}

    async def top_queries(self, sort_by: str, limit: int, database: str | None = None) -> list[dict[str, Any]]:
        db = self._db(database)
        status = await db.command({"profile": -1})
        if status.get("was", 0) == 0:
            raise GuidanceError(
                f"The profiler is off for database '{db.name}'. Enable it with: db.setProfilingLevel(1) "
                "(or setProfilingLevel(1, {slowms: 100})) and re-run the workload."
            )
        cursor = (
            db["system.profile"]
            .find({}, {"op": 1, "ns": 1, "millis": 1, "ts": 1, "command": 1, "planSummary": 1})
            .sort("millis", -1)
            .limit(limit)
        )
        rows = await cursor.to_list(length=limit)
        for row in rows:
            row.pop("_id", None)
        return rows

    async def active_ops(self, min_duration_ms: int = 0) -> list[dict[str, Any]]:
        try:
            cursor = await self._get_client().admin.aggregate(
                [
                    {"$currentOp": {"allUsers": True, "idleConnections": False}},
                    {"$match": {"active": True, "secs_running": {"$gte": min_duration_ms / 1000}}},
                    {
                        "$project": {
                            "opid": 1,
                            "op": 1,
                            "ns": 1,
                            "secs_running": 1,
                            "waitingForLock": 1,
                            "desc": 1,
                            "command": 1,
                        }
                    },
                ]
            )
            return await cursor.to_list(length=200)
        except OperationFailure as exc:
            raise GuidanceError(
                f"Cannot run $currentOp ({exc.details.get('errmsg', exc)}). Requires the inprog privilege "
                "(e.g. the clusterMonitor role)."
            ) from None

    async def blocking(self) -> list[dict[str, Any]]:
        try:
            cursor = await self._get_client().admin.aggregate(
                [
                    {"$currentOp": {"allUsers": True}},
                    {"$match": {"waitingForLock": True}},
                    {"$project": {"opid": 1, "op": 1, "ns": 1, "secs_running": 1, "command": 1, "locks": 1}},
                ]
            )
            return await cursor.to_list(length=200)
        except OperationFailure as exc:
            raise GuidanceError(
                f"Cannot inspect lock waits ({exc.details.get('errmsg', exc)}). Requires the clusterMonitor role."
            ) from None

    async def index_stats(self, database: str | None = None) -> dict[str, Any]:
        db = self._db(database)
        stats = []
        cursor = await db.list_collections(filter={"type": "collection"})
        async for info in cursor:
            name = info["name"]
            if name.startswith("system."):
                continue
            index_cursor = await db[name].aggregate([{"$indexStats": {}}], maxTimeMS=self._timeout_ms)
            async for entry in index_cursor:
                stats.append(
                    {
                        "collection": name,
                        "index": entry["name"],
                        "ops": entry.get("accesses", {}).get("ops", 0),
                        "since": entry.get("accesses", {}).get("since"),
                    }
                )
        return {"indexes": stats, "unused": [s for s in stats if s["ops"] == 0 and s["index"] != "_id_"]}

    async def table_stats(self, database: str | None = None) -> list[dict[str, Any]]:
        db = self._db(database)
        rows = []
        cursor = await db.list_collections(filter={"type": "collection"})
        async for info in cursor:
            name = info["name"]
            if name.startswith("system."):
                continue
            try:
                stats = await db.command({"collStats": name})
            except PyMongoError:
                continue
            rows.append(
                {
                    "collection": name,
                    "count": stats.get("count"),
                    "size_bytes": stats.get("size"),
                    "storage_bytes": stats.get("storageSize"),
                    "avg_doc_bytes": stats.get("avgObjSize"),
                    "total_index_bytes": stats.get("totalIndexSize"),
                    "indexes": stats.get("nindexes"),
                }
            )
        return sorted(rows, key=lambda r: r.get("size_bytes") or 0, reverse=True)

    async def health(self) -> dict[str, Any]:
        status = await self._get_client().admin.command("serverStatus")
        cache = status.get("wiredTiger", {}).get("cache", {})
        return {
            "version": status.get("version"),
            "uptime_s": status.get("uptime"),
            "connections": status.get("connections"),
            "opcounters": status.get("opcounters"),
            "memory_mb": {
                "resident": status.get("mem", {}).get("resident"),
                "virtual": status.get("mem", {}).get("virtual"),
            },
            "wiredtiger_cache": {
                "used_bytes": cache.get("bytes currently in the cache"),
                "max_bytes": cache.get("maximum bytes configured"),
            },
            "largest_databases": sorted(
                await self.list_databases(), key=lambda d: d.get("size_bytes") or 0, reverse=True
            )[:10],
        }

    async def replication(self) -> dict[str, Any]:
        """Replica-set status and members; error code 76 (not running with replication) means standalone."""
        client = self._get_client()
        try:
            status = await client.admin.command("replSetGetStatus")
        except OperationFailure as exc:
            if exc.code == 76:  # NoReplicationEnabled
                return {"role": "standalone", "note": "This mongod is not part of a replica set"}
            raise GuidanceError(
                f"Cannot read replica set status ({exc.details.get('errmsg', exc)}). Requires the clusterMonitor role."
            ) from None
        primary_optime = next(
            (m.get("optimeDate") for m in status.get("members", []) if m.get("stateStr") == "PRIMARY"), None
        )
        members = []
        for m in status.get("members", []):
            optime = m.get("optimeDate")
            lag_seconds = None
            if primary_optime and optime and m.get("stateStr") != "PRIMARY":
                lag_seconds = max(0, round((primary_optime - optime).total_seconds()))
            members.append(
                {
                    "name": m.get("name"),
                    "state": m.get("stateStr"),
                    "health": m.get("health"),
                    "optime": optime.isoformat() if optime else None,
                    "lag_seconds": lag_seconds,
                }
            )
        result = {"role": "replica_set", "set": status.get("set"), "members": members}
        try:
            shards = await client.admin.command("listShards")
            result["shards"] = shards.get("shards", [])
            balancer = await client.admin.command({"balancerStatus": 1})
            result["balancer"] = {"mode": balancer.get("mode"), "in_round": balancer.get("inBalancerRound")}
        except OperationFailure:
            pass
        return result

    async def settings(self, pattern: str | None = None) -> list[dict[str, Any]]:
        try:
            params = await self._get_client().admin.command({"getParameter": "*"})
        except OperationFailure as exc:
            raise GuidanceError(
                f"Cannot read server parameters ({exc.details.get('errmsg', exc)}). Requires clusterMonitor."
            ) from None
        params.pop("ok", None)
        items = sorted(params.items())
        if pattern:
            lowered = pattern.lower()
            items = [(k, v) for k, v in items if lowered in k.lower()]
        else:
            items = [(k, v) for k, v in items if not isinstance(v, dict | list)][:100]
        return [{"name": k, "value": v} for k, v in items]

    async def logs(self, limit: int = 100, level: str | None = None) -> list[dict[str, Any]]:
        try:
            log = await self._get_client().admin.command({"getLog": "global"})
        except OperationFailure as exc:
            raise GuidanceError(
                f"Cannot read the server log ({exc.details.get('errmsg', exc)}). Requires clusterMonitor."
            ) from None
        lines = log.get("log", [])
        if level:
            token = f'"s":"{level[0].upper()}"'
            lines = [line for line in lines if token in line]
        return [{"line": line} for line in lines[-limit:]]

    async def vector_stats(self, database: str | None = None, obj: str | None = None) -> dict[str, Any]:
        """Raw sections about vectorSearch indexes and their collections; findings live at the tool layer."""
        all_indexes = (await self.search_indexes(database, obj))["indexes"]
        vector_indexes = [entry for entry in all_indexes if entry["type"] == "vectorSearch"]
        db = self._db(database)
        counts = {}
        for name in sorted({entry["collection"] for entry in vector_indexes}):
            try:
                counts[name] = await db[name].estimated_document_count(maxTimeMS=self._timeout_ms)
            except PyMongoError:
                counts[name] = None
        return {
            "vector_indexes": vector_indexes,
            "collection_counts": counts,
            "search_indexes_total": len(all_indexes),
        }

    async def storage(self, database: str | None = None) -> dict[str, Any]:
        """Raw storage sections: dbStats (with filesystem usage where exposed) and the oplog window."""
        db = self._db(database)
        sections: dict[str, Any] = {}
        try:
            stats = await db.command({"dbStats": 1})
            sections["db"] = {
                "database": stats.get("db"),
                "data_bytes": stats.get("dataSize"),
                "storage_bytes": stats.get("storageSize"),
                "index_bytes": stats.get("indexSize"),
                "fs_used_bytes": stats.get("fsUsedSize"),
                "fs_total_bytes": stats.get("fsTotalSize"),
            }
        except PyMongoError as exc:
            sections["db"] = {"unavailable": str(exc)}
        try:
            client = self._get_client()
            local = client["local"]
            first = await local["oplog.rs"].find_one(sort=[("ts", 1)])
            last = await local["oplog.rs"].find_one(sort=[("ts", -1)])
            if first and last:
                window_s = last["ts"].time - first["ts"].time
                sections["oplog"] = {"window_hours": round(window_s / 3600, 2)}
            else:
                sections["oplog"] = {"unavailable": "no oplog (standalone mongod)"}
        except PyMongoError as exc:
            sections["oplog"] = {"unavailable": str(exc)}
        return sections

    async def config_signals(self) -> dict[str, Any]:
        """Raw configuration-vs-workload signals: wiredTiger cache pressure and connection headroom."""
        client = self._get_client()
        status = await client.admin.command("serverStatus")
        wt = status.get("wiredTiger", {}).get("cache", {})
        connections = status.get("connections", {})
        return {
            "cache": {
                "used_bytes": wt.get("bytes currently in the cache"),
                "max_bytes": wt.get("maximum bytes configured"),
            },
            "connections": {"current": connections.get("current"), "available": connections.get("available")},
        }

    async def index_signals(self, database: str | None = None) -> dict[str, Any]:
        """Raw index-gap signals: COLLSCAN aggregates from system.profile (requires the profiler on)."""
        db = self._db(database)
        try:
            level = await db.command({"profile": -1})
        except PyMongoError as exc:
            raise GuidanceError(f"Cannot read the profiler level ({exc})") from None
        if not level.get("was"):
            raise GuidanceError(
                "The profiler is off, so collection scans are not recorded. "
                "Enable it with db.setProfilingLevel(1) and re-run the workload first."
            )
        cursor = await db["system.profile"].aggregate(
            [
                {"$match": {"planSummary": {"$regex": "^COLLSCAN"}}},
                {"$group": {"_id": "$ns", "count": {"$sum": 1}, "avg_ms": {"$avg": "$millis"}}},
                {"$sort": {"count": -1}},
                {"$limit": 10},
            ],
            maxTimeMS=self._timeout_ms,
        )
        rows = await cursor.to_list(length=10)
        return {"collscans": [{"ns": row["_id"], "count": row["count"], "avg_ms": row.get("avg_ms")} for row in rows]}
