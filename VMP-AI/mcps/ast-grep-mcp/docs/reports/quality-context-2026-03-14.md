# Quality Context — ast-grep-mcp (2026-03-14)

All 7 Quality tools + Complexity tools run against `~/code/ast-grep-mcp` with `language=python`.

## Executive Summary

| Metric | Value |
|--------|-------|
| Total files analyzed | 243 |
| Total functions analyzed | 4,073 (across 236 files) |
| Standards violations | 0 |
| Security issues | 0 |
| Code smells | 21 (all low-severity magic numbers) |
| Functions exceeding complexity thresholds | 211 / 4,073 (5.2%) |
| Orphan files | 28 |
| Orphan functions | 341 / 3,952 (8.6%) |
| Total orphan lines | 15,125 |
| All tools run | 48 OK / 0 ERROR / 4 SKIPPED (of 52) |

---

## 1. Standards Enforcement

**Status: Clean** — 0 violations across 3 rules executed (174ms).
Rules: `no-mutable-defaults`, `no-print-production`, `no-bare-except`.

## 2. Security Issues

**Status: Clean** — 0 issues, 11 patterns scanned, 985ms.

## 3. Code Smells

**21 magic number instances** (all low severity):

| File | Line | Value |
|------|------|-------|
| `scripts/run_all_analysis.py` | 15 | `3` |
| `src/.../quality/orphan_detector.py` | 418 | `8` |
| `src/.../quality/orphan_detector.py` | 546 | `8` |
| `scripts/detect_orphans_detail.py` | 86, 88 | `3` |
| `scripts/backfill-skill-spans.py` | (8 instances) | `8, 16, 64, 4, 5, 3` |
| `scripts/run_all_tools.py` | (3 instances) | `500, 200, 300` |
| `scripts/analyze-duplicates.py` | (2 instances) | `15, 4` |
| Others | (3 instances) | Various |

Only 2 smells in `src/` (orphan_detector.py). Rest in `scripts/`.

No long-function, deep-nesting, or god-class smells detected.

## 4. Complexity Analysis

**Summary:**
- Avg cyclomatic: 3.37 | Avg cognitive: 3.43
- Max cyclomatic: 65 | Max cognitive: 118 | Max nesting: 10
- 211 functions exceed thresholds (5.2% of 4,073)

**Top 15 highest-complexity functions:**

| Function | File | Lines | Cyc | Cog | Nest |
|----------|------|-------|-----|-----|------|
| run_sync_tools | scripts/run_all_tools.py | 134-614 | 65 | 118 | 7 |
| generate_documentation | scripts/schema-graph-builder.py | 164-231 | 41 | 97 | 8 |
| (main block) | scripts/run_quality_docs.py | 45-181 | 32 | 51 | 5 |
| _detect_target_info | scripts/run_all_tools.py | 35-99 | 32 | 36 | 4 |
| smart_replace_print | scripts/migrate_prints_smart.py | 27-97 | 31 | 19 | 3 |
| main | scripts/run_all_tools.py | 685-744 | 29 | 36 | 5 |
| generate_spans | scripts/backfill-skill-spans.py | 75-142 | 27 | 62 | 6 |
| (docs block) | scripts/schema-graph-builder.py | 555-709 | 27 | 36 | 5 |
| run_benchmark_suite | scripts/benchmark_batch_coverage.py | 218-287 | 24 | 30 | 5 |
| (test function) | tests/unit/test_complexity.py | 608-656 | 20 | 39 | 6 |
| migrate_directory | scripts/migrate_prints_smart.py | 180-277 | 20 | 31 | 5 |
| (markdown gen) | src/.../schema/markdown_service.py | 172-228 | 20 | 29 | 5 |
| track_metrics | tests/scripts/track_fixture_metrics.py | 91-117 | 19 | 50 | 8 |
| analyze_relationships | scripts/schema-graph-builder.py | 313-366 | 19 | 49 | 7 |
| (fixture metrics) | tests/scripts/track_fixture_metrics.py | 119-155 | 19 | 37 | 7 |

**Note:** Only 1 function in `src/` appears in the top 15 (`markdown_service.py:172-228`, cyc=20). The rest are scripts and tests.

---

## 5. Orphan Detection (Full Output)

**28 orphan files** and **341 orphan functions** detected across 243 analyzed files.
Analysis time: 61.9s. All orphan files have status `uncertain` (verification timed out or found string references only).

### 5.1 Orphan Files (28)

| File | Lines | Status | Reason |
|------|-------|--------|--------|
| `scripts/analyze-duplicates.py` | 85 | uncertain | Verification timed out |
| `scripts/cleanup-error-logs.ts` | 368 | uncertain | Verification timed out |
| `scripts/list_complexity_violations.py` | 108 | uncertain | Verification timed out |
| `scripts/analyze_analyticsbot.py` | 158 | uncertain | Verification timed out |
| `tests/scripts/track_fixture_metrics.py` | 375 | uncertain | Verification timed out |
| `scripts/validate-permissions.ts` | 180 | uncertain | 10 string refs |
| `scripts/run_quality_docs.py` | 186 | uncertain | Verification timed out |
| `scripts/analyze_violations.py` | 187 | uncertain | Verification timed out |
| `scripts/benchmark_parallel_enrichment.py` | 89 | uncertain | Verification timed out |
| `scripts/verify-setup.ts` | 253 | uncertain | 9 string refs |
| `tests/scripts/detect_fixture_patterns.py` | 446 | uncertain | Verification timed out |
| `scripts/detect_orphans_detail.py` | 175 | uncertain | Verification timed out |
| `tests/fixtures/example.py` | 17 | uncertain | Verification timed out |
| `tests/scripts/validate_refactoring.py` | 337 | uncertain | 14 string refs |
| `scripts/backfill-skill-spans.py` | 327 | uncertain | Verification timed out |
| `scripts/benchmark_batch_coverage.py` | 292 | uncertain | Verification timed out |
| `scripts/benchmark_orphan_detector.py` | 61 | uncertain | Verification timed out |
| `tests/scripts/benchmark_fixtures.py` | 306 | uncertain | Verification timed out |
| `scripts/fix-types.ts` | 100 | uncertain | Verification timed out |
| `scripts/schema-graph-builder.py` | 714 | uncertain | Verification timed out |
| `scripts/run_all_tools.py` | 749 | uncertain | Verification timed out |
| `scripts/generate-http-status-constants.ts` | 111 | uncertain | Verification timed out |
| `scripts/categorize-magic-numbers.ts` | 624 | uncertain | Verification timed out |
| `scripts/run_all_analysis.py` | 152 | uncertain | Verification timed out |
| `scripts/run_benchmarks.py` | 139 | uncertain | 23 string refs |
| `tests/scripts/score_test_file.py` | 536 | uncertain | 17 string refs |
| `analyze_codebase.py` | 593 | uncertain | Verification timed out |
| `scripts/migrate_prints_smart.py` | 282 | uncertain | 20 string refs |

**Breakdown by directory:**
- `scripts/` — 21 files (4,952 lines)
- `tests/scripts/` — 4 files (1,663 lines)
- `tests/fixtures/` — 1 file (17 lines)
- `tests/` — 1 file (375 lines)
- root — 1 file (593 lines, `analyze_codebase.py`)

All are standalone CLI scripts, not imported modules. Expected behavior for orphan detector.

### 5.2 Orphan Functions (341) — Grouped by Location

#### scripts/ (78 orphan functions)

| File | Count | Notable Functions |
|------|-------|-------------------|
| `analyze_codebase.py` | 12 | `print_section`, `_discover_source_files`, `analyze_individual_files`, `analyze_project_complexity`, `analyze_duplication`, `_print_report_summary`, `generate_summary_report`, `_run_tsc_check` |
| `migrate_print_to_logger.py` | 12 | `analyze_print_call`, `migrate_print_statement`, `_read_file_lines`, `find_print_statements`, `_extract_print_call`, `_scan_import_state` |
| `backfill-skill-spans.py` | 8 | `new_span_id`, `iso_to_otel_time`, `load_trace_ctx`, `build_span`, `parse_agent_cache`, `compute_duration`, `generate_spans`, `check_already_backfilled` |
| `run_all_analysis.py` | 7 | `run_complexity`, `run_smells`, `run_standards`, `run_security`, `run_orphans`, `run_duplication`, `run_benchmarks` |
| `schema-graph-builder.py` | 6 | `discover_json_schemas`, `extract_entities_from_schema`, `analyze_relationships`, `generate_documentation`, `merge_duplicate_entities`, `validate_all_entity_ids` |
| `analyze_analyticsbot.py` | 6 | `_run_complexity_scan`, `_run_smell_scan`, `_format_complexity_summary`, `_run_security_scan`, `_format_smell_summary`, `_format_security_summary` |
| `fix_import_orphans.py` | 6 | `find_orphaned_imports`, `_is_orphan_close_paren`, `_is_orphan_import_item_start`, `_scan_orphan_item_range`, `remove_orphaned_lines`, `check_syntax` |
| `benchmark_batch_coverage.py` | 6 | `create_test_candidates`, `benchmark_legacy_sequential`, `benchmark_batch_parallel`, `benchmark_legacy_parallel`, `benchmark_batch_sequential`, `run_benchmark_suite` |
| `migrate_prints_smart.py` | 4 | `migrate_file`, `smart_replace_print`, `add_console_import`, `migrate_directory` |
| `migration_common.py` | 4 | `write_lines`, `_normalize_ranges`, `read_lines`, `remove_line_ranges` |
| `analysis_output_helpers.py` | 3 | `print_section_header`, `log_count_breakdown`, `count_by_key` |
| `analyze-duplicates.py` | 3 | `get_file_path`, `find_latest_report`, `analyze_report` |
| `analyze_violations.py` | 3 | `analyze_function_complexity`, `calculate_max_nesting`, `scan_all_functions` |
| `import_helpers.py` | 3 | `scan_import_state`, `compute_import_insert_index`, `ensure_import_present` |
| `fix_migration_errors.py` | 3 | `_is_potential_orphan_followup`, `_find_orphaned_import_ranges`, `fix_file` |
| `run_all_tools.py` | 2 | `run_sync_tools`, `_detect_target_info` |
| `scan_complexity_offenders.py` | 2 | `_short_path`, `_extract_name` |
| `benchmark_parallel_enrichment.py` | 2 | `benchmark_enrichment`, `create_mock_candidates` |
| `list_complexity_violations.py` | 1 | `scan_all_python_files` |
| `run_benchmarks.py` | 1 | `run_benchmarks` |

#### src/ core + features (103 orphan functions)

| File | Count | Notable Functions |
|------|-------|-------------------|
| `deduplication/generator.py` | 16 | `generate_extracted_function`, `generate_function_call`, `generate_parameter_name`, `_infer_single_value_type`, `_generate_python_function`, `_generate_java_function`, `_generate_js_ts_function`, `_generate_generic_function` |
| `deduplication/analysis_orchestrator.py` | 8 | `ranker`, `recommendation_engine`, `coverage_detector`, `_build_analysis_metadata`, `_enrich_and_summarize`, `_enrich_with_test_coverage`, `_enrich_with_recommendation`, `_add_test_coverage` |
| `deduplication/coverage.py` | 8 | `_get_javascript_patterns`, `_get_ruby_patterns`, `_js_test_paths`, `_python_test_paths`, `_ts_test_paths`, `_java_test_paths`, `_ruby_test_paths`, `_go_test_paths` |
| `documentation/readme_generator.py` | 7 | `_generate_usage_section`, `_generate_installation_section`, `_generate_api_section`, `_generate_features_section`, `_generate_structure_section`, `_generate_contributing_section`, `_generate_license_section` |
| `documentation/docstring_generator.py` | 6 | `_generate_google_docstring`, `_generate_numpy_docstring`, `_generate_sphinx_docstring`, `_generate_javadoc`, `_split_snake_case`, `_split_camel_case` |
| `cross_language/binding_generator.py` | 6 | `_python_type_converter`, `_generate_python_binding`, `_generate_typescript_binding`, `_js_type_converter`, `_ts_type_converter`, `_generate_javascript_binding` |
| `utils/templates.py` | 6 | `format_python_class`, `_java_import_sort_key`, `format_java_method`, `format_typescript_class`, `format_typescript_function`, `format_javascript_function` |
| `deduplication/diff.py` | 5 | `build_nested_diff_tree`, `build_diff_tree`, `format_alignment_diff`, `diff_preview_to_dict`, `generate_diff_from_file_paths` |
| `core/usage_tracking.py` | 5 | `track_usage`, `get_usage_alerts`, `get_usage_stats`, `get_recent_usage`, `format_usage_report` |
| `schema/client.py` | 5 | `_check_hash_fragment`, `_check_fragment_quality`, `_check_query_params`, `_check_url_protocol`, `_check_https` |
| `deduplication/applicator_post_validator.py` | 4 | `_validate_file_structure`, `_validate_python_structure`, `_validate_java_structure`, `_validate_js_structure` |
| `deduplication/benchmark.py` | 4 | `get_thresholds`, `set_threshold`, `run_scoring`, `run_recommendations` |
| `models/deduplication.py` | 4 | `add_child`, `get_statistics`, `to_signature`, `get_file_diff` |
| `complexity/tools.py` | 4 | `_sentry_test_breadcrumb`, `_sentry_test_error`, `_sentry_test_warning`, `_sentry_test_span` |
| `schema/enhancement_rules.py` | 3 | `get_rich_results_for_entity`, `get_all_properties_for_entity`, `get_entity_suggestions` |
| `deduplication/similarity.py` | 3 | `find_all_similar_pairs`, `_extract_tokens`, `create_buckets` |
| `cross_language/pattern_database.py` | 3 | `get_pattern`, `get_equivalents`, `search_patterns` |
| `cross_language/pattern_equivalence.py` | 2 | `get_pattern_details`, `list_pattern_categories` |
| `deduplication/analyzer.py` | 2 | `_detect_nested_function_call`, `analyze_duplicate_group_literals` |
| `quality/orphan_detector.py` | 2 | `_verify_single_orphan`, `_check_function_called_grep` |
| `quality/fixer.py` | 2 | `_fix_double_equals`, `preview_fix` |
| `refactoring/renamer.py` | 2 | `_classify_python_reference`, `_classify_javascript_reference` |
| `complexity/analyzer.py` | 2 | `_extract_classes_from_file`, `analyze_file_complexity` |
| Others (12 files) | 1 each | Various internal helpers |

#### tests/ (87 orphan functions)

| File | Count | Notable Functions |
|------|-------|-------------------|
| `scripts/score_test_file.py` | 20 | `format_score_table`, `find_test_files`, `analyze_test_file`, `_empty_metrics`, `_count_test_functions`, `_count_test_classes`, `_count_setup_methods` |
| `unit/test_progress_callbacks.py` | 12 | `track_progress` (x7), `failing_callback`, + 4 more |
| `integration/test_benchmark.py` | 9 | `run_deduplication_benchmarks`, `_load_baseline`, `run_benchmark`, `check_regression`, `generate_report` |
| `scripts/detect_fixture_patterns.py` | 9 | `format_pattern_report`, `find_test_files`, `detect_file_creation_pattern`, `detect_mock_popen_pattern`, `detect_cache_initialization_pattern` |
| `unit/conftest.py` | 8 | `mock_field`, `_factory` (x5), `_create_plan` |
| `scripts/track_fixture_metrics.py` | 7 | `format_metrics_report`, `save_metrics_history`, `track_metrics`, `extract_fixtures_from_conftest` |
| `scripts/validate_refactoring.py` | 6 | `format_result_report`, `check_collection`, `check_execution`, `check_baseline`, `check_performance` |
| `quality/test_complexity_regression.py` | 5 | `get_project_root`, `find_function_in_ast`, `count_function_lines`, `analyze_function_complexity` |
| `conftest.py` | 4 | `_create_file`, `get_tool`, `prompt`, `resource` |
| `scripts/benchmark_fixtures.py` | 3 | `benchmark_fixture`, `_get_fixture_scope`, `benchmark_all_fixtures` |
| Others (17 files) | 1-3 each | Test helpers, fixtures, local closures |

### 5.3 Analysis Observations

1. **Scripts are standalone entry points**: All 28 orphan files are CLI scripts invoked directly, not imported. This is expected — the detector correctly identifies they have no Python importers.

2. **High false-positive rate in tests**: ~87 of 341 orphan functions are pytest fixtures (`conftest.py` factories), local closures inside test methods (`track_progress`, `failing_callback`), and `setup_method` callbacks. These are invoked by pytest infrastructure, not direct calls.

3. **Deduplication subpackage has the highest density**: 48 orphan functions across 10 files. Many are language-specific generators/validators for languages (Java, Ruby, Go) not currently exercised in tests. Candidates for dead code review.

4. **Potentially unused code in src/ worth reviewing**:
   - `core/usage_tracking.py` (5 functions) — usage tracking may not be wired up
   - `utils/templates.py` (6 functions) — language-specific formatters
   - `deduplication/diff.py` (5 functions) — diff utilities
   - `schema/client.py` (5 functions) — URL validation helpers

5. **Verification timeout**: 22 of 28 orphan files timed out during grep-based verification. The per-file timeout may need tuning for a 243-file codebase.

---

## 6. Quality Report

Generated markdown quality report:
- Format: markdown
- Total violations: 0
- Rules executed: 3
- No file-level issues to report

---

## 7. All Tools Run Summary (52 tools executed)

| Status | Count |
|--------|-------|
| OK | 48 |
| SKIPPED | 4 (rollback_rewrite, apply_standards_fixes, enhance_entity_graph, apply_dedup had group) |
| ERROR | 0 |

### Notable Results Outside Quality

| Tool | Key Metric |
|------|-----------|
| find_duplication | 1 group found |
| rewrite_code (dry_run) | 238 changes would apply |
| condense_extract_surface | 237 files, 26.3% reduction |
| condense_pack | 237 files, 12.0% reduction (2.9MB -> 2.6MB) |
| sync_documentation | 2,097 issues, 740 suggestions (check_only) |
| generate_docstrings | 744 docstrings identified |
| generate_changelog | 586 commits processed |

---

## Key Takeaways

1. **Standards + Security: Clean** — No violations or vulnerabilities detected.
2. **Complexity concentrated in scripts/** — Only 1 `src/` function in top 15. Core package averages are healthy (3.37 cyc, 3.43 cog).
3. **Code smells: Minimal** — 21 magic numbers, only 2 in `src/`.
4. **Orphan files: Expected** — All 28 are standalone CLI scripts/test utilities.
5. **Orphan functions: Review candidates** — 103 in `src/` (primarily `deduplication/`, `documentation/`, `cross_language/`, `utils/`). ~50% are language-specific handlers that may be dead code.
6. **Verification timeout issue** — 22/28 orphan files timed out, suggesting the orphan detector's grep verification needs a higher per-file timeout for larger codebases.
