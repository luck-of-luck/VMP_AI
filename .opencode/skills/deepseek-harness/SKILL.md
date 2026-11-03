# DeepSeek Harness Integration Skill

Integrates DeepSeek Harness (dsh) with opencode via MCP server wrapper.

## When to Use

- Run DeepSeek Harness profiles (headless, web, tui, rescue) from opencode
- Execute one-shot tasks using dsh headless profile
- Manage dsh plugins and profiles
- Access dsh capabilities as MCP tools

## Tools Available (via MCP `dsh-mcp`)

| Tool | Description |
|------|-------------|
| `dsh_run_headless` | Run a one-shot task using dsh headless profile |
| `dsh_run_profile` | Run a dsh profile with arguments |
| `dsh_list_profiles` | List available dsh profiles |
| `dsh_dump_config` | Dump the composed profile configuration |
| `dsh_install_plugin` | Install a plugin into a dsh profile |

## Resources Available

| URI | Description |
|-----|-------------|
| `dsh://profiles` | List of available profiles (JSON) |
| `dsh://profiles/headless` | Headless profile config (YAML) |
| `dsh://profiles/web` | Web profile config (YAML) |

## Usage Examples

### Run a one-shot task
```javascript
// Use the dsh_run_headless tool
await mcp.dsh_mcp.dsh_run_headless({
  task: "analyze the codebase and find all TODO comments",
  profile: "headless"
});
```

### Run a profile with arguments
```javascript
// Use the dsh_run_profile tool
await mcp.dsh_mcp.dsh_run_profile({
  profile: "web",
  args: ["--port", "3080"]
});
```

### List profiles
```javascript
// Use the dsh_list_profiles tool
await mcp.dsh_mcp.dsh_list_profiles({});
```

### Dump profile configuration
```javascript
// Use the dsh_dump_config tool
await mcp.dsh_mcp.dsh_dump_config({
  profile: "headless",
  defaultOnly: false
});
```

### Install a plugin
```javascript
// Use the dsh_install_plugin tool
await mcp.dsh_mcp.dsh_install_plugin({
  profile: "headless",
  package: "@deepseek-ai/dsh-some-plugin"
});
```

## Integration with opencode Agents

This skill works with all opencode agents. The dsh-mcp tools are available to any agent that has MCP access.

### Recommended Agent: `9router-coder`
For coding tasks using dsh capabilities:
```
opencode run --agent 9router-coder "Use dsh to analyze the codebase"
```

### Recommended Agent: `9router-researcher`
For research tasks using dsh:
```
opencode run --agent 9router-researcher "Use dsh headless to research this topic"
```

## Configuration

The MCP server is configured in `opencode.jsonc`:
```json
"dsh-mcp": {
  "type": "local",
  "command": ["node", "{env:USERPROFILE}/.config/opencode/mcps/dsh-mcp/index.js"],
  "environment": {
    "PATH": "{env:PATH}"
  },
  "enabled": true
}
```

## DeepSeek Harness Profiles

| Profile | Use Case |
|---------|----------|
| `headless` | One-shot tasks, automation, CI/CD |
| `web` | Web UI at http://127.0.0.1:3080 |
| `tui` | Terminal UI for interactive use |
| `rescue` | Recovery/profile repair |
| `desktop` | Electron desktop app |

## Notes

- DeepSeek Harness must be built: `pnpm run build:artifacts` in the dsh directory
- The MCP server wraps `pnpm dsh` commands
- Requires Node.js and pnpm in PATH
- The dsh installation is typically at `%TEMP%/opencode/deepseek-harness`
- For persistent dsh home, set `DSH_HOME` environment variable

## Related Skills

- `codebase-memory` - Use graph tools before running dsh tasks
- `agro-build-cirurgico` - For agro ERP/app building with dsh
- `reverse-skill` - For reverse engineering tasks with dsh