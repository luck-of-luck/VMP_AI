"""SQLAdapter static helpers shared by every SQL engine: write protocol, kill-target parsing, LIKE escaping."""

import pytest

from mcp_database.adapters.base import Adapter, SQLAdapter
from mcp_database.errors import GuidanceError, QueryValidationError


class TestWriteOutcome:
    """_write_outcome decides what a write reports and whether the caller commits."""

    def test_applied(self):
        """A plain write reports applied+affected and tells the caller to commit."""
        outcome, commit = SQLAdapter._write_outcome(3, dry_run=False, expected_max_rows=None)
        assert outcome == {"applied": True, "affected": 3}
        assert commit is True

    def test_dry_run_rolls_back(self):
        """dry_run reports would_affect without applying and tells the caller to roll back."""
        outcome, commit = SQLAdapter._write_outcome(5, dry_run=True, expected_max_rows=None)
        assert outcome == {"applied": False, "dry_run": True, "would_affect": 5}
        assert commit is False

    def test_abort_beats_dry_run(self):
        """When the affected count exceeds expected_max_rows, the abort wins even if dry_run was also set."""
        outcome, commit = SQLAdapter._write_outcome(10, dry_run=True, expected_max_rows=2)
        assert outcome["applied"] is False
        assert "above expected_max_rows=2" in outcome["aborted"]
        assert "dry_run" not in outcome
        assert commit is False

    def test_boundary_equal_rows_applies(self):
        """affected == expected_max_rows is within the declared budget, so the write applies."""
        outcome, commit = SQLAdapter._write_outcome(2, dry_run=False, expected_max_rows=2)
        assert outcome == {"applied": True, "affected": 2}
        assert commit is True

    def test_zero_affected_applies(self):
        """A write that matches zero rows still applies (and commits) rather than erroring."""
        outcome, commit = SQLAdapter._write_outcome(0, dry_run=False, expected_max_rows=None)
        assert outcome == {"applied": True, "affected": 0}
        assert commit is True


def test_is_transient_defaults_to_false():
    """Without an engine override, no error is considered transient — retry stays opt-in per engine."""
    assert SQLAdapter._is_transient(RuntimeError("anything")) is False


class TestCapabilities:
    """Each engine declares the feature set that differs across engines, all within CAPABILITY_NAMES."""

    def _adapter(self, cls, uri):
        from mcp_database.config import parse_connection

        return cls(parse_connection("c", {"uri": uri}))

    def test_postgres_supports_the_full_set(self):
        from mcp_database.adapters.base import CAPABILITY_NAMES
        from mcp_database.adapters.postgres import PostgresAdapter

        caps = self._adapter(PostgresAdapter, "postgresql://u@h/db").capabilities()
        assert set(caps) == CAPABILITY_NAMES
        assert self._adapter(PostgresAdapter, "postgresql://u@h/db").supports("hypothetical_indexes")

    def test_mysql_is_a_strict_subset(self):
        from mcp_database.adapters.mysql import MySQLAdapter

        adapter = self._adapter(MySQLAdapter, "mysql://u@h/db")
        assert adapter.capabilities() == ["column_stats", "planner_analyze"]
        assert not adapter.supports("hypothetical_indexes")

    def test_mongodb_samples_and_vector_searches(self):
        from mcp_database.adapters.mongodb import MongoAdapter

        adapter = self._adapter(MongoAdapter, "mongodb://h/db")
        assert adapter.capabilities() == ["server_side_sampling", "vector_search"]
        assert not adapter.supports("column_stats")

    def test_declared_capabilities_are_all_known(self):
        from mcp_database.adapters.base import CAPABILITY_NAMES
        from mcp_database.adapters.mongodb import MongoAdapter
        from mcp_database.adapters.mysql import MySQLAdapter
        from mcp_database.adapters.postgres import PostgresAdapter

        for cls in (PostgresAdapter, MySQLAdapter, MongoAdapter):
            assert cls.CAPABILITIES <= CAPABILITY_NAMES


class TestSearchAndClusterDefaults:
    """The ABC defaults for search/vector/cluster raise GuidanceError naming the engine, never crash."""

    class _Bare:
        config = type("Cfg", (), {"type": "someengine"})()

    async def test_vector_search_default(self):
        with pytest.raises(GuidanceError, match="someengine has no vector similarity search"):
            await Adapter.vector_search(self._Bare(), "db", "t", "emb", [1.0], "cosine", 10)

    async def test_text_search_default(self):
        with pytest.raises(GuidanceError, match="someengine has no full-text search"):
            await Adapter.text_search(self._Bare(), "db", "t", "hello", limit=10)

    async def test_search_indexes_default(self):
        with pytest.raises(GuidanceError, match="no vector or full-text indexes"):
            await Adapter.search_indexes(self._Bare())

    async def test_vector_stats_default(self):
        with pytest.raises(GuidanceError, match="no vector search support"):
            await Adapter.vector_stats(self._Bare())

    async def test_search_index_write_default(self):
        with pytest.raises(GuidanceError, match="no vector or full-text indexes to manage"):
            await Adapter.search_index_write(self._Bare(), "db", "t", "create", "idx")

    async def test_cluster_action_default_names_the_action(self):
        with pytest.raises(GuidanceError, match="no cluster action 'step_down'"):
            await Adapter.cluster_action(self._Bare(), "step_down")

    async def test_storage_default(self):
        with pytest.raises(GuidanceError, match="no storage breakdown"):
            await Adapter.storage(self._Bare())

    async def test_config_signals_default(self):
        with pytest.raises(GuidanceError, match="no configuration signals"):
            await Adapter.config_signals(self._Bare())

    async def test_index_signals_default(self):
        with pytest.raises(GuidanceError, match="no index usage statistics"):
            await Adapter.index_signals(self._Bare())


class TestIntTarget:
    """_int_target parses a kill target id, rejecting anything non-numeric before it reaches SQL."""

    def test_happy(self):
        """A numeric string parses to the int the KILL statement needs."""
        assert SQLAdapter._int_target("42", "pid") == 42

    @pytest.mark.parametrize("value", ["abc", "", "12.5", "1; DROP TABLE t", "🤖"])
    def test_sad(self, value):
        """Non-numeric targets (text, empty, float, injection, emoji) are rejected with a clear error."""
        with pytest.raises(QueryValidationError, match="numeric"):
            SQLAdapter._int_target(value, "pid")


class TestLikeContains:
    """_like_contains turns a user search string into a literal %substring% LIKE argument."""

    def test_plain_text_is_wrapped(self):
        """Plain text is only wrapped in % anchors, nothing else changes."""
        assert SQLAdapter._like_contains("orders") == "%orders%"

    def test_wildcards_become_literals(self):
        """The LIKE wildcards % _ \\ are escaped so user input never acts as a pattern language."""
        assert SQLAdapter._like_contains("%_\\") == "%\\%\\_\\\\%"

    def test_unicode_untouched(self):
        """Unicode text passes through unescaped — only the three wildcard characters are special."""
        assert SQLAdapter._like_contains("José🚀") == "%José🚀%"

    def test_empty_pattern_matches_everything(self):
        """An empty search string becomes %%, the match-all pattern."""
        assert SQLAdapter._like_contains("") == "%%"
