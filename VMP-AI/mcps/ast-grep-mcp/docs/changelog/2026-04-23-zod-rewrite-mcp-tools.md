# Zod Rewrite MCP Tools (2026-04-23)

## Summary

Exposed `zod_templates.py` registry as two new MCP tools, bringing the public tool count from 55 → 57. Previously the module was unreachable (orphan file) and callers had to either inline full YAML rules or read `rules/*.yaml` files from disk.

**Status**: ✅ Complete
**Breaking Changes**: None

## New Tools

- `get_zod_rewrite_rule(rule_id)` — returns `{rule_id, yaml_rule}` ready to pass to `rewrite_code()`.
- `list_zod_rewrite_rules(category)` — lists rule IDs by `'schema'`, `'import'`, or `'all'`.

## Usage

```
rule = get_zod_rewrite_rule(rule_id="no-any-schema")
rewrite_code(project_folder="/path/to/project", yaml_rule=rule["yaml_rule"], dry_run=True)
```

Available rule IDs: 9 schema rules (e.g., `no-any-schema`, `require-schema-suffix`, `prefer-enum-over-literal-union`) and 5 import rules (e.g., `import-zod-named-to-namespace`). See `list_zod_rewrite_rules(category="all")` for the full set.

## Files Touched

- `src/ast_grep_mcp/features/rewrite/tools.py` — registered `_register_get_zod_rule` and `_register_list_zod_rules`.
- `docs/ZOD-REWRITE-GUIDE.md` — added MCP-tool usage section.
- `CLAUDE.md` — documented new tools under Public API; updated tool count (55 → 57, Rewrite 3 → 5).

## Context

Discovered via `scripts/benchmark_orphan_detector.py` run against `src/`, which flagged `zod_templates.py` with zero internal references despite defining a complete rule registry that duplicated the YAML files in `rules/`. Wiring it as MCP tools gives agents a stable, named API without re-reading YAML files on every call.
