"""Shared import-insertion helpers for migration scripts."""

from typing import List, Sequence, Tuple

CONSOLE_IMPORT_STMT = "from ast_grep_mcp.utils.console_logger import console"


def scan_import_state(lines: Sequence[str], import_statement: str) -> Tuple[bool, int]:
    """Return whether an import exists and the index of the last import line."""
    has_import = False
    import_line_index = -1

    for line_index, line in enumerate(lines):
        if import_statement in line:
            has_import = True
            break
        if line.startswith("import ") or line.startswith("from "):
            import_line_index = line_index

    return has_import, import_line_index


def compute_import_insert_index(lines: Sequence[str]) -> int:
    """Find insertion index after shebang/docstring."""
    insert_idx = 0

    for line_index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#!"):
            insert_idx = line_index + 1
        elif stripped.startswith('"""') or stripped.startswith("'''"):
            quote = '"""' if '"""' in line else "'''"
            if line.count(quote) >= 2:
                insert_idx = line_index + 1
                break

            for next_index in range(line_index + 1, len(lines)):
                if quote in lines[next_index]:
                    insert_idx = next_index + 1
                    break
            break

    return insert_idx


def ensure_import_present(
    lines: List[str],
    import_statement: str,
    *,
    add_blank_line: bool = True,
    blank_line_only_when_needed: bool = False,
) -> bool:
    """Insert import when missing.

    Returns:
        True when import was inserted, False when it already existed.
    """
    has_import, import_line_index = scan_import_state(lines, import_statement)
    if has_import:
        return False

    if import_line_index >= 0:
        lines.insert(import_line_index + 1, import_statement)
        return True

    insert_idx = compute_import_insert_index(lines)
    lines.insert(insert_idx, import_statement)

    if add_blank_line:
        should_add_blank = True
        if blank_line_only_when_needed:
            should_add_blank = insert_idx + 1 < len(lines) and bool(lines[insert_idx + 1].strip())
        if should_add_blank:
            lines.insert(insert_idx + 1, "")

    return True
