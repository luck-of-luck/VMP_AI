# Porkbun MCP Server

## Overview

DNS management and domain registration via Porkbun API

**Category:** Infrastructure
**Package:** `@modelcontextprotocol/server-porkbun`

## Configuration

### Local Server Configuration

```json
{
  "porkbun": {
    "command": "npx"
,
    "args": [
      "-y",
      "@modelcontextprotocol/server-porkbun"
    ]
,
    "env": {
      "PORKBUN_API_KEY": "$YOUR_PORKBUN_API_KEY_HERE",
      "PORKBUN_SECRET_API_KEY": "$YOUR_PORKBUN_SECRET_API_KEY_HERE"
    }
  }
}
```

## Required Environment Variables

- `PORKBUN_API_KEY`: Authentication token or API key
- `PORKBUN_SECRET_API_KEY`: Authentication token or API key

## Installation

Install via npm:

```bash
npm install -g @modelcontextprotocol/server-porkbun
```

Or use npx directly (recommended):

```bash
npx @modelcontextprotocol/server-porkbun
```

## Usage

Add this server to your MCP client configuration file (e.g., Claude Desktop config, Cursor MCP settings) using the configuration above.

## Schema.org Metadata

This directory includes a `schema.json` file with Schema.org structured data describing this MCP server.

## Resources

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Package Repository](https://github.com/modelcontextprotocol/server-porkbun)

