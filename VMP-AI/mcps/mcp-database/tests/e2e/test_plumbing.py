"""Server plumbing: query-shape validation, error mapping, cap notes and adapter shutdown."""

from mcp_database.errors import GuidanceError

from .helpers import FakeAdapter, call, payload


async def test_read_query_sql_conn_rejects_mongo_query(mcp_server):
    result = await call(
        mcp_server, "db_read_query", {"conn": "ro", "query": {"collection": "users", "operation": "find"}}
    )
    assert result.isError
    assert "must be a SQL string" in result.content[0].text


async def test_write_query_sql_conn_rejects_mongo_query(mcp_server):
    result = await call(
        mcp_server, "db_write_query", {"conn": "rw", "query": {"collection": "users", "operation": "insertMany"}}
    )
    assert result.isError
    assert "must be a SQL string" in result.content[0].text


async def test_adapter_timeout_becomes_clear_error(mcp_server, monkeypatch):
    async def timed_out(self, query, params, limit):
        raise TimeoutError

    monkeypatch.setattr(FakeAdapter, "read", timed_out)
    result = await call(mcp_server, "db_read_query", {"conn": "ro", "query": "SELECT 1"})
    assert result.isError
    assert "exceeded 30s" in result.content[0].text


async def test_adapter_error_redacts_uri_password(mcp_server, monkeypatch):
    async def boom(self, query, params, limit):
        raise ValueError("connect failed: postgresql://u:s3cret@h/db")

    monkeypatch.setattr(FakeAdapter, "read", boom)
    result = await call(mcp_server, "db_read_query", {"conn": "ro", "query": "SELECT 1"})
    assert result.isError
    text = result.content[0].text
    assert "s3cret" not in text
    assert "ValueError" in text


async def test_guidance_error_passes_through_untouched(mcp_server, monkeypatch):
    async def needs_extension(self, sort_by, limit, database=None):
        raise GuidanceError("pg_stat_statements is not enabled; run CREATE EXTENSION pg_stat_statements")

    monkeypatch.setattr(FakeAdapter, "top_queries", needs_extension)
    result = await call(mcp_server, "db_perf_top_queries", {"conn": "ro"})
    assert result.isError
    assert "CREATE EXTENSION pg_stat_statements" in result.content[0].text


async def test_search_results_capped_with_note(mcp_server, monkeypatch):
    async def many(self, pattern, scope=None):
        return {"objects": [{"name": f"t{i}"} for i in range(100)], "columns": []}

    monkeypatch.setattr(FakeAdapter, "search", many)
    data = payload(await call(mcp_server, "db_schema_search", {"conn": "ro", "pattern": "t"}))
    assert "capped at 100" in data["note"]


async def test_lifespan_closes_adapters_on_session_shutdown(mcp_server, monkeypatch):
    closed = []

    async def record_close(self):
        closed.append(self.config.name)

    monkeypatch.setattr(FakeAdapter, "close", record_close)
    payload(await call(mcp_server, "db_read_query", {"conn": "ro", "query": "SELECT 1"}))
    assert "ro" in closed


async def test_lifespan_swallows_adapter_close_errors(mcp_server, monkeypatch):
    async def bad_close(self):
        raise RuntimeError("close failed")

    monkeypatch.setattr(FakeAdapter, "close", bad_close)
    payload(await call(mcp_server, "db_read_query", {"conn": "ro", "query": "SELECT 1"}))


async def test_driver_native_values_are_serialized_not_crashed(mcp_server, monkeypatch):
    # A tool result carrying non-JSON-native values (e.g. MongoDB ObjectId, bytes) must serialize
    # cleanly through the MCP boundary — regression guard for the cross-engine serialization bug.
    class ObjectId:
        def __str__(self):
            return "651f9b2c"

    async def exotic_read(self, query, params, limit):
        return [{"_id": ObjectId(), "blob": b"\xff\xfe", "n": 1}]

    monkeypatch.setattr(FakeAdapter, "read", exotic_read)
    data = payload(await call(mcp_server, "db_read_query", {"conn": "ro", "query": "SELECT 1"}))
    assert data["rows"] == [{"_id": "651f9b2c", "blob": "<2 bytes>", "n": 1}]
