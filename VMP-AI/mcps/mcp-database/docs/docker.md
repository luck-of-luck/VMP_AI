# Docker

## Table of Contents

- [Running the image](#running-the-image)
- [MCP client entry](#mcp-client-entry)

## Running the image

CI publishes the image to GHCR only on a release — a push to `main` whose `pyproject.toml` version has no matching `v*` tag (tags: `X.Y.Z`, `sha`, `latest`):

```bash
docker run -i --rm --network host \
  -e NAME=pg_app \
  -e URI="postgresql://app@localhost:5432/app" \
  -e MODE=read_write \
  ghcr.io/diegobulhoes/mcp-database:latest
```

> `--network host` lets `localhost` URIs reach databases running on the host. Drop it for remote-only databases.
>
> With `PASSWORD_ENV`, forward the referenced variable into the container by adding `-e APP_PG_PASSWORD` (no value: Docker copies it from your shell).
>
> **macOS**: the image is multi-arch (amd64 + arm64), so it runs natively on Apple Silicon via Docker Desktop. Host networking behaves differently there: instead of `--network host`, use `host.docker.internal` in your connection URIs (e.g. `postgresql://app@host.docker.internal:5432/app`) to reach databases running on the Mac.

## MCP client entry

```json
{
  "mcpServers": {
    "db-postgres": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "--network", "host",
               "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
               "ghcr.io/diegobulhoes/mcp-database:latest"],
      "env": {
        "URI": "postgresql://app@localhost:5432/app",
        "ENGINE_TYPE": "postgres",
        "MODE": "read_write"
      }
    }
  }
}
```

See [configuration.md](configuration.md) for the full list of environment variables and
[connections.md](connections.md) for per-engine local and external examples.
