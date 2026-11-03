# Cloudflare Workers Bindings MCP Server

## Overview

Access Cloudflare Workers bindings and KV storage

**Category:** Cloud Infrastructure
**Package:** `@cloudflare/mcp-workers-bindings`

## Configuration

### Local Server Configuration

```json
{
  "cloudflare-workers-bindings": {
    "command": "npx"
,
    "args": [
      "mcp-remote",
      "https://bindings.mcp.cloudflare.com/mcp"
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

