# utils

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "utils",
  "description": "Directory containing 9 code files with 4 classes and 91 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "4 class definitions",
    "91 function definitions"
  ]
}
</script>

## Overview

This directory contains 9 code file(s) with extracted schemas.

## Files and Schemas

### `backup.py` (python)

**Functions:**
- `get_file_hash(file_path) -> str` - Line 10
- `resolve_backup_dir(prefix, timestamp, backup_base_dir) -> tuple[...]` - Line 26
- `copy_file_to_backup(file_path, project_folder, backup_dir, original_hashes) -> <ast.BinOp object at 0x107f882e0>` - Line 49
- `restore_file_from_backup(backup_path, original_path, make_parents) -> <ast.BinOp object at 0x10803b9d0>` - Line 88

**Key Imports:** `hashlib`, `os`, `pathlib`, `shutil`, `typing`

### `console_logger.py` (python)

**Classes:**
- `ConsoleLogger` - Line 42
  - Simple console logger for scripts and CLI tools.
  - Methods: __init__, set_quiet, set_verbose, log, info (+9 more)

**Functions:**
- `log(message) -> <ast.Constant object at 0x107ccc220>` - Line 205
- `error(message) -> <ast.Constant object at 0x107ccceb0>` - Line 210
- `success(message) -> <ast.Constant object at 0x107cccd90>` - Line 215

**Key Imports:** `ast_grep_mcp.constants`, `json`, `sys`, `typing`

### `formatters.py` (python)

**Classes:**
- `FileDiff` - Line 20
  - Represents a diff for a single file.
- `DiffPreview` - Line 45
  - Container for multi-file diff preview.
- `ImportSection` - Line 508
  - Container for organized import statements.
  - Methods: has_imports, format_sorted

**Functions:**
- `format_matches_as_text(matches) -> str` - Line 65
- `_colorize_diff_line(line) -> str` - Line 105
- `format_diff_with_colors(diff) -> str` - Line 117
- `_number_lines(lines) -> str` - Line 135
- `_extraction_explanation(function_name, original_line_count, replacement_line_count, lines_saved) -> str` - Line 139
- `generate_before_after_example(original_code, replacement_code, function_name) -> Dict[...]` - Line 149
- `_complexity_level(score) -> Tuple[...]` - Line 224
- `visualize_complexity(score) -> Dict[...]` - Line 232
- `_prepare_lines_for_diff(lines) -> List[...]` - Line 264
- `_parse_hunk_header(line) -> Dict[...]` - Line 278
- ... and 31 more functions

**Key Imports:** `ast_grep_mcp.constants`, `black`, `dataclasses`, `difflib`, `os` (+5 more)

### `parsing.py` (python)

**Functions:**
- `detect_triple_quote(line) -> Optional[...]` - Line 15
- `skip_blank_lines(lines, start) -> int` - Line 24

**Key Imports:** `typing`

### `slicing.py` (python)

**Functions:**
- `take_top_n(items, limit) -> list[...]` - Line 10

**Key Imports:** `collections.abc`, `itertools`, `typing`

### `syntax_validation.py` (python)

**Functions:**
- `_find_error_suggestion(error_lower) -> Optional[...]` - Line 28
- `suggest_syntax_fix(error, language, context) -> str` - Line 44
- `validate_bracket_balance(code) -> List[...]` - Line 72
- `validate_python_syntax(code) -> Tuple[...]` - Line 94
- `validate_javascript_syntax(code) -> Tuple[...]` - Line 117
- `validate_java_syntax(code) -> Tuple[...]` - Line 135
- `validate_code_for_language(code, language) -> Tuple[...]` - Line 162

**Key Imports:** `ast`, `ast_grep_mcp.constants`, `typing`

### `templates.py` (python)

**Functions:**
- `_ensure_python_indent(methods) -> str` - Line 26
- `format_python_class(name, methods, decorators, bases, docstring, class_vars) -> str` - Line 32
- `_try_google_java_format(code) -> Optional[...]` - Line 72
- `_java_import_sort_key(imp) -> tuple[...]` - Line 111
- `_classify_java_line(line, in_imports, import_lines, non_import_lines) -> bool` - Line 120
- `_process_java_imports(lines) -> tuple[...]` - Line 141
- `_merge_package_imports_code(import_lines, non_import_lines) -> list[...]` - Line 161
- `_compute_java_indent(stripped, indent_level) -> tuple[...]` - Line 191
- `_apply_java_indentation(lines) -> str` - Line 202
- `format_java_code(code) -> str` - Line 227
- ... and 13 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.utils.text`, `os`, `re`, `shutil` (+3 more)

### `text.py` (python)

**Functions:**
- `normalize_code(code, language) -> str` - Line 24
- `calculate_similarity(code1, code2, language) -> float` - Line 44
- `_trim_surrounding_blanks(lines) -> list[...]` - Line 69
- `clean_template_whitespace(template) -> str` - Line 77
- `_collapse_blank_lines(lines) -> list[...]` - Line 96
- `indent_lines(text, prefix) -> list[...]` - Line 109
- `read_file_lines(file_path) -> list[...]` - Line 125
- `write_file_lines(file_path, lines) -> <ast.Constant object at 0x109772700>` - Line 144

**Key Imports:** `difflib`, `os`, `tempfile`, `typing`

### `tool_context.py` (python)

**Functions:**
- `_handle_tool_error(tool_name, start_time, e, sentry_extras) -> <ast.Constant object at 0x10802f610>` - Line 13
- `tool_context(tool_name) -> Generator[...]` - Line 36

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `contextlib`, `sentry_sdk`, `time` (+1 more)

---
*Generated by Enhanced Schema Generator with schema.org markup*