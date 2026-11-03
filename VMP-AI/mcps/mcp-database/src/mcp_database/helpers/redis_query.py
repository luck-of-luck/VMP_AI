from __future__ import annotations

from typing import Any

from ..errors import QueryValidationError

READ_COMMANDS = frozenset(
    {
        "GET", "MGET", "GETRANGE", "STRLEN", "EXISTS", "TYPE", "TTL", "PTTL", "SCAN",
        "HGET", "HGETALL", "HKEYS", "HLEN", "LRANGE", "LLEN", "LINDEX",
        "SMEMBERS", "SISMEMBER", "SCARD", "ZRANGE", "ZSCORE", "ZCARD",
        "DBSIZE", "RANDOMKEY", "MEMORY USAGE", "OBJECT ENCODING",
    }
)  # fmt: skip
WRITE_COMMANDS: dict[str, str] = {
    "SET": "insert",
    "SETNX": "insert",
    "HSET": "insert",
    "LPUSH": "insert",
    "RPUSH": "insert",
    "SADD": "insert",
    "ZADD": "insert",
    "APPEND": "insert",
    "EXPIRE": "update",
    "PEXPIRE": "update",
    "PERSIST": "update",
    "RENAME": "update",
    "INCR": "update",
    "DECR": "update",
    "INCRBY": "update",
    "DECRBY": "update",
    "HINCRBY": "update",
    "SETRANGE": "update",
    "DEL": "delete",
    "UNLINK": "delete",
    "HDEL": "delete",
    "LPOP": "delete",
    "RPOP": "delete",
    "SREM": "delete",
    "ZREM": "delete",
    "LTRIM": "delete",
    "GETDEL": "delete",
}
# Never allowed, in any mode, for any tool: these are either irreversible at database scope,
# arbitrary code execution (the $where rationale), or O(N) blocking scans of the whole keyspace.
BANNED_COMMANDS: dict[str, str] = {
    "FLUSHDB": "it deletes every key in the database and cannot be bounded or undone",
    "FLUSHALL": "it deletes every key in every database and cannot be bounded or undone",
    "EVAL": "it executes arbitrary server-side Lua",
    "EVALSHA": "it executes arbitrary server-side Lua",
    "EVAL_RO": "it executes arbitrary server-side Lua",
    "EVALSHA_RO": "it executes arbitrary server-side Lua",
    "SCRIPT": "it manages arbitrary server-side Lua",
    "FUNCTION": "it manages arbitrary server-side functions",
    "FCALL": "it executes arbitrary server-side functions",
    "FCALL_RO": "it executes arbitrary server-side functions",
    "KEYS": "it blocks the server scanning the whole keyspace; use SCAN instead",
    "CONFIG": "runtime reconfiguration is out of scope; use db_perf_settings to read config",
    "DEBUG": "it is a server-crashing diagnostic surface",
    "SHUTDOWN": "it stops the server",
    "MONITOR": "it streams every command on the server",
    "MIGRATE": "it moves keys to another server",
    "SWAPDB": "it swaps entire databases atomically and cannot be bounded",
}
# Commands whose arguments are all key names (safe to keep verbatim in the audit log).
_ALL_KEY_ARGS = frozenset({"DEL", "UNLINK", "EXISTS", "MGET"})


def normalize_command(raw: Any) -> str:
    """The command uppercased with collapsed whitespace (MEMORY USAGE and OBJECT ENCODING are two words)."""
    if not isinstance(raw, str) or not raw.strip():
        raise QueryValidationError("Redis query requires a string 'command' field")
    return " ".join(raw.upper().split())


def parse_redis_query(query: Any) -> dict[str, Any]:
    """Validate the `{"command", "args", "database"}` envelope; banned commands are rejected with the reason."""
    if not isinstance(query, dict):
        raise QueryValidationError(
            'Redis queries are objects: {"command": "HGETALL", "args": ["key"]} — not raw strings'
        )
    command = normalize_command(query.get("command"))
    first_word = command.split()[0]
    for banned in (command, first_word):
        if banned in BANNED_COMMANDS:
            raise QueryValidationError(f"Command '{banned}' is never allowed: {BANNED_COMMANDS[banned]}")
    if command not in READ_COMMANDS and command not in WRITE_COMMANDS:
        known = ", ".join(sorted(READ_COMMANDS | set(WRITE_COMMANDS)))
        raise QueryValidationError(f"Unknown or unsupported Redis command '{command}' (supported: {known})")
    args = query.get("args", [])
    if not isinstance(args, list):
        raise QueryValidationError("'args' must be a list of scalars")
    for arg in args:
        if isinstance(arg, bool) or not isinstance(arg, (str, int, float)):
            raise QueryValidationError(f"Redis command arguments must be scalars, got {type(arg).__name__}")
    database = query.get("database")
    if database is not None and (isinstance(database, bool) or not isinstance(database, (str, int))):
        raise QueryValidationError("'database' must be the logical index (0-15) when provided")
    return {"command": command, "args": args, "database": str(database) if database is not None else None}


def audit_shape(parsed: dict[str, Any]) -> dict[str, Any]:
    """Command plus key names only: the first argument is the key, every later value becomes `?`."""
    command, args = parsed["command"], parsed["args"]
    if command in _ALL_KEY_ARGS:
        kept = list(args)
    else:
        kept = [args[0], *["?"] * (len(args) - 1)] if args else []
    return {"command": command, "args": kept, "database": parsed.get("database")}
