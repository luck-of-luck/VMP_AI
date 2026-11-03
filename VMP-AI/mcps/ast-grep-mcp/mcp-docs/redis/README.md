# Redis MCP Server

## Overview

Redis in-memory data store for caching and queuing

**Category:** Database
**Package:** `@redis/redis-mcp-server`

## Configuration

### Local Server Configuration

```json
{
  "redis": {
    "command": "npx"
,
    "args": [
      "-y",
      "@redis/redis-mcp-server"
    ]
,
    "env": {
      "REDIS_URL": "$YOUR_REDIS_URL_HERE"
    }
  }
}
```

## Required Environment Variables

- `REDIS_URL`: Connection URL

## Installation

Install via npm:

```bash
npm install -g @redis/redis-mcp-server
```

Or use npx directly (recommended):

```bash
npx @redis/redis-mcp-server
```

## Usage

Add this server to your MCP client configuration file (e.g., Claude Desktop config, Cursor MCP settings) using the configuration above.

## Schema.org Metadata

This directory includes a `schema.json` file with Schema.org structured data describing this MCP server.

## Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)

