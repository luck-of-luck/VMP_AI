import pytest

from mcp_database.adapters.mongodb import MongoAdapter
from mcp_database.errors import GuidanceError, QueryValidationError

from .conftest import make_cfg

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
async def adapter(mongo_uri):
    instance = MongoAdapter(make_cfg("mg", mongo_uri))
    yield instance
    await instance.close()


@pytest.fixture(scope="module", autouse=True)
async def seed(adapter):
    await adapter.write(
        {
            "collection": "users",
            "operation": "insertMany",
            "documents": [
                {"name": "Ana", "email": "ana@x.io", "age": 30},
                {"name": "Bob", "email": "bob@x.io", "age": 41},
            ],
        },
        None,
    )
    await adapter.write(
        {"collection": "users", "operation": "createIndex", "keys": {"email": 1}, "options": {"unique": True}},
        None,
    )


async def test_ping_and_databases(adapter):
    await adapter.ping()
    databases = [d["database"] for d in await adapter.list_databases()]
    assert "test" in databases


async def test_objects_and_describe(adapter):
    objects = await adapter.list_objects("test")
    users = next(o for o in objects if o["name"] == "users")
    assert users["type"] == "collection"
    assert users["approx_rows"] == 2

    with pytest.raises(QueryValidationError):
        await adapter.list_objects("test", "spaceship")

    described = await adapter.describe_object("test", "users")
    field_names = {f["name"] for f in described["fields"]}
    assert {"name", "email", "age"} <= field_names
    assert any(i["name"] == "email_1" for i in described["indexes"])

    no_sample = await adapter.describe_object("test", "users", sample=False)
    assert no_sample["fields"] == []
    assert "note" in no_sample


async def test_ddl_and_search_and_relationships(adapter):
    ddl = await adapter.get_ddl("test", "users")
    assert ddl["commands"][0]["create"] == "users"
    assert any("createIndexes" in c for c in ddl["commands"])

    with pytest.raises(QueryValidationError, match="not found"):
        await adapter.get_ddl("test", "ghost")

    found = await adapter.search("use")
    assert any(o["name"] == "users" for o in found["objects"])

    relationships = await adapter.relationships("test")
    assert relationships["relationships"] == []
    assert "foreign keys" in relationships["note"]


async def test_users_and_grants(adapter):
    users = await adapter.users()
    assert any(u["user"] == "test" for u in users)
    grants = await adapter.grants("test")
    assert grants and "roles" in grants[0]


async def test_read_operations(adapter):
    rows = await adapter.read({"collection": "users", "operation": "find", "filter": {"age": {"$gt": 35}}}, None, 10)
    assert len(rows) == 1 and rows[0]["name"] == "Bob"

    sorted_rows = await adapter.read({"collection": "users", "operation": "find", "sort": {"age": -1}}, None, 10)
    assert sorted_rows[0]["name"] == "Bob"

    aggregated = await adapter.read(
        {
            "collection": "users",
            "operation": "aggregate",
            "pipeline": [{"$group": {"_id": None, "avg_age": {"$avg": "$age"}}}],
        },
        None,
        10,
    )
    assert aggregated[0]["avg_age"] == 35.5

    count = await adapter.read({"collection": "users", "operation": "countDocuments"}, None, None)
    assert count == [{"count": 2}]

    distinct = await adapter.read({"collection": "users", "operation": "distinct", "key": "name"}, None, None)
    assert {d["value"] for d in distinct} == {"Ana", "Bob"}

    indexes = await adapter.read({"collection": "users", "operation": "listIndexes"}, None, None)
    assert any(i["name"] == "email_1" for i in indexes)


async def test_read_requires_database_when_uri_has_none(mongo_uri):
    base = mongo_uri.split("/test?")[0] + "/?authSource=admin"
    bare = MongoAdapter(make_cfg("bare", base))
    try:
        with pytest.raises(QueryValidationError, match="database"):
            await bare.read({"collection": "users", "operation": "find"}, None, 10)
        rows = await bare.read({"collection": "users", "operation": "find", "database": "test"}, None, 10)
        assert len(rows) == 2
    finally:
        await bare.close()


async def test_sample_and_explain(adapter):
    assert len(await adapter.sample("test", "users", 1)) == 1

    plan = await adapter.explain({"collection": "users", "operation": "find", "filter": {"email": "ana@x.io"}})
    assert "queryPlanner" in plan["plan"]

    with pytest.raises(QueryValidationError, match="explain supports"):
        await adapter.explain({"collection": "users", "operation": "listIndexes"})


async def test_top_queries_profiler_off_then_on(adapter):
    with pytest.raises(GuidanceError, match="setProfilingLevel"):
        await adapter.top_queries("total_time", 5, "test")

    db = adapter._db("test")
    await db.command({"profile": 2})
    try:
        await adapter.read({"collection": "users", "operation": "find"}, None, 10)
        rows = await adapter.top_queries("total_time", 5, "test")
        assert rows and "millis" in rows[0]
    finally:
        await db.command({"profile": 0})


async def test_perf_suite(adapter):
    assert isinstance(await adapter.active_ops(0), list)
    assert isinstance(await adapter.blocking(), list)

    index_stats = await adapter.index_stats("test")
    assert any(i["index"] == "email_1" for i in index_stats["indexes"])

    table_stats = await adapter.table_stats("test")
    assert any(t["collection"] == "users" for t in table_stats)

    health = await adapter.health()
    assert health["connections"]["current"] >= 1

    settings = await adapter.settings("wiredTiger")
    assert isinstance(settings, list)

    logs = await adapter.logs(limit=5)
    assert logs and "line" in logs[0]


async def test_replication_standalone(adapter):
    replication = await adapter.replication()
    assert replication["role"] == "standalone"


async def test_write_cycle(adapter):
    dry = await adapter.write(
        {"collection": "users", "operation": "updateMany", "filter": {}, "update": {"$set": {"tag": "x"}}},
        None,
        dry_run=True,
    )
    assert dry["would_affect"] == 2

    aborted = await adapter.write(
        {"collection": "users", "operation": "deleteMany", "filter": {}},
        None,
        expected_max_rows=1,
    )
    assert aborted["applied"] is False and aborted["affected"] == 2

    updated = await adapter.write(
        {
            "collection": "users",
            "operation": "updateOne",
            "filter": {"name": "Ana"},
            "update": {"$set": {"vip": True}},
        },
        None,
    )
    assert updated == {"applied": True, "affected": 1}

    with pytest.raises(QueryValidationError, match="filter"):
        await adapter.write({"collection": "users", "operation": "deleteMany"}, None)

    with pytest.raises(QueryValidationError, match="documents"):
        await adapter.write({"collection": "users", "operation": "insertMany"}, None)

    with pytest.raises(QueryValidationError, match="keys"):
        await adapter.write({"collection": "users", "operation": "createIndex"}, None)


async def test_collection_lifecycle(adapter):
    await adapter.write({"collection": "temp_coll", "operation": "createCollection"}, None)
    await adapter.write({"collection": "temp_coll", "operation": "renameCollection", "to": "temp_coll2"}, None)
    dropped = await adapter.write({"collection": "temp_coll2", "operation": "dropCollection"}, None)
    assert dropped["applied"] is True

    with pytest.raises(QueryValidationError, match="'to'"):
        await adapter.write({"collection": "users", "operation": "renameCollection"}, None)


async def test_analyze_unsupported_and_maintain(adapter):
    with pytest.raises(GuidanceError, match="ANALYZE"):
        await adapter.analyze("test", "users")

    with pytest.raises(QueryValidationError, match="compact"):
        await adapter.maintain("test", "users", "vacuum")


async def test_list_objects_filters_views(adapter):
    db = adapter._db("test")
    await db.create_collection("users_view", viewOn="users", pipeline=[])
    try:
        views = await adapter.list_objects("test", "view")
        assert [o["name"] for o in views] == ["users_view"]
        collections = await adapter.list_objects("test", "collection")
        assert all(o["type"] == "collection" for o in collections)
        assert "users_view" not in {o["name"] for o in collections}
    finally:
        await db.drop_collection("users_view")


async def test_describe_missing_collection_raises_not_found(adapter):
    with pytest.raises(QueryValidationError, match="not found"):
        await adapter.describe_object("test", "ghost")


async def test_read_estimated_count_and_unhandled_operation(adapter):
    count = await adapter.read({"collection": "users", "operation": "estimatedDocumentCount"}, None, None)
    assert count[0]["count"] >= 1

    with pytest.raises(QueryValidationError, match="Unhandled read operation"):
        await adapter.read({"collection": "users", "operation": "mapReduce"}, None, None)


async def test_explain_aggregate_and_count(adapter):
    aggregate_plan = await adapter.explain(
        {"collection": "users", "operation": "aggregate", "pipeline": [{"$match": {"age": 30}}]}
    )
    assert "plan" in aggregate_plan

    count_plan = await adapter.explain({"collection": "users", "operation": "countDocuments", "filter": {}})
    assert "plan" in count_plan


async def test_grants_filtered_by_object(adapter):
    grants = await adapter.grants("test", obj="users")
    assert grants and all("privileges" in g for g in grants)


async def test_settings_without_pattern_returns_scalars(adapter):
    settings = await adapter.settings()
    assert settings and len(settings) <= 100
    assert all(not isinstance(s["value"], dict | list) for s in settings)


async def test_logs_level_filter(adapter):
    lines = await adapter.logs(limit=5, level="informational")
    assert all('"s":"I"' in entry["line"] for entry in lines)


async def test_write_variants_and_dry_runs(adapter):
    docs = [{"n": i, "kind": "even" if i % 2 == 0 else "odd"} for i in range(4)]
    insert_dry = await adapter.write(
        {"collection": "wv", "operation": "insertMany", "documents": docs}, None, dry_run=True
    )
    assert insert_dry == {"applied": False, "dry_run": True, "would_affect": 4}

    await adapter.write({"collection": "wv", "operation": "insertMany", "documents": docs}, None)

    updated = await adapter.write(
        {"collection": "wv", "operation": "updateMany", "filter": {"kind": "even"}, "update": {"$set": {"seen": 1}}},
        None,
    )
    assert updated == {"applied": True, "affected": 2}

    replaced = await adapter.write(
        {"collection": "wv", "operation": "replaceOne", "filter": {"n": 1}, "replacement": {"n": 1, "kind": "prime"}},
        None,
    )
    assert replaced == {"applied": True, "affected": 1}

    deleted_one = await adapter.write({"collection": "wv", "operation": "deleteOne", "filter": {"n": 3}}, None)
    assert deleted_one == {"applied": True, "affected": 1}

    ddl_dry = await adapter.write(
        {"collection": "wv", "operation": "createIndex", "keys": {"n": 1}}, None, dry_run=True
    )
    assert ddl_dry["dry_run"] is True

    await adapter.write({"collection": "wv", "operation": "createIndex", "keys": {"n": 1}}, None)
    dropped_index = await adapter.write({"collection": "wv", "operation": "dropIndex", "name": "n_1"}, None)
    assert dropped_index == {"applied": True, "dropped_index": "n_1"}

    deleted_all = await adapter.write({"collection": "wv", "operation": "deleteMany", "filter": {}}, None)
    assert deleted_all["applied"] is True and deleted_all["affected"] == 3

    with pytest.raises(QueryValidationError, match="Unhandled write operation"):
        await adapter.write({"collection": "wv", "operation": "findAndModify"}, None)

    await adapter.write({"collection": "wv", "operation": "dropCollection"}, None)


async def test_kill_numeric_and_string_opids(adapter):
    result = await adapter.kill("999999999")
    assert result["action"] == "killOp"

    from pymongo.errors import PyMongoError

    with pytest.raises(PyMongoError):
        await adapter.kill("shard01:123")


async def test_maintain_compact_happy(adapter):
    result = await adapter.maintain("test", "users")
    assert result["action"] == "compact"


@pytest.fixture(scope="module")
async def restricted(adapter, mongo_uri):
    client = adapter._get_client()
    await client.admin.command("createUser", "weak", pwd="weak", roles=[])
    host_part = mongo_uri.split("@")[1].split("/")[0]
    weak = MongoAdapter(make_cfg("weak", f"mongodb://weak:weak@{host_part}/test?authSource=admin"))
    yield weak
    await weak.close()
    await client.admin.command("dropUser", "weak")


async def test_restricted_user_gets_guidance_errors(restricted):
    with pytest.raises(GuidanceError, match="viewUser"):
        await restricted.users()
    with pytest.raises(GuidanceError, match="viewUser"):
        await restricted.grants()
    with pytest.raises(GuidanceError, match="inprog"):
        await restricted.active_ops()
    with pytest.raises(GuidanceError, match="clusterMonitor"):
        await restricted.blocking()
    with pytest.raises(GuidanceError, match="clusterMonitor"):
        await restricted.settings()
    with pytest.raises(GuidanceError, match="clusterMonitor"):
        await restricted.logs()
    with pytest.raises(GuidanceError, match="compact"):
        await restricted.maintain("test", "users")


@pytest.fixture(scope="module")
async def rs_adapter():
    import time as _time

    from pymongo import MongoClient
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.wait_strategies import LogMessageWaitStrategy

    container = (
        DockerContainer("mongo:8")
        .with_exposed_ports(27017)
        .with_command("--replSet rs0 --bind_ip_all")
        .waiting_for(LogMessageWaitStrategy("Waiting for connections").with_startup_timeout(60))
    )
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(27017)
        uri = f"mongodb://{host}:{port}/test?directConnection=true"
        setup = MongoClient(uri, directConnection=True, serverSelectionTimeoutMS=10000)
        setup.admin.command("replSetInitiate")
        deadline = _time.time() + 30
        while not setup.admin.command("hello").get("isWritablePrimary"):
            if _time.time() > deadline:
                raise TimeoutError("replica set did not elect a primary")
            _time.sleep(0.5)
        setup.close()
        instance = MongoAdapter(make_cfg("rs", uri))
        yield instance
        await instance.close()


async def test_replication_replica_set_members(rs_adapter):
    replication = await rs_adapter.replication()
    assert replication["role"] == "replica_set"
    assert replication["set"] == "rs0"
    assert replication["members"] and replication["members"][0]["state"] == "PRIMARY"
    assert "shards" not in replication


async def test_unicode_round_trip(adapter):
    """Accented text, emoji and wildcard characters survive a real insertOne/find unchanged."""
    await adapter.write({"collection": "unicode_t", "operation": "insertOne", "document": {"name": "José 🚀 %_"}}, None)
    try:
        rows = await adapter.read(
            {"collection": "unicode_t", "operation": "find", "filter": {"name": "José 🚀 %_"}}, None, 10
        )
        assert len(rows) == 1
        assert rows[0]["name"] == "José 🚀 %_"
    finally:
        await adapter.write({"collection": "unicode_t", "operation": "dropCollection"}, None)


async def test_column_stats_gives_guidance(adapter):
    """MongoDB has no planner statistics; the tool points at db_schema_describe instead of erroring blindly."""
    with pytest.raises(GuidanceError, match="db_schema_describe"):
        await adapter.column_stats("test", "users")


async def test_explain_hypothetical_gives_guidance(adapter):
    """Hypothetical indexes are a PostgreSQL/hypopg feature; MongoDB points that out instead of failing oddly."""
    with pytest.raises(GuidanceError, match="hypopg"):
        await adapter.explain(
            {"collection": "users", "operation": "find"}, hypothetical_indexes=["CREATE INDEX ON users(email)"]
        )
