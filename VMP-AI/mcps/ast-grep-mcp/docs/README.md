# ast-grep + Schema.org MCP Server

MCP server combining [ast-grep](https://ast-grep.github.io/) structural code search with Schema.org structured data tools for AI assistants (Cursor, Claude Desktop, etc.).

## Overview

**Code Search (ast-grep):** AST-based pattern matching, code construct search, duplication detection, YAML rules, syntax tree debugging

**Structured Data (Schema.org):** Query 2600+ types/properties, search by keyword, explore hierarchies, generate JSON-LD examples, build knowledge graphs

## Quick Start

```bash
# Install prerequisites
brew install ast-grep  # or: cargo install ast-grep --locked
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/aledlie/ast-grep-mcp.git
cd ast-grep-mcp
uv sync

# Run directly from GitHub (no clone)
uvx --from git+https://github.com/aledlie/ast-grep-mcp ast-grep-server
```

## Configuration

Add to `.cursor-mcp/settings.json` or `~/Library/Application Support/Claude/claude_desktop_config.json`:

**With Doppler (recommended for production):**
```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "doppler",
      "args": ["run", "--project", "bottleneck", "--config", "dev", "--command",
               "uv --directory /path/to/ast-grep-mcp run main.py"]
    }
  }
}
```

**Without Doppler (local development):**
```json
{
  "mcpServers": {
    "ast-grep": {
      "command": "uv",
      "args": ["--directory", "/path/to/ast-grep-mcp", "run", "main.py"],
      "env": {
        "SENTRY_DSN": "optional-for-error-tracking",
        "SENTRY_ENVIRONMENT": "production"
      }
    }
  }
}
```

**Custom ast-grep config:** Use `--config /path/to/sgconfig.yaml` or `AST_GREP_CONFIG` env var. See [ast-grep config docs](https://ast-grep.github.io/guide/project/project-config.html).

**Rule writing guide:** See [ast-grep.mdc](https://github.com/aledlie/ast-grep-mcp/blob/main/ast-grep.mdc) for comprehensive rule patterns.

## Error Tracking (Optional)

**Sentry integration** (optional, zero overhead when disabled) provides:
- Error tracking for all 55 tools
- Performance monitoring (subprocess, API, batch operations)
- AI interaction tracking (with Anthropic SDK)
- Service tagging: `service:ast-grep-mcp`

**Setup:**
```bash
# With Doppler (recommended)
brew install dopplerhq/cli/doppler
doppler login
doppler secrets set SENTRY_DSN="your-dsn" --project bottleneck --config dev

# Manual
export SENTRY_DSN="your-dsn"
export SENTRY_ENVIRONMENT="production"
```

**Docs:** [SENTRY-INTEGRATION.md](SENTRY-INTEGRATION.md)

## Tools (55 Total)

| Feature | Count | Tools |
|---------|-------|-------|
| Search | 9 | find_code, find_code_by_rule, dump_syntax_tree, test_match_code_rule, debug_pattern, develop_pattern, get_ast_grep_docs, build_rule, get_pattern_examples |
| Rewrite | 3 | rewrite_code, rollback_rewrite, list_backups |
| Refactoring | 2 | extract_function, rename_symbol |
| Deduplication | 6 | find_duplication, analyze_deduplication_candidates, apply_deduplication, benchmark_deduplication, calculate_ast_similarity, calculate_semantic_similarity |
| Complexity | 3 | analyze_complexity, test_sentry_integration, detect_code_smells |
| Quality | 7 | create_linting_rule, list_linting_rules, apply_linting_rule, detect_security_issues, apply_standards_fixes, generate_quality_report, enforce_code_standards |
| Documentation | 5 | generate_docstrings, generate_readme_sections, generate_api_docs, generate_changelog, sync_documentation |
| Cross-Language | 5 | search_multi_language, find_language_equivalents, convert_code_language, refactor_polyglot, generate_language_bindings |
| Schema.org | 11 | get_schema_type, search_schemas, get_type_hierarchy, get_type_properties, generate_schema_example, generate_entity_id, validate_entity_id, build_entity_graph, enhance_entity_graph, detect_structured_data, validate_structured_data |
| Condense | 6 | condense_extract_surface, condense_normalize, condense_strip, condense_pack, condense_estimate, condense_train_dictionary |


## Usage Examples

**Pattern search:**
```yaml
# Find console.log statements
pattern: console.log($$$)
```

**Complex rules:**
```yaml
# Find async functions with await
all:
  - kind: function_declaration
  - has: { pattern: async }
  - has: { pattern: await $EXPR, stopBy: end }
```

**Duplication detection:**
```python
find_duplication(project_folder="/path", language="python",
                 construct_type="function_definition", min_similarity=0.8)
# Returns: summary stats, duplicate groups, refactoring suggestions
```

**Schema.org workflow:**
```python
search_schemas('blog')              # Find BlogPosting
get_type_properties('BlogPosting')  # List properties
generate_schema_example('BlogPosting', {'headline': '...', 'author': {...}})
# Returns: Complete JSON-LD markup
```

**Knowledge graph:**
```python
generate_entity_id('https://example.com', 'Organization')  # Generate @id
validate_entity_id('https://example.com/#organization')    # Validate
build_entity_graph([...], 'https://example.com')          # Build @graph
# Returns: Multi-entity JSON-LD with proper @id references
```

## Supported Languages

JavaScript/TypeScript, Python, Rust, Go, Java, C/C++, C#, and [many more](https://ast-grep.github.io/reference/languages.html). Add custom languages via `sgconfig.yaml` ([guide](https://ast-grep.github.io/guide/project/project-config.html#languagecustomlanguage)).

## Troubleshooting

**Common:**
- Command not found: Ensure `ast-grep` in PATH
- No matches: Add `stopBy: end` to relational rules
- Pattern issues: Use `dump_syntax_tree` to debug

**Sentry:** Run `test_sentry_integration()`, check `SENTRY_DSN`. See [SENTRY-INTEGRATION.md](SENTRY-INTEGRATION.md).

**Doppler:** Verify auth (`doppler login`) and secrets (`doppler secrets --project bottleneck --config dev`).

## Repository

```
src/ast_grep_mcp/          # 125 modules
├── core/                  # Config, cache, executor, logging, sentry, usage tracking
├── models/                # Data models (13 modules)
├── utils/                 # Formatters, validation, templates, text processing
├── features/              # 10 feature modules (search, rewrite, refactoring, deduplication,
│                          #   complexity, quality, documentation, cross_language, schema, condense)
└── server/                # MCP registry + runner
```

- `tests/` - 1,807 collected tests (unit + integration + quality regression)

## Recent Updates

- [changelog/2026-03-08-deduplication-precision-filters.md](changelog/2026-03-08-deduplication-precision-filters.md) - 5 false-positive group filters, constants + regex refactor, 32 tests.
- [changelog/2026-03-08-backup-refactoring-helper-adoption.md](changelog/2026-03-08-backup-refactoring-helper-adoption.md) - Shared backup utils, applicator_backup complexity reduction, tool_context adoption.
- [changelog/2026-03-08-shared-utils-consolidation.md](changelog/2026-03-08-shared-utils-consolidation.md) - Shared utility extractions, tool_context, normalize_excludes.
- [changelog/2026-03-08-review-follow-ups-testing.md](changelog/2026-03-08-review-follow-ups-testing.md) - Sentry exception capture, logger parameter deduplication.
- [changelog/2026-03-08-code-review-findings.md](changelog/2026-03-08-code-review-findings.md) - 4 code review items resolved.

## Related

- [ast-grep](https://ast-grep.github.io/) - Core search tool
- [Schema.org](https://schema.org/) - Structured data vocabulary
- [MCP](https://modelcontextprotocol.io/) - Protocol specification
- [FastMCP](https://github.com/pydantic/fastmcp) - Python framework

[![Security Assessment](https://mseep.net/pr/ast-grep-ast-grep-mcp-badge.png)](https://mseep.ai/app/ast-grep-ast-grep-mcp)
