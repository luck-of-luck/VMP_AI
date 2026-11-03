# Configuration examples

| File | What it is | Where it goes |
|------|-----------|---------------|
| [mcp.json](mcp.json) | MCP client registration via the GHCR Docker image. One entry per connection, configured with environment variables. Only `URI` is required (see `db-mysql` for the minimal form); includes a `PASSWORD_ENV` variant | Project root as `.mcp.json`, or merge into `claude_desktop_config.json` |
| [claude-permissions.json](claude-permissions.json) | Claude Code allowlist unlocking the 22 always-safe tools (`db_schema_`/`db_read_`/`db_perf_`) for the `db-postgres`/`db-mysql`/`db-mongo` server entries; `db_write_query` and `db_admin_*` keep prompting | Merge into the project's `.claude/settings.json` or your global settings |

Notes:

- Tool permissions are namespaced by the `mcpServers` entry key (`mcp__db-postgres__db_read_query`). If you rename an entry or add one, adjust the allowlist prefixes to match.
- `--network host` lets `localhost` URIs reach databases on the host (Linux). On macOS, drop it and use `host.docker.internal` in the URIs instead (see the [README Docker notes](../../README.md#docker)).
- Passwords: prefer `PASSWORD_ENV` over embedding credentials in URIs, especially in files that get committed. With Docker, forward the referenced variable into the container: `"-e", "PG_APP_PASSWORD"` before the image name.
