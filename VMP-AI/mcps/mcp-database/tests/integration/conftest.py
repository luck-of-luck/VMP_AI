import os

import pytest

from mcp_database.config import parse_connection

PG_IMAGE = os.environ.get("PG_IMAGE", "postgres:17-alpine")
MYSQL_IMAGE = os.environ.get("MYSQL_IMAGE", "mysql:8.4")
MARIADB_IMAGE = os.environ.get("MARIADB_IMAGE", "mariadb:11.4")
MONGO_IMAGE = os.environ.get("MONGO_IMAGE", "mongo:8")
REDIS_IMAGE = os.environ.get("REDIS_IMAGE", "redis:8")


from .cluster_topologies import (  # noqa: E402, F401 - shared cluster fixtures
    mariadb_cluster,
    mongo_cluster,
    mysql_cluster,
    pg_cluster,
    redis_cluster,
)


def make_cfg(name: str, uri: str, **overrides):
    return parse_connection(name, {"uri": uri, "access_mode": "read_write", **overrides})


@pytest.fixture(scope="session")
def pg_uri():
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer(PG_IMAGE, username="test", password="test", dbname="test")
    container.with_command("postgres -c shared_preload_libraries=pg_stat_statements")
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(5432)
        yield f"postgresql://test:test@{host}:{port}/test"


@pytest.fixture(scope="session")
def mysql_uri():
    from testcontainers.mysql import MySqlContainer

    container = MySqlContainer(MYSQL_IMAGE, username="test", password="test", dbname="test", root_password="test")
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(3306)
        yield f"mysql://root:test@{host}:{port}/test"


@pytest.fixture(scope="session")
def mariadb_uri():
    from testcontainers.mysql import MySqlContainer

    container = MySqlContainer(MARIADB_IMAGE, username="test", password="test", dbname="test", root_password="test")
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(3306)
        yield f"mariadb://root:test@{host}:{port}/test"


@pytest.fixture(scope="session")
def sqlite_uri(tmp_path_factory):
    return f"sqlite:///{tmp_path_factory.mktemp('sqlite') / 'matrix.db'}"


@pytest.fixture(scope="session")
def redis_uri():
    from testcontainers.redis import RedisContainer

    with RedisContainer(REDIS_IMAGE) as container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(6379)
        yield f"redis://{host}:{port}/0"


@pytest.fixture(scope="session")
def mongo_uri():
    from testcontainers.mongodb import MongoDbContainer

    container = MongoDbContainer(MONGO_IMAGE, username="test", password="test", dbname="test")
    with container:
        host = container.get_container_host_ip()
        port = container.get_exposed_port(27017)
        yield f"mongodb://test:test@{host}:{port}/test?authSource=admin"
