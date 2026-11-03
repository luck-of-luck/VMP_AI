from __future__ import annotations

import contextlib
from typing import Any

from psycopg import sql

from ...errors import GuidanceError, QueryValidationError
from ._common import _VECTOR_INDEX_OPTIONS, _VECTOR_OPCLASSES, _qualified


class PgWriteMixin:
    """PostgresAdapter write operations."""

    async def write(
        self,
        query: Any,
        params: list[Any] | None,
        *,
        dry_run: bool = False,
        expected_max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Run the write in a transaction; dry_run/abort exits via a rollback sentinel instead of committing.

        When intent was declared (dry_run/expected_max_rows) and the statement is a simple UPDATE/DELETE,
        the impact comes from a count(*) probe — a rolled-back execution would still create dead tuples.
        """
        if dry_run or expected_max_rows is not None:
            estimated = await self._estimate_affected(query, params)
            if estimated is not None:
                outcome, commit = self._write_outcome(estimated, dry_run=dry_run, expected_max_rows=expected_max_rows)
                if not commit:
                    return outcome
        pool = await self._ensure_pool()

        class _Rollback(Exception):  # noqa: N818 - control-flow sentinel, not an error
            pass

        outcome: dict[str, Any] = {}
        async with pool.connection() as conn:
            try:
                async with conn.transaction():
                    await conn.execute(
                        sql.SQL("SET LOCAL statement_timeout = {}").format(
                            sql.Literal(self.config.query_timeout_s * 1000)
                        )
                    )
                    await conn.execute(
                        sql.SQL("SET LOCAL lock_timeout = {}").format(sql.Literal(self._lock_timeout_ms))
                    )
                    cursor = await conn.execute(query, params)
                    outcome, commit = self._write_outcome(
                        max(cursor.rowcount, 0), dry_run=dry_run, expected_max_rows=expected_max_rows
                    )
                    if not commit:
                        raise _Rollback
            except _Rollback:
                pass
        return outcome

    async def kill(self, target_id: str, *, force: bool = False) -> dict[str, Any]:
        pid = self._int_target(target_id, "backend pid")
        function = "pg_terminate_backend" if force else "pg_cancel_backend"
        rows = await self._fetch(sql.SQL("SELECT {}(%s) AS success").format(sql.SQL(function)), (pid,), readonly=False)
        return {"target": pid, "action": "terminate" if force else "cancel", "success": rows[0]["success"]}

    async def analyze(self, database: str, obj: str | None = None) -> dict[str, Any]:
        statement = sql.SQL("ANALYZE {}").format(_qualified(database, obj)) if obj else sql.SQL("ANALYZE")
        await self._fetch(statement, readonly=False)
        return {"analyzed": f"{database}.{obj}" if obj else "all tables", "status": "ok"}

    async def maintain(self, database: str, obj: str, action: str | None = None) -> dict[str, Any]:
        """VACUUM (ANALYZE) one table; VACUUM cannot run in a transaction, so autocommit is toggled around it."""
        if action not in (None, "vacuum"):
            raise QueryValidationError(f"PostgreSQL supports action 'vacuum', got '{action}'")
        pool = await self._ensure_pool()
        async with pool.connection() as conn:
            await conn.set_autocommit(True)
            try:
                await conn.execute(sql.SQL("SET lock_timeout = {}").format(sql.Literal(self._lock_timeout_ms)))
                await conn.execute(sql.SQL("VACUUM (ANALYZE) {}").format(_qualified(database, obj)))
            finally:
                with contextlib.suppress(Exception):
                    await conn.execute("RESET lock_timeout")
                await conn.set_autocommit(False)
        return {"maintained": f"{database}.{obj}", "action": "vacuum", "status": "ok"}

    async def search_index_write(
        self, database: str, obj: str, action: str, name: str, definition: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Create or drop a pgvector index; method, metric and options come from internal allowlists only."""
        if action == "drop":
            await self._fetch(sql.SQL("DROP INDEX {}").format(_qualified(database, name)), readonly=False)
            return {"applied": True, "action": "drop", "index": f"{database}.{name}"}
        if action == "update":
            raise GuidanceError(
                "PostgreSQL vector indexes cannot be updated in place; drop and recreate, "
                "or ALTER INDEX ... SET (...) via db_write_query for storage options"
            )
        if action != "create":
            raise QueryValidationError(f"Unknown action '{action}' (supported: create, update, drop)")
        await self._pgvector_version()
        definition = definition or {}
        column = definition.get("column")
        if not isinstance(column, str) or not column:
            raise QueryValidationError("create requires definition.column (the vector column to index)")
        method = definition.get("method", "hnsw")
        allowed_options = _VECTOR_INDEX_OPTIONS.get(method)
        if allowed_options is None:
            raise QueryValidationError(f"Unknown method '{method}' (supported: {', '.join(_VECTOR_INDEX_OPTIONS)})")
        opclass = _VECTOR_OPCLASSES.get(definition.get("metric", "cosine"))
        if opclass is None:
            raise QueryValidationError(
                f"Unknown metric '{definition.get('metric')}' (supported: {', '.join(sorted(_VECTOR_OPCLASSES))})"
            )
        options = definition.get("options") or {}
        if not isinstance(options, dict):
            raise QueryValidationError("definition.options must be an object of index build parameters")
        unknown = set(options) - allowed_options
        if unknown:
            raise QueryValidationError(
                f"Unknown {method} options: {', '.join(sorted(unknown))} "
                f"(supported: {', '.join(sorted(allowed_options))})"
            )
        values: dict[str, int] = {}
        for key, value in options.items():
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise QueryValidationError(f"Option '{key}' must be a positive integer")
            values[key] = value
        statement = sql.SQL("CREATE INDEX {name} ON {tbl} USING {method} ({col} {opclass})").format(
            name=sql.Identifier(name),
            tbl=_qualified(database, obj),
            method=sql.SQL(method),
            col=sql.Identifier(column),
            opclass=sql.SQL(opclass),
        )
        if values:
            pairs = [sql.SQL("{} = {}").format(sql.SQL(key), sql.Literal(value)) for key, value in values.items()]
            statement = sql.SQL("{} WITH ({})").format(statement, sql.SQL(", ").join(pairs))
        await self._fetch(statement, readonly=False)
        return {"applied": True, "action": "create", "index": f"{database}.{name}", "method": method}

    async def cluster_action(self, action: str, seconds: int | None = None) -> dict[str, Any]:
        """Standby-only actions: promote ends recovery for good, pause/resume_replay freeze and resume WAL replay."""
        if action not in ("promote", *self._REPLICA_ACTIONS):
            raise GuidanceError(
                f"PostgreSQL supports cluster actions 'promote', 'pause_replay', 'resume_replay' "
                f"(on a replica), got '{action}'"
            )
        in_recovery = (await self._fetch("SELECT pg_is_in_recovery() AS in_recovery"))[0]["in_recovery"]
        if not in_recovery:
            raise QueryValidationError(f"This server is a primary; {action} applies to a streaming replica")
        if statement := self._REPLICA_ACTIONS.get(action):
            await self._fetch(statement, readonly=False)
            return {"action": action, "success": True}
        rows = await self._fetch("SELECT pg_promote(true, %s) AS success", (seconds or 60,), readonly=False)
        return {"action": "promote", "success": rows[0]["success"]}
