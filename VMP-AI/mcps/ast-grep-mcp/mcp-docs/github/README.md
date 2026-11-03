# Github MCP Server

## Overview

GitHub repository management and API integration

**Category:** Development Tools
**Package:** `@github/github-mcp-server`

## Configuration

### Local Server Configuration

```json
{
  "github": {
    "command": "docker"
,
    "args": [
      "run",
      "-i",
      "--rm",
      "-e",
      "GITHUB_PERSONAL_ACCESS_TOKEN",
      "ghcr.io/github/github-mcp-server"
    ]
,
    "env": {
      "GITHUB_PERSONAL_ACCESS_TOKEN": "$YOUR_GITHUB_PERSONAL_ACCESS_TOKEN_HERE"
    }
  }
}
```

## Required Environment Variables

- `GITHUB_PERSONAL_ACCESS_TOKEN`: Authentication token or API key

## Installation

Pull the Docker image:

```bash
docker pull ghcr.io/github/github-mcp-server
```

## Usage

Add this server to your MCP client configuration file (e.g., Claude Desktop config, Cursor MCP settings) using the configuration above.

## Schema.org Metadata

This directory includes a `schema.json` file with Schema.org structured data describing this MCP server.

## Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)

