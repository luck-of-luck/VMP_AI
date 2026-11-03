"""Redis envelope validation: allowlists, banned commands, audit shapes and the guard dispatch."""

import pytest

from mcp_database import guard
from mcp_database.errors import QueryValidationError
from mcp_database.helpers import redis_query


class TestParse:
    def test_happy_read(self):
        parsed = redis_query.parse_redis_query({"command": "hgetall", "args": ["user:1"]})
        assert parsed == {"command": "HGETALL", "args": ["user:1"], "database": None}

    def test_two_word_commands_normalize(self):
        parsed = redis_query.parse_redis_query({"command": "memory   usage", "args": ["k"]})
        assert parsed["command"] == "MEMORY USAGE"

    def test_database_becomes_string(self):
        assert redis_query.parse_redis_query({"command": "GET", "args": ["k"], "database": 3})["database"] == "3"

    @pytest.mark.parametrize("query", ["GET k", 42, None, ["GET", "k"]])
    def test_non_dict_envelopes_rejected(self, query):
        with pytest.raises(QueryValidationError, match="objects"):
            redis_query.parse_redis_query(query)

    @pytest.mark.parametrize("command", ["", "   ", None, 42])
    def test_missing_command_rejected(self, command):
        with pytest.raises(QueryValidationError, match="string 'command'"):
            redis_query.parse_redis_query({"command": command})

    @pytest.mark.parametrize("args", ["k", {"k": 1}, [["nested"]], [{"a": 1}], [True]])
    def test_non_scalar_args_rejected(self, args):
        with pytest.raises(QueryValidationError, match=r"scalar|list"):
            redis_query.parse_redis_query({"command": "GET", "args": args})

    @pytest.mark.parametrize("command", ["GETALL", "SUBSCRIBE", "XADD", "rm -rf /", "🤯"])
    def test_unknown_commands_rejected(self, command):
        with pytest.raises(QueryValidationError, match="Unknown or unsupported"):
            redis_query.parse_redis_query({"command": command})


class TestBannedCommands:
    @pytest.mark.parametrize(
        "command",
        ["FLUSHDB", "flushall", "EVAL", "EVALSHA", "eval_ro", "SCRIPT", "FUNCTION", "FCALL",
         "KEYS", "CONFIG", "config set", "DEBUG", "SHUTDOWN", "MONITOR", "MIGRATE", "SWAPDB"],
    )  # fmt: skip
    def test_banned_commands_never_parse(self, command):
        """FLUSH*/EVAL/KEYS and friends are rejected with the reason, before any allowlist."""
        with pytest.raises(QueryValidationError, match="never allowed"):
            redis_query.parse_redis_query({"command": command, "args": []})

    def test_banned_wins_over_read_shape(self):
        """Even wrapped in whitespace/case tricks, a banned command cannot reach an allowlist."""
        with pytest.raises(QueryValidationError, match="never allowed"):
            redis_query.parse_redis_query({"command": "  FlUsHdB  "})


class TestGuardDispatch:
    def test_validate_read_happy(self):
        assert guard.validate_redis_read({"command": "SCAN", "args": [0]})["command"] == "SCAN"

    def test_read_rejects_write_commands(self):
        with pytest.raises(QueryValidationError, match="db_write_query"):
            guard.validate_redis_read({"command": "DEL", "args": ["k"]})

    @pytest.mark.parametrize(
        ("command", "op"),
        [("SET", "insert"), ("EXPIRE", "update"), ("DEL", "delete"), ("ZADD", "insert"), ("LTRIM", "delete")],
    )
    def test_classify_write_maps_to_write_ops(self, command, op):
        parsed, kind = guard.classify_redis_write({"command": command, "args": ["k", "v"]})
        assert (parsed["command"], kind) == (command, op)

    def test_write_rejects_read_commands(self):
        with pytest.raises(QueryValidationError, match="db_read_query"):
            guard.classify_redis_write({"command": "GET", "args": ["k"]})


class TestAuditShape:
    def test_values_are_masked_keys_kept(self):
        shape = redis_query.audit_shape({"command": "SET", "args": ["user:1", "s3cr3t"], "database": "0"})
        assert shape == {"command": "SET", "args": ["user:1", "?"], "database": "0"}

    def test_multi_key_delete_keeps_all_keys(self):
        shape = redis_query.audit_shape({"command": "DEL", "args": ["a", "b", "c"], "database": None})
        assert shape["args"] == ["a", "b", "c"]

    def test_hset_masks_every_value(self):
        shape = redis_query.audit_shape({"command": "HSET", "args": ["user:1", "email", "x@y", "phone", "9"]})
        assert shape["args"] == ["user:1", "?", "?", "?", "?"]


class TestDatabaseField:
    @pytest.mark.parametrize("database", [1.5, True, {"db": 0}, ["0"]])
    def test_non_index_database_rejected(self, database):
        """The database field must be the logical index, not arbitrary structures."""
        with pytest.raises(QueryValidationError, match="logical index"):
            redis_query.parse_redis_query({"command": "GET", "args": ["k"], "database": database})
