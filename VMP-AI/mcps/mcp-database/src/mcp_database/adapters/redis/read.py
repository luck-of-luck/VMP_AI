from __future__ import annotations

from typing import Any

from ...errors import GuidanceError, QueryValidationError


class RedisReadMixin:
    """RedisAdapter read operations."""

    async def read(self, query: Any, params: list[Any] | None, limit: int | None) -> list[dict[str, Any]]:
        if params:
            raise QueryValidationError("Redis commands take no bind parameters; put every argument in 'args'")
        self._ensure_database(query.get("database"))
        result = await self._get_client().execute_command(query["command"], *query["args"])
        return self._rows(result, limit)

    @staticmethod
    def _rows(result: Any, limit: int | None = None) -> list[dict[str, Any]]:
        if isinstance(result, dict):
            rows = [{"field": key, "value": value} for key, value in result.items()]
        elif isinstance(result, (list, tuple)):
            rows = [{"value": item} for item in result]
        else:
            rows = [{"result": result}]
        return rows[: limit + 1] if limit is not None else rows

    async def sample(self, database: str, obj: str, n: int) -> list[dict[str, Any]]:
        self._ensure_database(database)
        client = self._get_client()
        kind = await client.type(obj)
        if kind == "none":
            raise QueryValidationError(f"Key '{obj}' not found in database {self._db_index}")
        if kind == "string":
            value = await client.getrange(obj, 0, 500)
            return [{"value": value}]
        if kind == "hash":
            fields = await client.hrandfield(obj, n, withvalues=True)
            if fields and not isinstance(fields[0], (list, tuple)):
                fields = list(zip(fields[::2], fields[1::2], strict=True))
            return [{"field": field, "value": value} for field, value in fields]
        if kind == "list":
            return self._rows(await client.lrange(obj, 0, n - 1))
        if kind == "set":
            return self._rows(await client.srandmember(obj, n))
        if kind == "zset":
            members = await client.zrandmember(obj, n, True)
            if members and not isinstance(members[0], (list, tuple)):
                members = list(zip(members[::2], members[1::2], strict=True))
            return [{"member": member, "score": score} for member, score in members]
        raise GuidanceError(f"Sampling is not implemented for type '{kind}'")
