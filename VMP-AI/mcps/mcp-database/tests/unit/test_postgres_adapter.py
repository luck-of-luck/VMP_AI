"""PostgresAdapter unit behaviors that real containers never reach: error branches, filters, replica paths."""

import psycopg
import pytest

from mcp_database.adapters.postgres import PostgresAdapter
from mcp_database.config import parse_connection
from mcp_database.errors import GuidanceError, QueryValidationError


def render(query):
    return query if isinstance(query, str) else query.as_string(None)


def make_adapter(monkeypatch, responses):
    adapter = PostgresAdapter(parse_connection("c", {"uri": "postgresql://u@h/db"}))
    calls = []

    async def fake_fetch(query, params=None, *, limit=None, readonly=True):
        calls.append({"sql": render(query), "params": params, "readonly": readonly})
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    return adapter, calls


class FakeCursor:
    def __init__(self, rows=None, rowcount=0):
        self._rows = rows or []
        self.rowcount = rowcount

    async def fetchall(self):
        return self._rows


class _NullCM:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, cursor):
        self._cursor = cursor
        self.executed = []
        self.rolled_back = False

    async def execute(self, query, params=None):
        self.executed.append((render(query), params))
        return self._cursor

    async def rollback(self):
        self.rolled_back = True

    def transaction(self):
        return _NullCM()


class FakePool:
    def __init__(self, conn):
        self._conn = conn

    def connection(self):
        conn = self._conn

        class _CM:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, *exc):
                return False

        return _CM()


def use_pool(monkeypatch, adapter, conn):
    async def fake_ensure_pool():
        return FakePool(conn)

    monkeypatch.setattr(adapter, "_ensure_pool", fake_ensure_pool)


@pytest.mark.parametrize(
    ("exc", "transient"),
    [
        (psycopg.OperationalError("connection unexpectedly closed"), True),
        (psycopg.errors.ConnectionFailure("server closed the connection"), True),
        (psycopg.errors.ConnectionException("bad connection"), True),
        (psycopg.errors.QueryCanceled("canceling statement due to statement timeout"), False),
        (psycopg.errors.SyntaxError("syntax error"), False),
        (ValueError("boom"), False),
    ],
)
def test_is_transient_classification(exc, transient):
    """Only connection-level failures (no sqlstate / class 08) are transient; cancels and SQL errors are not."""
    assert PostgresAdapter._is_transient(exc) is transient


class TestGetDdl:
    async def test_view_returns_create_or_replace(self, monkeypatch):
        """A view's DDL comes from pg_get_viewdef as CREATE OR REPLACE VIEW."""
        adapter, _ = make_adapter(monkeypatch, [[{"definition": "SELECT 1;"}]])

        async def is_view(database, obj):
            return True

        monkeypatch.setattr(adapter, "_is_view", is_view)
        result = await adapter.get_ddl("public", "v_users")
        assert result["ddl"].startswith('CREATE OR REPLACE VIEW "public"."v_users" AS')
        assert "SELECT 1;" in result["ddl"]

    async def test_missing_object_raises_not_found(self, monkeypatch):
        """An object with no columns raises a clear not-found error, never an empty DDL."""
        adapter, _ = make_adapter(monkeypatch, [])

        async def is_view(database, obj):
            return False

        async def describe(database, obj, *, sample=True):
            return {"columns": [], "constraints": [], "indexes": []}

        monkeypatch.setattr(adapter, "_is_view", is_view)
        monkeypatch.setattr(adapter, "describe_object", describe)
        with pytest.raises(QueryValidationError, match="not found"):
            await adapter.get_ddl("public", "ghost")


class TestOptionalFilters:
    async def test_relationships_object_filter_binds_both_sides(self, monkeypatch):
        """Filtering relationships by object binds the name for source and target tables."""
        adapter, calls = make_adapter(monkeypatch, [[]])
        await adapter.relationships("public", obj="users")
        assert "src.relname = %s OR tgt.relname = %s" in calls[-1]["sql"]
        assert calls[-1]["params"] == ["public", "users", "users"]

    async def test_grants_user_and_object_filters_bind(self, monkeypatch):
        """Filtering grants by user and object appends both as binds."""
        adapter, calls = make_adapter(monkeypatch, [[]])
        await adapter.grants(user="dev", obj="users")
        assert "grantee = %s" in calls[-1]["sql"]
        assert "table_name = %s" in calls[-1]["sql"]
        assert calls[-1]["params"] == ["dev", "users"]


class TestSampleFallback:
    async def test_tablesample_with_enough_rows_skips_the_fallback(self, monkeypatch):
        """When TABLESAMPLE already yields n rows, no LIMIT fallback query runs."""
        rows = [{"id": 1}, {"id": 2}]
        adapter, calls = make_adapter(monkeypatch, [rows])
        assert await adapter.sample("public", "users", 2) == rows
        assert len(calls) == 1
        assert "TABLESAMPLE" in calls[0]["sql"]

    async def test_tablesample_unsupported_falls_back_to_limit(self, monkeypatch):
        """Views reject TABLESAMPLE; the sample silently falls back to a plain LIMIT."""
        adapter, calls = make_adapter(
            monkeypatch,
            [psycopg.errors.FeatureNotSupported("TABLESAMPLE not supported"), [{"id": 1}]],
        )
        rows = await adapter.sample("public", "v_users", 5)
        assert rows == [{"id": 1}]
        assert "TABLESAMPLE" not in calls[-1]["sql"]
        assert calls[-1]["sql"].endswith("LIMIT 5")


class TestWithCost:
    @pytest.mark.parametrize("plan", [None, [], [{"no_plan_key": True}]])
    def test_malformed_plan_returns_without_cost(self, plan):
        """Plans missing Total Cost yield no estimated_cost instead of crashing."""
        adapter = PostgresAdapter(parse_connection("c", {"uri": "postgresql://u@h/db"}))
        result = adapter._with_cost(plan)
        assert result == {"plan": plan}


class TestHypotheticalExplain:
    async def test_happy_path_creates_explains_and_resets(self, monkeypatch):
        """HypoPG indexes are created, the plan captured, and the session reset on one connection."""
        adapter, _ = make_adapter(monkeypatch, [[{"?column?": 1}]])
        conn = FakeConn(FakeCursor(rows=[{"QUERY PLAN": [{"Plan": {"Total Cost": 1.0}}]}]))
        use_pool(monkeypatch, adapter, conn)
        result = await adapter._explain_hypothetical("SELECT * FROM t", ["CREATE INDEX ON t (a)"], analyze=False)
        assert result["plan"] == [{"Plan": {"Total Cost": 1.0}}]
        assert result["hypothetical_indexes"] == ["CREATE INDEX ON t (a)"]
        statements = [statement for statement, _ in conn.executed]
        assert any("hypopg_create_index" in statement for statement in statements)
        assert any("hypopg_reset" in statement for statement in statements)
        assert conn.rolled_back


class TestGuidanceBranches:
    async def test_top_queries_without_pg_stat_statements(self, monkeypatch):
        """Missing pg_stat_statements raises GuidanceError with the enabling command."""
        adapter, _ = make_adapter(monkeypatch, [[]])
        with pytest.raises(GuidanceError, match="CREATE EXTENSION pg_stat_statements"):
            await adapter.top_queries("total_time", 10)


class TestReplication:
    @pytest.mark.parametrize(
        ("age_rows", "expected_age"),
        [([{"replay_age_s": 7}], 7), ([{"replay_age_s": 0}], 0), ([], None)],
    )
    async def test_replica_reports_receiver_and_replay_age(self, monkeypatch, age_rows, expected_age):
        """On a replica, replication() surfaces the WAL receiver, the replay age and the pause flag."""
        receiver = [{"status": "streaming", "sender_host": "primary", "sender_port": 5432}]
        adapter, _ = make_adapter(monkeypatch, [[{"in_recovery": True}], receiver, age_rows, [{"paused": False}]])
        result = await adapter.replication()
        assert result["role"] == "replica"
        assert result["receiver"] == receiver
        assert result["replay_age_s"] == expected_age
        assert result["replay_paused"] is False


class TestLogs:
    async def test_happy_path_filters_by_level_and_tails(self, monkeypatch):
        """logs() reads the current logfile tail and filters lines by level."""
        chunk = "ERROR: broken\nLOG: fine\n\nERROR: again\n"
        adapter, _ = make_adapter(
            monkeypatch,
            [[{"logfile": "log/postgresql.log"}], [{"size": 100}], [{"chunk": chunk}]],
        )
        lines = await adapter.logs(limit=1, level="error")
        assert lines == [{"line": "ERROR: again"}]

    async def test_privilege_error_becomes_guidance(self, monkeypatch):
        """A pg_stat_file failure maps to GuidanceError naming the required role."""
        adapter, _ = make_adapter(
            monkeypatch,
            [[{"logfile": "log/postgresql.log"}], psycopg.errors.InsufficientPrivilege("denied")],
        )
        with pytest.raises(GuidanceError, match="pg_read_server_files"):
            await adapter.logs()


class TestWriteRollback:
    async def test_dry_run_executes_then_rolls_back(self, monkeypatch):
        """A non-probeable dry_run executes in a transaction and exits via the rollback sentinel."""
        adapter, _ = make_adapter(monkeypatch, [])

        async def no_estimate(query, params):
            return None

        monkeypatch.setattr(adapter, "_estimate_affected", no_estimate)
        conn = FakeConn(FakeCursor(rowcount=3))
        use_pool(monkeypatch, adapter, conn)
        outcome = await adapter.write("UPDATE t SET a = 1 WHERE id IN (SELECT id FROM u)", None, dry_run=True)
        assert outcome == {"applied": False, "dry_run": True, "would_affect": 3}


class TestEstimateAffected:
    @pytest.mark.parametrize(
        "query",
        ["UPDATE (((", "DELETE FROM t USING u WHERE t.id = u.id", "CREATE TABLE t (id int)"],
    )
    async def test_unparseable_or_unprobeable_returns_none(self, monkeypatch, query):
        """Broken SQL and non-simple statements fall back to execute+rollback (None estimate)."""
        adapter, calls = make_adapter(monkeypatch, [])
        assert await adapter._estimate_affected(query, None) is None
        assert calls == []


class TestSearchValidation:
    async def test_column_names_missing_object_raises(self, monkeypatch):
        """An unknown object raises not-found instead of returning an empty column list."""
        adapter, _ = make_adapter(monkeypatch, [[]])
        with pytest.raises(QueryValidationError, match="not found"):
            await adapter._column_names("public", "ghost")

    async def test_text_search_unknown_column_rejected(self, monkeypatch):
        """text_search validates the column against the object's real columns before building SQL."""
        adapter, _ = make_adapter(monkeypatch, [[{"column_name": "title"}]])
        with pytest.raises(QueryValidationError, match="Column 'body' not found"):
            await adapter.text_search("public", "articles", "hello", column="body", limit=5)


class TestVectorStats:
    async def test_sections_shape_and_vector_index_filter(self, monkeypatch):
        """vector_stats returns extension, columns, vector-only indexes, GUCs and in-flight builds."""
        columns = [{"schema": "public", "table": "articles", "column": "emb", "dimensions": 3, "approx_rows": 10}]
        settings = [{"hnsw.ef_search": "40", "ivfflat.probes": None}]
        builds = [{"pid": 1, "phase": "building index"}]
        adapter, _ = make_adapter(monkeypatch, [columns, settings, builds])

        async def version():
            return "0.8.0"

        async def indexes(database=None, obj=None):
            return {"indexes": [{"type": "vector", "index": "i_vec"}, {"type": "fulltext", "index": "i_fts"}]}

        monkeypatch.setattr(adapter, "_pgvector_version", version)
        monkeypatch.setattr(adapter, "search_indexes", indexes)
        result = await adapter.vector_stats("public", "articles")
        assert result["extension"] == {"name": "vector", "version": "0.8.0"}
        assert result["vector_columns"] == columns
        assert [index["index"] for index in result["vector_indexes"]] == ["i_vec"]
        assert result["settings"] == settings[0]
        assert result["index_builds"] == builds


class TestClusterActions:
    @pytest.mark.parametrize(
        ("action", "statement"),
        [("pause_replay", "pg_wal_replay_pause"), ("resume_replay", "pg_wal_replay_resume")],
    )
    async def test_replay_actions_run_on_a_replica(self, monkeypatch, action, statement):
        """pause/resume_replay execute their fixed statement after the recovery pre-check."""
        adapter, calls = make_adapter(monkeypatch, [[{"in_recovery": True}], []])
        outcome = await adapter.cluster_action(action)
        assert outcome == {"action": action, "success": True}
        assert statement in calls[-1]["sql"] and calls[-1]["readonly"] is False

    @pytest.mark.parametrize("action", ["promote", "pause_replay", "resume_replay"])
    async def test_replica_actions_rejected_on_a_primary(self, monkeypatch, action):
        """Every replica-only action is refused with a clear error on a primary."""
        adapter, _ = make_adapter(monkeypatch, [[{"in_recovery": False}]])
        with pytest.raises(QueryValidationError, match="applies to a streaming replica"):
            await adapter.cluster_action(action)

    @pytest.mark.parametrize("action", ["step_down", "freeze", "rm -rf /"])
    async def test_foreign_actions_guide(self, monkeypatch, action):
        """Actions from other engines name the PostgreSQL set instead of running anything."""
        adapter, calls = make_adapter(monkeypatch, [])
        with pytest.raises(GuidanceError, match="pause_replay"):
            await adapter.cluster_action(action)
        assert calls == []


class TestStorageBranches:
    async def test_wal_unavailable_degrades(self, monkeypatch):
        """A pg_ls_waldir permission error becomes an 'unavailable' section, not a failure."""
        responses = [
            [{"database": "app", "bytes": 1}],
            [{"schema": "public", "relation": "t", "kind": "r", "total_bytes": 1}],
            psycopg.errors.InsufficientPrivilege("pg_monitor needed"),
            [{"temp_files": 0, "temp_bytes": 0}],
            [],
        ]
        adapter, _ = make_adapter(monkeypatch, responses)
        sections = await adapter.storage()
        assert "unavailable" in sections["wal"]

    async def test_config_falls_back_to_bgwriter_on_old_pg(self, monkeypatch):
        """pg16 has no pg_stat_checkpointer; config_signals falls back to pg_stat_bgwriter."""
        responses = [
            [{"hits": 99, "reads": 1}],
            [{"current": 1, "max": 100}],
            [{"behind": 0}],
            psycopg.errors.UndefinedTable("pg_stat_checkpointer"),
            [{"timed": 5, "requested": 1}],
            [{"name": "work_mem", "setting": "4MB"}],
            [{"streaming": 0}],
        ]
        adapter, _ = make_adapter(monkeypatch, responses)
        signals = await adapter.config_signals()
        assert signals["checkpoints"] == {"timed": 5, "requested": 1}
