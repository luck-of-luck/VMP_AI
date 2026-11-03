"""RedisAdapter branches a real container does not reach: ACL failures, type dispatch, validation."""

import pytest
from redis.exceptions import ResponseError

from mcp_database.adapters.redis import RedisAdapter
from mcp_database.config import parse_connection
from mcp_database.errors import GuidanceError, QueryValidationError


class FakePipeline:
    def __init__(self, types):
        self._types = types

    def type(self, key):
        return None

    async def execute(self):
        return self._types


class FakeRedis:
    def __init__(self, **handlers):
        self._handlers = handlers

    def get_connection_kwargs(self):
        return {"db": 0}

    def pipeline(self, transaction=False):
        return FakePipeline(self._handlers["pipeline_types"])

    def __getattr__(self, name):
        handler = self._handlers.get(name)
        if handler is None:
            raise AttributeError(name)

        async def call(*args, **kwargs):
            result = handler(*args, **kwargs) if callable(handler) else handler
            if isinstance(result, Exception):
                raise result
            return result

        return call


def make_adapter(monkeypatch, **handlers):
    adapter = RedisAdapter(parse_connection("rd", {"uri": "redis://h:6379/0"}))
    monkeypatch.setattr(adapter, "_get_client", lambda: FakeRedis(**handlers))
    return adapter


class TestValidation:
    async def test_unknown_object_type_rejected(self, monkeypatch):
        """list_objects validates the type filter before touching the server."""
        adapter = make_adapter(monkeypatch)
        with pytest.raises(QueryValidationError, match="Unknown object_type"):
            await adapter.list_objects("0", object_type="banana")

    async def test_read_rejects_bind_params(self, monkeypatch):
        """Redis commands carry everything in args; bind params are a SQL concept."""
        adapter = make_adapter(monkeypatch)
        with pytest.raises(QueryValidationError, match="no bind parameters"):
            await adapter.read({"command": "GET", "args": ["k"], "database": None}, ["extra"], 1)

    async def test_kill_requires_numeric_id(self, monkeypatch):
        adapter = make_adapter(monkeypatch)
        with pytest.raises(QueryValidationError, match="numeric client id"):
            await adapter.kill("abc; DROP")

    async def test_foreign_cluster_action_guides(self, monkeypatch):
        adapter = make_adapter(monkeypatch)
        with pytest.raises(GuidanceError, match="promote"):
            await adapter.cluster_action("step_down")


class TestObjectsAndSampling:
    async def test_list_objects_filters_by_type(self, monkeypatch):
        """The type filter keeps only keys of the requested Redis type."""
        adapter = make_adapter(
            monkeypatch, scan=lambda cursor=0, count=200: (0, ["a", "b"]), pipeline_types=["string", "hash"]
        )
        rows = await adapter.list_objects("0", object_type="hash")
        assert rows == [{"name": "b", "type": "hash"}]

    async def test_sample_missing_key_not_found(self, monkeypatch):
        adapter = make_adapter(monkeypatch, type=lambda key: "none")
        with pytest.raises(QueryValidationError, match="not found"):
            await adapter.sample("0", "ghost", 3)

    async def test_sample_set_members(self, monkeypatch):
        adapter = make_adapter(monkeypatch, type=lambda key: "set", srandmember=lambda key, n: ["x", "y"])
        assert await adapter.sample("0", "tags", 2) == [{"value": "x"}, {"value": "y"}]

    async def test_sample_stream_guides(self, monkeypatch):
        adapter = make_adapter(monkeypatch, type=lambda key: "stream")
        with pytest.raises(GuidanceError, match="stream"):
            await adapter.sample("0", "events", 2)

    async def test_hash_and_zset_flat_pairs_normalize(self, monkeypatch):
        """Flat [field, value, ...] replies are zipped into rows."""
        adapter = make_adapter(monkeypatch, type=lambda key: "hash", hrandfield=lambda key, n, withvalues: ["f", "v"])
        assert await adapter.sample("0", "h", 1) == [{"field": "f", "value": "v"}]
        adapter = make_adapter(monkeypatch, type=lambda key: "zset", zrandmember=lambda key, n, ws: ["m", "1.5"])
        assert await adapter.sample("0", "z", 1) == [{"member": "m", "score": "1.5"}]


class TestAclBranches:
    async def test_users_without_acl_guides(self, monkeypatch):
        adapter = make_adapter(monkeypatch, acl_list=ResponseError("NOPERM"))
        with pytest.raises(GuidanceError, match="Requires Redis 6"):
            await adapter.users()

    async def test_grants_error_guides_and_missing_user_not_found(self, monkeypatch):
        adapter = make_adapter(monkeypatch, acl_getuser=ResponseError("NOPERM"))
        with pytest.raises(GuidanceError, match="Requires Redis 6"):
            await adapter.grants("dev")
        adapter = make_adapter(monkeypatch, acl_getuser=lambda user: None)
        with pytest.raises(QueryValidationError, match="not found"):
            await adapter.grants("ghost")

    async def test_grants_strips_password_hashes(self, monkeypatch):
        """ACL password hashes never reach the agent."""
        adapter = make_adapter(monkeypatch, acl_getuser=lambda user: {"keys": "~*", "passwords": ["hash"]})
        rows = await adapter.grants("dev")
        assert rows == [{"user": "dev", "keys": "~*"}]


class TestInfoBranches:
    async def test_replica_replication_fields(self, monkeypatch):
        adapter = make_adapter(
            monkeypatch,
            info=lambda section=None: {
                "role": "slave",
                "master_link_status": "up",
                "master_host": "primary",
                "master_last_io_seconds_ago": 1,
            },
        )
        result = await adapter.replication()
        assert result == {
            "role": "slave",
            "master_link_status": "up",
            "master_host": "primary",
            "seconds_since_last_io": 1,
        }

    async def test_top_queries_decodes_bytes_commands(self, monkeypatch):
        adapter = make_adapter(
            monkeypatch,
            slowlog_get=lambda limit: [
                {"id": 1, "start_time": 2, "duration": 30, "command": b"GET k", "client_address": "c"}
            ],
        )
        rows = await adapter.top_queries("duration", 5)
        assert rows[0]["command"] == "GET k"
