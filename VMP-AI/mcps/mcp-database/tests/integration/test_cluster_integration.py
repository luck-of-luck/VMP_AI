"""Real multi-node topologies: replication views, cluster findings and admin actions per engine.

Within each engine the tests run in definition order on a shared module-scoped topology; the
action test that breaks replication (promote) always comes last.
"""

import json

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_database.adapters.mariadb import MariaDBAdapter
from mcp_database.adapters.mysql import MySQLAdapter
from mcp_database.adapters.postgres import PostgresAdapter
from mcp_database.adapters.redis import RedisAdapter
from mcp_database.audit import AuditLogger
from mcp_database.server import build_server

from .cluster_topologies import poll
from .conftest import make_cfg

pytestmark = [pytest.mark.integration, pytest.mark.cluster]


async def call_tool(uri: str, tool: str, arguments: dict, tmp_path, *, mode: str = "read_write"):
    result = await call_tool_raw(uri, tool, arguments, tmp_path, mode=mode)
    assert not result.isError, result.content[0].text
    return json.loads(result.content[0].text)


async def call_tool_raw(uri: str, tool: str, arguments: dict, tmp_path, *, mode: str = "read_write"):
    cfg = make_cfg("target", uri, access_mode=mode)
    server = build_server({"target": cfg}, audit=AuditLogger(tmp_path / "audit.log"))
    async with create_connected_server_and_client_session(server._mcp_server) as client:
        return await client.call_tool(tool, arguments)


async def poll_async(check, *, what: str, cap_s: int = 90):
    """Await an async zero-arg check until truthy, failing loudly after the cap."""
    import asyncio
    import contextlib
    import time

    deadline = time.monotonic() + cap_s
    while time.monotonic() < deadline:
        with contextlib.suppress(Exception):
            if await check():
                return
        await asyncio.sleep(1)
    pytest.fail(f"topology never became ready: {what}")


class TestPostgresCluster:
    async def test_replication_views_and_data_flow(self, pg_cluster):
        """Primary sees a streaming replica, the standby sees its receiver, and rows actually flow."""
        primary = PostgresAdapter(make_cfg("pgp", pg_cluster["primary"]))
        standby = PostgresAdapter(make_cfg("pgs", pg_cluster["replica"]))
        try:
            state = await primary.replication()
            assert state["role"] == "primary"
            assert len(state["replicas"]) == 1 and state["replicas"][0]["state"] == "streaming"
            assert isinstance(state["replicas"][0]["replay_lag_bytes"], int)

            replica_state = await standby.replication()
            assert replica_state["role"] == "replica"
            assert replica_state["receiver"][0]["status"] == "streaming"

            await primary.write("CREATE TABLE IF NOT EXISTS t_repl (id int PRIMARY KEY)", None)
            await primary.write("INSERT INTO t_repl VALUES (1) ON CONFLICT DO NOTHING", None)

            async def replicated():
                rows = await standby.read("SELECT count(*) AS n FROM t_repl", None, 1)
                return rows and rows[0]["n"] == 1

            await poll_async(replicated, what="pg row visible on the standby")
        finally:
            await primary.close()
            await standby.close()

    async def test_cluster_tool_reports_healthy(self, pg_cluster, tmp_path):
        """db_perf_cluster on a healthy primary reports the streaming replica without findings."""
        body = await call_tool(pg_cluster["primary"], "db_perf_cluster", {"conn": "target"}, tmp_path)
        assert any("healthy" in finding for finding in body["findings"])

    async def test_modes_hold_on_a_real_replica(self, pg_cluster, tmp_path):
        """On the standby, monitor answers perf but denies reads; read_only denies writes before the database."""
        body = await call_tool(
            pg_cluster["replica"], "db_perf_replication", {"conn": "target"}, tmp_path, mode="monitor"
        )
        assert body["role"] == "replica"
        denied_read = await call_tool_raw(
            pg_cluster["replica"], "db_read_query", {"conn": "target", "query": "SELECT 1"}, tmp_path, mode="monitor"
        )
        assert denied_read.isError and "monitor" in denied_read.content[0].text
        denied_write = await call_tool_raw(
            pg_cluster["replica"],
            "db_write_query",
            {"conn": "target", "query": "DELETE FROM t_repl WHERE id = 1"},
            tmp_path,
            mode="read_only",
        )
        assert denied_write.isError and "read_only" in denied_write.content[0].text

    async def test_pause_replay_freezes_the_standby_until_resumed(self, pg_cluster, tmp_path):
        """pause_replay stops WAL apply (flagged by db_perf_cluster); resume_replay catches back up."""
        paused = await call_tool(
            pg_cluster["replica"], "db_admin_cluster", {"conn": "target", "action": "pause_replay"}, tmp_path
        )
        assert paused["success"] is True
        primary = PostgresAdapter(make_cfg("pgp", pg_cluster["primary"]))
        standby = PostgresAdapter(make_cfg("pgs", pg_cluster["replica"]))
        try:
            await primary.write("INSERT INTO t_repl VALUES (2) ON CONFLICT DO NOTHING", None)
            state = await standby.replication()
            assert state["replay_paused"] is True

            body = await call_tool(pg_cluster["replica"], "db_perf_cluster", {"conn": "target"}, tmp_path)
            assert any("WAL replay is paused" in finding for finding in body["findings"])
            assert any("resume_replay" in step for step in body["next"])

            resumed = await call_tool(
                pg_cluster["replica"], "db_admin_cluster", {"conn": "target", "action": "resume_replay"}, tmp_path
            )
            assert resumed["success"] is True

            async def caught_up():
                rows = await standby.read("SELECT count(*) AS n FROM t_repl", None, 1)
                return rows and rows[0]["n"] == 2

            await poll_async(caught_up, what="pg standby catching up after resume_replay")
        finally:
            await primary.close()
            await standby.close()

    async def test_failover_after_primary_crash(self, pg_cluster, tmp_path):
        """With the primary dead, promote turns the standby into the new primary (runs last)."""
        pg_cluster["containers"]["primary"].get_wrapped_container().stop()
        body = await call_tool(
            pg_cluster["replica"], "db_admin_cluster", {"conn": "target", "action": "promote"}, tmp_path
        )
        assert body["success"] is True
        promoted = PostgresAdapter(make_cfg("pgs", pg_cluster["replica"]))
        try:

            async def is_primary():
                return (await promoted.replication())["role"] == "primary"

            await poll_async(is_primary, what="pg standby leaving recovery after promote")
        finally:
            await promoted.close()


class TestMySQLCluster:
    async def test_replica_status_and_data_flow(self, mysql_cluster):
        """The replica reports running threads and numeric lag, and rows actually flow."""
        source = MySQLAdapter(make_cfg("myp", mysql_cluster["primary"]))
        replica = MySQLAdapter(make_cfg("myr", mysql_cluster["replica"]))
        try:
            state = await replica.replication()
            assert state["role"] == "replica"
            row = state["status"][0]
            assert row["Replica_IO_Running"] == "Yes" and row["Replica_SQL_Running"] == "Yes"
            assert isinstance(row["Seconds_Behind_Source"], int)

            await source.write("CREATE TABLE IF NOT EXISTS test.t_repl (id int PRIMARY KEY)", None)
            await source.write("INSERT IGNORE INTO test.t_repl VALUES (1)", None)

            async def replicated():
                rows = await replica.read("SELECT count(*) AS n FROM test.t_repl", None, 1)
                return rows and rows[0]["n"] == 1

            await poll_async(replicated, what="mysql row visible on the replica")
        finally:
            await source.close()
            await replica.close()

    async def test_stop_replica_surfaces_finding_then_start_recovers(self, mysql_cluster, tmp_path):
        """stop_replica halts the threads, db_perf_cluster flags it, start_replica recovers."""
        stopped = await call_tool(
            mysql_cluster["replica"], "db_admin_cluster", {"conn": "target", "action": "stop_replica"}, tmp_path
        )
        assert stopped["success"] is True

        body = await call_tool(mysql_cluster["replica"], "db_perf_cluster", {"conn": "target"}, tmp_path)
        assert any("replication thread is stopped" in finding for finding in body["findings"])
        assert any("start_replica" in step for step in body["next"])

        started = await call_tool(
            mysql_cluster["replica"], "db_admin_cluster", {"conn": "target", "action": "start_replica"}, tmp_path
        )
        assert started["success"] is True
        replica = MySQLAdapter(make_cfg("myr", mysql_cluster["replica"]))
        try:

            async def running():
                row = (await replica.replication())["status"][0]
                return row["Replica_IO_Running"] == "Yes" and row["Replica_SQL_Running"] == "Yes"

            await poll_async(running, what="mysql replication threads running again")
        finally:
            await replica.close()

    async def test_broken_replication_surfaces_the_error_finding(self, mysql_cluster, tmp_path):
        """A conflicting row on the replica halts the SQL thread; the finding carries the error (runs last)."""
        replica = MySQLAdapter(make_cfg("myr", mysql_cluster["replica"]))
        source = MySQLAdapter(make_cfg("myp", mysql_cluster["primary"]))
        try:
            await replica.write("INSERT INTO test.t_repl VALUES (99)", None)
            await source.write("INSERT INTO test.t_repl VALUES (99)", None)

            async def errored():
                status = (await replica.replication())["status"]
                return bool(status and status[0]["Last_Error"])

            await poll_async(errored, what="mysql SQL thread stopping on the conflict")
            body = await call_tool(mysql_cluster["replica"], "db_perf_cluster", {"conn": "target"}, tmp_path)
            assert any("replication error" in finding for finding in body["findings"])
        finally:
            await replica.close()
            await source.close()


class TestMariaDBCluster:
    async def test_replica_status_and_data_flow(self, mariadb_cluster):
        """The MariaDB replica reports running threads and rows actually flow (GTID slave_pos)."""
        source = MariaDBAdapter(make_cfg("map", mariadb_cluster["primary"]))
        replica = MariaDBAdapter(make_cfg("mar", mariadb_cluster["replica"]))
        try:
            state = await replica.replication()
            assert state["role"] == "replica"
            row = state["status"][0]
            assert row["Replica_IO_Running"] == "Yes" and row["Replica_SQL_Running"] == "Yes"

            await source.write("CREATE TABLE IF NOT EXISTS test.t_repl (id int PRIMARY KEY)", None)
            await source.write("INSERT IGNORE INTO test.t_repl VALUES (1)", None)

            async def replicated():
                rows = await replica.read("SELECT count(*) AS n FROM test.t_repl", None, 1)
                return rows and rows[0]["n"] == 1

            await poll_async(replicated, what="mariadb row visible on the replica")
        finally:
            await source.close()
            await replica.close()

    async def test_source_lists_replica_via_show_slave_hosts(self, mariadb_cluster):
        """The source-side view works through the MariaDB statement (SHOW SLAVE HOSTS)."""
        source = MariaDBAdapter(make_cfg("map", mariadb_cluster["primary"]))
        try:

            async def listed():
                state = await source.replication()
                return state["role"] == "source" and state["replicas"]

            await poll_async(listed, what="mariadb source listing its replica")
        finally:
            await source.close()


class TestMongoCluster:
    async def test_replica_set_status_and_lag(self, mongo_cluster):
        """A 3-member set reports exactly one PRIMARY and numeric lag on the secondaries."""
        from mcp_database.adapters.mongodb import MongoAdapter

        adapter = MongoAdapter(make_cfg("mg", mongo_cluster["members"][0]))
        try:
            state = await adapter.replication()
            assert state["role"] == "replica_set" and state["set"] == "rs0"
            assert len(state["members"]) == 3
            primaries = [m for m in state["members"] if m["state"] == "PRIMARY"]
            secondaries = [m for m in state["members"] if m["state"] == "SECONDARY"]
            assert len(primaries) == 1 and len(secondaries) == 2
            assert all(isinstance(m["lag_seconds"], int) for m in secondaries)
        finally:
            await adapter.close()

    @staticmethod
    def _primary_uri(mongo_cluster) -> str:
        from pymongo import MongoClient

        for uri in mongo_cluster["members"]:
            with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
                if client.admin.command("hello").get("isWritablePrimary"):
                    return uri
        pytest.fail("no PRIMARY found among the replica set members")

    async def test_step_down_elects_a_new_primary(self, mongo_cluster, tmp_path):
        """step_down on the primary succeeds (dropped connection = success) and a new PRIMARY appears."""
        from mcp_database.adapters.mongodb import MongoAdapter

        primary_uri = self._primary_uri(mongo_cluster)
        body = await call_tool(
            primary_uri,
            "db_admin_cluster",
            {"conn": "target", "action": "step_down", "seconds": 20},
            tmp_path,
        )
        assert body["success"] is True

        adapter = MongoAdapter(make_cfg("mg", mongo_cluster["members"][1]))
        try:

            async def new_primary():
                state = await adapter.replication()
                return any(m["state"] == "PRIMARY" for m in state["members"])

            await poll_async(new_primary, what="mongo replica set electing a new PRIMARY after step_down")
        finally:
            await adapter.close()

    async def test_primary_crash_triggers_reelection_then_quorum_loss_flags_it(self, mongo_cluster, tmp_path):
        """Losing the primary re-elects among survivors; losing quorum yields the no-PRIMARY finding (runs last)."""
        from mcp_database.adapters.mongodb import MongoAdapter

        primary_uri = self._primary_uri(mongo_cluster)
        primary_index = mongo_cluster["members"].index(primary_uri)
        mongo_cluster["containers"][primary_index].get_wrapped_container().stop()

        survivor_indexes = [i for i in range(3) if i != primary_index]
        survivor = MongoAdapter(make_cfg("mg", mongo_cluster["members"][survivor_indexes[0]]))
        try:

            async def reelected():
                state = await survivor.replication()
                return any(m["state"] == "PRIMARY" and m["health"] == 1 for m in state["members"])

            await poll_async(reelected, what="mongo surviving members electing a new PRIMARY after the crash")
        finally:
            await survivor.close()

        new_primary_uri = self._primary_uri_among(mongo_cluster, survivor_indexes)
        second_down = next(i for i in survivor_indexes if mongo_cluster["members"][i] != new_primary_uri)
        mongo_cluster["containers"][second_down].get_wrapped_container().stop()

        last_index = next(i for i in survivor_indexes if i != second_down)
        last_uri = mongo_cluster["members"][last_index]
        last = MongoAdapter(make_cfg("mg", last_uri))
        try:

            async def demoted():
                state = await last.replication()
                return not any(m["state"] == "PRIMARY" and m.get("health") == 1 for m in state["members"])

            await poll_async(demoted, what="mongo survivor stepping down after quorum loss")
        finally:
            await last.close()
        body = await call_tool(last_uri, "db_perf_cluster", {"conn": "target"}, tmp_path)
        assert any("no PRIMARY" in finding for finding in body["findings"])

    @staticmethod
    def _primary_uri_among(mongo_cluster, indexes) -> str:
        from pymongo import MongoClient

        def find():
            for i in indexes:
                with MongoClient(mongo_cluster["members"][i], serverSelectionTimeoutMS=3000) as client:
                    if client.admin.command("hello").get("isWritablePrimary"):
                        return mongo_cluster["members"][i]
            return None

        return poll(find, what="locating the re-elected PRIMARY")


class TestRedisCluster:
    async def test_roles_and_data_flow(self, redis_cluster):
        """Primary reports one connected replica, the replica reports its link, and keys flow."""
        primary = RedisAdapter(make_cfg("rdp", redis_cluster["primary"]))
        replica = RedisAdapter(make_cfg("rdr", redis_cluster["replica"]))
        try:
            state = await primary.replication()
            assert state["role"] == "master" and state["connected_replicas"] == 1
            replica_state = await replica.replication()
            assert replica_state["role"] == "slave" and replica_state["master_link_status"] == "up"

            await primary.write({"command": "SET", "args": ["k_repl", "42"], "database": None}, None)

            async def replicated():
                rows = await replica.read({"command": "GET", "args": ["k_repl"], "database": None}, None, 1)
                return rows and rows[0]["result"] == "42"

            await poll_async(replicated, what="redis key visible on the replica")
        finally:
            await primary.close()
            await replica.close()

    async def test_primary_crash_marks_the_link_down(self, redis_cluster, tmp_path):
        """With the primary dead, the replica reports its master link down and the finding says so."""
        redis_cluster["containers"]["primary"].get_wrapped_container().stop()
        replica = RedisAdapter(make_cfg("rdr", redis_cluster["replica"]))
        try:

            async def link_down():
                state = await replica.replication()
                return state["role"] == "slave" and state["master_link_status"] != "up"

            await poll_async(link_down, what="redis replica noticing the dead master")
        finally:
            await replica.close()
        body = await call_tool(redis_cluster["replica"], "db_perf_cluster", {"conn": "target"}, tmp_path)
        assert any("lost its master link" in finding for finding in body["findings"])

    async def test_promote_detaches_the_replica(self, redis_cluster, tmp_path):
        """promote (REPLICAOF NO ONE) turns the replica into a master (runs last: breaks replication)."""
        body = await call_tool(
            redis_cluster["replica"], "db_admin_cluster", {"conn": "target", "action": "promote"}, tmp_path
        )
        assert body["success"] is True
        promoted = RedisAdapter(make_cfg("rdr", redis_cluster["replica"]))
        try:

            async def is_master():
                return (await promoted.replication())["role"] == "master"

            await poll_async(is_master, what="redis replica reporting master after promote")
        finally:
            await promoted.close()
