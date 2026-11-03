"""Multi-node topologies for the cluster tests: real replication over a private docker network.

Each fixture yields the host-reachable URIs of the topology's members. Members talk to each other
through network aliases; the test process always connects through published ports (MongoDB with
directConnection, since replica-set members announce their internal aliases).
"""

import time
from pathlib import Path

import pytest
from testcontainers.core.container import DockerContainer
from testcontainers.core.network import Network
from testcontainers.core.waiting_utils import wait_for_logs

from .conftest import MARIADB_IMAGE, MONGO_IMAGE, MYSQL_IMAGE, PG_IMAGE, REDIS_IMAGE

CLUSTER_DIR = Path(__file__).parent / "cluster"
_POLL_CAP_S = 90


def poll(check, *, what: str, cap_s: int = _POLL_CAP_S):
    """Call `check` until it returns a truthy value, failing loudly after the cap."""
    deadline = time.monotonic() + cap_s
    while time.monotonic() < deadline:
        try:
            result = check()
        except Exception:
            result = None
        if result:
            return result
        time.sleep(1)
    pytest.fail(f"topology never became ready: {what}")


def _host_uri(container: DockerContainer, port: int, template: str) -> str:
    host = container.get_container_host_ip()
    return template.format(host=host, port=container.get_exposed_port(port))


@pytest.fixture(scope="module")
def pg_cluster():
    """postgres primary + streaming standby (pg_basebackup -R over the private network)."""
    standby_boot = (
        'mkdir -p "$PGDATA" && chown -R postgres:postgres "$PGDATA" && chmod 700 "$PGDATA" && '
        'until gosu postgres pg_basebackup -h pg-primary -p 5432 -U test -D "$PGDATA" -R -X stream; '
        "do sleep 1; done && exec gosu postgres postgres"
    )
    with Network() as net:
        primary = (
            DockerContainer(PG_IMAGE)
            .with_envs(POSTGRES_USER="test", POSTGRES_PASSWORD="test", POSTGRES_DB="test")
            .with_env("POSTGRES_HOST_AUTH_METHOD", "trust")
            .with_volume_mapping(str(CLUSTER_DIR), "/docker-entrypoint-initdb.d")
            .with_network(net)
            .with_network_aliases("pg-primary")
            .with_exposed_ports(5432)
        )
        with primary:
            wait_for_logs(primary, "database system is ready to accept connections", timeout=60)
            standby = (
                DockerContainer(PG_IMAGE)
                .with_command(["bash", "-c", standby_boot])
                .with_network(net)
                .with_network_aliases("pg-standby")
                .with_exposed_ports(5432)
            )
            with standby:
                wait_for_logs(standby, "database system is ready to accept read-only connections", timeout=90)
                yield {
                    "primary": _host_uri(primary, 5432, "postgresql://test:test@{host}:{port}/test"),
                    "replica": _host_uri(standby, 5432, "postgresql://test:test@{host}:{port}/test"),
                    "containers": {"primary": primary, "replica": standby},
                }


@pytest.fixture(scope="module")
def mysql_cluster():
    """mysql source + GTID replica (CHANGE REPLICATION SOURCE ... SOURCE_AUTO_POSITION=1)."""
    flags = "--gtid-mode=ON --enforce-gtid-consistency=ON --server-id={sid}"
    envs = {"MYSQL_ROOT_PASSWORD": "test", "MYSQL_DATABASE": "test"}
    with Network() as net:
        source = (
            DockerContainer(MYSQL_IMAGE)
            .with_envs(**envs)
            .with_command(flags.format(sid=1))
            .with_network(net)
            .with_network_aliases("mysql-primary")
            .with_exposed_ports(3306)
        )
        replica = (
            DockerContainer(MYSQL_IMAGE)
            .with_envs(**envs)
            .with_command(flags.format(sid=2))
            .with_network(net)
            .with_network_aliases("mysql-replica")
            .with_exposed_ports(3306)
        )
        with source, replica:
            for node in (source, replica):
                wait_for_logs(node, r"ready for connections.*port: 3306", timeout=120)
            _start_sql_replication(
                replica,
                "CHANGE REPLICATION SOURCE TO SOURCE_HOST='mysql-primary', SOURCE_PORT=3306, "
                "SOURCE_USER='root', SOURCE_PASSWORD='test', SOURCE_AUTO_POSITION=1, GET_SOURCE_PUBLIC_KEY=1",
            )
            yield {
                "primary": _host_uri(source, 3306, "mysql://root:test@{host}:{port}/test"),
                "replica": _host_uri(replica, 3306, "mysql://root:test@{host}:{port}/test"),
                "containers": {"primary": source, "replica": replica},
            }


def _start_sql_replication(replica: DockerContainer, change_statement: str) -> None:
    import pymysql

    def connect():
        return pymysql.connect(
            host=replica.get_container_host_ip(),
            port=int(replica.get_exposed_port(3306)),
            user="root",
            password="test",
            autocommit=True,
        )

    poll(lambda: connect() and True, what="sql replica accepting connections")
    with connect() as conn, conn.cursor() as cursor:
        cursor.execute(change_statement)
        cursor.execute("START REPLICA")

    def replicating():
        with connect() as conn, conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SHOW REPLICA STATUS")
            row = cursor.fetchone()
            io = row and (row.get("Replica_IO_Running") or row.get("Slave_IO_Running"))
            sql_thread = row and (row.get("Replica_SQL_Running") or row.get("Slave_SQL_Running"))
            return io == "Yes" and sql_thread == "Yes"

    poll(replicating, what="sql replication threads running")


@pytest.fixture(scope="module")
def mariadb_cluster():
    """mariadb source + replica over MASTER_USE_GTID=slave_pos (no SOURCE_AUTO_POSITION on MariaDB)."""
    envs = {"MARIADB_ROOT_PASSWORD": "test", "MARIADB_DATABASE": "test"}
    with Network() as net:
        source = (
            DockerContainer(MARIADB_IMAGE)
            .with_envs(**envs)
            .with_command("--log-bin --server-id=1")
            .with_network(net)
            .with_network_aliases("mariadb-primary")
            .with_exposed_ports(3306)
        )
        replica = (
            DockerContainer(MARIADB_IMAGE)
            .with_envs(**envs)
            .with_command("--log-bin --server-id=2")
            .with_network(net)
            .with_network_aliases("mariadb-replica")
            .with_exposed_ports(3306)
        )
        with source, replica:
            for node in (source, replica):
                wait_for_logs(node, r"ready for connections", timeout=120)
            _start_sql_replication(
                replica,
                "CHANGE MASTER TO MASTER_HOST='mariadb-primary', MASTER_PORT=3306, "
                "MASTER_USER='root', MASTER_PASSWORD='test', MASTER_USE_GTID=slave_pos",
            )
            yield {
                "primary": _host_uri(source, 3306, "mariadb://root:test@{host}:{port}/test"),
                "replica": _host_uri(replica, 3306, "mariadb://root:test@{host}:{port}/test"),
                "containers": {"primary": source, "replica": replica},
            }


@pytest.fixture(scope="module")
def mongo_cluster():
    """mongo 3-member replica set on a private network; members are reached via directConnection."""
    from pymongo import MongoClient

    with Network() as net:
        members = []
        for alias in ("m1", "m2", "m3"):
            member = (
                DockerContainer(MONGO_IMAGE)
                .with_command("--replSet rs0 --bind_ip_all")
                .with_network(net)
                .with_network_aliases(alias)
                .with_exposed_ports(27017)
            )
            member.start()
            members.append(member)
        try:
            for member in members:
                wait_for_logs(member, "Waiting for connections", timeout=60)
            uris = [_host_uri(m, 27017, "mongodb://{host}:{port}/test?directConnection=true") for m in members]
            with MongoClient(uris[0], serverSelectionTimeoutMS=5000) as client:
                client.admin.command(
                    "replSetInitiate",
                    {"_id": "rs0", "members": [{"_id": i, "host": f"m{i + 1}:27017"} for i in range(3)]},
                )

                def has_primary():
                    status = client.admin.command("replSetGetStatus")
                    return any(m["stateStr"] == "PRIMARY" for m in status["members"])

                poll(has_primary, what="mongo replica set PRIMARY election")
            yield {"members": uris, "containers": members}
        finally:
            for member in members:
                member.stop()


@pytest.fixture(scope="module")
def redis_cluster():
    """redis primary + replica (--replicaof over the private network)."""
    with Network() as net:
        primary = (
            DockerContainer(REDIS_IMAGE)
            .with_network(net)
            .with_network_aliases("redis-primary")
            .with_exposed_ports(6379)
        )
        with primary:
            wait_for_logs(primary, "Ready to accept connections", timeout=30)
            replica = (
                DockerContainer(REDIS_IMAGE)
                .with_command("redis-server --replicaof redis-primary 6379")
                .with_network(net)
                .with_network_aliases("redis-replica")
                .with_exposed_ports(6379)
            )
            with replica:
                wait_for_logs(replica, "MASTER <-> REPLICA sync: Finished with success", timeout=60)
                yield {
                    "primary": _host_uri(primary, 6379, "redis://{host}:{port}/0"),
                    "replica": _host_uri(replica, 6379, "redis://{host}:{port}/0"),
                    "containers": {"primary": primary, "replica": replica},
                }
