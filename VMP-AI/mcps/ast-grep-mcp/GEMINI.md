# Gemini CLI - Project Context: ast-grep-mcp

This file provides critical context and instructions for AI agents (like Gemini) working on the `ast-grep-mcp` project.

## Project Overview

**ast-grep-mcp** is a high-performance Model Context Protocol (MCP) server that provides structural code search, refactoring, and quality analysis capabilities using [ast-grep](https://ast-grep.github.io/).

- **Architecture:** Modular design with 126 modules.
- **Key Features:**
    - **Structural Search:** Pattern and YAML rule-based search across 15+ languages.
    - **Refactoring:** Safe rewrites, extract function, and scope-aware rename.
    - **Code Quality:** Complexity analysis, deduplication (MinHash/LSH), and linting (24+ templates).
    - **Documentation:** Automated docstring and README generation, OpenAPI sync.
    - **Semantic Analysis:** Code condensation and semantic similarity (Phase 5).
- **Primary Tech Stack:** Python 3.13+, `uv` (package manager), `ast-grep` (core engine), `FastMCP`.

## Directory Structure

```
src/ast_grep_mcp/
├── core/           # Infrastructure: Config, cache, executor, logging, sentry
├── models/         # Pydantic data models for tools and internal logic
├── utils/          # Shared utilities: Formatters, validation, text processing
├── features/       # 59 MCP tools organized by domain
│   ├── search/     # Code search & pattern debugging
│   ├── rewrite/    # Safe code transformations & rollbacks
│   ├── refactoring/# Extract function, rename symbol
│   ├── quality/    # Linting, security scanning, auto-fix
│   └── ...         # deduplication, complexity, documentation, schema, condense
└── server/         # MCP registry and runner
```

## Building and Running

### Prerequisites
- **Python 3.13+**
- **uv** (Python package manager)
- **ast-grep CLI** (installed via brew, npm, or cargo)

### Key Commands
- **Install Dependencies:** `uv sync`
- **Run Server Locally:** `uv run main.py`
- **Run Tests:** `uv run pytest` (Run all 1,849 tests)
- **Linting:** `uv run ruff check .`
- **Type Checking:** `uv run mypy src/`
- **Complexity Check:** `uv run pytest tests/quality/test_complexity_regression.py -v`

## Development Conventions

### 1. Tool Implementation
- **Synchronous by Default:** MCP tool functions are synchronous — call them directly, do NOT wrap in `asyncio.run()`. Exceptions: schema tools in `features/schema/tools.py` are `async def`, as is `async_stream_ast_grep_results()` in `core/executor.py`.
- **Registration:** Register new tools in `src/ast_grep_mcp/server/registry.py` and their respective `features/<name>/tools.py`.
- **Parameter Validation:** Use Pydantic `Field` for tool parameters to provide descriptions for LLM clients.

### 2. Code Quality Standards (Strict)
The project enforces "Zero Complexity Violations":
- **Cyclomatic Complexity:** ≤ 20
- **Cognitive Complexity:** ≤ 30
- **Nesting Depth:** ≤ 6
- **Function Length:** ≤ 150 lines
*Note: Any PR exceeding these limits will fail regression tests.*

### 3. ast-grep Patterns & Rules
- **Metavariables:** Must be UPPERCASE (e.g., `$NAME`, `$$$ARGS`).
- **Relational Rules:** Always use `stopBy: end` for `inside`, `has`, `follows`, or `precedes` unless immediate adjacency is explicitly required.
- **YAML Rules:** Must include `id`, `language`, and `rule` fields.

### 4. Testing
- **Fast Feedback:** Unit tests should use mocks (see `tests/unit/conftest.py`).
- **Integration:** Integration tests (`tests/integration/`) require the `ast-grep` binary.
- **Fixtures:** Use existing factories in `tests/unit/conftest.py` (e.g., `match_factory`, `yaml_rule_factory`).

### 5. Error Handling & Logging
- Use `structlog` for structured logging.
- Use the central `Executor` in `core/` for running shell commands.
- Ensure all file operations are backed up when performing rewrites (use the `rewrite` feature's infrastructure).

## Key Files for Reference
- `CLAUDE.md`: High-level summary and quick start (used by Claude/Cursor). **Source of truth** for tool/module/test counts, tool response field names, and public-API-vs-internals guidance — if this file disagrees with CLAUDE.md, trust CLAUDE.md.
- `README.md`: Comprehensive project overview and usage examples.
- `pyproject.toml`: Dependency and tool configuration.
- `src/ast_grep_mcp/server/registry.py`: Central list of all available tools.
