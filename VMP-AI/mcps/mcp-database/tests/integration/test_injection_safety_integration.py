"""Parser-differential and server-side-code injection are blocked end-to-end against real engines.

Two classes are covered against live databases through the full server path (guard + tools + adapter):
  1. MySQL executable comments (/*! ... */): MySQL runs their contents, sqlglot sees inert comments —
     a write could hide inside one. The guard must reject them before the adapter runs, data untouched.
  2. MongoDB server-side JavaScript ($where/$function/$accumulator): arbitrary code the read allowlist
     must never permit, rejected before reaching mongod.
"""

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_database.adapters import create_adapter
from mcp_database.audit import AuditLogger
from mcp_database.server import build_server

from .conftest import make_cfg

pytestmark = [pytest.mark.integration, pytest.mark.cross_engine]


async def call(server, tool, arguments):
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        return await client.call_tool(tool, arguments)


# Each smuggles a destructive statement inside a MySQL executable comment, wrapped as a "read".
MYSQL_SMUGGLED_READS = [
    "/*!50000 DELETE FROM canary */ SELECT 1",
    "/*! DROP TABLE canary */ SELECT 1",
    "SELECT 1 /*!50000, (SELECT 1 FROM canary) */",
    "/*!\nDELETE FROM canary\n*/ SELECT id FROM canary",
]

# write_ops-bypass attempts: a DDL/DELETE hidden inside an INSERT-shaped statement.
MYSQL_SMUGGLED_WRITES = [
    "INSERT INTO canary VALUES (99) /*!50000; DROP TABLE canary */",
    "/*!50000 DROP TABLE canary */ INSERT INTO canary VALUES (99)",
]


@pytest.fixture
async def mysql_canary(mysql_uri):
    """A 3-row table whose survival proves no smuggled write executed."""
    adapter = create_adapter(make_cfg("seed", mysql_uri))
    await adapter.write("DROP TABLE IF EXISTS canary", None)
    await adapter.write("CREATE TABLE canary (id int)", None)
    await adapter.write("INSERT INTO canary VALUES (1), (2), (3)", None)
    yield adapter
    await adapter.write("DROP TABLE IF EXISTS canary", None)
    await adapter.close()


@pytest.mark.parametrize("query", MYSQL_SMUGGLED_READS)
async def test_mysql_executable_comment_blocked_on_read(mysql_canary, mysql_uri, tmp_path, query):
    server = build_server({"target": make_cfg("target", mysql_uri)}, audit=AuditLogger(tmp_path / "audit.log"))
    result = await call(server, "db_read_query", {"conn": "target", "query": query})
    assert result.isError
    assert "executable comment" in result.content[0].text
    rows = await mysql_canary.read("SELECT count(*) AS n FROM canary", None, 10)
    assert rows[0]["n"] == 3, "a smuggled statement executed despite the guard"


@pytest.mark.parametrize("query", MYSQL_SMUGGLED_WRITES)
async def test_mysql_executable_comment_blocked_on_write(mysql_canary, mysql_uri, tmp_path, query):
    server = build_server({"target": make_cfg("target", mysql_uri)}, audit=AuditLogger(tmp_path / "audit.log"))
    result = await call(server, "db_write_query", {"conn": "target", "query": query})
    assert result.isError
    assert "executable comment" in result.content[0].text
    rows = await mysql_canary.read("SELECT count(*) AS n FROM canary", None, 10)
    assert rows[0]["n"] == 3
    assert not (tmp_path / "audit.log").exists(), "rejected before the adapter, so nothing is audited"


@pytest.mark.parametrize(
    "query",
    [
        "SELECT id FROM canary /* plain block comment */ ORDER BY id",
        "SELECT id FROM canary -- trailing line comment\n",
        "SELECT id FROM canary # mysql hash comment",
    ],
)
async def test_mysql_legitimate_comments_still_work(mysql_canary, mysql_uri, tmp_path, query):
    """The marker check is precise: ordinary comments do not trip it, real reads still run."""
    server = build_server({"target": make_cfg("target", mysql_uri)}, audit=AuditLogger(tmp_path / "audit.log"))
    result = await call(server, "db_read_query", {"conn": "target", "query": query})
    assert not result.isError, result.content[0].text
    assert len(json.loads(result.content[0].text)["rows"]) == 3


MONGO_JS_READS = [
    {"collection": "canary", "operation": "find", "filter": {"$where": "sleep(9000) || true"}},
    {"collection": "canary", "operation": "countDocuments", "filter": {"$where": "this.id > 0"}},
    {
        "collection": "canary",
        "operation": "aggregate",
        "pipeline": [{"$addFields": {"x": {"$function": {"body": "function(){return 1}", "args": [], "lang": "js"}}}}],
    },
]


@pytest.fixture
async def mongo_canary(mongo_uri):
    adapter = create_adapter(make_cfg("seed", mongo_uri))
    await adapter.write({"collection": "canary", "operation": "dropCollection"}, None)
    await adapter.write(
        {"collection": "canary", "operation": "insertMany", "documents": [{"id": i} for i in (1, 2, 3)]}, None
    )
    yield adapter
    await adapter.write({"collection": "canary", "operation": "dropCollection"}, None)
    await adapter.close()


@pytest.mark.parametrize("query", MONGO_JS_READS)
async def test_mongo_server_side_js_blocked(mongo_canary, mongo_uri, tmp_path, query):
    server = build_server({"target": make_cfg("target", mongo_uri)}, audit=AuditLogger(tmp_path / "audit.log"))
    result = await call(server, "db_read_query", {"conn": "target", "query": query})
    assert result.isError
    assert "server-side JavaScript" in result.content[0].text


@pytest.mark.parametrize(
    "filter_expr",
    [
        {"id": {"$gt": 1}},
        {"$expr": {"$gt": ["$id", 1]}},
        {"id": {"$in": [1, 2]}},
    ],
)
async def test_mongo_legitimate_filters_still_run(mongo_canary, mongo_uri, tmp_path, filter_expr):
    """$expr and standard operators are not JS and must keep working against a real mongod."""
    server = build_server({"target": make_cfg("target", mongo_uri)}, audit=AuditLogger(tmp_path / "audit.log"))
    result = await call(
        server,
        "db_read_query",
        {"conn": "target", "query": {"collection": "canary", "operation": "find", "filter": filter_expr}},
    )
    assert not result.isError, result.content[0].text
    assert len(json.loads(result.content[0].text)["rows"]) == 2
