# 2026-01-09: Pattern Debugging Tool

## Added

- `debug_pattern` tool for diagnosing why patterns don't match code
- Validates metavariable syntax (detects `$name` vs `$NAME`, `$123`, `$KEBAB-CASE` errors)
- Compares pattern AST with code AST to find structural mismatches
- Prioritized suggestions for fixing pattern issues
- New models: `pattern_debug.py` with 8 dataclasses/enums
- 31 new tests for pattern debugging
- Total MCP tools: 43

## Fixed

- Resolved 6 complexity violations in deduplication module (9bdd029)
- Resolved all lint errors (55de598)
