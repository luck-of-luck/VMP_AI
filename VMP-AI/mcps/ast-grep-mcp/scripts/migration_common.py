"""Shared helpers/constants for migration-fix scripts."""

from pathlib import Path
from typing import Iterator, List, Sequence, Tuple

MIGRATION_ERROR_TEST_FILES = [
    "tests/unit/test_duplication.py",
    "tests/unit/test_coverage_detection.py",
    "tests/unit/test_import_management.py",
    "tests/unit/test_parameter_extraction.py",
    "tests/unit/test_enhanced_suggestions.py",
    "tests/unit/test_function_generation.py",
    "tests/unit/test_standards_enforcement.py",
    "tests/unit/test_dependency_analysis.py",
    "tests/unit/test_linting_rules.py",
    "tests/unit/test_diff_preview.py",
    "tests/unit/test_complexity.py",
    "tests/unit/test_code_smells.py",
    "tests/unit/test_ast_diff.py",
    "tests/unit/test_variation_classification.py",
    "tests/unit/test_impact_analysis.py",
    "tests/unit/test_enhanced_reporting.py",
    "tests/unit/test_call_site.py",
]


def read_lines(file_path: Path) -> List[str]:
    """Read file lines preserving line endings."""
    with open(file_path, "r", encoding="utf-8") as file_obj:
        return file_obj.readlines()


def write_lines(file_path: Path, lines: Sequence[str]) -> None:
    """Write lines to file."""
    with open(file_path, "w", encoding="utf-8") as file_obj:
        file_obj.writelines(lines)


def iter_migration_targets(
    directory: Path,
    pattern: str = "**/*.py",
    skip_pycache: bool = True,
    sort: bool = False,
) -> Iterator[Path]:
    """Yield files under `directory` matching `pattern`, optionally skipping __pycache__."""
    paths = directory.glob(pattern)
    if sort:
        paths = sorted(paths)
    for file_path in paths:
        if not file_path.is_file():
            continue
        if skip_pycache and "__pycache__" in str(file_path):
            continue
        yield file_path


def _normalize_ranges(ranges: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    """Sort and merge line ranges (start inclusive, end exclusive)."""
    if not ranges:
        return []

    valid = sorted((start, end) for start, end in ranges if start < end)
    if not valid:
        return []

    merged: List[Tuple[int, int]] = [valid[0]]
    for start, end in valid[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def remove_line_ranges(lines: Sequence[str], ranges: Sequence[Tuple[int, int]]) -> List[str]:
    """Return a new list with line ranges removed.

    Args:
        lines: Original lines.
        ranges: Zero-based ranges with end-exclusive semantics.
    """
    merged = _normalize_ranges(ranges)
    if not merged:
        return list(lines)

    result: List[str] = []
    range_idx = 0
    current_start, current_end = merged[range_idx]

    for line_idx, line in enumerate(lines):
        while range_idx < len(merged) and line_idx >= current_end:
            range_idx += 1
            if range_idx < len(merged):
                current_start, current_end = merged[range_idx]

        in_range = range_idx < len(merged) and current_start <= line_idx < current_end
        if not in_range:
            result.append(line)

    return result
