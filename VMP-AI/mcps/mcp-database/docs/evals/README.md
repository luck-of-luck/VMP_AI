# Agent evaluations

Read-only questions with verified answers (28 across seven files), stored as JSON lists of
`{"question", "answer"}` objects. They test whether an LLM agent can answer realistic questions using only
the mcp-database tools, a fourth validation layer on top of the unit, e2e, and integration tests.

## Table of Contents

- [Question files](#question-files)
- [Seeds](#seeds)
- [Runner](#runner)
- [Adding questions](#adding-questions)

## Question files

| File | Connection | Questions | Covers |
|------|------------|-----------|--------|
| `evaluation-postgres.json` | `pg_app` | 8 | schema, counts, pgvector KNN, full-text search, search indexes |
| `evaluation-mysql.json` | `mysql_app` | 4 | seed data, FULLTEXT search, search indexes |
| `evaluation-mariadb.json` | `mariadb_app` | 3 | seed data, FULLTEXT search |
| `evaluation-sqlite.json` | `sqlite_app` | 3 | seed data, FTS5 text search |
| `evaluation-mongodb.json` | `mongo_app` | 3 | counts and aggregations |
| `evaluation-redis.json` | `redis_app` | 3 | key values, SCAN counting, sorted sets |
| `evaluation-atlas.json` | `atlas_app` | 4 | Atlas `$vectorSearch`, `$search`, search-index inspection |

## Seeds

Answers depend on the deterministic playground seeds. `make evals` is self-contained — it brings the
playground up, waits for readiness, loads every seed (including Atlas, waiting for the search indexes to
become queryable) and then runs all seven engines. The single-engine targets assume a playground that is
already up and seeded:

```bash
make up && make mongo-rs && make seed   # postgres (pgvector), mysql, mongodb
make atlas-local && make atlas-seed     # atlas file only (mongot on port 27018)
```

## Runner

The runner is `scripts/run_evals.py`: each question spawns a headless `claude -p` session (requires the
[claude CLI](https://docs.anthropic.com/en/docs/claude-code) logged in — no API key) with exactly one
stdio mcp-database server attached, configured through the same `NAME`/`URI`/`MODE` environment variables
a real client would use. A question passes when the expected answer appears in the reply.

Run everything with `make evals` (one report per engine lands in `temp/reports/evals-<engine>.md`), or a single
engine with `make eval-postgres` / `make eval-mysql` / `make eval-mongodb` / `make eval-atlas`. Override the
model with `EVAL_MODEL=<alias>` (default `sonnet`).

## Adding questions

Every question is independent, read-only, stable (schema facts, deterministic seed data, or startup
configuration), and has a single verifiable answer. When adding a question, verify the answer manually against
the seed before committing it.
