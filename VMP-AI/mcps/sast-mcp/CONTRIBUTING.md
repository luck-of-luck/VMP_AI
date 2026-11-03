# Contributing

Thanks for your interest in improving SAST MCP Server!

## Development setup

```bash
git clone https://github.com/Skyrxin/sast-mcp-server.git
cd sast-mcp-server
pip install -e ".[dev]"
```

## Quality gates (must pass before a PR)

CI enforces all three:

```bash
ruff check sast_mcp_server/      # lint
mypy sast_mcp_server/            # types (enforced)
pytest tests/ -v                 # tests (with coverage floor in CI)
```

Run a single test:

```bash
pytest tests/test_server.py::TestScanAll -v
```

## Adding a scanner

See `ARCHITECTURE.md` → "Scanner plugin architecture". In short:

1. Subclass `BaseScanner` in `sast_mcp_server/scanners/<name>.py` with a `name`
   class attribute, `version_command`, `check_dependency()`, and `scan()`.
2. Populate enterprise metadata (`cwe`, `cvss_*`, `owasp_category`,
   `references`, `remediation`) on each `Finding` where the tool provides it,
   using helpers in `enrichment/metadata.py`.
3. Register it in both `_SCANNER_REGISTRY` and `SCANNER_INFO` in
   `scanners/factory.py`, export it from `scanners/__init__.py`.
4. Add tests with recorded fixture output (mock `asyncio.create_subprocess_exec`).

## Adding an integration

Put outbound HTTP calls behind `integrations/_http.py` (`post_with_retry`) so
retries/backoff/timeouts are consistent, read credentials from env vars only,
and raise `IntegrationError` on failure. Then expose a thin `@mcp.tool()` in
`server.py` decorated with `@audited(<scope>)`.

## Conventions

- Match surrounding code style; keep logging on **stderr** only.
- Tools return user-facing strings (markdown by default; offer `output_format`
  where structured JSON is useful).
- Update `CHANGELOG.md` under an `Unreleased`/next-version heading.

## Releasing

Maintainers: bump the version in `pyproject.toml` and `sast_mcp_server/__init__.py`,
update `CHANGELOG.md`, then push a `vX.Y.Z` tag — CI publishes to PyPI via OIDC.
