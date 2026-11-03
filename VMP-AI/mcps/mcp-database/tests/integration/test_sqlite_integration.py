"""SQLiteAdapter end-to-end on a real file database (no container needed)."""

import pytest

from mcp_database.adapters.sqlite import SQLiteAdapter
from mcp_database.errors import GuidanceError, QueryValidationError

from .conftest import make_cfg

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
async def adapter(tmp_path_factory):
    path = tmp_path_factory.mktemp("sqlite") / "app.db"
    instance = SQLiteAdapter(make_cfg("sq", f"sqlite:///{path}"))
    await instance.write("CREATE TABLE users (id integer PRIMARY KEY, name text NOT NULL, email text UNIQUE)", None)
    await instance.write("INSERT INTO users (name, email) VALUES ('ana', 'ana@x'), ('bob', 'bob@x')", None)
    await instance.write("CREATE VIRTUAL TABLE notes USING fts5(title, body)", None)
    await instance.write("INSERT INTO notes VALUES ('n1', 'sqlite full text search works')", None)
    return instance


async def test_ping_schema_and_read(adapter):
    """The core read surface answers over a real file."""
    await adapter.ping()
    assert [db["database"] for db in await adapter.list_databases()] == ["main"]
    assert {obj["name"] for obj in await adapter.list_objects("main", object_type="table")} >= {"users"}
    rows = await adapter.read("SELECT count(*) AS n FROM users", None, 1)
    assert rows[0]["n"] == 2


async def test_write_protocol_and_readonly_guarantee(adapter):
    """Writes commit; the read path cannot mutate even when handed a mutation."""
    outcome = await adapter.write("UPDATE users SET name = 'ana' WHERE id = 1", None)
    assert outcome["applied"] is True
    with pytest.raises(Exception, match=r"readonly|attempt to write"):
        await adapter._fetch("DELETE FROM users", readonly=True)


async def test_fts5_search_and_explain(adapter):
    """FTS5 MATCH and EXPLAIN QUERY PLAN work end to end."""
    rows = await adapter.text_search("main", "notes", "sqlite", limit=5)
    assert [row["title"] for row in rows] == ["n1"]
    assert (await adapter.explain("SELECT * FROM users WHERE id = 1"))["plan"]


async def test_stats_cycle_and_health(adapter):
    """ANALYZE unlocks planner stats; health reports file-level integrity."""
    with pytest.raises(GuidanceError, match="ANALYZE"):
        await adapter.index_stats()
    await adapter.analyze("main")
    assert (await adapter.health())["quick_check"] == "ok"


async def test_sad_paths(adapter):
    """Missing objects and server-only surfaces produce clear errors."""
    with pytest.raises(QueryValidationError, match="not found"):
        await adapter.describe_object("main", "ghost")
    with pytest.raises(GuidanceError):
        await adapter.active_ops()
