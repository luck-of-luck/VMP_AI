"""Language conversion implementation.

This module provides functionality to convert code snippets
between programming languages.
"""

import re
import time
from typing import Dict, List, Tuple

from ast_grep_mcp.constants import ConversionFactors, RegexCaptureGroups
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.features.cross_language.pattern_database import (
    get_type_mapping,
)
from ast_grep_mcp.models.cross_language import (
    SUPPORTED_CONVERSION_PAIRS,
    ConversionResult,
    ConversionStyle,
    ConversionWarning,
    ConvertedCode,
    TypeMapping,
)

logger = get_logger(__name__)


# =============================================================================
# Conversion Rules
# =============================================================================

# Python to TypeScript/JavaScript patterns
PYTHON_TO_TS_PATTERNS: List[Tuple[str, str, str]] = [
    # Function definitions
    (r"def\s+(\w+)\s*\((.*?)\)\s*(?:->.*?)?\s*:", r"function \1(\2) {", "function_def"),
    (r"async\s+def\s+(\w+)\s*\((.*?)\)\s*(?:->.*?)?\s*:", r"async function \1(\2) {", "async_function"),
    # Lambda to arrow function
    (r"lambda\s+([\w,\s]+):\s*(.+)", r"(\1) => \2", "lambda"),
    # Class definition
    (r"class\s+(\w+)(?:\(.*?\))?\s*:", r"class \1 {", "class_def"),
    # Control flow
    (r"if\s+(.+):", r"if (\1) {", "if_statement"),
    (r"elif\s+(.+):", r"} else if (\1) {", "elif"),
    (r"else:", r"} else {", "else"),
    (r"for\s+(\w+)\s+in\s+(.+):", r"for (const \1 of \2) {", "for_in"),
    (r"for\s+(\w+),\s*(\w+)\s+in\s+enumerate\((.+)\):", r"for (const [\1, \2] of \3.entries()) {", "enumerate"),
    (r"while\s+(.+):", r"while (\1) {", "while"),
    # Exception handling
    (r"try:", r"try {", "try"),
    (r"except\s+(\w+)(?:\s+as\s+(\w+))?\s*:", r"} catch (\2) { // \1", "except"),
    (r"except:", r"} catch (e) {", "except_bare"),
    (r"finally:", r"} finally {", "finally"),
    (r"raise\s+(\w+)\((.*?)\)", r"throw new \1(\2)", "raise"),
    # Common functions
    (r"print\((.+)\)", r"console.log(\1)", "print"),
    (r"len\((.+)\)", r"\1.length", "len"),
    (r"range\((\d+)\)", r"[...Array(\1).keys()]", "range"),
    (r"range\((\d+),\s*(\d+)\)", r"[...Array(\2 - \1).keys()].map(i => i + \1)", "range_start"),
    (r"\.append\((.+)\)", r".push(\1)", "append"),
    (r"\.extend\((.+)\)", r".push(...\1)", "extend"),
    (r"str\((.+)\)", r"String(\1)", "str"),
    (r"int\((.+)\)", r"parseInt(\1)", "int"),
    (r"float\((.+)\)", r"parseFloat(\1)", "float"),
    # String formatting
    (r'f"(.+)"', r"`\1`", "f_string"),
    (r"f\'(.+)\'", r"`\1`", "f_string_single"),
    (r"\{(\w+)\}", r"${\1}", "f_string_var"),  # Within f-strings
    # Boolean/None
    (r"\bTrue\b", r"true", "true"),
    (r"\bFalse\b", r"false", "false"),
    (r"\bNone\b", r"null", "none"),
    # Comparison operators
    (r"\band\b", r"&&", "and"),
    (r"\bor\b", r"\|\|", "or"),
    (r"\bnot\b", r"!", "not"),
    (r"\bis\s+None\b", r"=== null", "is_none"),
    (r"\bis\s+not\s+None\b", r"!== null", "is_not_none"),
    # Self to this
    (r"\bself\.", r"this.", "self"),
    # List comprehension (simplified)
    (r"\[(.+)\s+for\s+(\w+)\s+in\s+(.+)\]", r"\3.map(\2 => \1)", "list_comp"),
    # Dict
    (r"dict\(\)", r"{}", "empty_dict"),
    (r"list\(\)", r"[]", "empty_list"),
    # Comments
    (r"#\s*(.+)", r"// \1", "comment"),
]

# TypeScript/JavaScript to Python patterns
TS_TO_PYTHON_PATTERNS: List[Tuple[str, str, str]] = [
    # Function definitions
    (r"function\s+(\w+)\s*\((.*?)\)\s*(?::\s*\w+)?\s*\{", r"def \1(\2):", "function_def"),
    (r"async\s+function\s+(\w+)\s*\((.*?)\)\s*(?::\s*\w+)?\s*\{", r"async def \1(\2):", "async_function"),
    # Arrow functions (multi-line)
    (r"const\s+(\w+)\s*=\s*(?:async\s+)?\((.*?)\)\s*(?::\s*\w+)?\s*=>\s*\{", r"def \1(\2):", "arrow_to_def"),
    # Arrow functions (single expression)
    (r"const\s+(\w+)\s*=\s*\((.*?)\)\s*=>\s*([^{].+);", r"\1 = lambda \2: \3", "arrow_lambda"),
    # Class definition
    (r"class\s+(\w+)\s*(?:extends\s+\w+)?\s*\{", r"class \1:", "class_def"),
    # Control flow
    (r"if\s*\((.+)\)\s*\{", r"if \1:", "if_statement"),
    (r"\}\s*else\s+if\s*\((.+)\)\s*\{", r"elif \1:", "else_if"),
    (r"\}\s*else\s*\{", r"else:", "else"),
    (r"for\s*\((?:const|let|var)\s+(\w+)\s+of\s+(.+)\)\s*\{", r"for \1 in \2:", "for_of"),
    (r"while\s*\((.+)\)\s*\{", r"while \1:", "while"),
    # Exception handling
    (r"try\s*\{", r"try:", "try"),
    (r"\}\s*catch\s*\((\w+)\)\s*\{", r"except Exception as \1:", "catch"),
    (r"\}\s*finally\s*\{", r"finally:", "finally"),
    (r"throw\s+new\s+(\w+)\((.*?)\);?", r"raise \1(\2)", "throw"),
    # Common functions
    (r"console\.log\((.+)\)", r"print(\1)", "console_log"),
    (r"(\w+)\.length", r"len(\1)", "length"),
    (r"\.push\((.+)\)", r".append(\1)", "push"),
    (r"String\((.+)\)", r"str(\1)", "string"),
    (r"parseInt\((.+)\)", r"int(\1)", "parseInt"),
    (r"parseFloat\((.+)\)", r"float(\1)", "parseFloat"),
    # Template literals
    (r"`([^`]+)`", r'f"\1"', "template_literal"),
    (r"\$\{(\w+)\}", r"{\1}", "template_var"),  # Within template literals
    # Boolean/null
    (r"\btrue\b", r"True", "true"),
    (r"\bfalse\b", r"False", "false"),
    (r"\bnull\b", r"None", "null"),
    (r"\bundefined\b", r"None", "undefined"),
    # Comparison operators
    (r"&&", r" and ", "and"),
    (r"\|\|", r" or ", "or"),
    (r"!", r"not ", "not"),
    (r"===\s*null", r"is None", "triple_equals_null"),
    (r"!==\s*null", r"is not None", "not_equals_null"),
    # This to self
    (r"\bthis\.", r"self.", "this"),
    # Comments
    (r"//\s*(.+)", r"# \1", "comment"),
    # Remove braces and semicolons
    (r"\{$", r"", "open_brace"),
    (r"^\s*\}", r"", "close_brace"),
    (r";$", r"", "semicolon"),
]

# Java to Kotlin patterns
JAVA_TO_KOTLIN_PATTERNS: List[Tuple[str, str, str]] = [
    # Variable declarations
    (r"(final\s+)?(\w+)\s+(\w+)\s*=\s*(.+);", r"val \3: \2 = \4", "val_decl"),
    (r"(\w+)\s+(\w+);", r"var \2: \1", "var_decl"),
    # Method to function
    (r"public\s+(\w+)\s+(\w+)\s*\((.*?)\)\s*\{", r"fun \2(\3): \1 {", "method"),
    (r"void\s+(\w+)\s*\((.*?)\)\s*\{", r"fun \1(\2) {", "void_method"),
    # Class
    (r"public\s+class\s+(\w+)\s*\{", r"class \1 {", "class"),
    # Control flow
    (r"if\s*\((.+)\)\s*\{", r"if (\1) {", "if"),
    # Null handling
    (r"(\w+)\s*!=\s*null", r"\1 != null", "not_null"),
    (r"(\w+)\s*==\s*null", r"\1 == null", "is_null"),
    # String templates
    (
        r'"(.+)"\s*\+\s*(\w+)\s*\+\s*"(.+)"',
        f'"${RegexCaptureGroups.FIRST}${RegexCaptureGroups.SECOND}${RegexCaptureGroups.THIRD}"',
        "string_concat",
    ),
    # System.out
    (r"System\.out\.println\((.*?)\)", r"println(\1)", "println"),
    # New instance
    (r"new\s+(\w+)\((.*?)\)", r"\1(\2)", "new"),
    # Getters
    (r"\.get(\w+)\(\)", r".\1", "getter"),
]


def _apply_single_pattern(
    result: str,
    pattern: str,
    replacement: str,
    name: str,
    applied: List[str],
) -> str:
    try:
        new_result = re.sub(pattern, replacement, result, flags=re.MULTILINE)
        if new_result != result:
            applied.append(name)
            return new_result
    except re.error as e:
        logger.warning("pattern_error", pattern_name=name, error=str(e))
    return result


def _apply_patterns(
    code: str,
    patterns: List[Tuple[str, str, str]],
) -> Tuple[str, List[str]]:
    """Apply conversion patterns to code.

    Args:
        code: Source code
        patterns: List of (pattern, replacement, name) tuples

    Returns:
        Tuple of (converted_code, list_of_applied_patterns)
    """
    applied: List[str] = []
    result = code
    for pattern, replacement, name in patterns:
        result = _apply_single_pattern(result, pattern, replacement, name, applied)
    return result, applied


def _try_replace_type(result: str, source_type: str, target_type: str) -> Tuple[str, bool]:
    pattern = rf"\b{re.escape(source_type)}\b"
    if re.search(pattern, result):
        return re.sub(pattern, target_type, result), True
    return result, False


def _convert_types(
    code: str,
    type_mappings: Dict[str, str],
) -> Tuple[str, List[TypeMapping]]:
    """Convert types in code using mapping."""
    mappings_used = []
    result = code
    for source_type, target_type in type_mappings.items():
        result, replaced = _try_replace_type(result, source_type, target_type)
        if replaced:
            mappings_used.append(TypeMapping(source_type=source_type, target_type=target_type))
    return result, mappings_used


_DEDENT_PREFIXES = ("elif", "else:", "except", "finally:", "}")


def _indent_python_line(stripped: str, indent_level: int) -> Tuple[str, int]:
    """Return indented line and updated indent level."""
    if stripped.startswith(_DEDENT_PREFIXES):
        indent_level = max(0, indent_level - 1)
    indented = "    " * indent_level + stripped
    if stripped.endswith(":"):
        indent_level += 1
    return indented, indent_level


def _process_python_line(stripped: str, indent_level: int, result_lines: List[str]) -> int:
    if not stripped:
        result_lines.append("")
        return indent_level
    indented, indent_level = _indent_python_line(stripped, indent_level)
    result_lines.append(indented)
    return indent_level


def _indent_python_lines(lines: List[str]) -> List[str]:
    result_lines: List[str] = []
    indent_level = 0
    for line in lines:
        indent_level = _process_python_line(line.strip(), indent_level, result_lines)
    return result_lines


def _add_indentation_fixes(code: str, to_language: str) -> str:
    """Fix indentation for target language."""
    if to_language != "python":
        return code
    return "\n".join(_indent_python_lines(code.split("\n")))


_PROBLEMATIC_PATTERNS: Dict[str, List[Tuple[str, str]]] = {
    "python_to_typescript": [
        (r"with\s+", "Context managers (with) don't have direct equivalent"),
        (r"yield\s+", "Generators may need manual conversion"),
        (r"@\w+", "Decorators need manual conversion to TypeScript"),
        (r"__\w+__", "Magic methods need manual conversion"),
    ],
    "typescript_to_python": [
        (r"interface\s+", "Interfaces should be converted to Protocol/ABC"),
        (r"type\s+\w+\s*=", "Type aliases may need adjustment"),
        (r"enum\s+", "Enums should be converted to Enum class"),
        (r"<\w+>", "Generic types may need adjustment"),
    ],
}


def _make_warning(message: str, line_num: int) -> ConversionWarning:
    return ConversionWarning(severity="warning", message=message, line_number=line_num, suggestion=f"Review code at line {line_num}")


def _generate_warnings(
    source_code: str,
    from_language: str,
    to_language: str,
    applied_patterns: List[str],
) -> List[ConversionWarning]:
    """Generate warnings about conversion issues."""
    warnings = []
    key = f"{from_language}_to_{to_language}"
    for pattern, message in _PROBLEMATIC_PATTERNS.get(key, []):
        for match in re.finditer(pattern, source_code):
            line_num = source_code[: match.start()].count("\n") + 1
            warnings.append(_make_warning(message, line_num))
    return warnings


_PAIR_PATTERNS: Dict[Tuple[str, str], List[Tuple[str, str, str]]] = {
    ("python", "typescript"): PYTHON_TO_TS_PATTERNS,
    ("python", "javascript"): PYTHON_TO_TS_PATTERNS,
    ("typescript", "python"): TS_TO_PYTHON_PATTERNS,
    ("javascript", "python"): TS_TO_PYTHON_PATTERNS,
    ("javascript", "typescript"): [],
    ("java", "kotlin"): JAVA_TO_KOTLIN_PATTERNS,
}

_BRACE_LANG_COMMENT = {"typescript", "javascript", "java", "kotlin"}


def _select_patterns(pair: Tuple[str, str]) -> List[Tuple[str, str, str]]:
    return _PAIR_PATTERNS.get(pair, [])


def _collect_imports(to_language: str, converted_code: str) -> List[str]:
    if to_language == "python" and "async" in converted_code:
        return ["import asyncio"]
    return []


def _add_conversion_header(code: str, from_language: str, to_language: str) -> str:
    prefix = "//" if to_language in _BRACE_LANG_COMMENT else "#"
    return f"{prefix} Converted from {from_language} to {to_language}\n" + code


def _build_converted_code(
    code_snippet: str,
    from_language: str,
    to_language: str,
    style: ConversionStyle,
    include_comments: bool,
) -> Tuple[ConvertedCode, List[str]]:
    pair = (from_language.lower(), to_language.lower())
    converted_code, applied_patterns = _apply_patterns(code_snippet, _select_patterns(pair))
    converted_code, type_mappings = _convert_types(converted_code, get_type_mapping(from_language, to_language))
    converted_code = _add_indentation_fixes(converted_code, to_language)
    warnings = _generate_warnings(code_snippet, from_language, to_language, applied_patterns)
    imports_needed = _collect_imports(to_language, converted_code)
    if include_comments:
        converted_code = _add_conversion_header(converted_code, from_language, to_language)
    return ConvertedCode(
        source_code=code_snippet,
        converted_code=converted_code,
        from_language=from_language,
        to_language=to_language,
        style=style,
        type_mappings=type_mappings,
        warnings=warnings,
        imports_needed=imports_needed,
        success=True,
    ), imports_needed


def convert_code_language_impl(
    code_snippet: str,
    from_language: str,
    to_language: str,
    conversion_style: str = "idiomatic",
    include_comments: bool = True,
) -> ConversionResult:
    """Convert code from one language to another."""
    start_time = time.time()
    pair = (from_language.lower(), to_language.lower())
    if pair not in SUPPORTED_CONVERSION_PAIRS:
        raise ValueError(f"Unsupported conversion pair: {from_language} -> {to_language}. Supported pairs: {SUPPORTED_CONVERSION_PAIRS}")
    style = ConversionStyle(conversion_style)
    converted, _ = _build_converted_code(code_snippet, from_language, to_language, style, include_comments)
    execution_time = int((time.time() - start_time) * ConversionFactors.MILLISECONDS_PER_SECOND)
    return ConversionResult(
        conversions=[converted],
        total_functions=1,
        successful_conversions=1,
        failed_conversions=0,
        execution_time_ms=execution_time,
    )
