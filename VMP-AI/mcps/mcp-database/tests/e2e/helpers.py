import json

from mcp.shared.memory import create_connected_server_and_client_session

from mcp_database.adapters.base import Adapter
from mcp_database.config import parse_connection

ROWS = [{"id": 1, "email": "a@b.c"}, {"id": 2, "email": "d@e.f"}]


class FakeAdapter(Adapter):
    async def ping(self):
        return None

    async def list_databases(self):
        return [{"schema": "public"}]

    async def list_objects(self, database, object_type=None):
        return [{"name": "users", "type": "table", "approx_rows": 2}]

    async def describe_object(self, database, obj, *, sample=True):
        return {"columns": [{"name": "id", "type": "int"}], "sampled": sample}

    async def get_ddl(self, database, obj):
        return {"ddl": "CREATE TABLE users (id int);"}

    async def search(self, pattern, scope=None):
        return {"objects": [], "columns": []}

    async def relationships(self, database, obj=None):
        return {"relationships": []}

    async def users(self, user=None):
        return [{"role": "app"}]

    async def grants(self, user=None, obj=None):
        return [{"grantee": "app", "privilege": "SELECT"}]

    async def read(self, query, params, limit):
        return list(ROWS)

    async def sample(self, database, obj, n):
        return list(ROWS[:n])

    async def explain(self, query, *, analyze=False, hypothetical_indexes=None):
        return {"plan": {"analyze": analyze}, "hypothetical_indexes": hypothetical_indexes}

    async def top_queries(self, sort_by, limit, database=None):
        return [{"query": "SELECT 1", "calls": 10}]

    async def active_ops(self, min_duration_ms=0):
        return []

    async def blocking(self):
        return []

    async def index_stats(self, database=None):
        return {"indexes": [], "unused": []}

    async def column_stats(self, database, obj, column=None):
        return [
            {"column": "id", "n_distinct": -1, "most_common_vals": None},
            {"column": "email", "n_distinct": 2, "most_common_vals": "{a@b.c,d@e.f}"},
        ]

    async def table_stats(self, database=None):
        return []

    async def health(self):
        return {"connections": {"used": 1, "max": 100}}

    async def replication(self):
        return {"role": "primary", "replicas": []}

    async def settings(self, pattern=None):
        return [{"name": "work_mem", "setting": "4MB"}]

    async def logs(self, limit=100, level=None):
        return [{"line": "log line"}]

    async def write(self, query, params, *, dry_run=False, expected_max_rows=None):
        if expected_max_rows is not None and expected_max_rows < 2:
            return {"applied": False, "affected": 2, "aborted": "above expected_max_rows"}
        if dry_run:
            return {"applied": False, "dry_run": True, "would_affect": 2}
        return {"applied": True, "affected": 2}

    async def kill(self, target_id, *, force=False):
        return {"target": target_id, "success": True}

    async def analyze(self, database, obj=None):
        return {"analyzed": f"{database}.{obj}"}

    async def maintain(self, database, obj, action=None):
        return {"maintained": f"{database}.{obj}"}

    async def vector_search(
        self, database, obj, column, vector, metric, limit, flt=None, index=None, num_candidates=None
    ):
        return [{"id": 1, "email": "a@b.c", "distance": 0.12}]

    async def text_search(self, database, obj, query, *, column=None, index=None, limit, flt=None, language=None):
        return [{"id": 1, "email": "a@b.c", "rank": 0.9}]

    async def search_indexes(self, database=None, obj=None):
        return {"indexes": [{"index": "emb_idx", "type": "vector", "metric": "cosine", "valid": True}]}

    async def vector_stats(self, database=None, obj=None):
        return {"vector_columns": [], "vector_indexes": [], "settings": {}, "index_builds": []}

    async def storage(self, database=None):
        return {"databases": [{"database": "app", "bytes": 1024}], "temp": {}, "dead_tuples": []}

    async def config_signals(self):
        return {"cache": {"hits": 99, "reads": 1}, "connections": {"current": 1, "max": 100}}

    async def index_signals(self, database=None):
        return {"unindexed_foreign_keys": [], "seq_scan_heavy": []}

    async def search_index_write(self, database, obj, action, name, definition=None):
        return {"applied": True, "action": action, "index": f"{database}.{name}"}

    async def cluster_action(self, action, seconds=None):
        return {"action": action, "success": True}


REGISTRY = {
    name: parse_connection(name, raw)
    for name, raw in {
        "rw": {"uri": "postgresql://u@h/db", "access_mode": "read_write"},
        "ro": {"uri": "postgresql://u@h/db", "access_mode": "read_only"},
        "mon": {"uri": "postgresql://u@h/db", "access_mode": "monitor"},
        "masked": {"uri": "postgresql://u@h/db", "access_mode": "read_only", "redact_fields": ["email"]},
        "pattern_masked": {
            "uri": "postgresql://u@h/db",
            "access_mode": "read_only",
            "redact_patterns": ["email$"],
        },
        "structure": {"uri": "postgresql://u@h/db", "access_mode": "read_only", "redact_fields": ["*"]},
        "limited": {"uri": "postgresql://u@h/db", "access_mode": "read_write", "write_ops": ["insert"]},
        "scoped": {"uri": "postgresql://u@h/db", "access_mode": "read_write", "database_modes": {"x": "read_only"}},
        "tiny_export": {"uri": "postgresql://u@h/db", "access_mode": "read_only", "export_max_rows": 1},
        "compact": {"uri": "postgresql://u@h/db", "access_mode": "read_write", "compact": True},
        "mysql_rw": {"uri": "mysql://u@h/db", "access_mode": "read_write"},
        "mariadb_rw": {"uri": "mariadb://u@h/db", "access_mode": "read_write"},
        "sqlite_rw": {"uri": "sqlite:///tmp/app.db", "access_mode": "read_write"},
        "mongo": {"uri": "mongodb://h:27017/app", "access_mode": "read_write"},
        "redis_rw": {"uri": "redis://h:6379/0", "access_mode": "read_write"},
    }.items()
}


async def call(mcp_server, tool, arguments):
    async with create_connected_server_and_client_session(mcp_server._mcp_server) as client:
        return await client.call_tool(tool, arguments)


def payload(result):
    assert result.content, "expected content"
    return json.loads(result.content[0].text)
