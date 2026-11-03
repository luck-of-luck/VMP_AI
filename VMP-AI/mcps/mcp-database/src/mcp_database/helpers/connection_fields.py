from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any, Literal

from ..errors import ConfigError

AccessMode = Literal["read_only", "read_write", "monitor"]

ACCESS_MODES: tuple[AccessMode, ...] = ("read_only", "read_write", "monitor")
WRITE_OPS = frozenset({"insert", "update", "delete", "ddl"})
DB_TYPES = ("postgres", "mysql", "mariadb", "sqlite", "mongodb", "redis")

_SCHEME_TYPES = {
    "postgres": "postgres",
    "postgresql": "postgres",
    "mysql": "mysql",
    "mariadb": "mariadb",
    "sqlite": "sqlite",
    "mongodb": "mongodb",
    "mongodb+srv": "mongodb",
    "redis": "redis",
    "rediss": "redis",
}


def infer_type(uri: str, name: str) -> str:
    """Map the URI scheme to a supported database type."""
    scheme = uri.partition("://")[0].lower()
    db_type = _SCHEME_TYPES.get(scheme)
    if db_type is None:
        raise ConfigError(
            f"Connection '{name}': cannot infer database type from URI scheme '{scheme}' "
            f"(expected one of: {', '.join(sorted(_SCHEME_TYPES))})"
        )
    return db_type


def require_positive_int(name: str, key: str, value: Any) -> int:
    """Accept only a positive int (bools rejected), for timeouts and row caps."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ConfigError(f"Connection '{name}': '{key}' must be a positive integer, got {value!r}")
    return value


def optional_positive_int(name: str, key: str, value: Any) -> int | None:
    """A positive int or None when the key is absent — for opt-in thresholds like max_plan_cost."""
    if value is None:
        return None
    return require_positive_int(name, key, value)


def parse_uri(name: str, raw: dict[str, Any]) -> str:
    """The mandatory connection URI, as a non-empty string."""
    uri = raw.get("uri")
    if not uri or not isinstance(uri, str):
        raise ConfigError(f"Connection '{name}': 'uri' is required")
    return uri


def parse_type(name: str, raw: dict[str, Any], uri: str) -> str:
    """The database type: explicit 'type' wins, otherwise inferred from the URI scheme."""
    db_type = raw.get("type") or infer_type(uri, name)
    if db_type not in DB_TYPES:
        raise ConfigError(f"Connection '{name}': unknown type '{db_type}' (expected one of: {', '.join(DB_TYPES)})")
    return db_type


def parse_mode(name: str, raw: dict[str, Any]) -> AccessMode:
    """The access_mode field, defaulting to read_only."""
    mode = raw.get("access_mode", "read_only")
    if mode not in ACCESS_MODES:
        raise ConfigError(
            f"Connection '{name}': invalid access_mode '{mode}' (expected one of: {', '.join(ACCESS_MODES)})"
        )
    return mode


def parse_write_ops(name: str, raw: dict[str, Any]) -> frozenset[str]:
    """The allowed write kinds; absent means all of insert/update/delete/ddl."""
    raw_ops = raw.get("write_ops")
    if raw_ops is None:
        return WRITE_OPS
    if not isinstance(raw_ops, list) or not set(raw_ops) <= WRITE_OPS:
        raise ConfigError(f"Connection '{name}': write_ops must be a subset of {sorted(WRITE_OPS)}")
    return frozenset(raw_ops)


def parse_database_modes(name: str, raw: dict[str, Any]) -> dict[str, AccessMode]:
    """Per-database access-mode overrides, each validated against the known modes."""
    raw_modes = raw.get("database_modes")
    if raw_modes is None:
        return {}
    if not isinstance(raw_modes, dict):
        raise ConfigError(f"Connection '{name}': database_modes must be an object")
    for db, db_mode in raw_modes.items():
        if db_mode not in ACCESS_MODES:
            raise ConfigError(f"Connection '{name}': invalid mode '{db_mode}' for database '{db}'")
    return dict(raw_modes)


def parse_redact_fields(name: str, raw: dict[str, Any]) -> tuple[str, ...]:
    """The fields to mask in results, lowercased (the '*' mask-everything marker kept as-is)."""
    raw_redact = raw.get("redact_fields")
    if raw_redact is None:
        return ()
    if not isinstance(raw_redact, list) or not all(isinstance(f, str) and f for f in raw_redact):
        raise ConfigError(f"Connection '{name}': redact_fields must be a list of non-empty strings")
    return tuple(f if f == "*" else f.lower() for f in raw_redact)


def parse_redact_patterns(name: str, raw: dict[str, Any]) -> tuple[str, ...]:
    """Regexes matched (case-insensitive) against field names, masking whatever redact_fields missed by name."""
    raw_patterns = raw.get("redact_patterns")
    if raw_patterns is None:
        return ()
    if not isinstance(raw_patterns, list) or not all(isinstance(p, str) and p for p in raw_patterns):
        raise ConfigError(f"Connection '{name}': redact_patterns must be a list of non-empty regex strings")
    for pattern in raw_patterns:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ConfigError(f"Connection '{name}': invalid redact_patterns regex {pattern!r} ({exc})") from None
    return tuple(raw_patterns)


def parse_password_env(name: str, raw: dict[str, Any]) -> str | None:
    """The name of the env var holding the password, when the URI should not carry it."""
    password_env = raw.get("password_env")
    if password_env is not None and (not isinstance(password_env, str) or not password_env):
        raise ConfigError(f"Connection '{name}': password_env must be a non-empty string")
    return password_env


def engine_from_env(env: Mapping[str, str], uri: str) -> str | None:
    """The optional ENGINE_TYPE env var, cross-checked against the URI scheme when one is present."""
    engine = env.get("ENGINE_TYPE")
    if not engine:
        return None
    if engine not in DB_TYPES:
        raise ConfigError(f"ENGINE_TYPE must be one of: {', '.join(DB_TYPES)}, got '{engine}'")
    if "://" in uri and infer_type(uri, env.get("NAME") or engine) != engine:
        scheme = uri.partition("://")[0].lower()
        raise ConfigError(f"URI scheme '{scheme}' does not match ENGINE_TYPE '{engine}'")
    return engine


def parse_int_env(var: str, value: str) -> int:
    """Parse an integer env var, naming the variable in the error."""
    try:
        return int(value)
    except ValueError:
        raise ConfigError(f"{var} must be an integer, got {value!r}") from None


def parse_json_env(var: str, value: str) -> Any:
    """Parse a JSON env var, naming the variable in the error."""
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{var}: invalid JSON ({exc})") from None


_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off", ""}


def parse_bool_env(var: str, value: str) -> bool:
    """Parse a boolean env var (true/false/1/0/yes/no/on/off), naming the variable in the error."""
    lowered = value.strip().lower()
    if lowered in _TRUE:
        return True
    if lowered in _FALSE:
        return False
    raise ConfigError(f"{var} must be a boolean (true/false), got {value!r}")


def parse_bool(name: str, key: str, value: Any) -> bool:
    """Validate an already-typed boolean config value (from a JSON config object)."""
    if not isinstance(value, bool):
        raise ConfigError(f"Connection '{name}': '{key}' must be a boolean, got {value!r}")
    return value
