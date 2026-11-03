"""Tests for _normalize_indentation in similarity.py."""

from ast_grep_mcp.features.deduplication.similarity import HybridSimilarity


class TestNormalizeIndentation:
    """Test adaptive 4-space vs 2-space indentation normalization."""

    calc = HybridSimilarity.__new__(HybridSimilarity)

    def test_two_space_indent_normalized_to_four(self):
        result = self.calc._normalize_indentation("  x = 1")
        assert result == "    x = 1"

    def test_four_space_indent_stays_four(self):
        result = self.calc._normalize_indentation("    x = 1")
        assert result == "    x = 1"

    def test_eight_space_indent_four_space_style(self):
        result = self.calc._normalize_indentation("        x = 1")
        assert result == "        x = 1"

    def test_six_space_indent_treated_as_two_space(self):
        # 6 % 4 != 0, so divisor is 2: 6 // 2 = 3 levels = 12 spaces
        result = self.calc._normalize_indentation("      x = 1")
        assert result == "            x = 1"

    def test_no_indent(self):
        result = self.calc._normalize_indentation("x = 1")
        assert result == "x = 1"

    def test_same_function_two_vs_four_space(self):
        """Functions with different indent styles should normalize identically."""
        two_space = "  return x"
        four_space = "    return x"
        assert self.calc._normalize_indentation(two_space) == self.calc._normalize_indentation(four_space)
