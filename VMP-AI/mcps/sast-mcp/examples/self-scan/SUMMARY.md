# Self-scan report

_SAST MCP Server v0.8.1 scanning `sast_mcp_server` — generated 2026-06-18 19:27 UTC._

This is the server running its own scanners against its own code: real
output from `scan_all`, exported to SARIF and summarized here.

## Summary

- **Total findings:** 7
- **Scanners run:** bandit
- **Scanners skipped (not installed):** bearer, checkov, codeql, gitleaks, grype, njsscan, osv-scanner, semgrep, trivy, zap

### Findings by severity

| Severity | Count |
|----------|------:|
| MEDIUM | 2 |
| LOW | 5 |

### Findings by scanner

| Scanner | Count |
|---------|------:|
| bandit | 7 |

### Top findings

| Severity | Scanner | Finding | Location |
|----------|---------|---------|----------|
| MEDIUM | bandit | blacklist | `sast_mcp_server/scanners/zap.py:174` |
| MEDIUM | bandit | hardcoded_bind_all_interfaces | `sast_mcp_server/server.py:2259` |
| LOW | bandit | hardcoded_password_string | `sast_mcp_server/config.py:24` |
| LOW | bandit | hardcoded_password_string | `sast_mcp_server/integrations/github.py:13` |
| LOW | bandit | hardcoded_password_string | `sast_mcp_server/integrations/gitlab.py:10` |
| LOW | bandit | hardcoded_password_string | `sast_mcp_server/integrations/jira.py:11` |
| LOW | bandit | try_except_pass | `sast_mcp_server/server.py:125` |
