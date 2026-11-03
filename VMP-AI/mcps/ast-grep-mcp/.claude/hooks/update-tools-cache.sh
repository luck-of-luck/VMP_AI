#!/bin/bash
# Hook: update-tools-cache.sh
# Event: PostToolUse (Bash with git commit)
# Purpose: Detect when tool files are modified and prompt for cache update

set -euo pipefail

# Read input from stdin
INPUT=$(cat)

# Only process Bash tool calls
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
if [[ "$TOOL_NAME" != "Bash" ]]; then
    exit 0
fi

# Get the command that was executed
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

# Only check git commit commands
if [[ ! "$COMMAND" =~ ^git\ commit ]]; then
    exit 0
fi

# Get the current working directory from input or use PWD
WORKING_DIR=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
if [[ -z "$WORKING_DIR" ]]; then
    WORKING_DIR="$PWD"
fi

# Check if we're in the ast-grep-mcp project
if [[ ! "$WORKING_DIR" =~ ast-grep-mcp ]]; then
    exit 0
fi

# Navigate to the project root
cd "$WORKING_DIR"

# Check if any tool files were modified in the last commit
TOOL_FILES_CHANGED=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null | grep -E 'src/ast_grep_mcp/features/.*/tools\.py$' || true)

if [[ -n "$TOOL_FILES_CHANGED" ]]; then
    # Output reminder to update cache
    cat << 'EOF'
{
  "result": "continue",
  "message": "Tool files were modified in this commit. Consider updating the MCP tools cache at .claude/cache/mcp-tools.md"
}
EOF
else
    echo '{"result": "continue"}'
fi
