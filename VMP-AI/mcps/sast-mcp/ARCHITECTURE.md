# Architecture

A high-level map of how SAST MCP Server is put together. For day-to-day rules
and conventions see `CLAUDE.md`.

## Big picture

```
AI agent ──MCP──> server.py (@mcp.tool functions)
                     │   ├─ auth (scope gate + audit log)
                     │   ├─ config (validated settings)
                     │   └─ output_format: markdown | json
                     ▼
            aggregator.run_all_scanners  ──>  scanners/*  (subprocess CLIs)
                     │                              │
                     ▼                              ▼
            dedup + metadata merge          Finding model (typed)
                     │
        ┌────────────┼───────────────┬───────────────┬───────────────┐
        ▼            ▼               ▼               ▼               ▼
     cache.py     sarif.py       reporting/      integrations/    enrichment/
   (baselines)  (SARIF+taxa)  (SBOM, HTML)   (DefectDojo, GitHub, (AST ctx, ignore,
                                              GitLab, Slack, Teams, patch, metadata)
                                              Jira)
```

## Layers

### Entry point — `server.py`
Builds the `FastMCP` instance and registers every `@mcp.tool()`. Each tool is
wrapped with `@audited(<scope>)`, which authenticates the caller (via `auth.py`),
enforces the required scope, and writes a structured JSON audit record to stderr.
Tool functions stay directly callable, so tests `await` them as plain functions.
`register_resources` / `register_prompts` wire up MCP Resources and Prompts.

### Configuration — `config.py`
A single validated `Settings` object loaded once from the environment (timeouts,
cache TTL/caps, HTTP retry/timeout, log level). Secrets are exposed as live
properties so rotation needs no restart. Other modules import `get_settings()`
rather than reading `os.environ` directly.

### Authentication — `auth.py`
Three modes: none (stdio local trust), static API key, or HMAC-SHA256 JWT with
`scopes`/`exp` claims. `authorize(provider, token, scope)` is the pure,
testable gate used by the server's `@audited` wrapper.

### Scanner plugins — `scanners/`
Each scanner subclasses `BaseScanner` with a `name`, optional `version_command`
(surfaced by `list_scanners` via `get_version()`), `check_dependency()`, and
`scan()`. `factory.py` is the single registration point. Parsers populate
enterprise metadata (CWE/CVSS/OWASP/references/remediation) where available.

### Aggregation — `aggregator.py`
Runs available scanners concurrently with per-scanner error isolation, then
deduplicates by `finding_hash` (keeping higher severity / richer data flow) and
**merges metadata** from collapsed duplicates so cross-scanner enrichment is
preserved. Sorted CRITICAL-first.

### Finding pipeline — `models.py` + `enrichment/`
`Finding` is the typed unit. `enrichment/` provides AST context, git-diff
filtering, ignore-list management, metadata normalization, and AI patch
prompt/apply helpers.

### Outputs
- `sarif.py` — SARIF 2.1.0 export (with a CWE taxonomy + `taxa`, and
  cvss/references/remediation in properties) and parsing. `parse_sarif` powers
  both CodeQL ingest and the generic `import_sarif` tool (any external SARIF
  joins the dedup/baseline/dashboard pipeline).
- `reporting/` — CycloneDX SBOM/VDR (`sbom.py`, with an optional Syft-backed full
  component inventory), SPDX 2.3 (`spdx.py`), CycloneDX VEX statements (`vex.py`,
  emitted by `triage_finding`), a standalone HTML report (`html.py`), an optional
  PDF report (`pdf.py`, the `[pdf]` extra), and compliance mapping
  (`compliance.py`, OWASP/SANS/PCI/CIS — the shared category source for `prompts.py`).
- `cache.py` — JSON scan cache with named baselines, atomic writes, TTL expiry,
  a size cap, and target fingerprints (incremental `use_cache` scans); powers
  `compare_baseline` and `evaluate_policy`.

### Closed-loop remediation
`remediate_and_verify` ties the pieces together: recover a finding by hash, dry-run
the patch via `enrichment/patch_apply.apply_unified_diff`, scan the file before/after,
and confirm the finding's hash is gone with no equal/higher-severity regression —
reverting the patch (`reverse=True` → `git apply -R`) on failure.

### Observability & reliability
- `metrics.py` — a dependency-free in-process metrics registry rendered in the
  Prometheus text format. Instrumented in one place: the `@audited` wrapper records
  every tool call/duration, and `aggregator` records scan counts/durations/errors.
- `ratelimit.py` — a per-client token-bucket limiter enforced in `@audited` for HTTP
  transports (disabled for stdio and when the budget is 0).
- HTTP ops endpoints registered via `@mcp.custom_route`: `/health` (liveness),
  `/ready` (scanner availability), `/metrics` (exposition).
- The aggregator bounds concurrent subprocess scanners with a semaphore
  (`SAST_MCP_MAX_CONCURRENT_SCANS`) and honors per-scanner timeout overrides.

### Integrations — `integrations/`
All outbound HTTP goes through `_http.py` (`post_with_retry`: retries, backoff,
timeouts). DefectDojo + GitHub (SARIF upload, PR comments), GitLab (MR notes),
Slack/Teams (webhooks), Jira (issue creation). Credentials are environment-only.

### CI gate
`evaluate_policy` runs `scan_all`, applies severity thresholds and an optional
"no new vs. baseline" rule, and returns an explicit PASS/FAIL verdict — the
integration point for blocking a pipeline.

## Deliberately out of scope

**Scheduled scans / webhook event streams.** An MCP server is request/response and
typically short-lived per client session; embedding a long-running scheduler or
event bus would fight that model. The supported pattern is to drive recurring scans
from CI/cron, calling `evaluate_policy` and the `notify_*` / `comment_on_pr` tools.
Also deferred: full RBAC/roles, multi-tenant cache isolation, reachability analysis,
scanner binary vendoring/checksums, and streaming output for very large scans.
```
