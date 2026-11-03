from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from ...errors import QueryValidationError
from ..base import Adapter
from .perf import RedisPerfMixin
from .read import RedisReadMixin
from .schema import RedisSchemaMixin
from .write import RedisWriteMixin


class RedisAdapter(RedisSchemaMixin, RedisReadMixin, RedisPerfMixin, RedisWriteMixin, Adapter):
    """Redis over redis-py asyncio: allowlisted commands only, one logical database per connection.

    The banned list (FLUSH*/EVAL/KEYS/...) is enforced in the guard before anything reaches here;
    this adapter maps the tool surface onto INFO/SCAN/SLOWLOG/CLIENT and per-key inspection.
    """

    CAPABILITIES = frozenset({"server_side_sampling"})

    def __init__(self, config: Any) -> None:
        super().__init__(config)
        self._client: aioredis.Redis | None = None

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self.config.resolved_uri(),
                decode_responses=True,
                socket_timeout=self.config.query_timeout_s,
                socket_connect_timeout=self.config.connect_timeout_s,
                client_name=f"mcp-database/{self.config.name}",
            )
        return self._client

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.aclose()

    @property
    def _db_index(self) -> str:
        return str(self._get_client().get_connection_kwargs().get("db") or 0)

    def _ensure_database(self, database: str | None) -> None:
        if database is not None and str(database) != self._db_index:
            raise QueryValidationError(
                f"This instance serves logical database {self._db_index}; "
                f"start another MCP entry with /{database} in the URI to reach database {database}"
            )

    async def ping(self) -> None:
        await self._get_client().ping()

    async def _keyspace(self) -> list[dict[str, Any]]:
        info = await self._get_client().info("keyspace")
        rows = []
        for name, stats in sorted(info.items()):
            if name.startswith("db") and isinstance(stats, dict):
                rows.append({"database": name.removeprefix("db"), **stats})
        return rows
