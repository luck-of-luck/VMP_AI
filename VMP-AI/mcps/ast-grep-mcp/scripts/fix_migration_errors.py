#!/usr/bin/env python3
"""Fix syntax errors from migration script."""

import re
from pathlib import Path
from typing import List, Tuple

from ast_grep_mcp.utils.console_logger import console

try:
    from scripts.migration_common import MIGRATION_ERROR_TEST_FILES, read_lines, remove_line_ranges, write_lines
except ImportError:  # pragma: no cover - script execution path
    from migration_common import MIGRATION_ERROR_TEST_FILES, read_lines, remove_line_ranges, write_lines


def _is_potential_orphan_followup(next_line: str) -> bool:
    """Check whether line after import may be orphaned import content."""
    stripped = next_line.strip()
    if not stripped:
        return False
    if stripped[0] in [",", ")"]:
        return True

    return (
        not stripped.startswith("from")
        and not stripped.startswith("import")
        and not stripped.startswith("#")
        and not stripped.startswith("class")
        and not stripped.startswith("def")
        and not stripped.startswith("@")
        and not stripped.startswith('"""')
        and not stripped.startswith("'''")
        and re.match(r"^\s+[a-zA-Z_]", next_line) is not None
    )


def _find_orphaned_import_ranges(lines: List[str]) -> List[Tuple[int, int]]:
    """Find orphaned import ranges as (start, end) with end-exclusive semantics."""
    ranges: List[Tuple[int, int]] = []

    for idx, line in enumerate(lines[:-1]):
        if not (line.strip().startswith("from ast_grep_mcp.") and "import" in line):
            continue
        if not _is_potential_orphan_followup(lines[idx + 1]):
            continue

        end_idx = idx + 1
        while end_idx < len(lines):
            stripped = lines[end_idx].strip()
            if stripped == ")":
                ranges.append((idx + 1, end_idx + 1))
                break
            if not stripped or stripped.startswith(("from", "import", "class", "def", "@", "#")):
                break
            end_idx += 1

    return ranges


def fix_file(filepath: Path) -> bool:
    """Fix orphaned import statement closing in a file."""
    lines = read_lines(filepath)
    ranges = _find_orphaned_import_ranges(lines)
    if not ranges:
        return False

    for start, end in ranges:
        console.log(f"  Fixing {filepath.name}: Removing orphaned lines {start + 1} to {end}")

    write_lines(filepath, remove_line_ranges(lines, ranges))
    return True


def main():
    """Fix all files with syntax errors."""
    console.log("Fixing migration syntax errors...")
    fixed_count = 0

    for filepath in MIGRATION_ERROR_TEST_FILES:
        path = Path(filepath)
        if not path.exists():
            console.log(f"  Skipping {filepath} - not found")
            continue

        console.log(f"\nProcessing {filepath}")
        if fix_file(path):
            fixed_count += 1

    console.success(f"\n✓ Fixed {fixed_count} files")


if __name__ == "__main__":
    main()
