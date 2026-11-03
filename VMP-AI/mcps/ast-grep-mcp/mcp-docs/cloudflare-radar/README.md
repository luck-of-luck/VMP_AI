# Cloudflare Radar MCP Server

## Overview

Access Cloudflare Radar internet intelligence data

**Category:** Analytics
**Package:** `@cloudflare/mcp-radar`

## Configuration

### Local Server Configuration

```json
{
  "cloudflare-radar": {
    "command": "npx"
,
    "args": [
      "mcp-remote",
      "https://radar.mcp.cloudflare.com/mcp"
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

