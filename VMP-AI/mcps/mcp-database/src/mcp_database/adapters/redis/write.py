from __future__ import annotations

from typing import Any

from ...errors import GuidanceError, QueryValidationError

_DRY_RUN_PROBEABLE = frozenset({"DEL", "UNLINK"})


class RedisWriteMixin:
    """RedisAdapter write operations."""

    async def write(
        self,
        query: Any,
        params: list[Any] | None,
        *,
        dry_run: bool = False,
        expected_max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Run the allowlisted command. Redis has no rollback, so dry_run/expected_max_rows work as an
        EXISTS pre-check and only for DEL/UNLINK — anything else gets an honest GuidanceError."""
        command, args = query["command"], query["args"]
        self._ensure_database(query.get("database"))
        client = self._get_client()
        if dry_run or expected_max_rows is not None:
            if command not in _DRY_RUN_PROBEABLE:
                raise GuidanceError(
                    f"Redis cannot roll back {command}: dry_run/expected_max_rows only apply to DEL/UNLINK "
                    "(estimated via EXISTS)"
                )
            estimated = await client.exists(*args) if args else 0
            outcome, proceed = self._write_outcome(estimated, dry_run=dry_run, expected_max_rows=expected_max_rows)
            if not proceed:
                return outcome
        result = await client.execute_command(command, *args)
        affected = result if isinstance(result, int) and not isinstance(result, bool) else 1
        return {"applied": True, "affected": affected, "result": result}

    async def kill(self, target_id: str, *, force: bool = False) -> dict[str, Any]:
        client_id = self._int_target(target_id)
        killed = await self._get_client().execute_command("CLIENT", "KILL", "ID", client_id)
        return {"target": client_id, "killed": killed, "success": bool(killed)}

    @staticmethod
    def _int_target(target_id: str) -> int:
        try:
            return int(target_id)
        except (TypeError, ValueError):
            raise QueryValidationError(f"target_id must be a numeric client id, got {target_id!r}") from None

    async def analyze(self, database: str, obj: str | None = None) -> dict[str, Any]:
        raise GuidanceError("Redis has no planner statistics; db_perf_health shows keyspace and memory state")

    async def maintain(self, database: str, obj: str, action: str | None = None) -> dict[str, Any]:
        raise GuidanceError("Redis needs no vacuum/optimize; memory is managed by eviction policies")

    async def cluster_action(self, action: str, seconds: int | None = None) -> dict[str, Any]:
        if action != "promote":
            raise GuidanceError("Redis supports the cluster action 'promote' (REPLICAOF NO ONE)")
        await self._get_client().execute_command("REPLICAOF", "NO", "ONE")
        return {"action": "promote", "success": True, "note": "This server no longer replicates from a master"}
