# Security Policy

## Supported Versions

Security fixes are provided for the latest released `0.x` minor version.

| Version | Supported |
|---------|-----------|
| 0.7.x   | ✅        |
| < 0.7   | ❌        |

## Reporting a Vulnerability

Please report security issues **privately** — do not open a public issue.

- Use GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing/privately-reporting-a-security-vulnerability)
  ("Report a vulnerability" under the repository's **Security** tab), or
- email the maintainer listed in `pyproject.toml`.

Please include a description, reproduction steps, and impact. We aim to
acknowledge reports within 5 business days and to ship a fix or mitigation as
quickly as severity warrants. We'll credit reporters who wish to be named once a
fix is released.

## Security Model & Hardening Notes

This server runs third-party scanner binaries and can talk to external services.
Key safeguards:

- **Credentials are environment-only.** Integration secrets (`GITHUB_TOKEN`,
  `DEFECTDOJO_*`, `GITLAB_TOKEN`, `SLACK_WEBHOOK_URL`, `TEAMS_WEBHOOK_URL`,
  `JIRA_*`) are read from environment variables and never accepted as tool
  arguments, so they don't appear in MCP transcripts or logs.
- **Authentication & scopes.** For HTTP transports, set `SAST_MCP_JWT_SECRET`
  (JWT) or `SAST_MCP_API_KEY`. Every tool is scope-gated (`scan:read`,
  `scan:write`, `config:write`, `admin`) and each call is recorded in a
  structured audit log on stderr. stdio (local) runs under a local trust model.
- **Patch application is sandboxed.** `apply_patch` shells out to `git apply`
  and never passes `--unsafe-paths`, so patches cannot modify files outside the
  target directory.
- **No stdout pollution.** All logging goes to stderr to keep the stdio MCP
  transport intact.

When deploying remotely, always enable authentication and run behind TLS.
