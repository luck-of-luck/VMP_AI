import pytest

from mcp_database.adapters.mysql import MySQLAdapter
from mcp_database.errors import GuidanceError, QueryValidationError

from .conftest import make_cfg

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
async def adapter(mysql_uri):
    instance = MySQLAdapter(make_cfg("my", mysql_uri))
    yield instance
    await instance.close()


@pytest.fixture(scope="module", autouse=True)
async def seed(adapter):
    await adapter.write(
        """
        CREATE TABLE IF NOT EXISTS users (
            id int AUTO_INCREMENT PRIMARY KEY,
            name varchar(100) NOT NULL,
            email varchar(200) UNIQUE
        )
        """,
        None,
    )
    await adapter.write(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id int AUTO_INCREMENT PRIMARY KEY,
            user_id int,
            total decimal(10, 2),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        None,
    )
    await adapter.write("INSERT INTO users (name, email) VALUES ('Ana', 'ana@x.io'), ('Bob', 'bob@x.io')", None)
    await adapter.write("INSERT INTO orders (user_id, total) VALUES (1, 10.5), (2, 3.0)", None)


async def test_ping_and_databases(adapter):
    await adapter.ping()
    databases = [row["database"] for row in await adapter.list_databases()]
    assert "test" in databases
    assert "mysql" not in databases


async def test_objects_describe_ddl(adapter):
    objects = await adapter.list_objects("test")
    names = {o["name"] for o in objects}
    assert {"users", "orders"} <= names

    with pytest.raises(QueryValidationError):
        await adapter.list_objects("test", "spaceship")

    described = await adapter.describe_object("test", "users")
    assert {"id", "name", "email"} <= {c["name"] for c in described["columns"]}
    assert any(i["name"] == "PRIMARY" for i in described["indexes"])

    ddl = (await adapter.get_ddl("test", "users"))["ddl"]
    assert "CREATE TABLE" in ddl

    with pytest.raises(Exception, match=r"(?i)exist|not found"):
        await adapter.get_ddl("test", "ghost")


async def test_search_relationships_users_grants(adapter):
    found = await adapter.search("user")
    assert any(o["name"] == "users" for o in found["objects"])

    relationships = (await adapter.relationships("test"))["relationships"]
    assert any(r["from_table"] == "orders" and r["to_table"] == "users" for r in relationships)

    users = await adapter.users()
    assert any(u["user"] == "root" for u in users)

    grants = await adapter.grants("root@%")
    assert grants and all("grant" in g for g in grants)

    with pytest.raises(QueryValidationError, match="not found"):
        await adapter.grants("ghost_user_404")


async def test_read_write_cycle(adapter):
    rows = await adapter.read("SELECT * FROM users ORDER BY id", None, 10)
    assert len(rows) == 2

    dry = await adapter.write("UPDATE users SET name = 'X'", None, dry_run=True)
    assert dry["would_affect"] == 2

    aborted = await adapter.write("UPDATE users SET name = 'X'", None, expected_max_rows=1)
    assert aborted["applied"] is False

    applied = await adapter.write("UPDATE users SET name = 'Zed' WHERE id = 1", None)
    assert applied == {"applied": True, "affected": 1}


async def test_read_only_session_blocks_writes(adapter):
    with pytest.raises(Exception, match=r"(?i)read.?only"):
        await adapter.read("DELETE FROM users", None, 10)


async def test_sample_and_explain(adapter):
    assert len(await adapter.sample("test", "users", 1)) == 1
    plan = await adapter.explain("SELECT * FROM users WHERE id = 1")
    assert plan["plan"]


async def test_perf_suite(adapter):
    top = await adapter.top_queries("total_time", 5, None)
    assert top and "query" in top[0]
    with pytest.raises(QueryValidationError):
        await adapter.top_queries("vibes", 5, None)

    assert isinstance(await adapter.active_ops(0), list)
    assert isinstance(await adapter.blocking(), list)

    index_stats = await adapter.index_stats("test")
    assert "unused" in index_stats and "redundant" in index_stats

    table_stats = await adapter.table_stats("test")
    assert any(t["table"] == "users" for t in table_stats)

    health = await adapter.health()
    assert health["connections"]["max"] is not None

    settings = await adapter.settings("buffer_pool")
    assert any("buffer_pool" in s["Variable_name"] for s in settings)

    logs = await adapter.logs(limit=5)
    assert isinstance(logs, list)


async def test_replication_standalone(adapter):
    replication = await adapter.replication()
    assert replication["role"] == "standalone"
    assert replication["note"]


async def test_kill_absurd_and_analyze_maintain(adapter):
    with pytest.raises(QueryValidationError, match="numeric"):
        await adapter.kill("abc")

    analyzed = await adapter.analyze("test", "users")
    assert analyzed["result"]

    with pytest.raises(QueryValidationError):
        await adapter.analyze("test", None)

    maintained = await adapter.maintain("test", "users")
    assert maintained["action"] == "optimize"

    with pytest.raises(QueryValidationError, match="optimize"):
        await adapter.maintain("test", "users", "vacuum")


async def test_read_sad_bad_sql(adapter):
    """Invalid SQL surfaces as the server's syntax error, never as a crash."""
    with pytest.raises(Exception, match=r"(?i)syntax|exist"):
        await adapter.read("SELECT FROM WHERE", None, 10)


async def test_describe_missing_object_not_found(adapter):
    """Describing a nonexistent table raises a clear 'not found', never an empty result."""
    with pytest.raises(QueryValidationError, match="not found"):
        await adapter.describe_object("test", "ghost_table")


async def test_kill_nonexistent_thread_is_clean_error(adapter):
    """Killing a thread id that does not exist yields the server's clean error."""
    with pytest.raises(Exception, match=r"(?i)unknown thread|not found"):
        await adapter.kill("999999999")


async def test_unicode_round_trip(adapter):
    """Accented text, emoji and LIKE metacharacters survive a real INSERT/SELECT unchanged."""
    await adapter.write("INSERT INTO users (name, email) VALUES (%s, %s)", ["José 🚀 %_", "jose@x.io"])
    rows = await adapter.read("SELECT name FROM users WHERE email = %s", ["jose@x.io"], 10)
    assert rows == [{"name": "José 🚀 %_"}]


async def test_bound_params_are_not_interpolated(adapter):
    """A SQL-injection payload passed via params is stored as literal data; the table survives."""
    hostile = "'; DROP TABLE users; --"
    await adapter.write("INSERT INTO users (name, email) VALUES (%s, %s)", [hostile, "evil@x.io"])
    rows = await adapter.read("SELECT name FROM users WHERE email = %s", ["evil@x.io"], 10)
    assert rows == [{"name": hostile}]
    assert (await adapter.read("SELECT count(*) AS n FROM users", None, None))[0]["n"] >= 2


@pytest.fixture(scope="module")
async def restricted(adapter, mysql_uri):
    """Adapter connected as a user that only has SELECT on test.* (dropped again on teardown)."""
    await adapter.write("CREATE USER IF NOT EXISTS 'peon'@'%' IDENTIFIED BY 'peon'", None)
    await adapter.write("GRANT SELECT ON test.* TO 'peon'@'%'", None)
    host_part = mysql_uri.split("@")[1].split("/")[0]
    instance = MySQLAdapter(make_cfg("peon", f"mysql://peon:peon@{host_part}/test"))
    yield instance
    await instance.close()
    await adapter.write("DROP USER IF EXISTS 'peon'@'%'", None)


async def test_restricted_user_gets_guidance(restricted):
    """A low-privilege user can still read, and missing privileges produce a GuidanceError naming the fix."""
    rows = await restricted.read("SELECT id FROM users ORDER BY id", None, 5)
    assert rows

    with pytest.raises(GuidanceError, match="mysql schema"):
        await restricted.users()


async def test_dry_run_does_not_execute_the_mutation(adapter):
    """dry_run answers from a count(*) probe: a booby-trapped trigger proves the UPDATE never runs."""
    await adapter.write("CREATE TABLE IF NOT EXISTS trapped (id int)", None)
    await adapter.write("INSERT INTO trapped VALUES (1), (2)", None)
    await adapter.write(
        "CREATE TRIGGER trap_upd BEFORE UPDATE ON trapped FOR EACH ROW "
        "SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'trap fired'",
        None,
    )
    try:
        dry = await adapter.write("UPDATE trapped SET id = id", None, dry_run=True)
        assert dry == {"applied": False, "dry_run": True, "would_affect": 2}

        with pytest.raises(Exception, match="trap fired"):
            await adapter.write("UPDATE trapped SET id = id", None)
    finally:
        await adapter.write("DROP TABLE IF EXISTS trapped", None)


async def test_column_stats_reports_cardinality(adapter):
    """Indexed columns report cardinality; histograms stay null until UPDATE HISTOGRAM is run."""
    rows = await adapter.column_stats("test", "users")
    by_name = {r["column"]: r for r in rows}
    assert {"id", "name", "email"} <= set(by_name)
    assert by_name["id"]["cardinality"] is not None

    with pytest.raises(QueryValidationError, match="statistics"):
        await adapter.column_stats("test", "ghost_table")


async def test_explain_hypothetical_gives_guidance(adapter):
    """Hypothetical indexes are a PostgreSQL/hypopg feature; MySQL points that out instead of failing oddly."""
    with pytest.raises(GuidanceError, match="hypopg"):
        await adapter.explain("SELECT 1", hypothetical_indexes=["CREATE INDEX idx ON users(email)"])
