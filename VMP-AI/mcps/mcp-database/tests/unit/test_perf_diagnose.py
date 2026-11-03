"""_summarize_diagnosis turns raw diagnosis sections into findings + suggested next tools."""

from mcp_database.tools.perf_summary import _summarize_diagnosis


def test_clean_system_reports_no_contention():
    findings, next_steps = _summarize_diagnosis(
        {"health": {"connections": {"current": 2, "max": 100}}, "active_ops": [], "blocking": [], "top_queries": []}
    )
    assert any("no obvious contention" in f for f in findings)
    assert next_steps == []


def test_slow_operation_is_flagged_with_next_step():
    findings, next_steps = _summarize_diagnosis({"active_ops": [{"duration_ms": 5000, "query": "SELECT ..."}]})
    assert any("1s or longer" in f for f in findings)
    assert any("db_perf_explain" in s for s in next_steps)


def test_idle_in_transaction_is_flagged():
    findings, _ = _summarize_diagnosis({"active_ops": [{"duration_ms": 10, "xact_age_ms": 120_000}]})
    assert any("open 60s or longer" in f for f in findings)


def test_lock_waits_suggest_kill():
    findings, next_steps = _summarize_diagnosis({"blocking": [{"blocked_pid": 1, "blocking_pid": 2}]})
    assert any("lock wait" in f for f in findings)
    assert any("db_admin_kill" in s for s in next_steps)


def test_connection_saturation_is_flagged():
    findings, _ = _summarize_diagnosis({"health": {"connections": {"current": 90, "max": 100}}})
    assert any("near saturation" in f for f in findings)


def test_unavailable_sections_are_tolerated():
    """A feature-gated section arrives as {'unavailable': ...}; the summary must not crash on it."""
    findings, next_steps = _summarize_diagnosis(
        {"health": {"unavailable": "no privilege"}, "top_queries": {"unavailable": "pg_stat_statements missing"}}
    )
    assert findings  # falls back to the no-contention message
    assert next_steps == []


def test_absurd_section_shapes_do_not_crash():
    findings, next_steps = _summarize_diagnosis({"active_ops": "garbage", "blocking": None, "health": 42})
    assert isinstance(findings, list) and isinstance(next_steps, list)
