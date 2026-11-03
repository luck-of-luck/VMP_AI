"""Code smell detection implementation.

This module provides functionality to detect common code smells and anti-patterns:
- Long functions
- Parameter bloat
- Deep nesting
- Large classes
- Magic numbers

Each smell includes severity ratings and actionable suggestions.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List

from ast_grep_mcp.features.quality.smells_detectors import (
    DeepNestingDetector,
    LargeClassDetector,
    LongFunctionDetector,
    MagicNumberDetector,
    ParameterBloatDetector,
    SmellAnalyzer,
)
from ast_grep_mcp.features.quality.smells_helpers import (
    aggregate_smell_results,
    find_smell_analysis_files,
    format_smell_detection_response,
    validate_smell_detection_inputs,
)


def _run_parallel_analysis(
    analyzer: SmellAnalyzer,
    files_to_analyze: List[str],
    normalized_language: str,
    project_path: Any,
    max_threads: int,
) -> List[Dict[str, Any]]:
    """Run smell analysis in parallel over files and return aggregated smells."""
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        file_results = list(executor.map(lambda f: analyzer.analyze_file(f, normalized_language, project_path), files_to_analyze))
    return aggregate_smell_results(file_results)


def detect_code_smells_impl(
    project_folder: str,
    language: str,
    include_patterns: List[str],
    exclude_patterns: List[str],
    long_function_lines: int,
    parameter_count: int,
    nesting_depth: int,
    class_lines: int,
    class_methods: int,
    detect_magic_numbers: bool,
    severity_filter: str,
    max_threads: int,
) -> Dict[str, Any]:
    """Detect common code smells in a project."""
    try:
        project_path, file_ext, normalized_language = validate_smell_detection_inputs(project_folder, language, severity_filter)
    except ValueError as e:
        return {"error": str(e)}

    files_to_analyze = find_smell_analysis_files(project_path, file_ext, include_patterns, exclude_patterns)

    if not files_to_analyze:
        return {
            "error": f"No {language} files found matching patterns",
            "project_folder": project_folder,
            "include_patterns": include_patterns,
            "exclude_patterns": exclude_patterns,
        }

    detectors = _create_detectors(long_function_lines, parameter_count, nesting_depth, class_lines, class_methods, detect_magic_numbers)
    analyzer = SmellAnalyzer(detectors)
    all_smells = _run_parallel_analysis(analyzer, files_to_analyze, normalized_language, project_path, max_threads)

    thresholds = {
        "long_function_lines": long_function_lines,
        "parameter_count": parameter_count,
        "nesting_depth": nesting_depth,
        "class_lines": class_lines,
        "class_methods": class_methods,
    }
    return format_smell_detection_response(project_folder, language, len(files_to_analyze), all_smells, thresholds, severity_filter)


def _create_detectors(
    long_function_lines: int, parameter_count: int, nesting_depth: int, class_lines: int, class_methods: int, detect_magic_numbers: bool
) -> List[Any]:
    """Create and configure smell detectors.

    Args:
        long_function_lines: Threshold for function length
        parameter_count: Threshold for parameter count
        nesting_depth: Threshold for nesting depth
        class_lines: Threshold for class lines
        class_methods: Threshold for class methods
        detect_magic_numbers: Whether to detect magic numbers

    Returns:
        List of configured detector instances
    """
    detectors = [
        LongFunctionDetector(long_function_lines),
        ParameterBloatDetector(parameter_count),
        DeepNestingDetector(nesting_depth),
        LargeClassDetector(class_lines, class_methods),
    ]

    if detect_magic_numbers:
        detectors.append(MagicNumberDetector(enabled=True))

    return detectors
