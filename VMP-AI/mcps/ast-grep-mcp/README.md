# ast-grep MCP Server

A Model Context Protocol (MCP) server providing structural code search, refactoring, and quality analysis using [ast-grep](https://ast-grep.github.io/).

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-package%20manager-green.svg)](https://github.com/astral-sh/uv)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple.svg)](https://modelcontextprotocol.io/)

## Features

- **Code Search** - Pattern and YAML rule-based structural search, AST visualization, pattern debugging
- **Code Transformation** - Safe rewrites with backup/rollback, dry-run preview, syntax validation
- **Refactoring** - Extract function with parameter detection, scope-aware rename with conflict detection
- **Deduplication** - Duplicate detection via MinHash/LSH, ranked candidates, automated refactoring with impact analysis
- **Complexity Analysis** - Cyclomatic, cognitive, nesting metrics; code smell detection
- **Code Quality** - 24+ linting templates (pattern and kind-based), custom rules, security scanning, auto-fix, standards enforcement
- **Documentation** - Docstring generation (Google/NumPy/JSDoc), README sections, OpenAPI specs, changelog, doc sync
- **Cross-Language** - Multi-language search, pattern equivalents, code conversion, polyglot refactoring, binding generation
- **Schema.org** - Type search, property listing, JSON-LD validation, template generation, entity graph enhancement
- **Code Condensation** - Semantic surface extraction, normalization, dead code stripping, token-aware packing, zstd dictionary training

## Architecture

```
src/ast_grep_mcp/          # 126 modules
├── core/                  # Config, cache, executor, logging, sentry, usage tracking
├── models/                # Data models (14 modules)
├── utils/                 # Formatters, validation, templates, text processing
├── features/
│   ├── search/            # 9 tools  — find_code, find_code_by_rule, dump_ast, debug_pattern, etc.
│   ├── rewrite/           # 5 tools  — rewrite_code, rollback_rewrite, list_backups, zod rule lookup/browse
│   ├── refactoring/       # 2 tools  — extract_function, rename_symbol
│   ├── deduplication/     # 6 tools  — find_duplication, analyze/apply/benchmark, AST/semantic similarity
│   ├── complexity/        # 3 tools  — analyze_complexity, test_sentry_integration, detect_code_smells
│   ├── quality/           # 7 tools  — linting, security scanner, auto-fix, reports
│   ├── documentation/     # 5 tools  — docstrings, readme, api_docs, changelog, sync
│   ├── cross_language/    # 5 tools  — multi-lang search, equivalents, conversion, refactoring, bindings
│   ├── schema/            # 11 tools — type search, properties, validation, templates, entity graph
│   └── condense/          # 6 tools  — surface extraction, normalization, strip, pack, estimate, dictionary
└── server/                # MCP registry + runner
```

**59 MCP tools** | **1,849 tests collected** | **Quality gates: Ruff + mypy + pytest + analyzer pipeline**

## Quick Start

### Prerequisites

- **Python 3.13+**
- **[uv](https://github.com/astral-sh/uv)** - Python package manager
- **[ast-grep](https://ast-grep.github.io/guide/quick-start.html)** - Structural code search

```bash
# Install ast-grep (any one of these)
brew install ast-grep          # macOS
npm install -g @ast-grep/cli   # npm
cargo install ast-grep         # cargo
```

### Install & Run

```bash
git clone https://github.com/aledlie/ast-grep-mcp.git
cd ast-grep-mcp
uv sync
uv run pytest                  # verify
uv run main.py                 # start server
```

### MCP Client Configuration

Add to your MCP client config (e.g., Claude Desktop):

**With Doppler:**
```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "doppler",
      "args": [
        "run", "--project", "bottleneck", "--config", "dev", "--command",
        "uv --directory /absolute/path/to/ast-grep-mcp run main.py"
      ]
    }
  }
}
```

**Without Doppler:**
```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/ast-grep-mcp", "run", "main.py"]
    }
  }
}
```

## Usage Examples

### Code Search

```python
# Pattern search
find_code(pattern="console.log($$$)", project_folder="/path/to/project", language="typescript")

# YAML rule search
find_code_by_rule(
    rule_yaml="rule:\n  pattern: $FUNC($$$)\n  constraints:\n    FUNC:\n      regex: ^(eval|exec)$",
    project_folder="/path/to/project",
    language="python"
)
```

### Code Transformation

```python
# Dry-run preview with YAML rule
rewrite_code(
    project_folder="/path",
    yaml_rule="rule:\n  pattern: var $VAR = $VALUE\n  language: javascript\nfix: const $VAR = $VALUE",
    dry_run=True
)

# Apply with automatic backup
rewrite_code(
    project_folder="/path",
    yaml_rule="rule:\n  pattern: var $VAR = $VALUE\n  language: javascript\nfix: const $VAR = $VALUE",
    dry_run=False
)

# Rollback if needed
rollback_rewrite(backup_id="backup-20251124-103045", project_folder="/path")
```

### Deduplication

```python
find_duplication(project_folder="/path", language="python", min_lines=5)
analyze_deduplication_candidates(project_path="/path", language="python", max_candidates=10)
apply_deduplication(candidate_id="dup-001", refactoring_strategy="extract_function", dry_run=True)
```

### Complexity & Quality

```python
analyze_complexity(project_folder="/path", language="python", cyclomatic_threshold=10)
detect_code_smells(project_folder="/path", language="python", severity_filter="high")
create_linting_rule(rule_name="no-console-log", pattern="console.log($$$)",
                    severity="warning", language="typescript", save_to_project=True)
```

## Configuration

| Variable | Description |
|----------|-------------|
| `AST_GREP_CONFIG` | Path to ast-grep config file |
| `LOG_LEVEL` | Logging level (default: INFO) |
| `SENTRY_DSN` | Sentry error tracking DSN |
| `SENTRY_ENVIRONMENT` | Sentry environment name |
| `CACHE_DISABLED` | Disable result caching |
| `CACHE_SIZE` / `CACHE_TTL` | Cache size and TTL |

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for details.

## Development

```bash
uv run pytest                              # all tests
uv run pytest tests/unit/ -v               # unit tests
uv run pytest tests/quality/ -v            # complexity regression tests
uv run pytest --cov=src/ast_grep_mcp       # with coverage
uv run ruff check . && uv run ruff format --check .  # lint + format
uv run mypy src/                           # type check
uv run python analyze_codebase.py <path> -l <lang>        # codebase analysis
uv run python analyze_codebase.py <path> -l <lang> --fix  # analysis + auto-fix
```

### Quality Reports

Standalone scripts for code smells, complexity, and orphan detection:

```bash
uv run python scripts/reports/code_smells.py [project] [-l lang] [--extended] [--json]
uv run python scripts/reports/complexity.py  [project] [-l lang] [-n top] [--extended] [--json]
uv run python scripts/reports/orphans.py     [project] [--extended] [--files-only] [--functions-only] [--json]
```

All default to the current project with `python` language. Use `--extended` for full detail, `--json` for machine-readable output.

### Adding Features

1. Create `src/ast_grep_mcp/features/<name>/` with `service.py` and `tools.py`
2. Register tools in `server/registry.py`
3. Add tests in `tests/unit/`

## Documentation

- [CLAUDE.md](CLAUDE.md) - Project instructions
- [docs/CHANGELOG.md](docs/CHANGELOG.md) - Version history
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) - Configuration options
- [docs/PATTERNS.md](docs/PATTERNS.md) - Refactoring patterns
- [docs/DEDUPLICATION-GUIDE.md](docs/DEDUPLICATION-GUIDE.md) - Deduplication workflow
- [docs/BENCHMARKING.md](docs/BENCHMARKING.md) - Performance benchmarking
- [docs/SENTRY-INTEGRATION.md](docs/SENTRY-INTEGRATION.md) - Error tracking
- [docs/CODE-CONDENSE-PHASE-2.md](docs/CODE-CONDENSE-PHASE-2.md) - Condense phase 2 design
- [docs/BACKLOG.md](docs/BACKLOG.md) - Open backlog items
- [docs/KNOWN_ISSUES.md](docs/KNOWN_ISSUES.md) - Known issues and workarounds
- [docs/BACKFILLING.md](docs/BACKFILLING.md) - OTEL telemetry backfilling for skills

## Acknowledgments

- [ast-grep](https://ast-grep.github.io/) - Structural code search engine
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
- [FastMCP](https://github.com/jlowin/fastmcp) - Python MCP framework
- [Schema.org](https://schema.org/) - Structured data vocabulary
