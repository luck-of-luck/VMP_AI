# CLAUDE.md

Multi-database MCP server (PostgreSQL, MySQL, MariaDB, SQLite, MongoDB, Redis) over stdio. Python 3.12, managed with `uv`.

- References: `docs/architecture.md` (decisions, component map, request flow, failure modes, runbook), `docs/tools.md` (39 tools, per-engine support), `docs/configuration.md`, `docs/connections.md` (per-engine local/external examples), `docs/examples/`.
- `temp/` is gitignored scratch space
- `scripts/` holds standalone dev/build scripts (see `scripts/README.md`); never import from it in `src/` or `tests/`.

## Commands

```bash
make install            # uv sync
make lint               # ruff check + format check (must pass clean)
make fmt                # autofix + reformat
make test-unit          # fast: tests/unit + tests/e2e, no Docker
make test-integration   # real databases via testcontainers (requires Docker)
make test-cluster       # multi-node topologies incl. failure scenarios (crash/failover/quorum); own CI job, never in the coverage gate
make test               # full suite; 95% coverage gate; HTML report in temp/reports/coverage/
make up && make mongo-rs && make seed  # playground + seed data (pgvector pg; host ports: mysql 3306, mariadb 3307, mongo 27019, redis 6380; sqlite → temp/playground.db)
make atlas-local && make atlas-seed    # optional: mongodb-atlas-local (mongot) on port 27018
make evals              # one-shot agent evals via the logged-in claude CLI; reports in temp/reports/
make run                # run the server against the playground PostgreSQL
uv run pytest tests/unit/test_guard_sql.py -k name  # single test
```

## Architecture

Full picture in `docs/architecture.md`. Map:

- `entry.py` — env-only config, no CLI: one connection per instance (`URI` required); more databases = more MCP entries.
- `server.py` — `build_server` only: assembles FastMCP, applies `TOOLS`/`DISABLE_TOOLS`, lifespan closes pools (the only close hook).
- `tools/` — one module per risk class (`schema.py`, `read.py`, `perf.py`, `write_admin.py`) + `params.py` + `context.py` (`ToolContext` orchestrates validation, timeout, audit); `perf.py`'s pure section-to-findings summarizers live in `perf_summary.py`. Prefix encodes risk: `db_schema_`/`db_read_`/`db_perf_` never write; `db_write_`/`db_admin_` are destructive and audited.
- `guard.py` — all authorization and query validation, fail-closed. SQL via sqlglot (`_DIALECTS`); MongoDB and Redis via envelope allowlists (`helpers/mongo_query.py`, `helpers/redis_query.py`).
- `adapters/` — `Adapter` ABC + shared `SQLAdapter` in `base.py`; engine features declared in `CAPABILITIES`. Every engine is a package: the full engines (`postgres/`, `mysql/`, `mongodb/`, `sqlite/`, `redis/`) are split by area into mixins mirroring `tools/` (`schema.py`/`read.py`/`perf.py`/`write.py` + optional `_common.py`, composed in `__init__.py`); `mariadb/` holds only its `MySQLAdapter` overrides in `__init__.py` (no mixins — it inherits everything). Import path is unchanged (`from .postgres import PostgresAdapter`).
- `formatter.py` — truncation, masking, `compact`, `sanitize_error`; `audit.py` — hash-chained JSONL shapes; `helpers/` — `sql_ast.py`, `mongo_query.py`, `connection_fields.py`.

## Invariants (do not weaken)

Mechanisms are detailed in `docs/architecture.md`; these are the rules.

**Authorization**
- Read tools never execute writes, on any connection, in any mode; validation is fail-closed (unparseable SQL is rejected).
- `write_`/`admin_` tools are rejected before touching the database on `read_only`/`monitor`.
- Unbounded mutations (`UPDATE`/`DELETE` without `WHERE`; Mongo `*Many` with empty filter) require `dry_run` or `expected_max_rows` — this barrier runs last, after mode/`database_modes`/`write_ops`.

**Sensitive data**
- Errors never contain passwords or echoed data values (`redact_uri_passwords` — ReDoS-safe, `sanitize_error`).
- `db_perf_column_stats` masks MCVs/histograms — planner stats carry real values; Mongo answers `GuidanceError`.
- `db_read_export`: capped at `export_max_rows` source- and client-side, always audited with the destination path; no byte cap, no path sandbox — by design.

**Injection safety**
- Redis commands outside the read/write allowlists never run; `FLUSHDB`/`FLUSHALL`/`EVAL`/`EVALSHA`/`SCRIPT`/`FUNCTION`/`FCALL`/`KEYS`/`CONFIG`/`DEBUG`/`SHUTDOWN`/`MONITOR`/`MIGRATE`/`SWAPDB` are banned in every mode, with the reason in the error. Redis audit entries carry key names only.
- Never interpolate user input into SQL text: identifiers quoted, values always binds, metrics/methods/opclasses/cluster actions from internal lookup dicts (`SHOW GRANTS` identities pass the `_account_part` allowlist; pgvector SQL is adapter-assembled — sqlglot cannot parse `<#>`/`<+>`).
- MySQL executable comments (`/*!`) are rejected in `guard.parse_sql` on every engine — MySQL runs their contents, sqlglot parses them as inert.
- User search input is never a pattern language: LIKE wildcards escaped, Mongo search is a substring test (never `$regex`), Redis SCAN globs escaped, SQLite FTS5 queries quoted into literal phrases.
- Mongo reads are swept for `$where`/`$function`/`$accumulator` and `$out`/`$merge` on the whole query, `find` filters included; `$expr`/`$regex` stay allowed.

**Execution bounds**
- SQLite reads open the file with `mode=ro` — structurally unable to write; Redis `dry_run`/`expected_max_rows` apply only to DEL/UNLINK (EXISTS probe) because nothing else can roll back.
- Every Mongo read sets `maxTimeMS`; non-readonly SQL sets a lock timeout (half budget, max 10s); a cancelled MySQL write closes its connection so the poisoned conn never returns to the pool.
- Reads retry once on a dead connection; writes never retry.
- `dry_run` DDL on MySQL → `GuidanceError` (implicit commit makes the rollback a lie); simple literal UPDATE/DELETE estimates use a `count(*)` probe; `expected_max_rows` is still enforced on the real rowcount.

**Agent UX**
- Missing feature (extension, profiler, privilege) → `GuidanceError` with the enabling command, never a generic error.
- `describe_object` raises a clear "not found" — never an empty result.
- Every connection identifies itself as `mcp-database/<conn>` (`application_name`/`program_name`/`appname`).
- Audit failure after an applied write raises explicitly — never silent, never pretends the write didn't happen.

## Adding or changing a tool

Prefix semantics + MCP annotations declared; add to `ALL_TOOL_NAMES` (`tool_names.py`), the e2e matrix (`VALID_ARGS` in `tests/e2e/test_tools_contract.py`) and `docs/tools.md`.

## Testing rules

- Every behavior needs **happy, sad and absurd** cases (empty/negative/huge/unicode/injection → clear error, never a crash); parametrize with ≥3 variations; tests get a 1-line docstring.
- Coverage gate 95% — keep it passing.
- Tiers: unit → e2e (real MCP protocol in memory, fakes in `tests/e2e/helpers.py`) → integration (testcontainers) → cluster (multi-node topologies in `tests/integration/cluster_topologies.py`, marker `cluster`, dedicated CI job outside the coverage gate). Integration files must be per-engine, `cross_engine`-marked or `cluster`-marked — `tests/unit/test_ci_partition_guard.py` enforces it.
- Every tool result flows through `ToolContext.run` → `formatter.to_jsonable`; never return raw driver objects.
- Evals (`docs/evals/`): 28 verified Q&A tied to the seeds — keep in sync with seed changes, verify manually before committing. `make evals` = one headless `claude -p` per question (logged-in CLI, never the Anthropic API directly); local only, never a CI gate.

## Dependencies (supply-chain)

- Majors capped; `[tool.uv] exclude-newer = "15 days"` cooldown; `uv.lock` hash-pinned, CI installs `--frozen`. Do not add `[tool.uv] required-version` (the Docker builder ships an older uv).
- Actions pinned by commit SHA; Dockerfile bases digest-pinned, non-root image; `.dockerignore` default-deny.
- CI flow: see `docs/development.md`. No PyPI. Two workflows: `test.yml` (lint/security/tests/compat/cluster on every push/PR — read-only, no write access anywhere) and `release.yml` (the only workflow with write access). **Publishing fires only on the push that bumps the version** — i.e. merging the release PR — detected by `release.yml`'s `check` job (`is_release` = the `pyproject.toml` version changed in this push and has no tag yet); it then publishes `docker` (image to GHCR) + `binaries` (linux/windows) + `release` (creates the `vX.Y.Z` tag + draft release with SBOM, binaries and a commit-log changelog). It does not re-run the gates — they already ran on the release PR and on this push via `test.yml`. An ordinary push never publishes.
- New workflows: top-level `permissions: contents: read`, elevate per-job; never `pull_request_target`/`workflow_run` with untrusted checkout; `persist-credentials: false` on checkouts; `.github/**` requires owner review. `codeql.yml` is visibility-gated — add its schedule only when the repo goes public.

## Docs to keep in sync

Any change to development workflow, architecture, security, configuration, tools, Docker or scripts must update the matching doc in the same change:

| Change touches | Update |
|----------------|--------|
| Tool behavior, parameters, per-engine support | `docs/tools.md` |
| Architecture: modules, request flow, failure modes, security mechanisms | `docs/architecture.md` |
| Env vars / connection config | `docs/configuration.md` + `docs/connections.md` + `docs/examples/` |
| Dev commands, playground, CI pipeline, evals flow | `docs/development.md` |
| Docker image usage | `docs/docker.md` |
| Seeds or eval answers | `docs/evals/README.md` + `docs/evals/evaluation-*.json` |
| Scripts added/removed | `scripts/README.md` |
| Contributor-facing gates and flow | `CONTRIBUTING.md` |
| Feature surface, quick start | `README.md` |

## Workflow

- Never run `git commit` or `git push` — the owner commits.
- All repo artifacts (code, comments, docs, examples) in English.
- Senior Python style: idiomatic, direct, minimal comments (only non-obvious constraints).
