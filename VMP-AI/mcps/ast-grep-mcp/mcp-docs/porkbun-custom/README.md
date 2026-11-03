# Porkbun Custom MCP Server

## Overview

Custom Porkbun DNS management implementation

**Category:** Infrastructure
**Package:** `custom-porkbun-mcp`

## Configuration

### Local Server Configuration

```json
{
  "porkbun-custom": {
    "command": "node"
,
    "args": [
      "/Users/alyshialedlie/code/bot_army/porkbun-mcp-server/build/index.js"
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

## Usage

Add this server to your MCP client configuration file (e.g., Claude Desktop config, Cursor MCP settings) using the configuration above.

## Schema.org Metadata

This directory includes a `schema.json` file with Schema.org structured data describing this MCP server.

## Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)

