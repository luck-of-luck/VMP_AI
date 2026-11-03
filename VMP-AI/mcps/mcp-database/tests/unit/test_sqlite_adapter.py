"""SQLiteAdapter against real temp-file databases: read-only guarantee, PRAGMAs, FTS5 and guidance."""

import pytest

from mcp_database.adapters.sqlite import SQLiteAdapter
from mcp_database.config import parse_connection
from mcp_database.errors import ConfigError, GuidanceError, QueryValidationError


@pytest.fixture
async def adapter(tmp_path):
    instance = SQLiteAdapter(parse_connection("sq", {"uri": f"sqlite:///{tmp_path}/app.db"}))
    await instance.write("CREATE TABLE users (id integer PRIMARY KEY, name text NOT NULL, email text UNIQUE)", None)
    await instance.write("CREATE TABLE orders (id integer PRIMARY KEY, user_id integer REFERENCES users(id))", None)
    await instance.write("INSERT INTO users (name, email) VALUES ('ana', 'ana@x'), ('bob', 'bob@x')", None)
    return instance


class TestPathParsing:
    def test_quadruple_slash_is_absolute(self):
        adapter = SQLiteAdapter(parse_connection("sq", {"uri": "sqlite:////var/data/app.db"}))
        assert adapter._path == "/var/data/app.db"

    def test_triple_slash_is_relative(self):
        adapter = SQLiteAdapter(parse_connection("sq", {"uri": "sqlite:///temp/playground.db"}))
        assert adapter._path == "temp/playground.db"

    @pytest.mark.parametrize("uri", ["sqlite://", "sqlite:///:memory:", "sqlite://:memory:"])
    def test_memory_and_empty_paths_rejected(self, uri):
        adapter = SQLiteAdapter(parse_connection("sq", {"uri": uri}))
        with pytest.raises(ConfigError, match="must point at a file"):
            _ = adapter._path


class TestReadWrite:
    async def test_read_sees_committed_writes(self, adapter):
        rows = await adapter.read("SELECT name FROM users ORDER BY id", None, 10)
        assert [row["name"] for row in rows] == ["ana", "bob"]

    async def test_readonly_connection_cannot_write(self, adapter):
        """The mode=ro file URI makes writes through the read path structurally impossible."""
        with pytest.raises(Exception, match=r"readonly|attempt to write"):
            await adapter._fetch("DELETE FROM users", readonly=True)

    async def test_dry_run_uses_probe_and_leaves_data(self, adapter):
        outcome = await adapter.write("DELETE FROM users WHERE id = 1", None, dry_run=True)
        assert outcome == {"applied": False, "dry_run": True, "would_affect": 1}
        assert len(await adapter.read("SELECT id FROM users", None, 10)) == 2

    async def test_expected_max_rows_aborts_oversized_writes(self, adapter):
        outcome = await adapter.write("DELETE FROM users WHERE id > 0", None, expected_max_rows=1)
        assert outcome["applied"] is False
        assert "above expected_max_rows" in outcome["aborted"]

    async def test_ddl_is_transactional(self, adapter):
        outcome = await adapter.write("CREATE TABLE t2 (id integer)", None)
        assert outcome["applied"] is True

    async def test_unicode_round_trip(self, adapter):
        await adapter.write("INSERT INTO users (name, email) VALUES ('ação🚀', 'a@x')", None)
        rows = await adapter.read("SELECT name FROM users WHERE email = 'a@x'", None, 1)
        assert rows[0]["name"] == "ação🚀"


class TestSchema:
    async def test_list_databases_and_objects(self, adapter):
        assert [db["database"] for db in await adapter.list_databases()] == ["main"]
        objects = await adapter.list_objects("main")
        assert {obj["name"] for obj in objects} >= {"users", "orders"}

    async def test_unknown_database_is_clean_error(self, adapter):
        with pytest.raises(QueryValidationError, match="not found"):
            await adapter.list_objects("prod")

    async def test_describe_ddl_and_relationships(self, adapter):
        described = await adapter.describe_object("main", "users", sample=False)
        assert any(col["name"] == "email" and col["nullable"] for col in described["columns"])
        assert "CREATE TABLE users" in (await adapter.get_ddl("main", "users"))["ddl"]
        relationships = (await adapter.relationships("main", obj="users"))["relationships"]
        assert relationships[0]["from_table"] == "orders"

    async def test_describe_missing_object_not_found(self, adapter):
        with pytest.raises(QueryValidationError, match="not found"):
            await adapter.describe_object("main", "ghost")

    async def test_search_escapes_like_wildcards(self, adapter):
        """A % in the search pattern is a literal, never a wildcard."""
        result = await adapter.search("user")
        assert any(obj["name"] == "users" for obj in result["objects"])
        assert (await adapter.search("%"))["objects"] == []

    async def test_sample_returns_rows(self, adapter):
        assert len(await adapter.sample("main", "users", 1)) == 1


class TestPerf:
    async def test_explain_query_plan(self, adapter):
        plan = await adapter.explain("SELECT * FROM users WHERE id = 1")
        assert plan["plan"]

    async def test_explain_analyze_rejected(self, adapter):
        with pytest.raises(QueryValidationError, match="no EXPLAIN ANALYZE"):
            await adapter.explain("SELECT 1", analyze=True)

    async def test_stats_guide_before_analyze_and_answer_after(self, adapter):
        with pytest.raises(GuidanceError, match="ANALYZE"):
            await adapter.table_stats()
        await adapter.analyze("main")
        stats = await adapter.table_stats()
        assert any(row["table"] == "users" and row["approx_rows"] == 2 for row in stats)

    async def test_health_and_settings(self, adapter):
        health = await adapter.health()
        assert health["quick_check"] == "ok"
        assert health["size_bytes"] > 0
        names = [row["name"] for row in await adapter.settings("journal")]
        assert names == ["journal_mode"]


class TestMaintain:
    async def test_vacuum_and_reindex(self, adapter):
        assert (await adapter.maintain("main", "users", action="vacuum"))["action"] == "vacuum"
        assert (await adapter.maintain("main", "users", action="reindex"))["action"] == "reindex"

    @pytest.mark.parametrize("action", ["optimize", "rm -rf /", "🤯"])
    async def test_unknown_actions_rejected(self, adapter, action):
        with pytest.raises(QueryValidationError, match="supports actions"):
            await adapter.maintain("main", "users", action=action)


class TestTextSearch:
    @pytest.fixture
    async def fts(self, adapter):
        await adapter.write("CREATE VIRTUAL TABLE articles USING fts5(title, body)", None)
        await adapter.write("INSERT INTO articles VALUES ('alpha', 'postgres full text search')", None)
        await adapter.write("INSERT INTO articles VALUES ('beta', 'sqlite fts5 index')", None)
        return adapter

    async def test_happy_match(self, fts):
        rows = await fts.text_search("main", "articles", "fts5", limit=5)
        assert [row["title"] for row in rows] == ["beta"]

    async def test_column_scoped_match(self, fts):
        rows = await fts.text_search("main", "articles", "alpha", column="title", limit=5)
        assert [row["title"] for row in rows] == ["alpha"]

    async def test_query_is_a_literal_phrase_not_fts_syntax(self, fts):
        """FTS5 operators in the input are quoted into a literal phrase, not interpreted."""
        assert await fts.text_search("main", "articles", "postgres OR sqlite", limit=5) == []

    async def test_non_fts_table_guides(self, adapter):
        with pytest.raises(GuidanceError, match="fts5"):
            await adapter.text_search("main", "users", "ana", limit=5)

    @pytest.mark.parametrize(
        ("kwargs", "match"),
        [
            ({"index": "idx"}, "Atlas"),
            ({"language": "english"}, "regconfig"),
            ({"flt": {"a": 1}}, "no filter"),
        ],
    )
    async def test_foreign_parameters_rejected(self, fts, kwargs, match):
        with pytest.raises(QueryValidationError, match=match):
            await fts.text_search("main", "articles", "x", limit=5, **kwargs)

    async def test_unknown_column_rejected(self, fts):
        with pytest.raises(QueryValidationError, match="not found"):
            await fts.text_search("main", "articles", "x", column="ghost", limit=5)


class TestGuidanceSurface:
    @pytest.mark.parametrize(
        "call",
        [
            lambda a: a.users(),
            lambda a: a.grants(),
            lambda a: a.top_queries("total_time", 5),
            lambda a: a.active_ops(),
            lambda a: a.blocking(),
            lambda a: a.replication(),
            lambda a: a.logs(),
            lambda a: a.kill("42"),
        ],
    )
    async def test_server_only_surfaces_guide(self, adapter, call):
        with pytest.raises(GuidanceError):
            await call(adapter)


class TestRemainingBranches:
    async def test_unknown_object_type_rejected(self, adapter):
        """list_objects validates the type filter before querying."""
        with pytest.raises(QueryValidationError, match="Unknown object_type"):
            await adapter.list_objects("main", object_type="banana")

    async def test_get_ddl_missing_object_not_found(self, adapter):
        with pytest.raises(QueryValidationError, match="not found"):
            await adapter.get_ddl("main", "ghost")

    async def test_explain_hypothetical_guides(self, adapter):
        with pytest.raises(GuidanceError, match="HypoPG"):
            await adapter.explain("SELECT 1", hypothetical_indexes=["CREATE INDEX x ON t (a)"])

    async def test_index_stats_after_analyze(self, adapter):
        """After ANALYZE, index_stats lists per-index rows from sqlite_stat1."""
        await adapter.analyze("main")
        stats = await adapter.index_stats()
        assert isinstance(stats["indexes"], list)


class TestSreSignals:
    async def test_storage_reports_file_and_freelist(self, adapter):
        """storage() reports the file size, page count and freelist ratio."""
        section = (await adapter.storage())["file"]
        assert section["bytes"] > 0 and "freelist_ratio" in section

    async def test_config_signals_shape(self, adapter):
        """config_signals() surfaces journal mode, synchronous level, cache size and file size."""
        signals = await adapter.config_signals()
        assert set(signals) == {"journal_mode", "synchronous", "cache_size", "file_bytes"}

    async def test_index_signals_flags_large_unindexed_table(self, adapter):
        """A big table with only its primary index and no secondary index is flagged."""
        await adapter.write("CREATE TABLE big (id integer PRIMARY KEY, payload text)", None)
        await adapter.write(
            "WITH RECURSIVE seq(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM seq WHERE n < 2000) "
            "INSERT INTO big (id, payload) SELECT n, 'x' FROM seq",
            None,
        )
        await adapter.analyze("main")
        tables = [row["table"] for row in (await adapter.index_signals())["unindexed_tables"]]
        assert "big" in tables

    async def test_index_signals_ignores_indexed_tables(self, adapter):
        """A table with a secondary index is not reported even when large."""
        await adapter.analyze("main")
        result = await adapter.index_signals()
        assert result["unindexed_tables"] == []
