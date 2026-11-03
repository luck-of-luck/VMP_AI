from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from .errors import QueryValidationError

MAX_RESPONSE_BYTES = 1024 * 1024
HARD_ROW_CAP = 5000
MASK = "***"

_URI_PASSWORD = re.compile(r"://([^:/@\s]+):([^@\s]+)@")


def redact_uri_passwords(text: str) -> str:
    """Replace the password of any user:pass@ URI in the text with *** (fixed linear regex, ReDoS-safe)."""
    return _URI_PASSWORD.sub(r"://\1:***@", text)


# Driver error messages that echo row/column values back to the caller (and into the audit log).
# Each pattern keeps the structural part and replaces the leaked value with a placeholder.
_ERROR_VALUE_PATTERNS = (
    (re.compile(r"(Key \([^)]*\)=)\([^)]*\)"), r"\1(?)"),  # pg unique/fk violation
    (re.compile(r"(Failing row contains )\(.*"), r"\1(?)"),  # pg not-null/check violation
    (re.compile(r'(invalid input syntax for type \w+: )"[^"]*"'), r'\1"?"'),  # pg type cast
    (re.compile(r"(Duplicate entry )'[^']*'"), r"\1'?'"),  # mysql unique violation
    (re.compile(r"(Incorrect \w+ value: )'[^']*'"), r"\1'?'"),  # mysql bad value cast
)


def sanitize_error(text: str) -> str:
    """Strip secrets and echoed data values from a driver error before it reaches the agent or the audit log."""
    text = redact_uri_passwords(text)
    for pattern, repl in _ERROR_VALUE_PATTERNS:
        text = pattern.sub(repl, text)
    return text


def json_default(value: Any) -> Any:
    """json.dumps fallback: isoformat dates, float Decimals, str UUIDs, '<N bytes>' blobs, str everything else."""
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes | bytearray | memoryview):
        return f"<{len(bytes(value))} bytes>"
    return str(value)


def type_placeholder(value: Any) -> str:
    """The '<type>' marker shown instead of a value when redact_fields is ['*'] (bool checked before int)."""
    if value is None:
        return "<null>"
    if isinstance(value, bool):
        return "<bool>"
    if isinstance(value, int):
        return "<int>"
    if isinstance(value, float | Decimal):
        return "<float>"
    if isinstance(value, datetime | date | time):
        return "<datetime>"
    if isinstance(value, str):
        return "<string>"
    if isinstance(value, bytes | bytearray | memoryview):
        return "<bytes>"
    return f"<{type(value).__name__}>"


def to_jsonable(value: Any) -> Any:
    """Recursively convert a value to JSON-native types (str/int/float/bool/None/list/dict).

    Driver-native values like MongoDB ObjectId, datetime, Decimal, UUID and bytes are not serializable
    by the MCP layer; this normalizes them (via json_default) before a tool result is returned.
    """
    if isinstance(value, dict):
        return {key: to_jsonable(nested) for key, nested in value.items()}
    if isinstance(value, list | tuple):
        return [to_jsonable(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return json_default(value)


def _mask_all(value: Any) -> Any:
    """Replace every leaf value with its type placeholder, preserving the dict/list structure."""
    if isinstance(value, dict):
        return {key: _mask_all(nested) for key, nested in value.items()}
    if isinstance(value, list | tuple):
        return [_mask_all(item) for item in value]
    return type_placeholder(value)


def _key_matches(key: Any, fields: set[str], patterns: list[re.Pattern[str]]) -> bool:
    """Whether a field name is redacted, by exact (lowercased) name or by any regex pattern."""
    if not isinstance(key, str):
        return False
    return key.lower() in fields or any(p.search(key) for p in patterns)


def _mask_fields(value: Any, fields: set[str], patterns: list[re.Pattern[str]]) -> Any:
    if isinstance(value, dict):
        return {
            key: MASK if _key_matches(key, fields, patterns) else _mask_fields(nested, fields, patterns)
            for key, nested in value.items()
        }
    if isinstance(value, list | tuple):
        return [_mask_fields(item, fields, patterns) for item in value]
    return value


def _compile_patterns(redact_patterns: Sequence[str]) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in redact_patterns]


def mask_rows(
    rows: list[dict[str, Any]], redact_fields: Sequence[str], redact_patterns: Sequence[str] = ()
) -> list[dict[str, Any]]:
    """Mask result fields: '*' masks everything, names and regex patterns mask matching fields at any depth."""
    if not redact_fields and not redact_patterns:
        return rows
    if "*" in redact_fields:
        return [_mask_all(row) for row in rows]
    fields = {f.lower() for f in redact_fields if f != "*"}
    patterns = _compile_patterns(redact_patterns)
    return [_mask_fields(row, fields, patterns) for row in rows]


_STATS_VALUE_KEYS = ("most_common_vals", "histogram")


def mask_column_stats(
    rows: list[dict[str, Any]], redact_fields: Sequence[str], redact_patterns: Sequence[str] = ()
) -> list[dict[str, Any]]:
    """Mask the data-bearing parts of planner statistics — MCV lists and histograms hold real values."""
    if not redact_fields and not redact_patterns:
        return rows
    mask_all = "*" in redact_fields
    fields = {f.lower() for f in redact_fields if f != "*"}
    patterns = _compile_patterns(redact_patterns)
    masked = []
    for row in rows:
        if mask_all or _key_matches(row.get("column"), fields, patterns):
            row = {k: MASK if k in _STATS_VALUE_KEYS and v is not None else v for k, v in row.items()}
        masked.append(row)
    return masked


def effective_row_limit(requested: int | None, default: int, cap: int = HARD_ROW_CAP) -> int:
    """Validate a caller-supplied row limit and cap it (and the default) at cap (default HARD_ROW_CAP)."""
    if requested is None:
        return min(default, cap)
    if isinstance(requested, bool) or not isinstance(requested, int) or requested <= 0:
        raise QueryValidationError(f"row_limit must be a positive integer, got {requested!r}")
    return min(requested, cap)


def _fit_byte_budget(
    rows: list[dict[str, Any]], max_bytes: int = MAX_RESPONSE_BYTES
) -> tuple[list[dict[str, Any]], bool]:
    """Keep rows until the response byte budget runs out (the first row always stays); returns (kept, truncated)."""
    kept: list[dict[str, Any]] = []
    budget = max_bytes
    for row in rows:
        encoded = len(json.dumps(row, default=json_default, ensure_ascii=False).encode()) + 2
        if kept and encoded > budget:
            return kept, True
        budget -= encoded
        kept.append(row)
    return kept, False


def _to_columnar(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Fold row dicts into `{columns, rows}` so repeated keys are stated once (token-efficient).

    Columns are the first-seen union across rows; a row missing a column gets null in that slot.
    """
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return {"columns": columns, "rows": [[row.get(c) for c in columns] for row in rows]}


def build_result(
    rows: list[dict[str, Any]],
    *,
    row_limit: int,
    redact_fields: Sequence[str] = (),
    redact_patterns: Sequence[str] = (),
    execution_ms: float | None = None,
    compact: bool = False,
    max_bytes: int = MAX_RESPONSE_BYTES,
    cap: int = HARD_ROW_CAP,
) -> dict[str, Any]:
    """Shape adapter rows into the tool result: row cap, masking, byte cap, truncation note, timing.

    compact emits `{columns, rows: [[...]]}` instead of `rows: [{...}]`, stating each key once.
    """
    limit = min(max(row_limit, 1), cap)
    truncated_by_rows = len(rows) > limit
    kept, truncated_by_bytes = _fit_byte_budget(mask_rows(rows[:limit], redact_fields, redact_patterns), max_bytes)

    result: dict[str, Any] = _to_columnar(kept) if compact else {"rows": kept}
    result["row_count"] = len(kept)
    result["truncated"] = truncated_by_rows or truncated_by_bytes
    if result["truncated"]:
        result["note"] = (
            "Result truncated. Narrow the query, raise row_limit (cap 5000), "
            "or use db_read_export to write the full result to a file."
        )
    if execution_ms is not None:
        result["execution_ms"] = round(execution_ms, 1)
    return result
