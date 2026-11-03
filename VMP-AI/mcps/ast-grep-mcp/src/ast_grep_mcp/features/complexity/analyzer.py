"""
Code complexity analysis.

This module provides functions for analyzing code complexity at the file level,
extracting functions, and calculating complexity metrics for each function.
"""

import json
import re
import subprocess
from typing import Any, Dict, List, Pattern, Tuple

from ast_grep_mcp.constants import SubprocessDefaults
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.models.complexity import (
    ComplexityMetrics,
    ComplexityThresholds,
    FunctionComplexity,
)
from ast_grep_mcp.utils.parsing import detect_triple_quote, skip_blank_lines

from .metrics import (
    calculate_cognitive_complexity,
    calculate_cyclomatic_complexity,
    calculate_nesting_depth,
    get_complexity_patterns,
)

__all__ = [
    "extract_functions_from_file",
    "analyze_file_complexity",
    "calculate_nesting_depth",
]


_FUNCTION_PATTERN_KEYS = ("function", "async_function", "arrow_function", "method")

_PYTHON_METHOD_PATTERN: Pattern[str] = re.compile(r"^\s+def\s+", re.MULTILINE)
_JS_TS_METHOD_PATTERN: Pattern[str] = re.compile(r"^\s+\w+\s*\([^)]*\)\s*\{", re.MULTILINE)
_PYTHON_FUNC_SIG_PATTERN: Pattern[str] = re.compile(r"def\s+\w+\s*\(([^)]*)\)")
_JS_TS_FUNC_SIG_PATTERN: Pattern[str] = re.compile(r"(?:function\s+\w+|\w+)\s*\(([^)]*)\)")
_PYTHON_SELF_PATTERN: Pattern[str] = re.compile(r"\bself\b\s*,?\s*")
_PYTHON_CLS_PATTERN: Pattern[str] = re.compile(r"\bcls\b\s*,?\s*")


def _run_pattern_search(file_path: str, language: str, pattern: str) -> List[Dict[str, Any]]:
    """Run ast-grep for one pattern against a file and return matches."""
    try:
        result = subprocess.run(
            ["ast-grep", "run", "--pattern", pattern, "--lang", language, "--json", file_path],
            capture_output=True,
            text=True,
            timeout=SubprocessDefaults.AST_GREP_TIMEOUT_SECONDS,
        )
        if result.returncode == 0 and result.stdout.strip():
            matches = json.loads(result.stdout)
            if isinstance(matches, list):
                return matches
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        logger = get_logger("complexity.extract")
        logger.warning("extract_functions_failed", file=file_path, error=str(e))
    return []


def extract_functions_from_file(file_path: str, language: str) -> List[Dict[str, Any]]:
    """Extract all functions from a file using ast-grep.

    Args:
        file_path: Path to source file
        language: Programming language

    Returns:
        List of function matches with metadata
    """
    patterns = get_complexity_patterns(language)
    function_patterns = [patterns[k] for k in _FUNCTION_PATTERN_KEYS if k in patterns]
    all_functions: List[Dict[str, Any]] = []
    for pattern in function_patterns:
        all_functions.extend(_run_pattern_search(file_path, language, pattern))
    return all_functions


def _get_class_extraction_pattern(language: str) -> str:
    """Get the ast-grep pattern for class detection based on language.

    Args:
        language: Programming language

    Returns:
        Pattern string for ast-grep
    """
    class_patterns = {
        "python": "class $NAME($$$): $$$",
        "typescript": "class $NAME { $$$ }",
        "javascript": "class $NAME { $$$ }",
        "java": "class $NAME { $$$ }",
    }
    return class_patterns.get(language.lower(), class_patterns["python"])


def _execute_ast_grep_for_classes(file_path: str, language: str, pattern: str) -> List[Dict[str, Any]]:
    """Run ast-grep to find class matches.

    Args:
        file_path: Path to file to analyze
        language: Programming language
        pattern: ast-grep pattern to use

    Returns:
        List of match dictionaries from ast-grep output
    """
    result = subprocess.run(
        ["ast-grep", "run", "--pattern", pattern, "--lang", language, "--json", file_path],
        capture_output=True,
        text=True,
        timeout=SubprocessDefaults.AST_GREP_TIMEOUT_SECONDS,
    )

    # Early return for failed or empty results
    if result.returncode != 0 or not result.stdout.strip():
        return []

    matches = json.loads(result.stdout)
    return matches if isinstance(matches, list) else []


def _process_class_match_results(matches: List[Dict[str, Any]], language: str) -> List[Dict[str, Any]]:
    """Process ast-grep matches into class information.

    Args:
        matches: Raw match data from ast-grep
        language: Programming language

    Returns:
        List of class information dictionaries
    """
    classes = []
    for match in matches:
        cls_info = _extract_single_class_info(match, language)
        classes.append(cls_info)
    return classes


def _extract_single_class_info(match: Dict[str, Any], language: str) -> Dict[str, Any]:
    """Extract class information from a single ast-grep match.

    Args:
        match: Single match dictionary from ast-grep
        language: Programming language

    Returns:
        Dictionary with class name, lines, method count, and code
    """
    cls_name = _extract_class_name_from_match(match)
    start_line, end_line = _extract_class_line_range(match)
    code = match.get("text", "")
    method_count = _count_class_methods(code, language)

    return {"name": cls_name, "start_line": start_line, "end_line": end_line, "method_count": method_count, "code": code}


def _extract_class_name_from_match(match: Dict[str, Any]) -> str:
    """Extract class name from ast-grep match metavariables.

    Args:
        match: Match dictionary from ast-grep

    Returns:
        Class name or "unknown" if not found
    """
    meta_vars = match.get("metaVariables", {})
    if "NAME" not in meta_vars:
        return "unknown"

    name_data = meta_vars["NAME"]

    # Handle both dict and string formats
    if isinstance(name_data, dict):
        result = name_data.get("text", "unknown")
        return str(result) if result is not None else "unknown"
    elif isinstance(name_data, str):
        return name_data
    else:
        return "unknown"


def _extract_class_line_range(match: Dict[str, Any]) -> Tuple[int, int]:
    """Extract start and end line numbers from ast-grep match.

    Args:
        match: Match dictionary from ast-grep

    Returns:
        Tuple of (start_line, end_line), 1-indexed
    """
    range_info = match.get("range", {})
    start_line = range_info.get("start", {}).get("line", 0) + 1
    end_line = range_info.get("end", {}).get("line", 0) + 1
    return start_line, end_line


def _count_class_methods(code: str, language: str) -> int:
    """Count the number of methods in a class.

    Args:
        code: Class code as string
        language: Programming language

    Returns:
        Number of methods found
    """
    if language.lower() == "python":
        return len(_PYTHON_METHOD_PATTERN.findall(code))
    else:
        # Count function/method patterns in class body
        return len(_JS_TS_METHOD_PATTERN.findall(code))


def _extract_param_string(code: str, language: str) -> str:
    """Extract the raw parameter string from a function signature."""
    if language.lower() == "python":
        match = _PYTHON_FUNC_SIG_PATTERN.search(code)
    else:
        match = _JS_TS_FUNC_SIG_PATTERN.search(code)
    return match.group(1).strip() if match else ""


def _strip_python_self_cls(params: str) -> str:
    """Remove self/cls receiver args from a Python parameter string."""
    params = _PYTHON_SELF_PATTERN.sub("", params)
    params = _PYTHON_CLS_PATTERN.sub("", params)
    return params.strip()


def _count_params_by_depth(params: str) -> int:
    """Count comma-separated params while respecting bracket depth."""
    if not params:
        return 0
    depth = 0
    count = 1
    for char in params:
        if char in "([{<":
            depth += 1
        elif char in ")]}>":
            depth -= 1
        elif char == "," and depth == 0:
            count += 1
    return count


def _count_function_parameters(code: str, language: str) -> int:
    """Count the number of parameters in a function.

    Args:
        code: Function source code
        language: Programming language

    Returns:
        Number of parameters
    """
    params = _extract_param_string(code, language)
    if not params:
        return 0
    if language.lower() == "python":
        params = _strip_python_self_cls(params)
    if not params:
        return 0
    return _count_params_by_depth(params)


def _extract_function_name(func: Dict[str, Any]) -> str:
    """Extract function name from ast-grep match.

    Args:
        func: Function match from ast-grep

    Returns:
        Function name or "unknown" if not found
    """
    meta_vars = func.get("metaVariables", {})
    if "NAME" not in meta_vars:
        return "unknown"

    name_data = meta_vars["NAME"]
    if isinstance(name_data, dict):
        result = name_data.get("text", "unknown")
        return str(result) if result is not None else "unknown"
    elif isinstance(name_data, str):
        return name_data
    return "unknown"


def _get_line_numbers(func: Dict[str, Any]) -> Tuple[int, int]:
    """Extract line numbers from ast-grep range info.

    Args:
        func: Function match from ast-grep

    Returns:
        Tuple of (start_line, end_line), 1-indexed
    """
    range_info = func.get("range", {})
    start_line = range_info.get("start", {}).get("line", 0) + 1
    end_line = range_info.get("end", {}).get("line", 0) + 1
    return start_line, end_line


def _find_signature_end(code_lines: List[str]) -> int:
    """Find the line index where a Python function signature ends (the colon line)."""
    in_signature = False
    for i, line in enumerate(code_lines):
        stripped = line.strip()
        if not in_signature and (stripped.startswith("def ") or stripped.startswith("async def ")):
            in_signature = True
        if in_signature and stripped.endswith(":"):
            return i
    return -1


def _measure_docstring(code_lines: List[str], doc_start: int) -> int:
    """Measure lines occupied by a docstring starting at doc_start.

    Returns number of lines, or 0 if no docstring found.
    """
    first_content = code_lines[doc_start].strip()
    quote = detect_triple_quote(first_content)
    if quote is None:
        return 0
    # Single-line docstring
    if first_content.count(quote) >= 2:
        return 1
    # Multi-line: find closing quote
    for j in range(doc_start + 1, len(code_lines)):
        if quote in code_lines[j]:
            return j - doc_start + 1
    return 0


def _find_docstring_extent(code_lines: List[str], start: int) -> int:
    """Count docstring lines starting from the given line index.

    Returns the number of lines the docstring occupies, or 0 if no docstring found.
    """
    doc_start = skip_blank_lines(code_lines, start)
    if doc_start >= len(code_lines):
        return 0
    return _measure_docstring(code_lines, doc_start)


def _count_docstring_lines(code: str, language: str) -> int:
    """Count lines occupied by the leading docstring in a function body.

    Excludes docstring lines from length calculations so that well-documented
    functions are not penalized for having MCP/API documentation.
    """
    if language != "python":
        return 0

    code_lines = code.split("\n")
    sig_end = _find_signature_end(code_lines)

    if sig_end < 0 or sig_end + 1 >= len(code_lines):
        return 0

    return _find_docstring_extent(code_lines, sig_end + 1)


def _calculate_all_metrics(code: str, language: str) -> ComplexityMetrics:
    """Calculate all complexity metrics for a function.

    Args:
        code: Function source code
        language: Programming language

    Returns:
        ComplexityMetrics with all calculated values
    """
    cyclomatic = calculate_cyclomatic_complexity(code, language)
    cognitive = calculate_cognitive_complexity(code, language)
    nesting = calculate_nesting_depth(code, language)
    lines = len(code.split("\n")) - _count_docstring_lines(code, language)
    param_count = _count_function_parameters(code, language)

    return ComplexityMetrics(cyclomatic=cyclomatic, cognitive=cognitive, nesting_depth=nesting, lines=lines, parameter_count=param_count)


def _check_threshold_violations(metrics: ComplexityMetrics, thresholds: ComplexityThresholds) -> List[str]:
    """Check which thresholds are exceeded.

    Args:
        metrics: Calculated metrics
        thresholds: Threshold values

    Returns:
        List of exceeded threshold names
    """
    exceeds: List[str] = []

    if metrics.cyclomatic > thresholds.cyclomatic:
        exceeds.append("cyclomatic")
    if metrics.cognitive > thresholds.cognitive:
        exceeds.append("cognitive")
    if metrics.nesting_depth > thresholds.nesting_depth:
        exceeds.append("nesting")
    if metrics.lines > thresholds.lines:
        exceeds.append("length")

    return exceeds


def _build_function_complexity(
    func: Dict[str, Any], file_path: str, language: str, thresholds: ComplexityThresholds
) -> FunctionComplexity | None:
    """Build a FunctionComplexity object from one ast-grep match, or None if code is empty."""
    code = func.get("text", "")
    if not code:
        return None
    func_name = _extract_function_name(func)
    start_line, end_line = _get_line_numbers(func)
    metrics = _calculate_all_metrics(code, language)
    exceeds = _check_threshold_violations(metrics, thresholds)
    return FunctionComplexity(
        file_path=file_path,
        function_name=func_name,
        start_line=start_line,
        end_line=end_line,
        metrics=metrics,
        language=language,
        exceeds=exceeds,
    )


def analyze_file_complexity(file_path: str, language: str, thresholds: ComplexityThresholds) -> List[FunctionComplexity]:
    """Analyze complexity of all functions in a file.

    Args:
        file_path: Path to source file
        language: Programming language
        thresholds: Complexity thresholds

    Returns:
        List of FunctionComplexity objects
    """
    results: List[FunctionComplexity] = []
    try:
        functions = extract_functions_from_file(file_path, language)
        for func in functions:
            fc = _build_function_complexity(func, file_path, language, thresholds)
            if fc is not None:
                results.append(fc)
    except Exception as e:
        logger = get_logger("complexity.analyze")
        logger.error("analyze_file_failed", file=file_path, error=str(e))
    return results
