# deduplication

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "deduplication",
  "description": "Directory containing 20 code files with 45 classes and 84 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "45 class definitions",
    "84 function definitions"
  ]
}
</script>

## Overview

This directory contains 20 code file(s) with extracted schemas.

## Files and Schemas

### `analysis_orchestrator.py` (python)

**Classes:**
- `DeduplicationAnalysisOrchestrator` - Line 24
  - Orchestrates the complete deduplication candidate analysis workflow.
  - Methods: __init__, detector, detector, ranker, ranker (+30 more)

**Key Imports:** `concurrent.futures`, `config`, `constants`, `core.logging`, `coverage` (+5 more)

### `analyzer.py` (python)

**Classes:**
- `PatternAnalyzer` - Line 122
  - Analyzes patterns and variations in duplicate code.
  - Methods: __init__, _compare_literal_maps, identify_varying_literals, _parse_literal_matches, _run_literal_scan (+45 more)

**Functions:**
- `detect_conditional_variations(code1, code2, language) -> List[...]` - Line 881
- `_detect_nested_function_call(code, identifier, language) -> Optional[...]` - Line 900
- `_collect_all_variations(analyzer, code1, code2, language) -> List[...]` - Line 919
- `_determine_overall_severity(classification, variation_count) -> str` - Line 949
- `classify_variations(code1, code2, language) -> Dict[...]` - Line 960
- `identify_varying_identifiers(code1, code2, language) -> List[...]` - Line 1004
- `_get_usage_type(context, name) -> str` - Line 1040
- `_extract_identifiers_from_code(code, language) -> Dict[...]` - Line 1050

**Key Imports:** `constants`, `core.logging`, `json`, `models.deduplication`, `os` (+6 more)

### `applicator.py` (python)

**Classes:**
- `DeduplicationApplicator` - Line 22
  - Applies deduplication refactoring with backup and validation.
  - Methods: __init__, apply_deduplication, _validate_and_prepare_plan, _extract_plan_components, _perform_pre_validation (+17 more)

**Functions:**
- `_get_applicator() -> Any` - Line 673
- `_plan_file_modification_order(files_to_modify, generated_code, extract_to_file, project_folder, language) -> Dict[...]` - Line 681
- `_add_import_to_content(content, import_statement, language) -> str` - Line 691
- `_generate_import_for_extracted_function(source_file, target_file, function_name, project_folder, language) -> str` - Line 699

**Key Imports:** `applicator_backup`, `applicator_executor`, `applicator_post_validator`, `applicator_validator`, `constants` (+4 more)

### `applicator_backup.py` (python)

**Classes:**
- `DeduplicationBackupManager` - Line 24
  - Manages backups for deduplication operations.
  - Methods: __init__, create_backup, rollback, cleanup_old_backups, get_file_hash (+6 more)

**Key Imports:** `constants`, `core.logging`, `datetime`, `json`, `os` (+4 more)

### `applicator_executor.py` (python)

**Classes:**
- `RefactoringExecutor` - Line 13
  - Executes the actual code modifications for refactoring.
  - Methods: __init__, apply_changes, _create_files, _create_single_file, _update_files (+3 more)

**Key Imports:** `applicator`, `core.logging`, `os`, `typing`

### `applicator_post_validator.py` (python)

**Classes:**
- `RefactoringPostValidator` - Line 29
  - Validates files after refactoring modifications.
  - Methods: __init__, validate_modified_files, _validate_file_syntax, _read_file_content

**Functions:**
- `_make_error(error_type, file_path, error, suggestion) -> Dict[...]` - Line 16
- `_file_not_found_error(file_path) -> Dict[...]` - Line 20

**Key Imports:** `applicator_validator`, `constants`, `core.logging`, `os`, `rewrite.service` (+2 more)

### `applicator_validator.py` (python)

**Classes:**
- `ValidationResult` - Line 15
  - Result of validation operation.
  - Methods: __init__, to_dict
- `RefactoringPlanValidator` - Line 33
  - Validates refactoring plans before application.
  - Methods: __init__, validate_plan, _validate_required_fields, _resolve_file_path, _check_file_error (+4 more)

**Key Imports:** `constants`, `core.logging`, `pathlib`, `typing`, `utils.syntax_validation`

### `benchmark.py` (python)

**Classes:**
- `BenchmarkExecutor` - Line 42
  - Executes timed benchmarks and collects statistics.
  - Methods: __init__, run_timed_benchmark, _make_scoring_test_cases, _run_scoring_cases, benchmark_scoring (+4 more)
- `BenchmarkReporter` - Line 254
  - Generates benchmark reports and manages baselines.
  - Methods: __init__, format_benchmark_report, save_baseline, load_baseline
- `RegressionDetector` - Line 352
  - Detects performance regressions in benchmark results.
  - Methods: __init__, _collect_regression_errors, check_regressions, _check_single_regression, set_threshold (+1 more)
- `DeduplicationBenchmark` - Line 464
  - Runs performance benchmarks for deduplication functions.
  - Methods: __init__, _check_regressions_if_requested, benchmark_deduplication

**Key Imports:** `constants`, `core.logging`, `json`, `os`, `ranker` (+5 more)

### `config.py` (python)

**Classes:**
- `AnalysisConfig` - Line 24
  - Configuration for deduplication candidate analysis.
  - Methods: __post_init__, to_dict

**Functions:**
- `_require_positive(value, name) -> <ast.Constant object at 0x107f9e100>` - Line 13
- `_require_positive_workers(value) -> <ast.Constant object at 0x107f9ebe0>` - Line 18

**Key Imports:** `constants`, `dataclasses`, `typing`

### `coverage.py` (python)

**Classes:**
- `CoverageDetector` - Line 212
  - Detects test coverage for source files to assess refactoring risk.
  - Methods: __init__, find_test_file_patterns, _get_potential_test_paths, _read_file_content, _check_import_patterns (+12 more)

**Functions:**
- `_get_javascript_patterns(source_name) -> List[...]` - Line 18
- `_get_ruby_patterns(source_name) -> List[...]` - Line 28
- `_python_test_paths(name, dir_path, root, _ext) -> List[...]` - Line 135
- `_js_test_paths(name, dir_path, root, _ext) -> List[...]` - Line 147
- `_ts_test_paths(name, dir_path, root, ext) -> List[...]` - Line 157
- `_java_test_paths(name, dir_path, root, _ext) -> List[...]` - Line 168
- `_go_test_paths(name, dir_path, root, _ext) -> List[...]` - Line 177
- `_ruby_test_paths(name, dir_path, root, _ext) -> List[...]` - Line 181

**Key Imports:** `concurrent.futures`, `constants`, `core.logging`, `glob`, `os` (+2 more)

### `detector.py` (python)

**Classes:**
- `DuplicationDetector` - Line 41
  - Core duplication detection functionality.
  - Methods: __init__, _code_line_count, _build_exclude_patterns, _run_detection, find_duplication (+39 more)

**Key Imports:** `constants`, `core.executor`, `core.logging`, `core.usage_tracking`, `difflib` (+4 more)

### `diff.py` (python)

**Classes:**
- `_DiffCounts` - Line 15
  - Accumulator for diff change counts.
  - Methods: __init__, to_summary
- `_DiffPreviewState` - Line 324
  - Accumulator for unified diff parsing state.
  - Methods: __init__, flush_hunk

**Functions:**
- `_classify_diff_line(diff_lines, i, counts, changes) -> int` - Line 34
- `_parse_unified_diff_lines(diff_lines) -> tuple[...]` - Line 62
- `_build_nested_structure(changes, language) -> dict[...]` - Line 72
- `build_nested_diff_tree(code1, code2, language) -> dict[...]` - Line 90
- `_append_lines_as_ops(diff_ops, lines, op_type) -> <ast.Constant object at 0x107cfa130>` - Line 123
- `_process_opcode(diff_ops, tag, lines1, lines2, i1, i2, j1, j2) -> <ast.Constant object at 0x107cde580>` - Line 129
- `_count_changes(diff_ops) -> int` - Line 154
- `build_diff_tree(code1, code2, language) -> dict[...]` - Line 159
- `_format_diff_alignment(alignment, lines) -> <ast.Constant object at 0x107c99070>` - Line 191
- `_format_alignment_entry(alignment, lines) -> <ast.Constant object at 0x107ca2fa0>` - Line 201
- ... and 15 more functions

**Key Imports:** `constants`, `difflib`, `pathlib`, `re`, `typing`

### `generator.py` (python)

**Classes:**
- `CodeGenerator` - Line 240
  - Generates refactored code for deduplication.
  - Methods: __init__, generate_function_call, _generate_python_import, _generate_js_import, generate_import_statement (+33 more)

**Functions:**
- `_infer_from_identifier_name(identifier, language) -> str` - Line 114
- `_is_boolean_literal(value) -> bool` - Line 157
- `_is_null_literal(value) -> bool` - Line 162
- `_is_quoted_string(value) -> bool` - Line 167
- `_is_integer_literal(value) -> bool` - Line 172
- `_try_get_float_type(value, literal_types) -> Optional[...]` - Line 177
- `_get_collection_type(value, language) -> Optional[...]` - Line 188
- `_infer_single_value_type(value, language) -> str` - Line 198
- `_strip_param_prefix(name) -> str` - Line 834
- `_build_param_candidates(base_name) -> List[...]` - Line 842
- ... and 6 more functions

**Key Imports:** `constants`, `core.logging`, `re`, `time`, `typing` (+2 more)

### `impact.py` (python)

**Classes:**
- `_RiskLevelConfig` (extends: TypedDict) - Line 23
  - Type definition for risk level configuration.
- `ImpactAnalyzer` - Line 108
  - Analyzes the impact of applying deduplication to code.
  - Methods: __init__, analyze_deduplication_impact, _parse_files_from_locations, _find_all_external_refs, _extract_function_names_from_code (+21 more)

**Key Imports:** `constants`, `core`, `core.logging`, `json`, `os` (+3 more)

### `ranker.py` (python)

**Classes:**
- `DeduplicationScoreCalculator` - Line 22
  - Calculates component scores for deduplication priority.
  - Methods: __init__, calculate_total_score, calculate_savings_score, calculate_complexity_score, calculate_risk_score (+1 more)
- `DeduplicationPriorityClassifier` - Line 215
  - Classifies deduplication candidates by priority and generates recommendations.
  - Methods: __init__, get_priority_label, get_score_breakdown, get_recommendation, classify_batch (+1 more)
- `DuplicationRanker` - Line 352
  - Ranks duplication candidates by refactoring value with score caching.
  - Methods: __init__, _generate_cache_key, clear_cache, get_cache_stats, calculate_deduplication_score (+5 more)

**Key Imports:** `concurrent.futures`, `constants`, `core.logging`, `functools`, `heapq` (+5 more)

### `recommendations.py` (python)

**Classes:**
- `RecommendationEngine` - Line 106
  - Generates actionable recommendations for deduplication candidates.
  - Methods: _calc_effort_value_ratio, _score_to_priority, generate_deduplication_recommendation, _calculate_strategy_score, _build_strategy_dict (+1 more)

**Functions:**
- `_extra_suggestions(num_duplicates, line_count, language) -> List[...]` - Line 266
- `generate_refactoring_suggestions(duplicates, language) -> List[...]` - Line 290

**Key Imports:** `constants`, `typing`

### `reporting.py` (python)

**Classes:**
- `EnhancedDuplicationCandidate` - Line 67
  - Enhanced duplication candidate with full reporting details.
- `DuplicationReporter` - Line 99
  - Creates enhanced reports for code duplication findings.
  - Methods: format_diff_with_colors, generate_before_after_example, visualize_complexity, create_enhanced_duplication_response, _build_enhanced_candidate (+4 more)

**Functions:**
- `_colorize_diff_line(line) -> str` - Line 20
- `_number_lines(lines) -> str` - Line 27
- `_get_complexity_level(score) -> Tuple[...]` - Line 31

**Key Imports:** `constants`, `dataclasses`, `datetime`, `typing`, `utils.formatters`

### `scoring_scales.py` (python)

**Classes:**
- `VariationScoreScale` (extends: IntEnum) - Line 6
  - Discrete variation complexity score levels used in pattern analysis.
- `VariationScoreCutoff` (extends: IntEnum) - Line 16
  - Cutoff thresholds for mapping variation scores to complexity labels.
- `SimilarityDiscreteBand` (extends: IntEnum) - Line 22
  - Discrete structural line-count bands for similarity bucketing.
- `SharedTopN` (extends: IntEnum) - Line 31
  - Shared top-N list sizing values used across reporting and scripts.
- `AnalyzeCodebaseTopN` (extends: IntEnum) - Line 41
  - Top-N limits for analyze_codebase reporting.
- `PatternEquivalenceTopN` (extends: IntEnum) - Line 52
  - Top-N limits for cross-language pattern equivalence suggestions.
- `AnalyticsBotTopN` (extends: IntEnum) - Line 61
  - Top-N limits for scripts/analyze_analyticsbot.py.
- `PrintMigrationTopN` (extends: IntEnum) - Line 68
  - Top-N limits for scripts/migrate_prints_smart.py.

**Key Imports:** `enum`

### `similarity.py` (python)

**Classes:**
- `SimilarityConfig` - Line 35
  - Configuration for MinHash similarity calculation.
- `SimilarityResult` - Line 70
  - Result of a similarity calculation.
- `HybridSimilarityConfig` - Line 87
  - Configuration for the hybrid two/three-stage similarity pipeline.
  - Methods: __post_init__, _apply_semantic_rebalance_if_needed, _validate_weight_bounds, _check_bound, _check_weight_sum (+1 more)
- `HybridSimilarityResult` - Line 155
  - Result of hybrid two/three-stage similarity calculation.
  - Methods: combined_similarity, to_dict
- `MinHashSimilarity` - Line 202
  - MinHash-based similarity calculator for code clone detection.
  - Methods: __init__, create_minhash, estimate_similarity, calculate_similarity, build_lsh_index (+13 more)
- `HybridSimilarity` - Line 462
  - Hybrid two/three-stage similarity calculator combining MinHash, AST, and CodeBERT.
  - Methods: __init__, _try_init_semantic, _get_semantic_calculator, _build_empty_similarity_result, _run_stage1_filter (+15 more)
- `SimilarityBucket` - Line 827
  - A bucket of potentially similar code items.
- `EnhancedStructureHash` - Line 834
  - Structure hash using AST-like node sequence patterns for bucket distribution.
  - Methods: __init__, calculate, _extract_node_sequence, _calculate_control_flow_complexity, _defined_name_from_line (+6 more)
- `SemanticSimilarityConfig` - Line 1095
  - Configuration for CodeBERT-based semantic similarity (Type-4 clone detection).
- `SemanticSimilarityResult` - Line 1109
  - Result of CodeBERT semantic similarity calculation.
  - Methods: model_name, embedding1_shape, embedding2_shape, to_dict
- `SemanticSimilarity` - Line 1155
  - CodeBERT-based semantic similarity for Type-4 clone detection.
  - Methods: __init__, is_available, _init_model_components, _load_model, _select_device (+7 more)

**Functions:**
- `_check_transformers_available() -> bool` - Line 1074

**Key Imports:** `constants`, `core.logging`, `dataclasses`, `datasketch`, `difflib` (+7 more)

### `tools.py` (python)

**Functions:**
- `find_duplication_tool(project_folder, language, min_similarity, min_lines, exclude_patterns) -> Dict[...]` - Line 25
- `analyze_deduplication_candidates_tool(project_path, language, min_similarity, include_test_coverage, min_lines, max_candidates, exclude_patterns) -> Dict[...]` - Line 69
- `apply_deduplication_tool(project_folder, group_id, refactoring_plan, dry_run, backup, extract_to_file) -> Dict[...]` - Line 106
- `benchmark_deduplication_tool(iterations, save_baseline, check_regression) -> Dict[...]` - Line 138
- `calculate_ast_similarity_tool(code1, code2) -> Dict[...]` - Line 174
- `calculate_semantic_similarity_tool(code1, code2, model_name) -> Dict[...]` - Line 198
- `_register_find_duplication(mcp) -> <ast.Constant object at 0x107f36040>` - Line 228
- `_register_analyze_candidates(mcp) -> <ast.Constant object at 0x107f9ed90>` - Line 249
- `_register_apply_deduplication(mcp) -> <ast.Constant object at 0x107f9b910>` - Line 274
- `_register_benchmark_deduplication(mcp) -> <ast.Constant object at 0x107f4a310>` - Line 299
- ... and 3 more functions

**Key Imports:** `analysis_orchestrator`, `applicator`, `benchmark`, `constants`, `core.logging` (+5 more)

---
*Generated by Enhanced Schema Generator with schema.org markup*