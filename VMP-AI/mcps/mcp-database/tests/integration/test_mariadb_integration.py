"""MariaDBAdapter against a real MariaDB container: the MySQL protocol surface must hold."""

import pytest

from mcp_database.adapters.mariadb import MariaDBAdapter
from mcp_database.errors import GuidanceError, QueryValidationError

from .conftest import make_cfg

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
async def adapter(mariadb_uri):
    instance = MariaDBAdapter(make_cfg("maria", mariadb_uri))
    yield instance
    await instance.close()


@pytest.fixture(scope="module", autouse=True)
async def seed(adapter):
    await adapter.write(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id int PRIMARY KEY,
            title varchar(50) NOT NULL,
            body text NOT NULL,
            FULLTEXT KEY articles_body_ft (body)
        ) CHARACTER SET utf8mb4
        """,
        None,
    )
    await adapter.write("DELETE FROM articles WHERE id > 0", None, expected_max_rows=10)
    await adapter.write("INSERT INTO articles VALUES (1, 'alpha', 'postgres full text search')", None)
    await adapter.write("INSERT INTO articles VALUES (2, 'beta', 'mariadb fulltext index')", None)
    await adapter.write("INSERT INTO articles VALUES (3, 'gamma', 'redis in memory store')", None)


async def test_ping_and_databases(adapter):
    """The connection opens and the seeded database is listed."""
    await adapter.ping()
    names = [row["database"] for row in await adapter.list_databases()]
    assert "test" in names


async def test_objects_describe_and_ddl(adapter):
    """Schema tools see the seeded table, its columns and its DDL."""
    objects = await adapter.list_objects("test")
    assert any(obj["name"] == "articles" for obj in objects)
    described = await adapter.describe_object("test", "articles", sample=False)
    assert any(col["name"] == "body" for col in described["columns"])
    assert "CREATE TABLE" in (await adapter.get_ddl("test", "articles"))["ddl"]


async def test_read_write_cycle_and_rowcounts(adapter):
    """Reads see committed writes; the write protocol reports affected rows."""
    outcome = await adapter.write("UPDATE articles SET title = 'alpha' WHERE id = 1", None)
    assert outcome["applied"] is True
    rows = await adapter.read("SELECT title FROM articles ORDER BY id", None, 10)
    assert [row["title"] for row in rows] == ["alpha", "beta", "gamma"]


async def test_fulltext_search_end_to_end(adapter):
    """MATCH...AGAINST works on the MariaDB FULLTEXT index through text_search."""
    rows = await adapter.text_search("test", "articles", "fulltext", column="body", limit=5)
    assert [row["title"] for row in rows] == ["beta"]
    indexes = (await adapter.search_indexes("test"))["indexes"]
    assert any(index["index"] == "articles_body_ft" for index in indexes)


async def test_perf_surface_is_best_effort(adapter):
    """health/settings/active_ops answer; performance_schema-backed tools may guide instead."""
    assert (await adapter.health())["connections"] is not None
    assert await adapter.settings("innodb%")
    assert isinstance(await adapter.active_ops(), list)
    try:
        await adapter.top_queries("total_time", 5)
    except GuidanceError as exc:
        assert "performance_schema" in str(exc)


async def test_replication_standalone(adapter):
    """A single container reports the standalone role."""
    assert (await adapter.replication())["role"] in ("standalone", "source")


async def test_dry_run_uses_probe(adapter):
    """dry_run estimates via count(*) and leaves the data untouched."""
    outcome = await adapter.write("DELETE FROM articles WHERE id = 3", None, dry_run=True)
    assert outcome == {"applied": False, "dry_run": True, "would_affect": 1}
    assert len(await adapter.read("SELECT id FROM articles", None, 10)) == 3


async def test_sad_paths_are_clean_errors(adapter):
    """Broken SQL and missing objects produce clear errors, never crashes."""
    with pytest.raises(Exception):  # noqa: B017 - engine error type varies
        await adapter.read("SELECT * FROM nowhere_at_all", None, 5)
    with pytest.raises(QueryValidationError, match="not found"):
        await adapter.describe_object("test", "ghost")


async def test_unicode_round_trip(adapter):
    """Unicode values survive the write/read cycle untouched."""
    await adapter.write("UPDATE articles SET title = 'ação🚀' WHERE id = 1", None)
    rows = await adapter.read("SELECT title FROM articles WHERE id = 1", None, 1)
    assert rows[0]["title"] == "ação🚀"
    await adapter.write("UPDATE articles SET title = 'alpha' WHERE id = 1", None)
