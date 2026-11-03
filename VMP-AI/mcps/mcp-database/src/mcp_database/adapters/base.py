from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import sqlglot
from sqlglot.errors import SqlglotError

from ..config import ConnectionConfig
from ..errors import GuidanceError, QueryValidationError
from ..helpers import sql_ast

# Engine-varying features a caller can query up front, instead of discovering them via GuidanceError.
CAPABILITY_NAMES = frozenset(
    {
        "hypothetical_indexes",  # db_perf_explain hypothetical_indexes (HypoPG)
        "column_stats",  # db_perf_column_stats
        "planner_analyze",  # db_admin_analyze refreshes planner statistics
        "transactional_ddl",  # DDL can be dry-run / rolled back
        "server_side_sampling",  # db_read_sample uses real random sampling
        "vector_search",  # db_read_vector_search (pgvector / Atlas $vectorSearch)
    }
)


class Adapter(ABC):
    """Contract every database engine implements; tools only ever talk to this interface.

    Methods return JSON-friendly dicts/lists (ToolContext.run converts driver-native values).
    When the engine lacks a feature or privilege, implementations raise GuidanceError naming the fix.
    """

    CAPABILITIES: frozenset[str] = frozenset()

    def __init__(self, config: ConnectionConfig) -> None:
        self.config = config

    def capabilities(self) -> list[str]:
        """Engine-varying features this adapter supports, sorted (a subset of CAPABILITY_NAMES)."""
        return sorted(self.CAPABILITIES)

    def supports(self, feature: str) -> bool:
        """Whether this engine supports a named capability."""
        return feature in self.CAPABILITIES

    @staticmethod
    def _write_outcome(affected: int, *, dry_run: bool, expected_max_rows: int | None) -> tuple[dict[str, Any], bool]:
        """Shared write protocol; the second element tells the caller whether to commit."""
        if expected_max_rows is not None and affected > expected_max_rows:
            outcome = {
                "applied": False,
                "affected": affected,
                "aborted": f"would affect {affected} rows, above expected_max_rows={expected_max_rows}",
            }
            return outcome, False
        if dry_run:
            return {"applied": False, "dry_run": True, "would_affect": affected}, False
        return {"applied": True, "affected": affected}, True

    async def close(self) -> None:  # noqa: B027 - optional hook, most adapters override
        """Release pools/clients; the adapter must be able to reopen lazily afterwards."""

    @abstractmethod
    async def ping(self) -> None:
        """Cheapest possible connectivity check; raises if the server is unreachable."""

    @abstractmethod
    async def list_databases(self) -> list[dict[str, Any]]:
        """The databases/schemas visible on this connection, system ones excluded."""

    @abstractmethod
    async def list_objects(self, database: str, object_type: str | None = None) -> list[dict[str, Any]]:
        """Tables/views/collections in one database, optionally filtered by type."""

    @abstractmethod
    async def describe_object(self, database: str, obj: str, *, sample: bool = True) -> dict[str, Any]:
        """Columns/fields, indexes and stats of one object; raises 'not found' for a missing object."""

    @abstractmethod
    async def get_ddl(self, database: str, obj: str) -> dict[str, Any]:
        """The CREATE statement (or reconstruction) of one object."""

    @abstractmethod
    async def search(self, pattern: str, scope: str | None = None) -> dict[str, Any]:
        """Find objects/columns whose name contains the pattern as a literal substring (never a regex)."""

    @abstractmethod
    async def relationships(self, database: str, obj: str | None = None) -> dict[str, Any]:
        """Foreign keys (SQL) or inferred references between objects."""

    @abstractmethod
    async def users(self, user: str | None = None) -> list[dict[str, Any]]:
        """Database accounts, optionally filtered to one user."""

    @abstractmethod
    async def grants(self, user: str | None = None, obj: str | None = None) -> list[dict[str, Any]]:
        """Privileges by user and/or object."""

    @abstractmethod
    async def read(self, query: Any, params: list[Any] | None, limit: int | None) -> list[dict[str, Any]]:
        """Execute an already-validated read query and return its rows (over-fetching limit+1)."""

    @abstractmethod
    async def sample(self, database: str, obj: str, n: int) -> list[dict[str, Any]]:
        """n example rows/documents from one object."""

    @abstractmethod
    async def explain(
        self, query: Any, *, analyze: bool = False, hypothetical_indexes: list[str] | None = None
    ) -> dict[str, Any]:
        """The execution plan of a read query; analyze=True actually runs it for real timings.

        hypothetical_indexes simulates CREATE INDEX statements before planning (PostgreSQL/hypopg only;
        other engines raise GuidanceError).
        """

    @abstractmethod
    async def top_queries(self, sort_by: str, limit: int, database: str | None = None) -> list[dict[str, Any]]:
        """The heaviest recorded statements; GuidanceError when the stats extension/profiler is off."""

    @abstractmethod
    async def active_ops(self, min_duration_ms: int = 0) -> list[dict[str, Any]]:
        """Currently running operations, filterable by minimum duration."""

    @abstractmethod
    async def blocking(self) -> list[dict[str, Any]]:
        """Lock waits: who is blocked and by whom."""

    @abstractmethod
    async def index_stats(self, database: str | None = None) -> dict[str, Any]:
        """Index usage, flagging unused and redundant indexes."""

    @abstractmethod
    async def table_stats(self, database: str | None = None) -> list[dict[str, Any]]:
        """Size and activity per table/collection."""

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Overall server health: connections, uptime, cache/traffic counters."""

    @abstractmethod
    async def replication(self) -> dict[str, Any]:
        """Replication topology and role; standalone servers report that explicitly."""

    @abstractmethod
    async def settings(self, pattern: str | None = None) -> list[dict[str, Any]]:
        """Server configuration values, optionally filtered by name substring."""

    @abstractmethod
    async def logs(self, limit: int = 100, level: str | None = None) -> list[dict[str, Any]]:
        """Recent server log entries; GuidanceError when logs are not readable on this setup."""

    @abstractmethod
    async def write(
        self,
        query: Any,
        params: list[Any] | None,
        *,
        dry_run: bool = False,
        expected_max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Apply an already-authorized write; honors dry_run (roll back) and the expected_max_rows abort."""

    @abstractmethod
    async def kill(self, target_id: str, *, force: bool = False) -> dict[str, Any]:
        """Cancel (or with force=True terminate) one running operation/session."""

    async def analyze(self, database: str, obj: str | None = None) -> dict[str, Any]:
        """Refresh planner statistics; the default says this engine has no equivalent."""
        raise GuidanceError(f"{self.config.type} has no planner-statistics equivalent of ANALYZE")

    async def column_stats(self, database: str, obj: str, column: str | None = None) -> list[dict[str, Any]]:
        """Planner statistics per column (cardinality, common values); the default says the engine has none."""
        raise GuidanceError(
            f"{self.config.type} has no planner column statistics; db_schema_describe shows sampled field shapes"
        )

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
        """K-nearest-neighbor search over a vector column/field; the default says the engine has none."""
        raise GuidanceError(f"{self.config.type} has no vector similarity search")

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
        """Relevance-ranked full-text search; the default says the engine has none."""
        raise GuidanceError(f"{self.config.type} has no full-text search")

    async def search_indexes(self, database: str | None = None, obj: str | None = None) -> dict[str, Any]:
        """Vector and full-text indexes with their definitions; the default says the engine has none."""
        raise GuidanceError(f"{self.config.type} has no vector or full-text indexes")

    async def storage(self, database: str | None = None) -> dict[str, Any]:
        """Raw storage sections (sizes, logs/journals, temp usage); the default says the engine has none."""
        raise GuidanceError(f"{self.config.type} exposes no storage breakdown")

    async def config_signals(self) -> dict[str, Any]:
        """Raw configuration-vs-workload signals; the default says the engine has none."""
        raise GuidanceError(f"{self.config.type} exposes no configuration signals")

    async def index_signals(self, database: str | None = None) -> dict[str, Any]:
        """Raw missing/ineffective-index signals; the default says the engine has none."""
        raise GuidanceError(f"{self.config.type} has no index usage statistics to advise on")

    async def vector_stats(self, database: str | None = None, obj: str | None = None) -> dict[str, Any]:
        """Raw sections about vector columns/indexes and their tuning; the default says the engine has none."""
        raise GuidanceError(f"{self.config.type} has no vector search support to inspect")

    async def search_index_write(
        self, database: str, obj: str, action: str, name: str, definition: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create/update/drop one vector or full-text index; the default says the engine has none."""
        raise GuidanceError(f"{self.config.type} has no vector or full-text indexes to manage")

    async def cluster_action(self, action: str, seconds: int | None = None) -> dict[str, Any]:
        """Run one allowlisted cluster/replication action; the default lists none for this engine."""
        raise GuidanceError(f"{self.config.type} has no cluster action '{action}' on this server")

    @abstractmethod
    async def maintain(self, database: str, obj: str, action: str | None = None) -> dict[str, Any]:
        """Run the engine's maintenance action on one object (VACUUM/OPTIMIZE/compact)."""


class SQLAdapter(Adapter):
    """Shared behavior for SQL engines: reads go through the driver-specific `_fetch_once`."""

    _SEARCH_OBJECTS_SQL: str
    _SEARCH_COLUMNS_SQL: str
    _DIALECT: str
    _TRANSIENT_RETRY_DELAY_S = 0.2

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        """Whether the error means the connection died (safe to retry a read); engines override."""
        return False

    async def _fetch(
        self,
        query: Any,
        params: Any = None,
        *,
        limit: int | None = None,
        readonly: bool = True,
    ) -> list[dict[str, Any]]:
        """Run one statement, retrying once on a fresh connection after a transient failure — reads only.

        Statements run with readonly=False (writes, kill) are never retried: they may have side effects.
        """
        try:
            return await self._fetch_once(query, params, limit=limit, readonly=readonly)
        except Exception as exc:
            if not readonly or not self._is_transient(exc):
                raise
            await asyncio.sleep(self._TRANSIENT_RETRY_DELAY_S)
            return await self._fetch_once(query, params, limit=limit, readonly=readonly)

    @abstractmethod
    async def _fetch_once(
        self,
        query: Any,
        params: Any = None,
        *,
        limit: int | None = None,
        readonly: bool = True,
    ) -> list[dict[str, Any]]:
        """Run one statement on a pooled connection with the engine's timeout; readonly reads never commit."""

    async def read(self, query: Any, params: list[Any] | None, limit: int | None) -> list[dict[str, Any]]:
        return await self._fetch(query, params, limit=limit)

    async def search(self, pattern: str, scope: str | None = None) -> dict[str, Any]:
        like = self._like_contains(pattern)
        result: dict[str, Any] = {}
        if scope in (None, "objects"):
            result["objects"] = await self._fetch(self._SEARCH_OBJECTS_SQL, (like,))
        if scope in (None, "columns"):
            result["columns"] = await self._fetch(self._SEARCH_COLUMNS_SQL, (like,))
        return result

    async def _estimate_affected(self, query: Any, params: Any) -> int | None:
        """Affected-rows estimate for a simple literal UPDATE/DELETE via SELECT count(*), skipping execution.

        A dry run that executes and rolls back still pays the full cost (dead tuples, WAL); the count
        probe does not. Returns None when not estimable (parameterized, joins, DDL, unparseable):
        callers then fall back to running the statement inside a rolled-back transaction.
        """
        if not isinstance(query, str) or params:
            return None
        try:
            tree = sqlglot.parse_one(query, read=self._DIALECT)
        except SqlglotError:
            return None
        probe = sql_ast.count_probe(tree)
        if probe is None:
            return None
        rows = await self._fetch(probe.sql(dialect=self._DIALECT))
        return int(rows[0]["n"]) if rows else None

    @staticmethod
    def _int_target(target_id: str, label: str) -> int:
        """Parse the kill target as an int, rejecting anything non-numeric before it reaches SQL."""
        try:
            return int(target_id)
        except ValueError:
            raise QueryValidationError(f"target_id must be a numeric {label}, got {target_id!r}") from None

    @staticmethod
    def _like_contains(pattern: str) -> str:
        """Turn a user search string into a literal LIKE argument: escape the `\\ % _` wildcards.

        Keeps a search pattern a plain substring (never a wildcard/regex language), matching the
        MongoDB substring adapter. Callers must pair it with the default `\\` LIKE escape character.
        """
        escaped = pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"
