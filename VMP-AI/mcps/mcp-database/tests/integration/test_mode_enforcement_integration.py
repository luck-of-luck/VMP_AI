"""Destructive operations against real databases must be denied on read_only/monitor connections.

The barrier under test is the full server path (guard + tools) in front of real adapters:
the write is rejected before touching the database, and the data stays intact.
"""

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_database.adapters.mongodb import MongoAdapter
from mcp_database.adapters.mysql import MySQLAdapter
from mcp_database.adapters.postgres import PostgresAdapter
from mcp_database.audit import AuditLogger
from mcp_database.server import build_server

from .conftest import make_cfg

pytestmark = [pytest.mark.integration, pytest.mark.cross_engine]

SQL_DESTRUCTIVE = [
    "DELETE FROM guarded",
    "UPDATE guarded SET id = 0",
    "ALTER TABLE guarded ADD COLUMN hacked int",
    "DROP TABLE guarded",
    "TRUNCATE TABLE guarded",
]

MONGO_DESTRUCTIVE = [
    {"collection": "guarded", "operation": "deleteMany", "filter": {}},
    {"collection": "guarded", "operation": "updateMany", "filter": {}, "update": {"$set": {"hacked": 1}}},
    {"collection": "guarded", "operation": "dropCollection"},
    {"collection": "guarded", "operation": "createIndex", "keys": {"hacked": 1}},
]


async def call(server, tool, arguments):
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        return await client.call_tool(tool, arguments)


def server_for(uri, mode, tmp_path):
    cfg = make_cfg("target", uri, access_mode=mode)
    return build_server({"target": cfg}, audit=AuditLogger(tmp_path / "audit.log"))


async def assert_all_denied(server, mode, queries):
    for query in queries:
        result = await call(server, "db_write_query", {"conn": "target", "query": query})
        assert result.isError, f"{mode} allowed destructive query: {query}"
        assert mode in result.content[0].text

    for tool, arguments in [
        ("db_admin_kill", {"conn": "target", "target_id": "1"}),
        ("db_admin_maintain", {"conn": "target", "database": "guarded_db", "object": "guarded"}),
        ("db_admin_cluster", {"conn": "target", "action": "promote"}),
        (
            "db_write_search_index",
            {"conn": "target", "database": "guarded_db", "object": "guarded", "action": "drop", "name": "idx"},
        ),
    ]:
        result = await call(server, tool, arguments)
        assert result.isError, f"{mode} allowed {tool}"


@pytest.fixture(scope="module")
async def pg_guarded(pg_uri):
    adapter = PostgresAdapter(make_cfg("seed_pg", pg_uri))
    await adapter.write("DROP TABLE IF EXISTS guarded", None)
    await adapter.write("CREATE TABLE guarded (id int PRIMARY KEY)", None)
    await adapter.write("INSERT INTO guarded VALUES (1), (2), (3)", None)
    yield adapter
    await adapter.write("DROP TABLE IF EXISTS guarded", None)
    await adapter.close()


@pytest.fixture(scope="module")
async def mysql_guarded(mysql_uri):
    adapter = MySQLAdapter(make_cfg("seed_my", mysql_uri))
    await adapter.write("DROP TABLE IF EXISTS guarded", None)
    await adapter.write("CREATE TABLE guarded (id int PRIMARY KEY)", None)
    await adapter.write("INSERT INTO guarded VALUES (1), (2), (3)", None)
    yield adapter
    await adapter.write("DROP TABLE IF EXISTS guarded", None)
    await adapter.close()


@pytest.fixture(scope="module")
async def mongo_guarded(mongo_uri):
    adapter = MongoAdapter(make_cfg("seed_mg", mongo_uri))
    await adapter.write({"collection": "guarded", "operation": "dropCollection"}, None)
    await adapter.write(
        {"collection": "guarded", "operation": "insertMany", "documents": [{"id": i} for i in (1, 2, 3)]}, None
    )
    yield adapter
    await adapter.write({"collection": "guarded", "operation": "dropCollection"}, None)
    await adapter.close()


@pytest.mark.parametrize("mode", ["read_only", "monitor"])
async def test_postgres_denies_destructive_ops(pg_guarded, pg_uri, tmp_path, mode):
    server = server_for(pg_uri, mode, tmp_path)
    await assert_all_denied(server, mode, SQL_DESTRUCTIVE)

    sneaky = await call(server, "db_read_query", {"conn": "target", "query": "DELETE FROM guarded"})
    assert sneaky.isError

    rows = await pg_guarded.read("SELECT count(*) AS n FROM guarded", None, 10)
    assert rows[0]["n"] == 3


@pytest.mark.parametrize("mode", ["read_only", "monitor"])
async def test_mysql_denies_destructive_ops(mysql_guarded, mysql_uri, tmp_path, mode):
    server = server_for(mysql_uri, mode, tmp_path)
    await assert_all_denied(server, mode, SQL_DESTRUCTIVE)

    sneaky = await call(server, "db_read_query", {"conn": "target", "query": "DROP TABLE guarded"})
    assert sneaky.isError

    rows = await mysql_guarded.read("SELECT count(*) AS n FROM guarded", None, 10)
    assert rows[0]["n"] == 3


@pytest.mark.parametrize("mode", ["read_only", "monitor"])
async def test_mongo_denies_destructive_ops(mongo_guarded, mongo_uri, tmp_path, mode):
    server = server_for(mongo_uri, mode, tmp_path)
    await assert_all_denied(server, mode, MONGO_DESTRUCTIVE)

    sneaky = await call(
        server,
        "db_read_query",
        {"conn": "target", "query": {"collection": "guarded", "operation": "deleteMany", "filter": {}}},
    )
    assert sneaky.isError

    rows = await mongo_guarded.read({"collection": "guarded", "operation": "countDocuments", "filter": {}}, None, None)
    assert rows == [{"count": 3}]


PROFILES = {
    "postgres": {
        "guarded": "pg_guarded",
        "uri": "pg_uri",
        "read": "SELECT * FROM guarded ORDER BY id",
        "write": "UPDATE guarded SET id = id WHERE id = 1",
    },
    "mysql": {
        "guarded": "mysql_guarded",
        "uri": "mysql_uri",
        "read": "SELECT * FROM guarded ORDER BY id",
        "write": "UPDATE guarded SET id = id WHERE id = 1",
    },
    "mongodb": {
        "guarded": "mongo_guarded",
        "uri": "mongo_uri",
        "read": {"collection": "guarded", "operation": "find"},
        "write": {
            "collection": "guarded",
            "operation": "updateOne",
            "filter": {"id": 1},
            "update": {"$set": {"id": 1}},
        },
    },
}


@pytest.mark.parametrize("engine", sorted(PROFILES))
@pytest.mark.parametrize("mode", ["read_write", "read_only", "monitor"])
async def test_mode_profile_matrix(engine, mode, request, tmp_path):
    """Each mode on each real engine: schema/perf always work, read stops at monitor, write/admin need read_write."""
    profile = PROFILES[engine]
    request.getfixturevalue(profile["guarded"])
    server = server_for(request.getfixturevalue(profile["uri"]), mode, tmp_path)

    for tool, arguments in [
        ("db_schema_databases", {"conn": "target"}),
        ("db_perf_health", {"conn": "target"}),
    ]:
        result = await call(server, tool, arguments)
        assert not result.isError, f"{engine}/{mode}/{tool}: {result.content[0].text}"

    read = await call(server, "db_read_query", {"conn": "target", "query": profile["read"]})
    if mode == "monitor":
        assert read.isError
        assert "monitor" in read.content[0].text
    else:
        assert not read.isError, f"{engine}/{mode}/read: {read.content[0].text}"

    write = await call(server, "db_write_query", {"conn": "target", "query": profile["write"]})
    if mode == "read_write":
        assert not write.isError, f"{engine}/write: {write.content[0].text}"
        assert json.loads(write.content[0].text)["applied"] is True
    else:
        assert write.isError
        assert mode in write.content[0].text

    if mode != "read_write":
        analyze = await call(server, "db_admin_analyze", {"conn": "target", "database": "guarded_db"})
        assert analyze.isError
        assert mode in analyze.content[0].text


@pytest.mark.parametrize("mode", ["read_only", "monitor"])
async def test_absurd_inputs_on_restricted_modes_stay_clean(pg_guarded, pg_uri, tmp_path, mode):
    """Hostile or nonsense input on a restricted connection is still a clean rejection, never a crash."""
    server = server_for(pg_uri, mode, tmp_path)
    for tool, arguments in [
        ("db_write_query", {"conn": "target", "query": ""}),
        ("db_write_query", {"conn": "target", "query": "DELETE FROM 🐘"}),
        ("db_read_query", {"conn": "target", "query": "DROP TABLE guarded"}),
        ("db_admin_kill", {"conn": "target", "target_id": "🤯"}),
        ("db_admin_cluster", {"conn": "target", "action": "rm -rf /"}),
        (
            "db_read_vector_search",
            {"conn": "target", "database": "public", "object": "guarded", "column": "id", "vector": [0.1]},
        ),
        ("db_read_text_search", {"conn": "target", "database": "public", "object": "guarded", "query": "🤯"}),
    ]:
        result = await call(server, tool, arguments)
        assert result.isError, f"{mode}/{tool} accepted absurd input"
        text = result.content[0].text.lower()
        assert not any(sign in text for sign in ("traceback", "has no attribute", "keyerror"))


async def test_database_modes_scoped_profile(mysql_guarded, mysql_uri, tmp_path):
    """database_modes downgrades one database on a read_write connection: writes there are denied, reads still work."""
    cfg = make_cfg("target", mysql_uri, database_modes={"test": "read_only"})
    server = build_server({"target": cfg}, audit=AuditLogger(tmp_path / "audit.log"))

    denied = await call(
        server, "db_write_query", {"conn": "target", "query": "UPDATE test.guarded SET id = 0 WHERE id = 1"}
    )
    assert denied.isError
    assert "read_only" in denied.content[0].text
    assert "for database 'test'" in denied.content[0].text

    unqualified = await call(
        server, "db_write_query", {"conn": "target", "query": "UPDATE guarded SET id = 0 WHERE id = 1"}
    )
    assert unqualified.isError

    allowed = await call(server, "db_read_query", {"conn": "target", "query": "SELECT * FROM test.guarded"})
    assert not allowed.isError, allowed.content[0].text

    rows = await mysql_guarded.read("SELECT count(*) AS n FROM guarded WHERE id = 0", None, 10)
    assert rows[0]["n"] == 0


async def test_denied_writes_leave_no_audit_entries(pg_uri, tmp_path):
    server = server_for(pg_uri, "read_only", tmp_path)
    result = await call(server, "db_write_query", {"conn": "target", "query": "DELETE FROM guarded"})
    assert result.isError
    assert not (tmp_path / "audit.log").exists()


async def test_monitor_still_allows_diagnosis(pg_guarded, pg_uri, tmp_path):
    server = server_for(pg_uri, "monitor", tmp_path)
    health = await call(server, "db_perf_health", {"conn": "target"})
    assert not health.isError
    payload = json.loads(health.content[0].text)
    assert "connections" in payload


async def test_write_error_does_not_leak_row_values(pg_uri, tmp_path):
    """A unique-violation error crosses the tool boundary with the conflicting value stripped."""
    server = server_for(pg_uri, "read_write", tmp_path)
    seed = PostgresAdapter(make_cfg("seed_leak", pg_uri))
    await seed.write("DROP TABLE IF EXISTS leaky", None)
    await seed.write("CREATE TABLE leaky (email text UNIQUE)", None)
    await seed.write("INSERT INTO leaky VALUES ('secret-leak@x.io')", None)
    try:
        result = await call(
            server, "db_write_query", {"conn": "target", "query": "INSERT INTO leaky VALUES ('secret-leak@x.io')"}
        )
        assert result.isError
        text = result.content[0].text
        assert "secret-leak@x.io" not in text
        assert "already exists" in text
        entry = json.loads((tmp_path / "audit.log").read_text().splitlines()[-1])
        assert "secret-leak@x.io" not in json.dumps(entry)
    finally:
        await seed.write("DROP TABLE IF EXISTS leaky", None)
        await seed.close()
