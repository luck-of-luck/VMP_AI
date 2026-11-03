"""Cross-engine parity matrix: every tool is exercised against every real engine.

For each (engine, tool) it asserts two order-independent invariants:
  1. No tool ever *crashes* — an error must be a clean domain message, never a serialization failure,
     an AttributeError, a bad-utf8, etc. (this is what caught the MongoDB ObjectId/bytes bugs).
  2. Every core tool (schema/read/explain/health/write) succeeds on every engine.
Feature-gated tools (top_queries needs an extension, grants needs a privilege, MongoDB has no ANALYZE)
may return a clean guidance error, which is fine — we only forbid crashes and core-path regressions.
"""

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_database.adapters import create_adapter
from mcp_database.audit import AuditLogger
from mcp_database.server import build_server

from .conftest import make_cfg

pytestmark = [pytest.mark.integration, pytest.mark.cross_engine]

TOOLS = [
    "db_schema_connections",
    "db_schema_databases",
    "db_schema_objects",
    "db_schema_describe",
    "db_schema_ddl",
    "db_schema_search",
    "db_schema_relationships",
    "db_schema_users",
    "db_schema_grants",
    "db_schema_search_indexes",
    "db_read_query",
    "db_read_sample",
    "db_read_export",
    "db_read_vector_search",
    "db_read_text_search",
    "db_perf_explain",
    "db_perf_column_stats",
    "db_perf_diagnose",
    "db_perf_top_queries",
    "db_perf_active_ops",
    "db_perf_blocking",
    "db_perf_index_stats",
    "db_perf_table_stats",
    "db_perf_health",
    "db_perf_replication",
    "db_perf_settings",
    "db_perf_logs",
    "db_perf_vector_stats",
    "db_perf_cluster",
    "db_perf_storage",
    "db_perf_tls",
    "db_perf_config_check",
    "db_perf_index_advisor",
    "db_write_query",
    "db_write_search_index",
    "db_admin_analyze",
    "db_admin_maintain",
    "db_admin_kill",
    "db_admin_cluster",
]

# Per-engine schema context: where the seeded object lives and how to read/write it.
CONTEXT = {
    "postgres": {
        "database": "public",
        "object": "matrix_t",
        "read": "SELECT * FROM matrix_t",
        "write": "UPDATE matrix_t SET n = 1 WHERE id = 1",
    },
    "mysql": {
        "database": "test",
        "object": "matrix_t",
        "read": "SELECT * FROM matrix_t",
        "write": "UPDATE matrix_t SET n = 1 WHERE id = 1",
    },
    "mongodb": {
        "database": "test",
        "object": "matrix_t",
        "read": {"collection": "matrix_t", "operation": "find"},
        "write": {
            "collection": "matrix_t",
            "operation": "updateMany",
            "filter": {"id": 1},
            "update": {"$set": {"n": 1}},
        },
    },
    "mariadb": {
        "database": "test",
        "object": "matrix_t",
        "read": "SELECT * FROM matrix_t",
        "write": "UPDATE matrix_t SET n = 1 WHERE id = 1",
    },
    "sqlite": {
        "database": "main",
        "object": "matrix_t",
        "read": "SELECT * FROM matrix_t",
        "write": "UPDATE matrix_t SET n = 1 WHERE id = 1",
    },
    "redis": {
        "database": "0",
        "object": "matrix_t",
        "read": {"command": "HGETALL", "args": ["matrix_t"]},
        "write": {"command": "HSET", "args": ["matrix_t", "n", "1"]},
    },
}

# Core tools that are structurally absent on an engine (clean GuidanceError expected, not a failure).
CORE_EXEMPT = {
    "sqlite": {"db_schema_users"},
    "redis": {"db_schema_ddl", "db_schema_relationships", "db_perf_explain"},
}

# Tools whose data path must work on every engine regardless of extensions/privileges.
CORE_TOOLS = {
    "db_schema_connections",
    "db_schema_databases",
    "db_schema_objects",
    "db_schema_describe",
    "db_schema_ddl",
    "db_schema_search",
    "db_schema_relationships",
    "db_schema_users",
    "db_read_query",
    "db_read_sample",
    "db_read_export",
    "db_perf_explain",
    "db_perf_health",
    "db_write_query",
}

# Substrings that mark an *unhandled* failure (a crash), as opposed to a clean domain error.
CRASH_SIGNS = ("serializ", "utf-8", "utf8", "has no attribute", "traceback", "'nonetype'", "keyerror")

URI_FIXTURE = {
    "postgres": "pg_uri",
    "mysql": "mysql_uri",
    "mariadb": "mariadb_uri",
    "sqlite": "sqlite_uri",
    "mongodb": "mongo_uri",
    "redis": "redis_uri",
}


def tool_args(tool, ctx, tmp_path):
    conn = {"conn": "target"}
    table = {"conn": "target", "database": ctx["database"], "object": ctx["object"]}
    return {
        "db_schema_connections": {},
        "db_schema_databases": conn,
        "db_schema_objects": {"conn": "target", "database": ctx["database"]},
        "db_schema_describe": table,
        "db_schema_ddl": table,
        "db_schema_search": {"conn": "target", "pattern": "matrix"},
        "db_schema_relationships": {"conn": "target", "database": ctx["database"]},
        "db_schema_users": conn,
        "db_schema_grants": conn,
        "db_read_query": {"conn": "target", "query": ctx["read"]},
        "db_read_sample": table,
        "db_read_export": {"conn": "target", "query": ctx["read"], "path": str(tmp_path / "out.json")},
        "db_perf_explain": {"conn": "target", "query": ctx["read"]},
        "db_perf_column_stats": table,
        "db_perf_diagnose": conn,
        "db_perf_top_queries": conn,
        "db_perf_active_ops": conn,
        "db_perf_blocking": conn,
        "db_perf_index_stats": conn,
        "db_perf_table_stats": conn,
        "db_perf_health": conn,
        "db_perf_replication": conn,
        "db_perf_settings": conn,
        "db_perf_logs": conn,
        "db_perf_vector_stats": conn,
        "db_perf_cluster": conn,
        "db_perf_storage": conn,
        "db_perf_tls": conn,
        "db_perf_config_check": conn,
        "db_perf_index_advisor": conn,
        "db_schema_search_indexes": conn,
        "db_read_vector_search": {**table, "column": "n", "vector": [0.1, 0.2], "index": "matrix_vidx"},
        "db_read_text_search": {**table, "query": "hello", "column": "note"},
        "db_write_search_index": {
            **table,
            "action": "create",
            "name": "matrix_sidx",
            "definition": {"column": "note", "columns": ["note"], "mappings": {"dynamic": True}},
        },
        "db_write_query": {"conn": "target", "query": ctx["write"]},
        "db_admin_analyze": table,
        "db_admin_maintain": table,
        "db_admin_kill": {"conn": "target", "target_id": "999999999"},
        "db_admin_cluster": {"conn": "target", "action": "promote"},
    }[tool]


async def _seed(uri, engine):
    adapter = create_adapter(make_cfg("seed", uri))
    try:
        if engine == "mongodb":
            await adapter.write({"collection": "matrix_t", "operation": "dropCollection"}, None)
            await adapter.write(
                {
                    "collection": "matrix_t",
                    "operation": "insertMany",
                    "documents": [{"id": 1, "n": 0, "note": "hello world"}],
                },
                None,
            )
        elif engine == "redis":
            await adapter.write({"command": "DEL", "args": ["matrix_t"]}, None)
            await adapter.write(
                {"command": "HSET", "args": ["matrix_t", "id", "1", "n", "0", "note", "hello world"]}, None
            )
        else:
            await adapter.write("DROP TABLE IF EXISTS matrix_t", None)
            await adapter.write("CREATE TABLE matrix_t (id int PRIMARY KEY, n int, note varchar(100))", None)
            await adapter.write("INSERT INTO matrix_t VALUES (1, 0, 'hello world')", None)
    finally:
        await adapter.close()


async def call(server, tool, arguments):
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        return await client.call_tool(tool, arguments)


@pytest.mark.parametrize("engine", ["postgres", "mysql", "mariadb", "sqlite", "mongodb", "redis"])
async def test_every_tool_reaches_every_engine(engine, request, tmp_path):
    uri = request.getfixturevalue(URI_FIXTURE[engine])
    await _seed(uri, engine)
    server = build_server({"target": make_cfg("target", uri)}, audit=AuditLogger(tmp_path / "audit.log"))
    ctx = CONTEXT[engine]

    for tool in TOOLS:
        result = await call(server, tool, tool_args(tool, ctx, tmp_path))
        if not result.isError:
            continue
        text = result.content[0].text.lower()
        crash = next((sign for sign in CRASH_SIGNS if sign in text), None)
        assert crash is None, f"{engine}/{tool} crashed ({crash!r}): {text}"
        core_failure = tool in CORE_TOOLS and tool not in CORE_EXEMPT.get(engine, set())
        assert not core_failure, f"{engine}/{tool} is a core tool but returned an error: {text}"


async def _seed_export(uri, engine):
    """Create export_t with 3 rows carrying a 'secret' field, so caps and masking are observable."""
    adapter = create_adapter(make_cfg("seed", uri))
    docs = [{"id": i, "secret": f"s{i}"} for i in (1, 2, 3)]
    try:
        if engine == "mongodb":
            await adapter.write({"collection": "export_t", "operation": "dropCollection"}, None)
            await adapter.write({"collection": "export_t", "operation": "insertMany", "documents": docs}, None)
        else:
            await adapter.write("DROP TABLE IF EXISTS export_t", None)
            await adapter.write("CREATE TABLE export_t (id int PRIMARY KEY, secret varchar(10))", None)
            await adapter.write("INSERT INTO export_t VALUES (1, 's1'), (2, 's2'), (3, 's3')", None)
    finally:
        await adapter.close()


@pytest.mark.parametrize("engine", ["postgres", "mysql", "mariadb", "sqlite", "mongodb"])
async def test_export_caps_masks_and_csv_on_every_engine(engine, request, tmp_path):
    """db_read_export on a real engine caps at export_max_rows, masks redact_fields, and audits both formats."""
    uri = request.getfixturevalue(URI_FIXTURE[engine])
    await _seed_export(uri, engine)
    cfg = make_cfg("target", uri, export_max_rows=2, redact_fields=["secret"])
    server = build_server({"target": cfg}, audit=AuditLogger(tmp_path / "audit.log"))
    query = (
        {"collection": "export_t", "operation": "find", "sort": {"id": 1}}
        if engine == "mongodb"
        else "SELECT * FROM export_t ORDER BY id"
    )

    json_path = tmp_path / "out.json"
    result = await call(server, "db_read_export", {"conn": "target", "query": query, "path": str(json_path)})
    assert not result.isError, result.content[0].text
    outcome = json.loads(result.content[0].text)
    assert outcome["row_count"] == 2
    assert outcome["truncated"] is True
    exported = json.loads(json_path.read_text())
    assert len(exported) == 2
    assert all(row["secret"] == "***" for row in exported)

    csv_path = tmp_path / "out.csv"
    result = await call(
        server, "db_read_export", {"conn": "target", "query": query, "path": str(csv_path), "format": "csv"}
    )
    assert not result.isError, result.content[0].text
    header, *lines = csv_path.read_text().strip().splitlines()
    assert "secret" in header
    assert len(lines) == 2
    assert all("s1" not in line and "s2" not in line for line in lines)

    audit_entries = [json.loads(line) for line in (tmp_path / "audit.log").read_text().splitlines()]
    export_entries = [e for e in audit_entries if e["tool"] == "db_read_export"]
    assert len(export_entries) == 2
    assert export_entries[0]["path"] == str(json_path)
    assert export_entries[1]["format"] == "csv"
