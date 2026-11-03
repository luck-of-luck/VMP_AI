"""RedisAdapter against a real Redis container: allowlisted surface, inspection tools and guardrails."""

import pytest

from mcp_database.adapters.redis import RedisAdapter
from mcp_database.errors import GuidanceError, QueryValidationError

from .conftest import make_cfg

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
async def adapter(redis_uri):
    instance = RedisAdapter(make_cfg("rd", redis_uri))
    await instance.write({"command": "SET", "args": ["greeting", "olá"], "database": None}, None)
    await instance.write(
        {"command": "HSET", "args": ["user:1", "name", "ana", "email", "ana@x"], "database": None}, None
    )
    await instance.write({"command": "RPUSH", "args": ["queue", "a", "b", "c"], "database": None}, None)
    await instance.write({"command": "ZADD", "args": ["ranking", 10, "ana", 20, "bob"], "database": None}, None)
    yield instance
    await instance.close()


async def test_ping_keyspace_and_objects(adapter):
    """The connection answers and the seeded keys are listed with their types."""
    await adapter.ping()
    assert (await adapter.list_databases())[0]["database"] == "0"
    rows = await adapter.list_objects("0")
    types = {row["name"]: row["type"] for row in rows}
    assert {"greeting": "string", "user:1": "hash", "queue": "list"}.items() <= types.items()


async def test_read_envelope_and_describe(adapter):
    """Allowlisted reads execute; describe reports type, TTL, encoding and a sample."""
    rows = await adapter.read({"command": "HGETALL", "args": ["user:1"], "database": None}, None, 10)
    assert {row["field"]: row["value"] for row in rows} == {"name": "ana", "email": "ana@x"}
    described = await adapter.describe_object("0", "queue")
    assert described["type"] == "list" and described["size"] == 3


async def test_search_escapes_glob_metacharacters(adapter):
    """A * in the pattern is literal: it must not match every key."""
    assert (await adapter.search("*"))["objects"] == []
    assert [obj["name"] for obj in (await adapter.search("user:"))["objects"]] == ["user:1"]


async def test_write_protocol_probe_and_honesty(adapter):
    """DEL supports the EXISTS probe; other commands refuse dry_run instead of faking a rollback."""
    await adapter.write({"command": "SET", "args": ["tmp", "1"], "database": None}, None)
    probe = await adapter.write({"command": "DEL", "args": ["tmp"], "database": None}, None, dry_run=True)
    assert probe == {"applied": False, "dry_run": True, "would_affect": 1}
    assert (await adapter.read({"command": "EXISTS", "args": ["tmp"], "database": None}, None, 1))[0]["result"] == 1
    with pytest.raises(GuidanceError, match="cannot roll back"):
        await adapter.write({"command": "SET", "args": ["tmp", "2"], "database": None}, None, dry_run=True)
    aborted = await adapter.write(
        {"command": "DEL", "args": ["tmp", "greeting"], "database": None}, None, expected_max_rows=1
    )
    assert aborted["applied"] is False and "above expected_max_rows" in aborted["aborted"]
    await adapter.write({"command": "DEL", "args": ["tmp"], "database": None}, None)


async def test_perf_surface(adapter):
    """health/replication/settings/top_queries/active_ops answer with real server data."""
    health = await adapter.health()
    assert health["version"] and health["used_memory_bytes"] > 0
    assert (await adapter.replication())["role"] == "master"
    assert any(row["name"] == "maxmemory" for row in await adapter.settings("maxmemory"))
    assert isinstance(await adapter.top_queries("duration", 5), list)
    assert len(await adapter.active_ops()) >= 1


async def test_sample_by_type(adapter):
    """Sampling adapts to the key type."""
    assert (await adapter.sample("0", "greeting", 3))[0]["value"] == "olá"
    assert len(await adapter.sample("0", "queue", 2)) == 2
    zs = await adapter.sample("0", "ranking", 2)
    assert {"member", "score"} <= set(zs[0])


async def test_wrong_database_and_missing_key_are_clean_errors(adapter):
    """The single-database contract and missing keys produce clear errors."""
    with pytest.raises(QueryValidationError, match="another MCP entry"):
        await adapter.read({"command": "GET", "args": ["k"], "database": "5"}, None, 1)
    with pytest.raises(QueryValidationError, match="not found"):
        await adapter.describe_object("0", "ghost")


async def test_guidance_surfaces(adapter):
    """Engine-foreign tools guide instead of erroring generically."""
    for call in (adapter.get_ddl("0", "k"), adapter.explain("x"), adapter.index_stats(), adapter.maintain("0", "k")):
        with pytest.raises(GuidanceError):
            await call


async def test_connection_identifies_itself(adapter):
    """The invariant: our session is visible as mcp-database/<conn> in CLIENT LIST."""
    clients = await adapter.active_ops()
    assert any(str(entry.get("name")) == "mcp-database/rd" for entry in clients)
