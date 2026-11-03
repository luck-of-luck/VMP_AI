#!/usr/bin/env python3
"""Remove orphaned import lines from migration."""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

from ast_grep_mcp.constants import DisplayDefaults, FormattingDefaults
from ast_grep_mcp.utils.console_logger import console

try:
    from scripts.migration_common import MIGRATION_ERROR_TEST_FILES, read_lines, remove_line_ranges, write_lines
except ImportError:  # pragma: no cover - script execution path
    from migration_common import MIGRATION_ERROR_TEST_FILES, read_lines, remove_line_ranges, write_lines


_IMPORT_KEYWORDS = ("from", "import", "#", '"""', "'''", "class", "def", "@")
_STATEMENT_STARTS = ("from", "import", "class", "def", "@", '"""', "'''")


def _is_orphan_close_paren(line: str, prev_line: str) -> bool:
    """Return True if line is a stray `)` immediately after a completed import."""
    return line == ")" and prev_line.endswith(")")


def _is_orphan_import_item_start(line: str, raw_line: str, prev_line: str) -> bool:
    """Return True if this indented line starts an orphaned import-item block."""
    return (
        bool(line)
        and not line.startswith(_IMPORT_KEYWORDS)
        and raw_line.startswith("    ")
        and "(" not in line
        and "=" not in line
        and "def " not in line
        and "class " not in line
        and prev_line.endswith(")")
    )


def _scan_orphan_item_range(lines: List[str], start: int) -> Tuple[int, int]:
    """Scan forward from start to find the end of an orphaned import-item block."""
    i = start
    while i < len(lines):
        curr = lines[i].strip()
        if curr == ")":
            return (start, i + 1)
        if curr.startswith(_STATEMENT_STARTS) or not curr or curr.startswith("#"):
            return (start, i)
        i += 1
    return (start, i)


def find_orphaned_imports(lines: List[str]) -> List[Tuple[int, int]]:
    """Find lines that are orphaned from old import blocks."""
    orphaned_ranges = []
    i = 0

    while i < len(lines):
        if i > 0:
            line = lines[i].strip()
            prev_line = lines[i - 1].strip()

            if _is_orphan_close_paren(line, prev_line):
                orphaned_ranges.append((i, i + 1))
                i += 1
                continue

            if _is_orphan_import_item_start(line, lines[i], prev_line):
                start, end = _scan_orphan_item_range(lines, i)
                orphaned_ranges.append((start, end))
                i = end
                continue

        i += 1

    return orphaned_ranges


def remove_orphaned_lines(filepath: Path):
    """Remove orphaned import lines from file."""
    lines = read_lines(filepath)

    orphaned = find_orphaned_imports(lines)

    if not orphaned:
        return False

    console.log(f"\n  Fixing {filepath.name}:")
    for start, end in orphaned:
        console.log(f"    Removing lines {start + 1}-{end}: {repr(lines[start].strip()[: DisplayDefaults.CONTENT_PREVIEW_LENGTH])}")

    write_lines(filepath, remove_line_ranges(lines, orphaned))

    return True


def check_syntax(filepath: Path):
    """Check if file has valid Python syntax."""
    result = subprocess.run([sys.executable, "-m", "py_compile", str(filepath)], capture_output=True, text=True)
    return result.returncode == 0, result.stderr


def main():
    """Fix all test files with orphaned imports."""
    console.log("=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    console.log("Fixing orphaned import lines from migration")
    console.log("=" * FormattingDefaults.WIDE_SECTION_WIDTH)

    fixed_count = 0
    failed = []

    for filepath_str in MIGRATION_ERROR_TEST_FILES:
        filepath = Path(filepath_str)
        if not filepath.exists():
            console.log(f"\n  Skipping {filepath} - not found")
            continue

        # Check syntax before
        valid_before, error_before = check_syntax(filepath)

        if valid_before:
            console.log(f"\n  Skipping {filepath.name} - already valid")
            continue

        # Try to fix
        if remove_orphaned_lines(filepath):
            # Check syntax after
            valid_after, error_after = check_syntax(filepath)

            if valid_after:
                console.success("    ✓ Fixed!")
                fixed_count += 1
            else:
                console.log("    ✗ Still has errors:")
                console.log(f"      {error_after.strip()}")
                failed.append(filepath_str)
        else:
            console.log(f"\n  No orphaned imports found in {filepath.name}")
            console.error(f"    Original error: {error_before.strip()}")
            failed.append(filepath_str)

    console.log("\n" + "=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    console.log(f"Results: {fixed_count} files fixed")

    if failed:
        console.error(f"\n{len(failed)} files still have errors:")
        for f in failed:
            console.log(f"  - {f}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
