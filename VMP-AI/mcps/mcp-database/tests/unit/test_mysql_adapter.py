"""MySQLAdapter connection lifecycle, tested with in-memory fakes (no Docker).

Covers the invariant that a cancelled write closes its connection so the poisoned
connection never returns to the pool, and the commit/rollback protocol around writes and reads.
"""

import asyncio

import pytest
from pymysql.err import OperationalError

from mcp_database.adapters.base import SQLAdapter
from mcp_database.adapters.mysql import MySQLAdapter
from mcp_database.config import parse_connection
from mcp_database.errors import GuidanceError, QueryValidationError


class FakeCursor:
    """aiomysql cursor double: records executed queries, serves canned rows, can fail on demand."""

    def __init__(self, fail_with=None):
        self._fail_with = fail_with
        self.rowcount = 3
        self.rows = []
        self.closed = False
        self.executed = []

    async def execute(self, query, params=None):
        self.executed.append(query)
        if self._fail_with is not None:
            raise self._fail_with

    async def fetchall(self):
        return self.rows

    async def fetchmany(self, n):
        return self.rows[:n]

    async def close(self):
        self.closed = True


class FakeCursorHandle:
    """Mimics aiomysql's cursor handle, which is both awaitable and an async context manager."""

    def __init__(self, cursor):
        self._cursor = cursor

    def __await__(self):
        async def resolve():
            return self._cursor

        return resolve().__await__()

    async def __aenter__(self):
        return self._cursor

    async def __aexit__(self, *exc):
        await self._cursor.close()
        return False


class FakeConn:
    """aiomysql connection double: counts commits/rollbacks and tracks close()."""

    def __init__(self, fail_with=None):
        self.closed = False
        self.commits = 0
        self.rollbacks = 0
        self.cursor_obj = FakeCursor(fail_with)

    def cursor(self, *args):
        return FakeCursorHandle(self.cursor_obj)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class FakeAcquire:
    """pool.acquire() double: async context manager yielding the fake connection."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *exc):
        return False


class FakePool:
    """aiomysql pool double handing out fake connections in order (the last one repeats)."""

    def __init__(self, *conns):
        self._conns = list(conns)

    def acquire(self):
        conn = self._conns.pop(0) if len(self._conns) > 1 else self._conns[0]
        return FakeAcquire(conn)


def make_adapter(*conns):
    """Build a MySQLAdapter whose pool is replaced by the fake, so no real server is needed."""
    adapter = MySQLAdapter(parse_connection("m", {"uri": "mysql://u@h/db", "access_mode": "read_write"}))
    adapter._pool = FakePool(*conns)
    return adapter


async def test_write_cancelled_closes_connection_and_reraises():
    """A cancelled write closes the connection (poisoned mid-statement) and re-raises the cancellation."""
    conn = FakeConn(fail_with=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await make_adapter(conn).write("DELETE FROM t WHERE id = 1", None)
    assert conn.closed is True
    assert conn.cursor_obj.closed is False
    assert conn.commits == 0
    assert conn.rollbacks == 0


async def test_write_commits_when_applied():
    """An applied write commits exactly once and closes its cursor."""
    conn = FakeConn()
    outcome = await make_adapter(conn).write("UPDATE t SET a = 1 WHERE id = 1", None)
    assert outcome == {"applied": True, "affected": 3}
    assert conn.commits == 1
    assert conn.rollbacks == 0
    assert conn.cursor_obj.closed is True


async def test_write_dry_run_uses_count_probe_and_never_mutates():
    """A dry_run on a simple DELETE is answered by SELECT count(*); the DELETE itself never executes."""
    conn = FakeConn()
    conn.cursor_obj.rows = [{"n": 5}]
    outcome = await make_adapter(conn).write("DELETE FROM t WHERE id = 1", None, dry_run=True)
    assert outcome == {"applied": False, "dry_run": True, "would_affect": 5}
    assert any(q.startswith("SELECT COUNT(*)") for q in conn.cursor_obj.executed)
    assert not any(q.startswith("DELETE") for q in conn.cursor_obj.executed)
    assert conn.commits == 0


async def test_write_abort_via_probe_skips_execution():
    """An expected_max_rows breach detected by the probe aborts before the mutation ever runs."""
    conn = FakeConn()
    conn.cursor_obj.rows = [{"n": 9}]
    outcome = await make_adapter(conn).write("UPDATE t SET a = 1", None, expected_max_rows=2)
    assert outcome["applied"] is False
    assert outcome["affected"] == 9
    assert not any(q.startswith("UPDATE") for q in conn.cursor_obj.executed)


async def test_write_within_expected_executes_for_real():
    """A probe estimate inside the budget lets the real write run; the actual rowcount still applies."""
    conn = FakeConn()
    conn.cursor_obj.rows = [{"n": 1}]
    conn.cursor_obj.rowcount = 1
    outcome = await make_adapter(conn).write("DELETE FROM t WHERE id = 1", None, expected_max_rows=2)
    assert outcome == {"applied": True, "affected": 1}
    assert any(q.startswith("DELETE") for q in conn.cursor_obj.executed)
    assert conn.commits == 1


async def test_write_dry_run_falls_back_to_rollback_when_not_estimable():
    """Parameterized statements skip the probe: dry_run falls back to execute + rollback."""
    conn = FakeConn()
    outcome = await make_adapter(conn).write("DELETE FROM t WHERE id = %s", [1], dry_run=True)
    assert outcome == {"applied": False, "dry_run": True, "would_affect": 3}
    assert any(q.startswith("DELETE") for q in conn.cursor_obj.executed)
    assert conn.commits == 0
    assert conn.rollbacks == 1


async def test_fetch_always_rolls_back():
    """_fetch ends every read with a rollback so no read leaves an open transaction on the pool."""
    conn = FakeConn()
    rows = await make_adapter(conn)._fetch("SELECT 1")
    assert rows == []
    assert conn.rollbacks == 1
    assert conn.cursor_obj.executed[-1] == "SELECT 1"
    assert conn.cursor_obj.closed is True


LOST_CONNECTION = OperationalError(2013, "Lost connection to MySQL server during query")


@pytest.mark.parametrize(
    ("exc", "transient"),
    [
        (OperationalError(2013, "Lost connection"), True),
        (OperationalError(2006, "MySQL server has gone away"), True),
        (OperationalError(1064, "You have an error in your SQL syntax"), False),
        (OperationalError(3024, "Query execution was interrupted, max_execution_time exceeded"), False),
        (ValueError("boom"), False),
    ],
)
def test_is_transient_classification(exc, transient):
    """Only lost/gone-away connection errors count as transient; SQL errors and timeouts never do."""
    assert MySQLAdapter._is_transient(exc) is transient


async def test_read_retries_once_on_lost_connection(monkeypatch):
    """A read hitting a dead connection is retried once on a fresh connection; the dead one is closed."""
    monkeypatch.setattr(SQLAdapter, "_TRANSIENT_RETRY_DELAY_S", 0)
    dead = FakeConn(fail_with=LOST_CONNECTION)
    healthy = FakeConn()
    rows = await make_adapter(dead, healthy)._fetch("SELECT 1")
    assert rows == []
    assert dead.closed is True
    assert healthy.rollbacks == 1


async def test_read_transient_failure_twice_gives_up(monkeypatch):
    """A second transient failure propagates — exactly one retry, never a loop."""
    monkeypatch.setattr(SQLAdapter, "_TRANSIENT_RETRY_DELAY_S", 0)
    with pytest.raises(OperationalError):
        await make_adapter(FakeConn(fail_with=LOST_CONNECTION), FakeConn(fail_with=LOST_CONNECTION))._fetch("SELECT 1")


async def test_non_readonly_fetch_is_never_retried(monkeypatch):
    """kill-style statements (readonly=False) propagate transient errors immediately."""
    monkeypatch.setattr(SQLAdapter, "_TRANSIENT_RETRY_DELAY_S", 0)
    dead = FakeConn(fail_with=LOST_CONNECTION)
    healthy = FakeConn()
    with pytest.raises(OperationalError):
        await make_adapter(dead, healthy)._fetch("KILL 42", readonly=False)
    assert healthy.cursor_obj.executed == []


async def test_write_is_never_retried(monkeypatch):
    """The write path has no retry: a transient error propagates without re-executing the statement."""
    monkeypatch.setattr(SQLAdapter, "_TRANSIENT_RETRY_DELAY_S", 0)
    dead = FakeConn(fail_with=LOST_CONNECTION)
    healthy = FakeConn()
    with pytest.raises(OperationalError):
        await make_adapter(dead, healthy).write("UPDATE t SET a = 1 WHERE id = 1", None)
    assert healthy.cursor_obj.executed == []


async def test_write_sets_lock_timeouts_before_the_statement():
    """Writes cap lock waits (MDL + InnoDB row locks) so a blocked DDL fails fast instead of queueing."""
    conn = FakeConn()
    await make_adapter(conn).write("UPDATE t SET a = 1 WHERE id = 1", None)
    executed = conn.cursor_obj.executed
    assert executed[0] == "SET SESSION TRANSACTION READ WRITE"
    assert executed[1].startswith("SET SESSION lock_wait_timeout")
    assert "innodb_lock_wait_timeout" in executed[1]
    assert executed[-1].startswith("UPDATE")


def make_fetch_adapter(monkeypatch, responses):
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


class TestSchemaBranches:
    async def test_get_ddl_missing_object_raises_not_found(self, monkeypatch):
        """An empty SHOW CREATE TABLE result raises not-found, never an empty DDL."""
        adapter, _ = make_fetch_adapter(monkeypatch, [[]])
        with pytest.raises(QueryValidationError, match="not found"):
            await adapter.get_ddl("app", "ghost")

    async def test_relationships_object_filter_binds_both_sides(self, monkeypatch):
        """Filtering relationships by object binds the name for table and referenced table."""
        adapter, calls = make_fetch_adapter(monkeypatch, [[]])
        await adapter.relationships("app", obj="users")
        assert "table_name = %s OR referenced_table_name = %s" in calls[-1]["sql"]
        assert calls[-1]["params"] == ["app", "users", "users"]

    async def test_grants_object_filter_keeps_matching_grants_only(self, monkeypatch):
        """The object filter keeps only grants whose text mentions the object."""
        rows = [{"Grants for current": "GRANT SELECT ON `app`.`users` TO `dev`"}]
        rows += [{"Grants for current": "GRANT SELECT ON `app`.`orders` TO `dev`"}]
        adapter, _ = make_fetch_adapter(monkeypatch, [rows])
        grants = await adapter.grants(obj="users")
        assert [g["grant"] for g in grants] == ["GRANT SELECT ON `app`.`users` TO `dev`"]

    async def test_column_stats_column_filter_binds(self, monkeypatch):
        """Filtering column_stats by column appends it as a bind."""
        adapter, calls = make_fetch_adapter(monkeypatch, [[{"column": "email", "cardinality": 10}]])
        rows = await adapter.column_stats("app", "users", column="email")
        assert rows[0]["column"] == "email"
        assert calls[-1]["params"] == ["app", "users", "email"]


class TestGuidanceMappings:
    """performance_schema/sys failures map to GuidanceError with the enabling requirement."""

    async def test_top_queries(self, monkeypatch):
        adapter, _ = make_fetch_adapter(monkeypatch, [OperationalError(1142, "denied")])
        with pytest.raises(GuidanceError, match="performance_schema=ON"):
            await adapter.top_queries("total_time", 10)

    async def test_blocking(self, monkeypatch):
        adapter, _ = make_fetch_adapter(monkeypatch, [OperationalError(1142, "denied")])
        with pytest.raises(GuidanceError, match="innodb_lock_waits"):
            await adapter.blocking()

    async def test_index_stats(self, monkeypatch):
        adapter, _ = make_fetch_adapter(monkeypatch, [OperationalError(1142, "denied")])
        with pytest.raises(GuidanceError, match="sys schema"):
            await adapter.index_stats("app")

    async def test_logs(self, monkeypatch):
        adapter, _ = make_fetch_adapter(monkeypatch, [OperationalError(1142, "denied")])
        with pytest.raises(GuidanceError, match="error_log"):
            await adapter.logs()


class TestLogsAndReplication:
    async def test_logs_level_filter_binds_capitalized_priority(self, monkeypatch):
        """The level filter becomes a WHERE prio bind with MySQL's capitalized priority."""
        adapter, calls = make_fetch_adapter(monkeypatch, [[]])
        await adapter.logs(limit=10, level="error")
        assert "WHERE prio = %s" in calls[-1]["sql"]
        assert calls[-1]["params"] == ["Error", 10]

    async def test_replica_reports_status_subset(self, monkeypatch):
        """On a replica, replication() surfaces the curated SHOW REPLICA STATUS keys."""
        status = {
            "Source_Host": "primary",
            "Replica_IO_Running": "Yes",
            "Replica_SQL_Running": "Yes",
            "Seconds_Behind_Source": 3,
            "Last_Error": "",
            "Irrelevant_Key": "noise",
        }
        adapter, _ = make_fetch_adapter(monkeypatch, [[status]])
        result = await adapter.replication()
        assert result["role"] == "replica"
        assert result["status"] == [
            dict(
                Source_Host="primary",
                Replica_IO_Running="Yes",
                Replica_SQL_Running="Yes",
                Seconds_Behind_Source=3,
                Last_Error="",
            )
        ]


class TestKill:
    @pytest.mark.parametrize(
        ("force", "statement", "action"),
        [(True, "KILL 42", "kill"), (False, "KILL QUERY 42", "kill query")],
    )
    async def test_kill_builds_fixed_statement(self, monkeypatch, force, statement, action):
        """kill interpolates only the validated integer id and never runs readonly."""
        adapter, calls = make_fetch_adapter(monkeypatch, [[]])
        result = await adapter.kill("42", force=force)
        assert calls[-1]["sql"] == statement
        assert calls[-1]["readonly"] is False
        assert result == {"target": 42, "action": action, "success": True}


class TestMariaDBStatusAliases:
    async def test_replica_status_normalizes_slave_columns(self, monkeypatch):
        """MariaDB answers SHOW REPLICA STATUS with Slave_* columns; the curated keys still fill in."""
        from mcp_database.adapters.mariadb import MariaDBAdapter

        adapter = MariaDBAdapter(parse_connection("c", {"uri": "mariadb://u@h/db"}))
        calls = []

        async def fake_fetch(query, params=None, *, limit=None, readonly=True):
            calls.append(query)
            return [
                {
                    "Master_Host": "primary",
                    "Slave_IO_Running": "Yes",
                    "Slave_SQL_Running": "Yes",
                    "Seconds_Behind_Master": 2,
                    "Last_Error": "",
                }
            ]

        monkeypatch.setattr(adapter, "_fetch", fake_fetch)
        state = await adapter.replication()
        assert state["role"] == "replica"
        assert state["status"] == [
            {
                "Source_Host": "primary",
                "Replica_IO_Running": "Yes",
                "Replica_SQL_Running": "Yes",
                "Seconds_Behind_Source": 2,
                "Last_Error": "",
            }
        ]


class TestIndexSignalsGuidance:
    async def test_missing_sys_schema_guides(self, monkeypatch):
        """index_signals maps a sys-schema failure to guidance naming performance_schema."""
        adapter, _ = make_fetch_adapter(monkeypatch, [OperationalError(1146, "sys missing")])
        with pytest.raises(GuidanceError, match="sys schema"):
            await adapter.index_signals("app")

    async def test_binary_logs_unavailable_degrades(self, monkeypatch):
        """A SHOW BINARY LOGS privilege error becomes an 'unavailable' section."""
        from pymysql.err import MySQLError

        responses = [[{"database": "app", "bytes": 1}], MySQLError("no REPLICATION CLIENT"), []]
        adapter, _ = make_fetch_adapter(monkeypatch, responses)
        sections = await adapter.storage()
        assert "unavailable" in sections["binary_logs"]
