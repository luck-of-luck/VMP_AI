# condense

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "condense",
  "description": "Directory containing 8 code files with 30 classes and 1 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "30 class definitions",
    "1 function definitions"
  ]
}
</script>

## Overview

This directory contains 8 code file(s) with extracted schemas.

## Files and Schemas

### `test_condense_tools.py` (python)

**Classes:**
- `TestExtractSurfaceTool` - Line 65
  - Methods: test_nonexistent_path_returns_error, test_valid_directory_returns_expected_keys, test_single_file_path, test_empty_directory
- `TestNormalizeTool` - Line 98
  - Methods: test_nonexistent_path_raises, test_directory_path_raises, test_valid_file_returns_expected_keys, test_js_normalization_applies
- `TestStripTool` - Line 133
  - Methods: test_nonexistent_path_raises, test_directory_path_raises, test_valid_file_returns_expected_keys, test_strips_print_statement, test_js_strips_console_log
- `TestPackTool` - Line 174
  - Methods: test_invalid_strategy_returns_error_with_descriptions, test_all_valid_strategies_accepted, test_valid_call_returns_expected_keys, test_nonexistent_path_returns_error, test_default_strategy_is_ai_analysis
- `TestEstimateTool` - Line 225
  - Methods: test_nonexistent_path_returns_error, test_valid_directory_returns_expected_keys, test_language_filter, test_empty_directory
- `TestTrainDictionaryTool` - Line 268
  - Methods: test_nonexistent_path_returns_error, test_file_path_returns_error, test_empty_directory_returns_error, test_successful_training_mocked, test_returns_error_dict_not_exception
- `TestRegisterCondenseTools` - Line 315
  - Methods: test_all_tools_registered
- `MockMCP` - Line 319
  - Methods: __init__, tool

**Functions:**
- `_write_project(tmp, files) -> <ast.Constant object at 0x107ccd2b0>` - Line 54

**Key Imports:** `ast_grep_mcp.features.condense.tools`, `pathlib`, `pytest`, `tempfile`, `unittest.mock` (+0 more)

### `test_dictionary.py` (python)

**Classes:**
- `TestTrainDictionaryImpl` - Line 14
  - Methods: test_nonexistent_path_returns_error, test_file_path_returns_error, test_empty_directory_returns_error, test_no_code_files_returns_error, test_successful_training_mocked (+2 more)
- `TestSelectSamples` - Line 100
  - Methods: test_respects_sample_count_limit, test_skips_oversized_files, test_empty_list
- `TestEstimateImprovement` - Line 125
  - Methods: test_few_samples_returns_low_estimate, test_moderate_samples, test_many_samples_returns_full_benefit

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.features.condense.dictionary`, `pathlib`, `tempfile`, `unittest.mock`

### `test_estimator.py` (python)

**Classes:**
- `TestEstimateCondensationImpl` - Line 14
  - Methods: test_nonexistent_path_returns_error, test_empty_directory, test_single_python_file, test_multiple_strategies_returned, test_token_estimates_proportional (+3 more)
- `TestCollectFiles` - Line 79
  - Methods: test_skips_image_extensions, test_language_filter
- `TestLanguageToExtensions` - Line 97
  - Methods: test_python, test_typescript, test_unknown_falls_back_to_code_extensions
- `TestRankReductionCandidates` - Line 114
  - Methods: test_empty_returns_empty, test_returns_sorted_by_lines, test_reducible_pct_sums_to_100

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.features.condense.estimator`, `pathlib`, `tempfile`

### `test_normalizer.py` (python)

**Classes:**
- `TestNormalizeSource` - Line 11
  - Methods: test_returns_tuple, test_count_is_non_negative, test_unknown_language_returns_source, test_strips_multiple_blank_lines
- `TestNormalizeJsTs` - Line 33
  - Methods: test_double_to_single_quotes, test_skips_strings_with_single_quotes, test_trailing_comma_removed, test_no_change_returns_zero_count
- `TestNormalizePython` - Line 58
  - Methods: test_trailing_whitespace_removed, test_no_trailing_whitespace_zero_count
- `TestDoubleToSingleQuotes` - Line 72
  - Methods: test_simple_string, test_string_with_single_quote_unchanged, test_empty_string, test_no_double_quotes

**Key Imports:** `ast_grep_mcp.features.condense.normalizer`

### `test_pack_pipeline.py` (python)

**Classes:**
- `TestCondensePackImpl` - Line 9
  - Methods: test_nonexistent_path_returns_error, test_empty_directory, test_python_ai_analysis_strategy, test_all_strategies_complete, test_reduction_pct_zero_on_empty (+5 more)

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.features.condense.service`, `pathlib`, `tempfile`

### `test_strategies.py` (python)

**Classes:**
- `TestValidStrategies` - Line 12
  - Methods: test_all_expected_strategies_present, test_reduction_ratios_in_range, test_ai_chat_highest_reduction, test_archival_lowest_reduction
- `TestValidateStrategy` - Line 31
  - Methods: test_known_strategy_returns_true, test_unknown_strategy_returns_false
- `TestDescribeStrategy` - Line 42
  - Methods: test_known_strategy_returns_string, test_unknown_strategy_returns_error_string, test_descriptions_not_empty

**Key Imports:** `ast_grep_mcp.features.condense.strategies`

### `test_strip.py` (python)

**Classes:**
- `TestStripDeadCode` - Line 10
  - Methods: test_returns_tuple, test_unknown_language_returns_source
- `TestStripJsTs` - Line 23
  - Methods: test_removes_console_log, test_removes_console_debug, test_removes_debugger, test_preserves_real_code, test_console_log_in_string_not_removed (+1 more)
- `TestStripPython` - Line 66
  - Methods: test_removes_print, test_removes_breakpoint, test_removes_pdb_set_trace, test_removes_import_pdb, test_preserves_real_code (+1 more)

**Key Imports:** `ast_grep_mcp.features.condense.strip`

### `test_surface_extraction.py` (python)

**Classes:**
- `TestExtractSurfaceImpl` - Line 14
  - Methods: test_nonexistent_path_returns_error, test_single_python_file, test_reduction_pct_in_range, test_empty_directory_returns_zero_files
- `TestExtractPythonSurface` - Line 43
  - Methods: test_keeps_function_definitions, test_keeps_class_definitions, test_includes_docstring_when_requested, test_excludes_body_lines
- `TestExtractJsTsSurface` - Line 78
  - Methods: test_keeps_export_function, test_internal_function_excluded, test_fallback_when_no_exports
- `TestExtractGenericSurface` - Line 110
  - Methods: test_keeps_declaration_lines, test_empty_input

**Key Imports:** `ast_grep_mcp.features.condense.service`, `pathlib`, `tempfile`

---
*Generated by Enhanced Schema Generator with schema.org markup*