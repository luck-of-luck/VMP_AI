from __future__ import annotations

from typing import Any

from ..errors import QueryValidationError

READ_OPS = frozenset({"find", "aggregate", "countDocuments", "estimatedDocumentCount", "distinct", "listIndexes"})
WRITE_OPS: dict[str, str] = {
    "insertOne": "insert",
    "insertMany": "insert",
    "updateOne": "update",
    "updateMany": "update",
    "replaceOne": "update",
    "deleteOne": "delete",
    "deleteMany": "delete",
    "createIndex": "ddl",
    "dropIndex": "ddl",
    "createCollection": "ddl",
    "dropCollection": "ddl",
    "renameCollection": "ddl",
}
FORBIDDEN_STAGES = frozenset({"$out", "$merge"})
# Operators that run server-side JavaScript: an injection/DoS surface, and arbitrary code the
# read allowlist should never permit. $expr itself is fine (field comparison); only the JS ones are barred.
JS_OPERATORS = frozenset({"$where", "$function", "$accumulator"})


def require_str_field(query: dict[str, Any], field: str) -> str:
    """The named field as a non-empty string, or a clear validation error."""
    value = query.get(field)
    if not isinstance(value, str) or not value:
        raise QueryValidationError(f"MongoDB query requires a string '{field}' field")
    return value


def ensure_known_operation(operation: str) -> None:
    """Reject any operation outside the read/write allowlists, listing what is supported."""
    if operation not in READ_OPS and operation not in WRITE_OPS:
        known = ", ".join(sorted(READ_OPS | set(WRITE_OPS)))
        raise QueryValidationError(f"Unknown MongoDB operation '{operation}' (supported: {known})")


def ensure_optional_database(query: dict[str, Any]) -> None:
    """'database', when present, must be a non-empty string."""
    database = query.get("database")
    if database is not None and (not isinstance(database, str) or not database):
        raise QueryValidationError("'database' must be a non-empty string when provided")


def scan_for_forbidden_operators(value: Any) -> None:
    """Walk a filter/pipeline recursively, rejecting write stages ($out/$merge) and server-side JS operators."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_STAGES:
                raise QueryValidationError(f"Pipeline stage '{key}' writes to a collection and is not allowed here")
            if key in JS_OPERATORS:
                raise QueryValidationError(
                    f"Operator '{key}' runs server-side JavaScript and is not allowed in a read; "
                    "express the condition with standard query/aggregation operators instead"
                )
            scan_for_forbidden_operators(nested)
    elif isinstance(value, list):
        for item in value:
            scan_for_forbidden_operators(item)


def validate_aggregate_read(parsed: dict[str, Any]) -> None:
    """aggregate needs a pipeline list, and that pipeline must not contain write stages or server-side JS."""
    pipeline = parsed.get("pipeline")
    if not isinstance(pipeline, list):
        raise QueryValidationError("aggregate requires a 'pipeline' list")
    scan_for_forbidden_operators(pipeline)


def validate_distinct_read(parsed: dict[str, Any]) -> None:
    """distinct needs a string 'key' to collect values for."""
    if not isinstance(parsed.get("key"), str):
        raise QueryValidationError("distinct requires a string 'key' field")


READ_VALIDATORS = {"aggregate": validate_aggregate_read, "distinct": validate_distinct_read}

UNBOUNDED_WRITE_OPS = frozenset({"updateMany", "deleteMany"})


def is_unbounded_write(parsed: dict[str, Any]) -> bool:
    """True for updateMany/deleteMany with a missing or empty filter (would touch every document)."""
    return parsed["operation"] in UNBOUNDED_WRITE_OPS and not parsed.get("filter")


_AUDIT_DATA_FIELDS = ("filter", "update", "replacement", "documents", "pipeline")


def _redact_values(value: Any) -> Any:
    """Replace every leaf value with '?', keeping dict keys and list shapes."""
    if isinstance(value, dict):
        return {key: _redact_values(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_redact_values(item) for item in value]
    return "?"


def audit_shape(parsed: dict[str, Any]) -> dict[str, Any]:
    """A copy of the write query with data-bearing values replaced by `?`, keeping the operation shape."""
    shape = dict(parsed)
    for field in _AUDIT_DATA_FIELDS:
        if field in shape:
            shape[field] = _redact_values(shape[field])
    return shape
