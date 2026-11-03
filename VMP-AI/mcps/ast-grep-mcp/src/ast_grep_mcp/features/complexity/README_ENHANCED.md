# complexity

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "complexity",
  "description": "Directory containing 7 code files with 4 classes and 67 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "4 class definitions",
    "67 function definitions"
  ]
}
</script>

## Overview

This directory contains 7 code file(s) with extracted schemas.

## Files and Schemas

### `analyzer.py` (python)

**Functions:**
- `_run_pattern_search(file_path, language, pattern) -> List[...]` - Line 46
- `extract_functions_from_file(file_path, language) -> List[...]` - Line 65
- `_get_class_extraction_pattern(language) -> str` - Line 83
- `_execute_ast_grep_for_classes(file_path, language, pattern) -> List[...]` - Line 101
- `_process_class_match_results(matches, language) -> List[...]` - Line 127
- `_extract_single_class_info(match, language) -> Dict[...]` - Line 144
- `_extract_class_name_from_match(match) -> str` - Line 162
- `_extract_class_line_range(match) -> Tuple[...]` - Line 187
- `_count_class_methods(code, language) -> int` - Line 202
- `_extract_param_string(code, language) -> str` - Line 219
- ... and 13 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.complexity`, `ast_grep_mcp.utils.parsing`, `json` (+4 more)

### `complexity_analyzer.py` (python)

**Classes:**
- `ParallelComplexityAnalyzer` - Line 16
  - Analyzes files in parallel for complexity metrics.
  - Methods: __init__, analyze_files, _collect_future_result, filter_exceeding_functions

**Key Imports:** `analyzer`, `concurrent.futures`, `constants`, `core.logging`, `models.complexity` (+1 more)

### `complexity_file_finder.py` (python)

**Classes:**
- `ComplexityFileFinder` - Line 14
  - Finds and filters files for complexity analysis.
  - Methods: __init__, find_files, _get_language_extensions, _build_glob_pattern, _find_matching_files (+2 more)

**Key Imports:** `core.logging`, `glob`, `pathlib`, `typing`

### `complexity_statistics.py` (python)

**Classes:**
- `ComplexityStatisticsAggregator` - Line 16
  - Aggregates statistics and formats complexity analysis results.
  - Methods: __init__, calculate_summary, _compute_metrics, _run_git_command, get_git_info (+4 more)

**Key Imports:** `constants`, `core.logging`, `models.complexity`, `storage`, `subprocess` (+1 more)

### `metrics.py` (python)

**Functions:**
- `get_complexity_patterns(language) -> Dict[...]` - Line 126
- `count_pattern_matches(code, pattern, language) -> int` - Line 142
- `_get_cyclomatic_config(language) -> Dict[...]` - Line 169
- `_count_occurrences(code, items) -> int` - Line 185
- `calculate_cyclomatic_complexity(code, language) -> int` - Line 201
- `_get_control_flow_keywords(language, patterns) -> List[...]` - Line 231
- `_calculate_line_indentation(line, base_indent) -> Tuple[...]` - Line 257
- `_is_comment_line(stripped) -> bool` - Line 284
- `_match_control_flow_keyword(stripped, control_flow) -> Optional[...]` - Line 296
- `_calculate_keyword_complexity(keyword, stripped, current_nesting) -> int` - Line 315
- ... and 7 more functions

**Key Imports:** `ast_grep_mcp.constants`, `json`, `re`, `subprocess`, `typing`

### `storage.py` (python)

**Classes:**
- `ComplexityStorage` - Line 172
  - SQLite storage for complexity analysis results.
  - Methods: __init__, _get_default_db_path, _get_connection, _init_db, get_or_create_project (+2 more)

**Functions:**
- `_build_run_params(project_id, commit_hash, branch_name, results) -> tuple[...]` - Line 77
- `_build_function_rows(functions) -> List[...]` - Line 99
- `_insert_run(conn, run_params) -> int` - Line 156
- `_insert_function_metrics(conn, run_id, function_rows) -> <ast.Constant object at 0x1056a95e0>` - Line 161

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.models.complexity`, `contextlib`, `os`, `pathlib` (+3 more)

### `tools.py` (python)

**Functions:**
- `_validate_inputs(language) -> <ast.Constant object at 0x1080acf40>` - Line 43
- `_normalize_complexity_exclude_patterns(exclude_patterns) -> List[...]` - Line 57
- `_find_files_to_analyze(project_folder, language, include_patterns, exclude_patterns, logger) -> tuple[...]` - Line 62
- `_analyze_files_parallel(files_to_analyze, language, thresholds, max_threads) -> tuple[...]` - Line 85
- `_calculate_summary_statistics(all_functions, exceeding_functions, total_files, execution_time) -> tuple[...]` - Line 110
- `_store_and_generate_trends(store_results, include_trends, project_folder, summary, all_functions, statistics) -> tuple[...]` - Line 130
- `_format_response(summary, thresholds_dict, exceeding_functions, run_id, stored_at, trends, statistics) -> Dict[...]` - Line 164
- `_handle_no_files_found(language, execution_time) -> Dict[...]` - Line 190
- `_thresholds_to_dict(thresholds) -> Dict[...]` - Line 212
- `_execute_analysis(project_folder, language, thresholds, files_to_analyze, store_results, include_trends, max_threads, start_time, logger) -> Dict[...]` - Line 221
- ... and 13 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.quality.smells`, `ast_grep_mcp.models.complexity`, `ast_grep_mcp.utils.tool_context` (+9 more)

---
*Generated by Enhanced Schema Generator with schema.org markup*