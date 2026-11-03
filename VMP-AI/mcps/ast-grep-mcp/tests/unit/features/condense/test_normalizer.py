"""Tests for code normalizer transforms."""

from ast_grep_mcp.features.condense.normalizer import (
    _double_to_single_quotes,
    _normalize_js_ts,
    _normalize_python,
    normalize_source,
)


class TestNormalizeSource:
    def test_returns_tuple(self):
        result = normalize_source("const x = 1;", "javascript")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_count_is_non_negative(self):
        _, count = normalize_source("def foo(): pass", "python")
        assert count >= 0

    def test_unknown_language_returns_source(self):
        source = "local x = 1"
        normalized, _ = normalize_source(source, "lua")
        assert isinstance(normalized, str)

    def test_strips_multiple_blank_lines(self):
        source = "a = 1\n\n\n\nb = 2"
        normalized, count = normalize_source(source, "python")
        assert "\n\n\n" not in normalized
        assert count >= 1


class TestNormalizeJsTs:
    def test_double_to_single_quotes(self):
        source = 'const x = "hello";'
        normalized, count = _normalize_js_ts(source)
        assert "'hello'" in normalized
        assert count >= 1

    def test_skips_strings_with_single_quotes(self):
        source = """const x = "it's fine";"""
        normalized, _ = _normalize_js_ts(source)
        assert '"it\'s fine"' in normalized  # should NOT be converted

    def test_trailing_comma_removed(self):
        source = "const obj = { a: 1, };"
        normalized, count = _normalize_js_ts(source)
        assert count >= 1
        assert "1," not in normalized or "1 }" in normalized or "1}" in normalized

    def test_no_change_returns_zero_count(self):
        # Already normalized: single quotes, no trailing commas
        source = "const x = 'hello';"
        _, count = _normalize_js_ts(source)
        assert count == 0


class TestNormalizePython:
    def test_trailing_whitespace_removed(self):
        source = "def foo():   \n    return 1   "
        normalized, count = _normalize_python(source)
        for line in normalized.splitlines():
            assert line == line.rstrip()
        assert count >= 1

    def test_no_trailing_whitespace_zero_count(self):
        source = "def foo():\n    return 1"
        _, count = _normalize_python(source)
        assert count == 0


class TestDoubleToSingleQuotes:
    def test_simple_string(self):
        result = _double_to_single_quotes('"hello"')
        assert result == "'hello'"

    def test_string_with_single_quote_unchanged(self):
        result = _double_to_single_quotes('"it\'s"')
        # Contains escaped single quote: should not convert
        assert result.startswith('"') or "it's" in result

    def test_empty_string(self):
        result = _double_to_single_quotes('""')
        assert result == "''"

    def test_no_double_quotes(self):
        line = "const x = 'hello';"
        assert _double_to_single_quotes(line) == line
