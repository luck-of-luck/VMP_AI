# mcp-database

[![CI](https://github.com/DiegoBulhoes/mcp-database/actions/workflows/test.yml/badge.svg)](https://github.com/DiegoBulhoes/mcp-database/actions/workflows/test.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

MCP database server for **PostgreSQL**, **MySQL**, **MariaDB**, **SQLite**, **MongoDB**, and **Redis**. One connection per instance, per-connection access modes, and a full performance-diagnosis toolkit for dev, SRE, and DBA workflows.

## Contents

- [Supported databases](#supported-databases)
- [Features](#features)
- [Tools](#tools)
- [Quick start](#quick-start)
- [Configuration](docs/configuration.md)
- [Architecture](docs/architecture.md)
- [Querying](#querying)
- [Docker](docs/docker.md)
- [Connecting to each engine](docs/connections.md)
- [Development](docs/development.md)
- [References](#references)
- [License](#license)

## Supported databases

One connection per instance; the engine is inferred from the URI scheme (override with `ENGINE_TYPE`).

| Database | URI scheme | `ENGINE_TYPE` | Driver | Highlights |
|----------|------------|---------------|--------|------------|
| **PostgreSQL** | `postgresql://`, `postgres://` | `postgres` | psycopg 3 | pgvector KNN, native full-text search, HypoPG hypothetical indexes, transactional DDL dry-run, planner column stats |
| **MySQL** | `mysql://` | `mysql` | aiomysql | FULLTEXT search, planner column stats + histograms, `performance_schema` diagnostics |
| **MariaDB** | `mariadb://` | `mariadb` | aiomysql | Follows the MySQL surface with the engine differences absorbed (`max_statement_time`, `SHOW SLAVE HOSTS`) |
| **SQLite** | `sqlite:///relative.db`, `sqlite:////absolute.db` | `sqlite` | aiosqlite | File databases with structurally read-only reads (`mode=ro`), FTS5 text search, EXPLAIN QUERY PLAN |
| **MongoDB** | `mongodb://`, `mongodb+srv://` | `mongodb` | PyMongo (async) | Atlas `$search` / `$vectorSearch`, aggregation reads, replica-set / shard topology |
| **Redis** | `redis://`, `rediss://` | `redis` | redis-py (async) | Allowlisted command envelope (`FLUSH*`/`EVAL`/`KEYS` never allowed), SCAN-based inspection, SLOWLOG/INFO/ACL diagnostics |

Engine support per tool (some features are engine-specific — e.g. HypoPG is PostgreSQL-only) is in [docs/tools.md](docs/tools.md). CI verifies every tool against real PostgreSQL 16/17, MySQL 8.0/8.4, MariaDB 10.11/11.4, SQLite, MongoDB 7/8, and Redis 7/8 (plus pgvector and Atlas-local images) on every push.

## Features

- **39 tools, risk-encoded names.** `db_schema_*` / `db_read_*` / `db_perf_*` never write (safe to always-allow); `db_write_*` / `db_admin_*` need approval.
- **Vector + full-text search.** pgvector KNN and FTS (PostgreSQL), FULLTEXT (MySQL), Atlas `$search` / `$vectorSearch` (MongoDB), plus index inspection and quality diagnostics.
- **Cluster tooling.** Replication-lag and topology triage (`db_perf_cluster`) with audited actions: promote, start/stop replica, step down, freeze.
- **Access modes per connection.** `read_write`, `read_only`, `monitor` (perf analysis with no data access, for production with PII).
- **Fail-closed read validation.** sqlglot rejects writes, DDL, multi-statement and dangerous functions; MongoDB is limited to a read-only op allowlist.
- **Fine-grained write control.** `write_ops` limits which operations run; `database_modes` sets a different mode per database.
- **Write safety belts.** `dry_run` (execute, roll back, report impact) and `expected_max_rows` (auto-abort oversized writes).
- **PII masking.** `redact_fields` masks values with `***`; `["*"]` shows type placeholders only, never values.
- **Audit log.** Every write, admin and export call is logged as JSONL (mode 600); literals become `?`, so PII never touches disk.
- **Result limits.** 500 rows / 1 MiB per response with source-side `LIMIT` injection; `db_read_export` streams big results to JSON/CSV.

## Tools

Full reference with parameters and per-database support indicators: [docs/tools.md](docs/tools.md).

| Class | Tools | Safe to always-allow |
|-------|-------|----------------------|
| `db_schema_` | connections, databases, objects, describe, ddl, search, relationships, users, grants, search_indexes | ✅ |
| `db_read_` | query, sample, export, vector_search, text_search | ✅ |
| `db_perf_` | explain, column_stats, diagnose, top_queries, active_ops, blocking, index_stats, table_stats, health, replication, settings, logs, vector_stats, cluster | ✅ |
| `db_write_` | query (with `dry_run` / `expected_max_rows`), search_index | case by case |
| `db_admin_` | kill, analyze, maintain, cluster | case by case |

Access-mode matrix:

| Class | `read_write` | `read_only` | `monitor` |
|-------|:---:|:---:|:---:|
| `db_schema_` | ✅ | ✅ | ✅ (no data sampling) |
| `db_read_` | ✅ | ✅ | ❌ |
| `db_perf_` | ✅ | ✅ | ✅ |
| `db_write_` / `db_admin_` | ✅ | ❌ | ❌ |

## Quick start

Requirements: Docker (runs both the playground databases and the published server image). [uv](https://docs.astral.sh/uv/) is only needed for [local development](docs/development.md).

```bash
# 1. Clone (for the playground compose file and seed data)
git clone https://github.com/DiegoBulhoes/mcp-database.git && cd mcp-database

# 2. Start and seed the playground databases (PostgreSQL + MySQL + MongoDB)
make up && make mongo-rs && make seed

# 3. Register with Claude Code — runs the published image, one connection per server entry.
#    All configuration lives in --env; the docker -e flags are a fixed forwarding template.
claude mcp add db-postgres \
  --env URI="postgresql://dev:dev@localhost:5432/app" \
  --env ENGINE_TYPE=postgres \
  --env MODE=read_write \
  -- docker run -i --rm --network host -e URI -e ENGINE_TYPE -e MODE -e NAME \
       ghcr.io/diegobulhoes/mcp-database:latest
```

> `--network host` lets the container reach `localhost` databases (Linux). On macOS/Windows Docker Desktop, drop it and use `host.docker.internal` in the URI instead.

Then ask Claude things like *"why is pg_app slow?"* and it will chain `db_perf_active_ops` → `db_perf_blocking` → `db_perf_top_queries` → `db_perf_explain` without a single permission prompt (see below).

## Querying

You don't call the tools yourself; your AI assistant does, picking the connection by name (it discovers what exists via `db_schema_connections`). You just ask in natural language:

| You ask | The assistant calls |
|---------|--------------------|
| *"how many orders over 100 in pg_app?"* | `db_read_query(conn="pg_app", query="SELECT count(*) FROM orders WHERE total > 100")` |
| *"top pages by clicks in mongo_app"* | `db_read_query(conn="mongo_app", query={"collection": "events", "operation": "aggregate", "pipeline": [{"$group": {"_id": "$page", "n": {"$sum": 1}}}]})` |
| *"why is pg_app slow?"* | `db_perf_active_ops` → `db_perf_blocking` → `db_perf_top_queries` → `db_perf_explain` (the SRE runbook, no prompts) |
| *"upgrade user 42 to the pro plan"* | `db_write_query(conn="pg_app", query="UPDATE users SET plan = 'pro' WHERE id = 42", expected_max_rows=1)` (this one asks for your approval) |

The `query` argument depends on the connection type:

- **PostgreSQL / MySQL:** a SQL string. `db_read_query` accepts only SELECT/UNION/VALUES (parser-validated, fail-closed); everything else goes through `db_write_query`.
- **MongoDB:** a JSON object `{"collection", "operation", ...}`. Reads: `find`, `aggregate`, `countDocuments`, `distinct`, `listIndexes`; writes (via `db_write_query`): `insertMany`, `updateMany`, `deleteMany`, `createIndex`.

Example `query` values:

```sql
SELECT id, total FROM orders WHERE total > 100 ORDER BY total DESC LIMIT 20
```

```json
{"collection": "events", "operation": "aggregate",
 "pipeline": [{"$group": {"_id": "$page", "n": {"$sum": 1}}}, {"$sort": {"n": -1}}]}
```

Write safety belts on `db_write_query`:

- **Unbounded-mutation guard**: an `UPDATE`/`DELETE` with no `WHERE` (or a MongoDB `updateMany`/`deleteMany` with an empty filter) is rejected outright unless the caller declares intent — either a `dry_run` or an `expected_max_rows`. This stops a careless model from wiping a whole table without saying so. (`DROP`/`TRUNCATE` are explicit by nature and stay allowed.)
- `dry_run: true` executes inside a transaction and rolls back, reporting how many rows *would* be affected.
- `expected_max_rows: N` aborts with rollback if the write would affect more than N rows (catches a missing WHERE before it hurts).

## References

Projects and resources that shaped this server's design:

- [Model Context Protocol](https://modelcontextprotocol.io): protocol specification and the [Python SDK](https://github.com/modelcontextprotocol/python-sdk) (FastMCP) this server is built on.
- [anthropics/skills](https://github.com/anthropics/skills) (Anthropic): two skills from this repo are bundled in `.claude/skills/`: [mcp-builder](https://github.com/anthropics/skills/tree/main/skills/mcp-builder), whose best practices this server was audited against (tool naming with the `db_` service prefix, parameter descriptions, annotations, actionable errors, and the [agent evaluations](docs/evals/) format), and [algorithmic-art](https://github.com/anthropics/skills/tree/main/skills/algorithmic-art) for generative-art sessions.
- [postgres-mcp](https://github.com/crystaldba/postgres-mcp) (Crystal DBA): inspiration for access modes, safe SQL execution, and the performance/health tool set.
- [mongodb-mcp-server](https://github.com/mongodb-js/mongodb-mcp-server) (MongoDB): inspiration for the export tool, byte-based response limits, and server log access.
- [mcp-server-mysql](https://github.com/benborla/mcp-server-mysql) (Ben Borla): inspiration for per-operation write permissions (`write_ops`) and per-database modes (`database_modes`).

## License

[Apache 2.0](LICENSE)
