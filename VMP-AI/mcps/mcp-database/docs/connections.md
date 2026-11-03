# Connecting to each engine

One `mcpServers` entry = one connection = one server instance. All configuration lives in the `env`
block; the Docker `args` line is a **fixed template you never edit** — the `-e` flags carry no values,
they only forward the `env` block into the container (absent variables are ignored):

```json
"args": ["run", "-i", "--rm", "--network", "host",
         "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
         "ghcr.io/diegobulhoes/mcp-database:latest"]
```

Two switches cover every case below:

- **Local database** (same machine): keep `--network host` so the container reaches `localhost`.
  On macOS/Windows Docker Desktop, drop it and use `host.docker.internal` in the URI instead.
- **External database** (managed/remote): drop `--network host` and put TLS in the URI
  (`?sslmode=require`, `mongodb+srv://`, `rediss://`).

`MODE` defaults to `read_only` — the safest entry is also the shortest. `ENGINE_TYPE` and `NAME` are
optional (engine is inferred from the URI scheme; `NAME` defaults to the engine). Full variable
reference: [configuration.md](configuration.md).

## Table of Contents

- [PostgreSQL](#postgresql)
- [MySQL](#mysql)
- [MariaDB](#mariadb)
- [SQLite](#sqlite)
- [MongoDB](#mongodb)
- [Redis](#redis)

## PostgreSQL

Local (playground):

```json
"db-postgres": {
  "command": "docker",
  "args": ["run", "-i", "--rm", "--network", "host",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "postgresql://dev:dev@localhost:5432/app",
    "ENGINE_TYPE": "postgres",
    "MODE": "read_write"
  }
}
```

External (e.g. RDS/Cloud SQL — no `--network host`, TLS required, mode defaults to `read_only`):

```json
"db-postgres-prod": {
  "command": "docker",
  "args": ["run", "-i", "--rm",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "postgresql://app:secret@mydb.abc123.us-east-1.rds.amazonaws.com:5432/orders?sslmode=require",
    "ENGINE_TYPE": "postgres"
  }
}
```

## MySQL

Local (playground):

```json
"db-mysql": {
  "command": "docker",
  "args": ["run", "-i", "--rm", "--network", "host",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "mysql://root:dev@localhost:3306/app",
    "ENGINE_TYPE": "mysql",
    "MODE": "read_write"
  }
}
```

External (e.g. RDS/PlanetScale):

```json
"db-mysql-prod": {
  "command": "docker",
  "args": ["run", "-i", "--rm",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "mysql://app:secret@mysql.abc123.us-east-1.rds.amazonaws.com:3306/orders?ssl=true",
    "ENGINE_TYPE": "mysql"
  }
}
```

## MariaDB

Local (playground, host port 3307):

```json
"db-mariadb": {
  "command": "docker",
  "args": ["run", "-i", "--rm", "--network", "host",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "mariadb://root:dev@localhost:3307/app",
    "ENGINE_TYPE": "mariadb",
    "MODE": "read_write"
  }
}
```

External (e.g. SkySQL/managed MariaDB):

```json
"db-mariadb-prod": {
  "command": "docker",
  "args": ["run", "-i", "--rm",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "mariadb://app:secret@db.example-sky.mariadb.com:3306/orders?ssl=true",
    "ENGINE_TYPE": "mariadb"
  }
}
```

## SQLite

SQLite is a local file, so there is no "external" form — the two variants are *how the file is reached*.
Simplest is running from a local checkout (the process sees your filesystem directly):

```json
"db-sqlite": {
  "command": "uv",
  "args": ["run", "--directory", "/path/to/mcp-database", "mcp-database"],
  "env": {
    "URI": "sqlite:///temp/playground.db",
    "ENGINE_TYPE": "sqlite",
    "MODE": "read_write"
  }
}
```

Via Docker the file must be mounted into the container (`-v`), and the URI points at the mount:

```json
"db-sqlite-docker": {
  "command": "docker",
  "args": ["run", "-i", "--rm",
           "-v", "/home/me/data:/data",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "sqlite:////data/app.db",
    "ENGINE_TYPE": "sqlite",
    "MODE": "read_write"
  }
}
```

`sqlite:///path` is relative, `sqlite:////path` is absolute; `:memory:` is rejected (independent
connections would each get their own empty database).

## MongoDB

Local (playground replica set, host port 27019 — `directConnection` because the replica set announces
its internal address):

```json
"db-mongo": {
  "command": "docker",
  "args": ["run", "-i", "--rm", "--network", "host",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "mongodb://localhost:27019/app?directConnection=true",
    "ENGINE_TYPE": "mongodb",
    "MODE": "read_write"
  }
}
```

External (Atlas — `mongodb+srv://` embeds TLS and cluster discovery):

```json
"db-mongo-atlas": {
  "command": "docker",
  "args": ["run", "-i", "--rm",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "mongodb+srv://reader:secret@cluster0.abc12.mongodb.net/app",
    "ENGINE_TYPE": "mongodb"
  }
}
```

## Redis

Local (playground, host port 6380; the `/0` picks the logical database — one per instance):

```json
"db-redis": {
  "command": "docker",
  "args": ["run", "-i", "--rm", "--network", "host",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "redis://localhost:6380/0",
    "ENGINE_TYPE": "redis",
    "MODE": "read_write"
  }
}
```

External (managed Redis — `rediss://` for TLS; `monitor` mode suits production diagnostics):

```json
"db-redis-cloud": {
  "command": "docker",
  "args": ["run", "-i", "--rm",
           "-e", "URI", "-e", "ENGINE_TYPE", "-e", "MODE", "-e", "NAME",
           "ghcr.io/diegobulhoes/mcp-database:latest"],
  "env": {
    "URI": "rediss://default:secret@redis-12345.c1.us-east-1-2.ec2.redns.redis-cloud.com:12345/0",
    "ENGINE_TYPE": "redis",
    "MODE": "monitor"
  }
}
```
