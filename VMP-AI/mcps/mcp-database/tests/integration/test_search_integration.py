"""Vector/text search and cluster actions against real engines.

pgvector happy paths run only when PG_IMAGE ships the extension (pgvector/pgvector:*); the stock image
asserts the GuidanceError contract instead. Atlas Search happy paths run only when MONGO_IMAGE is
mongodb/mongodb-atlas-local (bundled mongot); plain mongod asserts the guidance contract.
"""

import asyncio
import json
import time

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_database.adapters import create_adapter
from mcp_database.audit import AuditLogger
from mcp_database.server import build_server

from .conftest import MONGO_IMAGE, make_cfg

pytestmark = pytest.mark.integration


async def call(server, tool, arguments):
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        return await client.call_tool(tool, arguments)


def payload(result):
    return json.loads(result.content[0].text)


def make_server(uri, tmp_path):
    return build_server({"target": make_cfg("target", uri)}, audit=AuditLogger(tmp_path / "audit.log"))


async def _has_pgvector(uri):
    adapter = create_adapter(make_cfg("probe", uri))
    try:
        await adapter.write("CREATE EXTENSION IF NOT EXISTS vector", None)
        return True
    except Exception:
        return False
    finally:
        await adapter.close()


async def _seed_sql(uri, statements):
    adapter = create_adapter(make_cfg("seed", uri))
    try:
        for statement in statements:
            await adapter.write(statement, None)
    finally:
        await adapter.close()


async def test_pgvector_end_to_end(pg_uri, tmp_path):
    """Index creation, all four metrics, schema listing and stats against a real pgvector."""
    if not await _has_pgvector(pg_uri):
        pytest.skip("PG_IMAGE has no pgvector; run with PG_IMAGE=pgvector/pgvector:pg17")
    await _seed_sql(
        pg_uri,
        [
            "DROP TABLE IF EXISTS vec_t",
            "CREATE TABLE vec_t (id int PRIMARY KEY, note text, emb vector(3))",
            "INSERT INTO vec_t VALUES (1, 'alpha', '[1,0,0]'), (2, 'beta', '[0,1,0]'), (3, 'gamma', '[0,0,1]')",
        ],
    )
    server = make_server(pg_uri, tmp_path)

    result = await call(
        server,
        "db_write_search_index",
        {
            "conn": "target",
            "database": "public",
            "object": "vec_t",
            "action": "create",
            "name": "vec_t_emb_idx",
            "definition": {"column": "emb", "method": "hnsw", "metric": "l2", "options": {"m": 8}},
        },
    )
    assert not result.isError, result.content[0].text

    for metric in ("cosine", "l2", "inner_product", "l1"):
        result = await call(
            server,
            "db_read_vector_search",
            {
                "conn": "target",
                "database": "public",
                "object": "vec_t",
                "column": "emb",
                "vector": [1.0, 0.05, 0.0],
                "metric": metric,
                "row_limit": 2,
            },
        )
        assert not result.isError, f"{metric}: {result.content[0].text}"
        rows = payload(result)["rows"]
        assert rows and "distance" in rows[0]
        assert "emb" not in rows[0], "the vector column must not be echoed back"
        assert rows[0]["id"] == 1, f"{metric} should rank the nearest vector first"

    result = await call(server, "db_schema_search_indexes", {"conn": "target", "database": "public"})
    assert not result.isError
    indexes = payload(result)["indexes"]
    entry = next(i for i in indexes if i["index"] == "vec_t_emb_idx")
    assert entry["type"] == "vector"
    assert entry["metric"] == "l2"
    assert entry["dimensions"] == 3

    result = await call(server, "db_perf_vector_stats", {"conn": "target", "database": "public"})
    assert not result.isError
    sections = payload(result)["sections"]
    assert sections["extension"]["name"] == "vector"
    assert any(c["column"] == "emb" for c in sections["vector_columns"])

    result = await call(
        server,
        "db_write_search_index",
        {"conn": "target", "database": "public", "object": "vec_t", "action": "drop", "name": "vec_t_emb_idx"},
    )
    assert not result.isError

    audit_tools = [json.loads(line)["tool"] for line in (tmp_path / "audit.log").read_text().splitlines()]
    assert audit_tools.count("db_write_search_index") == 2


async def test_pgvector_missing_extension_guides(pg_uri, tmp_path):
    """Without the extension, vector tools answer with the enabling command, not a generic error."""
    if await _has_pgvector(pg_uri):
        pytest.skip("PG_IMAGE ships pgvector; the guidance path needs the stock image")
    server = make_server(pg_uri, tmp_path)
    for tool, args in [
        ("db_read_vector_search", {"database": "public", "object": "t", "column": "e", "vector": [0.1]}),
        ("db_perf_vector_stats", {}),
    ]:
        result = await call(server, tool, {"conn": "target", **args})
        assert result.isError
        assert "CREATE EXTENSION vector" in result.content[0].text


async def test_pg_text_search_ranks_and_survives_injection(pg_uri, tmp_path):
    """Native FTS works on any PostgreSQL image; a malicious regconfig fails cleanly without executing."""
    await _seed_sql(
        pg_uri,
        [
            "DROP TABLE IF EXISTS txt_t",
            "CREATE TABLE txt_t (id int PRIMARY KEY, body text)",
            "INSERT INTO txt_t VALUES (1, 'full text search in postgres'), (2, 'vector similarity search')",
        ],
    )
    server = make_server(pg_uri, tmp_path)
    result = await call(
        server,
        "db_read_text_search",
        {
            "conn": "target",
            "database": "public",
            "object": "txt_t",
            "query": "full text",
            "column": "body",
            "language": "english",
        },
    )
    assert not result.isError, result.content[0].text
    rows = payload(result)["rows"]
    assert rows[0]["id"] == 1
    assert "rank" in rows[0]

    evil = await call(
        server,
        "db_read_text_search",
        {
            "conn": "target",
            "database": "public",
            "object": "txt_t",
            "query": "x",
            "column": "body",
            "language": "english'; DROP TABLE txt_t;--",
        },
    )
    assert evil.isError
    survivor = await call(server, "db_read_query", {"conn": "target", "query": "SELECT count(*) AS n FROM txt_t"})
    assert not survivor.isError, "the injection attempt must not have dropped the table"


async def test_mysql_fulltext_end_to_end(mysql_uri, tmp_path):
    """Search without an index guides to index creation; after creating it, MATCH ranks results."""
    await _seed_sql(
        mysql_uri,
        [
            "DROP TABLE IF EXISTS ft_t",
            "CREATE TABLE ft_t (id int PRIMARY KEY, body text)",
            "INSERT INTO ft_t VALUES (1, 'wireless mouse with usb receiver'), (2, 'mechanical keyboard')",
        ],
    )
    server = make_server(mysql_uri, tmp_path)
    search_args = {
        "conn": "target",
        "database": "test",
        "object": "ft_t",
        "query": "wireless mouse",
        "column": "body",
    }

    before = await call(server, "db_read_text_search", search_args)
    assert before.isError
    assert "db_write_search_index" in before.content[0].text

    created = await call(
        server,
        "db_write_search_index",
        {
            "conn": "target",
            "database": "test",
            "object": "ft_t",
            "action": "create",
            "name": "ft_t_body_idx",
            "definition": {"columns": ["body"]},
        },
    )
    assert not created.isError, created.content[0].text

    listed = await call(server, "db_schema_search_indexes", {"conn": "target", "database": "test"})
    assert any(i["index"] == "ft_t_body_idx" for i in payload(listed)["indexes"])

    after = await call(server, "db_read_text_search", search_args)
    assert not after.isError, after.content[0].text
    rows = payload(after)["rows"]
    assert rows[0]["id"] == 1
    assert rows[0]["score"] > 0

    dropped = await call(
        server,
        "db_write_search_index",
        {"conn": "target", "database": "test", "object": "ft_t", "action": "drop", "name": "ft_t_body_idx"},
    )
    assert not dropped.isError


async def test_mongo_plain_search_guides_to_atlas(mongo_uri, tmp_path):
    """Plain mongod has no mongot: every search surface answers with Atlas guidance, never a crash."""
    if "atlas-local" in MONGO_IMAGE:
        pytest.skip("guidance paths need a stock mongo image; this MONGO_IMAGE ships mongot")
    server = make_server(mongo_uri, tmp_path)
    cases = [
        (
            "db_read_vector_search",
            {"database": "test", "object": "docs", "column": "emb", "vector": [0.1], "index": "v"},
        ),
        ("db_read_text_search", {"database": "test", "object": "docs", "query": "hello"}),
        ("db_schema_search_indexes", {"database": "test", "object": "docs"}),
    ]
    for tool, args in cases:
        result = await call(server, tool, {"conn": "target", **args})
        assert result.isError, f"{tool} should fail on plain mongod"
        assert "Atlas" in result.content[0].text, f"{tool}: {result.content[0].text}"


async def test_cluster_actions_fail_cleanly_on_single_nodes(pg_uri, mysql_uri, mongo_uri, tmp_path):
    """Single-node servers reject cluster actions with a clear role explanation, before doing anything."""
    pg = make_server(pg_uri, tmp_path / "pg")
    result = await call(pg, "db_admin_cluster", {"conn": "target", "action": "promote"})
    assert result.isError
    assert "is a primary" in result.content[0].text

    mysql = make_server(mysql_uri, tmp_path / "mysql")
    result = await call(mysql, "db_admin_cluster", {"conn": "target", "action": "stop_replica"})
    assert result.isError
    assert "no replication source" in result.content[0].text

    if "atlas-local" not in MONGO_IMAGE:  # atlas-local runs a single-node replica set, not a standalone
        mongo = make_server(mongo_uri, tmp_path / "mongo")
        result = await call(mongo, "db_admin_cluster", {"conn": "target", "action": "step_down"})
        assert result.isError
        assert "standalone" in result.content[0].text


async def test_perf_cluster_summarizes_on_every_engine(pg_uri, mysql_uri, mongo_uri, tmp_path):
    """db_perf_cluster always returns sections+findings, even on standalone servers."""
    for name, uri in [("pg", pg_uri), ("mysql", mysql_uri), ("mongo", mongo_uri)]:
        server = make_server(uri, tmp_path / name)
        result = await call(server, "db_perf_cluster", {"conn": "target"})
        assert not result.isError, f"{name}: {result.content[0].text}"
        body = payload(result)
        assert body["findings"], name
        assert "replication" in body["sections"], name


@pytest.fixture(scope="session")
def atlas_uri():
    if "atlas-local" not in MONGO_IMAGE:
        pytest.skip("Atlas Search happy paths need MONGO_IMAGE=mongodb/mongodb-atlas-local")
    from testcontainers.core.container import DockerContainer

    container = DockerContainer(MONGO_IMAGE).with_exposed_ports(27017)
    container.start()
    try:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(27017)
        yield f"mongodb://{host}:{port}/test?directConnection=true"
    finally:
        container.stop()


async def _wait_for_atlas(uri, deadline_s=300):
    """Wait until mongod answers and the search index management service (mongot) accepts a real create."""
    from pymongo import AsyncMongoClient
    from pymongo.operations import SearchIndexModel

    client = AsyncMongoClient(uri, serverSelectionTimeoutMS=2000)
    deadline = time.monotonic() + deadline_s
    while True:
        try:
            await client.admin.command("ping")
            probe = client["test"]["readiness_probe"]
            await probe.insert_one({"x": 1})
            await probe.create_search_index(
                SearchIndexModel(definition={"mappings": {"dynamic": True}}, name="probe_idx")
            )
            await client["test"].drop_collection("readiness_probe")
            break
        except Exception:
            if time.monotonic() > deadline:
                raise
            await asyncio.sleep(3)
    await client.close()


async def _wait_queryable(server, names, deadline_s=240):
    """Poll db_schema_search_indexes until every named index reports queryable=true."""
    deadline = time.monotonic() + deadline_s
    while True:
        result = await call(server, "db_schema_search_indexes", {"conn": "target", "database": "test"})
        if not result.isError:
            indexes = {i["index"]: i for i in payload(result)["indexes"]}
            if all(name in indexes and indexes[name].get("queryable") for name in names):
                return
        if time.monotonic() > deadline:
            raise AssertionError(f"search indexes {names} never became queryable: {result.content[0].text}")
        await asyncio.sleep(3)


async def _atlas_write_with_retry(coro_factory, deadline_s=120):
    """Retry a write while atlas-local's single-node replica set is still settling.

    The image bounces replication during mongot setup, surfacing as ShutdownInProgress (code 91) /
    RetryableWriteError even after the readiness probe passed — pymongo's single auto-retry isn't enough.
    """
    from pymongo.errors import AutoReconnect, BulkWriteError, ConnectionFailure, OperationFailure

    def transient(exc):
        if isinstance(exc, AutoReconnect | ConnectionFailure):
            return True
        details = getattr(exc, "details", None) or {}
        wce = list(details.get("writeConcernErrors") or [])
        if isinstance(details.get("writeConcernError"), dict):
            wce.append(details["writeConcernError"])
        if getattr(exc, "code", None) == 91 or any((e or {}).get("code") == 91 for e in wce):
            return True
        try:
            return bool(exc.has_error_label("RetryableWriteError"))
        except Exception:
            return False

    deadline = time.monotonic() + deadline_s
    while True:
        try:
            return await coro_factory()
        except (AutoReconnect, ConnectionFailure, BulkWriteError, OperationFailure) as exc:
            if not transient(exc) or time.monotonic() > deadline:
                raise
            await asyncio.sleep(2)


async def _atlas_index_with_retry(server, args, deadline_s=120):
    """Retry a search-index create while mongot is still bouncing after the readiness probe.

    Same window as _atlas_write_with_retry: the probe proves mongot answered once, but the image
    restarts it during setup, so the adapter reports the connection failure as Atlas guidance.
    """
    deadline = time.monotonic() + deadline_s
    while True:
        result = await call(server, "db_write_search_index", args)
        if not result.isError or time.monotonic() > deadline:
            return result
        if "Search Index Management" not in result.content[0].text:
            return result
        await asyncio.sleep(3)


async def test_atlas_vector_and_text_end_to_end(atlas_uri, tmp_path):
    """$vectorSearch and $search happy paths against mongodb-atlas-local (real mongot)."""
    await _wait_for_atlas(atlas_uri)
    adapter = create_adapter(make_cfg("seed", atlas_uri))

    async def seed():
        # drop + insert as one idempotent unit so a mid-seed retry re-drops before re-inserting.
        await adapter.write({"collection": "docs", "operation": "dropCollection"}, None)
        await adapter.write(
            {
                "collection": "docs",
                "operation": "insertMany",
                "documents": [
                    {"id": 1, "note": "alpha article about postgres", "emb": [1.0, 0.0, 0.0]},
                    {"id": 2, "note": "beta article about mysql", "emb": [0.0, 1.0, 0.0]},
                    {"id": 3, "note": "gamma article about mongodb", "emb": [0.0, 0.0, 1.0]},
                ],
            },
            None,
        )

    try:
        await _atlas_write_with_retry(seed)
    finally:
        await adapter.close()
    server = make_server(atlas_uri, tmp_path)

    created = await _atlas_index_with_retry(
        server,
        {
            "conn": "target",
            "database": "test",
            "object": "docs",
            "action": "create",
            "name": "vec_idx",
            "definition": {"fields": [{"type": "vector", "path": "emb", "numDimensions": 3, "similarity": "cosine"}]},
        },
    )
    assert not created.isError, created.content[0].text
    created = await _atlas_index_with_retry(
        server,
        {
            "conn": "target",
            "database": "test",
            "object": "docs",
            "action": "create",
            "name": "default",
            "definition": {"mappings": {"dynamic": True}},
        },
    )
    assert not created.isError, created.content[0].text

    await _wait_queryable(server, ["vec_idx", "default"])

    result = await call(
        server,
        "db_read_vector_search",
        {
            "conn": "target",
            "database": "test",
            "object": "docs",
            "column": "emb",
            "vector": [1.0, 0.1, 0.0],
            "index": "vec_idx",
            "row_limit": 2,
        },
    )
    assert not result.isError, result.content[0].text
    rows = payload(result)["rows"]
    assert rows and rows[0]["id"] == 1
    assert "_score" in rows[0]
    assert "emb" not in rows[0]

    result = await call(
        server,
        "db_read_text_search",
        {"conn": "target", "database": "test", "object": "docs", "query": "alpha"},
    )
    assert not result.isError, result.content[0].text
    rows = payload(result)["rows"]
    assert rows and rows[0]["id"] == 1

    result = await call(server, "db_perf_vector_stats", {"conn": "target", "database": "test"})
    assert not result.isError
    assert payload(result)["sections"]["vector_indexes"]


@pytest.mark.parametrize("language", ["simple", "english", "portuguese"])
async def test_pg_text_search_language_variants(pg_uri, tmp_path, language):
    """Every stock regconfig works as a bound language; results stay ranked."""
    await _seed_sql(
        pg_uri,
        [
            "DROP TABLE IF EXISTS lang_t",
            "CREATE TABLE lang_t (id int PRIMARY KEY, body text)",
            "INSERT INTO lang_t VALUES (1, 'searching databases quickly'), (2, 'unrelated content')",
        ],
    )
    server = make_server(pg_uri, tmp_path)
    result = await call(
        server,
        "db_read_text_search",
        {
            "conn": "target",
            "database": "public",
            "object": "lang_t",
            "query": "searching databases",
            "column": "body",
            "language": language,
        },
    )
    assert not result.isError, f"{language}: {result.content[0].text}"
    rows = payload(result)["rows"]
    assert rows and rows[0]["id"] == 1


@pytest.mark.parametrize(
    ("query", "expected_ids"),
    [
        ("wireless mouse", [1]),
        ("mechanical keyboard", [2]),
        ("quantum blender", []),
    ],
)
async def test_mysql_fulltext_query_variants(mysql_uri, tmp_path, query, expected_ids):
    """MATCH ranks the right row for each phrase and returns empty (not an error) on no hits."""
    await _seed_sql(
        mysql_uri,
        [
            "DROP TABLE IF EXISTS ftq_t",
            "CREATE TABLE ftq_t (id int PRIMARY KEY, body text)",
            "INSERT INTO ftq_t VALUES (1, 'wireless mouse with usb receiver'), (2, 'mechanical keyboard switches')",
            "CREATE FULLTEXT INDEX ftq_idx ON ftq_t (body)",
        ],
    )
    server = make_server(mysql_uri, tmp_path)
    result = await call(
        server,
        "db_read_text_search",
        {"conn": "target", "database": "test", "object": "ftq_t", "query": query, "column": "body"},
    )
    assert not result.isError, result.content[0].text
    assert [row["id"] for row in payload(result)["rows"]] == expected_ids


@pytest.mark.parametrize(
    ("uri_fixture", "action", "expected"),
    [
        ("pg_uri", "step_down", "promote"),
        ("pg_uri", "start_replica", "promote"),
        ("pg_uri", "freeze", "promote"),
        ("mysql_uri", "promote", "start_replica"),
        ("mysql_uri", "step_down", "start_replica"),
        ("mysql_uri", "freeze", "start_replica"),
    ],
)
async def test_cluster_foreign_actions_name_the_engines_own(uri_fixture, action, expected, request, tmp_path):
    """Asking one engine for another engine's action returns guidance naming what this engine supports."""
    server = make_server(request.getfixturevalue(uri_fixture), tmp_path)
    result = await call(server, "db_admin_cluster", {"conn": "target", "action": action})
    assert result.isError
    assert expected in result.content[0].text
