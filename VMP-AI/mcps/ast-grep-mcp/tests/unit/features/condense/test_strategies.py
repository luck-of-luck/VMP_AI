"""Tests for strategy definitions and validation."""

from ast_grep_mcp.features.condense.strategies import (
    STRATEGY_DESCRIPTIONS,
    STRATEGY_REDUCTION_RATIOS,
    VALID_STRATEGIES,
    describe_strategy,
    validate_strategy,
)


class TestValidStrategies:
    def test_all_expected_strategies_present(self):
        assert "ai_chat" in VALID_STRATEGIES
        assert "ai_analysis" in VALID_STRATEGIES
        assert "archival" in VALID_STRATEGIES
        assert "polyglot" in VALID_STRATEGIES

    def test_reduction_ratios_in_range(self):
        for strategy, ratio in STRATEGY_REDUCTION_RATIOS.items():
            assert 0.0 < ratio < 1.0, f"{strategy} ratio {ratio} out of range"

    def test_ai_chat_highest_reduction(self):
        assert STRATEGY_REDUCTION_RATIOS["ai_chat"] > STRATEGY_REDUCTION_RATIOS["ai_analysis"]
        assert STRATEGY_REDUCTION_RATIOS["ai_chat"] > STRATEGY_REDUCTION_RATIOS["archival"]

    def test_archival_lowest_reduction(self):
        assert STRATEGY_REDUCTION_RATIOS["archival"] <= STRATEGY_REDUCTION_RATIOS["ai_analysis"]


class TestValidateStrategy:
    def test_known_strategy_returns_true(self):
        for s in VALID_STRATEGIES:
            assert validate_strategy(s) is True

    def test_unknown_strategy_returns_false(self):
        assert validate_strategy("unknown") is False
        assert validate_strategy("") is False
        assert validate_strategy("AI_CHAT") is False  # case-sensitive


class TestDescribeStrategy:
    def test_known_strategy_returns_string(self):
        for s in VALID_STRATEGIES:
            desc = describe_strategy(s)
            assert isinstance(desc, str)
            assert len(desc) > 0

    def test_unknown_strategy_returns_error_string(self):
        desc = describe_strategy("nonexistent")
        assert "nonexistent" in desc.lower() or "unknown" in desc.lower()

    def test_descriptions_not_empty(self):
        for s in VALID_STRATEGIES:
            assert STRATEGY_DESCRIPTIONS[s].strip() != ""
