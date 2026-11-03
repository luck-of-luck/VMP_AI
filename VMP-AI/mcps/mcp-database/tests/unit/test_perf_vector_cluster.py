"""_summarize_vector and _summarize_cluster turn raw sections into findings + suggested next tools."""

import pytest

from mcp_database.tools.perf_summary import _summarize_cluster, _summarize_vector


class TestSummarizeVector:
    def test_healthy_index_reports_no_findings(self):
        sections = {
            "vector_columns": [{"schema": "public", "table": "docs", "column": "emb", "approx_rows": 1000}],
            "vector_indexes": [
                {"schema": "public", "table": "docs", "column": "emb", "index": "i", "method": "hnsw", "valid": True}
            ],
            "settings": {"hnsw.ef_search": "40", "ivfflat.probes": None},
            "index_builds": [],
        }
        findings, next_steps = _summarize_vector(sections)
        assert any("healthy" in f for f in findings)
        assert next_steps == []

    def test_unindexed_vector_column_is_flagged(self):
        sections = {
            "vector_columns": [{"schema": "public", "table": "docs", "column": "emb", "approx_rows": 10}],
            "vector_indexes": [],
        }
        findings, next_steps = _summarize_vector(sections)
        assert any("without a vector index" in f for f in findings)
        assert any("db_write_search_index" in s for s in next_steps)

    @pytest.mark.parametrize(
        ("rows", "lists", "flagged"),
        [
            (500_000, 10, True),  # far below rows/1000 = 500
            (500_000, 500, False),  # spot on
            (500_000, 5_000, True),  # far above
            (4_000_000, 100, True),  # sqrt(4M) = 2000; 100 is way low
            (4_000_000, 2_000, False),  # sqrt branch, spot on
        ],
    )
    def test_ivfflat_lists_heuristic(self, rows, lists, flagged):
        """lists far from rows/1000 (≤1M rows) or sqrt(rows) (beyond) is flagged with the recommendation."""
        sections = {
            "vector_columns": [{"schema": "s", "table": "t", "column": "e", "approx_rows": rows}],
            "vector_indexes": [
                {
                    "schema": "s",
                    "table": "t",
                    "column": "e",
                    "index": "i",
                    "method": "ivfflat",
                    "options": [f"lists={lists}"],
                    "valid": True,
                }
            ],
        }
        findings, _ = _summarize_vector(sections)
        assert any(f"lists={lists}" in f for f in findings) is flagged

    def test_invalid_index_is_flagged(self):
        findings, _ = _summarize_vector({"vector_indexes": [{"index": "broken", "valid": False}]})
        assert any("invalid" in f and "broken" in f for f in findings)

    def test_builds_in_progress_are_flagged(self):
        findings, _ = _summarize_vector({"vector_indexes": [], "index_builds": [{"pid": 1}, {"pid": 2}]})
        assert any("2 index build(s) in progress" in f for f in findings)

    def test_not_queryable_atlas_index_is_flagged(self):
        sections = {"vector_indexes": [{"index": "v", "status": "BUILDING", "queryable": False}]}
        findings, _ = _summarize_vector(sections)
        assert any("not queryable" in f for f in findings)

    def test_default_probes_is_flagged(self):
        sections = {"vector_indexes": [], "settings": {"ivfflat.probes": "1"}}
        findings, _ = _summarize_vector(sections)
        assert any("probes" in f for f in findings)

    @pytest.mark.parametrize(
        "sections",
        [
            {"vector_indexes": "garbage", "settings": 42, "index_builds": None},
            {"vector_indexes": ["not-a-dict", 42, None], "vector_columns": ["also-garbage"]},
            {"vector_columns": [{"table": None}], "vector_indexes": [{"method": "ivfflat", "options": [123]}]},
            {
                "vector_columns": [{"schema": "s", "table": "t", "column": "e", "approx_rows": 10}],
                "vector_indexes": [
                    {"schema": "s", "table": "t", "column": "e", "method": "ivfflat", "options": ["lists=abc"]}
                ],
            },
            {},
        ],
    )
    def test_absurd_shapes_do_not_crash(self, sections):
        findings, next_steps = _summarize_vector(sections)
        assert isinstance(findings, list) and isinstance(next_steps, list)


class TestSummarizeCluster:
    def test_standalone_is_informational(self):
        findings, _ = _summarize_cluster({"replication": {"role": "standalone"}})
        assert any("no active replication" in f for f in findings)

    @pytest.mark.parametrize(
        ("lag_bytes", "flagged"),
        [(0, False), (64 * 1024 * 1024, False), (64 * 1024 * 1024 + 1, True), (10**12, True)],
    )
    def test_pg_replica_lag_bytes_threshold(self, lag_bytes, flagged):
        sections = {
            "replication": {
                "role": "primary",
                "replicas": [{"application_name": "r1", "state": "streaming", "replay_lag_bytes": lag_bytes}],
            }
        }
        findings, next_steps = _summarize_cluster(sections)
        assert any("behind on WAL replay" in f for f in findings) is flagged
        if flagged:
            assert any("db_perf_replication" in s for s in next_steps)

    @pytest.mark.parametrize(("state", "flagged"), [("streaming", False), ("catchup", True), ("backup", True)])
    def test_pg_replica_state(self, state, flagged):
        sections = {"replication": {"role": "primary", "replicas": [{"client_addr": "10.0.0.2", "state": state}]}}
        findings, _ = _summarize_cluster(sections)
        assert any("expected 'streaming'" in f for f in findings) is flagged

    @pytest.mark.parametrize(("age", "flagged"), [(0, False), (9, False), (10, True), (7200, True)])
    def test_pg_replica_replay_age_threshold(self, age, flagged):
        findings, _ = _summarize_cluster({"replication": {"role": "replica", "replay_age_s": age}})
        assert any("last replayed" in f for f in findings) is flagged

    @pytest.mark.parametrize(
        ("row", "expected"),
        [
            ({"Replica_IO_Running": "No", "Replica_SQL_Running": "Yes"}, "stopped"),
            ({"Replica_IO_Running": "Yes", "Replica_SQL_Running": "Connecting"}, "stopped"),
            ({"Replica_IO_Running": "Yes", "Replica_SQL_Running": "Yes", "Seconds_Behind_Source": 42}, "42s behind"),
            (
                {"Replica_IO_Running": "Yes", "Replica_SQL_Running": "Yes", "Last_Error": "duplicate key"},
                "duplicate key",
            ),
        ],
    )
    def test_mysql_replica_problems(self, row, expected):
        findings, next_steps = _summarize_cluster({"replication": {"role": "replica", "status": [row]}})
        assert any(expected in f for f in findings)
        if expected == "stopped":
            assert any("start_replica" in s for s in next_steps)

    @pytest.mark.parametrize(
        "row",
        [
            {"Replica_IO_Running": "Yes", "Replica_SQL_Running": "Yes", "Seconds_Behind_Source": 0},
            {"Replica_IO_Running": "Yes", "Replica_SQL_Running": "Yes", "Seconds_Behind_Source": 9},
            {"Replica_IO_Running": "Yes", "Replica_SQL_Running": "Yes", "Last_Error": ""},
        ],
    )
    def test_mysql_healthy_replica_rows_stay_quiet(self, row):
        findings, _ = _summarize_cluster({"replication": {"role": "replica", "status": [row]}})
        assert any("healthy" in f for f in findings)

    def test_mongo_no_primary_and_lag(self):
        sections = {
            "replication": {
                "role": "replica_set",
                "members": [
                    {"name": "a", "state": "SECONDARY", "health": 1, "lag_seconds": 42},
                    {"name": "b", "state": "RECOVERING", "health": 0, "lag_seconds": None},
                ],
            }
        }
        findings, _ = _summarize_cluster(sections)
        assert any("no PRIMARY" in f for f in findings)
        assert any("42s behind" in f for f in findings)
        assert any("health=0" in f for f in findings)
        assert any("RECOVERING" in f for f in findings)

    def test_healthy_replica_set(self):
        sections = {
            "replication": {
                "role": "replica_set",
                "members": [
                    {"name": "a", "state": "PRIMARY", "health": 1, "lag_seconds": None},
                    {"name": "b", "state": "SECONDARY", "health": 1, "lag_seconds": 0},
                ],
            },
            "health": {"connections": {"current": 5, "max": 100}},
        }
        findings, next_steps = _summarize_cluster(sections)
        assert any("healthy" in f for f in findings)
        assert next_steps == []

    def test_saturation_reuses_health_section(self):
        findings, _ = _summarize_cluster({"health": {"connections": {"current": 95, "max": 100}}})
        assert any("saturation" in f for f in findings)

    @pytest.mark.parametrize(("lag", "flagged"), [(0, False), (9, False), (10, True), (3600, True)])
    def test_mongo_member_lag_threshold(self, lag, flagged):
        sections = {
            "replication": {
                "role": "replica_set",
                "members": [
                    {"name": "p", "state": "PRIMARY", "health": 1},
                    {"name": "s", "state": "SECONDARY", "health": 1, "lag_seconds": lag},
                ],
            }
        }
        findings, _ = _summarize_cluster(sections)
        assert any("behind the primary" in f for f in findings) is flagged

    @pytest.mark.parametrize(
        "sections",
        [
            {"replication": "garbage", "health": []},
            {"replication": {"role": "replica_set", "members": ["not-a-dict", None, 42]}},
            {"replication": {"replicas": ["junk"], "status": [17], "members": []}},
            {"replication": {"role": None, "replay_age_s": "soon"}, "health": {"connections": "many"}},
        ],
    )
    def test_absurd_shapes_do_not_crash(self, sections):
        findings, next_steps = _summarize_cluster(sections)
        assert isinstance(findings, list) and isinstance(next_steps, list)


class TestClusterFailureFindings:
    def test_paused_replay_finds_and_suggests_resume(self):
        """A paused standby yields the replay-paused finding plus the resume next step."""
        findings, next_steps = _summarize_cluster(
            {"replication": {"role": "replica", "replay_paused": True, "replay_age_s": 0}}
        )
        assert any("WAL replay is paused" in finding for finding in findings)
        assert any("resume_replay" in step for step in next_steps)

    @pytest.mark.parametrize("link", ["down", "connecting", "sync"])
    def test_redis_replica_with_broken_link_is_flagged(self, link):
        """A redis replica whose master link is not up yields the stale-data finding."""
        findings, _ = _summarize_cluster({"replication": {"role": "slave", "master_link_status": link}})
        assert any("lost its master link" in finding for finding in findings)

    def test_redis_replica_with_healthy_link_is_clean(self):
        """A replicating redis replica produces no link finding."""
        findings, _ = _summarize_cluster({"replication": {"role": "slave", "master_link_status": "up"}})
        assert not any("master link" in finding for finding in findings)
