# Cloudflare Observability MCP Server

## Overview

Monitor and analyze Cloudflare infrastructure metrics

**Category:** Monitoring
**Package:** `@cloudflare/mcp-observability`

## Configuration

### Local Server Configuration

```json
{
  "cloudflare-observability": {
    "command": "npx"
,
    "args": [
      "mcp-remote",
      "https://observability.mcp.cloudflare.com/mcp"
    ]
  }
}
```

## Installation

Install via npm:

```bash
npm install -g mcp-remote
```

Or use npx directly (recommended):

```bash
npx mcp-remote
```

## Usage

Add this server to your MCP client configuration file (e.g., Claude Desktop config, Cursor MCP settings) using the configuration above.

## Schema.org Metadata

This directory includes a `schema.json` file with Schema.org structured data describing this MCP server.

## Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)

