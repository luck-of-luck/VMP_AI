# Using SAST MCP Server with Cursor IDE

## Setup

### Step 1: Install the server
```bash
pip install sast-mcp-server
```

### Step 2: Configure in Cursor

Open Cursor Settings → MCP Servers and add a new server:

**Name:** `sast`

**Command:**
```
sast-mcp-server
```

Or using uvx (no pre-install needed):
```
uvx sast-mcp-server
```

### Alternative: Edit settings.json directly

Add to your Cursor `settings.json`:
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

## Usage

Once configured, you can use Cursor's AI features to:

1. **Scan the current project:**
   Ask: "Scan this project for security vulnerabilities using bandit"

2. **Review only changes:**
   Ask: "Check my recent changes for security issues" (uses git diff)

3. **Focus on critical issues:**
   Ask: "Show me only HIGH and CRITICAL security findings"

4. **Suppress false positives:**
   Ask: "Ignore this finding, it's a false positive because..."

## Scanner Requirements

Install at least one scanner:

| Scanner | Install | Languages |
|---------|---------|-----------|
| Bandit | `pip install bandit` | Python |
| njsscan | `pip install njsscan` | JavaScript, Node.js |
| Bearer | [docs.bearer.com](https://docs.bearer.com/installation/) | Multi-language |
