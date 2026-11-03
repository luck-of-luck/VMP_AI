# Ast Grep MCP Server

## Overview

Structural code search using Abstract Syntax Tree pattern matching

**Category:** Development Tools
**Package:** `sg-mcp`

## Configuration

### Local Server Configuration

```json
{
  "ast-grep": {
    "command": "uv"
,
    "args": [
      "--directory",
      "/Users/alyshialedlie/code/ast-grep-mcp",
      "run",
      "main.py"
    ]
  }
}
```

## Installation

Install using uv:

```bash
uv sync
```

## Usage

Add this server to your MCP client configuration file (e.g., Claude Desktop config, Cursor MCP settings) using the configuration above.

## Schema.org Metadata

This directory includes a `schema.json` file with Schema.org structured data describing this MCP server.

## Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)

