# Filesystem MCP Server

## Overview

File system access for reading and managing files

**Category:** System
**Package:** `@modelcontextprotocol/server-filesystem`

## Configuration

### Local Server Configuration

```json
{
  "filesystem": {
    "command": "npx"
,
    "args": [
      "-y",
      "@modelcontextprotocol/server-filesystem",
      "/Users/alyshialedlie/code"
    ]
  }
}
```

## Installation

Install via npm:

```bash
npm install -g @modelcontextprotocol/server-filesystem
```

Or use npx directly (recommended):

```bash
npx @modelcontextprotocol/server-filesystem
```

## Usage

Add this server to your MCP client configuration file (e.g., Claude Desktop config, Cursor MCP settings) using the configuration above.

## Schema.org Metadata

This directory includes a `schema.json` file with Schema.org structured data describing this MCP server.

## Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Package Repository](https://github.com/modelcontextprotocol/server-filesystem)

