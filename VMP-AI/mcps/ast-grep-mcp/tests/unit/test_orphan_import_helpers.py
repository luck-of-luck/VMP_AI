"""Tests for extracted helpers in fix_import_orphans.py."""

from scripts.fix_import_orphans import (
    _is_orphan_close_paren,
    _is_orphan_import_item_start,
    _scan_orphan_item_range,
    find_orphaned_imports,
)


class TestIsOrphanCloseParen:
    def test_close_paren_after_close_paren(self):
        assert _is_orphan_close_paren(")", "from foo import (bar)")

    def test_close_paren_after_regular_line(self):
        assert not _is_orphan_close_paren(")", "x = 1")

    def test_non_paren_line(self):
        assert not _is_orphan_close_paren("x = 1", "from foo import (bar)")


class TestIsOrphanImportItemStart:
    def test_indented_identifier_after_import_close(self):
        assert _is_orphan_import_item_start("bar", "    bar", "from foo import (x)")

    def test_from_line_not_orphan(self):
        assert not _is_orphan_import_item_start("from x import y", "from x import y", "from foo import (x)")

    def test_def_line_not_orphan(self):
        assert not _is_orphan_import_item_start("def foo():", "    def foo():", "from foo import (x)")

    def test_unindented_not_orphan(self):
        assert not _is_orphan_import_item_start("bar", "bar", "from foo import (x)")

    def test_line_with_equals_not_orphan(self):
        assert not _is_orphan_import_item_start("x = 1", "    x = 1", "from foo import (x)")

    def test_prev_not_ended_with_paren(self):
        assert not _is_orphan_import_item_start("bar", "    bar", "x = 1")

    def test_empty_line_not_orphan(self):
        assert not _is_orphan_import_item_start("", "    ", "from foo import (x)")


class TestScanOrphanItemRange:
    def test_ends_at_close_paren(self):
        lines = ["    bar,", "    baz,", ")"]
        assert _scan_orphan_item_range(lines, 0) == (0, 3)

    def test_ends_at_statement_start(self):
        lines = ["    bar,", "from x import y"]
        assert _scan_orphan_item_range(lines, 0) == (0, 1)

    def test_ends_at_empty_line(self):
        lines = ["    bar,", ""]
        assert _scan_orphan_item_range(lines, 0) == (0, 1)

    def test_ends_at_comment(self):
        lines = ["    bar,", "# comment"]
        assert _scan_orphan_item_range(lines, 0) == (0, 1)

    def test_ends_at_eof(self):
        lines = ["    bar,", "    baz,"]
        assert _scan_orphan_item_range(lines, 0) == (0, 2)


class TestFindOrphanedImportsIntegration:
    def test_no_orphans(self):
        lines = ["from foo import bar", "", "x = 1"]
        assert find_orphaned_imports(lines) == []

    def test_orphaned_close_paren(self):
        lines = ["from foo import (bar)", ")"]
        ranges = find_orphaned_imports(lines)
        assert ranges == [(1, 2)]

    def test_orphaned_indented_block(self):
        lines = [
            "from foo import (bar)",
            "    baz,",
            "    qux,",
            ")",
        ]
        ranges = find_orphaned_imports(lines)
        assert len(ranges) == 1
        assert ranges[0] == (1, 4)
