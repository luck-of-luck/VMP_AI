from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from .errors import ConfigError
from .formatter import HARD_ROW_CAP, MAX_RESPONSE_BYTES
from .helpers import connection_fields as fields
from .helpers.connection_fields import ACCESS_MODES, DB_TYPES, WRITE_OPS, AccessMode, infer_type
from .helpers.vector import MAX_CANDIDATES, MIN_CANDIDATES

DEFAULT_TIMEOUT_S = 30
DEFAULT_ROW_LIMIT = 500
DEFAULT_EXPORT_MAX_ROWS = 100_000
DEFAULT_POOL_SIZE = 2
DEFAULT_CONNECT_TIMEOUT_S = 5
DEFAULT_LOCK_TIMEOUT_MAX_S = 10

_RESTRICTIVENESS = {"monitor": 0, "read_only": 1, "read_write": 2}

__all__ = [
    "ACCESS_MODES",
    "DB_TYPES",
    "DEFAULT_EXPORT_MAX_ROWS",
    "DEFAULT_ROW_LIMIT",
    "DEFAULT_TIMEOUT_S",
    "WRITE_OPS",
    "AccessMode",
    "ConnectionConfig",
    "connection_from_env",
    "infer_type",
    "parse_connection",
]


@dataclass(frozen=True, slots=True)
class ConnectionConfig:
    """Immutable, validated configuration of one database connection (this instance serves exactly one)."""

    name: str
    type: str
    uri: str
    access_mode: AccessMode
    password_env: str | None = None
    query_timeout_s: int = DEFAULT_TIMEOUT_S
    row_limit: int = DEFAULT_ROW_LIMIT
    export_max_rows: int = DEFAULT_EXPORT_MAX_ROWS
    pool_size: int = DEFAULT_POOL_SIZE
    connect_timeout_s: int = DEFAULT_CONNECT_TIMEOUT_S
    lock_timeout_max_s: int = DEFAULT_LOCK_TIMEOUT_MAX_S
    max_response_bytes: int = MAX_RESPONSE_BYTES
    hard_row_cap: int = HARD_ROW_CAP
    vector_min_candidates: int = MIN_CANDIDATES
    vector_max_candidates: int = MAX_CANDIDATES
    write_ops: frozenset[str] = WRITE_OPS
    database_modes: dict[str, AccessMode] = field(default_factory=dict)
    redact_fields: tuple[str, ...] = ()
    redact_patterns: tuple[str, ...] = ()
    max_plan_cost: int | None = None
    compact: bool = False

    @property
    def redact_all(self) -> bool:
        """True when redact_fields is ['*'], meaning every value is replaced by a type placeholder."""
        return "*" in self.redact_fields

    def resolved_uri(self) -> str:
        """The URI with the password injected from the password_env environment variable, if configured."""
        if not self.password_env:
            return self.uri
        password = os.environ.get(self.password_env)
        if password is None:
            raise ConfigError(f"Connection '{self.name}': environment variable '{self.password_env}' is not set")
        scheme, sep, rest = self.uri.partition("://")
        authority = rest.split("/", 1)[0]
        if not sep or "@" not in authority:
            raise ConfigError(f"Connection '{self.name}': URI must include a username to use password_env")
        credentials, _, tail = rest.partition("@")
        username = credentials.split(":", 1)[0]
        return f"{scheme}://{username}:{quote(password, safe='')}@{tail}"

    def mode_for(self, database: str | None) -> AccessMode:
        """Effective access mode for a database: its database_modes entry, or the most restrictive when unknown."""
        if not self.database_modes:
            return self.access_mode
        if database is None:
            candidates = [self.access_mode, *self.database_modes.values()]
            return min(candidates, key=_RESTRICTIVENESS.__getitem__)
        return self.database_modes.get(database, self.access_mode)


def parse_connection(name: str, raw: Any) -> ConnectionConfig:
    """Validate a raw config dict field by field and build the ConnectionConfig (raises ConfigError on any problem)."""
    if not name or not isinstance(name, str):
        raise ConfigError(f"Connection name must be a non-empty string, got {name!r}")
    if not isinstance(raw, dict):
        raise ConfigError(f"Connection '{name}': definition must be an object, got {type(raw).__name__}")
    uri = fields.parse_uri(name, raw)
    return ConnectionConfig(
        name=name,
        type=fields.parse_type(name, raw, uri),
        uri=uri,
        access_mode=fields.parse_mode(name, raw),
        password_env=fields.parse_password_env(name, raw),
        query_timeout_s=fields.require_positive_int(
            name, "query_timeout_s", raw.get("query_timeout_s", DEFAULT_TIMEOUT_S)
        ),
        row_limit=fields.require_positive_int(name, "row_limit", raw.get("row_limit", DEFAULT_ROW_LIMIT)),
        export_max_rows=fields.require_positive_int(
            name, "export_max_rows", raw.get("export_max_rows", DEFAULT_EXPORT_MAX_ROWS)
        ),
        pool_size=fields.require_positive_int(name, "pool_size", raw.get("pool_size", DEFAULT_POOL_SIZE)),
        connect_timeout_s=fields.require_positive_int(
            name, "connect_timeout_s", raw.get("connect_timeout_s", DEFAULT_CONNECT_TIMEOUT_S)
        ),
        lock_timeout_max_s=fields.require_positive_int(
            name, "lock_timeout_max_s", raw.get("lock_timeout_max_s", DEFAULT_LOCK_TIMEOUT_MAX_S)
        ),
        max_response_bytes=fields.require_positive_int(
            name, "max_response_bytes", raw.get("max_response_bytes", MAX_RESPONSE_BYTES)
        ),
        hard_row_cap=fields.require_positive_int(name, "hard_row_cap", raw.get("hard_row_cap", HARD_ROW_CAP)),
        vector_min_candidates=fields.require_positive_int(
            name, "vector_min_candidates", raw.get("vector_min_candidates", MIN_CANDIDATES)
        ),
        vector_max_candidates=fields.require_positive_int(
            name, "vector_max_candidates", raw.get("vector_max_candidates", MAX_CANDIDATES)
        ),
        write_ops=fields.parse_write_ops(name, raw),
        database_modes=fields.parse_database_modes(name, raw),
        redact_fields=fields.parse_redact_fields(name, raw),
        redact_patterns=fields.parse_redact_patterns(name, raw),
        max_plan_cost=fields.optional_positive_int(name, "max_plan_cost", raw.get("max_plan_cost")),
        compact=fields.parse_bool(name, "compact", raw.get("compact", False)),
    )


_ENV_STR_FIELDS = {"MODE": "access_mode", "PASSWORD_ENV": "password_env"}
_ENV_INT_FIELDS = {
    "TIMEOUT": "query_timeout_s",
    "ROW_LIMIT": "row_limit",
    "EXPORT_MAX_ROWS": "export_max_rows",
    "POOL_SIZE": "pool_size",
    "MAX_PLAN_COST": "max_plan_cost",
    "CONNECT_TIMEOUT": "connect_timeout_s",
    "LOCK_TIMEOUT_MAX": "lock_timeout_max_s",
    "MAX_RESPONSE_BYTES": "max_response_bytes",
    "HARD_ROW_CAP": "hard_row_cap",
    "VECTOR_MIN_CANDIDATES": "vector_min_candidates",
    "VECTOR_MAX_CANDIDATES": "vector_max_candidates",
}
_ENV_JSON_FIELDS = {
    "WRITE_OPS": "write_ops",
    "DATABASE_MODES": "database_modes",
    "REDACT_FIELDS": "redact_fields",
    "REDACT_PATTERNS": "redact_patterns",
}


def _env_overrides(env: Mapping[str, str]) -> dict[str, Any]:
    """Collect the optional env vars into raw config fields; empty-string values are ignored."""
    raw: dict[str, Any] = {}
    for var, field_name in _ENV_STR_FIELDS.items():
        if value := env.get(var):
            raw[field_name] = value
    for var, field_name in _ENV_INT_FIELDS.items():
        if value := env.get(var):
            raw[field_name] = fields.parse_int_env(var, value)
    for var, field_name in _ENV_JSON_FIELDS.items():
        if value := env.get(var):
            raw[field_name] = fields.parse_json_env(var, value)
    if value := env.get("COMPACT_OUTPUT"):
        raw["compact"] = fields.parse_bool_env("COMPACT_OUTPUT", value)
    return raw


def connection_from_env(env: Mapping[str, str] | None = None) -> ConnectionConfig:
    """Build the instance's single connection from environment variables (URI, ENGINE_TYPE, NAME, MODE, ...)."""
    env = os.environ if env is None else env
    uri = env.get("URI")
    if not uri:
        raise ConfigError("URI is required (e.g. URI=postgresql://user@host:5432/db)")

    engine = fields.engine_from_env(env, uri)
    name = env.get("NAME") or engine or infer_type(uri, "URI")

    raw: dict[str, Any] = {"uri": uri, **_env_overrides(env)}
    if engine:
        raw["type"] = engine
    return parse_connection(name, raw)
