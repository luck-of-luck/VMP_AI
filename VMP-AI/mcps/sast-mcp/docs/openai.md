# Using SAST MCP Server with OpenAI Agents

## Overview

OpenAI's Agents SDK supports MCP servers as tool providers. You can connect the SAST MCP Server
to OpenAI-powered agents to add security scanning capabilities.

## Installation

```bash
pip install sast-mcp-server openai-agents
```

## Usage with OpenAI Agents SDK

```python
from agents import Agent
from agents.mcp import MCPServerStdio

# Create the MCP server connection
sast_server = MCPServerStdio(
    command="sast-mcp-server",
    # Or use: command="uvx", args=["sast-mcp-server"]
)

# Create an agent with SAST tools
agent = Agent(
    name="Security Reviewer",
    instructions="You are a security code reviewer. Use the SAST tools to scan code for vulnerabilities and suggest fixes.",
    mcp_servers=[sast_server],
)

# Run the agent
async def main():
    async with sast_server:
        result = await agent.run("Scan /path/to/project for security issues")
        print(result)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SAST_MCP_TIMEOUT` | `300` | Scan timeout in seconds |
| `SAST_MCP_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |

## Scanner Requirements

Ensure at least one scanner is installed on the system where the MCP server runs:

- **Bandit** (Python): `pip install bandit`
- **njsscan** (JavaScript): `pip install njsscan`
- **Bearer** (Multi-language): [Installation guide](https://docs.bearer.com/installation/)
