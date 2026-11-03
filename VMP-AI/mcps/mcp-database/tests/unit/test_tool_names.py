"""TOOLS / DISABLE_TOOLS resolve into the exposed tool set, rejecting nonsense fail-closed."""

import pytest

from mcp_database.errors import ConfigError
from mcp_database.tool_names import ALL_TOOL_NAMES, resolve_enabled_tools


def test_neither_set_exposes_all():
    assert resolve_enabled_tools({}) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('["db_read_query"]', {"db_read_query"}),
        (
            '["db_read_query", "db_schema_objects", "db_schema_connections"]',
            {"db_read_query", "db_schema_objects", "db_schema_connections"},
        ),
        ('["db_read_query", "db_read_query"]', {"db_read_query"}),  # duplicates collapse
    ],
)
def test_allowlist_happy(value, expected):
    assert resolve_enabled_tools({"TOOLS": value}) == frozenset(expected)


@pytest.mark.parametrize(
    "disabled",
    [
        '["db_admin_kill"]',
        '["db_admin_kill", "db_admin_cluster", "db_write_query"]',
        '["db_perf_logs", "db_perf_settings", "db_read_export"]',
    ],
)
def test_denylist_removes_from_all(disabled):
    import json

    enabled = resolve_enabled_tools({"DISABLE_TOOLS": disabled})
    assert enabled == ALL_TOOL_NAMES - set(json.loads(disabled))


def test_both_set_is_rejected():
    with pytest.raises(ConfigError, match="only one of TOOLS"):
        resolve_enabled_tools({"TOOLS": '["db_read_query"]', "DISABLE_TOOLS": '["db_admin_kill"]'})


@pytest.mark.parametrize(
    ("env", "match"),
    [
        ({"TOOLS": "[]"}, "empty"),
        ({"TOOLS": '["db_read_query", "nope", "also_fake"]'}, "unknown tools: also_fake, nope"),
        ({"TOOLS": "not json"}, "JSON array"),
        ({"TOOLS": '"db_read_query"'}, "JSON array"),
        ({"TOOLS": "[1, 2]"}, "strings"),
        ({"DISABLE_TOOLS": '["ghost_tool"]'}, "unknown tools: ghost_tool"),
        ({"DISABLE_TOOLS": "{}"}, "JSON array"),
    ],
)
def test_sad_and_absurd(env, match):
    with pytest.raises(ConfigError, match=match):
        resolve_enabled_tools(env)


def test_denylist_of_everything_is_rejected():
    everything = f"[{', '.join(repr(n) for n in ALL_TOOL_NAMES)}]".replace("'", '"')
    with pytest.raises(ConfigError, match="disables every tool"):
        resolve_enabled_tools({"DISABLE_TOOLS": everything})
