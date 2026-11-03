from __future__ import annotations

from typing import Any

from ...errors import GuidanceError


class RedisPerfMixin:
    """RedisAdapter perf operations."""

    async def explain(
        self, query: Any, *, analyze: bool = False, hypothetical_indexes: list[str] | None = None
    ) -> dict[str, Any]:
        raise GuidanceError("Redis has no query planner; use db_perf_top_queries (SLOWLOG) to find slow commands")

    async def top_queries(self, sort_by: str, limit: int, database: str | None = None) -> list[dict[str, Any]]:
        entries = await self._get_client().slowlog_get(limit)
        rows = []
        for entry in entries:
            command = entry.get("command")
            rows.append(
                {
                    "id": entry.get("id"),
                    "start_time": entry.get("start_time"),
                    "duration_us": entry.get("duration"),
                    "command": command.decode(errors="replace") if isinstance(command, bytes) else str(command),
                    "client": entry.get("client_address"),
                }
            )
        return rows

    async def active_ops(self, min_duration_ms: int = 0) -> list[dict[str, Any]]:
        return await self._get_client().client_list()

    async def blocking(self) -> list[dict[str, Any]]:
        clients = await self._get_client().client_list()
        return [entry for entry in clients if "b" in str(entry.get("flags", ""))]

    async def index_stats(self, database: str | None = None) -> dict[str, Any]:
        raise GuidanceError("Redis has no secondary indexes; key access is O(1) by design")

    async def table_stats(self, database: str | None = None) -> list[dict[str, Any]]:
        return await self._keyspace()

    async def health(self) -> dict[str, Any]:
        info = await self._get_client().info()
        hits, misses = info.get("keyspace_hits", 0), info.get("keyspace_misses", 0)
        return {
            "version": info.get("redis_version"),
            "uptime_s": info.get("uptime_in_seconds"),
            "connected_clients": info.get("connected_clients"),
            "blocked_clients": info.get("blocked_clients"),
            "used_memory_bytes": info.get("used_memory"),
            "maxmemory_bytes": info.get("maxmemory"),
            "mem_fragmentation_ratio": info.get("mem_fragmentation_ratio"),
            "evicted_keys": info.get("evicted_keys"),
            "hit_ratio": round(hits / (hits + misses), 4) if hits + misses else None,
        }

    async def replication(self) -> dict[str, Any]:
        info = await self._get_client().info("replication")
        result: dict[str, Any] = {"role": info.get("role")}
        if info.get("role") == "master":
            result["connected_replicas"] = info.get("connected_slaves", 0)
            result["replicas"] = [value for key, value in info.items() if key.startswith("slave")]
        else:
            result["master_link_status"] = info.get("master_link_status")
            result["master_host"] = info.get("master_host")
            result["seconds_since_last_io"] = info.get("master_last_io_seconds_ago")
        return result

    async def settings(self, pattern: str | None = None) -> list[dict[str, Any]]:
        config = await self._get_client().config_get(f"*{pattern}*" if pattern else "*")
        return [{"name": name, "value": value} for name, value in sorted(config.items())]

    async def logs(self, limit: int = 100, level: str | None = None) -> list[dict[str, Any]]:
        raise GuidanceError("Redis logs go to the server's logfile/stdout; use db_perf_top_queries for SLOWLOG")

    async def storage(self, database: str | None = None) -> dict[str, Any]:
        """Raw storage sections: memory pressure, fragmentation and persistence artifacts."""
        client = self._get_client()
        memory = await client.info("memory")
        persistence = await client.info("persistence")
        return {
            "memory": {
                "used_bytes": memory.get("used_memory"),
                "max_bytes": memory.get("maxmemory"),
                "fragmentation_ratio": memory.get("mem_fragmentation_ratio"),
                "peak_bytes": memory.get("used_memory_peak"),
            },
            "persistence": {
                "rdb_last_save": persistence.get("rdb_last_save_time"),
                "rdb_changes_since_save": persistence.get("rdb_changes_since_last_save"),
                "aof_enabled": bool(persistence.get("aof_enabled")),
                "aof_bytes": persistence.get("aof_current_size"),
            },
        }

    async def config_signals(self) -> dict[str, Any]:
        """Raw configuration-vs-workload signals: eviction policy, bounds and persistence settings."""
        client = self._get_client()
        config = await client.config_get("maxmemory")
        config.update(await client.config_get("maxmemory-policy"))
        config.update(await client.config_get("appendonly"))
        config.update(await client.config_get("save"))
        stats = await client.info("stats")
        return {
            "config": config,
            "evicted_keys": stats.get("evicted_keys", 0),
            "total_commands": stats.get("total_commands_processed", 0),
        }
