from __future__ import annotations

from typing import Any

from ...errors import GuidanceError, QueryValidationError
from ._common import _ident


class SqliteSchemaMixin:
    """SQLiteAdapter schema operations."""

    async def list_databases(self) -> list[dict[str, Any]]:
        rows = await self._fetch("PRAGMA database_list")
        return [{"database": row["name"], "file": row["file"]} for row in rows]

    async def list_objects(self, database: str, object_type: str | None = None) -> list[dict[str, Any]]:
        if object_type not in (None, "table", "view", "index"):
            raise QueryValidationError(f"Unknown object_type '{object_type}' (expected: table, view, index)")
        schema = await self._ensure_schema(database)
        rows = await self._fetch(
            f"SELECT name, type AS kind FROM {_ident(schema)}.sqlite_master "
            "WHERE type IN ('table', 'view', 'index') AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        if object_type:
            rows = [row for row in rows if row["kind"] == object_type]
        return rows

    async def describe_object(self, database: str, obj: str, *, sample: bool = True) -> dict[str, Any]:
        schema = await self._ensure_schema(database)
        columns = await self._fetch(f"PRAGMA {_ident(schema)}.table_info({_ident(obj)})")
        if not columns:
            raise QueryValidationError(f"Object '{database}.{obj}' not found")
        result: dict[str, Any] = {
            "columns": [
                {
                    "name": col["name"],
                    "type": col["type"],
                    "nullable": not col["notnull"],
                    "default": col["dflt_value"],
                    "primary_key": bool(col["pk"]),
                }
                for col in columns
            ],
            "indexes": await self._fetch(f"PRAGMA {_ident(schema)}.index_list({_ident(obj)})"),
            "foreign_keys": await self._fetch(f"PRAGMA {_ident(schema)}.foreign_key_list({_ident(obj)})"),
        }
        if sample:
            result["sample"] = await self._fetch(f"SELECT * FROM {_ident(schema)}.{_ident(obj)} LIMIT 5")
        return result

    async def get_ddl(self, database: str, obj: str) -> dict[str, Any]:
        schema = await self._ensure_schema(database)
        rows = await self._fetch(
            f"SELECT sql FROM {_ident(schema)}.sqlite_master WHERE name = ? AND sql IS NOT NULL", (obj,)
        )
        if not rows:
            raise QueryValidationError(f"Object '{database}.{obj}' not found")
        indexes = await self._fetch(
            f"SELECT sql FROM {_ident(schema)}.sqlite_master WHERE tbl_name = ? AND type = 'index' AND sql IS NOT NULL",
            (obj,),
        )
        statements = [rows[0]["sql"] + ";"] + [row["sql"] + ";" for row in indexes]
        return {"ddl": "\n".join(statements)}

    async def relationships(self, database: str, obj: str | None = None) -> dict[str, Any]:
        schema = await self._ensure_schema(database)
        rows = await self._fetch(
            f"""
            SELECT m.name AS from_table, f."table" AS to_table, f."from" AS from_column, f."to" AS to_column
            FROM {_ident(schema)}.sqlite_master m JOIN pragma_foreign_key_list(m.name) f
            WHERE m.type = 'table' ORDER BY m.name
            """
        )
        if obj:
            rows = [row for row in rows if obj in (row["from_table"], row["to_table"])]
        return {"relationships": rows}

    async def users(self, user: str | None = None) -> list[dict[str, Any]]:
        raise GuidanceError("SQLite has no user accounts; access control is the file's permissions")

    async def grants(self, user: str | None = None, obj: str | None = None) -> list[dict[str, Any]]:
        raise GuidanceError("SQLite has no grants; access control is the file's permissions")
