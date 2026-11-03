# Tool Reference

39 tools across five risk classes. Every tool except `db_schema_connections` takes `conn`, the name of a configured connection.
The name prefix encodes risk: `db_schema_`/`db_read_`/`db_perf_` never write to the database; `db_write_`/`db_admin_` do.
Setup and configuration live in the [README](../README.md); ready-made configs are in [examples/](examples/).

Legend: ✅ fully supported · ⚠️ supported with caveats (see notes) · ❌ not applicable (clear guidance error)

MariaDB follows the **MySQL** column: same protocol and dialect, with the engine differences (`max_statement_time`, `SHOW SLAVE HOSTS`, `performance_schema` off by default) absorbed by the adapter.

> Naming rationale: MCP guidelines suggest a service prefix (`db_read_query`) to avoid collisions between
> servers. Here the prefix is deliberately the **risk class** instead: it powers the permission semantics
> (allow all `db_read_*`/`db_perf_*` once, gate `db_write_*`/`db_admin_*`), and clients already namespace tools by server
> (`mcp__db-postgres__db_read_query`). Responses are JSON-only by design: the consumers are agents, and the
> row/byte limits plus `truncated`/`note` metadata keep responses context-efficient.

## Contents

- [Access modes](#access-modes)
- [All 39 tools at a glance](#all-39-tools-at-a-glance)
- [db_schema_ (catalogs & metadata)](#db_schema_-catalogs-and-metadata-always-safe)
- [db_read_ (data reads)](#db_read_-data-reads-always-safe-fail-closed-validation)
- [db_perf_ (performance diagnosis)](#db_perf_-performance-diagnosis-always-safe)
- [db_write_ / db_admin_ (writes & operations)](#db_write_--db_admin_-writes-and-operations-case-by-case-approval)
- [Notes](#notes)

## Access modes

Set per connection via `MODE`. Which tool classes each mode allows:

| Class | `read_write` | `read_only` | `monitor` |
|-------|:---:|:---:|:---:|
| `db_schema_` | ✅ | ✅ | ✅ (no data sampling) |
| `db_read_` | ✅ | ✅ | ❌ |
| `db_perf_` | ✅ | ✅ | ✅ |
| `db_write_` | ✅ | ❌ | ❌ |
| `db_admin_` | ✅ | ❌ | ❌ |

Per-connection refinements: `write_ops` restricts which operations (insert/update/delete/ddl) `db_write_query` may run; `database_modes` overrides the mode per database on the same server (the most restrictive wins when the target database cannot be determined); `redact_fields` masks values in every data-returning tool (`["*"]` masks everything with type placeholders, preserving structure).

## All 39 tools at a glance

| Class | Tools (full name = prefix + suffix) |
|-------|-------------------------------------|
| `db_schema_` (10) | connections · databases · objects · describe · ddl · search · relationships · users · grants · search_indexes |
| `db_read_` (5) | query · sample · export · vector_search · text_search |
| `db_perf_` (18) | explain · top_queries · active_ops · blocking · index_stats · table_stats · column_stats · diagnose · health · replication · settings · logs · vector_stats · cluster · storage · tls · config_check · index_advisor |
| `db_write_` (2) | query · search_index |
| `db_admin_` (4) | kill · analyze · maintain · cluster |

The tables below give parameters, descriptions and per-engine support for each.

## db_schema_: catalogs and metadata (always safe)

| Tool | Parameters | Description | PostgreSQL | MySQL | SQLite | MongoDB | Redis |
|------|-----------|-------------|:---:|:---:|:---:|:---:|:---:|
| `db_schema_connections` | — | List configured connections: name, type, access mode, reachability | ✅ | ✅ | ✅ | ✅ | ✅ |
| `db_schema_databases` | `conn` | List databases / schemas | ✅ ¹ | ✅ | ✅ | ✅ | ✅ ²² |
| `db_schema_objects` | `conn`, `database`, `object_type?` | List tables, views, indexes / collections with sizes and row counts | ✅ | ✅ | ✅ | ✅ | ✅ ²² |
| `db_schema_describe` | `conn`, `database`, `object` | Columns, constraints, indexes / sampled fields, indexes, stats | ✅ | ✅ | ✅ | ✅ ² | ✅ ²² |
| `db_schema_ddl` | `conn`, `database`, `object` | Creation DDL: CREATE TABLE / SHOW CREATE TABLE / create+createIndexes commands | ✅ | ✅ | ✅ | ✅ ³ | ❌ |
| `db_schema_search` | `conn`, `pattern`, `scope?` | Find objects and columns by name pattern | ✅ | ✅ | ✅ | ⚠️ ⁴ | ⚠️ ²² |
| `db_schema_relationships` | `conn`, `database`, `object?` | Foreign-key graph | ✅ | ✅ | ✅ | ❌ ⁵ | ❌ |
| `db_schema_users` | `conn`, `user?` | Users/roles and attributes (never password hashes) | ✅ | ✅ | ❌ ²¹ | ✅ | ⚠️ ²² |
| `db_schema_grants` | `conn`, `user?`, `object?` | Effective permissions per user or object | ✅ | ✅ | ❌ ²¹ | ✅ | ⚠️ ²² |
| `db_schema_search_indexes` | `conn`, `database?`, `object?` | Vector and full-text indexes with definitions: pgvector hnsw/ivfflat + tsvector (PG), FULLTEXT (MySQL), Atlas search/vectorSearch with build status (MongoDB) | ✅ ¹⁷ | ✅ | ❌ | ⚠️ ¹⁸ | ❌ |

## db_read_: data reads (always safe, fail-closed validation)

SQL validation rejects anything that is not SELECT/UNION/VALUES, as well as multi-statement queries, unparseable SQL (fail-closed), dangerous functions (`pg_terminate_backend`, `pg_read_file`, `pg_sleep`, `sleep`, `benchmark`, `dblink`, `load_file`, ...), and MySQL executable comments (`/*! ... */`, whose contents MySQL runs but the parser treats as inert). MongoDB read filters and pipelines are additionally swept for write stages (`$out`/`$merge`) and server-side JavaScript operators (`$where`/`$function`/`$accumulator`); `$expr` and `$regex` stay allowed and time-bounded. Reads run inside read-only transactions where the database supports them, a second barrier below the parser.

| Tool | Parameters | Description | PostgreSQL | MySQL | SQLite | MongoDB | Redis |
|------|-----------|-------------|:---:|:---:|:---:|:---:|:---:|
| `db_read_query` | `conn`, `query`, `params?`, `row_limit?` | Read-only query. SQL: SELECT/UNION/VALUES only. MongoDB: find, aggregate (no `$out`/`$merge`), countDocuments, estimatedDocumentCount, distinct, listIndexes | ✅ | ✅ | ✅ | ✅ | ✅ ²³ |
| `db_read_sample` | `conn`, `database`, `object`, `n?` | Up to n sample rows (`LIMIT` / `$sample`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| `db_read_export` | `conn`, `query`, `path`, `format?` | Write a read result to a local json/csv file, bypassing the conversation row limit up to `EXPORT_MAX_ROWS` (default 100000; `truncated: true` when hit). Every export is audit-logged with the destination path | ✅ | ✅ | ✅ | ✅ | ✅ |
| `db_read_vector_search` | `conn`, `database`, `object`, `column`, `vector`, `metric?`, `row_limit?`, `filter?`, `index?`, `num_candidates?` | K-nearest-neighbor search with a pre-computed embedding. PG: pgvector operator per metric (cosine/l2/inner_product/l1), SQL assembled from allowlists with the vector as a bind. MongoDB: Atlas `$vectorSearch` (`index` required; metric comes from the index; `num_candidates` defaults to 10× the limit). The vector column is projected out of the results | ✅ ¹⁷ | ❌ | ❌ | ⚠️ ¹⁸ | ❌ |
| `db_read_text_search` | `conn`, `database`, `object`, `query`, `column?`, `index?`, `row_limit?`, `filter?`, `language?` | Relevance-ranked full-text search: `websearch_to_tsquery` + `ts_rank` (PG, `language` = regconfig, default `simple`), `MATCH ... AGAINST` (MySQL), Atlas `$search` (MongoDB; omitting `column` searches all indexed fields). The phrase is literal text, never a pattern | ✅ | ⚠️ ¹⁹ | ⚠️ ²⁴ | ⚠️ ¹⁸ | ❌ |

## db_perf_: performance diagnosis (always safe)

| Tool | Parameters | Description | PostgreSQL | MySQL | SQLite | MongoDB | Redis |
|------|-----------|-------------|:---:|:---:|:---:|:---:|:---:|
| `db_perf_explain` | `conn`, `query`, `analyze?` | Execution plan; `analyze=true` runs the (read-only) query for real timings | ✅ | ✅ | ⚠️ ²¹ | ✅ ⁶ | ❌ |
| `db_perf_top_queries` | `conn`, `sort_by?`, `limit?`, `database?` | Most expensive queries | ⚠️ ⁷ | ✅ | ❌ ²¹ | ⚠️ ⁸ | ✅ |
| `db_perf_active_ops` | `conn`, `min_duration_ms?` | What is running right now, with durations | ✅ | ✅ | ❌ ²¹ | ✅ ⁹ | ✅ |
| `db_perf_blocking` | `conn` | Lock waits: who blocks whom | ✅ | ⚠️ ¹⁰ | ❌ ²¹ | ✅ ⁹ | ✅ |
| `db_perf_index_stats` | `conn`, `database?` | Unused/redundant/invalid indexes and sizes | ✅ | ⚠️ ¹⁰ | ⚠️ ²¹ | ✅ | ❌ |
| `db_perf_table_stats` | `conn`, `database?` | Seq vs index scans, dead rows / fragmentation / collStats | ✅ | ✅ | ⚠️ ²¹ | ✅ | ✅ |
| `db_perf_column_stats` | `conn`, `database`, `object`, `column?` | Planner column statistics: null fraction, distinct count, correlation, MCVs (masked per `redact_fields`) | ✅ | ✅ | ❌ | ⚠️ ¹⁵ | ❌ |
| `db_perf_diagnose` | `conn` | One-shot triage: health + active ops + lock waits + top queries, with findings and suggested next tools | ✅ | ✅ | ✅ | ✅ | ✅ |
| `db_perf_health` | `conn` | Connections vs max, cache/buffer hit ratio, largest objects | ✅ | ✅ | ✅ | ✅ | ✅ |
| `db_perf_replication` | `conn` | Replication lag / replica set members / shards; standalone returns a note | ✅ | ✅ | ❌ ²¹ | ✅ | ✅ |
| `db_perf_settings` | `conn`, `pattern?` | Non-default and key tuning parameters | ✅ | ✅ | ✅ | ⚠️ ¹¹ | ✅ |
| `db_perf_logs` | `conn`, `limit?`, `level?` | Recent server log entries | ⚠️ ¹² | ⚠️ ¹³ | ❌ ²¹ | ✅ | ❌ |
| `db_perf_vector_stats` | `conn`, `database?`, `object?` | Vector search quality triage: vector columns/indexes with build params, `hnsw.ef_search`/`ivfflat.probes`, in-flight builds (PG) or Atlas index build status (MongoDB), with findings (unindexed columns, mis-sized `lists`, non-queryable indexes) and next tools | ✅ ¹⁷ | ❌ | ❌ | ⚠️ ¹⁸ | ❌ |
| `db_perf_cluster` | `conn` | Cluster triage: topology + per-member lag + health in one call, with findings (lagging/broken replicas, missing primary, stopped threads, saturation) and next tools; standalone servers report that | ✅ | ✅ | ✅ | ✅ | ✅ |
| `db_perf_storage` | `conn`, `database?` | Storage triage: sizes, WAL/binlog/oplog window, temp/dead-tuple pressure and filesystem usage where the engine exposes it, with findings (near-full disk/memory, short oplog, bloat) and next tools | ✅ | ✅ | ✅ ²⁵ | ✅ ²⁶ | ✅ |
| `db_perf_tls` | `conn` | TLS/certificate triage from a credential-free handshake: whether the server offers TLS, the negotiated protocol/cipher, and the certificate issuer and days-to-expiry, with findings on soon-to-expire certs and unexpected plaintext | ✅ ²⁷ | ❌ ²⁸ | ❌ ²⁸ | ✅ ²⁷ | ✅ ²⁷ |
| `db_perf_config_check` | `conn` | Configuration-vs-workload triage: cache/buffer sizing, connection headroom, eviction/persistence policy, autovacuum/checkpoint pressure, summarized into heuristic findings that each name their signal | ✅ | ✅ | ✅ | ✅ | ✅ |
| `db_perf_index_advisor` | `conn`, `database?` | Missing-index triage: unindexed foreign keys with a suggested CREATE INDEX (PostgreSQL), full-table-scan statements (MySQL) or collection scans (MongoDB), with next tools | ✅ | ⚠️ ¹⁰ | ❌ | ⚠️ ⁸ | ❌ |

## db_write_ / db_admin_: writes and operations (case-by-case approval)

| Tool | Parameters | Description | PostgreSQL | MySQL | SQLite | MongoDB | Redis |
|------|-----------|-------------|:---:|:---:|:---:|:---:|:---:|
| `db_write_query` | `conn`, `query`, `params?`, `dry_run?`, `expected_max_rows?` | DML/DDL (SQL) or insert/update/delete/index/collection operations (MongoDB). `dry_run` rolls back and reports impact (rejected for MySQL DDL, which commits implicitly); `expected_max_rows` auto-aborts oversized writes. An unbounded `UPDATE`/`DELETE` (no `WHERE`, or Mongo empty filter) is rejected unless `dry_run` or `expected_max_rows` is set. Requires `read_write` | ✅ | ✅ | ✅ | ✅ ¹⁴ | ✅ ²³ |
| `db_write_search_index` | `conn`, `database`, `object`, `action`, `name`, `definition?` | Create/update/drop a vector or full-text index. PG: `{"column", "method": "hnsw"\|"ivfflat", "metric", "options": {"m"\|"ef_construction"\|"lists"}}` (update → drop+recreate guidance). MySQL: `{"columns": [...]}` FULLTEXT. MongoDB Atlas: `{"fields": [...]}` (vectorSearch) or `{"mappings": {...}}` (search); builds are asynchronous — poll `db_schema_search_indexes` until `queryable`. Gated as DDL (`write_ops`) and audit-logged | ✅ ¹⁷ | ✅ | ⚠️ ¹⁸ |
| `db_admin_kill` | `conn`, `target_id`, `force?` | Cancel (default) or terminate a running operation | ✅ | ✅ | ❌ ²¹ | ✅ | ✅ |
| `db_admin_analyze` | `conn`, `database`, `object?` | Refresh planner statistics (ANALYZE / ANALYZE TABLE) | ✅ | ✅ | ✅ | ❌ ¹⁵ | ❌ |
| `db_admin_maintain` | `conn`, `database`, `object`, `action?` | Reclaim space: VACUUM / OPTIMIZE TABLE / compact | ✅ | ✅ | ✅ | ⚠️ ¹⁶ | ❌ |
| `db_admin_cluster` | `conn`, `action`, `seconds?` | One cluster/replication action from a fixed allowlist: `promote`/`pause_replay`/`resume_replay` (PG replica), `start_replica`/`stop_replica` (MySQL), `step_down`/`freeze` (MongoDB replica set; `step_down` treats the dropped connection as success), `promote` (Redis replica). Actions outside the engine's set return guidance; audit-logged | ✅ ²⁰ | ✅ ²⁰ | ❌ | ✅ ²⁰ | ✅ ²⁰ |

## Notes

1. PostgreSQL lists **schemas** of the connected database (cross-database queries are not possible in PG).
2. MongoDB fields are inferred by sampling 50 documents; sampling is skipped in `monitor` mode (indexes and stats only).
3. MongoDB returns equivalent `create` + `createIndexes` commands as JSON.
4. MongoDB matches collection names only; field names are not searched (use `db_schema_describe`).
5. MongoDB has no foreign keys; returns an empty list with an explanatory note.
6. MongoDB explain supports `find`, `aggregate` and `countDocuments`.
7. Requires the `pg_stat_statements` extension; the error explains how to enable it.
8. Requires the profiler (`db.setProfilingLevel(1)`); the error explains how to enable it.
9. Requires the `inprog` privilege (e.g. `clusterMonitor` role) on MongoDB.
10. Requires the `sys` schema (MySQL 5.7+) and the PROCESS privilege.
11. Requires `clusterMonitor`; returns scalar parameters from `getParameter: "*"`.
12. Requires `logging_collector=on` and the `pg_read_server_files` role (or superuser).
13. Requires MySQL 8.0.22+ (`performance_schema.error_log`).
14. Mongo write operations: insertOne/Many, updateOne/Many, replaceOne, deleteOne/Many, createIndex, dropIndex, createCollection, dropCollection, renameCollection. For update/delete, `dry_run` counts the matching documents without modifying them.
15. MongoDB has no planner-statistics equivalent; returns a guidance error.
16. `compact` requires the compact privilege on the collection.
17. Requires the pgvector extension (`CREATE EXTENSION vector;`); the error names the command. The playground image for it is `pgvector/pgvector:pg17`.
18. Requires MongoDB Atlas or a local deployment with mongot — `make atlas-local` starts the `mongodb/mongodb-atlas-local` playground (port 27018), `make atlas-seed` loads demo vectors; plain mongod returns guidance.
19. Requires a FULLTEXT index on the column; the error points to `db_write_search_index`.
20. Only the listed per-engine actions exist; anything else returns guidance naming them. All actions run fixed statements/commands — no user input is ever interpolated. PostgreSQL replicas support `promote`, `pause_replay` and `resume_replay` (`pg_promote`/`pg_wal_replay_pause`/`pg_wal_replay_resume`); Redis supports `promote` (`REPLICAOF NO ONE`).
21. SQLite is an in-process, single-file engine: there are no accounts, sessions, server logs or replication to inspect (guidance explains each); `explain` is `EXPLAIN QUERY PLAN` (no analyze), and index/table stats come from `sqlite_stat1` after `db_admin_analyze`. Reads open the file with `mode=ro` — a read cannot write even in principle.
22. Redis key listing/search/describe are `SCAN`-based (capped at the row limit; search patterns are literal — glob metacharacters are escaped) plus per-key `TYPE`/`TTL`/`OBJECT ENCODING`/`MEMORY USAGE`; users/grants read ACLs when available (password hashes stripped).
23. Redis queries are envelopes `{"command": "HGETALL", "args": [...]}` validated against read/write allowlists. `FLUSHDB`, `FLUSHALL`, `EVAL`/`EVALSHA`, `SCRIPT`, `FUNCTION`, `FCALL`, `KEYS`, `CONFIG` (set), `DEBUG`, `SHUTDOWN`, `MONITOR`, `MIGRATE` and `SWAPDB` are **never allowed, in any mode**. `dry_run`/`expected_max_rows` apply only to `DEL`/`UNLINK` (estimated via `EXISTS`); other commands cannot be rolled back and say so.
24. SQLite text search requires an FTS5 virtual table (the error shows how to create one); the query is quoted into a literal phrase, so FTS5 operators in the input are not interpreted.
25. SQLite storage reports the file size, page count and freelist ratio (a VACUUM candidate).
26. Filesystem usage (fsUsedSize/fsTotalSize) and the oplog window come from dbStats and local.oplog.rs where exposed; a standalone mongod has no oplog.
27. The probe reads what the server presents without credentials or verification (self-signed chains included). PostgreSQL uses its SSLRequest preamble; MongoDB/Redis (and rediss) use a direct TLS handshake.
28. MySQL/MariaDB negotiate TLS after the auth handshake, so a credential-free probe cannot inspect it; the tool points to `openssl s_client -starttls`. SQLite is a local file with no endpoint.

