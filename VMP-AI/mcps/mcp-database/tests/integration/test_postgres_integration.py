import asyncio

import pytest

from mcp_database.adapters.postgres import PostgresAdapter
from mcp_database.errors import GuidanceError, QueryValidationError

from .conftest import make_cfg

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
async def adapter(pg_uri):
    instance = PostgresAdapter(make_cfg("pg", pg_uri))
    yield instance
    await instance.close()


@pytest.fixture(scope="module", autouse=True)
async def seed(adapter):
    await adapter.write("CREATE EXTENSION IF NOT EXISTS pg_stat_statements", None)
    await adapter.write(
        """
        CREATE TABLE IF NOT EXISTS users (
            id serial PRIMARY KEY,
            name text NOT NULL,
            email text UNIQUE
        )
        """,
        None,
    )
    await adapter.write(
        "CREATE TABLE IF NOT EXISTS orders (id serial PRIMARY KEY, user_id int REFERENCES users(id), total numeric)",
        None,
    )
    await adapter.write("INSERT INTO users (name, email) VALUES ('Ana', 'ana@x.io'), ('Bob', 'bob@x.io')", None)
    await adapter.write("INSERT INTO orders (user_id, total) VALUES (1, 10.5), (1, 99.9), (2, 3.0)", None)


async def test_ping(adapter):
    await adapter.ping()


async def test_list_databases_and_objects(adapter):
    schemas = [row["schema"] for row in await adapter.list_databases()]
    assert "public" in schemas
    objects = await adapter.list_objects("public")
    names = {o["name"]: o["type"] for o in objects}
    assert names["users"] == "table"
    tables_only = await adapter.list_objects("public", "table")
    assert all(o["type"] == "table" for o in tables_only)


async def test_list_objects_absurd_type(adapter):
    with pytest.raises(QueryValidationError):
        await adapter.list_objects("public", "spaceship")


async def test_describe_and_ddl(adapter):
    described = await adapter.describe_object("public", "users")
    columns = {c["name"] for c in described["columns"]}
    assert {"id", "name", "email"} <= columns
    assert described["total_bytes"] is not None

    ddl = (await adapter.get_ddl("public", "users"))["ddl"]
    assert 'CREATE TABLE "public"."users"' in ddl
    assert "NOT NULL" in ddl


async def test_ddl_missing_object(adapter):
    with pytest.raises(QueryValidationError, match="not found"):
        await adapter.get_ddl("public", "ghost_table")


async def test_search_and_relationships(adapter):
    found = await adapter.search("user")
    assert any(o["name"] == "users" for o in found["objects"])
    assert any(c["column"] == "user_id" for c in found["columns"])

    relationships = (await adapter.relationships("public"))["relationships"]
    assert any(r["from_table"] == "orders" and r["to_table"] == "users" for r in relationships)


async def test_users_and_grants(adapter):
    users = await adapter.users()
    assert any(u["role"] == "test" and u["superuser"] for u in users)
    just_one = await adapter.users("test")
    assert len(just_one) == 1
    grants = await adapter.grants(obj="users")
    assert isinstance(grants, list)


async def test_read_happy_and_limit(adapter):
    rows = await adapter.read("SELECT * FROM users ORDER BY id", None, 1)
    assert len(rows) == 2  # limit + 1 so the caller can detect truncation
    all_rows = await adapter.read("SELECT * FROM users", None, None)
    assert len(all_rows) == 2


async def test_read_sad_bad_sql(adapter):
    with pytest.raises(Exception, match=r"(?i)syntax|exist"):
        await adapter.read("SELECT * FROM missing_table", None, 10)


async def test_read_only_transaction_blocks_writes_at_db_level(adapter):
    with pytest.raises(Exception, match="read-only"):
        await adapter.read("INSERT INTO users (name) VALUES ('intruso')", None, 10)


async def test_sample_and_explain(adapter):
    sample = await adapter.sample("public", "users", 1)
    assert len(sample) == 1
    plan = await adapter.explain("SELECT * FROM users WHERE id = 1")
    assert plan["plan"] is not None
    analyzed = await adapter.explain("SELECT * FROM users WHERE id = 1", analyze=True)
    assert "Execution Time" in str(analyzed["plan"])
    assert "Shared Hit Blocks" in str(analyzed["plan"])


async def test_explain_reports_cost_and_warns_over_threshold(adapter, pg_uri):
    """EXPLAIN surfaces the planner's total cost; a low max_plan_cost turns it into an actionable warning."""
    thrifty = PostgresAdapter(make_cfg("thrifty", pg_uri, max_plan_cost=1))
    try:
        plan = await thrifty.explain("SELECT * FROM users")
        assert "estimated_cost" in plan
        assert "cost_warning" in plan and "max_plan_cost 1" in plan["cost_warning"]
    finally:
        await thrifty.close()

    generous = await adapter.explain("SELECT * FROM users")
    assert "estimated_cost" in generous
    assert "cost_warning" not in generous


async def test_top_queries_happy(adapter):
    rows = await adapter.top_queries("total_time", 5, None)
    assert rows and "query" in rows[0]
    assert "temp_blks_written" in rows[0]
    assert "wal_bytes" in rows[0]


async def test_top_queries_absurd_sort(adapter):
    with pytest.raises(QueryValidationError, match="sort_by"):
        await adapter.top_queries("vibes", 5, None)


async def test_perf_suite(adapter):
    assert isinstance(await adapter.active_ops(0), list)
    assert isinstance(await adapter.blocking(), list)
    index_stats = await adapter.index_stats("public")
    assert any(i["table"] == "users" for i in index_stats["indexes"])
    assert index_stats["invalid"] == []
    table_stats = await adapter.table_stats("public")
    assert any(t["table"] == "users" for t in table_stats)
    health = await adapter.health()
    assert health["connections"]["max"] > 0
    settings = await adapter.settings("work_mem")
    assert any(s["name"] == "work_mem" for s in settings)


async def test_replication_standalone_primary(adapter):
    replication = await adapter.replication()
    assert replication["role"] == "primary"
    assert replication["replicas"] == []
    assert "note" in replication


async def test_logs_without_collector_gives_guidance(adapter):
    with pytest.raises(GuidanceError, match="logging_collector"):
        await adapter.logs()


async def test_write_happy_dry_run_and_abort(adapter):
    dry = await adapter.write("UPDATE users SET name = name", None, dry_run=True)
    assert dry == {"applied": False, "dry_run": True, "would_affect": 2}
    count = (await adapter.read("SELECT count(*) AS n FROM users WHERE name = 'Zed'", None, None))[0]["n"]
    assert count == 0

    aborted = await adapter.write("UPDATE users SET name = 'Zed'", None, expected_max_rows=1)
    assert aborted["applied"] is False
    assert aborted["affected"] == 2

    applied = await adapter.write("UPDATE users SET name = 'Zed' WHERE id = 1", None, expected_max_rows=1)
    assert applied == {"applied": True, "affected": 1}


async def test_kill_absurd_target(adapter):
    with pytest.raises(QueryValidationError, match="numeric"):
        await adapter.kill("not-a-pid")


async def test_kill_nonexistent_pid(adapter):
    result = await adapter.kill("999999")
    assert result["success"] is False


async def test_analyze_and_maintain(adapter):
    assert (await adapter.analyze("public", "users"))["status"] == "ok"
    assert (await adapter.maintain("public", "users"))["status"] == "ok"
    with pytest.raises(QueryValidationError, match="vacuum"):
        await adapter.maintain("public", "users", "defrag")


async def test_describe_missing_object_not_found(adapter):
    """Describing a nonexistent table raises a clear 'not found', never an empty result."""
    with pytest.raises(QueryValidationError, match="not found"):
        await adapter.describe_object("public", "ghost_table")


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


async def test_kill_running_query_terminates_it(adapter, pg_uri):
    """kill() cancels a query that is actually running: find its pid via active_ops, cancel it, watch it die."""
    victim = PostgresAdapter(make_cfg("victim", pg_uri))
    task = asyncio.create_task(victim.read("SELECT pg_sleep(30)", None, 1))
    try:
        pid = None
        for _ in range(100):
            ops = await adapter.active_ops(0)
            sleeper = next((op for op in ops if "pg_sleep" in (op.get("query") or "")), None)
            if sleeper is not None:
                pid = sleeper["pid"]
                assert "xact_age_ms" in sleeper
                break
            await asyncio.sleep(0.1)
        assert pid is not None, "pg_sleep never appeared in active_ops"

        result = await adapter.kill(str(pid))
        assert result["success"] is True
        with pytest.raises(Exception, match=r"(?i)cancel"):
            await task
    finally:
        task.cancel()
        await victim.close()


async def test_dry_run_does_not_execute_the_mutation(adapter):
    """dry_run/abort answer from a count(*) probe: a booby-trapped trigger proves the UPDATE never runs."""
    await adapter.write("CREATE TABLE IF NOT EXISTS trapped (id int)", None)
    await adapter.write("INSERT INTO trapped VALUES (1), (2)", None)
    await adapter.write(
        "CREATE OR REPLACE FUNCTION trap() RETURNS trigger AS 'BEGIN RAISE EXCEPTION ''trap fired''; END' "
        "LANGUAGE plpgsql",
        None,
    )
    await adapter.write("CREATE TRIGGER trap_upd BEFORE UPDATE ON trapped FOR EACH ROW EXECUTE FUNCTION trap()", None)
    try:
        dry = await adapter.write("UPDATE trapped SET id = id", None, dry_run=True)
        assert dry == {"applied": False, "dry_run": True, "would_affect": 2}

        aborted = await adapter.write("UPDATE trapped SET id = 0 WHERE id = 1", None, expected_max_rows=0)
        assert aborted["applied"] is False
        assert aborted["affected"] == 1

        with pytest.raises(Exception, match="trap fired"):
            await adapter.write("UPDATE trapped SET id = id", None)
    finally:
        await adapter.write("DROP TABLE IF EXISTS trapped CASCADE", None)
        await adapter.write("DROP FUNCTION IF EXISTS trap() CASCADE", None)


async def test_connections_identify_themselves(adapter):
    """Every session carries application_name so DBAs (and active_ops) can tell the tool's sessions apart."""
    rows = await adapter.read("SELECT current_setting('application_name') AS app", None, 1)
    assert rows[0]["app"] == "mcp-database/pg"


async def test_ddl_blocked_by_lock_fails_fast(adapter, pg_uri):
    """A write waiting on a table lock hits lock_timeout instead of queueing behind it indefinitely."""
    import psycopg

    holder = await psycopg.AsyncConnection.connect(pg_uri)
    fast = PostgresAdapter(make_cfg("locky", pg_uri, query_timeout_s=2))
    try:
        await holder.execute("LOCK TABLE users IN ACCESS EXCLUSIVE MODE")
        with pytest.raises(Exception, match=r"(?i)lock timeout"):
            await fast.write("ALTER TABLE users ADD COLUMN hacked int", None)
    finally:
        await holder.rollback()
        await holder.close()
        await fast.close()
    assert "hacked" not in {c["name"] for c in (await adapter.describe_object("public", "users"))["columns"]}


async def test_sample_falls_back_for_views(adapter):
    """TABLESAMPLE only works on tables; sampling a view transparently falls back to LIMIT."""
    await adapter.write("CREATE OR REPLACE VIEW users_view AS SELECT * FROM users", None)
    try:
        rows = await adapter.sample("public", "users_view", 1)
        assert len(rows) == 1
    finally:
        await adapter.write("DROP VIEW IF EXISTS users_view", None)


async def test_column_stats_after_analyze(adapter):
    """pg_stats exposes what the planner believes: rows appear after ANALYZE, filtered by column on demand."""
    await adapter.analyze("public", "users")
    rows = await adapter.column_stats("public", "users")
    assert {"id", "name", "email"} <= {r["column"] for r in rows}
    assert all("n_distinct" in r and "null_frac" in r for r in rows)

    only_email = await adapter.column_stats("public", "users", "email")
    assert [r["column"] for r in only_email] == ["email"]

    with pytest.raises(QueryValidationError, match="statistics"):
        await adapter.column_stats("public", "ghost_table")


async def test_explain_hypothetical_without_hypopg_gives_guidance(adapter):
    """Without the hypopg extension the tool explains exactly how to enable it; analyze+hypo is rejected."""
    with pytest.raises(GuidanceError, match="hypopg"):
        await adapter.explain(
            "SELECT * FROM users WHERE email = 'x'", hypothetical_indexes=["CREATE INDEX ON users(email)"]
        )

    with pytest.raises(QueryValidationError, match="planning"):
        await adapter.explain("SELECT 1", analyze=True, hypothetical_indexes=["CREATE INDEX ON users(email)"])
