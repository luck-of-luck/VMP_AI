# Browserbase MCP Server

## Overview

Browser automation and web scraping capabilities

**Category:** Web Automation
**Package:** `@browserbasehq/mcp-server-browserbase`

## Configuration

### Local Server Configuration

```json
{
  "browserbase": {
    "command": "doppler"
,
    "args": [
      "run",
      "--project",
      "integrity-studio",
      "--config",
      "dev",
      "--",
      "npx",
      "@browserbasehq/mcp-server-browserbase"
    ]
  }
}
```

## Installation

## Usage

Add this server to your MCP client configuration file (e.g., Claude Desktop config, Cursor MCP settings) using the configuration above.

## Schema.org Metadata

This directory includes a `schema.json` file with Schema.org structured data describing this MCP server.

## Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)

