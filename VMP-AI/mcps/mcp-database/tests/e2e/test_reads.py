"""db_read_ tools: queries, sampling, export and masking."""

import json

import pytest

from .helpers import ROWS, FakeAdapter, call, payload


@pytest.fixture
def captured_read(monkeypatch):
    """Capture the exact query string the adapter receives, to observe source-side LIMIT injection."""
    box: dict[str, object] = {}

    async def spy(self, query, params, limit):
        box["query"] = query
        return list(ROWS)

    monkeypatch.setattr(FakeAdapter, "read", spy)
    return box


async def test_read_query_injects_limit_when_absent(mcp_server, captured_read):
    await call(mcp_server, "db_read_query", {"conn": "ro", "query": "SELECT * FROM users"})
    assert "LIMIT" in str(captured_read["query"]).upper()


async def test_read_query_keeps_existing_limit(mcp_server, captured_read):
    await call(mcp_server, "db_read_query", {"conn": "ro", "query": "SELECT * FROM users LIMIT 3"})
    assert captured_read["query"] == "SELECT * FROM users LIMIT 3"


async def test_read_query_with_params_is_not_rewritten(mcp_server, captured_read):
    await call(
        mcp_server,
        "db_read_query",
        {"conn": "ro", "query": "SELECT * FROM users WHERE id = %s", "params": [1]},
    )
    assert captured_read["query"] == "SELECT * FROM users WHERE id = %s"


async def test_read_query_happy(mcp_server):
    result = await call(mcp_server, "db_read_query", {"conn": "ro", "query": "SELECT * FROM users"})
    assert not result.isError
    data = payload(result)
    assert data["row_count"] == 2
    assert data["truncated"] is False
    assert "execution_ms" in data


async def test_read_query_mongo_happy(mcp_server):
    data = payload(
        await call(
            mcp_server,
            "db_read_query",
            {"conn": "mongo", "query": {"collection": "users", "operation": "find", "database": "app"}},
        )
    )
    assert data["row_count"] == 2


async def test_read_query_unknown_connection(mcp_server):
    result = await call(mcp_server, "db_read_query", {"conn": "ghost", "query": "SELECT 1"})
    assert result.isError
    assert "Unknown connection 'ghost'" in result.content[0].text


async def test_read_query_rejects_write_statement(mcp_server):
    result = await call(mcp_server, "db_read_query", {"conn": "rw", "query": "DELETE FROM users"})
    assert result.isError


async def test_read_query_masks_fields(mcp_server):
    data = payload(await call(mcp_server, "db_read_query", {"conn": "masked", "query": "SELECT * FROM users"}))
    assert all(row["email"] == "***" for row in data["rows"])
    assert all(row["id"] in (1, 2) for row in data["rows"])


async def test_read_query_masks_by_pattern(mcp_server):
    """redact_patterns masks fields by regex on their name, catching what an exact redact_fields list missed."""
    data = payload(await call(mcp_server, "db_read_query", {"conn": "pattern_masked", "query": "SELECT * FROM users"}))
    assert all(row["email"] == "***" for row in data["rows"])
    assert all(row["id"] in (1, 2) for row in data["rows"])


async def test_read_query_structure_mode_masks_everything(mcp_server):
    data = payload(await call(mcp_server, "db_read_query", {"conn": "structure", "query": "SELECT * FROM users"}))
    assert data["rows"][0] == {"id": "<int>", "email": "<string>"}


async def test_read_query_absurd_row_limit(mcp_server):
    result = await call(mcp_server, "db_read_query", {"conn": "ro", "query": "SELECT 1", "row_limit": 0})
    assert result.isError
    assert "row_limit" in result.content[0].text


async def test_truncated_read_includes_actionable_note(mcp_server):
    data = payload(await call(mcp_server, "db_read_query", {"conn": "ro", "query": "SELECT 1", "row_limit": 1}))
    assert data["truncated"] is True
    assert "db_read_export" in data["note"]


async def test_read_sample_happy_and_masked(mcp_server):
    data = payload(await call(mcp_server, "db_read_sample", {"conn": "ro", "database": "public", "object": "users"}))
    assert data["row_count"] == 2

    masked = payload(
        await call(mcp_server, "db_read_sample", {"conn": "masked", "database": "public", "object": "users", "n": 1})
    )
    assert masked["rows"][0]["email"] == "***"

    absurd = await call(mcp_server, "db_read_sample", {"conn": "ro", "database": "public", "object": "users", "n": -3})
    assert absurd.isError


async def test_read_export_json_applies_masking(mcp_server, tmp_path):
    target = tmp_path / "out" / "export.json"
    data = payload(
        await call(
            mcp_server,
            "db_read_export",
            {"conn": "masked", "query": "SELECT * FROM users", "path": str(target)},
        )
    )
    assert data["row_count"] == 2
    exported = json.loads(target.read_text())
    assert all(row["email"] == "***" for row in exported)


async def test_read_export_csv(mcp_server, tmp_path):
    target = tmp_path / "export.csv"
    payload(
        await call(
            mcp_server,
            "db_read_export",
            {"conn": "ro", "query": "SELECT * FROM users", "path": str(target), "format": "csv"},
        )
    )
    lines = target.read_text().splitlines()
    assert lines[0] == "email,id"
    assert len(lines) == 3


async def test_read_export_absurd_format(mcp_server, tmp_path):
    result = await call(
        mcp_server,
        "db_read_export",
        {"conn": "ro", "query": "SELECT 1", "path": str(tmp_path / "x.xml"), "format": "xml"},
    )
    assert result.isError


async def test_read_export_writes_audit_entry_with_query_shape(mcp_server, audit_path, tmp_path):
    target = tmp_path / "out.json"
    data = payload(
        await call(
            mcp_server,
            "db_read_export",
            {"conn": "ro", "query": "SELECT * FROM users WHERE id = 741", "path": str(target)},
        )
    )
    assert data["truncated"] is False
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["tool"] == "db_read_export"
    assert entry["ok"] is True
    assert entry["path"] == str(target)
    assert entry["format"] == "json"
    assert entry["affected"] == 2
    assert "741" not in entry["query"]
    assert "?" in entry["query"]


async def test_read_export_truncates_at_export_max_rows(mcp_server, tmp_path):
    target = tmp_path / "capped.json"
    data = payload(
        await call(
            mcp_server,
            "db_read_export",
            {"conn": "tiny_export", "query": "SELECT * FROM users", "path": str(target)},
        )
    )
    assert data["truncated"] is True
    assert data["row_count"] == 1
    assert len(json.loads(target.read_text())) == 1


async def test_read_export_failure_is_audited(mcp_server, audit_path, tmp_path, monkeypatch):
    async def boom(self, query, params, limit):
        raise ValueError("db exploded")

    monkeypatch.setattr(FakeAdapter, "read", boom)
    result = await call(
        mcp_server, "db_read_export", {"conn": "ro", "query": "SELECT 1", "path": str(tmp_path / "o.json")}
    )
    assert result.isError
    entry = json.loads(audit_path.read_text().splitlines()[-1])
    assert entry["tool"] == "db_read_export"
    assert entry["ok"] is False
    assert "db exploded" in entry["error"]


async def test_read_export_absurd_unicode_path(mcp_server, tmp_path):
    target = tmp_path / "relatório 😀" / "export.json"
    data = payload(await call(mcp_server, "db_read_export", {"conn": "ro", "query": "SELECT 1", "path": str(target)}))
    assert data["path"] == str(target)
    assert target.exists()


@pytest.mark.parametrize(
    "flt",
    [{"lang": "pt"}, {"tags": {"$in": ["a", "b"]}}, {"$and": [{"a": 1}, {"b": {"$gte": 2}}]}],
)
async def test_vector_search_mongo_benign_filters_pass(mcp_server, flt):
    """A benign MongoDB pre-filter passes the forbidden-stage scan and reaches the adapter."""
    result = await call(
        mcp_server,
        "db_read_vector_search",
        {
            "conn": "mongo",
            "database": "app",
            "object": "docs",
            "column": "emb",
            "vector": [0.1, 0.2],
            "index": "v",
            "filter": flt,
        },
    )
    assert not result.isError, result.content[0].text


@pytest.mark.parametrize(
    "flt",
    [{"$out": "stolen"}, {"a": {"$in": [{"$merge": "deep"}]}}, {"$facet": {"x": [{"$out": "y"}]}}],
)
@pytest.mark.parametrize("tool", ["db_read_vector_search", "db_read_text_search"])
async def test_search_tools_reject_write_stages_in_mongo_filter(mcp_server, tool, flt):
    """$out/$merge anywhere in a search pre-filter is rejected before the adapter runs."""
    arguments = {"conn": "mongo", "database": "app", "object": "docs", "filter": flt}
    if tool == "db_read_vector_search":
        arguments |= {"column": "emb", "vector": [0.1], "index": "v"}
    else:
        arguments |= {"query": "hello"}
    result = await call(mcp_server, tool, arguments)
    assert result.isError
    assert "not allowed" in result.content[0].text


@pytest.mark.parametrize(
    "flt",
    [{"tags": ["a", "b"]}, {"meta": {"$gt": 1}}, "brand=acme"],
)
async def test_text_search_sql_filter_must_be_scalar_map(mcp_server, flt):
    """SQL engines only take a flat column->scalar filter; nested/typed filters are MongoDB-only."""
    result = await call(
        mcp_server,
        "db_read_text_search",
        {"conn": "rw", "database": "public", "object": "docs", "query": "hello", "column": "title", "filter": flt},
    )
    assert result.isError


@pytest.mark.parametrize("flt", [{"lang": "pt"}, {"status": {"$ne": "draft"}}, None])
async def test_text_search_mongo_filters_pass(mcp_server, flt):
    result = await call(
        mcp_server,
        "db_read_text_search",
        {"conn": "mongo", "database": "app", "object": "docs", "query": "hello", "filter": flt},
    )
    assert not result.isError, result.content[0].text


async def test_compact_connection_returns_columnar(mcp_server):
    """A connection with compact=True returns {columns, rows:[[...]]} instead of dict-per-row."""
    result = await call(mcp_server, "db_read_query", {"conn": "compact", "query": "SELECT * FROM users"})
    body = payload(result)
    assert body["columns"] == ["id", "email"]
    assert body["rows"] == [[1, "a@b.c"], [2, "d@e.f"]]
    assert "row_count" in body


async def test_non_compact_connection_returns_dicts(mcp_server):
    """Default connections keep the dict-per-row shape (compact is opt-in)."""
    result = await call(mcp_server, "db_read_query", {"conn": "rw", "query": "SELECT * FROM users"})
    body = payload(result)
    assert body["rows"] == [{"id": 1, "email": "a@b.c"}, {"id": 2, "email": "d@e.f"}]
    assert "columns" not in body
