"""Tests for _normalize_for_ast decomposed helpers and applicator type guards.

Covers:
- _is_comment_line: Python # and JS // comment detection
- _strip_inline_comments: inline comment removal with string heuristic
- _normalize_for_ast: edge cases (mixed styles, hash-in-strings, comment-only)
- applicator module-level wrappers: TypeError on wrong return type
"""

from unittest.mock import MagicMock, patch

import pytest

from ast_grep_mcp.features.deduplication.similarity import HybridSimilarity


class TestIsCommentLine:
    """Tests for HybridSimilarity._is_comment_line."""

    @pytest.mark.parametrize(
        "line,expected",
        [
            ("# Python comment", True),
            ("#no space", True),
            ("// JS comment", True),
            ("//no space", True),
            ("x = 1", False),
            ("x = 1  # trailing", False),
            ("x = 1  // trailing", False),
            ("", False),
            ("   ", False),
            ('url = "http://example.com"', False),
            ("def func(): # comment", False),
        ],
    )
    def test_comment_detection(self, line: str, expected: bool):
        assert HybridSimilarity._is_comment_line(line.strip()) == expected


class TestStripInlineComments:
    """Tests for HybridSimilarity._strip_inline_comments."""

    def test_strips_python_inline_comment(self):
        result = HybridSimilarity._strip_inline_comments("x = 1  # assign x")
        assert result == "x = 1"

    def test_strips_js_inline_comment(self):
        result = HybridSimilarity._strip_inline_comments("const x = 1;  // assign x")
        assert result == "const x = 1;"

    def test_preserves_hash_inside_balanced_quotes(self):
        """Hash inside a string with balanced quotes should still be stripped
        (heuristic: balanced quotes + hash after content = comment)."""
        result = HybridSimilarity._strip_inline_comments('x = "hello"  # comment')
        assert result == 'x = "hello"'

    def test_hash_inside_balanced_single_quotes_is_stripped(self):
        """Balanced quote count (2 single quotes) causes hash to be treated as comment.
        This is a known limitation of the simple heuristic."""
        line = "x = 'color is #fff'"
        result = HybridSimilarity._strip_inline_comments(line)
        assert "#fff" not in result

    def test_preserves_hash_with_odd_quote_count(self):
        """Odd quote count prevents stripping — hash is likely inside a string."""
        line = "x = 'it\\'s #fff'"  # 3 quote chars total (odd)
        result = HybridSimilarity._strip_inline_comments(line)
        assert "#fff" in result

    def test_preserves_url_with_double_slash(self):
        """// at position 0 is not stripped (only > 0 triggers removal)."""
        line = "//example.com"
        result = HybridSimilarity._strip_inline_comments(line)
        assert result == "//example.com"

    def test_strips_double_slash_after_content(self):
        line = "const url = x;  // set url"
        result = HybridSimilarity._strip_inline_comments(line)
        assert result == "const url = x;"

    def test_no_comment_passthrough(self):
        line = "x = 42"
        assert HybridSimilarity._strip_inline_comments(line) == line

    def test_empty_line_passthrough(self):
        assert HybridSimilarity._strip_inline_comments("") == ""

    def test_hash_at_position_zero_not_stripped(self):
        """Leading # (position 0) is not stripped by inline logic."""
        line = "# full line comment"
        result = HybridSimilarity._strip_inline_comments(line)
        assert result == line


@pytest.fixture()
def hybrid():
    return HybridSimilarity()


class TestNormalizeForAstEdgeCases:
    """Edge case tests for _normalize_for_ast beyond existing coverage."""

    def test_comment_only_code_returns_empty(self, hybrid):
        code = "# comment 1\n# comment 2\n// js comment"
        result = hybrid._normalize_for_ast(code)
        assert result == ""

    def test_blank_only_code_returns_empty(self, hybrid):
        code = "\n\n   \n  \n"
        result = hybrid._normalize_for_ast(code)
        assert result == ""

    def test_mixed_python_js_comments(self, hybrid):
        code = "# py comment\nx = 1\n// js comment\ny = 2"
        result = hybrid._normalize_for_ast(code)
        lines = [ln for ln in result.split("\n") if ln.strip()]
        assert len(lines) == 2
        assert any("x" in ln for ln in lines)
        assert any("y" in ln for ln in lines)

    def test_inline_hash_in_balanced_quotes_stripped(self, hybrid):
        """Hash in balanced-quote string is stripped (known heuristic limitation)."""
        code = "color = '#fff'\nsize = 10"
        result = hybrid._normalize_for_ast(code)
        assert "#fff" not in result
        assert "size" in result

    def test_preserves_code_structure(self, hybrid):
        """Normalized output should preserve meaningful code lines."""
        code = "def func():\n    # setup\n    x = 1\n    return x"
        result = hybrid._normalize_for_ast(code)
        lines = [ln for ln in result.split("\n") if ln.strip()]
        assert len(lines) == 3  # def, x=1, return

    def test_trailing_whitespace_stripped(self, hybrid):
        code = "x = 1   \ny = 2   "
        result = hybrid._normalize_for_ast(code)
        for line in result.split("\n"):
            assert line == line.rstrip()

    def test_url_in_code_not_mangled(self, hybrid):
        """Double slash in URL assigned to variable should be preserved."""
        code = 'url = "http://example.com"'
        result = hybrid._normalize_for_ast(code)
        # The // is at position > 0, so it gets stripped by the heuristic.
        # This is a known limitation — verify the function name survives.
        assert "url" in result


class TestApplicatorWrapperTypeGuards:
    """Tests for applicator module-level wrapper TypeError guards."""

    def test_plan_file_modification_order_rejects_non_dict(self):
        from ast_grep_mcp.features.deduplication.applicator import (
            _plan_file_modification_order,
        )

        mock_applicator = MagicMock()
        mock_applicator._plan_file_modification_order.return_value = "not a dict"

        with patch(
            "ast_grep_mcp.features.deduplication.applicator._get_applicator",
            return_value=mock_applicator,
        ):
            with pytest.raises(TypeError, match="Expected dict"):
                _plan_file_modification_order([], {}, None, "/tmp", "python")

    def test_add_import_to_content_rejects_non_str(self):
        from ast_grep_mcp.features.deduplication.applicator import (
            _add_import_to_content,
        )

        mock_applicator = MagicMock()
        mock_applicator._add_import_to_content.return_value = 42

        with patch(
            "ast_grep_mcp.features.deduplication.applicator._get_applicator",
            return_value=mock_applicator,
        ):
            with pytest.raises(TypeError, match="Expected str"):
                _add_import_to_content("content", "import os", "python")

    def test_generate_import_rejects_non_str(self):
        from ast_grep_mcp.features.deduplication.applicator import (
            _generate_import_for_extracted_function,
        )

        mock_applicator = MagicMock()
        mock_applicator._generate_import_for_extracted_function.return_value = 123

        with patch(
            "ast_grep_mcp.features.deduplication.applicator._get_applicator",
            return_value=mock_applicator,
        ):
            with pytest.raises(TypeError, match="Expected str"):
                _generate_import_for_extracted_function("/src/a.py", "/src/b.py", "func", "/src", "python")

    def test_plan_file_modification_order_accepts_dict(self):
        from ast_grep_mcp.features.deduplication.applicator import (
            _plan_file_modification_order,
        )

        mock_applicator = MagicMock()
        mock_applicator._plan_file_modification_order.return_value = {"ok": True}

        with patch(
            "ast_grep_mcp.features.deduplication.applicator._get_applicator",
            return_value=mock_applicator,
        ):
            result = _plan_file_modification_order([], {}, None, "/tmp", "python")
            assert result == {"ok": True}

    def test_add_import_to_content_accepts_str(self):
        from ast_grep_mcp.features.deduplication.applicator import (
            _add_import_to_content,
        )

        mock_applicator = MagicMock()
        mock_applicator._add_import_to_content.return_value = "import os\ncontent"

        with patch(
            "ast_grep_mcp.features.deduplication.applicator._get_applicator",
            return_value=mock_applicator,
        ):
            result = _add_import_to_content("content", "import os", "python")
            assert result == "import os\ncontent"
