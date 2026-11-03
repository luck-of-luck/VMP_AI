from __future__ import annotations

from pymongo import AsyncMongoClient
from pymongo.errors import ConfigurationError

from ...errors import QueryValidationError
from ..base import Adapter
from .perf import MongoPerfMixin
from .read import MongoReadMixin
from .schema import MongoSchemaMixin
from .write import MongoWriteMixin


class MongoAdapter(MongoSchemaMixin, MongoReadMixin, MongoPerfMixin, MongoWriteMixin, Adapter):
    """MongoDB over PyMongo async; every read op carries maxTimeMS so filters stay time-bounded."""

    CAPABILITIES = frozenset({"server_side_sampling", "vector_search"})

    _client: AsyncMongoClient | None = None

    def _get_client(self) -> AsyncMongoClient:
        """The lazy client (connect_timeout_s selection/connect timeouts), created on first use."""
        if self._client is None:
            timeout_ms = self.config.connect_timeout_s * 1000
            self._client = AsyncMongoClient(
                self.config.resolved_uri(),
                serverSelectionTimeoutMS=timeout_ms,
                connectTimeoutMS=timeout_ms,
                maxPoolSize=self.config.pool_size,
                appname=f"mcp-database/{self.config.name}",
            )
        return self._client

    def _db(self, database: str | None):
        """The requested database, or the URI's default; a clear error when neither exists."""
        client = self._get_client()
        if database:
            return client[database]
        try:
            return client.get_default_database()
        except ConfigurationError:
            raise QueryValidationError(
                f"Connection '{self.config.name}' has no default database in its URI; pass 'database' explicitly"
            ) from None

    @property
    def _timeout_ms(self) -> int:
        """The connection's query timeout as the maxTimeMS every read op carries."""
        return self.config.query_timeout_s * 1000

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            await client.close()

    async def ping(self) -> None:
        await self._get_client().admin.command("ping")
