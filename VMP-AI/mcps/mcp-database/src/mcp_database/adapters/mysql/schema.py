from __future__ import annotations

import re
from typing import Any

from pymysql.err import MySQLError

from ...errors import GuidanceError, QueryValidationError
from ._common import _qualified

_SYSTEM_SCHEMAS = ("mysql", "information_schema", "performance_schema", "sys")

_ACCOUNT_PART = re.compile(r"^[A-Za-z0-9_.%:-]+$")


def _account_part(value: str) -> str:
    """Allowlist one half of a 'user'@'host' identity before it is interpolated into SHOW GRANTS."""
    if not _ACCOUNT_PART.match(value):
        raise QueryValidationError(f"Invalid MySQL account identifier {value!r}")
    return value


class MySchemaMixin:
    """MySQLAdapter schema operations."""

    async def list_databases(self) -> list[dict[str, Any]]:
        placeholders = ", ".join(["%s"] * len(_SYSTEM_SCHEMAS))
        return await self._fetch(
            f"SELECT schema_name AS `database` FROM information_schema.schemata "
            f"WHERE schema_name NOT IN ({placeholders}) ORDER BY schema_name",
            _SYSTEM_SCHEMAS,
        )

    async def list_objects(self, database: str, object_type: str | None = None) -> list[dict[str, Any]]:
        if object_type not in (None, "table", "view", "index"):
            raise QueryValidationError(f"Unknown object_type '{object_type}' (expected: table, view, index)")
        results: list[dict[str, Any]] = []
        if object_type in (None, "table", "view"):
            type_filter = {"table": ("BASE TABLE",), "view": ("VIEW",)}.get(object_type, ("BASE TABLE", "VIEW"))
            placeholders = ", ".join(["%s"] * len(type_filter))
            results += await self._fetch(
                f"""
                SELECT table_name AS name,
                       IF(table_type = 'VIEW', 'view', 'table') AS type,
                       COALESCE(data_length + index_length, 0) AS total_bytes,
                       COALESCE(table_rows, 0) AS approx_rows
                FROM information_schema.tables
                WHERE table_schema = %s AND table_type IN ({placeholders})
                ORDER BY data_length + index_length DESC, table_name
                """,
                (database, *type_filter),
            )
        if object_type in (None, "index"):
            results += await self._fetch(
                """
                SELECT DISTINCT index_name AS name, 'index' AS type, table_name AS `table`
                FROM information_schema.statistics
                WHERE table_schema = %s AND index_name <> 'PRIMARY'
                ORDER BY index_name
                """,
                (database,),
            )
        return results

    async def describe_object(self, database: str, obj: str, *, sample: bool = True) -> dict[str, Any]:
        columns = await self._fetch(
            """
            SELECT column_name AS name, column_type AS type, is_nullable = 'YES' AS nullable,
                   column_default AS `default`, column_key AS `key`, extra
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (database, obj),
        )
        indexes = await self._fetch(
            """
            SELECT index_name AS name, GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns,
                   MIN(non_unique) = 0 AS `unique`
            FROM information_schema.statistics
            WHERE table_schema = %s AND table_name = %s
            GROUP BY index_name
            """,
            (database, obj),
        )
        constraints = await self._fetch(
            """
            SELECT constraint_name AS name, constraint_type AS type
            FROM information_schema.table_constraints
            WHERE table_schema = %s AND table_name = %s
            """,
            (database, obj),
        )
        size = await self._fetch(
            """
            SELECT COALESCE(data_length + index_length, 0) AS total_bytes
            FROM information_schema.tables WHERE table_schema = %s AND table_name = %s
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
        rows = await self._fetch(f"SHOW CREATE TABLE {_qualified(database, obj)}")
        if not rows:
            raise QueryValidationError(f"Object '{database}.{obj}' not found")
        row = rows[0]
        return {"ddl": row.get("Create Table") or row.get("Create View") or ""}

    async def relationships(self, database: str, obj: str | None = None) -> dict[str, Any]:
        query = """
            SELECT constraint_name AS `constraint`, table_name AS from_table,
                   referenced_table_name AS to_table,
                   GROUP_CONCAT(column_name ORDER BY ordinal_position) AS columns
            FROM information_schema.key_column_usage
            WHERE table_schema = %s AND referenced_table_name IS NOT NULL
        """
        params: list[Any] = [database]
        if obj:
            query += " AND (table_name = %s OR referenced_table_name = %s)"
            params += [obj, obj]
        query += " GROUP BY constraint_name, table_name, referenced_table_name ORDER BY from_table"
        return {"relationships": await self._fetch(query, params)}

    async def users(self, user: str | None = None) -> list[dict[str, Any]]:
        query = self._USERS_SELECT
        params: list[Any] = []
        if user:
            query += " WHERE user = %s"
            params.append(user)
        try:
            return await self._fetch(query + " ORDER BY user, host", params)
        except MySQLError as exc:
            raise GuidanceError(f"Cannot read mysql.user ({exc}). This requires SELECT on the mysql schema.") from None

    async def grants(self, user: str | None = None, obj: str | None = None) -> list[dict[str, Any]]:
        if user:
            if "@" in user:
                name, _, host = user.partition("@")
                accounts = [(name, host)]
            else:
                rows = await self.users(user)
                accounts = [(r["user"], r["host"]) for r in rows]
                if not accounts:
                    raise QueryValidationError(f"User '{user}' not found")
            grants: list[dict[str, Any]] = []
            for name, host in accounts:
                account = f"'{_account_part(name)}'@'{_account_part(host)}'"
                for row in await self._fetch(f"SHOW GRANTS FOR {account}"):
                    grants += [{"user": f"{name}@{host}", "grant": value} for value in row.values()]
        else:
            grants = [
                {"user": "current", "grant": value}
                for row in await self._fetch("SHOW GRANTS")
                for value in row.values()
            ]
        if obj:
            grants = [g for g in grants if obj in g["grant"]]
        return grants

    async def search_indexes(self, database: str | None = None, obj: str | None = None) -> dict[str, Any]:
        rows = await self._fetch(
            """
            SELECT table_schema AS `database`, table_name AS `table`, index_name AS `index`,
                   GROUP_CONCAT(column_name ORDER BY seq_in_index) AS columns
            FROM information_schema.statistics
            WHERE index_type = 'FULLTEXT'
              AND (%s IS NULL OR table_schema = %s) AND (%s IS NULL OR table_name = %s)
            GROUP BY table_schema, table_name, index_name
            ORDER BY 1, 2, 3
            """,
            (database, database, obj, obj),
        )
        return {"indexes": [{**row, "type": "fulltext"} for row in rows]}
