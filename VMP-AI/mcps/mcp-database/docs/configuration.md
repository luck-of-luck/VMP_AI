# Configuration

**One instance, one connection, environment variables only.** The binary takes no command-line arguments: each `mcpServers` entry configures its single connection through environment variables and points at exactly one database. To reach more databases, add more entries, each running its own instance. Everything lives in the MCP client config (e.g. `.mcp.json`), with no separate file to manage.

## Table of Contents

- [Environment variables](#environment-variables)
- [Minimal entry](#minimal-entry)
- [Multiple entries and modes](#multiple-entries-and-modes)
- [Local checkout](#local-checkout)
- [Examples and permissions](#examples-and-permissions)

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `URI` | **required** | Connection URI: `postgresql://`, `mysql://`, `mariadb://`, `sqlite:///path.db`, `mongodb://`, `mongodb+srv://`, `redis://` or `rediss://` |
| `ENGINE_TYPE` | inferred from the URI scheme | `postgres` \| `mysql` \| `mariadb` \| `sqlite` \| `mongodb` \| `redis`; a mismatch with the URI scheme is rejected at startup |
| `NAME` | the engine | What tools receive as `conn` |
| `MODE` | `read_only` | `read_only` \| `read_write` \| `monitor` |
| `TIMEOUT` | `30` | Query timeout in seconds |
| `ROW_LIMIT` | `500` | Rows per result |
| `EXPORT_MAX_ROWS` | `100000` | Row cap for `db_read_export`; the result reports `truncated: true` when hit |
| `POOL_SIZE` | `2` | Connection pool size per instance (also the per-connection concurrency cap) |
| `CONNECT_TIMEOUT` | `5` | Seconds to establish/select a connection (pg/mysql connect, mongo selection + connect, redis socket, the reachability ping) |
| `LOCK_TIMEOUT_MAX` | `10` | Upper bound in seconds for the lock/busy timeout (otherwise half the query budget); pg/mysql/sqlite |
| `MAX_RESPONSE_BYTES` | `1048576` | Byte budget for one tool result; rows beyond it are dropped with `truncated: true` |
| `HARD_ROW_CAP` | `5000` | Absolute ceiling on rows per result, above `ROW_LIMIT`/`n` |
| `VECTOR_MIN_CANDIDATES` | `100` | Lower bound for MongoDB `numCandidates` in `db_read_vector_search` |
| `VECTOR_MAX_CANDIDATES` | `10000` | Upper bound for MongoDB `numCandidates` in `db_read_vector_search` |
| `PASSWORD_ENV` | — | Name of another variable holding the password for the URI user (keeps secrets out of the URI) |
| `WRITE_OPS` | all | JSON array, subset of `["insert", "update", "delete", "ddl"]` |
| `DATABASE_MODES` | `{}` | JSON object mapping database name → mode, e.g. `{"prod": "read_only"}` |
| `REDACT_FIELDS` | `[]` | JSON array of field names to mask; `["*"]` masks every value |
| `TOOLS` | all | JSON array: expose **only** these tools (allowlist), e.g. `["db_read_query", "db_schema_connections"]` |
| `DISABLE_TOOLS` | `[]` | JSON array: hide these tools (denylist); mutually exclusive with `TOOLS` |
| `COMPACT_OUTPUT` | `false` | Read results as `{columns, rows: [[...]]}` (keys stated once) instead of `rows: [{...}]`, to save context |
| `AUDIT_LOG` | `~/.local/state/mcp-database/audit.log` | JSONL audit log path |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |

## Minimal entry

Only `URI` is required; everything else has a safe default (`MODE` defaults to `read_only`). All
configuration lives in the `env` block; the Docker `args` line is a fixed forwarding template — the
`-e` flags carry no values and absent variables are ignored, so the same line serves every entry:

```json
{
  "mcpServers": {
    "db-postgres": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--network", "host",
               "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
               "ghcr.io/diegobulhoes/mcp-database:latest"],
      "env": { "URI": "postgresql://dev:dev@localhost:5432/app" }
    }
  }
}
```

Per-engine examples — each engine connecting locally and to an external/managed service — are in
[connections.md](connections.md).

## Multiple entries and modes

The entry key (`db-postgres-stg`) namespaces the tools (`mcp__db-postgres-stg__db_read_query`); `NAME` is the connection name the tools receive as `conn`. The same database can appear in several entries with different modes (e.g. staging `read_write`, production `monitor`):

```json
{
  "mcpServers": {
    "db-postgres-stg": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm", "--network", "host",
        "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
        "ghcr.io/diegobulhoes/mcp-database:latest"
      ],
      "env": {
        "NAME": "pg_app_stg",
        "URI": "postgresql://app@stg.internal:5432/app",
        "MODE": "read_write"
      }
    },
    "db-postgres-prod": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm", "--network", "host",
        "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
        "-e", "PASSWORD_ENV", "-e", "PG_PROD_PASSWORD",
        "ghcr.io/diegobulhoes/mcp-database:latest"
      ],
      "env": {
        "NAME": "pg_app_prod",
        "URI": "postgresql://monitor@prod.internal:5432/app",
        "MODE": "monitor",
        "PASSWORD_ENV": "PG_PROD_PASSWORD"
      }
    }
  }
}
```

## Local checkout

Running from a local checkout instead of Docker: swap `"command": "docker"` for `"command": "uv"` with `"args": ["run", "--directory", "/path/to/mcp-database", "mcp-database"]` and keep the same `"env"` block (no `-e` forwarding needed outside Docker).

> The published artifact is the [Docker image](docker.md); for everything else, run `uv run --directory` from a clone as shown here. The package is not on PyPI.

## Examples and permissions

More examples in [examples/](examples/): [mcp.json](examples/mcp.json) and a ready-made [Claude Code permission allowlist](examples/claude-permissions.json) that unlocks the safe tools once and keeps prompts only for `db_write_query` and `db_admin_*`. Permissions are namespaced by the `mcpServers` entry key (`mcp__db-postgres__db_read_query`), so keep the allowlist in sync with your entry names.
