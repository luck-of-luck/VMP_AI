from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from .config import ConnectionConfig
from .errors import AccessDeniedError, QueryValidationError
from .helpers import mongo_query, redis_query, sql_ast


class ToolClass(StrEnum):
    """Risk class encoded in every tool name prefix (db_schema_, db_read_, ...); drives the mode matrix."""

    SCHEMA = "schema"
    READ = "read"
    PERF = "perf"
    WRITE = "write"
    ADMIN = "admin"


MODE_ALLOWS: dict[str, frozenset[ToolClass]] = {
    "read_write": frozenset(ToolClass),
    "read_only": frozenset({ToolClass.SCHEMA, ToolClass.READ, ToolClass.PERF}),
    "monitor": frozenset({ToolClass.SCHEMA, ToolClass.PERF}),
}

_DIALECTS = {"postgres": "postgres", "mysql": "mysql", "mariadb": "mysql", "sqlite": "sqlite"}

MONGO_READ_OPS = mongo_query.READ_OPS
MONGO_WRITE_OPS = mongo_query.WRITE_OPS


def ensure_tool_allowed(cfg: ConnectionConfig, tool_class: ToolClass, database: str | None = None) -> None:
    """Reject the call if the effective access mode does not allow this tool class."""
    mode = cfg.mode_for(database)
    if tool_class in MODE_ALLOWS[mode]:
        return
    scope = f" for database '{database}'" if database and database in cfg.database_modes else ""
    allowed = ", ".join(sorted(f"db_{c.value}_*" for c in MODE_ALLOWS[mode]))
    raise AccessDeniedError(
        f"Connection '{cfg.name}' is '{mode}'{scope}: db_{tool_class.value}_* tools are not allowed "
        f"(allowed here: {allowed})"
    )


def ensure_databases_allowed(cfg: ConnectionConfig, tool_class: ToolClass, databases: set[str]) -> None:
    """Check every database the query touches; an unqualified query is checked against the most restrictive mode."""
    if not databases:
        ensure_tool_allowed(cfg, tool_class, None)
        return
    for database in databases:
        ensure_tool_allowed(cfg, tool_class, database)


def ensure_write_op_allowed(cfg: ConnectionConfig, op: str) -> None:
    """Reject the write if its kind (insert/update/delete/ddl) is not in the connection's write_ops."""
    if op not in cfg.write_ops:
        raise AccessDeniedError(
            f"Connection '{cfg.name}' does not allow '{op}' operations (write_ops: {sorted(cfg.write_ops)})"
        )


def parse_sql(query: str, conn_type: str) -> exp.Expression:
    """Parse exactly one SQL statement with sqlglot, fail-closed: anything unparseable is rejected."""
    if not isinstance(query, str) or not query.strip():
        raise QueryValidationError("Query must be a non-empty SQL string")
    if "/*!" in query:
        # MySQL executable comments (/*! ... */, /*!NNNNN ... */) run their contents as SQL, but sqlglot
        # parses them as inert comments — a write could hide inside one and pass the read/write_ops checks.
        # No legitimate agent query needs the marker; reject it fail-closed on every engine.
        raise QueryValidationError(
            "SQL contains a MySQL executable comment marker (/*!) and is rejected: its contents would run "
            "on MySQL but are invisible to validation. Remove the /*! marker."
        )
    try:
        statements = [s for s in sqlglot.parse(query, read=_DIALECTS[conn_type]) if s is not None]
    except SqlglotError as exc:
        message = sql_ast.describe_parse_error(exc)
        if conn_type == "mysql" and "%s" in query:
            message += " (In MySQL, '%' is parsed as the modulo operator, so a bare '%s' is invalid syntax here.)"
        raise QueryValidationError(message) from None
    if len(statements) != 1:
        raise QueryValidationError(f"Exactly one statement is allowed, got {len(statements)}")
    return statements[0]


def validate_sql_read(query: str, conn_type: str) -> None:
    """Prove a query is a pure read: read root, no embedded writes, no forbidden functions."""
    tree = parse_sql(query, conn_type)
    sql_ast.ensure_read_root(tree)
    sql_ast.ensure_no_embedded_writes(tree)
    sql_ast.ensure_no_forbidden_functions(tree)


def classify_sql_write(query: str, conn_type: str) -> str:
    """Classify a write statement as insert/update/delete/ddl (reads are rejected)."""
    return sql_ast.classify_write_tree(parse_sql(query, conn_type))


def sql_databases(query: str, conn_type: str) -> set[str]:
    """The database qualifiers a query references (for database_modes enforcement)."""
    return sql_ast.database_qualifiers(parse_sql(query, conn_type))


@dataclass(frozen=True, slots=True)
class SqlWrite:
    """Everything the write path needs from one parse of the statement."""

    op: str
    databases: set[str]
    unbounded: bool  # UPDATE/DELETE with no WHERE clause
    audit_shape: str  # query rendered with literals replaced by placeholders


def analyze_sql_write(query: str, conn_type: str) -> SqlWrite:
    """Parse a write query once and derive everything the write path needs from the single tree."""
    tree = parse_sql(query, conn_type)
    return SqlWrite(
        op=sql_ast.classify_write_tree(tree),
        databases=sql_ast.database_qualifiers(tree),
        unbounded=sql_ast.is_unbounded_mutation(tree),
        audit_shape=sql_ast.normalize_literals(tree),
    )


def apply_read_limit(query: str, conn_type: str, limit: int) -> str:
    """Inject a LIMIT into a SELECT/UNION that has none, bounding the work at the database."""
    tree, injected = sql_ast.with_row_limit(parse_sql(query, conn_type), limit)
    return tree.sql(dialect=_DIALECTS[conn_type]) if injected else query


def mongo_audit_shape(parsed: dict[str, Any]) -> dict[str, Any]:
    """The MongoDB write query with data values replaced by '?', for audit entries."""
    return mongo_query.audit_shape(parsed)


def read_audit_shape(conn_type: str, query: Any) -> Any:
    """Privacy-preserving shape of an already-validated read query, for audit entries."""
    if conn_type == "mongodb":
        return mongo_query.audit_shape(query)
    if conn_type == "redis":
        return redis_query.audit_shape(query)
    return sql_ast.normalize_literals(parse_sql(query, conn_type))


def parse_mongo_query(query: Any) -> dict[str, Any]:
    """Validate the common MongoDB query envelope: dict with known operation, collection, optional database."""
    if not isinstance(query, dict):
        raise QueryValidationError(
            'MongoDB queries must be JSON objects like {"collection": ..., "operation": "find", ...}'
        )
    mongo_query.ensure_known_operation(mongo_query.require_str_field(query, "operation"))
    mongo_query.require_str_field(query, "collection")
    mongo_query.ensure_optional_database(query)
    return query


def validate_mongo_read(query: Any) -> dict[str, Any]:
    """Accept only read operations, running the per-operation validator (pipeline stages, distinct key).

    Every read is also swept for write stages ($out/$merge) and server-side JS operators ($where/$function/
    $accumulator) wherever they appear — a find filter is not covered by the per-operation validators.
    """
    parsed = parse_mongo_query(query)
    operation = parsed["operation"]
    if operation not in MONGO_READ_OPS:
        raise QueryValidationError(f"Operation '{operation}' writes; use db_write_query instead")
    mongo_query.scan_for_forbidden_operators(parsed)
    if validator := mongo_query.READ_VALIDATORS.get(operation):
        validator(parsed)
    return parsed


def classify_mongo_write(query: Any) -> tuple[dict[str, Any], str]:
    """Validate a write operation and return (parsed query, write kind) for write_ops enforcement."""
    parsed = parse_mongo_query(query)
    operation = parsed["operation"]
    if operation in MONGO_READ_OPS:
        raise QueryValidationError(f"Operation '{operation}' is a read; use db_read_query instead")
    return parsed, MONGO_WRITE_OPS[operation]


def validate_redis_read(query: Any) -> dict[str, Any]:
    """Parse the Redis envelope and prove the command is on the read allowlist (banned ones never pass)."""
    parsed = redis_query.parse_redis_query(query)
    if parsed["command"] in redis_query.WRITE_COMMANDS:
        raise QueryValidationError(f"Command '{parsed['command']}' writes data; use db_write_query instead")
    return parsed


def classify_redis_write(query: Any) -> tuple[dict[str, Any], str]:
    """Validate a Redis write command and return (parsed query, write kind) for write_ops enforcement."""
    parsed = redis_query.parse_redis_query(query)
    if parsed["command"] in redis_query.READ_COMMANDS:
        raise QueryValidationError(f"Command '{parsed['command']}' is a read; use db_read_query instead")
    return parsed, redis_query.WRITE_COMMANDS[parsed["command"]]


redis_audit_shape = redis_query.audit_shape


def ensure_bounded_sql_write(op: str, unbounded: bool) -> None:
    """Reject an UPDATE/DELETE with no WHERE unless the caller declared intent (see write_context)."""
    if unbounded:
        raise QueryValidationError(
            f"Unbounded {op.upper()} (no WHERE clause) would affect every row. Add a WHERE clause, "
            "set expected_max_rows to confirm the intended size, or pass dry_run=true to preview the impact."
        )


def ensure_bounded_mongo_write(parsed: dict[str, Any]) -> None:
    """Reject an updateMany/deleteMany with an empty filter unless the caller declared intent."""
    if mongo_query.is_unbounded_write(parsed):
        raise QueryValidationError(
            f"Unbounded {parsed['operation']} (empty filter) would affect every document. Add a filter, "
            "set expected_max_rows to confirm the intended size, or pass dry_run=true to preview the impact."
        )
