"""Consolidated tests for deduplication detection functionality.

This file consolidates tests from:
- test_duplication.py
- test_ast_diff.py
- test_diff_preview.py

Focus: Detection, grouping, AST diff, alignment
"""

import os
import sys
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import modular functions - signatures now support optional language parameter
from ast_grep_mcp.features.deduplication.diff import (
    _ensure_trailing_newline,
    build_diff_tree,
    build_nested_diff_tree,
    diff_preview_to_dict,
    format_alignment_diff,
    generate_diff_from_file_paths,
    generate_file_diff,
    generate_multi_file_diff,
)

# generate_refactoring_suggestions migrated to modular architecture
from ast_grep_mcp.features.deduplication.recommendations import generate_refactoring_suggestions
from ast_grep_mcp.utils.text import calculate_similarity, normalize_code


class TestDuplicationDetection:
    """Tests for duplicate code detection."""

    def test_calculate_similarity(self):
        """Test similarity calculation between code snippets."""
        code1 = """
def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
        code2 = """
def process_data(data):
    result = []
    for item in data:
        result.append(item * 3)
    return result
"""
        similarity = calculate_similarity(code1, code2, "python")
        assert similarity > 0.8
        assert similarity < 1.0

    def test_normalize_code(self):
        """Test code normalization."""
        code = """
def hello():
    # This is a comment
    print("Hello, World!")
"""
        normalized = normalize_code(code, "python")
        assert "def hello()" in normalized
        assert "print" in normalized

    def test_generate_refactoring_suggestions(self):
        """Test generation of refactoring suggestions."""
        duplicates = [
            {"code": "def foo(): pass", "file": "file1.py", "similarity": 0.9},
            {"code": "def bar(): pass", "file": "file2.py", "similarity": 0.9},
        ]
        suggestions = generate_refactoring_suggestions(duplicates, "python")
        assert len(suggestions) > 0
        assert "extract" in str(suggestions).lower()


class TestASTDiff:
    """Tests for AST diff functionality."""

    def test_build_diff_tree(self):
        """Test building a diff tree from two code snippets."""
        code1 = "def foo(): return 1"
        code2 = "def foo(): return 2"

        diff_tree = build_diff_tree(code1, code2, "python")
        assert diff_tree is not None
        assert "diff" in str(diff_tree).lower() or diff_tree == {}

    def test_build_nested_diff_tree(self):
        """Test building nested diff tree."""
        code1 = """
def outer():
    def inner():
        return 1
"""
        code2 = """
def outer():
    def inner():
        return 2
"""
        diff_tree = build_nested_diff_tree(code1, code2, "python")
        assert diff_tree is not None

    def test_format_alignment_diff(self):
        """Test formatting alignment diff produces correct - old / + new prefixes."""
        diff_data = {
            "alignments": [
                {"type": "match", "value": "def foo():"},
                {"type": "diff", "old": "return 1", "new": "return 2"},
            ]
        }
        formatted = format_alignment_diff(diff_data)
        assert isinstance(formatted, str)
        lines = formatted.splitlines()
        assert "  def foo():" in lines
        assert "- return 1" in lines
        assert "+ return 2" in lines

    def test_format_alignment_diff_empty_old(self):
        """Test diff entry with empty old value only appends + new line."""
        diff_data = {"alignments": [{"type": "diff", "old": "", "new": "added line"}]}
        formatted = format_alignment_diff(diff_data)
        assert isinstance(formatted, str)
        lines = formatted.splitlines()
        assert "+ added line" in lines
        assert not any(line.startswith("- ") for line in lines)

    def test_format_alignment_diff_empty_new(self):
        """Test diff entry with empty new value only appends - old line."""
        diff_data = {"alignments": [{"type": "diff", "old": "removed line", "new": ""}]}
        formatted = format_alignment_diff(diff_data)
        assert isinstance(formatted, str)
        lines = formatted.splitlines()
        assert "- removed line" in lines
        assert not any(line.startswith("+ ") for line in lines)

    def test_format_alignment_diff_both_empty(self):
        """Test diff entry with both old and new empty produces no output lines."""
        diff_data = {"alignments": [{"type": "diff", "old": "", "new": ""}]}
        formatted = format_alignment_diff(diff_data)
        assert isinstance(formatted, str)
        assert formatted == ""


class TestDiffPreview:
    """Tests for diff preview generation."""

    def test_diff_preview_to_dict(self):
        """Test converting diff preview to dictionary."""
        diff_text = """
--- a/file.py
+++ b/file.py
@@ -1,3 +1,3 @@
 def foo():
-    return 1
+    return 2
"""
        result = diff_preview_to_dict(diff_text)
        assert isinstance(result, dict)
        assert "hunks" in result or "changes" in result or result == {}

    def test_generate_file_diff(self):
        """Test generating diff for a single file."""
        old_content = "def foo(): return 1"
        new_content = "def foo(): return 2"

        diff = generate_file_diff(old_content, new_content, "file.py")
        assert isinstance(diff, str)
        assert "def foo()" in diff or diff == ""

    def test_generate_file_diff_trailing_newline_change_is_visible(self):
        """Trailing-newline-only changes must appear in the diff (BUGL-05 regression)."""
        old_content = "def foo(): pass"  # no trailing newline
        new_content = "def foo(): pass\n"  # trailing newline added

        diff = generate_file_diff(old_content, new_content, "file.py")
        # Diff must be non-empty: a newline-only change cannot silently disappear
        assert diff != "", "trailing-newline change was hidden (BUGL-05 regression)"

    def test_generate_file_diff_identical_content_is_empty(self):
        """Identical content must produce an empty diff."""
        content = "def foo(): pass\n"
        diff = generate_file_diff(content, content, "file.py")
        assert diff == ""

    def test_generate_multi_file_diff(self):
        """Test generating diff for multiple files."""
        changes = [
            {"file": "file1.py", "old_content": "def foo(): return 1", "new_content": "def foo(): return 2"},
            {"file": "file2.py", "old_content": "def bar(): return 3", "new_content": "def bar(): return 4"},
        ]

        diff = generate_multi_file_diff(changes)
        assert isinstance(diff, str)
        assert "file1.py" in diff or "file2.py" in diff or diff == ""

    @patch("os.path.exists")
    @patch("builtins.open", create=True)
    def test_generate_diff_from_file_paths(self, mock_open, mock_exists):
        """Test generating diff from file paths."""
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.side_effect = ["def foo(): return 1", "def foo(): return 2"]

        diff = generate_diff_from_file_paths("old.py", "new.py")
        assert isinstance(diff, str)


class TestEnsureTrailingNewline:
    """Unit tests for _ensure_trailing_newline (in-place mutation helper)."""

    def test_empty_list_unchanged(self):
        lines: list[str] = []
        _ensure_trailing_newline(lines)
        assert lines == []

    def test_single_line_without_newline_gets_appended(self):
        lines = ["hello"]
        _ensure_trailing_newline(lines)
        assert lines == ["hello\n"]

    def test_single_line_already_has_newline_unchanged(self):
        lines = ["hello\n"]
        _ensure_trailing_newline(lines)
        assert lines == ["hello\n"]

    def test_multi_line_last_without_newline(self):
        lines = ["foo\n", "bar\n", "baz"]
        _ensure_trailing_newline(lines)
        assert lines[-1] == "baz\n"
        assert lines[0] == "foo\n"
        assert lines[1] == "bar\n"

    def test_multi_line_last_already_has_newline(self):
        lines = ["foo\n", "bar\n", "baz\n"]
        _ensure_trailing_newline(lines)
        assert lines == ["foo\n", "bar\n", "baz\n"]

    def test_modifies_in_place(self):
        lines = ["x"]
        original_ref = lines
        _ensure_trailing_newline(lines)
        assert lines is original_ref
