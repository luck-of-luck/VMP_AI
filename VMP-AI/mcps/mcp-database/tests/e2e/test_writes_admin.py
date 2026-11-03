"""db_write_ and db_admin_ tools: mode barriers, safety belts and the audit log."""

import json
import logging

import pytest

from mcp_database.audit import AuditLogger
from mcp_database.config import parse_connection
from mcp_database.errors import GuidanceError
from mcp_database.server import build_server

from .helpers import FakeAdapter, call, payload


async def test_write_query_blocked_on_read_only(mcp_server, audit_path):
    result = await call(mcp_server, "db_write_query", {"conn": "ro", "query": "DELETE FROM users"})
    assert result.isError
    assert "read_only" in result.content[0].text
    assert not audit_path.exists()


async def test_write_query_happy_and_audited(mcp_server, audit_path):
    data = payload(await call(mcp_server, "db_write_query", {"conn": "rw", "query": "DELETE FROM users WHERE id = 1"}))
    assert data["applied"] is True
    assert data["operation"] == "delete"
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["tool"] == "db_write_query"
    assert entry["ok"] is True


async def test_write_query_dry_run(mcp_server, audit_path):
    data = payload(
        await call(mcp_server, "db_write_query", {"conn": "rw", "query": "DELETE FROM users", "dry_run": True})
    )
    assert data == {"applied": False, "dry_run": True, "would_affect": 2, "operation": "delete"}
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["dry_run"] is True


async def test_write_query_expected_max_rows_aborts(mcp_server):
    data = payload(
        await call(
            mcp_server,
            "db_write_query",
            {"conn": "rw", "query": "DELETE FROM users", "expected_max_rows": 1},
        )
    )
    assert data["applied"] is False
    assert "aborted" in data


async def test_write_query_absurd_expected_max_rows(mcp_server):
    result = await call(
        mcp_server, "db_write_query", {"conn": "rw", "query": "DELETE FROM users", "expected_max_rows": -1}
    )
    assert result.isError


@pytest.mark.parametrize(
    "query",
    ["DELETE FROM users", "UPDATE users SET plan = 'pro'", "update users set a = 1, b = 2, c = 3"],
)
async def test_unbounded_sql_write_needs_declared_intent(mcp_server, audit_path, query):
    result = await call(mcp_server, "db_write_query", {"conn": "rw", "query": query})
    assert result.isError
    assert "no WHERE clause" in result.content[0].text
    assert not audit_path.exists()  # rejected before touching the database or the audit log


async def test_unbounded_sql_write_allowed_with_expected_max_rows(mcp_server):
    result = await call(
        mcp_server, "db_write_query", {"conn": "rw", "query": "DELETE FROM users", "expected_max_rows": 1000}
    )
    assert not result.isError
    assert payload(result)["applied"] is True


async def test_unbounded_sql_write_allowed_with_dry_run(mcp_server):
    result = await call(mcp_server, "db_write_query", {"conn": "rw", "query": "DELETE FROM users", "dry_run": True})
    assert not result.isError
    assert payload(result)["dry_run"] is True


async def test_bounded_sql_write_passes_without_intent(mcp_server):
    result = await call(mcp_server, "db_write_query", {"conn": "rw", "query": "DELETE FROM users WHERE id = 1"})
    assert not result.isError


async def test_unbounded_mongo_write_needs_declared_intent(mcp_server, audit_path):
    result = await call(
        mcp_server,
        "db_write_query",
        {"conn": "mongo", "query": {"collection": "users", "operation": "deleteMany", "filter": {}}},
    )
    assert result.isError
    assert "every document" in result.content[0].text
    assert not audit_path.exists()


async def test_unbounded_mongo_write_allowed_with_intent(mcp_server):
    ok_bound = await call(
        mcp_server,
        "db_write_query",
        {
            "conn": "mongo",
            "query": {"collection": "users", "operation": "deleteMany", "filter": {}},
            "expected_max_rows": 1000,
        },
    )
    assert not ok_bound.isError

    ok_filter = await call(
        mcp_server,
        "db_write_query",
        {"conn": "mongo", "query": {"collection": "users", "operation": "deleteMany", "filter": {"id": 1}}},
    )
    assert not ok_filter.isError


async def test_write_ops_restriction_enforced(mcp_server):
    ok = await call(mcp_server, "db_write_query", {"conn": "limited", "query": "INSERT INTO t (a) VALUES (1)"})
    assert not ok.isError
    denied = await call(mcp_server, "db_write_query", {"conn": "limited", "query": "DELETE FROM t"})
    assert denied.isError
    assert "write_ops" in denied.content[0].text


async def test_mongo_write_requires_object_query(mcp_server):
    result = await call(mcp_server, "db_write_query", {"conn": "mongo", "query": "DELETE FROM users"})
    assert result.isError

    ok = await call(
        mcp_server,
        "db_write_query",
        {"conn": "mongo", "query": {"collection": "users", "operation": "deleteMany", "filter": {"id": 1}}},
    )
    assert not ok.isError


async def test_write_audit_log_redacts_sql_literals(mcp_server, audit_path):
    await call(
        mcp_server,
        "db_write_query",
        {"conn": "rw", "query": "UPDATE users SET ssn = '123-45-6789' WHERE id = 42"},
    )
    # Assert on the logged query field, not the whole line (ts/duration_ms could coincidentally match).
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["query"] == "UPDATE users SET ssn = ? WHERE id = ?"  # literals never hit the audit log


async def test_write_audit_log_redacts_mongo_values(mcp_server, audit_path):
    await call(
        mcp_server,
        "db_write_query",
        {
            "conn": "mongo",
            "query": {
                "collection": "users",
                "operation": "updateMany",
                "filter": {"ssn": "secret-ssn"},
                "update": {"$set": {"plan": "pro-plan"}},
            },
        },
    )
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["query"]["operation"] == "updateMany"  # operation shape is kept
    assert entry["query"]["filter"] == {"ssn": "?"}  # values redacted, keys kept
    assert entry["query"]["update"] == {"$set": {"plan": "?"}}


async def test_write_failure_is_audited(mcp_server, audit_path, monkeypatch):
    async def failing_write(self, query, params, *, dry_run=False, expected_max_rows=None):
        raise GuidanceError("server rejected the write")

    monkeypatch.setattr(FakeAdapter, "write", failing_write)
    result = await call(mcp_server, "db_write_query", {"conn": "rw", "query": "DELETE FROM users WHERE id = 1"})
    assert result.isError
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["ok"] is False
    assert "server rejected the write" in entry["error"]


async def test_mysql_ddl_dry_run_rejected_with_guidance(mcp_server, audit_path):
    result = await call(mcp_server, "db_write_query", {"conn": "mysql_rw", "query": "DROP TABLE t", "dry_run": True})
    assert result.isError
    assert "implicitly" in result.content[0].text
    assert not audit_path.exists()


async def test_postgres_ddl_dry_run_still_allowed(mcp_server):
    data = payload(await call(mcp_server, "db_write_query", {"conn": "rw", "query": "DROP TABLE t", "dry_run": True}))
    assert data["applied"] is False
    assert data["dry_run"] is True


async def test_mysql_ddl_without_dry_run_still_allowed(mcp_server):
    data = payload(await call(mcp_server, "db_write_query", {"conn": "mysql_rw", "query": "DROP TABLE t"}))
    assert data["applied"] is True


async def test_audit_failure_after_applied_write_is_explicit(mcp_server, monkeypatch):
    def broken_record(self, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(AuditLogger, "record", broken_record)
    result = await call(mcp_server, "db_write_query", {"conn": "rw", "query": "DELETE FROM users WHERE id = 1"})
    assert result.isError
    text = result.content[0].text
    assert "audit logging failed" in text
    assert "applied" in text


async def test_audit_retry_recovers_from_transient_failure(mcp_server, audit_path, monkeypatch):
    """A single transient audit-write failure is absorbed by the retry; the caller sees success and the entry lands."""
    original = AuditLogger.record
    calls = {"n": 0}

    def flaky_record(self, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk hiccup")
        original(self, **kwargs)

    monkeypatch.setattr(AuditLogger, "record", flaky_record)
    data = payload(await call(mcp_server, "db_write_query", {"conn": "rw", "query": "DELETE FROM users WHERE id = 1"}))
    assert data["applied"] is True
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["ok"] is True
    assert calls["n"] == 2


async def test_audit_failure_on_failed_write_keeps_original_error(mcp_server, monkeypatch, caplog):
    """When the write and its audit entry both fail, the caller sees the write's error; the audit failure only warns."""

    async def failing_write(self, query, params, *, dry_run=False, expected_max_rows=None):
        raise GuidanceError("server rejected the write")

    def broken_record(self, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(FakeAdapter, "write", failing_write)
    monkeypatch.setattr(AuditLogger, "record", broken_record)
    with caplog.at_level(logging.WARNING):
        result = await call(mcp_server, "db_write_query", {"conn": "rw", "query": "DELETE FROM users WHERE id = 1"})
    assert result.isError
    text = result.content[0].text
    assert "server rejected the write" in text
    assert "audit logging failed" not in text
    assert any("Audit logging failed" in record.message for record in caplog.records)


async def test_database_modes_double_barrier(monkeypatch, tmp_path):
    monkeypatch.setattr("mcp_database.tools.context.create_adapter", lambda cfg: FakeAdapter(cfg))
    registry = {
        "mixed": parse_connection(
            "mixed",
            {"uri": "mysql://u@h", "access_mode": "read_write", "database_modes": {"prod": "read_only"}},
        )
    }
    srv = build_server(registry, audit=AuditLogger(tmp_path / "a.log"))
    denied = await call(srv, "db_write_query", {"conn": "mixed", "query": "DELETE FROM prod.users WHERE id = 1"})
    assert denied.isError
    assert "prod" in denied.content[0].text
    allowed = await call(srv, "db_write_query", {"conn": "mixed", "query": "DELETE FROM dev.users WHERE id = 1"})
    assert not allowed.isError


async def test_admin_kill_blocked_on_read_only_and_allowed_on_rw(mcp_server, audit_path):
    denied = await call(mcp_server, "db_admin_kill", {"conn": "ro", "target_id": "42"})
    assert denied.isError
    allowed = payload(await call(mcp_server, "db_admin_kill", {"conn": "rw", "target_id": "42"}))
    assert allowed["success"] is True
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["tool"] == "db_admin_kill"


async def test_admin_analyze_happy_and_denied(mcp_server, audit_path):
    allowed = payload(
        await call(mcp_server, "db_admin_analyze", {"conn": "rw", "database": "public", "object": "users"})
    )
    assert allowed["analyzed"] == "public.users"
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["tool"] == "db_admin_analyze"

    denied = await call(mcp_server, "db_admin_analyze", {"conn": "mon", "database": "public"})
    assert denied.isError


async def test_admin_maintain_happy_and_denied(mcp_server, audit_path):
    allowed = payload(
        await call(mcp_server, "db_admin_maintain", {"conn": "rw", "database": "public", "object": "users"})
    )
    assert allowed["maintained"] == "public.users"
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["tool"] == "db_admin_maintain"

    denied = await call(mcp_server, "db_admin_maintain", {"conn": "ro", "database": "public", "object": "users"})
    assert denied.isError
