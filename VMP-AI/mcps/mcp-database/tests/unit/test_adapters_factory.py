import pytest

from mcp_database.adapters import create_adapter
from mcp_database.adapters.mariadb import MariaDBAdapter
from mcp_database.adapters.mongodb import MongoAdapter
from mcp_database.adapters.mysql import MySQLAdapter
from mcp_database.adapters.postgres import PostgresAdapter
from mcp_database.config import parse_connection


@pytest.mark.parametrize(
    ("uri", "adapter_cls"),
    [
        ("postgresql://u@h/db", PostgresAdapter),
        ("mysql://u@h/db", MySQLAdapter),
        ("mariadb://u@h/db", MariaDBAdapter),
        ("mongodb://h:27017/db", MongoAdapter),
    ],
)
def test_create_adapter_matches_engine(uri, adapter_cls):
    cfg = parse_connection("c", {"uri": uri})
    adapter = create_adapter(cfg)
    assert isinstance(adapter, adapter_cls)
    assert adapter.config is cfg
