"""Tests for utils.parsing shared primitives."""

from ast_grep_mcp.features.complexity.analyzer import _find_docstring_extent, _measure_docstring
from ast_grep_mcp.utils.parsing import detect_triple_quote, skip_blank_lines


class TestDetectTripleQuote:
    def test_double_quote(self) -> None:
        assert detect_triple_quote('"""docstring"""') == '"""'

    def test_single_quote(self) -> None:
        assert detect_triple_quote("'''docstring'''") == "'''"

    def test_no_triple_quote(self) -> None:
        assert detect_triple_quote("regular line") is None

    def test_empty_string(self) -> None:
        assert detect_triple_quote("") is None

    def test_single_quote_char(self) -> None:
        assert detect_triple_quote('"not triple"') is None

    def test_double_quote_only(self) -> None:
        assert detect_triple_quote('""not triple') is None

    def test_triple_quote_start_only(self) -> None:
        assert detect_triple_quote('"""start of multiline') == '"""'


class TestSkipBlankLines:
    def test_no_blanks(self) -> None:
        lines = ["code", "more code"]
        assert skip_blank_lines(lines, 0) == 0

    def test_skip_blanks(self) -> None:
        lines = ["", "  ", "code"]
        assert skip_blank_lines(lines, 0) == 2

    def test_start_midway(self) -> None:
        lines = ["code", "", "", "more"]
        assert skip_blank_lines(lines, 1) == 3

    def test_all_blank(self) -> None:
        lines = ["", "  ", "\t"]
        assert skip_blank_lines(lines, 0) == 3

    def test_empty_list(self) -> None:
        assert skip_blank_lines([], 0) == 0

    def test_start_at_end(self) -> None:
        lines = ["code"]
        assert skip_blank_lines(lines, 1) == 1

    def test_whitespace_only_lines(self) -> None:
        lines = ["  \t  ", "code"]
        assert skip_blank_lines(lines, 0) == 1


class TestMeasureDocstring:
    def test_single_line_double_quote(self) -> None:
        lines = ['    """One liner."""', "    pass"]
        assert _measure_docstring(lines, 0) == 1

    def test_single_line_single_quote(self) -> None:
        lines = ["    '''One liner.'''", "    pass"]
        assert _measure_docstring(lines, 0) == 1

    def test_multi_line(self) -> None:
        lines = ['    """', "    Multi line.", '    """', "    pass"]
        assert _measure_docstring(lines, 0) == 3

    def test_no_docstring(self) -> None:
        lines = ["    pass"]
        assert _measure_docstring(lines, 0) == 0

    def test_unclosed_docstring(self) -> None:
        lines = ['    """Start', "    no closing"]
        assert _measure_docstring(lines, 0) == 0


class TestFindDocstringExtent:
    def test_single_line_docstring(self) -> None:
        lines = ["def foo():", '    """One liner."""', "    pass"]
        assert _find_docstring_extent(lines, 1) == 1

    def test_multi_line_docstring(self) -> None:
        lines = ["def foo():", '    """', "    Multi line.", '    """', "    pass"]
        assert _find_docstring_extent(lines, 1) == 3

    def test_no_docstring(self) -> None:
        lines = ["def foo():", "    pass"]
        assert _find_docstring_extent(lines, 1) == 0

    def test_skips_blank_lines(self) -> None:
        lines = ["def foo():", "", '    """Docstring."""', "    pass"]
        assert _find_docstring_extent(lines, 1) == 1

    def test_all_blank_after_start(self) -> None:
        lines = ["def foo():", "", ""]
        assert _find_docstring_extent(lines, 1) == 0

    def test_start_beyond_end(self) -> None:
        lines = ["def foo():"]
        assert _find_docstring_extent(lines, 5) == 0
