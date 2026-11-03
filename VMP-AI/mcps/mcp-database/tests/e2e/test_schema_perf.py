"""db_schema_ and db_perf_ tools, including the monitor-mode barriers."""

import pytest

from mcp_database.audit import AuditLogger
from mcp_database.config import parse_connection
from mcp_database.server import build_server

from .helpers import FakeAdapter, call, payload


async def test_every_remaining_schema_tool_happy(mcp_server):
    for tool, arguments in [
        ("db_schema_databases", {"conn": "ro"}),
        ("db_schema_objects", {"conn": "ro", "database": "public"}),
        ("db_schema_objects", {"conn": "ro", "database": "public", "object_type": "table"}),
        ("db_schema_ddl", {"conn": "ro", "database": "public", "object": "users"}),
        ("db_schema_relationships", {"conn": "ro", "database": "public"}),
        ("db_schema_users", {"conn": "ro"}),
        ("db_schema_users", {"conn": "ro", "user": "app"}),
        ("db_schema_grants", {"conn": "ro"}),
        ("db_schema_grants", {"conn": "ro", "user": "app", "object": "users"}),
        ("db_schema_search", {"conn": "ro", "pattern": "user"}),
        ("db_schema_describe", {"conn": "ro", "database": "public", "object": "users"}),
    ]:
        result = await call(mcp_server, tool, arguments)
        assert not result.isError, f"{tool} failed: {result.content[0].text}"


async def test_schema_search_absurd_inputs(mcp_server):
    empty = await call(mcp_server, "db_schema_search", {"conn": "ro", "pattern": "   "})
    assert empty.isError
    bad_scope = await call(mcp_server, "db_schema_search", {"conn": "ro", "pattern": "user", "scope": "planets"})
    assert bad_scope.isError


async def test_schema_connections_reports_modes(mcp_server):
    data = payload(await call(mcp_server, "db_schema_connections", {}))
    by_name = {c["name"]: c for c in data["connections"]}
    assert by_name["mon"]["access_mode"] == "monitor"
    assert by_name["limited"]["write_ops"] == ["insert"]
    assert by_name["structure"]["redact_fields"] == ["*"]
    assert all(c["status"] == "ok" for c in data["connections"])


async def test_schema_connections_reports_database_modes(mcp_server):
    data = payload(await call(mcp_server, "db_schema_connections", {}))
    by_name = {c["name"]: c for c in data["connections"]}
    assert by_name["scoped"]["database_modes"] == {"x": "read_only"}


async def test_schema_connections_sad_unreachable(monkeypatch, tmp_path):
    class DeadAdapter(FakeAdapter):
        async def ping(self):
            raise ConnectionError("connect to postgresql://u:hunter2@h:5432/db refused")

    monkeypatch.setattr("mcp_database.tools.context.create_adapter", lambda cfg: DeadAdapter(cfg))
    srv = build_server(
        {"down": parse_connection("down", {"uri": "postgresql://u@h/db"})}, audit=AuditLogger(tmp_path / "a.log")
    )
    data = payload(await call(srv, "db_schema_connections", {}))
    entry = data["connections"][0]
    assert entry["status"] == "unreachable"
    assert "hunter2" not in entry["error"]


async def test_monitor_blocks_data_reads_but_allows_perf(mcp_server):
    denied = await call(mcp_server, "db_read_query", {"conn": "mon", "query": "SELECT 1"})
    assert denied.isError
    assert "monitor" in denied.content[0].text

    denied_sample = await call(mcp_server, "db_read_sample", {"conn": "mon", "database": "public", "object": "users"})
    assert denied_sample.isError

    allowed = await call(mcp_server, "db_perf_health", {"conn": "mon"})
    assert not allowed.isError

    describe = payload(
        await call(mcp_server, "db_schema_describe", {"conn": "mon", "database": "public", "object": "users"})
    )
    assert describe["sampled"] is False


async def test_schema_tools_denied_only_for_unsafe_classes(mcp_server):
    for tool, arguments in [
        ("db_schema_databases", {"conn": "mon"}),
        ("db_perf_health", {"conn": "mon"}),
    ]:
        result = await call(mcp_server, tool, arguments)
        assert not result.isError, f"{tool} should be allowed in monitor mode"


async def test_perf_tools_happy(mcp_server):
    for tool, arguments in [
        ("db_perf_top_queries", {"conn": "mon"}),
        ("db_perf_active_ops", {"conn": "mon"}),
        ("db_perf_blocking", {"conn": "mon"}),
        ("db_perf_index_stats", {"conn": "mon"}),
        ("db_perf_table_stats", {"conn": "mon"}),
        ("db_perf_replication", {"conn": "mon"}),
        ("db_perf_settings", {"conn": "mon"}),
        ("db_perf_logs", {"conn": "mon"}),
        ("db_perf_explain", {"conn": "mon", "query": "SELECT 1"}),
        ("db_perf_diagnose", {"conn": "mon"}),
    ]:
        result = await call(mcp_server, tool, arguments)
        assert not result.isError, f"{tool} failed: {result.content[0].text}"


async def test_diagnose_aggregates_sections_and_findings(mcp_server):
    """db_perf_diagnose returns every section plus a findings list and next-step suggestions in one call."""
    data = payload(await call(mcp_server, "db_perf_diagnose", {"conn": "mon"}))
    assert set(data["sections"]) == {"health", "active_ops", "blocking", "top_queries"}
    assert isinstance(data["findings"], list) and data["findings"]
    assert isinstance(data["next"], list)


async def test_perf_active_ops_absurd_duration(mcp_server):
    result = await call(mcp_server, "db_perf_active_ops", {"conn": "mon", "min_duration_ms": -10})
    assert result.isError


async def test_column_stats_masks_redacted_columns(mcp_server):
    """MCV lists carry real data: a redacted column's values are masked while other columns pass through."""
    data = payload(
        await call(mcp_server, "db_perf_column_stats", {"conn": "masked", "database": "d", "object": "users"})
    )
    by_name = {c["column"]: c for c in data["columns"]}
    assert by_name["email"]["most_common_vals"] == "***"
    assert by_name["id"]["most_common_vals"] is None


async def test_connections_expose_capabilities(mcp_server):
    """db_schema_connections lists each connection's capabilities so the agent can plan without trial and error."""
    data = payload(await call(mcp_server, "db_schema_connections", {}))
    by_name = {c["name"]: c for c in data["connections"]}
    assert "capabilities" in by_name["rw"]
    assert isinstance(by_name["rw"]["capabilities"], list)


async def test_explain_forwards_hypothetical_indexes(mcp_server):
    """The hypothetical_indexes parameter reaches the adapter untouched (real behavior is engine-side)."""
    data = payload(
        await call(
            mcp_server,
            "db_perf_explain",
            {"conn": "rw", "query": "SELECT 1", "hypothetical_indexes": ["CREATE INDEX ON users(email)"]},
        )
    )
    assert data["hypothetical_indexes"] == ["CREATE INDEX ON users(email)"]


@pytest.mark.parametrize("failing", [["replication"], ["health"], ["replication", "health"]])
async def test_perf_cluster_reports_unavailable_sections(mcp_server, monkeypatch, failing):
    """A section that needs a missing privilege becomes {'unavailable': ...} instead of failing the call."""
    from mcp_database.errors import GuidanceError

    async def boom(self):
        raise GuidanceError("requires the clusterMonitor role")

    for method in failing:
        monkeypatch.setattr(FakeAdapter, method, boom)
    result = await call(mcp_server, "db_perf_cluster", {"conn": "rw"})
    assert not result.isError, result.content[0].text
    body = payload(result)
    for method in failing:
        assert "clusterMonitor" in body["sections"][method]["unavailable"]
    assert isinstance(body["findings"], list) and body["findings"]
