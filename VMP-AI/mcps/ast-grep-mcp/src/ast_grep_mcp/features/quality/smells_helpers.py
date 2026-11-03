"""Helper functions for code smell detection.

This module contains utility functions extracted from the main smell detection
implementation to reduce complexity and improve maintainability.
"""

from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List

from ast_grep_mcp.constants import SeverityRankingDefaults, SmellSeverityDefaults
from ast_grep_mcp.core.logging import get_logger


def validate_smell_detection_inputs(project_folder: str, language: str, severity_filter: str) -> tuple[Path, str, str]:
    """Validate inputs for smell detection.

    Args:
        project_folder: Path to project directory
        language: Programming language
        severity_filter: Severity filter (all, high, medium, low)

    Returns:
        Tuple of (project_path, file_extension, normalized_language)

    Raises:
        Dict with error key if validation fails
    """
    # Validate project folder
    project_path = Path(project_folder)
    if not project_path.exists():
        raise ValueError(f"Project folder not found: {project_folder}")
    if not project_path.is_dir():
        raise ValueError(f"Path is not a directory: {project_folder}")

    # Validate and get file extension for language
    ext_map = {"python": ".py", "typescript": ".ts", "javascript": ".js", "java": ".java"}
    normalized_language = language.lower()
    if normalized_language not in ext_map:
        raise ValueError(f"Unsupported language: {language}")

    file_ext = ext_map[normalized_language]

    # Validate severity filter
    valid_severities = ["all", "high", "medium", "low"]
    if severity_filter not in valid_severities:
        raise ValueError(f"Invalid severity filter: {severity_filter}. Must be one of {valid_severities}")

    return project_path, file_ext, normalized_language


def _adjust_include_pattern(pattern: str, file_ext: str) -> str:
    if pattern.endswith(file_ext):
        return pattern
    if not pattern.endswith("*"):
        return pattern.rstrip("/") + f"/**/*{file_ext}"
    if pattern.endswith("*/"):
        return pattern + file_ext
    return pattern.rstrip("*") + f"*{file_ext}"


def _is_file_excluded(file_path: str, project_path: Path, exclude_patterns: List[str]) -> bool:
    try:
        rel_path = str(Path(file_path).relative_to(project_path))
    except ValueError:
        return True
    return any(fnmatch(rel_path, exc.lstrip("/")) for exc in exclude_patterns)


def find_smell_analysis_files(project_path: Path, file_ext: str, include_patterns: List[str], exclude_patterns: List[str]) -> List[str]:
    """Find files to analyze for code smells.

    Args:
        project_path: Path to project directory
        file_ext: File extension to search for
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude

    Returns:
        List of file paths to analyze
    """
    logger = get_logger("smell_detection.find_files")

    all_files: List[str] = []
    for pattern in include_patterns:
        adjusted = _adjust_include_pattern(pattern, file_ext)
        matches = list(project_path.glob(adjusted.lstrip("/")))
        all_files.extend(str(f) for f in matches if f.is_file())
    all_files = list(set(all_files))

    filtered_files = [f for f in all_files if not _is_file_excluded(f, project_path, exclude_patterns)]

    logger.info("files_found", total=len(all_files), filtered=len(filtered_files))
    return filtered_files


def _severity_for_ratio(ratio: float) -> str:
    if ratio > SmellSeverityDefaults.HIGH_RATIO_THRESHOLD:
        return "high"
    if ratio > SmellSeverityDefaults.MEDIUM_RATIO_THRESHOLD:
        return "medium"
    return "low"


def _severity_for_parameter_bloat(metric: float, threshold: float) -> str:
    if metric > threshold * 2:
        return "high"
    if metric > threshold + 2:
        return "medium"
    return "low"


def _severity_for_deep_nesting(metric: float, threshold: float) -> str:
    excess = metric - threshold
    if excess > 2:
        return "high"
    if excess > 1:
        return "medium"
    return "low"


def calculate_smell_severity(metric: float, threshold: float, smell_type: str) -> str:
    """Calculate severity level based on metric value and threshold.

    Args:
        metric: The measured value
        threshold: The threshold value
        smell_type: Type of smell for specific severity calculation

    Returns:
        Severity level: "high", "medium", or "low"
    """
    if smell_type in ("long_function", "large_class"):
        ratio = metric / threshold if threshold > 0 else float("inf")
        return _severity_for_ratio(ratio)
    if smell_type == "parameter_bloat":
        return _severity_for_parameter_bloat(metric, threshold)
    if smell_type == "deep_nesting":
        return _severity_for_deep_nesting(metric, threshold)
    return "low"


def format_smell_detection_response(
    project_folder: str, language: str, files_analyzed: int, smells: List[Dict[str, Any]], thresholds: Dict[str, Any], severity_filter: str
) -> Dict[str, Any]:
    """Format the final smell detection response.

    Args:
        project_folder: Path to project directory
        language: Programming language analyzed
        files_analyzed: Number of files analyzed
        smells: List of detected smells
        thresholds: Threshold values used
        severity_filter: Applied severity filter

    Returns:
        Formatted response dictionary
    """
    # Filter by severity if requested
    if severity_filter != "all":
        smells = [s for s in smells if s.get("severity") == severity_filter]

    # Sort by severity (high > medium > low) then by type
    severity_order = SeverityRankingDefaults.SMELL_SORT_ORDER
    smells.sort(
        key=lambda s: (
            severity_order.get(s.get("severity", "low"), SeverityRankingDefaults.FALLBACK_RANK),
            s.get("type", ""),
        )
    )

    # Generate summary statistics
    smell_counts: Dict[str, int] = {}
    severity_counts: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}

    for smell in smells:
        smell_type = smell.get("type", "unknown")
        smell_counts[smell_type] = smell_counts.get(smell_type, 0) + 1
        severity_counts[smell.get("severity", "low")] += 1

    return {
        "project_folder": project_folder,
        "language": language,
        "files_analyzed": files_analyzed,
        "total_smells": len(smells),
        "summary": {"by_type": smell_counts, "by_severity": severity_counts},
        "smells": smells,
        "thresholds": thresholds,
    }


def aggregate_smell_results(file_results: List[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Aggregate smell detection results from multiple files.

    Args:
        file_results: List of smell lists from individual files

    Returns:
        Flattened list of all smells
    """
    all_smells = []
    for file_smells in file_results:
        if file_smells:  # Skip empty results
            all_smells.extend(file_smells)
    return all_smells
