# MCP Servers Documentation

This directory contains comprehensive documentation for all configured Model Context Protocol (MCP) servers.

## Overview

MCP servers extend AI assistants with specialized capabilities through a standardized protocol. Each server provides tools, resources, and prompts that AI can use to perform specific tasks.

## Configured Servers


### AI/ML

- **[cloudflare-ai-gateway](./cloudflare-ai-gateway/README.md)** - Interface with Cloudflare AI Gateway for AI model access
- **[memory](./memory/README.md)** - Persistent memory and context storage for AI conversations

### Analytics

- **[cloudflare-radar](./cloudflare-radar/README.md)** - Access Cloudflare Radar internet intelligence data

### Authentication

- **[auth0](./auth0/README.md)** - Identity and access management via Auth0

### Automation

- **[mcp-cron](./mcp-cron/README.md)** - Cron-based task scheduling interface
- **[scheduler-mcp](./scheduler-mcp/README.md)** - Task scheduling and cron job management

### Cloud Infrastructure

- **[cloudflare-workers-bindings](./cloudflare-workers-bindings/README.md)** - Access Cloudflare Workers bindings and KV storage

### Communication

- **[discord](./discord/README.md)** - Discord bot integration and server management

### Database

- **[postgres](./postgres/README.md)** - PostgreSQL database query and management interface
- **[redis](./redis/README.md)** - Redis in-memory data store for caching and queuing
- **[supabase](./supabase/README.md)** - Supabase database and backend-as-a-service integration

### Development Tools

- **[ast-grep](./ast-grep/README.md)** - Structural code search using Abstract Syntax Tree pattern matching
- **[git-visualization](./git-visualization/README.md)** - Git repository visualization and analysis tools
- **[github](./github/README.md)** - GitHub repository management and API integration
- **[openapi](./openapi/README.md)** - OpenAPI/Swagger specification parsing and API exploration

### Events

- **[eventbrite](./eventbrite/README.md)** - Event management and ticketing via Eventbrite API

### Infrastructure

- **[porkbun](./porkbun/README.md)** - DNS management and domain registration via Porkbun API
- **[porkbun-custom](./porkbun-custom/README.md)** - Custom Porkbun DNS management implementation

### Monitoring

- **[cloudflare-observability](./cloudflare-observability/README.md)** - Monitor and analyze Cloudflare infrastructure metrics

### Networking

- **[tailscale](./tailscale/README.md)** - Tailscale VPN management and network configuration

### Productivity

- **[google-calendar](./google-calendar/README.md)** - Google Calendar integration for event management

### Queue

- **[bullmq](./bullmq/README.md)** - Job queue management using BullMQ and Redis

### SEO/Semantic Web

- **[schema-org](./schema-org/README.md)** - Generate and validate Schema.org structured data markup

### Security

- **[doppler-custom](./doppler-custom/README.md)** - Doppler secrets management and configuration

### Social Media

- **[linkedin](./linkedin/README.md)** - LinkedIn integration MCP server running locally

### System

- **[filesystem](./filesystem/README.md)** - File system access for reading and managing files

### Web

- **[fetch](./fetch/README.md)** - HTTP request capabilities for fetching web content

### Web Automation

- **[browserbase](./browserbase/README.md)** - Browser automation and web scraping capabilities
- **[cloudflare-browser-rendering](./cloudflare-browser-rendering/README.md)** - Server-side browser rendering via Cloudflare


## Directory Structure

Each MCP server has its own subdirectory containing:

- `README.md` - Comprehensive documentation including configuration, installation, and usage
- `schema.json` - Schema.org structured data describing the server

## Total Servers

**29** MCP servers are currently documented.

## Adding a New Server

To document a new MCP server:

1. Add server configuration to your MCP client config file
2. Add metadata to `MCP_DESCRIPTIONS` in `generate_mcp_docs.py`
3. Run `python generate_mcp_docs.py` to regenerate documentation

## Resources

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [MCP Server Registry](https://github.com/modelcontextprotocol/servers)
- [Claude Code Documentation](https://docs.claude.com/claude-code)

---

*Documentation generated automatically from MCP configuration files.*
