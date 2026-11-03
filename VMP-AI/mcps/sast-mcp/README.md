<!-- mcp-name: io.github.Skyrxin/sast-mcp-server -->

# SAST MCP Server

[![PyPI version](https://img.shields.io/pypi/v/sast-mcp-server)](https://pypi.org/project/sast-mcp-server/)
[![sast-mcp-server MCP server](https://glama.ai/mcp/servers/Skyrxin/sast-mcp-server/badges/score.svg)](https://glama.ai/mcp/servers/Skyrxin/sast-mcp-server)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/Skyrxin/sast-mcp-server/actions/workflows/ci.yml/badge.svg)](https://github.com/Skyrxin/sast-mcp-server/actions)
[![codecov](https://codecov.io/gh/Skyrxin/sast-mcp-server/branch/main/graph/badge.svg)](https://codecov.io/gh/Skyrxin/sast-mcp-server)

**Static Application Security Testing (SAST) for AI agents.** A production-ready [MCP](https://modelcontextprotocol.io/) server that gives any AI agent the ability to scan code for security vulnerabilities.

Supports **11 industry-standard scanners**:

| Scanner | Languages / Scope | Type |
|---------|-------------------|------|
| **[Bandit](https://bandit.readthedocs.io/)** | Python | Security linter |
| **[njsscan](https://github.com/ajinabraham/njsscan)** | JavaScript, Node.js | Static analysis |
| **[Bearer](https://www.bearer.com/)** | Python, JS, Ruby, Java, Go, PHP | Data-flow SAST |
| **[Semgrep](https://semgrep.dev/)** | 30+ languages | Rule-based SAST |
| **[Trivy](https://trivy.dev/)** | All (CVEs, Secrets, IaC, images) | Multi-scanner |
| **[CodeQL](https://codeql.github.com/)** | Python, JS, Java, Go, C/C++, C#, Ruby, Swift | Semantic SAST |
| **[Checkov](https://www.checkov.io/)** | Terraform, K8s, Docker, CloudFormation | IaC policy scanner |
| **[Gitleaks](https://gitleaks.io/)** | All (.git history) | Deep secret scanning |
| **[OSV-Scanner](https://google.github.io/osv-scanner/)**| Multiple (lockfiles, sboms) | SCA |
| **[Grype](https://github.com/anchore/grype)** | Containers, OS packages, lockfiles, SBOMs | SCA / image scanning |
| **[OWASP ZAP](https://www.zaproxy.org/)** | RUNTIME | Dynamic (DAST) via Docker |

Works with **any MCP-compatible agent**: Gemini CLI, Claude Desktop, OpenAI Agents, Cursor, Windsurf, and more.

---

## Features

- 🔍 **11 SAST/SCA/DAST scanners** with a unified output format
- 🌳 **AST-aware context** — shows the full enclosing function, not just a line number
- 📊 **Severity & confidence filtering** — focus on what matters
- 🔀 **Git diff mode** — scan only modified files for incremental reviews
- 🙈 **Ignore management** — suppress false positives with audit trail
- 📄 **Pagination** — handle large codebases without overwhelming the agent
- 🌐 **Dual transport** — stdio (local) or Streamable HTTP (remote deployments)
- 🔐 **JWT & API key authentication** — secure remote deployments
- 📦 **One command install** — `pip install sast-mcp-server`
- 🚀 **Multi-scanner mode** — run all installed scanners in parallel with deduplication
- 📋 **SARIF export** — CI/CD integration with GitHub, GitLab, Azure DevOps
- 🏗️ **IaC scanning** — Terraform, Kubernetes, Docker security policies
- 🔑 **Secret detection** — find hardcoded API keys, tokens, and passwords in code and git history
- 📦 **SCA / dependency CVEs** — scan lock files for known vulnerabilities against the OSV database
- 🕷️ **DAST** — dynamic baseline scans of running apps via OWASP ZAP + Docker
- 📈 **Baselines & trend tracking** — cache scans and diff against a saved baseline
- 🤖 **MCP Prompts & Resources** — pre-built security workflows and live dashboards for agents
- 📤 **Dashboard integrations** — push SARIF results to DefectDojo or GitHub Code Scanning
- 🩹 **AI-assisted remediation** — generate fix prompts and apply agent-written patches via `git apply`

---

## Quick Start

The server is only as useful as the scanners installed alongside it. Pick the
install path that matches how much of the toolset you want out of the box.

### Option 1 — Full container (recommended: 9 scanners, zero setup)

```bash
docker pull ghcr.io/skyrxin/sast-mcp-server:full
```

Bundles **bandit, njsscan, bearer, semgrep, trivy, checkov, gitleaks,
osv-scanner, and grype** so `scan_all` works immediately. Or bring up an HTTP
server with one command:

```bash
docker compose up          # serves http://localhost:8080/mcp + /health /ready /metrics
```

### Option 2 — pip extra (4 pip-installable scanners)

```bash
pip install "sast-mcp-server[scanners]"   # adds bandit, njsscan, semgrep, checkov
```

### Option 3 — minimal / custom

```bash
pip install sast-mcp-server               # server only — bring your own scanners
uvx sast-mcp-server                        # run without installing
```

Then install whichever scanners you need (binary scanners aren't pip packages):

```bash
pip install bandit njsscan semgrep checkov     # pip-installable
# trivy:        https://aquasecurity.github.io/trivy/latest/getting-started/installation/
# grype:        https://github.com/anchore/grype#installation
# gitleaks:     https://github.com/gitleaks/gitleaks#installing
# osv-scanner:  https://google.github.io/osv-scanner/installation/
# bearer:       https://docs.bearer.com/installation/
# codeql:       https://github.com/github/codeql-cli-binaries/releases
```

### What ships where

| Scanner | `:full` image | `[scanners]` extra | Notes |
|---------|:---:|:---:|-------|
| Bandit | ✅ | ✅ | pip |
| njsscan | ✅ | ✅ | pip |
| Semgrep | ✅ | ✅ | pip |
| Checkov | ✅ | ✅ | pip |
| Bearer | ✅ | — | install script |
| Trivy | ✅ | — | binary |
| Gitleaks | ✅ | — | binary |
| OSV-Scanner | ✅ | — | binary |
| Grype | ✅ | — | binary |
| CodeQL | — | — | multi-GB bundle — mount at runtime |
| OWASP ZAP | — | — | runs via Docker on the host (`run_active_scan`) |

> At startup the server logs how many scanners it can actually see (e.g.
> `Scanners available: 9/11 (...)`), and the `list_scanners` tool / `/ready`
> endpoint report the same — so it's always obvious what you have.




[![sast-mcp-server MCP server](https://glama.ai/mcp/servers/Skyrxin/sast-mcp-server/badges/card.svg)](https://glama.ai/mcp/servers/Skyrxin/sast-mcp-server)

---

## Usage with AI Agents

### Gemini CLI

Install as an extension:
```bash
gemini extensions install https://github.com/Skyrxin/sast-mcp-server
```

Or add to your `~/.gemini/settings.json`:
```json
{
  "mcpServers": {
    "sast": {
      "command": "uvx",
      "args": ["sast-mcp-server"]
    }
  }
}
```

### Claude Desktop

Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "sast": {
      "command": "uvx",
      "args": ["sast-mcp-server"]
    }
  }
}
```

See [full Claude Desktop guide](docs/claude-desktop.md).

### Cursor IDE

Add to Cursor Settings → MCP Servers:
```json
{
  "mcpServers": {
    "sast": {
      "command": "uvx",
      "args": ["sast-mcp-server"]
    }
  }
}
```

See [full Cursor guide](docs/cursor.md).

### OpenAI Agents SDK

```python
from agents.mcp import MCPServerStdio

sast_server = MCPServerStdio(command="uvx", args=["sast-mcp-server"])
```

See [full OpenAI guide](docs/openai.md).

---

## Available MCP Tools

### `scan_vulnerabilities`
Scan a directory for security vulnerabilities using a specific scanner.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Path to scan |
| `scanner_name` | string | `"bearer"` | Scanner: `bandit`, `njsscan`, `bearer`, `semgrep`, `trivy`, `codeql`, `checkov` |
| `min_severity` | string | `"LOW"` | Minimum severity: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `min_confidence` | string | `"LOW"` | Minimum confidence: `LOW`, `MEDIUM`, `HIGH` |
| `git_diff_only` | bool | `false` | Only scan git-modified files |
| `limit` | int | `50` | Max findings to return |
| `offset` | int | `0` | Pagination offset |

### `scan_all`
Run ALL installed scanners in parallel with automatic deduplication. **Recommended for comprehensive security scanning.**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Path to scan |
| `min_severity` | string | `"MEDIUM"` | Minimum severity (higher default to reduce noise) |
| `min_confidence` | string | `"LOW"` | Minimum confidence |
| `git_diff_only` | bool | `false` | Only scan git-modified files |
| `limit` | int | `50` | Max findings to return |
| `offset` | int | `0` | Pagination offset |

### `scan_git_history`
Scan the entire `.git` history for leaked secrets and credentials using Gitleaks.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | `"."` | Path to the repository root (must contain `.git`) |
| `min_severity` | string | `"LOW"` | Minimum severity to report |

### `run_active_scan`
Run a dynamic (DAST) baseline scan with OWASP ZAP by orchestrating a Docker Compose stack.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Directory containing the docker-compose file |
| `docker_compose_file` | string | *required* | Name of the docker-compose file (e.g. `docker-compose.yml`) |
| `target_url` | string | *required* | URL of the running app once it's up (e.g. `http://localhost:8080`) |

### `export_sarif`
Export scan results in SARIF 2.1.0 format for CI/CD integration.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Path to scan |
| `scanner_name` | string | `"bearer"` | Scanner to use |
| `min_severity` | string | `"LOW"` | Minimum severity |
| `min_confidence` | string | `"LOW"` | Minimum confidence |
| `output_path` | string | `""` | File path to write SARIF (empty = return as string) |

### `list_scanners`
List available scanners, their installation status, and supported languages.

### `ignore_vulnerability`
Suppress a finding from future scans (with audit trail).

### `unignore_vulnerability`
Re-enable a previously suppressed finding.

### `list_ignored_vulnerabilities`
Show all currently suppressed findings for a project.

### `save_baseline`
Run a scan and cache the results as a named baseline for future trend comparison.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Path to scan |
| `tag` | string | `"latest"` | Name for this baseline (e.g. `main`, `pre-release`) |
| `scanner_name` | string | `"bearer"` | Scanner to use |
| `min_severity` | string | `"LOW"` | Minimum severity to include |
| `min_confidence` | string | `"LOW"` | Minimum confidence to include |

### `compare_baseline`
Compare a fresh scan against a saved baseline to highlight new and fixed findings.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Path to scan |
| `tag` | string | `"latest"` | Baseline tag to compare against |
| `scanner_name` | string | `"bearer"` | Scanner to use |
| `min_severity` | string | `"LOW"` | Minimum severity to include |
| `min_confidence` | string | `"LOW"` | Minimum confidence to include |

### `upload_to_defectdojo`
Import a SARIF export into a DefectDojo engagement. Requires `DEFECTDOJO_URL`
and `DEFECTDOJO_API_KEY` environment variables.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sarif_path` | string | *required* | Path to a SARIF file from `export_sarif` |
| `engagement_id` | int | *required* | Target DefectDojo engagement ID |
| `active` | bool | `true` | Mark imported findings active |
| `verified` | bool | `false` | Mark imported findings verified |

### `upload_to_github`
Upload a SARIF report to GitHub Code Scanning. Requires a `GITHUB_TOKEN` with
`security_events: write` scope.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sarif_path` | string | *required* | Path to a SARIF file from `export_sarif` |
| `repo` | string | *required* | Repository in `owner/name` form |
| `commit_sha` | string | *required* | Full commit SHA the results apply to |
| `ref` | string | *required* | Fully qualified ref, e.g. `refs/heads/main` |

### `generate_fix_prompt`
Package a cached finding's vulnerable code and context into an LLM-ready prompt
that asks for a strict unified diff fix.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Scanned project root (with `.sast-mcp-cache`) |
| `finding_hash` | string | *required* | Hash of the finding to fix (from scan output) |
| `context_window` | int | `15` | Source lines to include before/after the finding |

### `apply_patch`
Apply an agent-generated unified diff to disk via `git apply` (paths that escape
the target directory are rejected).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Directory the patch paths are relative to |
| `patch` | string | *required* | The unified diff text to apply |
| `check_only` | bool | `false` | Validate without modifying files |

### `evaluate_policy`
Run all scanners and return an explicit **PASS/FAIL** verdict for CI gating.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Path to scan |
| `max_critical` | int | `0` | Max allowed CRITICAL (−1 = unlimited) |
| `max_high` | int | `-1` | Max allowed HIGH (−1 = unlimited) |
| `max_medium` | int | `-1` | Max allowed MEDIUM (−1 = unlimited) |
| `fail_on_new` | bool | `false` | Fail if findings are new vs. a `scan_all` baseline |
| `baseline_tag` | string | `"latest"` | Baseline tag used when `fail_on_new` |
| `output_format` | string | `"markdown"` | `markdown` or `json` |

### `export_sbom`
Run all scanners and export an SBOM / vulnerability report. In CycloneDX mode, if
[Syft](https://github.com/anchore/syft) is installed the component inventory is the
*full* dependency list (not just vulnerable packages).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Path to scan |
| `output_path` | string | `""` | File to write (empty = return inline) |
| `min_severity` | string | `"LOW"` | Minimum severity to include |
| `sca_only` | bool | `true` | Only dependency (SCA) findings; `false` = all |
| `format` | string | `"cyclonedx"` | `cyclonedx` or `spdx` (SPDX 2.3) |

### `generate_report`
Run all scanners and render an executive security report.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Path to scan |
| `output_path` | string | `""` | File to write (empty = return inline HTML; required for PDF) |
| `min_severity` | string | `"LOW"` | Minimum severity to include |
| `format` | string | `"html"` | `html` or `pdf` (needs the `[pdf]` extra) |

### `compliance_report`
Map findings to a compliance framework and report the posture.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Path to scan |
| `framework` | string | `"owasp"` | `owasp`, `sans`, `pci`, or `cis` |
| `output_path` | string | `""` | Optional file to write the markdown report |
| `min_severity` | string | `"LOW"` | Minimum severity to include |

### `scan_image`
Scan a container image reference for vulnerabilities and secrets (Trivy or Grype).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image_ref` | string | *required* | Image reference, e.g. `nginx:1.25` |
| `scanner_name` | string | `"trivy"` | `trivy` or `grype` |
| `min_severity` | string | `"MEDIUM"` | Minimum severity to report |
| `output_format` | string | `"markdown"` | `markdown` or `json` |

### `remediate_and_verify`
Closed-loop remediation: dry-run a patch, apply it, re-scan, and confirm the
finding is gone (rolling the patch back on failure).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Project root (with a `.sast-mcp-cache`) |
| `finding_hash` | string | *required* | Hash of the finding to fix |
| `patch` | string | *required* | Unified diff to apply |
| `scanner_name` | string | `""` | Re-scan scanner (default: the finding's scanner) |
| `auto_rollback` | bool | `true` | Revert the patch if verification fails |

### `import_sarif`
Ingest an external SARIF file (Snyk, Veracode, CI jobs, …) into the normalized
finding pipeline so it joins dedup / baselines / dashboards.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Project root the results belong to |
| `sarif_path` | string | *required* | Path to a SARIF 2.1.0 file |
| `scanner_name` | string | `"external"` | Source scanner name to record |
| `save` | bool | `true` | Cache the imported findings |

### `triage_finding`
Get an exploitability/false-positive assessment prompt, or record a CycloneDX VEX
decision (suppressing dispositions also add the finding to the ignore-list).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `target_path` | string | *required* | Project root (with a `.sast-mcp-cache`) |
| `finding_hash` | string | *required* | Hash of the finding to triage |
| `disposition` | string | `""` | `exploitable`, `not_affected`, `false_positive`, `resolved`, `in_triage` (empty = return a prompt) |
| `justification` | string | `""` | Rationale / CycloneDX justification keyword |

### `comment_on_pr`
Post a security summary on a GitHub PR or GitLab merge request. Requires
`GITHUB_TOKEN` or `GITLAB_TOKEN` (+ optional `GITLAB_URL`).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | string | *required* | `github` or `gitlab` |
| `repo` | string | *required* | `owner/name` (GitHub) or project ID/path (GitLab) |
| `pr_number` | int | *required* | PR number / MR IID |
| `body` | string | *required* | Markdown comment body |

### `notify_slack` / `notify_teams`
Send a notification to a Slack or Microsoft Teams incoming webhook
(`SLACK_WEBHOOK_URL` / `TEAMS_WEBHOOK_URL`).

### `create_jira_issue`
Open a Jira issue for a finding. Requires `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_key` | string | *required* | Jira project key (e.g. `SEC`) |
| `summary` | string | *required* | Issue title |
| `description` | string | *required* | Issue description |
| `issue_type` | string | `"Bug"` | Jira issue type |

> **Tip:** `scan_vulnerabilities`, `scan_all`, and `scan_git_history` accept
> `output_format="json"` for machine-readable results in CI/agent pipelines.

> **Auth:** On HTTP transports every tool is scope-gated — `scan:read` (scans,
> reports, exports), `scan:write` (baselines, patches, uploads, notifications),
> `config:write` (ignore list). Set `SAST_MCP_JWT_SECRET` and issue scoped JWTs.

---

## SARIF / CI/CD Integration

Export scan results in SARIF 2.1.0 format for integration with CI/CD platforms:

```bash
# In your CI pipeline, use the MCP tool:
# export_sarif(target_path=".", scanner_name="semgrep", output_path="results.sarif")

# Then upload to GitHub Code Scanning:
# gh api /repos/{owner}/{repo}/code-scanning/sarifs -f sarif=@results.sarif
```

Compatible with: GitHub Code Scanning, GitLab SAST, Azure DevOps, VS Code SARIF Viewer.

---

### Remote Deployment (Streamable HTTP)

For remote or cloud-hosted deployments, the 2026 MCP standard uses **Streamable HTTP**.

You can secure the server with **JWT Bearer Authentication** by setting a secret. Alternatively, for backward compatibility, you can use a static API key.

```bash
# Set JWT secret for secure authentication
export SAST_MCP_JWT_SECRET="your_hmac_sha256_secret"

# Or use the legacy API key method
export SAST_MCP_API_KEY="your_secure_api_key_here"

# Start the server with streamable-http transport
uv run sast-mcp-server --transport streamable-http --port 8080 --host 0.0.0.0
```

> **Note**: The old `sse` transport is deprecated. Please migrate to `streamable-http`.

## Core Workflows

### 1. Unified Vulnerability Scanning
Run any of the installed scanners individually (`scan_vulnerabilities(scanner_name="bandit")`) or run **all of them at once** using `scan_all`.

### 2. Deep Secret & Dynamic Scanning
Use `scan_git_history` to find API keys leaked years ago, or `run_active_scan` to spin up your application with Docker Compose and test it dynamically with OWASP ZAP.

### 3. Baseline & Trend Tracking
Save a scan as a named baseline and compare future scans against it to track new vulnerabilities, fixed issues, and severity trends over time.
- `save_baseline(target_path=".", tag="main")`
- `compare_baseline(target_path=".", tag="main")`

### 4. CI/CD Integration
Export scan results to SARIF format (`export_sarif`) to integrate with GitHub Code Scanning, GitLab SAST, or any other SARIF-compatible platform.

### 5. MCP Prompts (Security Workflows)
Pre-built security workflows that guide AI agents:
- `security_review`: Full codebase assessment
- `fix_vulnerability`: Focused remediation advisor
- `pr_security_check`: Scan only git diffs and enforce a severity gate
- `compliance_report`: Generate an OWASP Top 10 or PCI-DSS report

### 6. MCP Resources (Security Dashboards)
Read-only contextual data for AI agents without running a full scan:
- `sast://dashboard/{path}`: Security posture dashboard
- `sast://config`: Server configuration and status
- `sast://scanners`: Available scanners and languages
- `sast://cache/{path}/latest`: Latest scan results metadata

### 7. Dashboard Upload & AI-Assisted Remediation
Push SARIF results to external platforms and remediate findings with agent-written patches:
- `upload_to_defectdojo` / `upload_to_github`: Push a SARIF export to a dashboard
- `generate_fix_prompt`: Build an LLM-ready prompt for a specific finding
- `apply_patch`: Apply the resulting unified diff via `git apply`

### Docker

Pre-built images are published to GHCR on every release:

```bash
docker pull ghcr.io/skyrxin/sast-mcp-server:full       # 9 scanners (recommended)
docker pull ghcr.io/skyrxin/sast-mcp-server:minimal    # bandit, njsscan, bearer

# Run as an HTTP server
docker run -p 8080:8080 -e SAST_MCP_JWT_SECRET=your-secret \
  ghcr.io/skyrxin/sast-mcp-server:full --transport streamable-http

# …or use the bundled compose file (exposes /health /ready /metrics too)
docker compose up
```

Prefer to build locally?

```bash
docker build -t sast-mcp-server .                       # minimal
docker build -f Dockerfile.full -t sast-mcp-server:full .   # full
```

> CodeQL and OWASP ZAP are not bundled in the image — CodeQL ships a multi-GB
> bundle (mount at runtime) and ZAP's `run_active_scan` orchestrates Docker on
> the host.

---

## Reliability

"Production-ready" isn't a slogan here — it's measured in CI on every push:

- **226 tests**, **74% line coverage** ([Codecov](https://codecov.io/gh/Skyrxin/sast-mcp-server)), green across **Python 3.10–3.13**, with **mypy** type-checking enforced.
- **Self-scan, every build.** The server runs its own scanners against its own code in CI; the SARIF + summary are published as the `self-scan-report` artifact. A snapshot lives in [`examples/self-scan/`](examples/self-scan/SUMMARY.md).
- **Load-tested HTTP transport.** [`scripts/loadtest.py`](scripts/loadtest.py) runs in CI against the Streamable HTTP server: a local run sustains **~210 req/s at p95 ≈ 290 ms with zero failures** across `/health`, `/ready`, `/metrics` under 30 concurrent workers.
- **Ops endpoints** — `/health` (liveness), `/ready` (cached scanner inventory, 503 when none installed), `/metrics` (Prometheus text).
- **Bounded under load** — a configurable concurrency cap (`SAST_MCP_MAX_CONCURRENT_SCANS`) around subprocess scanners, per-client token-bucket rate limiting (`SAST_MCP_RATE_LIMIT_PER_MIN`) for HTTP transports, per-scanner timeouts, and an optional incremental-scan cache.

Run the load test yourself:

```bash
python scripts/loadtest.py --requests 2000 --concurrency 50
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SAST_MCP_TIMEOUT` | `300` | Scan timeout in seconds |
| `SAST_MCP_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `SAST_MCP_CACHE_TTL` | `86400` | Cache time-to-live in seconds (non-tagged scans) |
| `SAST_MCP_CACHE_MAX_SCANS` | `200` | Max non-tagged cached scans to retain (0 = unlimited) |
| `SAST_MCP_HTTP_RETRIES` | `3` | Retry attempts for integration HTTP calls |
| `SAST_MCP_HTTP_TIMEOUT` | `60` | Per-request timeout (s) for integration HTTP calls |
| `SAST_MCP_MAX_CONCURRENT_SCANS` | `8` | Max subprocess scanners running at once (0 = unlimited) |
| `SAST_MCP_RATE_LIMIT_PER_MIN` | `0` | Per-client request budget for HTTP transports (0 = disabled) |
| `SAST_MCP_SCANNER_TIMEOUTS` | *(none)* | JSON map of per-scanner timeout overrides, e.g. `{"trivy":600}` |
| `SAST_MCP_API_KEY` | *(none)* | API key for remote (HTTP) authentication |
| `SAST_MCP_JWT_SECRET` | *(none)* | HMAC-SHA256 secret for JWT bearer auth (scopes enforced per tool) |
| `DEFECTDOJO_URL` | *(none)* | Base URL of a DefectDojo instance (for `upload_to_defectdojo`) |
| `DEFECTDOJO_API_KEY` | *(none)* | DefectDojo API v2 token |
| `GITHUB_TOKEN` | *(none)* | Token with `security_events: write` (SARIF upload + PR comments) |
| `GITLAB_TOKEN` | *(none)* | GitLab token with `api` scope (for `comment_on_pr`) |
| `GITLAB_URL` | `https://gitlab.com` | GitLab base URL (self-managed override) |
| `SLACK_WEBHOOK_URL` | *(none)* | Slack incoming webhook (for `notify_slack`) |
| `TEAMS_WEBHOOK_URL` | *(none)* | Microsoft Teams incoming webhook (for `notify_teams`) |
| `JIRA_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` | *(none)* | Jira Cloud credentials (for `create_jira_issue`) |

### Operational endpoints (HTTP transports)

When running with `--transport streamable-http`, the server exposes:

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness probe — `200` with version while the process is up |
| `GET /ready` | Readiness probe — lists installed scanners (`503` if none) |
| `GET /metrics` | Prometheus text exposition (tool calls, scan durations, findings) |

### Incremental scans

`scan_vulnerabilities` and `scan_all` accept `use_cache=true`: the server
fingerprints the target's files and reuses the previous scan when nothing has
changed, so repeated scans in a session are fast.

---

## Development

```bash
# Clone and install with dev dependencies
git clone https://github.com/Skyrxin/sast-mcp-server.git
cd sast-mcp-server
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint
ruff check sast_mcp_server/

# Run locally
python -m sast_mcp_server
```

---

## Project Structure

```
sast_mcp_server/
├── __init__.py          # Package version
├── __main__.py          # python -m entry point
├── server.py            # FastMCP server with all tools + /health /ready /metrics
├── models.py            # Typed data models (Finding, Severity, etc.)
├── config.py            # Central validated settings (env-driven)
├── sarif.py             # SARIF 2.1.0 export and parsing
├── aggregator.py        # Multi-scanner parallel execution + deduplication
├── cache.py             # Scan caching, baselines, comparison, fingerprints
├── auth.py              # JWT / API key authentication for remote transports
├── metrics.py           # In-process Prometheus metrics
├── ratelimit.py         # Per-client token-bucket rate limiting
├── prompts.py           # MCP prompt templates (security workflows)
├── resources.py         # MCP resources (sast:// dashboards and metadata)
├── scanners/
│   ├── base.py          # Abstract scanner base class
│   ├── factory.py       # Scanner registry and factory
│   ├── bandit.py        # Bandit (Python)
│   ├── njsscan.py       # njsscan (JavaScript)
│   ├── bearer.py        # Bearer (multi-language)
│   ├── semgrep.py       # Semgrep (30+ languages)
│   ├── trivy.py         # Trivy (CVEs, secrets, IaC)
│   ├── codeql.py        # CodeQL (deep semantic SAST)
│   ├── checkov.py       # Checkov (IaC policies)
│   ├── gitleaks.py      # Gitleaks (git history secret scanning)
│   ├── osv_scanner.py   # OSV-Scanner (SCA / dependency CVEs)
│   ├── grype.py         # Grype (SCA + container image scanning)
│   └── zap.py           # OWASP ZAP (DAST via Docker)
├── enrichment/
│   ├── ast_context.py   # AST-aware code context extraction
│   ├── git_diff.py      # Git diff for incremental scanning
│   ├── ignore_manager.py # Finding ignore list management
│   ├── patch_prompt.py  # Builds LLM prompts to fix a cached finding
│   └── patch_apply.py   # Applies/reverts agent-generated diffs via `git apply`
├── reporting/
│   ├── sbom.py          # CycloneDX SBOM/VDR (+ optional Syft inventory)
│   ├── spdx.py          # SPDX 2.3 SBOM
│   ├── vex.py           # CycloneDX VEX statements (triage decisions)
│   ├── html.py          # Standalone HTML executive report
│   ├── pdf.py           # PDF report (optional [pdf] extra)
│   └── compliance.py    # OWASP / SANS / PCI / CIS mapping
└── integrations/
    ├── defectdojo.py    # Upload SARIF to DefectDojo
    ├── github.py        # GitHub Code Scanning + PR comments
    ├── gitlab.py        # GitLab MR comments
    ├── slack.py / teams.py  # Webhook notifications
    └── jira.py          # Create Jira issues
```

---

## License

[MIT](LICENSE)
