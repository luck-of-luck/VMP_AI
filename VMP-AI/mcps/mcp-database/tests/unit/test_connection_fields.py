import pytest

from mcp_database.errors import ConfigError
from mcp_database.helpers import connection_fields as fields


@pytest.mark.parametrize(
    ("uri", "expected"),
    [
        ("postgres://u@h/db", "postgres"),
        ("postgresql://u@h/db", "postgres"),
        ("mysql://u@h/db", "mysql"),
        ("mariadb://u@h/db", "mariadb"),
        ("sqlite:///tmp/app.db", "sqlite"),
        ("mongodb://u@h/db", "mongodb"),
        ("mongodb+srv://u@h/db", "mongodb"),
        ("redis://h:6379/0", "redis"),
        ("rediss://h:6380/0", "redis"),
    ],
)
def test_infer_type_happy(uri, expected):
    assert fields.infer_type(uri, "c") == expected


@pytest.mark.parametrize("uri", ["oracle://u@h/db", "not-a-uri", "", "🤯://x"])
def test_infer_type_sad(uri):
    with pytest.raises(ConfigError):
        fields.infer_type(uri, "c")


@pytest.mark.parametrize("value", [1, 30, 10**9])
def test_require_positive_int_happy(value):
    assert fields.require_positive_int("c", "k", value) == value


@pytest.mark.parametrize("value", [0, -1, True, False, "5", 3.5, None])
def test_require_positive_int_sad(value):
    with pytest.raises(ConfigError, match="positive integer"):
        fields.require_positive_int("c", "k", value)


@pytest.mark.parametrize("raw", [{}, {"uri": ""}, {"uri": 42}])
def test_parse_uri_sad(raw):
    with pytest.raises(ConfigError, match="'uri' is required"):
        fields.parse_uri("c", raw)


def test_parse_type_explicit_overrides_scheme():
    assert fields.parse_type("c", {"type": "mysql"}, "postgres://u@h/db") == "mysql"


def test_parse_type_sad_unknown():
    with pytest.raises(ConfigError, match="unknown type"):
        fields.parse_type("c", {"type": "oracle"}, "postgres://u@h/db")


def test_parse_mode_defaults_to_read_only():
    assert fields.parse_mode("c", {}) == "read_only"


@pytest.mark.parametrize("mode", ["rw", "READ_ONLY", "", 42])
def test_parse_mode_sad(mode):
    with pytest.raises(ConfigError, match="access_mode"):
        fields.parse_mode("c", {"access_mode": mode})


def test_parse_write_ops_defaults_to_all():
    assert fields.parse_write_ops("c", {}) == fields.WRITE_OPS


def test_parse_write_ops_happy_subset():
    assert fields.parse_write_ops("c", {"write_ops": ["insert", "update"]}) == frozenset({"insert", "update"})


@pytest.mark.parametrize("ops", ["insert", {"insert": True}, ["insert", "drop"], ["INSERT"]])
def test_parse_write_ops_sad(ops):
    with pytest.raises(ConfigError, match="write_ops"):
        fields.parse_write_ops("c", {"write_ops": ops})


def test_parse_database_modes_happy():
    assert fields.parse_database_modes("c", {"database_modes": {"app": "read_write"}}) == {"app": "read_write"}


@pytest.mark.parametrize("modes", [["app"], {"app": "rw"}, {"app": ""}])
def test_parse_database_modes_sad(modes):
    with pytest.raises(ConfigError):
        fields.parse_database_modes("c", {"database_modes": modes})


def test_parse_redact_fields_lowercases_but_keeps_star():
    assert fields.parse_redact_fields("c", {"redact_fields": ["Email", "*", "SSN"]}) == ("email", "*", "ssn")


@pytest.mark.parametrize("redact", ["email", [""], [42], [None]])
def test_parse_redact_fields_sad(redact):
    with pytest.raises(ConfigError, match="redact_fields"):
        fields.parse_redact_fields("c", {"redact_fields": redact})


def test_parse_password_env_happy():
    assert fields.parse_password_env("c", {}) is None
    assert fields.parse_password_env("c", {"password_env": "PG_PASS"}) == "PG_PASS"


@pytest.mark.parametrize("value", ["", 42, ["PG_PASS"], {"var": "PG_PASS"}])
def test_parse_password_env_sad(value):
    with pytest.raises(ConfigError, match="password_env"):
        fields.parse_password_env("c", {"password_env": value})


def test_engine_from_env_absent_is_none():
    assert fields.engine_from_env({}, "postgres://u@h/db") is None


def test_engine_from_env_happy_match():
    assert fields.engine_from_env({"ENGINE_TYPE": "postgres"}, "postgresql://u@h/db") == "postgres"


def test_engine_from_env_sad_unknown_engine():
    with pytest.raises(ConfigError, match="ENGINE_TYPE"):
        fields.engine_from_env({"ENGINE_TYPE": "oracle"}, "oracle://u@h/db")


def test_parse_redact_patterns_happy():
    assert fields.parse_redact_patterns("c", {"redact_patterns": ["ssn", ".*_email$"]}) == ("ssn", ".*_email$")


def test_parse_redact_patterns_default_empty():
    assert fields.parse_redact_patterns("c", {}) == ()


@pytest.mark.parametrize("patterns", ["ssn", [""], [42], ["(unclosed"]])
def test_parse_redact_patterns_sad(patterns):
    with pytest.raises(ConfigError, match="redact_patterns"):
        fields.parse_redact_patterns("c", {"redact_patterns": patterns})


def test_engine_from_env_schemeless_uri_skips_mismatch_check():
    """Without :// there is no scheme to compare, so ENGINE_TYPE is accepted as-is instead of erroring."""
    assert fields.engine_from_env({"ENGINE_TYPE": "postgres"}, "host-without-scheme") == "postgres"


def test_engine_from_env_sad_scheme_mismatch():
    with pytest.raises(ConfigError, match="does not match"):
        fields.engine_from_env({"ENGINE_TYPE": "mysql"}, "postgresql://u@h/db")


def test_parse_int_env():
    assert fields.parse_int_env("TIMEOUT", "5") == 5
    with pytest.raises(ConfigError, match="must be an integer"):
        fields.parse_int_env("TIMEOUT", "five")


def test_parse_json_env():
    assert fields.parse_json_env("WRITE_OPS", '["insert"]') == ["insert"]
    with pytest.raises(ConfigError, match="invalid JSON"):
        fields.parse_json_env("WRITE_OPS", "{not json")
