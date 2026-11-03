"""Utilities module for ast-grep MCP server.

This module provides various utility functions for:
- Code generation templates
- Text formatting and display
- String manipulation and similarity
- Configuration validation
"""

# Template utilities
# Formatting utilities
from .formatters import (
    DiffPreview,
    FileDiff,
    format_diff_with_colors,
    format_matches_as_text,
    generate_before_after_example,
    generate_file_diff,
    generate_multi_file_diff,
    visualize_complexity,
)
from .slicing import (
    take_top_n,
)
from .templates import (
    JAVA_METHOD_TEMPLATE,
    JAVASCRIPT_ARROW_FUNCTION_TEMPLATE,
    JAVASCRIPT_ASYNC_FUNCTION_TEMPLATE,
    JAVASCRIPT_FUNCTION_TEMPLATE,
    # Templates
    PYTHON_CLASS_TEMPLATE,
    TYPESCRIPT_ARROW_FUNCTION_TEMPLATE,
    TYPESCRIPT_ASYNC_FUNCTION_TEMPLATE,
    TYPESCRIPT_CLASS_TEMPLATE,
    TYPESCRIPT_FUNCTION_TEMPLATE,
    # Java formatting
    format_java_code,
    format_java_method,
    # JavaScript formatting
    format_javascript_function,
    # Python formatting
    format_python_class,
    # TypeScript formatting
    format_typescript_class,
    format_typescript_function,
)

# Text utilities
from .text import (
    _clean_template_whitespace,
    calculate_similarity,
    clean_template_whitespace,
    indent_lines,
    normalize_code,
    read_file_lines,
    write_file_lines,
)

# Validation utilities
from .validation import (
    validate_config_file,
)

__all__ = [
    # Templates
    "PYTHON_CLASS_TEMPLATE",
    "JAVA_METHOD_TEMPLATE",
    "TYPESCRIPT_CLASS_TEMPLATE",
    "TYPESCRIPT_FUNCTION_TEMPLATE",
    "TYPESCRIPT_ASYNC_FUNCTION_TEMPLATE",
    "TYPESCRIPT_ARROW_FUNCTION_TEMPLATE",
    "JAVASCRIPT_FUNCTION_TEMPLATE",
    "JAVASCRIPT_ASYNC_FUNCTION_TEMPLATE",
    "JAVASCRIPT_ARROW_FUNCTION_TEMPLATE",
    # Template formatting functions
    "format_python_class",
    "format_java_code",
    "format_java_method",
    "format_typescript_class",
    "format_typescript_function",
    "format_javascript_function",
    # Formatters
    "format_matches_as_text",
    "format_diff_with_colors",
    "generate_before_after_example",
    "visualize_complexity",
    "generate_file_diff",
    "generate_multi_file_diff",
    "FileDiff",
    "DiffPreview",
    # Slicing utilities
    "take_top_n",
    # Text utilities
    "normalize_code",
    "calculate_similarity",
    "clean_template_whitespace",
    "_clean_template_whitespace",
    "indent_lines",
    "read_file_lines",
    "write_file_lines",
    # Validation
    "validate_config_file",
]
