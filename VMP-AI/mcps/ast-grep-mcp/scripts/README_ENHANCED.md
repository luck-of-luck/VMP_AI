# scripts

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "scripts",
  "description": "Directory containing 23 code files with 4 classes and 82 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "4 class definitions",
    "82 function definitions"
  ]
}
</script>

## Overview

This directory contains 23 code file(s) with extracted schemas.

## Files and Schemas

### `analysis_output_helpers.py` (python)

**Functions:**
- `print_section_header(log, title) -> <ast.Constant object at 0x107c9b3a0>` - Line 10
- `count_by_key(items, key) -> dict[...]` - Line 27
- `log_count_breakdown(log, counts) -> <ast.Constant object at 0x107cbceb0>` - Line 37

**Key Imports:** `ast_grep_mcp.constants`, `typing`

### `analyze-duplicates.py` (python)

**Functions:**
- `get_file_path(location)` - Line 20
- `analyze_report(report_path)` - Line 29
- `find_latest_report()` - Line 60

**Key Imports:** `collections`, `json`, `pathlib`, `sys`

### `analyze_violations.py` (python)

**Functions:**
- `analyze_function_complexity(file_path, func_name) -> dict` - Line 13
- `calculate_cyclomatic_complexity(node) -> int` - Line 34
- `calculate_cognitive_complexity(node, depth) -> int` - Line 51
- `calculate_max_nesting(node, current_depth) -> int` - Line 75
- `scan_all_functions(project_root)` - Line 104
- `main()` - Line 126

**Key Imports:** `ast`, `ast_grep_mcp.constants`, `pathlib`, `sys`

### `backfill-skill-spans.py` (python)

**Functions:**
- `new_span_id() -> str` - Line 51
- `iso_to_otel_time(iso_str) -> list[...]` - Line 55
- `load_trace_ctx(session_id) -> <ast.BinOp object at 0x107f4d3a0>` - Line 64
- `parse_agent_cache(agent_name, project_filter, session_filter) -> list[...]` - Line 76
- `build_span(name, trace_id, session_id, start_time, end_time, duration, skill_name, agent_name, category, extra_attrs) -> dict[...]` - Line 145
- `compute_duration(start, end) -> list[...]` - Line 191
- `generate_spans(invocations, skill_name, agent_name, category) -> list[...]` - Line 201
- `check_already_backfilled(trace_file, skill_name) -> set[...]` - Line 264
- `main() -> <ast.Constant object at 0x107f33bb0>` - Line 280

**Key Imports:** `__future__`, `argparse`, `datetime`, `json`, `pathlib` (+3 more)

### `benchmark_batch_coverage.py` (python)

**Functions:**
- `create_test_candidates(file_count, files_per_candidate) -> List[...]` - Line 32
- `_run_timed_benchmark(method, candidates, action) -> Dict` - Line 73
- `benchmark_legacy_sequential(detector, candidates, project_path) -> Dict` - Line 90
- `benchmark_legacy_parallel(orchestrator, candidates, project_path) -> Dict` - Line 103
- `benchmark_batch_sequential(orchestrator, candidates, project_path) -> Dict` - Line 112
- `benchmark_batch_parallel(orchestrator, candidates, project_path) -> Dict` - Line 121
- `run_benchmark_suite(file_count, files_per_candidate, project_path) -> Dict` - Line 132
- `main() -> <ast.Constant object at 0x1056a2250>` - Line 192

**Key Imports:** `argparse`, `ast_grep_mcp.constants`, `ast_grep_mcp.features.deduplication.analysis_orchestrator`, `ast_grep_mcp.features.deduplication.coverage`, `ast_grep_mcp.utils.console_logger` (+4 more)

### `benchmark_parallel_enrichment.py` (python)

**Functions:**
- `create_mock_candidates(count) -> List[...]` - Line 25
- `benchmark_enrichment()` - Line 41

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.features.deduplication.analysis_orchestrator`, `ast_grep_mcp.utils.console_logger`, `time`, `typing`

### `fix_import_orphans.py` (python)

**Functions:**
- `_is_orphan_close_paren(line, prev_line) -> bool` - Line 22
- `_is_orphan_import_item_start(line, raw_line, prev_line) -> bool` - Line 27
- `_scan_orphan_item_range(lines, start) -> Tuple[...]` - Line 41
- `find_orphaned_imports(lines) -> List[...]` - Line 54
- `remove_orphaned_lines(filepath)` - Line 80
- `check_syntax(filepath)` - Line 98
- `main()` - Line 104

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.utils.console_logger`, `migration_common`, `pathlib`, `scripts.migration_common` (+3 more)

### `fix_migration_errors.py` (python)

**Functions:**
- `_is_potential_orphan_followup(next_line) -> bool` - Line 16
- `_find_orphaned_import_ranges(lines) -> List[...]` - Line 37
- `fix_file(filepath) -> bool` - Line 60
- `main()` - Line 74

**Key Imports:** `ast_grep_mcp.utils.console_logger`, `migration_common`, `pathlib`, `re`, `scripts.migration_common` (+1 more)

### `generate_import_zod_rules.py` (python)

**Functions:**
- `print_header(title, leading_newline) -> <ast.Constant object at 0x10978d550>` - Line 10

**Key Imports:** `ast_grep_mcp.features.search.service`

### `generate_zod_rules.py` (python)

**Functions:**
- `print_header(title, leading_newline) -> <ast.Constant object at 0x1082ab460>` - Line 10

**Key Imports:** `ast_grep_mcp.features.search.service`

### `import_helpers.py` (python)

**Functions:**
- `scan_import_state(lines, import_statement) -> Tuple[...]` - Line 8
- `compute_import_insert_index(lines) -> int` - Line 23
- `ensure_import_present(lines, import_statement) -> bool` - Line 46

**Key Imports:** `typing`

### `list_complexity_violations.py` (python)

**Functions:**
- `scan_all_python_files(root) -> list[...]` - Line 22
- `main()` - Line 50

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.features.complexity.analyzer`, `pathlib`, `sys`

### `list_tools.py` (python)

**Functions:**
- `main() -> int` - Line 113

**Key Imports:** `__future__`, `argparse`, `ast_grep_mcp.server.registry`, `asyncio`, `json` (+2 more)

### `migrate_print_to_logger.py` (python)

**Classes:**
- `PrintStatement` - Line 43
  - Represents a console.blank() statement to migrate.
- `PrintMigrator` - Line 54
  - Migrates console.blank() statements to console logger calls.
  - Methods: __init__, analyze_print_call, migrate_print_statement, find_print_statements, _extract_print_call (+9 more)

**Functions:**
- `main()` - Line 338

**Key Imports:** `argparse`, `ast_grep_mcp.constants`, `ast_grep_mcp.utils.console_logger`, `dataclasses`, `import_helpers` (+7 more)

### `migrate_prints_smart.py` (python)

**Functions:**
- `smart_replace_print(line) -> Tuple[...]` - Line 29
- `add_console_import(lines) -> List[...]` - Line 102
- `migrate_file(file_path, dry_run) -> Tuple[...]` - Line 116
- `migrate_directory(dir_path, pattern, dry_run)` - Line 156
- `main()` - Line 180

**Key Imports:** `argparse`, `ast_grep_mcp.constants`, `ast_grep_mcp.features.deduplication.scoring_scales`, `ast_grep_mcp.utils.console_logger`, `ast_grep_mcp.utils.slicing` (+6 more)

### `migration_common.py` (python)

**Functions:**
- `read_lines(file_path) -> List[...]` - Line 27
- `write_lines(file_path, lines) -> <ast.Constant object at 0x107f51520>` - Line 33
- `iter_migration_targets(directory, pattern, skip_pycache, sort) -> Iterator[...]` - Line 39
- `_normalize_ranges(ranges) -> List[...]` - Line 57
- `remove_line_ranges(lines, ranges) -> List[...]` - Line 76

**Key Imports:** `pathlib`, `typing`

### `run_all_analysis.py` (python)

**Functions:**
- `run_complexity(project_folder) -> dict` - Line 18
- `run_smells(project_folder) -> dict` - Line 36
- `run_standards(project_folder) -> dict` - Line 53
- `run_security(project_folder) -> dict` - Line 69
- `run_orphans(project_folder) -> dict` - Line 85
- `run_duplication(project_folder) -> dict` - Line 101
- `run_benchmarks() -> dict` - Line 120
- `main() -> <ast.Constant object at 0x107f37f70>` - Line 133

**Key Imports:** `ast_grep_mcp.features.complexity.tools`, `ast_grep_mcp.features.deduplication.tools`, `ast_grep_mcp.features.quality.tools`, `json`, `pathlib` (+2 more)

### `run_all_tools.py` (python)

**Functions:**
- `_detect_target_info(target) -> dict` - Line 47
- `record(name, result, error, skipped)` - Line 108
- `run_sync_tools()` - Line 112
- `main()` - Line 666

**Key Imports:** `ast_grep_mcp.features.complexity.tools`, `ast_grep_mcp.features.condense.tools`, `ast_grep_mcp.features.cross_language.tools`, `ast_grep_mcp.features.deduplication.tools`, `ast_grep_mcp.features.documentation.tools` (+14 more)

### `run_benchmarks.py` (python)

**Functions:**
- `run_benchmarks(save_baseline, check_regression, output_file) -> int` - Line 30
- `main() -> int` - Line 104

**Key Imports:** `argparse`, `ast_grep_mcp.constants`, `ast_grep_mcp.utils.console_logger`, `pathlib`, `subprocess` (+1 more)

### `run_quality_docs.py` (python)

**Functions:**
- `record(name, result, error, skipped)` - Line 19
- `main()` - Line 31

**Key Imports:** `ast_grep_mcp.features.documentation.tools`, `ast_grep_mcp.features.quality.tools`, `json`, `pathlib`, `sys` (+2 more)

### `scan_complexity_offenders.py` (python)

**Functions:**
- `_short_path(path) -> str` - Line 38
- `_extract_name(code) -> str` - Line 42
- `main() -> <ast.Constant object at 0x1097b17c0>` - Line 51

**Key Imports:** `ast_grep_mcp.features.complexity.analyzer`, `ast_grep_mcp.features.complexity.metrics`, `pathlib`, `sys`

### `schema-graph-builder.py` (python)

**Classes:**
- `StatsDict` (extends: TypedDict) - Line 35
  - Type definition for stats dictionary.
- `SchemaGraphBuilder` - Line 47
  - Main class for building and analyzing Schema.org entity graphs.
  - Methods: __init__, _extract_project_name, discover_json_schemas, generate_entity_id, validate_entity_id (+6 more)

**Functions:**
- `main() -> <ast.Constant object at 0x106446f40>` - Line 555

**Key Imports:** `argparse`, `ast_grep_mcp.constants`, `ast_grep_mcp.utils.console_logger`, `collections`, `datetime` (+4 more)

### `tool_result_recorder.py` (python)

**Functions:**
- `record_tool_result(results, name, result, error, skipped, include_string_preview, include_other_fallback) -> <ast.Constant object at 0x107f33b50>` - Line 11

**Key Imports:** `typing`

---
*Generated by Enhanced Schema Generator with schema.org markup*