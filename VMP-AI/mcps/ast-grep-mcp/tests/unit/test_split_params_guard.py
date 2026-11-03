"""Tests for _split_params depth guard and sync_checker rstrip fix."""

from ast_grep_mcp.features.documentation.docstring_generator import FunctionSignatureParser


class TestSplitParamsDepthGuard:
    """Test that > in arrow function defaults doesn't corrupt depth."""

    gen = FunctionSignatureParser.__new__(FunctionSignatureParser)

    def test_simple_params(self):
        result = self.gen._split_params("a, b, c")
        assert [p.strip() for p in result] == ["a", "b", "c"]

    def test_generic_type_param(self):
        result = self.gen._split_params("x: Map<string, number>, y: int")
        assert len(result) == 2
        assert "Map<string, number>" in result[0]

    def test_arrow_function_default(self):
        """Arrow function `=>` should not make depth go negative."""
        result = self.gen._split_params("fn: (x) => x > 0, y: number")
        assert len(result) == 2

    def test_nested_generics(self):
        result = self.gen._split_params("x: Map<string, List<int>>, y: string")
        assert len(result) == 2

    def test_empty_string(self):
        result = self.gen._split_params("")
        assert result == []

    def test_single_param(self):
        result = self.gen._split_params("x: number")
        assert result == ["x: number"]

    def test_braces_in_default_value(self):
        result = self.gen._split_params("opts: {a: 1, b: 2}, cb: () => void")
        assert len(result) == 2

    def test_multiple_greater_than(self):
        """Multiple > without matching < should not crash."""
        result = self.gen._split_params("a > b, c > d")
        assert len(result) == 2
