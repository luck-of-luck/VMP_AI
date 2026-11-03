# cross_language

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "cross_language",
  "description": "Directory containing 7 code files with 0 classes and 104 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "104 function definitions"
  ]
}
</script>

## Overview

This directory contains 7 code file(s) with extracted schemas.

## Files and Schemas

### `binding_generator.py` (python)

**Functions:**
- `_to_camel_case(name) -> str` - Line 54
- `_to_pascal_case(name) -> str` - Line 60
- `_parse_parameter(param) -> Dict[...]` - Line 71
- `_parse_request_body(operation) -> Optional[...]` - Line 82
- `_parse_responses(operation) -> Dict[...]` - Line 92
- `_parse_operation(path, method, operation) -> Optional[...]` - Line 105
- `_parse_openapi_spec(spec) -> Tuple[...]` - Line 127
- `_load_api_spec(file_path) -> Tuple[...]` - Line 148
- `_parse_spec_content(content, suffix) -> Dict[...]` - Line 165
- `_classify_parameters(parameters, type_converter) -> Tuple[...]` - Line 188
- ... and 16 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.cross_language`, `json`, `pathlib` (+4 more)

### `language_converter.py` (python)

**Functions:**
- `_apply_single_pattern(result, pattern, replacement, name, applied) -> str` - Line 172
- `_apply_patterns(code, patterns) -> Tuple[...]` - Line 189
- `_try_replace_type(result, source_type, target_type) -> Tuple[...]` - Line 209
- `_convert_types(code, type_mappings) -> Tuple[...]` - Line 216
- `_indent_python_line(stripped, indent_level) -> Tuple[...]` - Line 233
- `_process_python_line(stripped, indent_level, result_lines) -> int` - Line 243
- `_indent_python_lines(lines) -> List[...]` - Line 252
- `_add_indentation_fixes(code, to_language) -> str` - Line 260
- `_make_warning(message, line_num) -> ConversionWarning` - Line 283
- `_generate_warnings(source_code, from_language, to_language, applied_patterns) -> List[...]` - Line 287
- ... and 5 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.cross_language.pattern_database`, `ast_grep_mcp.models.cross_language`, `re` (+2 more)

### `multi_language_search.py` (python)

**Functions:**
- `_detect_semantic_group(snippet) -> str` - Line 133
- `_group_by_semantic(matches, semantic_query) -> List[...]` - Line 145
- `_detect_languages(project_folder) -> List[...]` - Line 160
- `_get_ast_grep_pattern(semantic, language) -> Optional[...]` - Line 174
- `_parse_match(match_data, language) -> MultiLanguageMatch` - Line 180
- `_search_language(project_folder, language, pattern, max_results) -> List[...]` - Line 192
- `_parse_semantic_query(query) -> str` - Line 259
- `_resolve_languages(project_folder, languages) -> List[...]` - Line 275
- `_submit_language_futures(executor, project_folder, languages, semantic_key, max_results_per_language) -> Dict[...]` - Line 283
- `_collect_future_results(futures) -> tuple[...]` - Line 306
- ... and 2 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.executor`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.cross_language`, `concurrent.futures` (+5 more)

### `pattern_database.py` (python)

**Functions:**
- `get_pattern(pattern_id) -> <ast.BinOp object at 0x10567bdf0>` - Line 654
- `search_patterns(query, category) -> List[...]` - Line 666
- `get_equivalents(pattern_id, source_language, target_languages) -> <ast.BinOp object at 0x1056c3700>` - Line 694
- `get_type_mapping(from_lang, to_lang) -> Dict[...]` - Line 729

**Key Imports:** `constants`, `typing`

### `pattern_equivalence.py` (python)

**Functions:**
- `_example_from_data(lang, ex_data) -> Optional[...]` - Line 28
- `_build_examples(pattern_data, target_languages) -> List[...]` - Line 41
- `_complexity_label(lines) -> str` - Line 55
- `_build_complexity_comparison(examples) -> Dict[...]` - Line 63
- `_create_pattern_equivalence(pattern_id, pattern_data, target_languages) -> PatternEquivalence` - Line 67
- `_direct_match_patterns(query_lower) -> List[...]` - Line 94
- `_word_match_patterns(query_lower) -> List[...]` - Line 104
- `_fuzzy_match_pattern(query) -> List[...]` - Line 116
- `_related_suggestions(found_patterns) -> List[...]` - Line 132
- `_category_suggestions(found_patterns, category) -> List[...]` - Line 143
- ... and 6 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.cross_language.pattern_database`, `ast_grep_mcp.features.deduplication.scoring_scales`, `ast_grep_mcp.models.cross_language` (+3 more)

### `polyglot_refactoring.py` (python)

**Functions:**
- `_find_files_with_language(project_folder, languages) -> Dict[...]` - Line 94
- `_match_pattern_type(line, patterns, symbol) -> Optional[...]` - Line 118
- `_find_symbol_occurrences(file_path, symbol, language) -> List[...]` - Line 127
- `_create_rename_change(file_path, line_number, original_line, symbol, new_name, language) -> PolyglotChange` - Line 159
- `_collect_changes_for_file(file_path, symbol_name, new_name, language) -> List[...]` - Line 180
- `_collect_all_changes(files_by_language, symbol_name, new_name) -> List[...]` - Line 195
- `_analyze_risks(changes, symbol, new_name) -> List[...]` - Line 217
- `_check_config_file(file_path, symbol) -> Optional[...]` - Line 249
- `_identify_manual_review(project_folder, symbol, languages) -> List[...]` - Line 258
- `_apply_changes_to_file(file_path, file_changes) -> bool` - Line 281
- ... and 5 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.cross_language`, `ast_grep_mcp.utils.text`, `os` (+4 more)

### `tools.py` (python)

**Functions:**
- `_format_example(ex) -> Dict[...]` - Line 40
- `_format_equivalence(e) -> Dict[...]` - Line 50
- `_format_equivalents_result(result) -> Dict[...]` - Line 63
- `_format_type_mapping(t) -> Dict[...]` - Line 75
- `_format_warning(w) -> Dict[...]` - Line 80
- `_format_conversion(c) -> Dict[...]` - Line 90
- `_format_conversion_result(result) -> Dict[...]` - Line 105
- `_format_search_result(result) -> Dict[...]` - Line 121
- `search_multi_language_tool(project_folder, semantic_pattern, languages, group_by, max_results_per_language) -> Dict[...]` - Line 143
- `find_language_equivalents_tool(pattern_description, source_language, target_languages) -> Dict[...]` - Line 175
- ... and 6 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.cross_language.binding_generator`, `ast_grep_mcp.features.cross_language.language_converter`, `ast_grep_mcp.features.cross_language.multi_language_search` (+8 more)

---
*Generated by Enhanced Schema Generator with schema.org markup*