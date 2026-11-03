import json

import pytest

from mcp_database.config import WRITE_OPS, connection_from_env, parse_connection
from mcp_database.errors import ConfigError


class TestParseConnection:
    def test_happy_full(self):
        cfg = parse_connection(
            "pg_app",
            {
                "type": "postgres",
                "uri": "postgresql://app@localhost:5432/app",
                "access_mode": "read_write",
                "password_env": "PG_PASS",
                "query_timeout_s": 60,
                "row_limit": 1000,
                "write_ops": ["insert", "update"],
                "database_modes": {"prod": "read_only"},
                "redact_fields": ["Email", "*"],
            },
        )
        assert cfg.type == "postgres"
        assert cfg.write_ops == frozenset({"insert", "update"})
        assert cfg.database_modes == {"prod": "read_only"}
        assert cfg.redact_fields == ("email", "*")
        assert cfg.redact_all

    @pytest.mark.parametrize(
        ("uri", "expected"),
        [
            ("postgresql://u@h/db", "postgres"),
            ("postgres://u@h/db", "postgres"),
            ("mysql://u@h/db", "mysql"),
            ("mongodb://h:27017/db", "mongodb"),
            ("mongodb+srv://cluster.example.com/db", "mongodb"),
        ],
    )
    def test_type_inferred_from_scheme(self, uri, expected):
        assert parse_connection("c", {"uri": uri}).type == expected

    def test_defaults(self):
        cfg = parse_connection("c", {"uri": "mysql://u@h/db"})
        assert cfg.access_mode == "read_only"
        assert cfg.query_timeout_s == 30
        assert cfg.row_limit == 500
        assert cfg.write_ops == WRITE_OPS

    def test_emoji_connection_name_is_allowed(self):
        assert parse_connection("banco😀", {"uri": "mysql://u@h/db"}).name == "banco😀"

    @pytest.mark.parametrize(
        "raw",
        [
            {},
            {"uri": ""},
            {"uri": 42},
            {"uri": "ftp://h/db"},
            {"uri": "mysql://u@h/db", "access_mode": "rw"},
            {"uri": "mysql://u@h/db", "type": "oracle"},
            {"uri": "mysql://u@h/db", "write_ops": ["explode"]},
            {"uri": "mysql://u@h/db", "write_ops": "insert"},
            {"uri": "mysql://u@h/db", "database_modes": {"x": "everything"}},
            {"uri": "mysql://u@h/db", "database_modes": ["x"]},
            {"uri": "mysql://u@h/db", "redact_fields": [""]},
            {"uri": "mysql://u@h/db", "redact_fields": "email"},
            {"uri": "mysql://u@h/db", "query_timeout_s": 0},
            {"uri": "mysql://u@h/db", "query_timeout_s": -5},
            {"uri": "mysql://u@h/db", "query_timeout_s": True},
            {"uri": "mysql://u@h/db", "row_limit": 0},
            {"uri": "mysql://u@h/db", "password_env": ""},
        ],
    )
    def test_sad_inputs(self, raw):
        with pytest.raises(ConfigError):
            parse_connection("c", raw)

    @pytest.mark.parametrize("name", ["", None, 42])
    def test_absurd_names(self, name):
        with pytest.raises(ConfigError):
            parse_connection(name, {"uri": "mysql://u@h/db"})

    def test_definition_must_be_object(self):
        with pytest.raises(ConfigError, match="object"):
            parse_connection("c", "mysql://u@h/db")


class TestResolvedUri:
    def test_no_password_env_returns_uri_untouched(self):
        cfg = parse_connection("c", {"uri": "mysql://u:plain@h/db"})
        assert cfg.resolved_uri() == "mysql://u:plain@h/db"

    def test_injects_password_from_env(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "s3cr3t/with@chars")
        cfg = parse_connection("c", {"uri": "postgresql://app@localhost:5432/db", "password_env": "MY_SECRET"})
        assert cfg.resolved_uri() == "postgresql://app:s3cr3t%2Fwith%40chars@localhost:5432/db"

    def test_replaces_existing_password(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "new")
        cfg = parse_connection("c", {"uri": "mysql://u:old@h/db", "password_env": "MY_SECRET"})
        assert cfg.resolved_uri() == "mysql://u:new@h/db"

    def test_multi_host_mongodb_uri(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "pw")
        cfg = parse_connection(
            "c", {"uri": "mongodb://u@h1:27017,h2:27017/db?replicaSet=rs0", "password_env": "MY_SECRET"}
        )
        assert cfg.resolved_uri() == "mongodb://u:pw@h1:27017,h2:27017/db?replicaSet=rs0"

    def test_missing_env_var(self, monkeypatch):
        monkeypatch.delenv("NOPE", raising=False)
        cfg = parse_connection("c", {"uri": "mysql://u@h/db", "password_env": "NOPE"})
        with pytest.raises(ConfigError, match="NOPE"):
            cfg.resolved_uri()

    def test_uri_without_user(self, monkeypatch):
        monkeypatch.setenv("MY_SECRET", "pw")
        cfg = parse_connection("c", {"uri": "mongodb://localhost:27017/db", "password_env": "MY_SECRET"})
        with pytest.raises(ConfigError, match="username"):
            cfg.resolved_uri()

    def test_at_sign_only_in_path_is_not_a_username(self, monkeypatch):
        """An @ after the first / is part of the path, not credentials, so password_env still needs a username."""
        monkeypatch.setenv("MY_SECRET", "pw")
        cfg = parse_connection("c", {"uri": "postgresql://localhost:5432/db@weird", "password_env": "MY_SECRET"})
        with pytest.raises(ConfigError, match="username"):
            cfg.resolved_uri()


class TestModeFor:
    def test_without_database_modes(self):
        cfg = parse_connection("c", {"uri": "mysql://u@h/db", "access_mode": "read_write"})
        assert cfg.mode_for(None) == "read_write"
        assert cfg.mode_for("anything") == "read_write"

    def test_override_and_fallback(self):
        cfg = parse_connection(
            "c",
            {"uri": "mysql://u@h", "access_mode": "read_write", "database_modes": {"prod": "monitor"}},
        )
        assert cfg.mode_for("prod") == "monitor"
        assert cfg.mode_for("dev") == "read_write"
        assert cfg.mode_for(None) == "monitor"  # fail-restrictive when the target is unknown


class TestConnectionFromEnv:
    def test_happy_full(self):
        cfg = connection_from_env(
            env={
                "ENGINE_TYPE": "postgres",
                "URI": "postgresql://app@localhost:5432/app",
                "NAME": "pg_app",
                "MODE": "read_write",
                "TIMEOUT": "60",
                "ROW_LIMIT": "1000",
                "PASSWORD_ENV": "PG_PASS",
                "WRITE_OPS": json.dumps(["insert", "update"]),
                "DATABASE_MODES": json.dumps({"prod": "read_only"}),
                "REDACT_FIELDS": json.dumps(["Email", "*"]),
            }
        )
        assert (cfg.name, cfg.type, cfg.access_mode) == ("pg_app", "postgres", "read_write")
        assert cfg.query_timeout_s == 60
        assert cfg.row_limit == 1000
        assert cfg.password_env == "PG_PASS"
        assert cfg.write_ops == frozenset({"insert", "update"})
        assert cfg.database_modes == {"prod": "read_only"}
        assert cfg.redact_fields == ("email", "*")

    def test_happy_defaults(self):
        cfg = connection_from_env(env={"URI": "mysql://u@h/db"})
        assert (cfg.name, cfg.type, cfg.access_mode) == ("mysql", "mysql", "read_only")
        assert cfg.query_timeout_s == 30
        assert cfg.row_limit == 500
        assert cfg.export_max_rows == 100_000
        assert cfg.pool_size == 2
        assert cfg.compact is False

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("true", True), ("1", True), ("yes", True), ("on", True), ("false", False), ("0", False), ("no", False)],
    )
    def test_compact_output_env(self, value, expected):
        cfg = connection_from_env(env={"URI": "mysql://u@h/db", "COMPACT_OUTPUT": value})
        assert cfg.compact is expected

    @pytest.mark.parametrize("value", ["maybe", "sim", "🤔"])
    def test_sad_compact_output_env(self, value):
        with pytest.raises(ConfigError, match="COMPACT_OUTPUT"):
            connection_from_env(env={"URI": "mysql://u@h/db", "COMPACT_OUTPUT": value})

    def test_compact_from_json_config(self):
        assert parse_connection("c", {"uri": "mysql://u@h/db", "compact": True}).compact is True

    @pytest.mark.parametrize("value", ["true", 1, [], {"x": 1}])
    def test_sad_compact_json_must_be_bool(self, value):
        with pytest.raises(ConfigError, match="compact"):
            parse_connection("c", {"uri": "mysql://u@h/db", "compact": value})

    def test_happy_export_max_rows(self):
        cfg = connection_from_env(env={"URI": "mysql://u@h/db", "EXPORT_MAX_ROWS": "123"})
        assert cfg.export_max_rows == 123

    @pytest.mark.parametrize("value", ["many", "0", "-5"])
    def test_sad_export_max_rows(self, value):
        with pytest.raises(ConfigError):
            connection_from_env(env={"URI": "mysql://u@h/db", "EXPORT_MAX_ROWS": value})

    def test_sad_export_max_rows_absurd_huge_is_accepted_as_int(self):
        cfg = connection_from_env(env={"URI": "mysql://u@h/db", "EXPORT_MAX_ROWS": str(10**12)})
        assert cfg.export_max_rows == 10**12

    def test_happy_pool_size(self):
        """POOL_SIZE overrides the default of 2 connections per pool."""
        cfg = connection_from_env(env={"URI": "mysql://u@h/db", "POOL_SIZE": "8"})
        assert cfg.pool_size == 8

    def test_max_plan_cost_defaults_to_none_and_parses(self):
        """MAX_PLAN_COST is opt-in: absent means no cost guardrail, present must be a positive int."""
        assert connection_from_env(env={"URI": "mysql://u@h/db"}).max_plan_cost is None
        assert connection_from_env(env={"URI": "mysql://u@h/db", "MAX_PLAN_COST": "50000"}).max_plan_cost == 50000

    @pytest.mark.parametrize("value", ["0", "-1", "lots"])
    def test_sad_max_plan_cost(self, value):
        with pytest.raises(ConfigError):
            connection_from_env(env={"URI": "mysql://u@h/db", "MAX_PLAN_COST": value})

    @pytest.mark.parametrize("value", ["many", "0", "-3", "2.5", "🚀"])
    def test_sad_pool_size(self, value):
        """Non-positive or non-integer POOL_SIZE is rejected with a clear config error."""
        with pytest.raises(ConfigError):
            connection_from_env(env={"URI": "mysql://u@h/db", "POOL_SIZE": value})

    def test_happy_operational_limit_defaults(self):
        """Connect/lock/response/vector limits fall back to their module-constant defaults when unset."""
        cfg = connection_from_env(env={"URI": "mysql://u@h/db"})
        assert (cfg.connect_timeout_s, cfg.lock_timeout_max_s) == (5, 10)
        assert (cfg.max_response_bytes, cfg.hard_row_cap) == (1024 * 1024, 5000)
        assert (cfg.vector_min_candidates, cfg.vector_max_candidates) == (100, 10000)

    @pytest.mark.parametrize(
        "var, attr, expected",
        [
            ("CONNECT_TIMEOUT", "connect_timeout_s", 12),
            ("LOCK_TIMEOUT_MAX", "lock_timeout_max_s", 20),
            ("MAX_RESPONSE_BYTES", "max_response_bytes", 2048),
            ("HARD_ROW_CAP", "hard_row_cap", 9000),
            ("VECTOR_MIN_CANDIDATES", "vector_min_candidates", 50),
            ("VECTOR_MAX_CANDIDATES", "vector_max_candidates", 20000),
        ],
    )
    def test_happy_operational_limit_env_override(self, var, attr, expected):
        """Each operational-limit env var overrides its config field."""
        cfg = connection_from_env(env={"URI": "mysql://u@h/db", var: str(expected)})
        assert getattr(cfg, attr) == expected

    @pytest.mark.parametrize("var", ["CONNECT_TIMEOUT", "LOCK_TIMEOUT_MAX", "HARD_ROW_CAP", "VECTOR_MIN_CANDIDATES"])
    @pytest.mark.parametrize("value", ["0", "-5", "huge"])
    def test_sad_operational_limit_env_rejects_non_positive(self, var, value):
        """The operational-limit envs reject zero/negative/non-integer like the other positive ints."""
        with pytest.raises(ConfigError):
            connection_from_env(env={"URI": "mysql://u@h/db", var: value})

    def test_happy_name_defaults_to_engine(self):
        cfg = connection_from_env(env={"ENGINE_TYPE": "mongodb", "URI": "mongodb://localhost:27017/app"})
        assert cfg.name == "mongodb"

    def test_sad_missing_uri(self):
        with pytest.raises(ConfigError, match="URI is required"):
            connection_from_env(env={"ENGINE_TYPE": "postgres"})

    def test_sad_engine_uri_scheme_mismatch(self):
        with pytest.raises(ConfigError, match="does not match ENGINE_TYPE"):
            connection_from_env(env={"ENGINE_TYPE": "postgres", "URI": "mysql://u@h/db"})

    def test_sad_unknown_engine(self):
        with pytest.raises(ConfigError, match="ENGINE_TYPE must be one of"):
            connection_from_env(env={"ENGINE_TYPE": "oracle", "URI": "oracle://u@h/db"})

    def test_sad_unknown_scheme_without_engine(self):
        with pytest.raises(ConfigError, match="cannot infer"):
            connection_from_env(env={"URI": "oracle://u@h/db"})

    @pytest.mark.parametrize("value", ["abc", "1.5", "", "🚀"])
    def test_sad_non_integer_timeout(self, value):
        env = {"URI": "mysql://u@h/db", "TIMEOUT": value}
        if not value:
            assert connection_from_env(env=env).query_timeout_s == 30  # empty env var counts as unset
        else:
            with pytest.raises(ConfigError, match="TIMEOUT"):
                connection_from_env(env=env)

    def test_sad_invalid_mode(self):
        with pytest.raises(ConfigError, match="access_mode"):
            connection_from_env(env={"URI": "mysql://u@h/db", "MODE": "rw"})

    @pytest.mark.parametrize("var", ["WRITE_OPS", "DATABASE_MODES", "REDACT_FIELDS"])
    def test_sad_invalid_json_fields(self, var):
        with pytest.raises(ConfigError, match=var):
            connection_from_env(env={"URI": "mysql://u@h/db", var: "[broken"})

    def test_absurd_unicode_name(self):
        cfg = connection_from_env(env={"URI": "mysql://u@h/db", "NAME": "produção-🚀"})
        assert cfg.name == "produção-🚀"

    def test_absurd_empty_uri_is_missing(self):
        with pytest.raises(ConfigError, match="URI is required"):
            connection_from_env(env={"URI": ""})

    def test_absurd_legacy_connections_var_is_ignored(self):
        env = {
            "MCPDB_CONNECTIONS": json.dumps([{"name": "a", "uri": "mysql://u@h/db"}]),
            "URI": "postgresql://u@h/db",
        }
        cfg = connection_from_env(env=env)
        assert cfg.name == "postgres"  # the legacy multi-connection variable has no effect
