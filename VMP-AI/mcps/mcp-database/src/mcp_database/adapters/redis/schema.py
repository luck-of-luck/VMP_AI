from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from ...errors import GuidanceError, QueryValidationError

_REDIS_TYPES = ("string", "hash", "list", "set", "zset", "stream")

_SIZE_COMMANDS = {"string": "STRLEN", "hash": "HLEN", "list": "LLEN", "set": "SCARD", "zset": "ZCARD"}


def _escape_glob(pattern: str) -> str:
    """Make a user search string a literal SCAN MATCH argument: escape the glob metacharacters."""
    out = []
    for char in pattern:
        if char in "*?[]\\":
            out.append("\\")
        out.append(char)
    return "".join(out)


class RedisSchemaMixin:
    """RedisAdapter schema operations."""

    async def list_databases(self) -> list[dict[str, Any]]:
        return await self._keyspace()

    async def list_objects(self, database: str, object_type: str | None = None) -> list[dict[str, Any]]:
        if object_type not in (None, *_REDIS_TYPES):
            raise QueryValidationError(f"Unknown object_type '{object_type}' (expected: {', '.join(_REDIS_TYPES)})")
        self._ensure_database(database)
        client = self._get_client()
        keys: list[str] = []
        cursor = 0
        while len(keys) < self.config.row_limit:
            cursor, page = await client.scan(cursor=cursor, count=200)
            keys.extend(page)
            if cursor == 0:
                break
        keys = sorted(keys)[: self.config.row_limit]
        pipeline = client.pipeline(transaction=False)
        for key in keys:
            pipeline.type(key)
        types = await pipeline.execute()
        rows = [{"name": key, "type": kind} for key, kind in zip(keys, types, strict=True)]
        if object_type:
            rows = [row for row in rows if row["type"] == object_type]
        return rows

    async def describe_object(self, database: str, obj: str, *, sample: bool = True) -> dict[str, Any]:
        self._ensure_database(database)
        client = self._get_client()
        kind = await client.type(obj)
        if kind == "none":
            raise QueryValidationError(f"Key '{obj}' not found in database {self._db_index}")
        result: dict[str, Any] = {"key": obj, "type": kind, "ttl": await client.ttl(obj)}
        result["encoding"] = await client.object("ENCODING", obj)
        result["memory_bytes"] = await client.memory_usage(obj)
        if size_command := _SIZE_COMMANDS.get(kind):
            result["size"] = await client.execute_command(size_command, obj)
        if sample:
            result["sample"] = await self.sample(database, obj, 5)
        return result

    async def get_ddl(self, database: str, obj: str) -> dict[str, Any]:
        raise GuidanceError("Redis keys have no DDL; db_schema_describe_object shows type, TTL and encoding")

    async def search(self, pattern: str, scope: str | None = None) -> dict[str, Any]:
        client = self._get_client()
        match = f"*{_escape_glob(pattern)}*"
        keys: list[str] = []
        cursor = 0
        while len(keys) < 100:
            cursor, page = await client.scan(cursor=cursor, match=match, count=500)
            keys.extend(page)
            if cursor == 0:
                break
        return {"objects": [{"name": key} for key in sorted(keys)[:100]], "columns": []}

    async def relationships(self, database: str, obj: str | None = None) -> dict[str, Any]:
        raise GuidanceError("Redis has no foreign keys; key naming conventions are the only relationships")

    async def users(self, user: str | None = None) -> list[dict[str, Any]]:
        try:
            acl = await self._get_client().acl_list()
        except aioredis.ResponseError as exc:
            raise GuidanceError(f"Cannot read ACLs ({exc}). Requires Redis 6+ and the admin ACL category") from None
        return [{"acl": line} for line in acl]

    async def grants(self, user: str | None = None, obj: str | None = None) -> list[dict[str, Any]]:
        if not user:
            return await self.users()
        try:
            detail = await self._get_client().acl_getuser(user)
        except aioredis.ResponseError as exc:
            raise GuidanceError(f"Cannot read ACL for '{user}' ({exc}). Requires Redis 6+") from None
        if detail is None:
            raise QueryValidationError(f"User '{user}' not found")
        return [{"user": user, **{key: value for key, value in detail.items() if key != "passwords"}}]
