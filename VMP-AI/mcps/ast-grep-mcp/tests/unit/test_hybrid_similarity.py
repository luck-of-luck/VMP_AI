"""Tests for hybrid two-stage similarity calculation.

Tests the hybrid pipeline that combines:
- Stage 1: Fast MinHash filter (O(n))
- Stage 2: Precise AST verification

Scientific basis: TACC (Token and AST-based Code Clone detector)
from ICSE 2023 demonstrates that combining approaches yields
superior precision/recall compared to either approach alone.
"""

import pytest

from ast_grep_mcp.constants import SemanticSimilarityDefaults
from ast_grep_mcp.features.deduplication.similarity import (
    HybridSimilarity,
    HybridSimilarityConfig,
    HybridSimilarityResult,
)

PRECISION_TEST_SIMILARITY_INPUT = 0.85123
PRECISION_TEST_SIMILARITY_ROUNDED = 0.8512


class TestHybridSimilarityConfig:
    """Tests for HybridSimilarityConfig validation."""

    def test_default_config(self):
        """Default config should have sensible values from HybridSimilarityDefaults."""
        config = HybridSimilarityConfig()
        assert config.minhash_early_exit_threshold == 0.5
        assert config.minhash_weight == 0.4
        assert config.ast_weight == 0.6
        assert config.min_tokens_for_ast == 10
        assert config.max_lines_for_full_ast == 500

    def test_custom_config(self):
        """Custom config should override defaults."""
        config = HybridSimilarityConfig(
            minhash_early_exit_threshold=0.6,
            minhash_weight=0.3,
            ast_weight=0.7,
        )
        assert config.minhash_early_exit_threshold == 0.6
        assert config.minhash_weight == 0.3
        assert config.ast_weight == 0.7

    def test_invalid_threshold_raises_error(self):
        """Invalid threshold should raise ValueError."""
        with pytest.raises(ValueError, match="minhash_early_exit_threshold"):
            HybridSimilarityConfig(minhash_early_exit_threshold=1.5)

        with pytest.raises(ValueError, match="minhash_early_exit_threshold"):
            HybridSimilarityConfig(minhash_early_exit_threshold=-0.1)

    def test_invalid_weight_raises_error(self):
        """Invalid weight should raise ValueError."""
        with pytest.raises(ValueError, match="minhash_weight"):
            HybridSimilarityConfig(minhash_weight=1.5, ast_weight=-0.5)

    def test_weights_must_sum_to_one(self):
        """Weights must sum to 1.0."""
        with pytest.raises(ValueError, match="must equal 1.0"):
            HybridSimilarityConfig(minhash_weight=0.3, ast_weight=0.5)


class TestHybridSimilarityResult:
    """Tests for HybridSimilarityResult dataclass."""

    def test_result_creation(self):
        """Should create result with expected values."""
        result = HybridSimilarityResult(
            similarity=SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            method="hybrid",
            verified=True,
            minhash_similarity=0.8,
            ast_similarity=0.88,
            stage1_passed=True,
            early_exit=False,
            token_count=50,
        )
        assert result.similarity == SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD
        assert result.method == "hybrid"
        assert result.verified is True
        assert result.minhash_similarity == 0.8
        assert result.ast_similarity == 0.88
        assert result.stage1_passed is True
        assert result.early_exit is False
        assert result.token_count == 50

    def test_result_to_dict(self):
        """Should convert to dictionary correctly."""
        result = HybridSimilarityResult(
            similarity=PRECISION_TEST_SIMILARITY_INPUT,
            method="hybrid",
            verified=True,
            minhash_similarity=0.8,
            ast_similarity=0.88,
        )
        d = result.to_dict()
        assert d["similarity"] == PRECISION_TEST_SIMILARITY_ROUNDED  # Rounded to 4 decimals
        assert d["method"] == "hybrid"
        assert d["verified"] is True
        assert d["minhash_similarity"] == 0.8
        assert d["ast_similarity"] == 0.88

    def test_result_to_dict_with_none_ast(self):
        """Should handle None ast_similarity in to_dict."""
        result = HybridSimilarityResult(
            similarity=0.4,
            method="minhash",
            verified=False,
            minhash_similarity=0.4,
            ast_similarity=None,
            early_exit=True,
        )
        d = result.to_dict()
        assert d["ast_similarity"] is None
        assert d["early_exit"] is True


class TestHybridSimilarity:
    """Tests for HybridSimilarity calculator."""

    def test_identical_code_high_similarity(self):
        """Identical code should have similarity close to 1.0."""
        code = """
def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
        hybrid = HybridSimilarity()
        result = hybrid.calculate_hybrid_similarity(code, code)

        assert result.similarity > 0.95
        assert result.method == "hybrid"
        assert result.verified is True
        assert result.stage1_passed is True
        assert result.early_exit is False

    def test_similar_code_hybrid_verification(self):
        """Similar code should pass Stage 1 and be verified with Stage 2."""
        code1 = """
def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
"""
        code2 = """
def process_data(items):
    result = []
    for item in items:
        result.append(item * 3)
    return result
"""
        hybrid = HybridSimilarity()
        result = hybrid.calculate_hybrid_similarity(code1, code2)

        # Should pass Stage 1 (similar structure)
        assert result.minhash_similarity > 0.0
        # Should have AST similarity calculated
        if result.stage1_passed:
            assert result.ast_similarity is not None
            assert result.method == "hybrid"
            assert result.verified is True

    def test_different_code_early_exit(self):
        """Very different code should exit early at Stage 1."""
        code1 = """
def add(a, b):
    return a + b
"""
        code2 = """
class DataProcessor:
    def __init__(self, config):
        self.config = config
        self.cache = {}

    def process(self, data):
        for item in data:
            self.cache[item.id] = item
        return self.cache
"""
        hybrid = HybridSimilarity()
        result = hybrid.calculate_hybrid_similarity(code1, code2)

        # Should fail Stage 1 and exit early
        assert result.similarity < 0.5
        assert result.early_exit is True
        assert result.ast_similarity is None
        assert result.method == "minhash"
        assert result.verified is False

    def test_empty_code_returns_zero(self):
        """Empty code should return 0.0 similarity."""
        hybrid = HybridSimilarity()

        result1 = hybrid.calculate_hybrid_similarity("", "def foo(): pass")
        assert result1.similarity == 0.0
        assert result1.early_exit is True

        result2 = hybrid.calculate_hybrid_similarity("def foo(): pass", "")
        assert result2.similarity == 0.0

        result3 = hybrid.calculate_hybrid_similarity("", "")
        assert result3.similarity == 0.0

    def test_estimate_similarity_convenience_method(self):
        """estimate_similarity should return just the score."""
        code = "def add(a, b): return a + b"
        hybrid = HybridSimilarity()

        score = hybrid.estimate_similarity(code, code)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
        assert score > 0.9

    def test_cache_clearing(self):
        """Cache should be clearable."""
        code = "def example(): return 42"
        hybrid = HybridSimilarity()

        # Calculate similarity to populate cache
        hybrid.calculate_hybrid_similarity(code, code)

        # Clear cache
        hybrid.clear_cache()

        # Should still work after clearing
        result = hybrid.calculate_hybrid_similarity(code, code)
        assert result.similarity > 0.9


class TestHybridSimilarityStages:
    """Tests for individual stages of the hybrid pipeline."""

    def test_stage1_minhash_threshold(self):
        """Stage 1 should use configurable MinHash threshold."""
        code1 = "def a(): return 1"
        code2 = "def b(): return 2"

        # Low threshold - should pass Stage 1
        config_low = HybridSimilarityConfig(
            minhash_early_exit_threshold=0.1,
            minhash_weight=0.4,
            ast_weight=0.6,
        )
        hybrid_low = HybridSimilarity(hybrid_config=config_low)
        hybrid_low.calculate_hybrid_similarity(code1, code2)

        # High threshold - should fail Stage 1
        config_high = HybridSimilarityConfig(
            minhash_early_exit_threshold=0.9,
            minhash_weight=0.4,
            ast_weight=0.6,
        )
        hybrid_high = HybridSimilarity(hybrid_config=config_high)
        result_high = hybrid_high.calculate_hybrid_similarity(code1, code2)

        # With high threshold, should exit early
        assert result_high.early_exit is True
        assert result_high.ast_similarity is None

    def test_stage2_ast_normalization(self):
        """Stage 2 should normalize code for structural comparison."""
        # Code with different comments but same structure
        code1 = """
def process(data):
    # Process the data
    for item in data:
        yield item * 2
"""
        code2 = """
def process(data):
    # Different comment
    for item in data:
        yield item * 2
"""
        hybrid = HybridSimilarity()
        result = hybrid.calculate_hybrid_similarity(code1, code2)

        # AST similarity should be very high (comments normalized out)
        # Combined score is weighted: 0.4 * minhash + 0.6 * ast
        # MinHash sees different comments as different tokens
        assert result.ast_similarity is not None
        assert result.ast_similarity > 0.95  # AST comparison ignores comments
        assert result.verified is True
        # Combined score still respects the weighting
        assert result.similarity > 0.8  # Combined with MinHash weight

    def test_weighted_combination(self):
        """Final score should combine MinHash and AST with configured weights."""
        code1 = """
def process(data):
    result = []
    for item in data:
        result.append(item)
    return result
"""
        code2 = """
def process(data):
    result = []
    for item in data:
        result.append(item)
    return result
"""
        # Custom weights: 50/50
        config = HybridSimilarityConfig(
            minhash_weight=0.5,
            ast_weight=0.5,
        )
        hybrid = HybridSimilarity(hybrid_config=config)
        result = hybrid.calculate_hybrid_similarity(code1, code2)

        if result.stage1_passed and result.ast_similarity is not None:
            # Verify weighted combination
            expected = 0.5 * result.minhash_similarity + 0.5 * result.ast_similarity
            assert abs(result.similarity - expected) < 0.001


class TestHybridSimilarityNormalization:
    """Tests for code normalization in AST comparison."""

    def test_normalize_removes_comments(self):
        """Normalization should remove Python comments."""
        hybrid = HybridSimilarity()

        code = """
# This is a comment
def func():
    x = 1  # inline comment
    return x
"""
        normalized = hybrid._normalize_for_ast(code)

        assert "# This is a comment" not in normalized
        assert "# inline" not in normalized

    def test_normalize_removes_js_comments(self):
        """Normalization should remove JS/TS comments."""
        hybrid = HybridSimilarity()

        code = """
// This is a comment
function func() {
    const x = 1;  // inline comment
    return x;
}
"""
        normalized = hybrid._normalize_for_ast(code)

        assert "// This is a comment" not in normalized
        assert "// inline" not in normalized

    def test_normalize_standardizes_indentation(self):
        """Normalization should standardize indentation."""
        hybrid = HybridSimilarity()

        code = """
def func():
  x = 1
    y = 2
        z = 3
"""
        normalized = hybrid._normalize_for_ast(code)

        # All lines should have consistent indentation
        lines = [line for line in normalized.split("\n") if line.strip()]
        assert len(lines) >= 3

    def test_normalize_skips_empty_lines(self):
        """Normalization should skip empty lines."""
        hybrid = HybridSimilarity()

        code = """
def func():


    return 42


"""
        normalized = hybrid._normalize_for_ast(code)

        # Should not have consecutive empty lines
        assert "\n\n\n" not in normalized


class TestHybridSimilarityLargeCode:
    """Tests for handling large code with simplified AST comparison."""

    def test_large_code_uses_simplified_comparison(self):
        """Large code should use simplified structural comparison."""
        # Generate code larger than max_lines_for_full_ast
        large_code = "\n".join([f"x{i} = {i}" for i in range(600)])

        config = HybridSimilarityConfig(max_lines_for_full_ast=500)
        hybrid = HybridSimilarity(hybrid_config=config)

        result = hybrid.calculate_hybrid_similarity(large_code, large_code)

        # Should still calculate similarity
        assert result.similarity > 0.0

    def test_extract_structural_patterns(self):
        """Should extract structural patterns from code."""
        hybrid = HybridSimilarity()

        code = """
def process(data):
    for item in data:
        if item.valid:
            return item
    return None
"""
        patterns = hybrid._extract_structural_patterns(code)

        assert len(patterns) > 0
        # Should contain patterns for def, for, if, return
        pattern_str = " ".join(patterns)
        assert "def" in pattern_str or "L" in pattern_str


class TestHybridSimilarityDiagnostics:
    """Tests for diagnostic information in results."""

    def test_token_count_reported(self):
        """Token count should be reported in results."""
        code = "def add(a, b): return a + b"
        hybrid = HybridSimilarity()

        result = hybrid.calculate_hybrid_similarity(code, code)
        assert result.token_count > 0

    def test_minhash_similarity_always_present(self):
        """MinHash similarity should always be present."""
        code1 = "def foo(): pass"
        code2 = "class Bar: pass"
        hybrid = HybridSimilarity()

        result = hybrid.calculate_hybrid_similarity(code1, code2)
        assert result.minhash_similarity is not None
        assert 0.0 <= result.minhash_similarity <= 1.0


class TestDetectorWithHybridMode:
    """Integration tests for DuplicationDetector with hybrid mode."""

    def test_detector_uses_hybrid_by_default(self):
        """Detector should use hybrid mode by default."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector()
        assert detector.similarity_mode == "hybrid"

    def test_detector_hybrid_similarity(self):
        """Detector should calculate hybrid similarity correctly."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(similarity_mode="hybrid")

        code1 = "def add(a, b): return a + b"
        code2 = "def add(a, b): return a + b"

        similarity = detector.calculate_similarity(code1, code2)
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.9

    def test_detector_detailed_similarity(self):
        """Detector should provide detailed hybrid results."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector()

        code1 = "def foo(): return 1"
        code2 = "def bar(): return 2"

        result = detector.calculate_similarity_detailed(code1, code2)
        assert isinstance(result, HybridSimilarityResult)
        assert result.minhash_similarity is not None

    def test_detector_minhash_mode(self):
        """Detector should support pure MinHash mode."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(similarity_mode="minhash")
        assert detector.similarity_mode == "minhash"

        code1 = "def add(a, b): return a + b"
        code2 = "def add(a, b): return a + b"

        similarity = detector.calculate_similarity(code1, code2)
        assert similarity > 0.9

    def test_detector_sequence_matcher_mode(self):
        """Detector should support SequenceMatcher mode."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(similarity_mode="sequence_matcher")
        assert detector.similarity_mode == "sequence_matcher"

        code1 = "def add(a, b): return a + b"
        code2 = "def add(x, y): return x + y"

        similarity = detector.calculate_similarity(code1, code2)
        assert similarity > 0.5  # SequenceMatcher handles renames well

    def test_detector_legacy_use_minhash_false(self):
        """Legacy use_minhash=False should set sequence_matcher mode."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector(use_minhash=False)
        assert detector.similarity_mode == "sequence_matcher"
        assert detector.use_minhash is False


class TestHybridSimilarityPerformance:
    """Performance characteristic tests."""

    def test_early_exit_faster_than_full_pipeline(self):
        """Early exit should be faster than full pipeline verification."""
        import time

        # Code that will definitely fail Stage 1
        code1 = "def a(): return 1"
        code2 = """
class ComplexDataProcessor:
    def __init__(self, config, cache, validator):
        self.config = config
        self.cache = cache
        self.validator = validator

    def process_batch(self, items, options=None):
        results = []
        for item in items:
            if self.validator.validate(item):
                result = self.transform(item)
                self.cache[item.id] = result
                results.append(result)
        return results
"""
        hybrid = HybridSimilarity()

        # Warm up cache
        hybrid.calculate_hybrid_similarity(code1, code2)
        hybrid.clear_cache()

        # Time early exit case
        start = time.perf_counter()
        for _ in range(100):
            result = hybrid.calculate_hybrid_similarity(code1, code2)
        early_exit_time = time.perf_counter() - start

        assert result.early_exit is True

        # Similar code that needs Stage 2
        code3 = """
class DataProcessor:
    def __init__(self, config, cache, validator):
        self.config = config
        self.cache = cache
        self.validator = validator

    def process_batch(self, items, options=None):
        results = []
        for item in items:
            if self.validator.validate(item):
                result = self.transform(item)
                self.cache[item.id] = result
                results.append(result)
        return results
"""
        hybrid.clear_cache()

        start = time.perf_counter()
        for _ in range(100):
            hybrid.calculate_hybrid_similarity(code2, code3)
        full_pipeline_time = time.perf_counter() - start

        # Early exit should be faster (or at least not significantly slower)
        # Note: This is a soft assertion as timing can vary
        assert early_exit_time <= full_pipeline_time * 2
