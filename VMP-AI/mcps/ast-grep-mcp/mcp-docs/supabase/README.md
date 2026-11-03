# Supabase MCP Server

## Overview

Supabase database and backend-as-a-service integration

**Category:** Database
**Package:** `@supabase/mcp-server`

## Configuration

### Remote Server Configuration

This MCP connects to a remote server endpoint.

```json
{
  "supabase": {
    "url": "https://mcp.supabase.com/mcp?project_ref=cfrbahzzklwrnmbtqojl"
,
    "headers": {
      "Authorization": "Bearer YOUR_TOKEN_HERE"
    }
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

