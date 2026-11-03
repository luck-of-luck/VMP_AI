## Tool Purpose

This extension provides **SAST (Static Application Security Testing)** scanning capabilities.
It can scan codebases for security vulnerabilities using industry-standard tools:
Bandit (Python), njsscan (JavaScript/Node.js), Bearer (multi-language with data-flow analysis),
Semgrep (30+ languages with community rule registry), Trivy (vulnerabilities, secrets, IaC),
CodeQL (deep semantic analysis with taint tracking), Checkov (Infrastructure-as-Code policies),
Gitleaks (deep secret scanning in git history), OSV-Scanner (Software Composition Analysis),
and OWASP ZAP (Dynamic Application Security Testing via Docker orchestration).

## Available Tools

1. **`scan_vulnerabilities`** — Scan a directory for security vulnerabilities (SAST)
2. **`scan_all`** — Run ALL installed scanners in parallel with deduplication
3. **`scan_git_history`** — Scan the entire `.git` history for leaked secrets (Gitleaks)
4. **`run_active_scan`** — Run a dynamic (DAST) baseline scan by orchestrating Docker Compose (ZAP)
5. **`export_sarif`** — Export scan results in SARIF 2.1.0 format for CI/CD
6. **`list_scanners`** — Check which scanners are installed and available
7. **`ignore_vulnerability`** — Suppress a known false positive
8. **`unignore_vulnerability`** — Re-enable a previously ignored finding
9. **`list_ignored_vulnerabilities`** — Show all currently suppressed findings
10. **`save_baseline`** — Save a scan result as a baseline for future comparison
11. **`compare_baseline`** — Compare current codebase against a saved baseline
12. **`upload_to_defectdojo`** — Import a SARIF export into a DefectDojo engagement
13. **`upload_to_github`** — Upload a SARIF report to GitHub Code Scanning
14. **`generate_fix_prompt`** — Build an LLM prompt to fix a finding as a unified diff
15. **`apply_patch`** — Apply an agent-generated unified diff to disk (via `git apply`)

## Usage Patterns

### Initial Setup
Always start by calling `list_scanners` to verify which tools are available on the user's system.

### Choosing a Scanner
- **Python projects** → use `scanner_name="bandit"` or `scanner_name="semgrep"`
- **JavaScript/Node.js projects** → use `scanner_name="njsscan"` or `scanner_name="semgrep"`
- **Multi-language or uncertain** → use `scanner_name="semgrep"` (broadest coverage)
- **Data-flow analysis needed** → use `scanner_name="bearer"`
- **Dependency CVEs / supply chain** → use `scanner_name="osv-scanner"` or `trivy`
- **Secrets in git history** → use `scan_git_history`
- **Deep semantic analysis** → use `scanner_name="codeql"` (slower but finds complex flaws)
- **Infrastructure-as-Code policies** → use `scanner_name="checkov"`
- **Dynamic Application Testing (DAST)** → use `run_active_scan` (orchestrates ZAP via Docker)
- **Comprehensive scan** → use `scan_all` to run everything installed at once

### Scanning Workflow
1. Call `scan_vulnerabilities` (or `scan_all` for comprehensive coverage) with the project root path
2. Review findings — focus on HIGH and CRITICAL severity first
3. For each finding, suggest a fix based on the provided code context
4. If the user confirms a false positive, use `ignore_vulnerability` with a clear reason

### Regression & Trend Tracking (Baselines)
When establishing a security posture or before a major refactor:
1. Call `save_baseline(tag="main")` to snapshot the current state
2. After changes, call `compare_baseline(tag="main")` to see newly introduced vs. fixed vulnerabilities

### Using MCP Prompts (Workflows)
You have access to pre-built security workflows via MCP prompts. You should invoke these when asked to perform a broad security task:
- `security_review`: For a comprehensive codebase assessment
- `fix_vulnerability`: For deep-dive remediation of a specific finding hash
- `pr_security_check`: When reviewing a Pull Request or git diff
- `compliance_report`: When asked about OWASP Top 10 or PCI-DSS compliance

### Using MCP Resources (Context)
You can access read-only contextual data without running a scan by requesting these resources:
- `sast://dashboard/{target_path}`: View a high-level severity distribution and overall security posture
- `sast://cache/{target_path}/latest`: View metadata of the most recent scans without waiting for execution

### CI/CD Integration
Use `export_sarif` to generate SARIF 2.1.0 output that can be uploaded to:
- GitHub Code Scanning
- GitLab SAST
- Azure DevOps
- Any SARIF-compatible security dashboard

### Dashboard Upload & AI Remediation (v0.6.0)
- After `export_sarif(output_path=...)`, push the report to a dashboard with
  `upload_to_defectdojo` or `upload_to_github`. Credentials come from
  environment variables only (`DEFECTDOJO_URL`/`DEFECTDOJO_API_KEY`,
  `GITHUB_TOKEN`) — never ask the user to paste secrets as arguments.
- To remediate a finding: call `generate_fix_prompt(target_path, finding_hash)`
  to get an LLM-ready prompt, produce a unified diff, then `apply_patch` with
  `check_only=True` before applying for real. The finding must come from a
  cached scan (`scan_all`/`save_baseline`).

### Incremental Scanning
When reviewing a pull request or recent changes, use `git_diff_only=True` to only scan modified files.

### Pagination
For large codebases, use `min_severity="HIGH"` to focus on critical issues first,
or use `limit` and `offset` for pagination.

## Best Practices
- Always explain findings in plain language, not just technical jargon
- Provide concrete code fix suggestions alongside each finding
- Group related findings together when presenting results
- Use `min_severity="MEDIUM"` as a sensible default for most scans
- When a scan returns many results, summarize the top issues before showing details
- Use `scan_all` for the most comprehensive security assessment
- **New for v0.4.0**: Use `compare_baseline` to highlight newly introduced vulnerabilities instead of overwhelming the user with legacy issues.
