from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import aiomysql

from ...errors import GuidanceError, QueryValidationError
from ._common import _ident, _qualified


class MyWriteMixin:
    """MySQLAdapter write operations."""

    async def write(
        self,
        query: Any,
        params: list[Any] | None,
        *,
        dry_run: bool = False,
        expected_max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Run the write, committing per _write_outcome; on cancellation the connection is closed, not pooled.

        When intent was declared (dry_run/expected_max_rows) and the statement is a simple UPDATE/DELETE,
        the impact comes from a count(*) probe instead of executing the mutation.
        """
        if dry_run or expected_max_rows is not None:
            estimated = await self._estimate_affected(query, params)
            if estimated is not None:
                outcome, commit = self._write_outcome(estimated, dry_run=dry_run, expected_max_rows=expected_max_rows)
                if not commit:
                    return outcome
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            cursor = await conn.cursor(aiomysql.DictCursor)
            try:
                await cursor.execute("SET SESSION TRANSACTION READ WRITE")
                await cursor.execute(
                    f"SET SESSION lock_wait_timeout = {self._lock_timeout_s}, "
                    f"innodb_lock_wait_timeout = {self._lock_timeout_s}"
                )
                await cursor.execute(query, params)
                outcome, commit = self._write_outcome(
                    max(cursor.rowcount, 0), dry_run=dry_run, expected_max_rows=expected_max_rows
                )
                await (conn.commit() if commit else conn.rollback())
                return outcome
            except asyncio.CancelledError:
                conn.close()
                raise
            except Exception:
                with contextlib.suppress(Exception):
                    await conn.rollback()
                raise
            finally:
                if not conn.closed:
                    await cursor.close()

    async def kill(self, target_id: str, *, force: bool = False) -> dict[str, Any]:
        thread_id = self._int_target(target_id, "thread id")
        statement = f"KILL {thread_id}" if force else f"KILL QUERY {thread_id}"
        await self._fetch(statement, readonly=False)
        return {"target": thread_id, "action": "kill" if force else "kill query", "success": True}

    async def analyze(self, database: str, obj: str | None = None) -> dict[str, Any]:
        """ANALYZE TABLE; unlike Postgres, MySQL has no all-tables form, so an object is required."""
        if not obj:
            raise QueryValidationError("MySQL ANALYZE TABLE requires an object name")
        rows = await self._fetch(f"ANALYZE TABLE {_qualified(database, obj)}", readonly=False)
        return {"analyzed": f"{database}.{obj}", "result": rows}

    async def search_index_write(
        self, database: str, obj: str, action: str, name: str, definition: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create or drop a FULLTEXT index; identifiers are backtick-quoted, nothing else enters the DDL."""
        if action == "drop":
            await self._fetch(f"ALTER TABLE {_qualified(database, obj)} DROP INDEX {_ident(name)}", readonly=False)
            return {"applied": True, "action": "drop", "index": f"{database}.{name}"}
        if action == "update":
            raise GuidanceError("MySQL FULLTEXT indexes cannot be updated in place; drop and recreate")
        if action != "create":
            raise QueryValidationError(f"Unknown action '{action}' (supported: create, update, drop)")
        definition = definition or {}
        columns = definition.get("columns")
        if columns is None and isinstance(definition.get("column"), str):
            columns = [definition["column"]]
        if not isinstance(columns, list) or not columns or any(not isinstance(c, str) or not c for c in columns):
            raise QueryValidationError("create requires definition.columns (non-empty list of text columns)")
        column_list = ", ".join(_ident(c) for c in columns)
        await self._fetch(
            f"CREATE FULLTEXT INDEX {_ident(name)} ON {_qualified(database, obj)} ({column_list})",
            readonly=False,
        )
        return {
            "applied": True,
            "action": "create",
            "index": f"{database}.{name}",
            "note": "MySQL DDL commits implicitly and cannot be rolled back",
        }

    async def cluster_action(self, action: str, seconds: int | None = None) -> dict[str, Any]:
        """start/stop the replication threads on a configured replica; the statement is fixed, never composed."""
        statement = {"start_replica": "START REPLICA", "stop_replica": "STOP REPLICA"}.get(action)
        if statement is None:
            raise GuidanceError(
                f"MySQL supports cluster actions 'start_replica' and 'stop_replica' (on a replica), got '{action}'"
            )
        if seconds is not None:
            raise QueryValidationError("'seconds' applies to MongoDB step_down/freeze only")
        status = await self._fetch("SHOW REPLICA STATUS")
        if not status:
            raise GuidanceError(
                "This server has no replication source configured; "
                "start_replica/stop_replica apply to a replica (CHANGE REPLICATION SOURCE first)"
            )
        await self._fetch(statement, readonly=False)
        return {"action": action, "success": True}

    async def maintain(self, database: str, obj: str, action: str | None = None) -> dict[str, Any]:
        """OPTIMIZE TABLE — on InnoDB this is ALTER TABLE FORCE: a full rebuild, reported with the table size."""
        if action not in (None, "optimize"):
            raise QueryValidationError(f"MySQL supports action 'optimize', got '{action}'")
        size = await self._fetch(
            "SELECT data_length + index_length AS total FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name = %s",
            (database, obj),
        )
        rows = await self._fetch(f"OPTIMIZE TABLE {_qualified(database, obj)}", readonly=False)
        return {
            "maintained": f"{database}.{obj}",
            "action": "optimize",
            "result": rows,
            "table_bytes": size[0]["total"] if size else None,
            "note": (
                "OPTIMIZE TABLE rebuilds InnoDB tables (ALTER TABLE FORCE): "
                "expect locks and long runtime on large tables"
            ),
        }
