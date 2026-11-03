#!/usr/bin/env python3
"""Run all 53 ast-grep-mcp tools against ~/.claude/hooks."""

import asyncio
import json
import sys
import time
from pathlib import Path

from tool_result_recorder import record_tool_result

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

TARGET = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / ".claude" / "hooks")
LANG = sys.argv[2] if len(sys.argv) > 2 else "typescript"

results: dict[str, dict] = {}

# Extensions considered "config-only" (non-executable, no function definitions)
# Note: dotfiles like .env have no suffix via Path.suffix and are handled separately
_CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cjs"}
_CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".rs", ".go", ".java", ".rb", ".cs"}
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}
_MAX_DISPLAY_EXTS = 8

# Known language mappings for auto-suggestion
# .jsx maps to javascript — ast-grep does not have a separate "jsx" language
_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}


def _detect_target_info(target: str) -> dict:
    """Scan target directory and return extension counts and language recommendations.

    Returns dict with keys:
        ext_counts: {ext: count} for all found extensions
        code_ext_counts: {ext: count} for code-only extensions
        config_ext_counts: {ext: count} for config-only extensions
        is_config_only: True if no code extensions were found
        recommended_langs: list of suggested languages to pass
        warnings: list of warning strings to print
    """
    ext_counts: dict[str, int] = {}
    target_path = Path(target)

    if not target_path.exists():
        return {
            "ext_counts": {},
            "code_ext_counts": {},
            "config_ext_counts": {},
            "is_config_only": False,
            "recommended_langs": [LANG],
            "warnings": [f"Target directory not found: {target}"],
        }

    for p in target_path.rglob("*"):
        if p.is_file() and not any(part in _SKIP_DIRS for part in p.relative_to(target_path).parts):
            ext = p.suffix.lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1

    code_ext_counts = {e: c for e, c in ext_counts.items() if e in _CODE_EXTS}
    config_ext_counts = {e: c for e, c in ext_counts.items() if e in _CONFIG_EXTS}
    is_config_only = bool(config_ext_counts) and not bool(code_ext_counts)

    # Build language recommendations from detected extensions
    recommended_langs = sorted({_EXT_TO_LANG[e] for e in ext_counts if e in _EXT_TO_LANG})
    if not recommended_langs:
        recommended_langs = [LANG]

    warnings = []
    if not ext_counts:
        warnings.append("WARNING: No files with recognized extensions found in target directory.")
    elif is_config_only:
        warnings.append("WARNING: Target appears to contain config files only (no .py/.ts/.js/etc found).")
        warnings.append("  Function-oriented patterns (function $NAME, class $C) will return 0 matches.")
        warnings.append("  See docs/CONFIG_PATTERNS.md for patterns that work against config formats.")
        if config_ext_counts:
            suggestions = ", ".join(f"{_EXT_TO_LANG[e]} (for {e})" for e in sorted(config_ext_counts) if e in _EXT_TO_LANG)
            if suggestions:
                warnings.append(f"  Suggested languages: {suggestions}")

    return {
        "ext_counts": ext_counts,
        "code_ext_counts": code_ext_counts,
        "config_ext_counts": config_ext_counts,
        "is_config_only": is_config_only,
        "recommended_langs": recommended_langs,
        "warnings": warnings,
    }


def record(name: str, result=None, error=None, skipped=None):
    record_tool_result(results, name, result=result, error=error, skipped=skipped)


def run_sync_tools():
    # File extension mapping for target language
    _exts = {"typescript": "*.ts", "javascript": "*.cjs", "python": "*.py"}
    _glob = _exts.get(LANG, "*.ts")

    # ── Search tools ──
    from ast_grep_mcp.features.search.docs import get_docs, get_pattern_examples
    from ast_grep_mcp.features.search.service import (
        build_rule_impl,
        debug_pattern_impl,
        develop_pattern_impl,
        dump_syntax_tree_impl,
        find_code_by_rule_impl,
        find_code_impl,
    )

    sample_code = (
        "function hello(name: string) { console.log(`Hello ${name}`); }"
        if LANG == "typescript"
        else "function hello(name) { console.log(`Hello ${name}`); }"
    )

    try:
        r = dump_syntax_tree_impl(code=sample_code, language=LANG)
        record("dump_syntax_tree", r)
    except Exception as e:
        record("dump_syntax_tree", error=e)

    try:
        r = find_code_impl(project_folder=TARGET, pattern="function $NAME($$$ARGS)", language=LANG)
        record("find_code", r)
    except Exception as e:
        record("find_code", error=e)

    try:
        if LANG == "javascript":
            yaml_rule = f"""
id: find-exports
language: {LANG}
rule:
  pattern: module.exports = $$$DECL
"""
        elif LANG == "python":
            yaml_rule = f"""
id: find-exports
language: {LANG}
rule:
  kind: import_from_statement
"""
        else:
            yaml_rule = f"""
id: find-exports
language: {LANG}
rule:
  kind: export_statement
"""
        r = find_code_by_rule_impl(project_folder=TARGET, yaml_rule=yaml_rule)
        record("find_code_by_rule", r)
    except Exception as e:
        record("find_code_by_rule", error=e)

    try:
        r = debug_pattern_impl(pattern="console.log($$$ARGS)", code=sample_code, language=LANG)
        record("debug_pattern", r)
    except Exception as e:
        record("debug_pattern", error=e)

    try:
        r = get_docs("all")
        record("get_ast_grep_docs", r)
    except Exception as e:
        record("get_ast_grep_docs", error=e)

    try:
        r = build_rule_impl(pattern="console.log($$$ARGS)", language=LANG)
        record("build_rule", r)
    except Exception as e:
        record("build_rule", error=e)

    try:
        r = get_pattern_examples(language=LANG)
        record("get_pattern_examples_tool", r)
    except Exception as e:
        record("get_pattern_examples_tool", error=e)

    try:
        r = develop_pattern_impl(code=sample_code, language=LANG, goal="find function declarations")
        record("develop_pattern", r)
    except Exception as e:
        record("develop_pattern", error=e)

    # test_match_code_rule - uses find_code_by_rule_impl with inline code
    try:
        yaml_rule = f"""
id: test-match
language: {LANG}
rule:
  pattern: console.log($$$ARGS)
"""
        from ast_grep_mcp.features.search.service import find_code_by_rule_impl as match_impl

        r = match_impl(project_folder=TARGET, yaml_rule=yaml_rule)
        record("test_match_code_rule", r)
    except Exception as e:
        record("test_match_code_rule", error=e)

    # ── Rewrite tools ──
    import shutil
    import tempfile

    from ast_grep_mcp.features.rewrite.service import list_backups_impl, rewrite_code_impl, rollback_rewrite_impl

    try:
        yaml_rule = f"""
id: dry-run-test
language: {LANG}
rule:
  pattern: console.log($$$ARGS)
fix: console.info($$$ARGS)
"""
        r = rewrite_code_impl(project_folder=TARGET, yaml_rule=yaml_rule, dry_run=True, backup=False)
        record("rewrite_code", r)
    except Exception as e:
        record("rewrite_code", error=e)

    try:
        r = list_backups_impl(project_folder=TARGET)
        record("list_backups", r)
    except Exception as e:
        record("list_backups", error=e)

    # Real rewrite + rollback on a temp copy to exercise the full cycle
    _rewrite_tmp = None
    try:
        _rewrite_tmp = tempfile.mkdtemp(prefix="ast-grep-rewrite-")
        # Copy a single .ts file to avoid modifying the real target
        _src_ts = next(Path(TARGET).rglob(_glob), None) or next(Path(TARGET).rglob("*.js"), None)
        if not _src_ts:
            raise FileNotFoundError("No .ts files found for rollback test")
        shutil.copy2(_src_ts, Path(_rewrite_tmp) / _src_ts.name)

        yaml_rule_live = f"""
id: rollback-test
language: {LANG}
rule:
  pattern: console.log($$$ARGS)
fix: console.info($$$ARGS)
"""
        rw = rewrite_code_impl(project_folder=_rewrite_tmp, yaml_rule=yaml_rule_live, dry_run=False, backup=True)
        bid = rw.get("backup_id")
        if bid:
            r = rollback_rewrite_impl(backup_id=bid, project_folder=_rewrite_tmp)
            record("rollback_rewrite", r)
        else:
            # No matches to rewrite — no backup created
            record("rollback_rewrite", skipped="Rewrite found no matches; no backup to rollback")
    except Exception as e:
        record("rollback_rewrite", error=e)
    finally:
        if _rewrite_tmp:
            shutil.rmtree(_rewrite_tmp, ignore_errors=True)

    # ── Refactoring tools ──
    from ast_grep_mcp.features.refactoring.tools import extract_function_tool, rename_symbol_tool

    # Find a source file to use
    ts_files = list(Path(TARGET).rglob(_glob)) or list(Path(TARGET).rglob("*.js"))
    if ts_files:
        ts_file = str(ts_files[0])
        try:
            r = extract_function_tool(
                project_folder=TARGET,
                file_path=ts_file,
                start_line=1,
                end_line=5,
                language=LANG,
            )
            record("extract_function", r)
        except Exception as e:
            record("extract_function", error=e)
    else:
        record("extract_function", skipped="No .ts files found")

    try:
        r = rename_symbol_tool(
            project_folder=TARGET,
            symbol_name="instrumentHook",
            new_name="instrumentHook",
            language=LANG,
            dry_run=True,
        )
        record("rename_symbol", r)
    except Exception as e:
        record("rename_symbol", error=e)

    # ── Deduplication tools ──
    from ast_grep_mcp.features.deduplication.tools import (
        analyze_deduplication_candidates_tool,
        apply_deduplication_tool,
        benchmark_deduplication_tool,
        find_duplication_tool,
    )

    _dedup_result = None
    try:
        _dedup_result = find_duplication_tool(project_folder=TARGET, language=LANG)
        record("find_duplication", _dedup_result)
    except Exception as e:
        record("find_duplication", error=e)

    try:
        r = analyze_deduplication_candidates_tool(project_path=TARGET, language=LANG)
        record("analyze_deduplication_candidates", r)
    except Exception as e:
        record("analyze_deduplication_candidates", error=e)

    try:
        r = benchmark_deduplication_tool(iterations=3, save_baseline=False, check_regression=False)
        record("benchmark_deduplication", r)
    except Exception as e:
        record("benchmark_deduplication", error=e)

    # apply_deduplication — use a real group from find_duplication, dry_run only
    try:
        groups = (_dedup_result or {}).get("duplication_groups", [])
        if not groups:
            record("apply_deduplication", skipped="No duplication groups found to apply")
        else:
            group = groups[0]
            gid = group.get("group_id", 0)
            plan = {"strategy": "extract_function", "function_name": "dedup_test", "dry_run": True}
            r = apply_deduplication_tool(
                project_folder=TARGET,
                group_id=gid,
                refactoring_plan=plan,
                dry_run=True,
                backup=False,
            )
            record("apply_deduplication", r)
    except Exception as e:
        record("apply_deduplication", error=e)

    # ── Complexity tools ──
    from ast_grep_mcp.features.complexity.tools import (
        analyze_complexity_tool,
        detect_code_smells_tool,
        test_sentry_integration_tool,
    )

    try:
        r = analyze_complexity_tool(project_folder=TARGET, language=LANG)
        record("analyze_complexity", r)
    except Exception as e:
        record("analyze_complexity", error=e)

    try:
        r = detect_code_smells_tool(project_folder=TARGET, language=LANG)
        record("detect_code_smells", r)
    except Exception as e:
        record("detect_code_smells", error=e)

    try:
        r = test_sentry_integration_tool(test_type="breadcrumb", message="ast-grep-mcp test")
        record("test_sentry_integration", r)
    except Exception as e:
        record("test_sentry_integration", error=e)

    # ── Quality tools ──
    from ast_grep_mcp.features.quality.tools import (
        create_linting_rule_tool,
        detect_orphans_tool,
        detect_security_issues_tool,
        enforce_standards_tool,
        generate_quality_report_tool,
        list_rule_templates_tool,
    )

    try:
        r = create_linting_rule_tool(
            rule_name="no-console-log",
            description="Disallow console.log",
            pattern="console.log($$$ARGS)",
            severity="warning",
            language=LANG,
        )
        record("create_linting_rule", r)
    except Exception as e:
        record("create_linting_rule", error=e)

    try:
        r = list_rule_templates_tool(language=LANG)
        record("list_rule_templates", r)
    except Exception as e:
        record("list_rule_templates", error=e)

    try:
        r = enforce_standards_tool(project_folder=TARGET, language=LANG)
        record("enforce_standards", r)
    except Exception as e:
        record("enforce_standards", error=e)

    # apply_standards_fixes needs real violations
    record("apply_standards_fixes", skipped="Requires violations list from enforce_standards")

    try:
        # generate_quality_report needs an enforcement_result
        enforcement = enforce_standards_tool(project_folder=TARGET, language=LANG)
        r = generate_quality_report_tool(enforcement_result=enforcement, project_name="claude-hooks")
        record("generate_quality_report", r)
    except Exception as e:
        record("generate_quality_report", error=e)

    try:
        r = detect_security_issues_tool(project_folder=TARGET, language=LANG)
        record("detect_security_issues", r)
    except Exception as e:
        record("detect_security_issues", error=e)

    try:
        r = detect_orphans_tool(project_folder=TARGET)
        record("detect_orphans", r)
    except Exception as e:
        record("detect_orphans", error=e)

    # ── Documentation tools ──
    from ast_grep_mcp.features.documentation.tools import (
        generate_api_docs_tool,
        generate_changelog_tool,
        generate_docstrings_tool,
        generate_readme_sections_tool,
        sync_documentation_tool,
    )

    try:
        _doc_pattern = f"**/{_glob}"
        r = generate_docstrings_tool(project_folder=TARGET, file_pattern=_doc_pattern, language=LANG, dry_run=True)
        record("generate_docstrings", r)
    except Exception as e:
        record("generate_docstrings", error=e)

    try:
        r = generate_readme_sections_tool(project_folder=TARGET, language=LANG)
        record("generate_readme_sections", r)
    except Exception as e:
        record("generate_readme_sections", error=e)

    try:
        r = generate_api_docs_tool(project_folder=TARGET, language=LANG)
        record("generate_api_docs", r)
    except Exception as e:
        record("generate_api_docs", error=e)

    try:
        r = generate_changelog_tool(project_folder=TARGET)
        record("generate_changelog", r)
    except Exception as e:
        record("generate_changelog", error=e)

    try:
        r = sync_documentation_tool(project_folder=TARGET, language=LANG, check_only=True)
        record("sync_documentation", r)
    except Exception as e:
        record("sync_documentation", error=e)

    # ── Cross-language tools ──
    from ast_grep_mcp.features.cross_language.tools import (
        convert_code_language_tool,
        find_language_equivalents_tool,
        generate_language_bindings_tool,
        refactor_polyglot_tool,
        search_multi_language_tool,
    )

    try:
        r = search_multi_language_tool(project_folder=TARGET, semantic_pattern="error handling")
        record("search_multi_language", r)
    except Exception as e:
        record("search_multi_language", error=e)

    try:
        r = find_language_equivalents_tool(pattern_description="try/catch error handling", source_language=LANG)
        record("find_language_equivalents", r)
    except Exception as e:
        record("find_language_equivalents", error=e)

    try:
        to_lang = "typescript" if LANG == "python" else "python"
        r = convert_code_language_tool(code_snippet=sample_code, from_language=LANG, to_language=to_lang)
        record("convert_code_language", r)
    except Exception as e:
        record("convert_code_language", error=e)

    try:
        r = refactor_polyglot_tool(
            project_folder=TARGET, refactoring_type="rename_api", symbol_name="instrumentHook", new_name="instrumentHook", dry_run=True
        )
        record("refactor_polyglot", r)
    except Exception as e:
        record("refactor_polyglot", error=e)

    # generate_language_bindings — create a minimal OpenAPI spec fixture
    try:
        import json as _json
        import tempfile

        _spec = {
            "openapi": "3.0.0",
            "info": {"title": "Hooks API", "version": "1.0.0"},
            "servers": [{"url": "https://hooks.example.com"}],
            "paths": {
                "/hooks": {
                    "post": {
                        "operationId": "runHook",
                        "summary": "Execute a hook",
                        "parameters": [
                            {"name": "hookName", "in": "query", "schema": {"type": "string"}},
                        ],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        _spec_file = tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False)
        _json.dump(_spec, _spec_file)
        _spec_file.close()
        r = generate_language_bindings_tool(api_definition_file=_spec_file.name)
        record("generate_language_bindings", r)
        Path(_spec_file.name).unlink(missing_ok=True)
    except Exception as e:
        record("generate_language_bindings", error=e)

    # ── Condense tools ──
    from ast_grep_mcp.features.condense.tools import (
        condense_estimate_tool,
        condense_extract_surface_tool,
        condense_normalize_tool,
        condense_pack_tool,
        condense_strip_tool,
        condense_train_dictionary_tool,
    )

    try:
        r = condense_extract_surface_tool(path=TARGET, language=LANG)
        record("condense_extract_surface", r)
    except Exception as e:
        record("condense_extract_surface", error=e)

    # condense_normalize and condense_strip expect a single file, not a directory
    _ts_sample = next(Path(TARGET).rglob(_glob), None) or next(Path(TARGET).rglob("*.js"), None)
    _ts_sample_path = str(_ts_sample) if _ts_sample else None

    try:
        if not _ts_sample_path:
            raise FileNotFoundError("No .ts files found in target")
        r = condense_normalize_tool(path=_ts_sample_path, language=LANG)
        record("condense_normalize", r)
    except Exception as e:
        record("condense_normalize", error=e)

    try:
        if not _ts_sample_path:
            raise FileNotFoundError("No .ts files found in target")
        r = condense_strip_tool(path=_ts_sample_path, language=LANG)
        record("condense_strip", r)
    except Exception as e:
        record("condense_strip", error=e)

    try:
        r = condense_pack_tool(path=TARGET, language=LANG)
        record("condense_pack", r)
    except Exception as e:
        record("condense_pack", error=e)

    try:
        r = condense_estimate_tool(path=TARGET, language=LANG)
        record("condense_estimate", r)
    except Exception as e:
        record("condense_estimate", error=e)

    try:
        r = condense_train_dictionary_tool(path=TARGET, language=LANG)
        record("condense_train_dictionary", r)
    except Exception as e:
        record("condense_train_dictionary", error=e)


async def run_async_tools():
    """Run schema.org async tools."""
    from ast_grep_mcp.features.schema.tools import (
        build_entity_graph_tool,
        generate_entity_id_tool,
        generate_schema_example_tool,
        get_schema_type_tool,
        get_type_hierarchy_tool,
        get_type_properties_tool,
        search_schemas_tool,
        validate_entity_id_tool,
    )

    try:
        r = await get_schema_type_tool("SoftwareApplication")
        record("get_schema_type", r)
    except Exception as e:
        record("get_schema_type", error=e)

    try:
        r = await search_schemas_tool("software")
        record("search_schemas", r)
    except Exception as e:
        record("search_schemas", error=e)

    try:
        r = await get_type_hierarchy_tool("SoftwareApplication")
        record("get_type_hierarchy", r)
    except Exception as e:
        record("get_type_hierarchy", error=e)

    try:
        r = await get_type_properties_tool("SoftwareApplication")
        record("get_type_properties", r)
    except Exception as e:
        record("get_type_properties", error=e)

    try:
        r = await generate_schema_example_tool("SoftwareApplication")
        record("generate_schema_example", r)
    except Exception as e:
        record("generate_schema_example", error=e)

    try:
        r = generate_entity_id_tool(base_url="https://example.com", entity_type="SoftwareApplication", entity_slug="ast-grep-mcp")
        record("generate_entity_id", r)
    except Exception as e:
        record("generate_entity_id", error=e)

    try:
        r = validate_entity_id_tool("https://example.com/#SoftwareApplication/ast-grep-mcp")
        record("validate_entity_id", r)
    except Exception as e:
        record("validate_entity_id", error=e)

    try:
        entities = [
            {"type": "SoftwareApplication", "name": "ast-grep-mcp", "description": "MCP server"},
        ]
        r = await build_entity_graph_tool(entities=entities, base_url="https://example.com")
        record("build_entity_graph", r)
    except Exception as e:
        record("build_entity_graph", error=e)

    # enhance_entity_graph needs existing JSON-LD files
    record("enhance_entity_graph", skipped="Requires existing JSON-LD files")


def main():
    start = time.time()
    print(f"Running all tools against {TARGET}")
    print(f"Language: {LANG}\n")

    # Detect target directory contents and warn about config-only targets
    target_info = _detect_target_info(TARGET)
    if target_info["ext_counts"]:
        top_exts = sorted(target_info["ext_counts"].items(), key=lambda x: -x[1])[:_MAX_DISPLAY_EXTS]
        print(f"Detected extensions: {', '.join(f'{e}({c})' for e, c in top_exts)}")
    for warning in target_info["warnings"]:
        print(warning)
    if target_info["warnings"]:
        print()

    run_sync_tools()
    asyncio.run(run_async_tools())

    elapsed = time.time() - start

    # Summary
    ok = sum(1 for r in results.values() if r["status"] == "OK")
    err = sum(1 for r in results.values() if r["status"] == "ERROR")
    skip = sum(1 for r in results.values() if r["status"] == "SKIPPED")

    print(f"\n{'=' * 70}")
    print(f"RESULTS: {ok} OK | {err} ERROR | {skip} SKIPPED | {len(results)} total | {elapsed:.1f}s")
    print(f"{'=' * 70}\n")

    for name, entry in results.items():
        status = entry["status"]
        icon = {"OK": "+", "ERROR": "!", "SKIPPED": "-"}[status]
        line = f"[{icon}] {name}"
        if status == "ERROR":
            line += f"  -> {entry.get('error', '')[:80]}"
        elif status == "SKIPPED":
            line += f"  -> {entry.get('reason', '')}"
        elif status == "OK":
            # Show a useful summary
            extras = []
            for k, v in entry.items():
                if k in ("tool", "status", "result_keys"):
                    continue
                if k.endswith("_count"):
                    extras.append(f"{k}={v}")
                elif k == "result_length":
                    extras.append(f"len={v}")
                elif k == "result_preview":
                    continue
                elif isinstance(v, (int, float)):
                    extras.append(f"{k}={v}")
            if extras:
                line += f"  ({', '.join(extras[:5])})"
        print(line)

    # Write full JSON
    out_path = Path(__file__).parent / "all_tools_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results: {out_path}")


if __name__ == "__main__":
    main()
