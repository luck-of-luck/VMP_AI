# List MCP Tools

Display the cached list of all MCP tools available in this ast-grep-mcp server.

## Instructions

Read and display the cached tool list from `.claude/cache/mcp-tools.md`.

This cache is automatically updated by a PostToolUse hook when commits modify tool files in:
- `src/ast_grep_mcp/features/*/tools.py`

If the cache appears stale, you can regenerate it by reading the tool source files directly.

## Cache Location

```
.claude/cache/mcp-tools.md
```

## Output

Display the contents of the cached tool list file.
