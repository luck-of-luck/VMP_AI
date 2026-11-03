# Using SAST MCP Server with Claude Desktop

## Installation

### Option 1: Via PyPI (recommended)
```bash
pip install sast-mcp-server
```

### Option 2: Via uvx (no install needed)
No pre-installation required — `uvx` handles it automatically.

## Configuration

Add the following to your Claude Desktop configuration file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

### Using uvx (recommended)
```json
{
  "mcpServers": {
    "sast": {
      "command": "uvx",
      "args": ["sast-mcp-server"],
      "env": {
        "SAST_MCP_TIMEOUT": "300"
      }
    }
  }
}
```

### Using pip-installed binary
```json
{
  "mcpServers": {
    "sast": {
      "command": "sast-mcp-server",
      "args": [],
      "env": {
        "SAST_MCP_TIMEOUT": "300"
      }
    }
  }
}
```

### Using Docker
```json
{
  "mcpServers": {
    "sast": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "/path/to/your/code:/code", "sast-mcp-server"],
      "env": {}
    }
  }
}
```

## Scanner Requirements

The SAST MCP Server requires at least one scanner to be installed:

| Scanner | Language | Install Command |
|---------|----------|----------------|
| Bandit | Python | `pip install bandit` |
| njsscan | JavaScript/Node.js | `pip install njsscan` |
| Bearer | Multi-language | [Installation guide](https://docs.bearer.com/installation/) |

> **Tip:** Use the `list_scanners` tool to check which scanners are available.

## Usage

Once configured, you can ask Claude to:
- "Scan my project at /path/to/project for security vulnerabilities"
- "Check for Python security issues using bandit"
- "Show me only HIGH severity findings"
- "Scan only the files I changed recently"
