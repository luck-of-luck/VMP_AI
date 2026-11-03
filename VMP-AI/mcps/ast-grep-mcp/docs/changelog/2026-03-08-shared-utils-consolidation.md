# 2026-03-08: Shared Utils & Tool Consolidation

## Summary

Major refactoring pass to extract shared utilities, consolidate error handling patterns, and reduce complexity across hotspot files. 23 commits from `1b5f331` through `a5c7879`.

## Changes

### Shared Utility Extractions

- **`utils/tool_context.py`** — extracted `tool_context` context manager (timing + error logging + Sentry capture) from `quality/tools.py`. Adopted by `complexity/tools.py` and all 6 `condense/tools.py` tool functions. 8 unit tests added.
- **`FilePatterns.normalize_excludes()`** — new classmethod on `constants.py:FilePatterns`. Consolidates all `_normalize_exclude_patterns` functions across quality, complexity, deduplication, and documentation tools.
- **`indent_lines`, `read_file_lines`, `write_file_lines`** promoted from `deduplication/generator.py` and `documentation/docstring_generator.py` to shared `utils/`.

### Tool Registration Consolidation

- Replaced `_create_mcp_field_definitions` and field-dict indirection with inline `Field()` across cross_language, documentation, and quality tool registrations.

### Complexity Reductions

- **`deduplication/applicator_executor.py`** (cog 33 -> 16) — extracted `_create_single_file`, `_update_single_file`, `_apply_import_addition`.
- **`documentation/changelog_generator.py`** (cog 30 -> 18) — extracted `_get_commits`, `_group_commits_by_version`, `_format_changelog_entry`. Hardened with `str | None` types.
- **`refactoring/extractor.py`** — decomposed `_generate_docstring`, `_generate_function_body`, and `_scan_imports` via `FunctionExtractor` helper methods.
- **`deduplication/detector.py`** — extracted `_match_line`, `_format_instance`; moved strategy tables to class-level constants.
- **`refactoring/analyzer.py`** — keyword sets to class-level frozensets; extracted `_register_variable` and `_scan_and_register_identifiers`.

### Other

- Added `review` skill for diff-aware code review.
- Added OTEL telemetry backfill script and docs.
- Reorganized repomix scripts into `scripts/repomix/` subdirectory.
- Removed unused performance monitoring module.
- Fixed flaky cache benchmark assertions (ratio -> absolute ceiling).

## Stats

- 1,622 tests collected (up from 1,598)
- Complexity baseline: 434 -> 80 remaining violations
