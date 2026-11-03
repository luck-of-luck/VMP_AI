"""Tool inventory, annotations and the per-tool happy/sad/absurd matrix."""

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_database.audit import AuditLogger
from mcp_database.server import build_server
from mcp_database.tool_names import ALL_TOOL_NAMES

from .helpers import REGISTRY, FakeAdapter, call

VALID_ARGS = {
    "db_schema_connections": {},
    "db_schema_databases": {"conn": "rw"},
    "db_schema_objects": {"conn": "rw", "database": "public"},
    "db_schema_describe": {"conn": "rw", "database": "public", "object": "users"},
    "db_schema_ddl": {"conn": "rw", "database": "public", "object": "users"},
    "db_schema_search": {"conn": "rw", "pattern": "user"},
    "db_schema_relationships": {"conn": "rw", "database": "public"},
    "db_schema_users": {"conn": "rw"},
    "db_schema_grants": {"conn": "rw"},
    "db_schema_search_indexes": {"conn": "rw"},
    "db_read_query": {"conn": "rw", "query": "SELECT 1"},
    "db_read_sample": {"conn": "rw", "database": "public", "object": "users"},
    "db_read_export": {"conn": "rw", "query": "SELECT 1", "path": "__TMP__/out.json"},
    "db_read_vector_search": {
        "conn": "rw",
        "database": "public",
        "object": "docs",
        "column": "emb",
        "vector": [0.1, 0.2],
    },
    "db_read_text_search": {"conn": "rw", "database": "public", "object": "docs", "query": "hello", "column": "title"},
    "db_perf_explain": {"conn": "rw", "query": "SELECT 1"},
    "db_perf_column_stats": {"conn": "rw", "database": "public", "object": "users"},
    "db_perf_diagnose": {"conn": "rw"},
    "db_perf_top_queries": {"conn": "rw"},
    "db_perf_active_ops": {"conn": "rw"},
    "db_perf_blocking": {"conn": "rw"},
    "db_perf_index_stats": {"conn": "rw"},
    "db_perf_table_stats": {"conn": "rw"},
    "db_perf_health": {"conn": "rw"},
    "db_perf_replication": {"conn": "rw"},
    "db_perf_settings": {"conn": "rw"},
    "db_perf_logs": {"conn": "rw"},
    "db_perf_vector_stats": {"conn": "rw"},
    "db_perf_cluster": {"conn": "rw"},
    "db_perf_storage": {"conn": "rw"},
    "db_perf_tls": {"conn": "rw"},
    "db_perf_config_check": {"conn": "rw"},
    "db_perf_index_advisor": {"conn": "rw"},
    "db_write_query": {"conn": "rw", "query": "DELETE FROM t WHERE id = 1"},
    "db_write_search_index": {
        "conn": "rw",
        "database": "public",
        "object": "docs",
        "action": "create",
        "name": "emb_idx",
        "definition": {"column": "emb"},
    },
    "db_admin_kill": {"conn": "rw", "target_id": "42"},
    "db_admin_cluster": {"conn": "rw", "action": "step_down"},
    "db_admin_analyze": {"conn": "rw", "database": "public", "object": "users"},
    "db_admin_maintain": {"conn": "rw", "database": "public", "object": "users"},
}

DENIED_ON_MONITOR = {
    "db_read_query",
    "db_read_sample",
    "db_read_export",
    "db_read_vector_search",
    "db_read_text_search",
    "db_write_query",
    "db_write_search_index",
    "db_admin_kill",
    "db_admin_analyze",
    "db_admin_maintain",
    "db_admin_cluster",
}

DENIED_ON_READ_ONLY = {
    "db_write_query",
    "db_write_search_index",
    "db_admin_kill",
    "db_admin_analyze",
    "db_admin_maintain",
    "db_admin_cluster",
}

MISSING_ARG_CASES = [
    ("db_read_query", "conn"),
    ("db_read_query", "query"),
    ("db_read_sample", "object"),
    ("db_read_export", "path"),
    ("db_schema_objects", "database"),
    ("db_schema_describe", "object"),
    ("db_schema_ddl", "object"),
    ("db_schema_search", "pattern"),
    ("db_schema_relationships", "database"),
    ("db_perf_explain", "query"),
    ("db_write_query", "query"),
    ("db_admin_kill", "target_id"),
    ("db_admin_analyze", "database"),
    ("db_admin_maintain", "object"),
    ("db_read_vector_search", "vector"),
    ("db_read_vector_search", "column"),
    ("db_read_text_search", "query"),
    ("db_write_search_index", "action"),
    ("db_write_search_index", "name"),
    ("db_admin_cluster", "action"),
]


def _args(tool, tmp_path, conn=None):
    arguments = dict(VALID_ARGS[tool])
    for key, value in arguments.items():
        if value == "__TMP__/out.json":
            arguments[key] = str(tmp_path / "out.json")
        elif conn and key in ("conn", "conn_a"):
            arguments[key] = conn
    return arguments


async def test_lists_all_39_tools_with_annotations(mcp_server):
    async with create_connected_server_and_client_session(mcp_server._mcp_server) as client:
        listed = await client.list_tools()
    tools = {t.name: t for t in listed.tools}
    assert len(tools) == 39
    assert set(tools) == ALL_TOOL_NAMES  # the canonical inventory must not drift from what registers
    safe = [n for n in tools if n.split("_")[1] in ("schema", "read", "perf")]
    assert len(safe) == 33
    assert all(tools[n].annotations.readOnlyHint for n in safe)
    for name in (
        "db_write_query",
        "db_write_search_index",
        "db_admin_kill",
        "db_admin_analyze",
        "db_admin_maintain",
        "db_admin_cluster",
    ):
        assert tools[name].annotations.destructiveHint


def _restricted_server(audit_path, enabled):
    return build_server(dict(REGISTRY), audit=AuditLogger(audit_path), enabled_tools=enabled)


async def test_enabled_tools_allowlist_exposes_only_the_named(monkeypatch, audit_path):
    """A TOOLS allowlist registers exactly the named tools and nothing else."""
    monkeypatch.setattr("mcp_database.tools.context.create_adapter", lambda cfg: FakeAdapter(cfg))
    server = _restricted_server(audit_path, frozenset({"db_read_query", "db_schema_connections"}))
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        tools = {t.name for t in (await client.list_tools()).tools}
    assert tools == {"db_read_query", "db_schema_connections"}


async def test_disable_tools_denylist_hides_only_the_named(monkeypatch, audit_path):
    """A DISABLE_TOOLS denylist hides exactly the named tools, leaving the rest."""
    monkeypatch.setattr("mcp_database.tools.context.create_adapter", lambda cfg: FakeAdapter(cfg))
    hidden = {"db_admin_kill", "db_admin_cluster", "db_write_query"}
    server = _restricted_server(audit_path, ALL_TOOL_NAMES - hidden)
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        tools = {t.name for t in (await client.list_tools()).tools}
    assert tools == ALL_TOOL_NAMES - hidden
    assert len(tools) == 36


async def test_hidden_tool_cannot_be_called(monkeypatch, audit_path):
    """A tool excluded from the allowlist is not merely unlisted — calling it errors."""
    monkeypatch.setattr("mcp_database.tools.context.create_adapter", lambda cfg: FakeAdapter(cfg))
    server = _restricted_server(audit_path, frozenset({"db_schema_connections"}))
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        result = await client.call_tool("db_write_query", {"conn": "rw", "query": "DELETE FROM t WHERE id = 1"})
    assert result.isError


async def test_annotations_idempotent_hints(mcp_server):
    async with create_connected_server_and_client_session(mcp_server._mcp_server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    assert tools["db_read_query"].annotations.idempotentHint is True
    assert tools["db_write_query"].annotations.idempotentHint is False
    for name in ("db_admin_kill", "db_admin_analyze", "db_admin_maintain"):
        assert tools[name].annotations.idempotentHint is True


async def test_param_descriptions_exposed(mcp_server):
    async with create_connected_server_and_client_session(mcp_server._mcp_server) as client:
        tools = {t.name: t for t in (await client.list_tools()).tools}
    read_props = tools["db_read_query"].inputSchema["properties"]
    assert "db_schema_connections" in read_props["conn"]["description"]
    assert "collection" in read_props["query"]["description"]
    write_props = tools["db_write_query"].inputSchema["properties"]
    assert "insertOne" in write_props["query"]["description"]
    assert "WHERE" in write_props["expected_max_rows"]["description"]


@pytest.mark.parametrize("tool", sorted(VALID_ARGS))
async def test_matrix_happy(mcp_server, tmp_path, tool):
    result = await call(mcp_server, tool, _args(tool, tmp_path))
    assert not result.isError, f"{tool}: {result.content[0].text}"


@pytest.mark.parametrize("tool", sorted(t for t in VALID_ARGS if t != "db_schema_connections"))
async def test_matrix_sad_unknown_connection(mcp_server, tmp_path, tool):
    result = await call(mcp_server, tool, _args(tool, tmp_path, conn="ghost"))
    assert result.isError
    assert "Unknown connection 'ghost'" in result.content[0].text


@pytest.mark.parametrize("tool", sorted(DENIED_ON_MONITOR))
async def test_matrix_sad_denied_by_monitor_mode(mcp_server, tmp_path, tool):
    result = await call(mcp_server, tool, _args(tool, tmp_path, conn="mon"))
    assert result.isError
    assert "monitor" in result.content[0].text


@pytest.mark.parametrize("tool", sorted(DENIED_ON_READ_ONLY))
async def test_matrix_sad_denied_by_read_only_mode(mcp_server, tmp_path, tool):
    """Every write/admin tool is rejected on a read_only connection, naming the mode in the error."""
    result = await call(mcp_server, tool, _args(tool, tmp_path, conn="ro"))
    assert result.isError
    assert "read_only" in result.content[0].text


@pytest.mark.parametrize("tool", sorted(set(VALID_ARGS) - DENIED_ON_MONITOR - {"db_schema_connections"}))
async def test_matrix_happy_on_monitor(mcp_server, tmp_path, tool):
    """Every schema/perf tool still works on a monitor connection — that mode only blocks data access."""
    result = await call(mcp_server, tool, _args(tool, tmp_path, conn="mon"))
    assert not result.isError, f"{tool}: {result.content[0].text}"


@pytest.mark.parametrize(("tool", "missing"), MISSING_ARG_CASES)
async def test_matrix_sad_missing_required_argument(mcp_server, tmp_path, tool, missing):
    """Dropping a required argument yields a clean validation error, never a crash."""
    arguments = _args(tool, tmp_path)
    del arguments[missing]
    result = await call(mcp_server, tool, arguments)
    assert result.isError, f"{tool} without {missing!r} should fail"


@pytest.mark.parametrize("tool", sorted(t for t in VALID_ARGS if t != "db_schema_connections"))
async def test_matrix_absurd_emoji_connection(mcp_server, tmp_path, tool):
    result = await call(mcp_server, tool, _args(tool, tmp_path, conn="🐘🤯"))
    assert result.isError
    assert "Unknown connection" in result.content[0].text


async def test_matrix_absurd_wrong_argument_types(mcp_server):
    for tool, arguments in [
        ("db_read_query", {"conn": "rw", "query": 12345}),
        ("db_write_query", {"conn": "rw", "query": ["not", "a", "query"]}),
        ("db_perf_explain", {"conn": "rw", "query": True}),
        ("db_read_sample", {"conn": "rw", "database": "public", "object": "users", "n": "muitos"}),
        ("db_perf_top_queries", {"conn": "rw", "limit": -5}),
        ("db_perf_logs", {"conn": "rw", "limit": 0}),
        ("db_admin_kill", {"conn": "rw", "target_id": ["1", "2"]}),
        ("db_admin_kill", {"conn": "rw", "target_id": "42", "force": "maybe"}),
        ("db_schema_objects", {"conn": "rw", "database": 123}),
        ("db_schema_describe", {"conn": "rw", "database": "public", "object": {"a": 1}}),
        ("db_read_export", {"conn": "rw", "query": "SELECT 1", "path": 123}),
        ("db_read_query", {"conn": "rw", "query": "SELECT 1", "params": "not-a-list"}),
        ("db_write_query", {"conn": "rw", "query": "DELETE FROM t WHERE id = 1", "expected_max_rows": "many"}),
        ("db_admin_maintain", {"conn": "rw", "database": "public", "object": "users", "action": 42}),
        ("db_perf_column_stats", {"conn": "rw", "database": "public", "object": "users", "column": ["id"]}),
        ("db_read_vector_search", {"conn": "rw", "database": "public", "object": "d", "column": "e", "vector": []}),
        (
            "db_read_vector_search",
            {"conn": "rw", "database": "public", "object": "d", "column": "e", "vector": [0.1], "metric": "banana"},
        ),
        (
            "db_read_vector_search",
            {
                "conn": "mongo",
                "database": "app",
                "object": "d",
                "column": "e",
                "vector": [0.1],
                "index": "i",
                "num_candidates": -1,
            },
        ),
        ("db_read_text_search", {"conn": "rw", "database": "public", "object": "d", "query": "   "}),
        (
            "db_write_search_index",
            {"conn": "rw", "database": "public", "object": "d", "action": "explode", "name": "i"},
        ),
        ("db_write_search_index", {"conn": "rw", "database": "public", "object": "d", "action": "create", "name": " "}),
        ("db_admin_cluster", {"conn": "rw", "action": "rm -rf /"}),
        ("db_admin_cluster", {"conn": "rw", "action": "step_down", "seconds": "depois"}),
        ("db_admin_cluster", {"conn": "rw", "action": "step_down", "seconds": -1}),
    ]:
        result = await call(mcp_server, tool, arguments)
        assert result.isError, f"{tool} should reject absurd arguments"
