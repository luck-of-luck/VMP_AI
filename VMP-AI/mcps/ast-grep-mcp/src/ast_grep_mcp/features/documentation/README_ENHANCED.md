# documentation

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "documentation",
  "description": "Directory containing 6 code files with 5 classes and 144 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "5 class definitions",
    "144 function definitions"
  ]
}
</script>

## Overview

This directory contains 6 code file(s) with extracted schemas.

## Files and Schemas

### `api_docs_generator.py` (python)

**Classes:**
- `RouteParser` (extends: Protocol) - Line 125
  - Protocol for route parsers.
  - Methods: parse_file
- `ExpressRouteParser` - Line 133
  - Parse Express.js routes.
  - Methods: parse_file, _extract_path_params
- `FastAPIRouteParser` - Line 176
  - Parse FastAPI routes.
  - Methods: _find_func_line, _parse_handler, parse_file, _extract_path_params, _param_from_part (+1 more)
- `FlaskRouteParser` - Line 264
  - Parse Flask routes.
  - Methods: parse_file, _parse_decorator_match, _find_next_handler_name, _build_routes_for_methods, _extract_path_params

**Functions:**
- `_detect_js_api_framework(project_folder) -> Optional[...]` - Line 48
- `_read_file_lower(filepath) -> str` - Line 74
- `_detect_python_api_framework(project_folder) -> Optional[...]` - Line 83
- `_detect_framework(project_folder, language) -> Optional[...]` - Line 101
- `_group_routes_by_prefix(routes) -> Dict[...]` - Line 336
- `_markdown_param_table(route) -> List[...]` - Line 345
- `_markdown_default_responses() -> List[...]` - Line 361
- `_markdown_route_section(route) -> List[...]` - Line 375
- `_generate_markdown_docs(routes, framework) -> str` - Line 388
- `_build_openapi_param(param) -> Dict[...]` - Line 406
- ... and 9 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.documentation`, `json`, `os` (+4 more)

### `changelog_generator.py` (python)

**Functions:**
- `_run_git_command(project_folder, args) -> Tuple[...]` - Line 32
- `_resolve_version_ref(project_folder, version) -> str` - Line 59
- `_get_first_commit(project_folder) -> <ast.BinOp object at 0x10637e9a0>` - Line 87
- `_find_previous_tag(project_folder, exclude_ref) -> <ast.BinOp object at 0x106347730>` - Line 100
- `_get_commit_range(project_folder, from_version, to_version) -> Tuple[...]` - Line 121
- `_get_commits(project_folder, from_ref, to_ref) -> List[...]` - Line 149
- `_parse_conventional_commit(subject, body) -> Dict[...]` - Line 216
- `_map_commit_type_to_change_type(commit_type) -> ChangeType` - Line 266
- `_group_commits_by_version(commits, project_folder, to_version) -> List[...]` - Line 306
- `_format_changelog_entry(entry) -> str` - Line 388
- ... and 6 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.documentation`, `datetime`, `os` (+4 more)

### `docstring_generator.py` (python)

**Classes:**
- `FunctionSignatureParser` - Line 466
  - Parse function signatures from source code.
  - Methods: __init__, parse_file, _collect_decorators, _build_python_sig, _parse_python_functions (+17 more)

**Functions:**
- `_split_camel_case(name) -> List[...]` - Line 33
- `_split_snake_case(name) -> List[...]` - Line 40
- `_infer_description_from_name(name) -> str` - Line 124
- `_build_prefix_description(first_word, rest_words, prefix_meanings) -> str` - Line 138
- `_check_suffix_pattern(name) -> Optional[...]` - Line 311
- `_check_prefix_pattern(name) -> Optional[...]` - Line 320
- `_infer_parameter_description(param, function_context) -> str` - Line 329
- `_get_return_from_type(return_type) -> str` - Line 369
- `_apply_return_prefix_handler(template, rest, return_type) -> str` - Line 378
- `_function_name_words(function_name) -> List[...]` - Line 385
- ... and 25 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.documentation`, `ast_grep_mcp.utils.text`, `glob` (+5 more)

### `readme_generator.py` (python)

**Functions:**
- `_parse_json_metadata(file_path) -> Tuple[...]` - Line 31
- `_parse_toml_metadata(file_path) -> Tuple[...]` - Line 41
- `_parse_go_mod(file_path) -> Tuple[...]` - Line 53
- `_detect_js_package_manager(project_folder) -> str` - Line 64
- `_detect_python_package_manager(project_folder) -> str` - Line 73
- `_detect_package_manager(project_folder) -> Tuple[...]` - Line 82
- `_count_extensions(project_folder) -> Dict[...]` - Line 143
- `_detect_language(project_folder) -> str` - Line 154
- `_detect_js_frameworks(project_folder) -> List[...]` - Line 197
- `_read_file_lower(filepath) -> str` - Line 226
- ... and 28 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.documentation`, `json`, `os` (+4 more)

### `sync_checker.py` (python)

**Functions:**
- `_extract_google_style_params(docstring) -> List[...]` - Line 32
- `_extract_numpy_style_params(docstring) -> List[...]` - Line 43
- `_extract_python_docstring_params(docstring) -> List[...]` - Line 54
- `_extract_js_docstring_params(docstring) -> List[...]` - Line 70
- `_extract_docstring_params(docstring, language) -> List[...]` - Line 82
- `_extract_docstring_return(docstring, language) -> bool` - Line 107
- `_make_issue(func, issue_type, description, severity, suggested_fix) -> DocSyncIssue` - Line 120
- `_check_param_sync(func, language) -> List[...]` - Line 138
- `_check_return_sync(func, language) -> List[...]` - Line 158
- `_check_docstring_sync(func, language) -> List[...]` - Line 171
- ... and 14 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.documentation`, `docstring_generator`, `glob` (+5 more)

### `tools.py` (python)

**Functions:**
- `_format_docstrings_response(result) -> Dict[...]` - Line 28
- `_format_readme_response(result) -> Dict[...]` - Line 53
- `_format_changelog_version(v) -> Dict[...]` - Line 71
- `_format_sync_doc_coverage(result) -> <ast.BinOp object at 0x10979dd30>` - Line 94
- `_format_sync_response(result) -> Dict[...]` - Line 100
- `generate_docstrings_tool(project_folder, file_pattern, language, style, overwrite_existing, dry_run, skip_private) -> Dict[...]` - Line 133
- `generate_readme_sections_tool(project_folder, language, sections, include_examples) -> Dict[...]` - Line 174
- `_format_route_for_output(route) -> Dict[...]` - Line 210
- `generate_api_docs_tool(project_folder, language, framework, output_format, include_examples) -> Dict[...]` - Line 229
- `generate_changelog_tool(project_folder, from_version, to_version, changelog_format, group_by) -> Dict[...]` - Line 271
- ... and 2 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.features.documentation.api_docs_generator`, `ast_grep_mcp.features.documentation.changelog_generator`, `ast_grep_mcp.features.documentation.docstring_generator` (+8 more)

---
*Generated by Enhanced Schema Generator with schema.org markup*