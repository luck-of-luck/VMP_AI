"""Tests for _count_structural_braces in condense service."""

from ast_grep_mcp.features.condense.service import _count_structural_braces


class TestCountStructuralBraces:
    """Test string/comment/template-literal awareness of brace counting."""

    def test_plain_open_brace(self):
        assert _count_structural_braces("function foo() {") == 1

    def test_plain_close_brace(self):
        assert _count_structural_braces("}") == -1

    def test_balanced_braces(self):
        assert _count_structural_braces("if (x) { y() }") == 0

    def test_braces_in_double_quoted_string(self):
        assert _count_structural_braces('const x = "{ hello }";') == 0

    def test_braces_in_single_quoted_string(self):
        assert _count_structural_braces("const x = '{ hello }';") == 0

    def test_braces_in_template_literal(self):
        assert _count_structural_braces("const x = `{ hello }`;") == 0

    def test_braces_after_line_comment(self):
        assert _count_structural_braces("x = 1; // { not counted }") == 0

    def test_structural_brace_before_comment(self):
        assert _count_structural_braces("if (x) { // open") == 1

    def test_escaped_quote_in_string(self):
        assert _count_structural_braces(r'const x = "escaped \" { }";') == 0

    def test_empty_line(self):
        assert _count_structural_braces("") == 0

    def test_mixed_structural_and_string(self):
        assert _count_structural_braces('if ("}" === x) {') == 1

    def test_nested_braces(self):
        assert _count_structural_braces("const obj = { a: { b: 1 }") == 1

    def test_only_close_brace_in_string(self):
        assert _count_structural_braces("console.log('}');") == 0
