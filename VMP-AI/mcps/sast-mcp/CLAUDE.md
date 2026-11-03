# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SAST MCP Server — a [FastMCP](https://github.com/jlowin/fastmcp)-based MCP server that exposes
11 static/dynamic security scanners (Bandit, njsscan, Bearer, Semgrep, Trivy, CodeQL, Checkov,
Gitleaks, OSV-Scanner, Grype, OWASP ZAP) as tools for AI agents (Gemini CLI, Claude Desktop,
Cursor, OpenAI Agents, etc.). Findings are normalized into a typed `Finding` model, enriched with
AST-aware code context, deduplicated across scanners, and can be exported as SARIF 2.1.0 for
CI/CD.

## Development Commands

```bash
# Install with dev dependencies (editable)
pip install -e ".[dev]"

# Run the full test suite
pytest tests/ -v

# Run a single test file
pytest tests/test_scanners.py -v

# Run a single test
pytest tests/test_scanners.py::TestBanditScanner::test_parse_findings -v

# Lint (this is what CI runs)
ruff check sast_mcp_server/

# Type check (configured in pyproject.toml, not enforced in CI)
mypy sast_mcp_server/

# Run the server locally (stdio transport, for MCP client integration)
python -m sast_mcp_server
# or, once installed:
sast-mcp-server

# Run as a remote HTTP server (Streamable HTTP is the current standard; SSE is deprecated)
sast-mcp-server --transport streamable-http --host 0.0.0.0 --port 8080
```

CI (`.github/workflows/ci.yml`) runs `ruff check sast_mcp_server/` and
`pytest tests/ -v --tb=short` across Python 3.10–3.13, then publishes to PyPI on `v*` tags.

## Architecture

### Entry point and server registration

`sast_mcp_server/server.py` builds the `FastMCP` instance and registers all `@mcp.tool()`
functions (`scan_vulnerabilities`, `scan_all`, `scan_git_history`, `run_active_scan`,
`export_sarif`, `save_baseline`, `compare_baseline`, `list_scanners`, `ignore_vulnerability`,
`unignore_vulnerability`, `list_ignored_vulnerabilities`, plus the v0.6.0 tools
`upload_to_defectdojo`, `upload_to_github`, `generate_fix_prompt`, `apply_patch`).
`register_resources(mcp)` and `register_prompts(mcp)` wire up MCP Resources and Prompts from
`resources.py` / `prompts.py`. The decorated tool functions stay directly callable, so tests
import and `await` them as plain functions.

**Critical constraint:** all logging is configured to go to `stderr`
(`logging.basicConfig(..., stream=sys.stderr)`). Never write to stdout — it corrupts the stdio
MCP transport.

### Scanner plugin architecture

Each scanner lives in `sast_mcp_server/scanners/<name>.py` and subclasses `BaseScanner`
(`scanners/base.py`), implementing:
- `check_dependency()` — raises `RuntimeError` if the underlying CLI/binary isn't available.
- `scan(target_path, min_severity, min_confidence, modified_files, timeout)` — runs the tool
  (usually via `asyncio.create_subprocess_exec`, parsing JSON/SARIF stdout or a report file) and
  returns `list[Finding]`.

`scanners/factory.py` is the single source of truth for scanner registration:
- `_SCANNER_REGISTRY` maps scanner name → class (used by `ScannerFactory.get_scanner()` /
  `list_scanners()`).
- `SCANNER_INFO` provides display metadata (description, languages, install command) for the
  `list_scanners` tool and `sast://scanners` resource.

Every scanner sets a `name` class attribute (declared as `ClassVar[str]` on `BaseScanner`) equal
to its registry key; it is used both as `Finding.scanner` and by callers that persist results
(e.g. `cache.save_scan(scanner.name, ...)`). To add a new scanner: implement the `BaseScanner`
subclass (including `name`), register it in both `_SCANNER_REGISTRY` and `SCANNER_INFO` in
`factory.py`, and export it from `scanners/__init__.py`.

ZAP is the only DAST scanner — its `scan()` raises `NotImplementedError` and instead exposes
`run_dynamic_scan()`, invoked via the dedicated `run_active_scan` tool, which orchestrates
`docker compose up` → wait for the URL → run the `zap-baseline.py` container → `docker compose down`.

### Finding pipeline

1. Scanner produces raw `Finding` objects (`models.py`): `scanner`, `title`, `message`, `file`,
   `line_start/end`, `severity` (`SeverityLevel`), `confidence` (`ConfidenceLevel`), `context`,
   `language`, `finding_hash`, optional `data_flow: list[DataFlowStep]`.
2. `finding_hash` is computed by `BaseScanner.generate_hash(file_path, title, code_snippet)` —
   a SHA-256 of `file:title:normalized_snippet`, designed to stay stable across line-number
   shifts but change if the vulnerable code moves elsewhere. This hash is the key used for
   ignore-list entries, dedup, and baseline diffing.
3. `enrichment/ast_context.get_function_context()` expands a bare line number into the full
   enclosing function/class: native `ast` for Python, tree-sitter for JS/TS (if installed),
   falling back to ±10 lines for everything else.
4. `enrichment/ignore_manager.IgnoreManager` filters out findings whose hash is in
   `<target>/.sast-mcp-ignore.json` (atomic write via temp-file + `os.replace`).
5. `enrichment/git_diff.get_modified_files()` supports `git_diff_only=True` by intersecting
   findings with `git diff --name-only HEAD`.

### Multi-scanner aggregation (`aggregator.py`)

`run_all_scanners()` checks `check_dependency()` for every registered scanner, runs the
available ones concurrently with `asyncio.gather`, then `_deduplicate_findings()` collapses
findings sharing a `finding_hash` (keeping the higher-severity / data-flow-bearing copy), and
sorts the result by `SEVERITY_ORDER` (CRITICAL first). Returns
`(findings, used_scanners, skipped_scanners)`.

### Caching & baselines (`cache.py`)

`ScanCache` persists scan results as JSON under `<target_path>/.sast-mcp-cache/`:
- `save_scan(..., tag=...)` writes a timestamped file and, if `tag` is set, also overwrites
  `<scanner>_tag_<tag>.json` (used as a named baseline).
- `compare(baseline, current_findings)` returns a `ScanDiff` (new/fixed/unchanged findings +
  per-severity trend), driving the `compare_baseline` tool and `pr_security_check` prompt.
- `cleanup_expired()` removes non-tagged scans older than `SAST_MCP_CACHE_TTL` (default 24h).

### SARIF (`sarif.py`)

Bidirectional SARIF 2.1.0 conversion: `findings_to_sarif()` powers `export_sarif`;
`parse_sarif()` is used by the CodeQL scanner to ingest CodeQL's native SARIF output and
re-enrich it with AST context and stable hashes.

### Dashboard integrations (`integrations/`)

`integrations/defectdojo.py` and `integrations/github.py` push a SARIF export to external
platforms via `httpx.AsyncClient`. Credentials come **only** from environment variables
(`DEFECTDOJO_URL`/`DEFECTDOJO_API_KEY`, `GITHUB_TOKEN`) so secrets never land in tool arguments
or transcripts. Both raise the shared `IntegrationError` (from `integrations/__init__.py`) on
missing config, unreadable files, or non-2xx responses; the server tools catch it and return a
friendly message. GitHub's endpoint requires the SARIF be gzip-compressed then base64-encoded.

### AI patch generation (`enrichment/patch_prompt.py`, `enrichment/patch_apply.py`)

Division of responsibility: the **server packages context**, the **agent generates the diff**,
and `apply_patch` writes it. `build_patch_prompt()` recovers a finding by hash via
`ScanCache.find_finding_by_hash()`, reads a line-numbered window of the source, and renders a
prompt instructing an LLM to emit a strict unified diff. `apply_unified_diff()` shells out to
`git apply` (works without a repo; rejects paths escaping the target unless `--unsafe-paths`,
which we never pass) and supports `check_only` for a dry run.

### Auth (`auth.py`)

`AuthProvider` supports three modes selected by env vars: no auth (stdio/local — all scopes
granted), static `SAST_MCP_API_KEY` (legacy), or `SAST_MCP_JWT_SECRET` (HMAC-SHA256 JWT with
`scopes`/`exp` claims, scopes drawn from `SCOPE_SCAN_READ`/`SCOPE_SCAN_WRITE`/`SCOPE_CONFIG_WRITE`/
`SCOPE_ADMIN`). `create_jwt()` is a helper for minting test tokens.

### MCP Resources & Prompts

- `resources.py` exposes read-only `sast://` URIs (`sast://scanners`, `sast://config`,
  `sast://cache/{target_path}/latest`, `sast://cache/{target_path}/baseline/{tag}`,
  `sast://ignore/{target_path}`, `sast://dashboard/{target_path}`) backed by `ScanCache` /
  `IgnoreManager` / `ScannerFactory` — no scans are run.
- `prompts.py` defines reusable workflow templates (`security_review`, `fix_vulnerability`,
  `pr_security_check`, `compliance_report`) that return instruction strings guiding an agent
  through a sequence of tool calls.

## Testing conventions

- Tests live in `tests/`, fixtures (recorded scanner JSON/SARIF output) in `tests/fixtures/`.
- Subprocess-based scanners are tested by patching `asyncio.create_subprocess_exec` and
  `asyncio.wait_for` to return a mocked process whose `communicate()` resolves to fixture bytes
  (see the `_mock_subprocess` helper duplicated in `test_scanners.py` / `test_new_scanners.py`).
- `pytest-asyncio` is in `auto` mode (`pyproject.toml`), so `async def test_*` functions need no
  extra decorator beyond `@pytest.mark.asyncio` (already used throughout for consistency).
