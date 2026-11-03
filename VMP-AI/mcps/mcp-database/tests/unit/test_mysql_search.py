"""MySQLAdapter FULLTEXT search/index management and replica actions build SQL from quoted identifiers only."""

import pytest
from pymysql.err import OperationalError

from mcp_database.adapters.mysql import MySQLAdapter
from mcp_database.config import parse_connection
from mcp_database.errors import GuidanceError, QueryValidationError


def make_adapter(monkeypatch, responses):
    adapter = MySQLAdapter(parse_connection("c", {"uri": "mysql://u@h/db"}))
    calls = []

    async def fake_fetch(query, params=None, *, limit=None, readonly=True):
        calls.append({"sql": query, "params": params, "readonly": readonly})
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    return adapter, calls


class TestTextSearch:
    async def test_happy(self, monkeypatch):
        adapter, calls = make_adapter(monkeypatch, [[{"id": 1, "score": 1.2}]])
        rows = await adapter.text_search("shop", "products", "wireless mouse", column="description", limit=10)
        assert rows == [{"id": 1, "score": 1.2}]
        statement = calls[-1]["sql"]
        assert "MATCH (`description`) AGAINST (%s IN NATURAL LANGUAGE MODE)" in statement
        assert "FROM `shop`.`products`" in statement
        assert statement.endswith("ORDER BY score DESC LIMIT 10")
        assert calls[-1]["params"] == ["wireless mouse", "wireless mouse"]

    async def test_filter_values_are_bound(self, monkeypatch):
        adapter, calls = make_adapter(monkeypatch, [[]])
        await adapter.text_search("shop", "products", "q", column="name", limit=5, flt={"brand": "acme"})
        assert "AND `brand` = %s" in calls[-1]["sql"]
        assert calls[-1]["params"] == ["q", "q", "acme"]

    @pytest.mark.parametrize(
        "error",
        [
            OperationalError(1191, "Can't find FULLTEXT index matching the column list"),
            OperationalError(1214, "The used table type doesn't support FULLTEXT indexes"),
        ],
    )
    async def test_missing_fulltext_index_guides(self, monkeypatch, error):
        adapter, _ = make_adapter(monkeypatch, [error])
        with pytest.raises(GuidanceError, match="db_write_search_index"):
            await adapter.text_search("shop", "products", "q", column="name", limit=5)

    @pytest.mark.parametrize(
        "error",
        [
            OperationalError(1045, "Access denied"),
            OperationalError(2013, "Lost connection"),
            OperationalError(1064, "You have an error in your SQL syntax"),
        ],
    )
    async def test_unrelated_errors_are_not_masked(self, monkeypatch, error):
        adapter, _ = make_adapter(monkeypatch, [error])
        with pytest.raises(OperationalError):
            await adapter.text_search("shop", "products", "q", column="name", limit=5)

    async def test_column_required_and_foreign_params_rejected(self, monkeypatch):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(QueryValidationError, match="requires 'column'"):
            await adapter.text_search("shop", "products", "q", limit=5)
        with pytest.raises(QueryValidationError, match="Atlas"):
            await adapter.text_search("shop", "products", "q", column="name", index="default", limit=5)
        with pytest.raises(QueryValidationError, match="PostgreSQL"):
            await adapter.text_search("shop", "products", "q", column="name", language="english", limit=5)


class TestSearchIndexes:
    async def test_rows_are_typed_fulltext(self, monkeypatch):
        adapter, calls = make_adapter(
            monkeypatch, [[{"database": "shop", "table": "products", "index": "ft", "columns": "name"}]]
        )
        result = await adapter.search_indexes("shop")
        assert result["indexes"][0]["type"] == "fulltext"
        assert "index_type = 'FULLTEXT'" in calls[-1]["sql"]


class TestSearchIndexWrite:
    @pytest.mark.parametrize(
        ("definition", "column_list"),
        [
            ({"columns": ["name"]}, "(`name`)"),
            ({"columns": ["name", "descr`iption"]}, "(`name`, `descr``iption`)"),
            ({"column": "body"}, "(`body`)"),
        ],
    )
    async def test_create(self, monkeypatch, definition, column_list):
        adapter, calls = make_adapter(monkeypatch, [[]])
        result = await adapter.search_index_write("shop", "products", "create", "ft_name", definition)
        assert calls[-1]["sql"] == f"CREATE FULLTEXT INDEX `ft_name` ON `shop`.`products` {column_list}"
        assert calls[-1]["readonly"] is False
        assert result["applied"] is True
        assert "implicitly" in result["note"]

    async def test_drop(self, monkeypatch):
        adapter, calls = make_adapter(monkeypatch, [[]])
        await adapter.search_index_write("shop", "products", "drop", "ft_name")
        assert calls[-1]["sql"] == "ALTER TABLE `shop`.`products` DROP INDEX `ft_name`"

    async def test_update_guides(self, monkeypatch):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(GuidanceError, match="drop and recreate"):
            await adapter.search_index_write("shop", "products", "update", "ft")

    @pytest.mark.parametrize("definition", [None, {}, {"columns": []}, {"columns": [1]}, {"columns": "name"}])
    async def test_create_sad_definitions(self, monkeypatch, definition):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(QueryValidationError, match=r"definition\.columns"):
            await adapter.search_index_write("shop", "products", "create", "ft", definition)


class TestClusterAction:
    async def test_stop_replica_happy(self, monkeypatch):
        adapter, calls = make_adapter(monkeypatch, [[{"Replica_IO_Running": "Yes"}], []])
        result = await adapter.cluster_action("stop_replica")
        assert result == {"action": "stop_replica", "success": True}
        assert calls[-1]["sql"] == "STOP REPLICA"
        assert calls[-1]["readonly"] is False

    async def test_not_a_replica_guides(self, monkeypatch):
        adapter, _ = make_adapter(monkeypatch, [[]])
        with pytest.raises(GuidanceError, match="no replication source"):
            await adapter.cluster_action("start_replica")

    @pytest.mark.parametrize("action", ["promote", "step_down", "DROP TABLE", ""])
    async def test_foreign_actions_guide(self, monkeypatch, action):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(GuidanceError, match="start_replica"):
            await adapter.cluster_action(action)

    async def test_seconds_rejected(self, monkeypatch):
        adapter, _ = make_adapter(monkeypatch, [])
        with pytest.raises(QueryValidationError, match="MongoDB"):
            await adapter.cluster_action("stop_replica", seconds=30)


class TestSearchIndexUnknownAction:
    @pytest.mark.parametrize("action", ["banana", "recreate", ""])
    async def test_unknown_action_rejected(self, monkeypatch, action):
        """Actions outside create/update/drop are rejected before touching the database."""
        adapter, calls = make_adapter(monkeypatch, [])
        with pytest.raises(QueryValidationError, match="Unknown action"):
            await adapter.search_index_write("shop", "products", action, "ft")
        assert calls == []
