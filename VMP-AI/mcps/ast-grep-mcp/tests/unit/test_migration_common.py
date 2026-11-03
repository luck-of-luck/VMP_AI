from scripts.migration_common import (
    MIGRATION_ERROR_TEST_FILES,
    remove_line_ranges,
)


def test_remove_line_ranges_removes_and_merges_overlaps() -> None:
    lines = ["l0\n", "l1\n", "l2\n", "l3\n", "l4\n", "l5\n"]
    ranges = [(1, 3), (2, 5)]  # overlap, should remove lines 1..4

    result = remove_line_ranges(lines, ranges)

    assert result == ["l0\n", "l5\n"]


def test_remove_line_ranges_ignores_invalid_ranges() -> None:
    lines = ["a\n", "b\n", "c\n"]
    ranges = [(2, 2), (3, 1)]  # invalid, no-op

    result = remove_line_ranges(lines, ranges)

    assert result == lines


def test_migration_error_targets_contains_expected_files() -> None:
    assert "tests/unit/test_enhanced_reporting.py" in MIGRATION_ERROR_TEST_FILES
    assert "tests/unit/test_duplication.py" in MIGRATION_ERROR_TEST_FILES
