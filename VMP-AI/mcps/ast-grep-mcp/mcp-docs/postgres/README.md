# Postgres MCP Server

## Overview

PostgreSQL database query and management interface

**Category:** Database
**Package:** `@modelcontextprotocol/server-postgres`

## Configuration

### Local Server Configuration

```json
{
  "postgres": {
    "command": "npx"
,
    "args": [
      "-y",
      "@modelcontextprotocol/server-postgres"
    ]
,
    "env": {
      "DATABASE_URL": "$YOUR_DATABASE_URL_HERE"
    }
  }
}
```

## Required Environment Variables

- `DATABASE_URL`: Connection URL

## Installation

Install via npm:

```bash
npm install -g @modelcontextprotocol/server-postgres
```

Or use npx directly (recommended):

```bash
npx @modelcontextprotocol/server-postgres
```

## Usage

Add this server to your MCP client configuration file (e.g., Claude Desktop config, Cursor MCP settings) using the configuration above.

## Schema.org Metadata

This directory includes a `schema.json` file with Schema.org structured data describing this MCP server.

## Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Package Repository](https://github.com/modelcontextprotocol/server-postgres)

