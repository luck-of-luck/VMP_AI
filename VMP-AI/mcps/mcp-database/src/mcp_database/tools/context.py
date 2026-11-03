from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .. import guard
from ..adapters import Adapter, create_adapter
from ..audit import AuditLogger
from ..config import ConnectionConfig
from ..errors import McpDatabaseError, QueryValidationError, UnknownConnectionError
from ..formatter import redact_uri_passwords, sanitize_error, to_jsonable
from ..guard import ToolClass


@dataclass
class ToolContext:
    """Shared runtime for all tool modules: connection registry, lazy adapters and audit log."""

    registry: dict[str, ConnectionConfig]
    audit: AuditLogger
    adapters: dict[str, Adapter] = field(default_factory=dict)

    def cfg_of(self, conn: str) -> ConnectionConfig:
        """The config for a connection name, or UnknownConnectionError listing the configured ones."""
        try:
            return self.registry[conn]
        except KeyError:
            raise UnknownConnectionError(conn, list(self.registry)) from None

    def adapter_of(self, cfg: ConnectionConfig) -> Adapter:
        """The adapter for a connection, created lazily on first use and cached until close_all."""
        if cfg.name not in self.adapters:
            self.adapters[cfg.name] = create_adapter(cfg)
        return self.adapters[cfg.name]

    async def run(self, cfg: ConnectionConfig, coro: Any) -> Any:
        """Execute an adapter coroutine with a timeout, then normalize the result for the MCP boundary.

        Driver-native values (MongoDB ObjectId, bytes, datetime, Decimal, ...) are not serializable by
        FastMCP; to_jsonable converts them here, the single point every adapter result flows through.
        """
        try:
            result = await asyncio.wait_for(coro, timeout=cfg.query_timeout_s + 5)
        except TimeoutError:
            raise McpDatabaseError(
                f"Operation on '{cfg.name}' exceeded {cfg.query_timeout_s}s and was cancelled"
            ) from None
        except McpDatabaseError:
            raise
        except Exception as exc:
            raise McpDatabaseError(sanitize_error(f"{type(exc).__name__}: {exc}")) from None
        return to_jsonable(result)

    def validated_read(self, cfg: ConnectionConfig, query: Any, tool_class: ToolClass) -> Any:
        """Validate a read query for this engine (guard + database_modes) and return the parsed form."""
        if cfg.type == "mongodb":
            parsed = guard.validate_mongo_read(query)
            databases = {parsed["database"]} if parsed.get("database") else set()
            guard.ensure_databases_allowed(cfg, tool_class, databases)
            return parsed
        if cfg.type == "redis":
            parsed = guard.validate_redis_read(query)
            databases = {parsed["database"]} if parsed.get("database") else set()
            guard.ensure_databases_allowed(cfg, tool_class, databases)
            return parsed
        if not isinstance(query, str):
            raise QueryValidationError(f"Connection '{cfg.name}' is {cfg.type}: 'query' must be a SQL string")
        guard.validate_sql_read(query, cfg.type)
        guard.ensure_databases_allowed(cfg, tool_class, guard.sql_databases(query, cfg.type))
        return query

    @staticmethod
    def with_cap_note(result: dict[str, Any], **caps: int) -> dict[str, Any]:
        """Append a note when a result list hit its cap, telling the caller how to see the rest."""
        capped = [
            f"'{key}' capped at {cap}"
            for key, cap in caps.items()
            if isinstance(result.get(key), list) and len(result[key]) >= cap
        ]
        if capped:
            result["note"] = ", ".join(capped) + " — refine the pattern or filter to see the rest"
        return result

    def write_context(
        self, cfg: ConnectionConfig, query: Any, *, expected_max_rows: int | None = None, dry_run: bool = False
    ) -> tuple[Any, str, Any]:
        """Validate and authorize a write; returns (parsed_query, operation, audit_shape).

        audit_shape is the query with literals replaced by placeholders — logged instead of raw values.
        In every path: authorization first (mode/database_modes/write_ops), then the mass-mutation nag,
        which is skipped when the caller declared intent (a dry run or an expected_max_rows bound).
        """
        declared_intent = dry_run or expected_max_rows is not None
        if cfg.type == "mongodb":
            parsed, op = guard.classify_mongo_write(query)
            databases = {parsed["database"]} if parsed.get("database") else set()
            guard.ensure_databases_allowed(cfg, ToolClass.WRITE, databases)
            guard.ensure_write_op_allowed(cfg, op)
            if not declared_intent:
                guard.ensure_bounded_mongo_write(parsed)
            return parsed, op, guard.mongo_audit_shape(parsed)

        if cfg.type == "redis":
            parsed, op = guard.classify_redis_write(query)
            databases = {parsed["database"]} if parsed.get("database") else set()
            guard.ensure_databases_allowed(cfg, ToolClass.WRITE, databases)
            guard.ensure_write_op_allowed(cfg, op)
            return parsed, op, guard.redis_audit_shape(parsed)

        if not isinstance(query, str):
            raise QueryValidationError(f"Connection '{cfg.name}' is {cfg.type}: 'query' must be a SQL string")
        info = guard.analyze_sql_write(query, cfg.type)
        guard.ensure_databases_allowed(cfg, ToolClass.WRITE, info.databases)
        guard.ensure_write_op_allowed(cfg, info.op)
        if not declared_intent:
            guard.ensure_bounded_sql_write(info.op, info.unbounded)
        return query, info.op, info.audit_shape

    async def run_audited(
        self,
        cfg: ConnectionConfig,
        tool: str,
        query: Any,
        coro: Any,
        *,
        dry_run: bool = False,
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run a destructive operation and audit it: failures are logged best-effort, but a missing
        audit entry for an *applied* operation raises an explicit 'applied, but audit logging failed' error."""
        started = time.perf_counter()
        try:
            result = await self.run(cfg, coro)
        except McpDatabaseError as exc:
            try:
                await self._record_with_retry(
                    connection=cfg.name,
                    tool=tool,
                    query=query,
                    ok=False,
                    dry_run=dry_run,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    error=str(exc),
                    detail=detail,
                )
            except Exception:
                logging.getLogger(__name__).warning("Audit logging failed for %s on '%s'", tool, cfg.name)
            raise
        try:
            await self._record_with_retry(
                connection=cfg.name,
                tool=tool,
                query=query,
                ok=True,
                dry_run=dry_run or bool(result.get("dry_run")),
                affected=result.get("affected", result.get("would_affect", result.get("row_count"))),
                duration_ms=(time.perf_counter() - started) * 1000,
                detail=detail,
            )
        except Exception as exc:
            raise McpDatabaseError(
                redact_uri_passwords(
                    f"{tool} on '{cfg.name}' succeeded and its effects were applied, but audit logging failed: {exc}"
                )
            ) from None
        return result

    async def _record_with_retry(self, **kwargs: Any) -> None:
        """Write one audit entry, retrying once after a short pause before giving up."""
        try:
            await asyncio.to_thread(self.audit.record, **kwargs)
        except Exception:
            await asyncio.sleep(0.05)
            await asyncio.to_thread(self.audit.record, **kwargs)

    async def close_all(self) -> None:
        """Close every cached adapter (called from the server lifespan), swallowing per-adapter errors."""
        for adapter in self.adapters.values():
            with contextlib.suppress(Exception):
                await adapter.close()
