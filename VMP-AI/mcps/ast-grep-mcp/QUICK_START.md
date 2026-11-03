# Quick Start

Manual commands for the two entry points: `main.py` (MCP server) and `analyze_codebase.py` (standalone CLI analyzer).

## Setup

```bash
uv sync                          # Install dependencies (Python 3.13+, uv required)
ast-grep --version               # Verify ast-grep CLI is installed (required)
```

## Entry Point 1: `main.py` — MCP Server

Serves all 59 tools (search, rewrite, refactoring, deduplication, Schema.org, complexity, quality, documentation, cross-language, condense) over the Model Context Protocol.

```bash
uv run main.py                   # Run the MCP server locally (stdio)
doppler run -- uv run main.py    # Run with Doppler-managed secrets (SENTRY_DSN, etc.)
```

Configure via environment variables (auto-read by pydantic-settings):

```bash
LOG_LEVEL=DEBUG uv run main.py
CACHE_DISABLED=1 uv run main.py
```

Register with a Claude Code / MCP client (`.mcp.json`):

```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "uv",
      "args": ["run", "main.py"],
      "cwd": "/path/to/ast-grep-mcp"
    }
  }
}
```

### Invoking server functionality without an MCP client

Tool implementations are importable directly:

```bash
# Structural search
uv run python -c "
from ast_grep_mcp.features.search.service import find_code_impl
print(find_code_impl(project_folder='src/ast_grep_mcp', pattern='def \$NAME(\$\$\$)', language='python', max_results=5))
"

# Complexity analysis
uv run python -c "
from ast_grep_mcp.features.complexity.tools import analyze_complexity_tool
r = analyze_complexity_tool('src/ast_grep_mcp', language='python')
print(r['summary'])
"

# Duplication detection
uv run python -c "
from ast_grep_mcp.features.deduplication.tools import find_duplication_tool
r = find_duplication_tool('src/ast_grep_mcp', 'python', min_similarity=0.8, min_lines=5)
print(r['summary'])
"
```

Note: quality/complexity tools (`analyze_complexity`, `detect_code_smells`, `detect_security_issues`) require the `language` argument. Most tool handlers are synchronous — call them directly, do not wrap in `asyncio.run()`.

## Entry Point 2: `analyze_codebase.py` — CLI Analyzer

One-shot batch analysis of a codebase: complexity, code smells, duplication candidates, security issues, and standards violations, using the same feature modules the server exposes.

```bash
uv run python analyze_codebase.py                        # Analyze src/ast_grep_mcp (python)
uv run python analyze_codebase.py path/to/project        # Analyze another folder
uv run python analyze_codebase.py path/to/project -l typescript
uv run python analyze_codebase.py path/to/project --fix  # Apply safe auto-fixes for standards violations
```

Options:

| Flag | Meaning | Default |
|------|---------|---------|
| `project_folder` | Folder to analyze | `src/ast_grep_mcp` |
| `-l, --language` | Source language | `python` |
| `--fix` | Apply safe standards auto-fixes | off |

Supported languages: python, javascript, typescript, tsx, html, css, json, yaml, rust, go, java, kotlin, c, cpp, csharp, swift, ruby, lua, scala.

Full analysis suite (wraps additional scripts):

```bash
uv run python scripts/run_all_analysis.py [src_path]
```

## Verifying Changes

```bash
uv run pytest                            # Full test suite
uv run ruff check . && uv run mypy src/  # Lint + type check
```

## Which Entry Point Do I Want?

- **Interactive tool access from an MCP client (Claude Code, etc.)** → `main.py`
- **One-shot report or auto-fix pass over a codebase from the terminal** → `analyze_codebase.py`

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for all environment variables and [CLAUDE.md](CLAUDE.md) for tool import patterns and response field names.
