# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.8.3] - 2026-06-23
### Fixed
- **`Dockerfile.full` failed to build** — `TRIVY_VERSION` was pinned to `0.55.0`,
  a release tag that doesn't exist for aquasecurity/trivy, so the install
  script 404'd and the full (9-scanner) image build failed in CI on every
  v0.8.2 run. Bumped to `0.71.2`.

## [0.8.2] - 2026-06-21
### Added
- **Published container images** — GHCR workflow builds and pushes both the
  minimal and full (9-scanner) images on every release (`ghcr.io/skyrxin/
  sast-mcp-server:full` / `:minimal`), and builds them on every PR so the
  Dockerfiles can't silently rot. Added a `docker-compose.yml` for one-command
  HTTP deployment.
- **`[scanners]` pip extra** — `pip install "sast-mcp-server[scanners]"` installs
  the pip-based scanners (bandit, njsscan, semgrep, checkov) in one step.
- **Startup scanner-availability log** — the server logs `Scanners available:
  N/11 (...)` at boot (stderr) so it's immediately clear what's usable.
- **Reliability evidence** — Codecov coverage badge/upload in CI; a self-scan CI
  job that publishes the SARIF + summary as artifacts (snapshot in
  `examples/self-scan/`); and `scripts/loadtest.py` with a CI smoke job that
  load-tests the HTTP transport and ops endpoints. New `tests/test_ops.py`
  covers the `/health` `/ready` `/metrics` routes and the concurrency cap.
- **End-to-end engagement evidence** — a full SAST engagement against OWASP crAPI
  driven entirely through the server (full-repo scan benchmarks, closed-loop
  remediation FAIL/PASS verdicts, and a CI policy gate). Published separately as
  a write-up rather than committed to the repo.
### Changed
- **README install story** now leads with the batteries-included container and
  a scanner-availability matrix.
### Fixed
- **`/ready` performance** — the readiness probe cached its scanner inventory
  (15s TTL) instead of spawning a subprocess per scanner on every request,
  which under load tanked latency (p95 ~9s → ~290ms in the load test).
- **`compare_baseline` now accepts `scanner_name="scan_all"`** — it previously
  rejected the aggregated form that `save_baseline` and
  `evaluate_policy(fail_on_new=True)` already accept, making a `scan_all`
  baseline impossible to diff. Covered by new regression tests.
- **Bandit JSON parsing on Linux** — added `-q` so bandit's progress/metric
  lines (emitted to stdout on some platforms) no longer corrupt the JSON output
  we parse.

## [0.8.1] - 2026-06-17
### Fixed
- Corrected the `mcp-name` ownership marker and `server.json` namespace to the
  exact GitHub username case (`io.github.Skyrxin/...`) so publishing to the
  official MCP Registry passes PyPI ownership validation.

## [0.8.0] - 2026-06-15
### Added
- **Closed-loop remediation** — `remediate_and_verify` applies an agent-generated
  patch, re-scans the affected file, and confirms the finding's hash is gone (and
  that no equal/higher-severity regression appeared), rolling the patch back on
  failure. Turns "suggest a fix" into "prove the fix worked."
- **SARIF ingestion** — `import_sarif` pulls any external SARIF (Snyk, Veracode,
  CodeQL, CI jobs) into the normalized finding pipeline (dedup, baseline,
  dashboards), making the server a vendor-neutral aggregation hub.
- **Triage & VEX** — `triage_finding` returns an exploitability/false-positive
  assessment prompt or records a CycloneDX VEX statement; suppressing dispositions
  add the finding to the ignore-list with justification.
- **Container image scanning** — `scan_image` scans an image reference with Trivy
  or the new **Grype** scanner (Anchore). Grype also scans directories/SBOMs.
- **Real SBOM + SPDX** — `export_sbom` gains `format="cyclonedx"|"spdx"` (SPDX 2.3);
  when Syft is installed the CycloneDX component inventory is the full dependency
  list, not just vulnerable packages.
- **Enterprise reporting** — `generate_report` gains `format="pdf"` (optional
  `[pdf]` extra, reportlab); new `compliance_report` maps findings to OWASP Top 10,
  SANS CWE Top 25, PCI DSS, or CIS.
- **Production endpoints** — HTTP transports expose `/health`, `/ready`
  (scanner availability), and `/metrics` (Prometheus text).
- **Rate limiting & concurrency** — optional per-client token-bucket rate limiting
  (`SAST_MCP_RATE_LIMIT_PER_MIN`) and a global subprocess-scanner concurrency cap
  (`SAST_MCP_MAX_CONCURRENT_SCANS`), plus per-scanner timeout overrides
  (`SAST_MCP_SCANNER_TIMEOUTS`).
- **Incremental scans** — `scan_vulnerabilities`/`scan_all` accept `use_cache=True`
  to reuse the last scan when the target's files are unchanged (file-fingerprint).

### Changed
- In-process metrics are recorded for every tool call and scan via the existing
  `@audited` wrapper and the aggregator.
- Compliance framework category lists are now shared between `prompts.py` and the
  new `reporting/compliance.py` (single source of truth).

## [0.7.0] - 2026-06-14
### Added
- **Enforced authentication & audit logging**: every MCP tool is now scope-gated
  (`scan:read` / `scan:write` / `config:write` / `admin`) via a new `@audited`
  wrapper and `auth.authorize()`; each call emits a structured JSON audit record
  to stderr. Tokens are validated (incl. expiry) for HTTP transports; stdio keeps
  the local trust model.
- **Machine-readable output**: `scan_vulnerabilities`, `scan_all`, and
  `scan_git_history` accept `output_format="json"` for agents/CI.
- **`evaluate_policy` tool**: runs all scanners and returns an explicit PASS/FAIL
  CI verdict from severity thresholds and an optional "no new vs. baseline" rule.
  `save_baseline` now accepts `scanner_name="scan_all"` for aggregate baselines.
- **Enterprise finding metadata**: `Finding` now carries `cwe`, `cvss_score`,
  `cvss_vector`, `owasp_category`, `references`, and `remediation`, populated from
  Semgrep, Trivy, OSV-Scanner, Checkov, and Bandit. SARIF export emits a CWE
  taxonomy + `taxa` and `security-severity`; dedup merges metadata across scanners.
- **Reporting**: `export_sbom` (CycloneDX 1.5 SBOM/VDR) and `generate_report`
  (standalone HTML executive report) tools and a new `reporting/` package.
- **New integrations**: GitLab MR comments, Slack & Microsoft Teams webhooks,
  and Jira issue creation, plus GitHub PR comments. New tools `comment_on_pr`,
  `notify_slack`, `notify_teams`, `create_jira_issue`. All credentials are
  environment-only.
- **Central config** (`config.py`): one validated `Settings` object replaces
  scattered `os.getenv` reads; new `SAST_MCP_HTTP_RETRIES`, `SAST_MCP_HTTP_TIMEOUT`,
  `SAST_MCP_CACHE_MAX_SCANS` knobs.
- **Scanner version detection** surfaced in `list_scanners` (`get_version()`).
- **Infra**: enforced `mypy` + coverage floor + self-scan ("dogfood") in CI,
  Dependabot, a CodeQL workflow, a multi-stage `Dockerfile.full` bundling all CLI
  scanners, and new `SECURITY.md` / `CONTRIBUTING.md` / `ARCHITECTURE.md`.

### Changed
- Outbound integrations now share `integrations/_http.py` with retry, exponential
  backoff, and a configurable timeout.
- The scan cache writes atomically and self-prunes (TTL expiry + size cap).

## [0.6.0] - 2026-06-12
### Added
- **DefectDojo integration**: New `upload_to_defectdojo` tool imports a SARIF
  export into a DefectDojo engagement (`/api/v2/import-scan/`). Configured via
  `DEFECTDOJO_URL` / `DEFECTDOJO_API_KEY` environment variables.
- **GitHub Code Scanning integration**: New `upload_to_github` tool pushes a
  gzipped+base64 SARIF report to `/repos/{owner}/{repo}/code-scanning/sarifs`.
  Configured via the `GITHUB_TOKEN` environment variable.
- **AI patch generation**: New `generate_fix_prompt` tool packages a cached
  finding's vulnerable code and context into an LLM-ready prompt that asks for
  a strict unified diff; the new `apply_patch` tool applies an agent-supplied
  diff to disk via `git apply` (rejecting paths that escape the target).
- **`integrations/` package** (`defectdojo.py`, `github.py`) and
  **`enrichment/patch_prompt.py`** / **`enrichment/patch_apply.py`** modules.
- `ScanCache.find_finding_by_hash()` to recover full finding details by hash.

### Changed
- Standardized a `name` class attribute on every scanner via `BaseScanner`,
  replacing the inconsistent `name` property on the newer scanners.
- Added `httpx` as an explicit runtime dependency.
- The `fix_vulnerability` MCP prompt now drives the
  `generate_fix_prompt` → `apply_patch` workflow.

### Fixed
- Resolved all `ruff` lint violations across the scanner modules so CI lint
  passes again; cleaned up dead CVSS-parsing code in the OSV scanner and gave
  it an honest `database_specific.severity` mapping.
- Aligned scanner `scan()` signatures with the base class
  (`modified_files: set[str] | None`), fixing Liskov/type violations.
- Eliminated `coroutine was never awaited` warnings in the scanner test suite.

## [0.5.0] - 2026-06-12
### Added
- **Gitleaks Integration**: Deep secret scanning across entire git histories to detect leaked API keys and tokens from past commits.
- **OSV-Scanner Integration**: Advanced Software Composition Analysis (SCA) mapped to the Google OSV database.
- **OWASP ZAP Integration (DAST)**: Dynamic Application Security Testing capability via Docker Compose orchestration (`run_active_scan` tool).

## [0.4.0] - 2026-06-11
### Added
- **Streamable HTTP Transport**: Added `--transport streamable-http` for production remote deployments (MCP 2026 standard).
- **JWT Authentication**: Replaced static API key with JWT scoped tokens (`SAST_MCP_JWT_SECRET`).
- **Baseline Caching**: Scans are automatically cached. New tools `save_baseline` and `compare_baseline` to track security trends and regressions over time.
- **MCP Resources**: Expose read-only security dashboards, cache metadata, configuration, and scanner status via `sast://` resource URIs.
- **MCP Prompts**: Added pre-built security workflows for agents: `security_review`, `fix_vulnerability`, `pr_security_check`, and `compliance_report`.

### Changed
- SSE transport is now deprecated in favor of Streamable HTTP.
- Dependency `pyjwt` added for authentication capabilities.

## [0.3.0] - 2026-06-09

### Added
- **Trivy scanner** — 5th scanner covering dependency CVEs (SCA), secret detection, and IaC misconfigurations (Terraform, Kubernetes, Docker, CloudFormation)
- **CodeQL scanner** — 6th scanner providing deep semantic SAST with data-flow and taint tracking (by GitHub); supports database caching for faster re-scans
- **Checkov scanner** — 7th scanner for Infrastructure-as-Code policy enforcement with 1000+ built-in checks
- **`scan_all` tool** — run ALL installed scanners in parallel with automatic content-based deduplication; shows which scanners were used vs. skipped
- **`export_sarif` tool** — export scan results in SARIF 2.1.0 format for CI/CD integration (GitHub Code Scanning, GitLab SAST, Azure DevOps)
- **SARIF module** (`sarif.py`) — bidirectional SARIF 2.1.0 conversion: Finding→SARIF for export, SARIF→Finding for CodeQL import
- **Multi-scanner aggregator** (`aggregator.py`) — concurrent scanner execution with `asyncio.gather()`, hash-based deduplication keeping highest severity, severity-sorted output
- **CodeQL language auto-detection** — counts file extensions in target directory to pick the dominant supported language
- **CodeQL database caching** — stores database in `.sast-mcp-codeql-db/` to avoid rebuilding on every scan
- **Trivy multi-type parsing** — unified parser for three different Trivy JSON output structures (Vulnerabilities, Secrets, Misconfigurations)
- **Checkov multi-block parsing** — handles both single-dict and list-of-dicts output formats from Checkov
- **IaC language detection** — detects Terraform, Kubernetes YAML, Dockerfile, CloudFormation, Bicep, and Helm files
- **SARIF data flow support** — serializes `DataFlowStep` traces into SARIF `codeFlows` / `threadFlows`
- **SARIF fingerprint preservation** — round-trips finding hashes through SARIF `fingerprints.primaryLocationHash`
- **Comprehensive test suite** — 25+ new tests covering all three new scanners, SARIF export/parse, aggregator deduplication, and new server tools

### Changed
- Scanner factory now registers 7 scanners (was 4)
- MCP server instructions updated to describe all 7 scanners and new tools
- Updated `pyproject.toml` keywords to include trivy, codeql, checkov, sarif
- Version bumped to 0.3.0

## [0.2.0] - 2026-06-07

### Added
- **Semgrep scanner** — 4th scanner supporting 30+ languages with community rule registry
- **SSE/HTTP transport** — remote deployments via `--transport sse --port 8080`
- **API key authentication** — `SAST_MCP_API_KEY` env var for secure remote access
- **`list_scanners` tool** — check available scanners and their installation status
- **`unignore_vulnerability` tool** — reverse a previous ignore action
- **`list_ignored_vulnerabilities` tool** — view all suppressed findings
- **Typed data models** — `Finding`, `SeverityLevel`, `ConfidenceLevel` enums
- **Tree-sitter JavaScript/TypeScript support** — AST-aware context for JS/TS files
- **Configurable scan timeout** — `SAST_MCP_TIMEOUT` env var (default 300s)
- **Structured logging** — logs to stderr only (prevents stdio transport corruption)
- **Gemini CLI extension** — `gemini-extension.json` + `GEMINI.md` context file
- **Cross-platform docs** — setup guides for Claude Desktop, OpenAI, Cursor
- **Smithery.ai manifest** — marketplace listing for discovery
- **Docker support** — Dockerfile with all scanners pre-installed
- **CI/CD pipeline** — GitHub Actions for lint, test, and PyPI publish
- **Comprehensive test suite** — 30+ tests covering all scanners, enrichment, and server logic
- **Atomic ignore file writes** — prevents corruption on crash
- **Timestamps in ignore entries** — audit trail for suppressed findings
- **Backward-compatible ignore format** — migrates old `hash → reason` format

### Fixed
- **Bearer confidence hardcoded to HIGH** — now parsed from actual output
- **njsscan severity hardcoded to HIGH** — now parsed from metadata
- **njsscan only processed first file** — now handles all files in multi-file findings
- **Scanner errors silently swallowed** — stderr now propagated in error messages
- **Hash instability** — finding hashes no longer depend on line numbers
- **tree-sitter deps declared but unused** — now actually used for JS/TS context
- **Invalid severity/confidence accepted** — now validated against enum values
- **Logging to stdout corrupted stdio transport** — fixed to log to stderr only

### Changed
- Restructured to proper Python package layout (`sast_mcp_server/`)
- Updated `pyproject.toml` with full PyPI metadata, entry points, and tool configs
- Scanner factory now supports dynamic registration and metadata queries
- Replaced raw `Dict` returns with typed `Finding` dataclass

## [0.1.0] - Initial Release

### Added
- Basic MCP server with Bandit, njsscan, and Bearer scanners
- AST context enrichment for Python files
- Git diff filtering
- Finding ignore list
- Severity and confidence filtering
- Pagination support
