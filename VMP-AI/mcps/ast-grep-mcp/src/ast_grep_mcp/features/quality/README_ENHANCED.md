# quality

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "quality",
  "description": "Directory containing 11 code files with 9 classes and 140 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "9 class definitions",
    "140 function definitions"
  ]
}
</script>

## Overview

This directory contains 11 code file(s) with extracted schemas.

## Files and Schemas

### `enforcer.py` (python)

**Functions:**
- `template_to_linting_rule(template) -> LintingRule` - Line 92
- `load_custom_rules(project_folder, language) -> List[...]` - Line 114
- `_load_rules_from_templates(rule_ids, language) -> List[...]` - Line 136
- `_load_all_rules(language, logger) -> RuleSet` - Line 155
- `_load_custom_rule_set(project_folder, language, logger) -> RuleSet` - Line 175
- `_load_builtin_rule_set(rule_set_name, language, logger) -> RuleSet` - Line 191
- `load_rule_set(rule_set_name, project_folder, language) -> RuleSet` - Line 218
- `_extract_single_meta_vars(meta_data) -> Dict[...]` - Line 249
- `_extract_multi_meta_vars(meta_data) -> Dict[...]` - Line 256
- `_extract_meta_vars(match) -> Any` - Line 263
- ... and 24 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.executor`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.quality.rules`, `ast_grep_mcp.models.standards` (+8 more)

### `fixer.py` (python)

**Functions:**
- `classify_fix_safety(rule_id, violation) -> FixValidation` - Line 65
- `_splice_fixed_code(lines, start_line, end_line, snippet, fixed_code) -> List[...]` - Line 106
- `apply_pattern_fix(file_path, violation, fix_pattern, language) -> FixResult` - Line 149
- `_apply_fix_pattern(code, fix_pattern, meta_vars) -> str` - Line 247
- `apply_removal_fix(file_path, violation, language) -> FixResult` - Line 269
- `apply_fixes_batch(violations, language, project_folder, fix_types, dry_run, create_backup_flag) -> FixBatchResult` - Line 357
- `_execute_dry_run(fixable_violations, start_time) -> FixBatchResult` - Line 405
- `_create_backup_if_needed(fixable_violations, project_folder, create_backup_flag) -> Optional[...]` - Line 446
- `_group_violations_by_file(fixable_violations) -> Dict[...]` - Line 471
- `_execute_real_run(violations_by_file, language) -> Tuple[...]` - Line 488
- ... and 13 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.rewrite.backup`, `ast_grep_mcp.features.rewrite.service`, `ast_grep_mcp.models.standards` (+4 more)

### `orphan_detector.py` (python)

**Classes:**
- `OrphanDetector` - Line 31
  - Detects orphan files and functions in a codebase.
  - Methods: __init__, analyze, _build_dependency_graph, _should_exclude, _matches_exclude_pattern (+35 more)

**Functions:**
- `_build_orphan_config(include_patterns, exclude_patterns, analyze_functions, verify_with_grep) -> OrphanAnalysisConfig` - Line 616
- `detect_orphans_impl(project_folder, include_patterns, exclude_patterns, analyze_functions, verify_with_grep) -> Dict[...]` - Line 633

**Key Imports:** `ast`, `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.orphan`, `concurrent.futures` (+6 more)

### `reporter.py` (python)

**Functions:**
- `_generate_report_header(project_name, result) -> List[...]` - Line 25
- `_generate_summary_section(result) -> List[...]` - Line 44
- `_format_violation_entry(violation) -> str` - Line 67
- `_generate_rule_violations_section(rule_id, rule_violations, include_violations, max_violations_per_rule) -> List[...]` - Line 80
- `_generate_violations_by_severity_section(result, include_violations, max_violations_per_rule) -> List[...]` - Line 115
- `_get_most_common_severity(violations) -> str` - Line 152
- `_generate_top_issues_table(result) -> List[...]` - Line 165
- `_count_violations_by_severity(violations) -> tuple[...]` - Line 186
- `_generate_problematic_files_table(result) -> List[...]` - Line 201
- `_generate_recommendations_section(result) -> List[...]` - Line 229
- ... and 8 more functions

**Key Imports:** `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.standards`, `datetime`, `json`, `pathlib` (+1 more)

### `rules.py` (python)

**Functions:**
- `get_available_templates(language, category) -> List[...]` - Line 363
- `create_rule_from_template(template_id, rule_id, overrides) -> LintingRule` - Line 384
- `save_rule_to_project(rule, project_folder) -> str` - Line 417
- `load_rule_from_file(file_path) -> LintingRule` - Line 461
- `load_rules_from_project(project_folder) -> List[...]` - Line 503
- `delete_rule_from_project(rule_id, project_folder) -> bool` - Line 532

**Key Imports:** `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.standards`, `pathlib`, `sentry_sdk`, `typing` (+1 more)

### `security_scanner.py` (python)

**Functions:**
- `_match_to_issue(match, pattern_def) -> SecurityIssue` - Line 291
- `scan_for_vulnerability(project_folder, language, patterns) -> List[...]` - Line 309
- `scan_for_secrets_regex(project_folder, language) -> List[...]` - Line 335
- `_get_language_extensions(language) -> List[...]` - Line 359
- `_should_skip_file(file_path) -> bool` - Line 372
- `_scan_files_for_secrets(project_path, ext) -> List[...]` - Line 385
- `_scan_single_file_for_secrets(file_path) -> List[...]` - Line 407
- `_scan_lines_for_pattern(lines, pattern_def, file_path) -> List[...]` - Line 434
- `_create_secret_issue(file_path, line_num, line, match, pattern_def) -> SecurityIssue` - Line 457
- `_scan_for_issue_type(issue_type, config, project_folder, language) -> List[...]` - Line 492
- ... and 5 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.executor`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.standards`, `copy` (+5 more)

### `smells.py` (python)

**Functions:**
- `_run_parallel_analysis(analyzer, files_to_analyze, normalized_language, project_path, max_threads) -> List[...]` - Line 32
- `detect_code_smells_impl(project_folder, language, include_patterns, exclude_patterns, long_function_lines, parameter_count, nesting_depth, class_lines, class_methods, detect_magic_numbers, severity_filter, max_threads) -> Dict[...]` - Line 45
- `_create_detectors(long_function_lines, parameter_count, nesting_depth, class_lines, class_methods, detect_magic_numbers) -> List[...]` - Line 89

**Key Imports:** `ast_grep_mcp.features.quality.smells_detectors`, `ast_grep_mcp.features.quality.smells_helpers`, `concurrent.futures`, `typing`

### `smells_detectors.py` (python)

**Classes:**
- `SmellInfo` - Line 24
  - Information about a detected code smell.
  - Methods: to_dict
- `SmellDetector` (extends: ABC) - Line 52
  - Base class for smell detectors.
  - Methods: __init__, detect
- `LongFunctionDetector` (extends: SmellDetector) - Line 75
  - Detects functions that are too long.
  - Methods: __init__, detect, _check_func
- `ParameterBloatDetector` (extends: SmellDetector) - Line 113
  - Detects functions with too many parameters.
  - Methods: __init__, detect, _check_func, _count_parameters, _extract_param_string (+1 more)
- `DeepNestingDetector` (extends: SmellDetector) - Line 187
  - Detects excessive nesting depth in functions.
  - Methods: __init__, detect, _check_func
- `LargeClassDetector` (extends: SmellDetector) - Line 225
  - Detects classes that are too large.
  - Methods: __init__, detect, _build_reason, _check_class, _extract_classes (+7 more)
- `MagicNumberDetector` (extends: SmellDetector) - Line 414
  - Detects magic numbers in code.
  - Methods: __init__, _is_excluded, detect, _make_smell, _find_magic_numbers (+6 more)
- `SmellAnalyzer` - Line 584
  - Orchestrates smell detection across files.
  - Methods: __init__, analyze_file

**Key Imports:** `abc`, `ast`, `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.complexity.analyzer` (+8 more)

### `smells_helpers.py` (python)

**Functions:**
- `validate_smell_detection_inputs(project_folder, language, severity_filter) -> tuple[...]` - Line 15
- `_adjust_include_pattern(pattern, file_ext) -> str` - Line 52
- `_is_file_excluded(file_path, project_path, exclude_patterns) -> bool` - Line 62
- `find_smell_analysis_files(project_path, file_ext, include_patterns, exclude_patterns) -> List[...]` - Line 70
- `_severity_for_ratio(ratio) -> str` - Line 97
- `_severity_for_parameter_bloat(metric, threshold) -> str` - Line 105
- `_severity_for_deep_nesting(metric, threshold) -> str` - Line 113
- `calculate_smell_severity(metric, threshold, smell_type) -> str` - Line 122
- `format_smell_detection_response(project_folder, language, files_analyzed, smells, thresholds, severity_filter) -> Dict[...]` - Line 143
- `aggregate_smell_results(file_results) -> List[...]` - Line 192

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `fnmatch`, `pathlib`, `typing`

### `tools.py` (python)

**Functions:**
- `_create_rule_from_params(rule_name, description, pattern, severity, language, suggested_fix, note, use_template) -> LintingRule` - Line 41
- `_save_rule_if_requested(rule, save_to_project, project_folder, validation_result) -> Optional[...]` - Line 72
- `_format_rule_result(rule, validation_result, saved_path) -> Dict[...]` - Line 86
- `create_linting_rule_tool(rule_name, description, pattern, severity, language, suggested_fix, note, save_to_project, project_folder, use_template) -> Dict[...]` - Line 108
- `list_rule_templates_tool(language, category) -> Dict[...]` - Line 158
- `_get_default_exclude_patterns() -> List[...]` - Line 205
- `_validate_enforcement_inputs(severity_threshold, output_format) -> <ast.Constant object at 0x107f51100>` - Line 210
- `_format_enforcement_output(result, output_format) -> Dict[...]` - Line 219
- `enforce_standards_tool(project_folder, language, rule_set, custom_rules, include_patterns, exclude_patterns, severity_threshold, max_violations, max_threads, output_format) -> Dict[...]` - Line 257
- `_convert_violations_to_objects(violations) -> List[...]` - Line 315
- ... and 14 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.quality.enforcer`, `ast_grep_mcp.features.quality.fixer`, `ast_grep_mcp.features.quality.orphan_detector` (+15 more)

### `validator.py` (python)

**Functions:**
- `_classify_pattern_error(error_msg, errors, warnings, logger) -> <ast.Constant object at 0x10639e460>` - Line 30
- `validate_rule_pattern(pattern, language) -> RuleValidationResult` - Line 38
- `_validate_rule_fields(rule, errors, warnings) -> <ast.Constant object at 0x106371a60>` - Line 71
- `validate_rule_definition(rule) -> RuleValidationResult` - Line 96
- `validate_linting_rules_impl(rules, fail_fast) -> Dict[...]` - Line 124

**Key Imports:** `ast_grep_mcp.core.executor`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.standards`, `re`, `sentry_sdk` (+2 more)

---
*Generated by Enhanced Schema Generator with schema.org markup*