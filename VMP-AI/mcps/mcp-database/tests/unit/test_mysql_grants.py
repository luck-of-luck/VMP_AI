import pytest

from mcp_database.adapters.mysql import MySQLAdapter
from mcp_database.adapters.mysql.schema import _account_part
from mcp_database.config import parse_connection
from mcp_database.errors import QueryValidationError


def make_adapter():
    return MySQLAdapter(parse_connection("m", {"uri": "mysql://u@h/db", "access_mode": "read_only"}))


@pytest.mark.parametrize("value", ["app_user", "10.0.0.%", "::1", "host-name.local", "%", "a.b_c-d"])
def test_account_part_happy(value):
    assert _account_part(value) == value


@pytest.mark.parametrize("value", ["", "bob'", 'a"b', "x\\", "u@h", "😀", "a b", "x;DROP TABLE t", "a`b"])
def test_account_part_sad(value):
    with pytest.raises(QueryValidationError, match="account identifier"):
        _account_part(value)


async def test_grants_rejects_hostile_identity_before_touching_db():
    with pytest.raises(QueryValidationError):
        await make_adapter().grants("bob'-- @'%")


async def test_grants_composes_quoted_account(monkeypatch):
    adapter = make_adapter()
    captured = {}

    async def fake_fetch(query, params=None, *, limit=None, readonly=True):
        captured["query"] = query
        return [{"Grants for bob": "GRANT SELECT ON db.* TO 'bob'"}]

    monkeypatch.setattr(adapter, "_fetch", fake_fetch)
    rows = await adapter.grants("bob@10.0.0.%")
    assert captured["query"] == "SHOW GRANTS FOR 'bob'@'10.0.0.%'"
    assert rows == [{"user": "bob@10.0.0.%", "grant": "GRANT SELECT ON db.* TO 'bob'"}]
