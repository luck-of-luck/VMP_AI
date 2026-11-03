"""Tests for extracted HybridSimilarityConfig validation helpers."""

import pytest

from ast_grep_mcp.features.deduplication.similarity import HybridSimilarityConfig


class TestValidateWeightBounds:
    """Test _validate_weight_bounds data-driven validation."""

    def test_valid_config_passes(self):
        cfg = HybridSimilarityConfig()
        cfg._validate_weight_bounds()  # should not raise

    def test_negative_minhash_weight(self):
        cfg = HybridSimilarityConfig.__new__(HybridSimilarityConfig)
        cfg.minhash_early_exit_threshold = 0.5
        cfg.minhash_weight = -0.1
        cfg.ast_weight = 0.5
        cfg.semantic_weight = 0.0
        cfg.semantic_stage_threshold = 0.5
        with pytest.raises(ValueError, match="minhash_weight"):
            cfg._validate_weight_bounds()

    def test_ast_weight_above_one(self):
        cfg = HybridSimilarityConfig.__new__(HybridSimilarityConfig)
        cfg.minhash_early_exit_threshold = 0.5
        cfg.minhash_weight = 0.3
        cfg.ast_weight = 1.5
        cfg.semantic_weight = 0.0
        cfg.semantic_stage_threshold = 0.5
        with pytest.raises(ValueError, match="ast_weight"):
            cfg._validate_weight_bounds()

    def test_semantic_stage_threshold_negative(self):
        cfg = HybridSimilarityConfig.__new__(HybridSimilarityConfig)
        cfg.minhash_early_exit_threshold = 0.5
        cfg.minhash_weight = 0.3
        cfg.ast_weight = 0.7
        cfg.semantic_weight = 0.0
        cfg.semantic_stage_threshold = -0.1
        with pytest.raises(ValueError, match="semantic_stage_threshold"):
            cfg._validate_weight_bounds()


class TestValidateWeightSum:
    """Test _validate_weight_sum for 2-stage and 3-stage modes."""

    def test_two_stage_valid_sum(self):
        cfg = HybridSimilarityConfig(minhash_weight=0.4, ast_weight=0.6)
        cfg._validate_weight_sum()  # should not raise

    def test_two_stage_invalid_sum(self):
        cfg = HybridSimilarityConfig.__new__(HybridSimilarityConfig)
        cfg.enable_semantic = False
        cfg.minhash_weight = 0.3
        cfg.ast_weight = 0.3
        cfg.semantic_weight = 0.0
        with pytest.raises(ValueError, match="must equal 1.0"):
            cfg._validate_weight_sum()

    def test_three_stage_valid_sum(self):
        cfg = HybridSimilarityConfig.__new__(HybridSimilarityConfig)
        cfg.enable_semantic = True
        cfg.minhash_weight = 0.3
        cfg.ast_weight = 0.4
        cfg.semantic_weight = 0.3
        cfg._validate_weight_sum()  # should not raise

    def test_three_stage_invalid_sum(self):
        cfg = HybridSimilarityConfig.__new__(HybridSimilarityConfig)
        cfg.enable_semantic = True
        cfg.minhash_weight = 0.3
        cfg.ast_weight = 0.4
        cfg.semantic_weight = 0.1
        with pytest.raises(ValueError, match="semantic is enabled"):
            cfg._validate_weight_sum()


class TestApplySemanticRebalance:
    """Test _apply_semantic_rebalance_if_needed preserves or rebalances."""

    def test_rebalance_on_legacy_defaults_with_semantic(self):
        cfg = HybridSimilarityConfig(enable_semantic=True)
        # After rebalance, minhash_weight and ast_weight should change
        assert cfg.minhash_weight != 0.4  # original default was 0.4

    def test_no_rebalance_when_custom_weights(self):
        cfg = HybridSimilarityConfig.__new__(HybridSimilarityConfig)
        cfg.enable_semantic = True
        cfg.minhash_weight = 0.2
        cfg.ast_weight = 0.5
        cfg.semantic_weight = 0.3
        cfg._apply_semantic_rebalance_if_needed()
        # Custom weights should not be changed
        assert cfg.minhash_weight == 0.2
        assert cfg.ast_weight == 0.5
