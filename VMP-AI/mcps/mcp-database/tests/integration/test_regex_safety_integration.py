"""User-supplied search patterns must never be interpreted as regular expressions.

This prevents both ReDoS (catastrophic backtracking) and regex injection: db_schema_search
feeds a parameterized SQL LIKE or a Python substring test, never a compiled regex. MongoDB read
filters may still carry a legitimate `$regex`, but every read operation is bounded by maxTimeMS.
"""

import pytest

from mcp_database.adapters.mongodb import MongoAdapter
from mcp_database.adapters.mysql import MySQLAdapter
from mcp_database.adapters.postgres import PostgresAdapter

from .conftest import make_cfg

pytestmark = [pytest.mark.integration, pytest.mark.cross_engine]

# Each of these matches "everything" as a regex but is a literal substring to LIKE / `in`.
# None of them appears literally in the seeded object name, so a correct (non-regex) search
# returns zero matches. A regex engine would match the object, exposing the vulnerability.
REGEX_METACHARS = [".*", "(a+)+", "^.*$", "a|b", ".+"]


@pytest.fixture(scope="module")
async def pg_searchable(pg_uri):
    adapter = PostgresAdapter(make_cfg("pg_rx", pg_uri))
    await adapter.write("DROP TABLE IF EXISTS catalog_items", None)
    await adapter.write("CREATE TABLE catalog_items (id int)", None)
    yield adapter
    await adapter.write("DROP TABLE IF EXISTS catalog_items", None)
    await adapter.close()


@pytest.fixture(scope="module")
async def mysql_searchable(mysql_uri):
    adapter = MySQLAdapter(make_cfg("my_rx", mysql_uri))
    await adapter.write("DROP TABLE IF EXISTS catalog_items", None)
    await adapter.write("CREATE TABLE catalog_items (id int)", None)
    yield adapter
    await adapter.write("DROP TABLE IF EXISTS catalog_items", None)
    await adapter.close()


@pytest.fixture(scope="module")
async def mongo_searchable(mongo_uri):
    adapter = MongoAdapter(make_cfg("mg_rx", mongo_uri))
    await adapter.write({"collection": "catalog_items", "operation": "dropCollection"}, None)
    await adapter.write({"collection": "catalog_items", "operation": "createCollection"}, None)
    yield adapter
    await adapter.write({"collection": "catalog_items", "operation": "dropCollection"}, None)
    await adapter.close()


def _names(result):
    return {o["name"] for o in result["objects"]}


@pytest.mark.parametrize("pattern", REGEX_METACHARS)
async def test_postgres_search_pattern_is_not_a_regex(pg_searchable, pattern):
    result = await pg_searchable.search(pattern)
    assert "catalog_items" not in _names(result)  # would match if the pattern were a regex
    assert "catalog_items" in _names(await pg_searchable.search("catalog"))  # literal substring works


@pytest.mark.parametrize("pattern", REGEX_METACHARS)
async def test_mysql_search_pattern_is_not_a_regex(mysql_searchable, pattern):
    result = await mysql_searchable.search(pattern)
    assert "catalog_items" not in _names(result)
    assert "catalog_items" in _names(await mysql_searchable.search("catalog"))


@pytest.mark.parametrize("pattern", REGEX_METACHARS)
async def test_mongo_search_pattern_is_not_a_regex(mongo_searchable, pattern):
    result = await mongo_searchable.search(pattern)
    assert "catalog_items" not in _names(result)
    assert "catalog_items" in _names(await mongo_searchable.search("catalog"))


async def test_search_escapes_sql_like_wildcards(pg_searchable, mysql_searchable):
    # '%' and '_' are LIKE wildcards; the adapters escape them so the pattern is a literal substring.
    for adapter in (pg_searchable, mysql_searchable):
        # '%' as a raw wildcard would match everything; escaped, it matches only a literal '%'.
        assert "catalog_items" not in _names(await adapter.search("%"))
        assert "catalog_items" not in _names(await adapter.search("zzz"))
        # the literal underscore in the name is matched as a plain character, not a single-char wildcard.
        assert "catalog_items" in _names(await adapter.search("catalog_items"))


async def test_mongo_search_wildcards_are_literal(mongo_searchable):
    """Mongo search is a plain substring test: '%' matches nothing, the literal '_' in the name matches."""
    assert "catalog_items" not in _names(await mongo_searchable.search("%"))
    assert "catalog_items" in _names(await mongo_searchable.search("_"))
    assert "catalog_items" in _names(await mongo_searchable.search("catalog_items"))


async def test_mongo_regex_filter_is_allowed_but_time_bounded(mongo_uri):
    # A $regex inside a read filter is a legitimate MongoDB feature, so it is NOT blocked; it is
    # instead bounded server-side by maxTimeMS (short here) and by the app-level asyncio timeout.
    adapter = MongoAdapter(make_cfg("mg_filter", mongo_uri, query_timeout_s=2))
    try:
        await adapter.write(
            {
                "collection": "rx_docs",
                "operation": "insertMany",
                "documents": [{"name": "alpha"}, {"name": "beta"}, {"name": "gamma"}],
            },
            None,
        )
        found = await adapter.read(
            {"collection": "rx_docs", "operation": "find", "filter": {"name": {"$regex": "^al"}}}, None, 10
        )
        assert [r["name"] for r in found] == ["alpha"]

        # distinct now carries maxTimeMS too (the one read op that used to lack a server deadline).
        values = await adapter.read(
            {"collection": "rx_docs", "operation": "distinct", "key": "name", "filter": {"name": {"$regex": "a$"}}},
            None,
            None,
        )
        assert {v["value"] for v in values} == {"alpha", "beta", "gamma"}
    finally:
        await adapter.write({"collection": "rx_docs", "operation": "dropCollection"}, None)
        await adapter.close()
