from pathlib import Path
from textwrap import dedent

from scripts.fix_migration_errors import _find_orphaned_import_ranges, fix_file


def _write_file(path: Path, content: str) -> None:
    path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")


def test_find_orphaned_import_ranges_detects_orphan_block() -> None:
    lines = [
        "from ast_grep_mcp.constants import (\n",
        "    Foo,\n",
        ")\n",
        "def keep_me():\n",
        "    return 1\n",
    ]

    ranges = _find_orphaned_import_ranges(lines)

    assert ranges == [(1, 3)]


def test_fix_file_removes_orphaned_block(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    _write_file(
        file_path,
        """
        from ast_grep_mcp.constants import (
            Foo,
        )
        def keep_me():
            return 1
        """,
    )

    fixed = fix_file(file_path)
    content = file_path.read_text(encoding="utf-8")

    assert fixed is True
    assert "Foo," not in content
    assert ")\n" not in content
    assert "def keep_me():" in content


def test_fix_file_no_change_without_orphan(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    original = """
    from ast_grep_mcp.constants import Foo
    def keep_me():
        return 1
    """
    _write_file(file_path, original)

    fixed = fix_file(file_path)

    assert fixed is False
    assert file_path.read_text(encoding="utf-8") == dedent(original).lstrip("\n")
