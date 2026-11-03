from pathlib import Path
from textwrap import dedent

from scripts.migrate_print_to_logger import PrintMigrator


def _write_file(path: Path, content: str) -> None:
    path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")


def test_migrate_file_dry_run_keeps_original_content(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    original = """
    #!/usr/bin/env python3
    \"\"\"Module docs.\"\"\"
    print("hello")
    """
    _write_file(file_path, original)

    migrator = PrintMigrator(dry_run=True, backup=True)
    count, changes = migrator.migrate_file(file_path)

    assert count == 1
    assert any(change.startswith("Line 3:") for change in changes)
    assert any(change.startswith("Added import:") for change in changes)
    assert not file_path.with_suffix(".py.bak").exists()
    assert file_path.read_text(encoding="utf-8") == dedent(original).lstrip("\n")


def test_migrate_file_creates_backup_and_writes_changes(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    original = """
    print("hello")
    """
    _write_file(file_path, original)

    migrator = PrintMigrator(dry_run=False, backup=True)
    count, changes = migrator.migrate_file(file_path)

    backup_path = file_path.with_suffix(".py.bak")
    migrated = file_path.read_text(encoding="utf-8")

    assert count == 1
    assert backup_path.exists()
    assert backup_path.read_text(encoding="utf-8") == dedent(original).lstrip("\n")
    assert any(change.startswith("Created backup:") for change in changes)
    assert "from ast_grep_mcp.utils.console_logger import console" in migrated
    assert "print(" not in migrated


def test_import_inserted_after_last_import(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    _write_file(
        file_path,
        """
        import os
        from pathlib import Path

        print("hello")
        """,
    )

    migrator = PrintMigrator(dry_run=False, backup=False)
    count, _changes = migrator.migrate_file(file_path)
    lines = file_path.read_text(encoding="utf-8").splitlines()

    assert count == 1
    assert lines[0] == "import os"
    assert lines[1] == "from pathlib import Path"
    assert lines[2] == "from ast_grep_mcp.utils.console_logger import console"


def test_import_inserted_after_shebang_and_docstring(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    _write_file(
        file_path,
        """
        #!/usr/bin/env python3
        \"\"\"Module docs.
        More docs.
        \"\"\"
        print("hello")
        """,
    )

    migrator = PrintMigrator(dry_run=False, backup=False)
    count, _changes = migrator.migrate_file(file_path)
    lines = file_path.read_text(encoding="utf-8").splitlines()

    assert count == 1
    assert lines[4] == "from ast_grep_mcp.utils.console_logger import console"
    assert lines[5] == ""


def test_migrate_file_replaces_multiple_statements(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    _write_file(
        file_path,
        """
        print("first")
        x = 1
        print("second")
        """,
    )

    migrator = PrintMigrator(dry_run=False, backup=False)
    count, changes = migrator.migrate_file(file_path)
    migrated = file_path.read_text(encoding="utf-8")

    assert count == 2
    assert any(change.startswith("Line 1:") for change in changes)
    assert any(change.startswith("Line 3:") for change in changes)
    assert "print(" not in migrated
    assert "console.error(" in migrated
