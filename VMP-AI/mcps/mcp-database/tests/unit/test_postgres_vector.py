"""PostgresAdapter vector/text search and index management assemble SQL from allowlists and binds only."""

import json

import pytest
from psycopg import sql

from mcp_database.adapters.postgres import PostgresAdapter
from mcp_database.config import parse_connection
from mcp_database.errors import GuidanceError, QueryValidationError

EXTENSION = [{"extversion": "0.8.0"}]
COLUMNS = [{"column_name": "id"}, {"column_name": "title"}, {"column_name": "emb"}]


def render(query):
    return query if isinstance(query, str) else query.as_string(None)


def make_adapter(monkeypatch, responses):
    adapter = PostgresAdapter(parse_connection("c", {"uri": "postgresql://u@h/db"}))
    calls = []

    async def fake_fetch(query, params=None, *, limit=None, readonly=True):
        calls.append({"sql": render(query), "params": params, "readonly": readonly})
        return responses.pop(0)

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    return adapter, calls


class TestVectorSearch:
    async def test_happy_cosine(self, monkeypatch):
        adapter, calls = make_adapter(monkeypatch, [EXTENSION, COLUMNS, [{"id": 1, "distance": 0.1}]])
        rows = await adapter.vector_search("public", "items", "emb", [1.0, 2.0], "cosine", 5)
        assert rows == [{"id": 1, "distance": 0.1}]
        statement = calls[-1]["sql"]
        assert '"emb" <=> %s::vector AS distance' in statement
        assert 'FROM "public"."items"' in statement
        assert '"emb",' not in statement
        assert statement.endswith("ORDER BY distance LIMIT 5")
        assert calls[-1]["params"][0] == json.dumps([1.0, 2.0])
        assert calls[-1]["readonly"] is True

    @pytest.mark.parametrize(
        ("metric", "operator"),
        [("cosine", "<=>"), ("l2", "<->"), ("inner_product", "<#>"), ("l1", "<+>")],
    )
    async def test_every_metric_maps_to_its_operator(self, monkeypatch, metric, operator):
        adapter, calls = make_adapter(monkeypatch, [EXTENSION, COLUMNS, []])
        await adapter.vector_search("public", "items", "emb", [0.5], metric, 3)
        assert f'"emb" {operator} %s::vector' in calls[-1]["sql"]

    async def test_filter_keys_are_quoted_and_values_bound(self, monkeypatch):
        adapter, calls = make_adapter(monkeypatch, [EXTENSION, COLUMNS, []])
        await adapter.vector_search("public", "items", "emb", [0.5], "l2", 3, flt={'evil"col': "x"})
        assert 'AND "evil""col" = %s' in calls[-1]["sql"]
        assert calls[-1]["params"][1] == "x"

    async def test_unknown_metric_rejected_before_any_query(self, monkeypatch):
        adapter, calls = make_adapter(monkeypatch, [])
        with pytest.raises(QueryValidationError, match="Unknown metric"):
            await adapter.vector_search("public", "items", "emb", [0.5], "banana", 3)
        assert calls == []

    async def test_mongo_only_parameters_rejected(self, monkeypatch):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(QueryValidationError, match="MongoDB"):
            await adapter.vector_search("public", "items", "emb", [0.5], "l2", 3, index="idx")
        with pytest.raises(QueryValidationError, match="MongoDB"):
            await adapter.vector_search("public", "items", "emb", [0.5], "l2", 3, num_candidates=100)

    async def test_missing_extension_guides(self, monkeypatch):
        adapter, _ = make_adapter(monkeypatch, [[]])
        with pytest.raises(GuidanceError, match="CREATE EXTENSION vector"):
            await adapter.vector_search("public", "items", "emb", [0.5], "l2", 3)

    async def test_injection_column_is_not_found(self, monkeypatch):
        """A column name that is not in information_schema never reaches the statement."""
        adapter, calls = make_adapter(monkeypatch, [EXTENSION, COLUMNS])
        with pytest.raises(QueryValidationError, match="not found"):
            await adapter.vector_search("public", "items", '"; DROP TABLE items--', [0.5], "l2", 3)
        assert len(calls) == 2


class TestTextSearch:
    async def test_happy_default_language(self, monkeypatch):
        adapter, calls = make_adapter(monkeypatch, [COLUMNS, [{"id": 1, "rank": 0.9}]])
        rows = await adapter.text_search("public", "items", "hello world", column="title", limit=10)
        assert rows == [{"id": 1, "rank": 0.9}]
        statement = calls[-1]["sql"]
        assert "websearch_to_tsquery" in statement
        assert '"title"' in statement
        assert statement.endswith("ORDER BY rank DESC LIMIT 10")
        assert calls[-1]["params"] == ["simple", "simple", "hello world", "simple", "simple", "hello world"]

    @pytest.mark.parametrize("language", ["english", "portuguese", "en'; DROP TABLE items;--"])
    async def test_language_is_bound_not_interpolated(self, monkeypatch, language):
        """Any regconfig value — legitimate or hostile — travels as a bind, never inside the SQL text."""
        adapter, calls = make_adapter(monkeypatch, [COLUMNS, []])
        await adapter.text_search("public", "items", "q", column="title", limit=5, language=language)
        assert language not in calls[-1]["sql"]
        assert calls[-1]["params"][0] == language

    async def test_column_is_required(self, monkeypatch):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(QueryValidationError, match="requires 'column'"):
            await adapter.text_search("public", "items", "q", limit=5)

    async def test_atlas_index_parameter_rejected(self, monkeypatch):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(QueryValidationError, match="Atlas"):
            await adapter.text_search("public", "items", "q", column="title", index="default", limit=5)


class TestSearchIndexes:
    async def test_metric_derived_from_definition(self, monkeypatch):
        vector_rows = [
            {"index": "i1", "definition": "CREATE INDEX i1 ... USING hnsw (emb vector_l2_ops)", "valid": True}
        ]
        fulltext_rows = [{"index": "i2", "definition": "CREATE INDEX i2 ... gin (to_tsvector(...))", "valid": True}]
        adapter, _ = make_adapter(monkeypatch, [vector_rows, fulltext_rows])
        result = await adapter.search_indexes("public")
        assert result["indexes"][0]["type"] == "vector"
        assert result["indexes"][0]["metric"] == "l2"
        assert result["indexes"][1]["type"] == "fulltext"


class TestSearchIndexWrite:
    @pytest.mark.parametrize(
        ("definition", "expected_core", "expected_with"),
        [
            (
                {"column": "emb", "method": "hnsw", "metric": "cosine", "options": {"m": 16}},
                'USING hnsw ("emb" vector_cosine_ops)',
                "WITH (m = 16)",
            ),
            (
                {"column": "emb", "method": "hnsw", "metric": "l2", "options": {"m": 8, "ef_construction": 64}},
                'USING hnsw ("emb" vector_l2_ops)',
                "ef_construction = 64",
            ),
            (
                {"column": "emb", "method": "ivfflat", "metric": "inner_product", "options": {"lists": 200}},
                'USING ivfflat ("emb" vector_ip_ops)',
                "WITH (lists = 200)",
            ),
            ({"column": "emb"}, 'USING hnsw ("emb" vector_cosine_ops)', None),
        ],
    )
    async def test_create_variants(self, monkeypatch, definition, expected_core, expected_with):
        """Method/metric/options come from allowlists; defaults are hnsw+cosine with no WITH clause."""
        adapter, calls = make_adapter(monkeypatch, [EXTENSION, []])
        result = await adapter.search_index_write("public", "items", "create", "items_emb_idx", definition)
        statement = calls[-1]["sql"]
        assert 'CREATE INDEX "items_emb_idx" ON "public"."items"' in statement
        assert expected_core in statement
        if expected_with is None:
            assert "WITH" not in statement
        else:
            assert expected_with in statement
        assert calls[-1]["readonly"] is False
        assert result["applied"] is True

    @pytest.mark.parametrize(
        ("name", "rendered"),
        [
            ("items_emb_idx", '"items_emb_idx"'),
            ('weird"name', '"weird""name"'),
            ("índice_🚀", '"índice_🚀"'),
        ],
    )
    async def test_drop_quotes_the_index_name(self, monkeypatch, name, rendered):
        adapter, calls = make_adapter(monkeypatch, [[]])
        await adapter.search_index_write("public", "items", "drop", name)
        assert calls[-1]["sql"] == f'DROP INDEX "public".{rendered}'
        assert calls[-1]["readonly"] is False

    async def test_update_guides_to_recreate(self, monkeypatch):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(GuidanceError, match="drop and recreate"):
            await adapter.search_index_write("public", "items", "update", "idx", {"column": "emb"})

    @pytest.mark.parametrize(
        ("definition", "message"),
        [
            ({}, "definition.column"),
            ({"column": "emb", "method": "btree"}, "Unknown method"),
            ({"column": "emb", "metric": "banana"}, "Unknown metric"),
            ({"column": "emb", "options": {"lists": 10}}, "Unknown hnsw options"),
            ({"column": "emb", "options": {"m": -1}}, "positive integer"),
            ({"column": "emb", "options": {"m": True}}, "positive integer"),
            ({"column": "emb", "options": "m=16"}, "must be an object"),
        ],
    )
    async def test_create_sad_definitions(self, monkeypatch, definition, message):
        adapter, _ = make_adapter(monkeypatch, [EXTENSION])
        with pytest.raises(QueryValidationError, match=message):
            await adapter.search_index_write("public", "items", "create", "idx", definition)

    async def test_unknown_action(self, monkeypatch):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(QueryValidationError, match="Unknown action"):
            await adapter.search_index_write("public", "items", "rebuild", "idx")


class TestClusterAction:
    async def test_promote_happy_on_replica(self, monkeypatch):
        adapter, calls = make_adapter(monkeypatch, [[{"in_recovery": True}], [{"success": True}]])
        result = await adapter.cluster_action("promote")
        assert result == {"action": "promote", "success": True}
        assert calls[-1]["readonly"] is False

    async def test_promote_on_primary_is_rejected(self, monkeypatch):
        adapter, calls = make_adapter(monkeypatch, [[{"in_recovery": False}]])
        with pytest.raises(QueryValidationError, match="is a primary"):
            await adapter.cluster_action("promote")
        assert len(calls) == 1

    @pytest.mark.parametrize("action", ["step_down", "start_replica", "rm -rf /", ""])
    async def test_foreign_actions_guide(self, monkeypatch, action):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(GuidanceError, match="promote"):
            await adapter.cluster_action(action)


def test_identifier_rendering_sanity():
    """as_string(None) renders identifiers with proper double-quote escaping (test-helper invariant)."""
    assert sql.Identifier('evil"col').as_string(None) == '"evil""col"'
