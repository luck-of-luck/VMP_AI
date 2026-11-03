from __future__ import annotations

from typing import Any

from ...errors import QueryValidationError
from ._common import _VECTOR_OPCLASSES

_OBJECT_KINDS = {
    "table": ("r", "p"),
    "view": ("v", "m"),
    "index": ("i",),
    "sequence": ("S",),
}

_KIND_NAMES = {"r": "table", "p": "table", "v": "view", "m": "materialized view", "i": "index", "S": "sequence"}


class PgSchemaMixin:
    """PostgresAdapter schema operations."""

    async def list_databases(self) -> list[dict[str, Any]]:
        return await self._fetch(
            """
            SELECT nspname AS schema, pg_get_userbyid(nspowner) AS owner
            FROM pg_namespace
            WHERE nspname NOT IN ('information_schema') AND nspname NOT LIKE 'pg\\_%'
            ORDER BY nspname
            """
        )

    async def list_objects(self, database: str, object_type: str | None = None) -> list[dict[str, Any]]:
        kinds = _OBJECT_KINDS.get(object_type, tuple(_KIND_NAMES)) if object_type else tuple(_KIND_NAMES)
        if object_type and object_type not in _OBJECT_KINDS:
            raise QueryValidationError(f"Unknown object_type '{object_type}' (expected: {', '.join(_OBJECT_KINDS)})")
        rows = await self._fetch(
            """
            SELECT c.relname AS name, c.relkind::text AS kind,
                   pg_total_relation_size(c.oid) AS total_bytes,
                   greatest(c.reltuples, 0)::bigint AS approx_rows
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relkind = ANY(%s)
            ORDER BY pg_total_relation_size(c.oid) DESC, c.relname
            """,
            (database, list(kinds)),
        )
        return [{**row, "type": _KIND_NAMES[row.pop("kind")]} for row in rows]

    async def describe_object(self, database: str, obj: str, *, sample: bool = True) -> dict[str, Any]:
        columns = await self._fetch(
            """
            SELECT column_name AS name, data_type AS type, is_nullable = 'YES' AS nullable, column_default AS default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (database, obj),
        )
        constraints = await self._fetch(
            """
            SELECT con.conname AS name, pg_get_constraintdef(con.oid) AS definition
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (database, obj),
        )
        indexes = await self._fetch(
            "SELECT indexname AS name, indexdef AS definition FROM pg_indexes WHERE schemaname = %s AND tablename = %s",
            (database, obj),
        )
        size = await self._fetch(
            """
            SELECT pg_total_relation_size(c.oid) AS total_bytes
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
            """,
            (database, obj),
        )
        if not columns and not size:
            raise QueryValidationError(f"Object '{database}.{obj}' not found")
        return {
            "columns": columns,
            "constraints": constraints,
            "indexes": indexes,
            "total_bytes": size[0]["total_bytes"] if size else None,
        }

    async def get_ddl(self, database: str, obj: str) -> dict[str, Any]:
        view = (
            await self._fetch(
                "SELECT pg_get_viewdef(%s::regclass, true) AS definition",
                (f'"{database}"."{obj}"',),
            )
            if await self._is_view(database, obj)
            else []
        )
        if view:
            return {"ddl": f'CREATE OR REPLACE VIEW "{database}"."{obj}" AS\n{view[0]["definition"]}'}

        described = await self.describe_object(database, obj, sample=False)
        if not described["columns"]:
            raise QueryValidationError(f"Object '{database}.{obj}' not found or has no columns")
        column_lines = []
        for col in described["columns"]:
            line = f'    "{col["name"]}" {col["type"]}'
            if col["default"]:
                line += f" DEFAULT {col['default']}"
            if not col["nullable"]:
                line += " NOT NULL"
            column_lines.append(line)
        statements = [f'CREATE TABLE "{database}"."{obj}" (\n' + ",\n".join(column_lines) + "\n);"]
        statements += [
            f'ALTER TABLE "{database}"."{obj}" ADD CONSTRAINT "{c["name"]}" {c["definition"]};'
            for c in described["constraints"]
        ]
        statements += [f"{i['definition']};" for i in described["indexes"]]
        return {"ddl": "\n".join(statements)}

    async def _is_view(self, database: str, obj: str) -> bool:
        """Whether the object is a (materialized) view, deciding the get_ddl strategy."""
        rows = await self._fetch(
            """
            SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s AND c.relkind IN ('v', 'm')
            """,
            (database, obj),
        )
        return bool(rows)

    async def relationships(self, database: str, obj: str | None = None) -> dict[str, Any]:
        query = """
            SELECT con.conname AS constraint, src.relname AS from_table, tgt.relname AS to_table,
                   pg_get_constraintdef(con.oid) AS definition
            FROM pg_constraint con
            JOIN pg_class src ON src.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = src.relnamespace
            JOIN pg_class tgt ON tgt.oid = con.confrelid
            WHERE con.contype = 'f' AND n.nspname = %s
        """
        params: list[Any] = [database]
        if obj:
            query += " AND (src.relname = %s OR tgt.relname = %s)"
            params += [obj, obj]
        return {"relationships": await self._fetch(query + " ORDER BY 2", params)}

    async def users(self, user: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT r.rolname AS role, r.rolsuper AS superuser, r.rolcanlogin AS can_login,
                   r.rolcreaterole AS can_create_role, r.rolcreatedb AS can_create_db,
                   r.rolvaliduntil::text AS valid_until,
                   ARRAY(SELECT g.rolname FROM pg_auth_members m
                         JOIN pg_roles g ON g.oid = m.roleid WHERE m.member = r.oid) AS member_of
            FROM pg_roles r
        """
        params: list[Any] = []
        if user:
            query += " WHERE r.rolname = %s"
            params.append(user)
        return await self._fetch(query + " ORDER BY r.rolname", params)

    async def grants(self, user: str | None = None, obj: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT grantee, table_schema AS schema, table_name AS "table", privilege_type AS privilege
            FROM information_schema.role_table_grants
            WHERE grantee NOT IN ('PUBLIC')
        """
        params: list[Any] = []
        if user:
            query += " AND grantee = %s"
            params.append(user)
        if obj:
            query += " AND table_name = %s"
            params.append(obj)
        return await self._fetch(query + " ORDER BY grantee, table_schema, table_name", params)

    async def search_indexes(self, database: str | None = None, obj: str | None = None) -> dict[str, Any]:
        params = (database, database, obj, obj)
        vector_rows = await self._fetch(
            self._SEARCH_INDEXES_SQL + " AND am.amname IN ('hnsw', 'ivfflat') ORDER BY 1, 2, 3", params
        )
        fulltext_rows = await self._fetch(
            self._SEARCH_INDEXES_SQL
            + " AND am.amname IN ('gin', 'gist') AND pg_get_indexdef(i.indexrelid) ILIKE '%%tsvector%%'"
            + " ORDER BY 1, 2, 3",
            params,
        )
        for row in vector_rows:
            row["type"] = "vector"
            row["metric"] = next(
                (metric for metric, opclass in _VECTOR_OPCLASSES.items() if opclass in (row["definition"] or "")),
                None,
            )
        for row in fulltext_rows:
            row["type"] = "fulltext"
        return {"indexes": vector_rows + fulltext_rows}
