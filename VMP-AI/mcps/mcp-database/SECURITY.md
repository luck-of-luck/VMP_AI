# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue for them.

Use GitHub's private vulnerability reporting: **Security → Advisories → Report a vulnerability**
(<https://github.com/DiegoBulhoes/mcp-database/security/advisories/new>).

Include, if you can:

- affected version or commit,
- a description and impact,
- steps to reproduce (a minimal query, connection mode, or config is ideal).

You can expect an acknowledgement within a few days. Please give a reasonable window to fix and
release before any public disclosure.

## Scope

This server sits between an LLM agent and your databases, so the security-relevant surface is:

- the access-mode matrix and fail-closed query validation (a read tool must never write; unbounded
  or destructive writes are gated),
- credential and PII handling (URI passwords are redacted from errors; audit logs record query
  shapes, not literal values),
- the supply chain of the server itself.

## Supply chain

- Dependencies are pinned with hashes in `uv.lock` and installed with `uv sync --frozen`.
- New versions are only adopted after a 15-day cooldown (`[tool.uv] exclude-newer`), and runtime
  dependencies are capped to their current major.
- GitHub Actions are pinned by commit SHA and Docker base images by digest.
- When the repository is public, the published Docker image also carries SLSA build provenance
  (verify with `gh attestation verify oci://ghcr.io/diegobulhoes/mcp-database:<tag> --owner DiegoBulhoes`).
  Provenance attestation is skipped while the repository is private (a GitHub platform limitation).

## Supported versions

This project tracks `main`; fixes land there and in the latest published image and tag.
