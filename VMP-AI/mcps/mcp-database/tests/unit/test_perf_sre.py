"""The SRE summarizers turn raw engine sections into findings; happy, sad and absurd inputs."""

import pytest

from mcp_database.tools.perf_summary import _summarize_config, _summarize_indexes, _summarize_storage, _summarize_tls


class TestStorage:
    def test_full_filesystem_flagged(self):
        findings, _ = _summarize_storage("mongodb", {"db": {"fs_used_bytes": 90, "fs_total_bytes": 100}})
        assert any("90% full" in finding for finding in findings)

    def test_short_oplog_window_flagged(self):
        findings, _ = _summarize_storage("mongodb", {"oplog": {"window_hours": 0.5}})
        assert any("oplog window" in finding for finding in findings)

    @pytest.mark.parametrize("used", [80, 95, 100])
    def test_redis_memory_pressure(self, used):
        findings, _ = _summarize_storage("redis", {"memory": {"used_bytes": used, "max_bytes": 100}})
        assert any("maxmemory" in finding for finding in findings)

    def test_dead_tuple_bloat_suggests_maintain(self):
        findings, next_steps = _summarize_storage(
            "postgres", {"dead_tuples": [{"relation": "t", "n_live_tup": 100, "n_dead_tup": 30}]}
        )
        assert any("dead tuples" in finding for finding in findings)
        assert any("db_admin_maintain" in step for step in next_steps)

    def test_sqlite_freelist_suggests_vacuum(self):
        findings, next_steps = _summarize_storage("sqlite", {"file": {"freelist_ratio": 0.4}})
        assert any("VACUUM" in finding for finding in findings)
        assert any("vacuum" in step for step in next_steps)

    @pytest.mark.parametrize("sections", [{}, {"db": {}}, {"memory": {"used_bytes": None, "max_bytes": 0}}])
    def test_no_signals_reports_healthy(self, sections):
        findings, _ = _summarize_storage("postgres", sections)
        assert any("healthy" in finding for finding in findings)


class TestTls:
    def test_unreachable_is_reported_not_crashed(self):
        findings, _ = _summarize_tls({"reachable": False, "note": "gaierror", "host": "h"})
        assert any("could not reach" in finding for finding in findings)

    def test_plaintext_remote_host_flagged(self):
        findings, steps = _summarize_tls({"tls": False, "host": "db.example.com", "note": "N"})
        assert any("no TLS" in finding for finding in findings)
        assert steps

    def test_plaintext_local_is_benign(self):
        findings, steps = _summarize_tls({"tls": False, "host": "localhost"})
        assert findings == ["no TLS (local connection)"] and steps == []

    @pytest.mark.parametrize(
        ("days", "needle"),
        [(-3, "expired 3 days ago"), (5, "expires in 5 days"), (20, "expires in 20 days")],
    )
    def test_certificate_expiry_windows(self, days, needle):
        findings, _ = _summarize_tls({"tls": True, "protocol": "TLSv1.3", "certificate": {"days_left": days}})
        assert any(needle in finding for finding in findings)

    def test_self_signed_flagged(self):
        findings, _ = _summarize_tls(
            {"tls": True, "protocol": "TLSv1.3", "certificate": {"days_left": 400, "self_signed": True}}
        )
        assert any("self-signed" in finding for finding in findings)

    def test_healthy_certificate_reports_ok(self):
        findings, _ = _summarize_tls(
            {"tls": True, "protocol": "TLSv1.3", "certificate": {"days_left": 200, "self_signed": False}}
        )
        assert any("healthy" in finding for finding in findings)


class TestConfig:
    def test_low_cache_hit_ratio_flagged(self):
        findings, _ = _summarize_config("postgres", {"cache": {"hits": 80, "reads": 20}})
        assert any("hit ratio" in finding for finding in findings)

    def test_connection_saturation_flagged(self):
        findings, _ = _summarize_config("postgres", {"connections": {"current": 90, "max": 100}})
        assert any("connections at" in finding for finding in findings)

    @pytest.mark.parametrize(
        "config",
        [
            {"maxmemory": "0", "maxmemory-policy": "noeviction"},
            {"maxmemory": "100", "maxmemory-policy": "noeviction"},
            {"maxmemory": "100", "appendonly": "no", "save": ""},
        ],
    )
    def test_redis_config_risks(self, config):
        findings, _ = _summarize_config("redis", {"config": config, "evicted_keys": 0})
        assert findings and "reasonable" not in findings[0]

    def test_undersized_buffer_pool_flagged(self):
        findings, _ = _summarize_config("mysql", {"data_bytes": 1000, "variables": {"innodb_buffer_pool_size": "500"}})
        assert any("buffer_pool" in finding for finding in findings)

    def test_sqlite_non_wal_journal_flagged(self):
        findings, _ = _summarize_config("sqlite", {"journal_mode": "delete"})
        assert any("journal_mode" in finding for finding in findings)

    def test_healthy_config_is_reported(self):
        findings, _ = _summarize_config("postgres", {"cache": {"hits": 999, "reads": 1}})
        assert any("reasonable" in finding for finding in findings)


class TestIndexes:
    def test_unindexed_fk_surfaces_suggestion(self):
        findings, next_steps = _summarize_indexes(
            "postgres",
            {
                "unindexed_foreign_keys": [
                    {"constraint": "fk1", "table": "orders", "columns": "user_id", "suggested": "CREATE INDEX ..."}
                ]
            },
        )
        assert any("no covering index" in finding for finding in findings)
        assert any("hypothetical_indexes" in step for step in next_steps)

    def test_seq_scan_heavy_table_flagged(self):
        findings, _ = _summarize_indexes(
            "postgres", {"seq_scan_heavy": [{"table": "big", "seq_scan": 5000, "n_live_tup": 100000}]}
        )
        assert any("sequential scans" in finding for finding in findings)

    @pytest.mark.parametrize(
        ("key", "row"),
        [("full_scan_tables", {"object_name": "t"}), ("collscans", {"ns": "app.events"})],
    )
    def test_engine_scan_signals(self, key, row):
        findings, _ = _summarize_indexes("mysql", {key: [row]})
        assert any("scans" in finding for finding in findings)

    def test_sqlite_unindexed_table_flagged(self):
        findings, _ = _summarize_indexes("sqlite", {"unindexed_tables": [{"table": "logs", "approx_rows": 50000}]})
        assert any("no secondary index" in finding for finding in findings)

    def test_no_signals_reports_clean(self):
        findings, _ = _summarize_indexes("postgres", {"unindexed_foreign_keys": [], "seq_scan_heavy": []})
        assert any("no obvious missing indexes" in finding for finding in findings)


class TestExtraStorageAndConfigBranches:
    def test_temp_spill_flagged_and_suggests_config(self):
        findings, next_steps = _summarize_storage("postgres", {"temp": {"temp_bytes": 2 << 30}})
        assert any("temp files spilled" in finding for finding in findings)
        assert any("db_perf_config_check" in step for step in next_steps)

    def test_large_binary_logs_flagged(self):
        findings, _ = _summarize_storage("mysql", {"binary_logs": {"bytes": 6 << 30}})
        assert any("binary logs" in finding for finding in findings)

    def test_autovacuum_behind_flagged(self):
        findings, _ = _summarize_config("postgres", {"autovacuum_behind_tables": 3})
        assert any("autovacuum" in finding for finding in findings)

    def test_mysql_tmp_disk_spill_flagged(self):
        findings, _ = _summarize_config("mysql", {"status": {"Created_tmp_disk_tables": 30, "Created_tmp_tables": 100}})
        assert any("spilled to disk" in finding for finding in findings)

    def test_checkpoint_pressure_flagged(self):
        findings, _ = _summarize_config("postgres", {"checkpoints": {"requested": 50, "timed": 10}})
        assert any("checkpoints" in finding for finding in findings)
