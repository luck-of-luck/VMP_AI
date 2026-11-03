from __future__ import annotations

from typing import Any

import aiosqlite

from ...errors import GuidanceError, QueryValidationError
from ._common import _ident

_MAINTAIN_ACTIONS = ("vacuum", "reindex")


class SqliteWriteMixin:
    """SQLiteAdapter write operations."""

    async def write(
        self,
        query: Any,
        params: list[Any] | None,
        *,
        dry_run: bool = False,
        expected_max_rows: int | None = None,
    ) -> dict[str, Any]:
        """Run the write in a transaction, committing per the shared protocol (probe first when estimable)."""
        if dry_run or expected_max_rows is not None:
            estimated = await self._estimate_affected(query, params)
            if estimated is not None:
                outcome, commit = self._write_outcome(estimated, dry_run=dry_run, expected_max_rows=expected_max_rows)
                if not commit:
                    return outcome
        async with aiosqlite.connect(self._path, timeout=self._busy_timeout_s) as conn:
            cursor = await conn.execute(query, params or [])
            outcome, commit = self._write_outcome(
                max(cursor.rowcount, 0), dry_run=dry_run, expected_max_rows=expected_max_rows
            )
            await (conn.commit() if commit else conn.rollback())
            return outcome

    async def kill(self, target_id: str, *, force: bool = False) -> dict[str, Any]:
        raise GuidanceError("SQLite is in-process: there are no sessions to kill")

    async def analyze(self, database: str, obj: str | None = None) -> dict[str, Any]:
        schema = await self._ensure_schema(database)
        target = f"{_ident(schema)}.{_ident(obj)}" if obj else _ident(schema)
        await self.write(f"ANALYZE {target}", None)
        return {"analyzed": f"{database}.{obj}" if obj else database}

    async def maintain(self, database: str, obj: str, action: str | None = None) -> dict[str, Any]:
        if action not in (None, *_MAINTAIN_ACTIONS):
            raise QueryValidationError(f"SQLite supports actions {_MAINTAIN_ACTIONS}, got '{action}'")
        schema = await self._ensure_schema(database)
        if action == "vacuum":
            await self.write(f"VACUUM {_ident(schema)}", None)
            return {"action": "vacuum", "target": database}
        await self.write(f"REINDEX {_ident(schema)}.{_ident(obj)}", None)
        return {"action": "reindex", "target": f"{database}.{obj}"}
