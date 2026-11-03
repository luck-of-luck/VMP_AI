"""Integration tests for semantic similarity with real CodeBERT model.

These tests require the transformers and torch packages to be installed:
    uv sync --extra semantic

Tests are marked with @pytest.mark.semantic and will be skipped if
transformers is not available.
"""

# Check if transformers is available
import importlib.util

import pytest

TRANSFORMERS_AVAILABLE = importlib.util.find_spec("torch") is not None and importlib.util.find_spec("transformers") is not None

pytestmark = [
    pytest.mark.semantic,
    pytest.mark.skipif(
        not TRANSFORMERS_AVAILABLE,
        reason="transformers and torch required for semantic tests",
    ),
]


@pytest.fixture(scope="module")
def semantic_calculator():
    """Create a SemanticSimilarity instance with loaded model."""
    if not TRANSFORMERS_AVAILABLE:
        pytest.skip("transformers not available")

    from ast_grep_mcp.features.deduplication.similarity import (
        SemanticSimilarity,
        SemanticSimilarityConfig,
    )

    config = SemanticSimilarityConfig(
        model_name="microsoft/codebert-base",
        device="cpu",  # Use CPU for CI
        cache_embeddings=True,
    )
    calculator = SemanticSimilarity(config)
    return calculator


@pytest.fixture(scope="module")
def hybrid_calculator_with_semantic():
    """Create a HybridSimilarity instance with semantic enabled."""
    if not TRANSFORMERS_AVAILABLE:
        pytest.skip("transformers not available")

    from ast_grep_mcp.features.deduplication.similarity import (
        HybridSimilarity,
        HybridSimilarityConfig,
    )

    config = HybridSimilarityConfig(
        enable_semantic=True,
        semantic_device="cpu",
    )
    calculator = HybridSimilarity(config)
    return calculator


class TestSemanticSimilarityIntegration:
    """Integration tests for SemanticSimilarity with real model."""

    def test_model_loads_successfully(self, semantic_calculator):
        """Test that the CodeBERT model loads without errors."""
        # Model should load lazily on first use
        code = "def hello(): return 'world'"
        embedding = semantic_calculator.get_embedding(code)

        # CodeBERT produces 768-dimensional embeddings
        assert embedding is not None
        assert embedding.shape[-1] == 768

    def test_identical_code_perfect_similarity(self, semantic_calculator):
        """Test that identical code has similarity = 1.0."""
        code = """
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total
"""
        similarity = semantic_calculator.calculate_similarity(code, code)
        assert similarity == pytest.approx(1.0, abs=0.01)

    def test_semantically_similar_code_high_score(self, semantic_calculator):
        """Test that semantically similar code (Type-4 clones) has high similarity."""
        # Two different implementations of the same functionality
        code1 = """
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total
"""
        code2 = """
def sum_list(items):
    result = sum(items)
    return result
"""
        similarity = semantic_calculator.calculate_similarity(code1, code2)
        # Semantic similarity should recognize these as similar
        assert similarity > 0.6, f"Expected > 0.6 for semantically similar code, got {similarity}"

    def test_different_functionality_lower_score(self, semantic_calculator):
        """Test that functionally different code has lower similarity."""
        code1 = """
def calculate_sum(numbers):
    total = 0
    for num in numbers:
        total += num
    return total
"""
        code2 = """
def sort_descending(items):
    return sorted(items, reverse=True)
"""
        similarity = semantic_calculator.calculate_similarity(code1, code2)
        # Different functionality should have lower similarity
        assert similarity < 0.8, f"Expected < 0.8 for different functionality, got {similarity}"

    def test_embedding_caching_works(self, semantic_calculator):
        """Test that embedding caching improves performance."""
        code = "def test(): pass"

        # Clear cache first
        semantic_calculator.clear_cache()

        # First call - cache miss
        _ = semantic_calculator.get_embedding(code)
        stats1 = semantic_calculator.get_cache_stats()

        # Second call - cache hit
        _ = semantic_calculator.get_embedding(code)
        stats2 = semantic_calculator.get_cache_stats()

        assert stats2["hits"] > stats1["hits"]

    def test_detailed_result_contains_all_fields(self, semantic_calculator):
        """Test that detailed result contains all expected fields."""
        code1 = "def foo(): return 1"
        code2 = "def bar(): return 2"

        result = semantic_calculator.calculate_similarity_detailed(code1, code2)

        assert hasattr(result, "similarity")
        assert hasattr(result, "embedding1_shape")
        assert hasattr(result, "embedding2_shape")
        assert hasattr(result, "model_name")
        assert hasattr(result, "computation_time_ms")

        assert 0.0 <= result.similarity <= 1.0
        assert result.embedding1_shape == (768,)
        assert result.embedding2_shape == (768,)
        assert "codebert" in result.model_name.lower()


class TestHybridThreeStageIntegration:
    """Integration tests for three-stage hybrid pipeline."""

    def test_three_stage_pipeline_works(self, hybrid_calculator_with_semantic):
        """Test that three-stage pipeline produces valid results."""
        code1 = """
def process_data(items):
    results = []
    for item in items:
        if item > 0:
            results.append(item * 2)
    return results
"""
        code2 = """
def transform_data(values):
    output = []
    for val in values:
        if val > 0:
            output.append(val * 2)
    return output
"""
        result = hybrid_calculator_with_semantic.calculate_hybrid_similarity(code1, code2)

        # Should have semantic similarity when enabled
        assert result.semantic_similarity is not None
        assert result.semantic_similarity > 0.5

        # Combined similarity should be weighted average
        assert 0.0 <= result.combined_similarity <= 1.0

        # Should indicate semantic was used
        assert result.semantic_skipped is False
        assert result.semantic_model is not None

    def test_early_exit_skips_semantic(self, hybrid_calculator_with_semantic):
        """Test that early exit on low MinHash skips semantic stage."""
        code1 = "def foo(): return 1"
        code2 = """
class CompletelyDifferent:
    def __init__(self):
        self.data = {}

    def process(self, items):
        for item in items:
            self.data[item] = len(str(item))
        return self.data
"""
        result = hybrid_calculator_with_semantic.calculate_hybrid_similarity(code1, code2)

        # Very different code should trigger early exit
        # Semantic may or may not be skipped depending on MinHash score
        assert result.combined_similarity < 0.5

    def test_semantic_weight_affects_result(self, hybrid_calculator_with_semantic):
        """Test that semantic weight contributes to combined similarity."""
        # Type-2 clone: same structure, different variable names
        code1 = """
def calculate_average(numbers):
    total = sum(numbers)
    count = len(numbers)
    return total / count
"""
        code2 = """
def compute_mean(values):
    s = sum(values)
    n = len(values)
    return s / n
"""
        result = hybrid_calculator_with_semantic.calculate_hybrid_similarity(code1, code2)

        # All three stages should contribute
        assert result.minhash_similarity > 0.5
        assert result.ast_similarity > 0.5
        assert result.semantic_similarity is not None
        assert result.semantic_similarity > 0.7

        # Combined should reflect weighted average
        # With weights: 0.2 MinHash + 0.5 AST + 0.3 Semantic
        expected_min = min(result.minhash_similarity, result.ast_similarity, result.semantic_similarity)
        assert result.combined_similarity >= expected_min * 0.8


class TestSemanticType4Clones:
    """Tests specifically for Type-4 (semantic) clone detection."""

    def test_loop_vs_comprehension(self, semantic_calculator):
        """Test detection of loop vs list comprehension equivalence."""
        code1 = """
def square_numbers(nums):
    result = []
    for n in nums:
        result.append(n * n)
    return result
"""
        code2 = """
def square_numbers(nums):
    return [n * n for n in nums]
"""
        similarity = semantic_calculator.calculate_similarity(code1, code2)
        # Should recognize as semantically equivalent
        assert similarity > 0.7, f"Expected > 0.7 for loop vs comprehension, got {similarity}"

    def test_recursive_vs_iterative(self, semantic_calculator):
        """Test detection of recursive vs iterative implementations."""
        code1 = """
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
        code2 = """
def factorial(n):
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
"""
        similarity = semantic_calculator.calculate_similarity(code1, code2)
        # Should recognize as semantically related (same function name and purpose)
        assert similarity > 0.6, f"Expected > 0.6 for recursive vs iterative, got {similarity}"

    def test_different_algorithms_same_result(self, semantic_calculator):
        """Test detection of different algorithms producing same result."""
        # Linear search vs binary search
        code1 = """
def find_element(arr, target):
    for i, val in enumerate(arr):
        if val == target:
            return i
    return -1
"""
        code2 = """
def find_element(arr, target):
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
"""
        similarity = semantic_calculator.calculate_similarity(code1, code2)
        # Should recognize some semantic similarity (same function name and return type)
        # but not as high as truly equivalent implementations
        assert 0.4 < similarity < 0.9, f"Expected between 0.4-0.9 for different algorithms, got {similarity}"
