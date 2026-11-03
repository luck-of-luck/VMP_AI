"""Tests for _apply_fix_pattern handling of list meta_vars."""

from ast_grep_mcp.features.quality.fixer import _apply_fix_pattern


class TestApplyFixPatternListMetavars:
    """Test that list values from $$$ multi-captures are joined."""

    def test_string_metavar(self):
        result = _apply_fix_pattern("eval(x)", "safe($VAR)", {"VAR": "x"})
        assert result == "safe(x)"

    def test_list_metavar_joined_with_space(self):
        # enforcer stores multi-capture keys like "ARGS" with list values
        result = _apply_fix_pattern("old(a b c)", "new($ARGS)", {"ARGS": ["a", "b", "c"]})
        assert result == "new(a b c)"

    def test_empty_list_metavar(self):
        result = _apply_fix_pattern("fn()", "fn($ARGS)", {"ARGS": []})
        assert result == "fn()"

    def test_single_item_list(self):
        result = _apply_fix_pattern("fn(only)", "fn($A)", {"A": ["only"]})
        assert result == "fn(only)"

    def test_mixed_string_and_list_metavars(self):
        result = _apply_fix_pattern(
            "old(x, y z)",
            "new($VAR, $REST)",
            {"VAR": "x", "REST": ["y", "z"]},
        )
        assert result == "new(x, y z)"
