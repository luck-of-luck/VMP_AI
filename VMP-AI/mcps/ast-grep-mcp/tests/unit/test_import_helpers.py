from scripts.import_helpers import compute_import_insert_index, ensure_import_present, scan_import_state

IMPORT_STMT = "from ast_grep_mcp.utils.console_logger import console"


def test_scan_import_state_detects_existing_import_and_last_index() -> None:
    lines = [
        "import os",
        "from pathlib import Path",
        IMPORT_STMT,
        "",
        "print('x')",
    ]

    has_import, import_index = scan_import_state(lines, IMPORT_STMT)

    assert has_import is True
    assert import_index == 1


def test_compute_import_insert_index_handles_shebang_and_multiline_docstring() -> None:
    lines = [
        "#!/usr/bin/env python3",
        '"""Module docs.',
        "More docs.",
        '"""',
        "print('x')",
    ]

    assert compute_import_insert_index(lines) == 4


def test_ensure_import_present_inserts_after_last_import() -> None:
    lines = [
        "import os",
        "from pathlib import Path",
        "",
        "print('x')",
    ]

    added = ensure_import_present(lines, IMPORT_STMT)

    assert added is True
    assert lines[2] == IMPORT_STMT


def test_ensure_import_present_top_insert_adds_blank_line() -> None:
    lines = [
        "#!/usr/bin/env python3",
        "print('x')",
    ]

    added = ensure_import_present(lines, IMPORT_STMT, add_blank_line=True, blank_line_only_when_needed=False)

    assert added is True
    assert lines[1] == IMPORT_STMT
    assert lines[2] == ""


def test_ensure_import_present_blank_line_only_when_needed() -> None:
    lines = [
        "#!/usr/bin/env python3",
        "",
        "print('x')",
    ]

    added = ensure_import_present(lines, IMPORT_STMT, add_blank_line=True, blank_line_only_when_needed=True)

    assert added is True
    assert lines[1] == IMPORT_STMT
    assert lines[2] == ""
    assert lines[3] == "print('x')"
