"""MongoAdapter Atlas search/vector methods: pipeline assembly, error mapping and cluster actions."""

from datetime import UTC, datetime

import pytest
from pymongo.errors import AutoReconnect, OperationFailure, PyMongoError

from mcp_database.adapters.mongodb import MongoAdapter
from mcp_database.config import parse_connection
from mcp_database.errors import GuidanceError, QueryValidationError


class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    async def to_list(self, length=None):
        return self._docs[:length] if length else self._docs

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration from None


class FakeCollection:
    def __init__(self, script):
        self.script = script
        self.calls = []

    def _next(self, method, **kwargs):
        self.calls.append({"method": method, **kwargs})
        result = self.script.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def aggregate(self, pipeline, maxTimeMS=None):  # noqa: N803 - pymongo API name
        return FakeCursor(self._next("aggregate", pipeline=pipeline, maxTimeMS=maxTimeMS))

    async def list_search_indexes(self):
        return FakeCursor(self._next("list_search_indexes"))

    async def create_search_index(self, model):
        return self._next("create_search_index", model=model)

    async def update_search_index(self, name, definition):
        return self._next("update_search_index", name=name, definition=definition)

    async def drop_search_index(self, name):
        return self._next("drop_search_index", name=name)

    async def estimated_document_count(self, maxTimeMS=None):  # noqa: N803 - pymongo API name
        return self._next("estimated_document_count")

    async def index_information(self):
        return self._next("index_information")


class FakeDB:
    def __init__(self, collection, infos=None, commands=None):
        self.collection = collection
        self.infos = infos or []
        self.commands = commands or []

    def __getitem__(self, name):
        return self.collection

    async def list_collections(self, filter=None):
        return FakeCursor(self.infos)

    async def command(self, cmd):
        result = self.commands.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeAdmin:
    def __init__(self, script):
        self.script = script
        self.commands = []

    async def command(self, cmd):
        self.commands.append(cmd)
        result = self.script.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeClient:
    def __init__(self, admin):
        self.admin = admin


def make_adapter(monkeypatch, collection=None, admin=None, infos=None, commands=None):
    adapter = MongoAdapter(parse_connection("c", {"uri": "mongodb://h/db"}))
    if collection is not None:
        monkeypatch.setattr(adapter, "_db", lambda database=None: FakeDB(collection, infos, commands))
    if admin is not None:
        monkeypatch.setattr(adapter, "_get_client", lambda: FakeClient(admin))
    return adapter


UNRECOGNIZED = OperationFailure("Unrecognized pipeline stage name: '$vectorSearch'", 40324, {"errmsg": "no mongot"})


class TestSearchUnavailablePredicate:
    """_is_search_unavailable separates 'no mongot here' from real query/privilege failures."""

    @pytest.mark.parametrize("code", [40324, 31082, 6047401, 115])
    def test_known_codes_match(self, code):
        from mcp_database.adapters.mongodb._common import _is_search_unavailable

        assert _is_search_unavailable(OperationFailure("boom", code, None)) is True

    @pytest.mark.parametrize(
        "errmsg",
        [
            "Unrecognized pipeline stage name: '$vectorSearch'",
            "$search stage is only allowed on MongoDB Atlas",
            "Error connecting to Search Index Management service.",
            "mongot is not available",
        ],
    )
    def test_messages_match_regardless_of_code(self, errmsg):
        from mcp_database.adapters.mongodb._common import _is_search_unavailable

        assert _is_search_unavailable(OperationFailure(errmsg, 8000, {"errmsg": errmsg})) is True

    @pytest.mark.parametrize(
        ("code", "errmsg"),
        [(13, "not authorized on db"), (50, "operation exceeded time limit"), (11600, "interrupted at shutdown")],
    )
    def test_unrelated_failures_do_not_match(self, code, errmsg):
        from mcp_database.adapters.mongodb._common import _is_search_unavailable

        assert _is_search_unavailable(OperationFailure(errmsg, code, {"errmsg": errmsg})) is False


class TestVectorSearch:
    async def test_happy_pipeline_shape(self, monkeypatch):
        collection = FakeCollection([[{"_id": 1, "_score": 0.9}]])
        adapter = make_adapter(monkeypatch, collection=collection)
        rows = await adapter.vector_search("db", "docs", "emb", [0.1, 0.2], "cosine", 5, index="vec_idx")
        assert rows == [{"_id": 1, "_score": 0.9}]
        pipeline = collection.calls[0]["pipeline"]
        assert pipeline[0]["$vectorSearch"] == {
            "index": "vec_idx",
            "path": "emb",
            "queryVector": [0.1, 0.2],
            "numCandidates": 100,
            "limit": 5,
        }
        assert pipeline[1] == {"$addFields": {"_score": {"$meta": "vectorSearchScore"}}}
        assert pipeline[2] == {"$project": {"emb": 0}}
        assert collection.calls[0]["maxTimeMS"] == adapter._timeout_ms

    async def test_filter_and_candidates_forwarded(self, monkeypatch):
        collection = FakeCollection([[]])
        adapter = make_adapter(monkeypatch, collection=collection)
        await adapter.vector_search(
            "db", "docs", "emb", [0.1], "cosine", 5, flt={"lang": "pt"}, index="v", num_candidates=500
        )
        stage = collection.calls[0]["pipeline"][0]["$vectorSearch"]
        assert stage["filter"] == {"lang": "pt"}
        assert stage["numCandidates"] == 500

    @pytest.mark.parametrize(
        ("num_candidates", "limit", "expected"),
        [(None, 5, 100), (None, 50, 500), (None, 3, 100), (250, 5, 250)],
    )
    async def test_num_candidates_default_is_ten_x_limit_floor_100(self, monkeypatch, num_candidates, limit, expected):
        collection = FakeCollection([[]])
        adapter = make_adapter(monkeypatch, collection=collection)
        await adapter.vector_search(
            "db", "docs", "emb", [0.1], "cosine", limit, index="v", num_candidates=num_candidates
        )
        assert collection.calls[0]["pipeline"][0]["$vectorSearch"]["numCandidates"] == expected

    async def test_index_is_required(self, monkeypatch):
        adapter = make_adapter(monkeypatch, collection=FakeCollection([]))
        with pytest.raises(QueryValidationError, match="requires 'index'"):
            await adapter.vector_search("db", "docs", "emb", [0.1], "cosine", 5)

    async def test_no_mongot_maps_to_guidance(self, monkeypatch):
        adapter = make_adapter(monkeypatch, collection=FakeCollection([UNRECOGNIZED]))
        with pytest.raises(GuidanceError, match="mongodb-atlas-local"):
            await adapter.vector_search("db", "docs", "emb", [0.1], "cosine", 5, index="v")

    async def test_unrelated_operation_failure_is_not_masked(self, monkeypatch):
        boom = OperationFailure("not authorized on db", 13, {"errmsg": "not authorized on db"})
        adapter = make_adapter(monkeypatch, collection=FakeCollection([boom]))
        with pytest.raises(OperationFailure, match="not authorized"):
            await adapter.vector_search("db", "docs", "emb", [0.1], "cosine", 5, index="v")


class TestTextSearch:
    async def test_happy_wildcard_path_and_default_index(self, monkeypatch):
        collection = FakeCollection([[{"_id": 1}]])
        adapter = make_adapter(monkeypatch, collection=collection)
        await adapter.text_search("db", "docs", "hello", limit=10)
        pipeline = collection.calls[0]["pipeline"]
        assert pipeline[0]["$search"] == {"index": "default", "text": {"query": "hello", "path": {"wildcard": "*"}}}
        assert pipeline[-2] == {"$limit": 10}

    async def test_column_filter_and_index(self, monkeypatch):
        collection = FakeCollection([[]])
        adapter = make_adapter(monkeypatch, collection=collection)
        await adapter.text_search("db", "docs", "hello", column="title", index="idx", limit=5, flt={"lang": "pt"})
        pipeline = collection.calls[0]["pipeline"]
        assert pipeline[0]["$search"]["index"] == "idx"
        assert pipeline[0]["$search"]["text"]["path"] == "title"
        assert {"$match": {"lang": "pt"}} in pipeline

    async def test_language_rejected(self, monkeypatch):
        adapter = make_adapter(monkeypatch, collection=FakeCollection([]))
        with pytest.raises(QueryValidationError, match="PostgreSQL"):
            await adapter.text_search("db", "docs", "q", language="english", limit=5)

    async def test_no_mongot_maps_to_guidance(self, monkeypatch):
        missing = OperationFailure("Unrecognized pipeline stage name: '$search'", 40324, None)
        adapter = make_adapter(monkeypatch, collection=FakeCollection([missing]))
        with pytest.raises(GuidanceError, match="Atlas"):
            await adapter.text_search("db", "docs", "q", limit=5)


class TestSearchIndexes:
    async def test_happy_with_explicit_collection(self, monkeypatch):
        entries = [
            {
                "name": "vec_idx",
                "type": "vectorSearch",
                "status": "READY",
                "queryable": True,
                "latestDefinition": {"fields": [{"path": "emb", "numDimensions": 3, "similarity": "cosine"}]},
            }
        ]
        collection = FakeCollection([entries])
        adapter = make_adapter(monkeypatch, collection=collection)
        result = await adapter.search_indexes("db", "docs")
        row = result["indexes"][0]
        assert row["collection"] == "docs"
        assert row["type"] == "vectorSearch"
        assert row["queryable"] is True
        assert row["definition"]["fields"][0]["numDimensions"] == 3

    async def test_no_mongot_maps_to_guidance(self, monkeypatch):
        missing = OperationFailure("listSearchIndexes not allowed", 115, {"errmsg": "Atlas only"})
        adapter = make_adapter(monkeypatch, collection=FakeCollection([missing]))
        with pytest.raises(GuidanceError, match="Atlas"):
            await adapter.search_indexes("db", "docs")

    async def test_without_object_walks_collections_skipping_system(self, monkeypatch):
        """Omitting 'object' lists every non-system collection and aggregates their search indexes."""
        entry = {"name": "i", "type": "search", "status": "READY", "queryable": True, "latestDefinition": {}}
        collection = FakeCollection([[entry], [entry]])
        infos = [{"name": "b"}, {"name": "system.views"}, {"name": "a"}]
        adapter = make_adapter(monkeypatch, collection=collection, infos=infos)
        result = await adapter.search_indexes("db")
        assert [row["collection"] for row in result["indexes"]] == ["a", "b"]


class TestVectorStats:
    async def test_sections_shape(self, monkeypatch):
        entries = [
            {"name": "v", "type": "vectorSearch", "status": "READY", "queryable": True, "latestDefinition": {}},
            {"name": "t", "type": "search", "status": "READY", "queryable": True, "latestDefinition": {}},
        ]
        collection = FakeCollection([entries, 42])
        adapter = make_adapter(monkeypatch, collection=collection)
        result = await adapter.vector_stats("db", "docs")
        assert len(result["vector_indexes"]) == 1
        assert result["collection_counts"] == {"docs": 42}
        assert result["search_indexes_total"] == 2


class TestSearchIndexWrite:
    async def test_create_infers_vector_type_from_fields(self, monkeypatch):
        collection = FakeCollection(["vec_idx"])
        adapter = make_adapter(monkeypatch, collection=collection)
        definition = {"fields": [{"type": "vector", "path": "emb", "numDimensions": 3, "similarity": "cosine"}]}
        result = await adapter.search_index_write("db", "docs", "create", "vec_idx", definition)
        model = collection.calls[0]["model"]
        assert model.document["type"] == "vectorSearch"
        assert result["applied"] is True
        assert "asynchronous" in result["note"]

    async def test_create_defaults_to_search_type_for_mappings(self, monkeypatch):
        collection = FakeCollection(["txt_idx"])
        adapter = make_adapter(monkeypatch, collection=collection)
        await adapter.search_index_write("db", "docs", "create", "txt_idx", {"mappings": {"dynamic": True}})
        assert collection.calls[0]["model"].document["type"] == "search"

    async def test_update_and_drop(self, monkeypatch):
        collection = FakeCollection([None, None])
        adapter = make_adapter(monkeypatch, collection=collection)
        await adapter.search_index_write("db", "docs", "update", "idx", {"mappings": {"dynamic": False}})
        await adapter.search_index_write("db", "docs", "drop", "idx")
        assert collection.calls[0]["method"] == "update_search_index"
        assert collection.calls[1] == {"method": "drop_search_index", "name": "idx"}

    async def test_create_requires_definition(self, monkeypatch):
        adapter = make_adapter(monkeypatch, collection=FakeCollection([]))
        with pytest.raises(QueryValidationError, match="requires 'definition'"):
            await adapter.search_index_write("db", "docs", "create", "idx")

    async def test_unknown_action(self, monkeypatch):
        adapter = make_adapter(monkeypatch, collection=FakeCollection([]))
        with pytest.raises(QueryValidationError, match="Unknown action"):
            await adapter.search_index_write("db", "docs", "rebuild", "idx")


class TestClusterAction:
    @pytest.mark.parametrize(("seconds", "expected"), [(None, 60), (0, 0), (30, 30), (86400, 86400)])
    async def test_step_down_seconds_variants(self, monkeypatch, seconds, expected):
        admin = FakeAdmin([{"ok": 1}])
        adapter = make_adapter(monkeypatch, admin=admin)
        result = await adapter.cluster_action("step_down", seconds=seconds)
        assert admin.commands == [{"replSetStepDown": expected}]
        assert result["success"] is True

    async def test_step_down_survives_dropped_connection(self, monkeypatch):
        """The primary closes connections while stepping down; AutoReconnect is the success path."""
        admin = FakeAdmin([AutoReconnect("connection closed")])
        adapter = make_adapter(monkeypatch, admin=admin)
        result = await adapter.cluster_action("step_down", seconds=30)
        assert result == {
            "action": "step_down",
            "seconds": 30,
            "success": True,
            "note": "Primary stepped down; the replica set will elect a new primary",
        }

    async def test_step_down_standalone_guides(self, monkeypatch):
        admin = FakeAdmin([OperationFailure("not running with --replSet", 76, None)])
        adapter = make_adapter(monkeypatch, admin=admin)
        with pytest.raises(GuidanceError, match="standalone"):
            await adapter.cluster_action("step_down")

    async def test_freeze_requires_seconds(self, monkeypatch):
        adapter = make_adapter(monkeypatch, admin=FakeAdmin([]))
        with pytest.raises(QueryValidationError, match="requires 'seconds'"):
            await adapter.cluster_action("freeze")

    async def test_freeze_happy(self, monkeypatch):
        admin = FakeAdmin([{"ok": 1}])
        adapter = make_adapter(monkeypatch, admin=admin)
        result = await adapter.cluster_action("freeze", seconds=120)
        assert admin.commands == [{"replSetFreeze": 120}]
        assert result["success"] is True

    @pytest.mark.parametrize("action", ["promote", "start_replica", "sudo reboot", ""])
    async def test_foreign_actions_guide(self, monkeypatch, action):
        adapter = make_adapter(monkeypatch, admin=FakeAdmin([]))
        with pytest.raises(GuidanceError, match="step_down"):
            await adapter.cluster_action(action)


class TestObjectStatsBranches:
    async def test_list_objects_count_failure_yields_none(self, monkeypatch):
        """A failing estimated_document_count degrades to approx_rows=None, never an error."""
        collection = FakeCollection([PyMongoError("count failed")])
        adapter = make_adapter(monkeypatch, collection=collection, infos=[{"name": "events"}])
        rows = await adapter.list_objects("app")
        assert rows == [{"name": "events", "type": "collection", "approx_rows": None}]

    async def test_describe_object_survives_index_and_stats_failures(self, monkeypatch):
        """describe_object reports indexes_error and stats=None instead of failing outright."""
        collection = FakeCollection([PyMongoError("no privilege")])
        adapter = make_adapter(
            monkeypatch,
            collection=collection,
            infos=[{"name": "events"}],
            commands=[PyMongoError("collStats denied")],
        )
        result = await adapter.describe_object("app", "events", sample=False)
        assert "no privilege" in result["indexes_error"]
        assert result["stats"] is None

    async def test_table_stats_skips_collections_without_collstats(self, monkeypatch):
        """A collection whose collStats fails is skipped, not fatal."""
        adapter = make_adapter(
            monkeypatch,
            collection=FakeCollection([]),
            infos=[{"name": "broken"}, {"name": "ok"}],
            commands=[PyMongoError("denied"), {"count": 2, "size": 10}],
        )
        rows = await adapter.table_stats("app")
        assert [row["collection"] for row in rows] == ["ok"]


class TestReplicationBranches:
    async def test_permission_failure_becomes_guidance(self, monkeypatch):
        """A non-76 replSetGetStatus failure maps to GuidanceError naming clusterMonitor."""
        admin = FakeAdmin([OperationFailure("unauthorized", 13, {"errmsg": "unauthorized"})])
        adapter = make_adapter(monkeypatch, admin=admin)
        with pytest.raises(GuidanceError, match="clusterMonitor"):
            await adapter.replication()

    async def test_secondary_lag_and_sharding_sections(self, monkeypatch):
        """Secondaries report lag against the primary optime; sharded clusters add shards and balancer."""
        primary_time = datetime(2026, 7, 18, 10, 0, 10, tzinfo=UTC)
        secondary_time = datetime(2026, 7, 18, 10, 0, 0, tzinfo=UTC)
        status = {
            "set": "rs0",
            "members": [
                {"name": "m1", "stateStr": "PRIMARY", "health": 1, "optimeDate": primary_time},
                {"name": "m2", "stateStr": "SECONDARY", "health": 1, "optimeDate": secondary_time},
            ],
        }
        admin = FakeAdmin([status, {"shards": [{"_id": "sh1"}]}, {"mode": "full", "inBalancerRound": False}])
        adapter = make_adapter(monkeypatch, admin=admin)
        result = await adapter.replication()
        lags = {member["name"]: member["lag_seconds"] for member in result["members"]}
        assert lags == {"m1": None, "m2": 10}
        assert result["shards"] == [{"_id": "sh1"}]
        assert result["balancer"] == {"mode": "full", "in_round": False}


class TestSearchErrorPassthrough:
    async def test_text_search_reraises_non_search_failures(self, monkeypatch):
        """A permission failure during $search is not masked as missing mongot."""
        adapter = make_adapter(monkeypatch, collection=FakeCollection([OperationFailure("denied", 13, {})]))
        with pytest.raises(OperationFailure, match="denied"):
            await adapter.text_search("db", "docs", "q", limit=5)

    async def test_search_indexes_reraises_non_search_failures(self, monkeypatch):
        """Listing search indexes propagates real failures untouched."""
        adapter = make_adapter(
            monkeypatch,
            collection=FakeCollection([OperationFailure("denied", 13, {})]),
            infos=[{"name": "docs"}],
        )
        with pytest.raises(OperationFailure, match="denied"):
            await adapter.search_indexes("db", "docs")

    async def test_search_index_write_reraises_non_search_failures(self, monkeypatch):
        """Managing search indexes propagates real failures untouched."""
        collection = FakeCollection([OperationFailure("denied", 13, {})])
        adapter = make_adapter(monkeypatch, collection=collection)
        with pytest.raises(OperationFailure, match="denied"):
            await adapter.search_index_write("db", "docs", "drop", "idx")

    async def test_update_requires_a_definition(self, monkeypatch):
        """update without the full new definition is rejected before touching the server."""
        adapter = make_adapter(monkeypatch, collection=FakeCollection([]))
        with pytest.raises(QueryValidationError, match="requires 'definition'"):
            await adapter.search_index_write("db", "docs", "update", "idx")


class TestVectorStatsBranches:
    async def test_count_failure_yields_none(self, monkeypatch):
        """A failing count for an indexed collection degrades to None in collection_counts."""
        collection = FakeCollection([PyMongoError("denied")])
        adapter = make_adapter(monkeypatch, collection=collection)

        async def fake_indexes(database=None, obj=None):
            return {"indexes": [{"collection": "docs", "index": "v", "type": "vectorSearch"}]}

        monkeypatch.setattr(adapter, "search_indexes", fake_indexes)
        result = await adapter.vector_stats("db")
        assert result["collection_counts"] == {"docs": None}
        assert result["search_indexes_total"] == 1


class TestClusterErrorPassthrough:
    async def test_step_down_reraises_non_standalone_failures(self, monkeypatch):
        """A permission failure on replSetStepDown propagates instead of claiming standalone."""
        adapter = make_adapter(monkeypatch, admin=FakeAdmin([OperationFailure("unauthorized", 13, {})]))
        with pytest.raises(OperationFailure, match="unauthorized"):
            await adapter.cluster_action("step_down")

    async def test_freeze_on_standalone_guides(self, monkeypatch):
        """replSetFreeze code 76 maps to the standalone GuidanceError."""
        adapter = make_adapter(monkeypatch, admin=FakeAdmin([OperationFailure("not running with --replSet", 76, {})]))
        with pytest.raises(GuidanceError, match="standalone"):
            await adapter.cluster_action("freeze", seconds=60)

    async def test_freeze_reraises_other_failures(self, monkeypatch):
        """Non-76 replSetFreeze failures propagate untouched."""
        adapter = make_adapter(monkeypatch, admin=FakeAdmin([OperationFailure("unauthorized", 13, {})]))
        with pytest.raises(OperationFailure, match="unauthorized"):
            await adapter.cluster_action("freeze", seconds=60)


class TestStorageAndIndexSignals:
    async def test_storage_degrades_on_errors(self, monkeypatch):
        """dbStats and oplog failures become 'unavailable' sections instead of raising."""
        collection = FakeCollection([])
        adapter = make_adapter(monkeypatch, collection=collection, commands=[PyMongoError("denied")])
        monkeypatch.setattr(adapter, "_get_client", lambda: (_ for _ in ()).throw(PyMongoError("no local")))
        sections = await adapter.storage()
        assert "unavailable" in sections["db"] and "unavailable" in sections["oplog"]

    async def test_index_signals_profiler_off_guides(self, monkeypatch):
        """A profiler level of 0 raises guidance telling how to enable it."""
        adapter = make_adapter(monkeypatch, collection=FakeCollection([]), commands=[{"was": 0}])
        with pytest.raises(GuidanceError, match="profiler is off"):
            await adapter.index_signals("app")

    async def test_index_signals_reports_collscans(self, monkeypatch):
        """With the profiler on, COLLSCAN aggregates are returned per namespace."""
        collection = FakeCollection([[{"_id": "app.events", "count": 3, "avg_ms": 12.0}]])
        adapter = make_adapter(monkeypatch, collection=collection, commands=[{"was": 1}])
        result = await adapter.index_signals("app")
        assert result["collscans"] == [{"ns": "app.events", "count": 3, "avg_ms": 12.0}]

    async def test_index_signals_profiler_error_guides(self, monkeypatch):
        """A failure reading the profiler level surfaces as guidance."""
        adapter = make_adapter(monkeypatch, collection=FakeCollection([]), commands=[PyMongoError("denied")])
        with pytest.raises(GuidanceError, match="profiler level"):
            await adapter.index_signals("app")

    async def test_storage_standalone_has_no_oplog(self, monkeypatch):
        """On a standalone mongod the oplog is empty, reported as unavailable, not an error."""

        class EmptyOplog:
            async def find_one(self, sort=None):
                return None

        class LocalClient:
            def __getitem__(self, name):
                return type("DB", (), {"__getitem__": lambda self, key: EmptyOplog()})()

        adapter = make_adapter(monkeypatch, collection=FakeCollection([]), commands=[{"db": "app", "dataSize": 1}])
        monkeypatch.setattr(adapter, "_get_client", lambda: LocalClient())
        sections = await adapter.storage()
        assert sections["oplog"] == {"unavailable": "no oplog (standalone mongod)"}

    async def test_storage_reports_oplog_window(self, monkeypatch):
        """A replica-set oplog yields a window in hours from the first and last entries' timestamps."""

        class Ts:
            def __init__(self, seconds):
                self.time = seconds

        class Oplog:
            async def find_one(self, sort=None):
                return {"ts": Ts(0)} if sort[0][1] == 1 else {"ts": Ts(7200)}

        class LocalClient:
            def __getitem__(self, name):
                return type("DB", (), {"__getitem__": lambda self, key: Oplog()})()

        adapter = make_adapter(monkeypatch, collection=FakeCollection([]), commands=[{"db": "app", "dataSize": 1}])
        monkeypatch.setattr(adapter, "_get_client", lambda: LocalClient())
        sections = await adapter.storage()
        assert sections["oplog"] == {"window_hours": 2.0}
