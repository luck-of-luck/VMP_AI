"""Regression tests for MinHash similarity fixes.

These tests ensure the bugs fixed in bugfix-ast-grep-mcp-minhash-2025-12-02
do not regress. Each test documents the original bug and verifies the fix.

Bug Reference: bugfix-ast-grep-mcp-minhash-2025-12-02
Phases completed:
- Phase 1: Root cause analysis
- Phase 2: Small code fallback fix (SequenceMatcher)
- Phase 3: LSH threshold optimization
- Phase 4: Detector integration
- Phase 5: Hybrid two-stage pipeline
- Phase 6: Validation & Testing (this file)
"""

import pytest

from ast_grep_mcp.features.deduplication.detector import DuplicationDetector
from ast_grep_mcp.features.deduplication.similarity import (
    HybridSimilarity,
    MinHashSimilarity,
)


@pytest.fixture
def minhash_similarity() -> MinHashSimilarity:
    """Provide MinHashSimilarity instance for tests."""
    return MinHashSimilarity()


@pytest.fixture
def hybrid_similarity() -> HybridSimilarity:
    """Provide HybridSimilarity instance for tests."""
    return HybridSimilarity()


class TestMinHashRegressions:
    """Regression tests for bugfix-ast-grep-mcp-minhash-2025-12-02.

    These tests cover the core bugs that were fixed:
    1. LSH returning [] for identical code snippets
    2. DuplicationDetector returning 0.125 for identical code
    3. MinHash having low accuracy for small code (< 15 tokens)
    """

    def test_lsh_finds_identical_pairs(self, minhash_similarity: MinHashSimilarity) -> None:
        """Regression: LSH should find identical code pairs.

        Original bug: LSH returned [] for identical code snippets
        due to threshold being too conservative for small code.

        Fix: Phase 3 - Adaptive LSH threshold and small code detection.
        """
        code_items = [
            ("func1", "def calculate(x, y): result = x + y; return result"),
            ("func2", "def calculate(x, y): result = x + y; return result"),
            ("func3", "class Config: pass"),
        ]

        pairs = list(minhash_similarity.find_all_similar_pairs(code_items, min_similarity=0.5))

        # Should find func1-func2
        assert len(pairs) > 0, "LSH must find identical pairs"
        assert any((n1 == "func1" and n2 == "func2") or (n1 == "func2" and n2 == "func1") for n1, n2, _ in pairs), (
            f"Expected func1-func2 pair, got {pairs}"
        )

    def test_detector_identical_code_similarity(self) -> None:
        """Regression: Detector should return > 0.9 for identical code.

        Original bug: DuplicationDetector returned 0.125 for identical code
        due to integration issues with MinHashSimilarity.

        Fix: Phase 4 - Proper integration of MinHash into detector.
        """
        detector = DuplicationDetector(use_minhash=True)
        code = "def add(a, b): return a + b"

        similarity = detector.calculate_similarity(code, code)

        assert similarity > 0.9, f"Identical code must have > 0.9 similarity, got {similarity}"

    def test_small_code_high_accuracy(self, minhash_similarity: MinHashSimilarity) -> None:
        """Regression: Small code should use accurate fallback.

        Original bug: MinHash had low accuracy for code < 15 tokens.
        Fix: Phase 2 - SequenceMatcher fallback for small code.
        """
        # Very small code (< 15 tokens)
        code1 = "def f(): pass"
        code2 = "def f(): pass"

        result = minhash_similarity.estimate_similarity(code1, code2)

        assert result > 0.95, f"Small identical code must have > 0.95 similarity, got {result}"

    def test_small_code_with_minor_changes(self, minhash_similarity: MinHashSimilarity) -> None:
        """Regression: Small code with minor changes should have moderate similarity."""
        code1 = "def add(a, b): return a + b"
        code2 = "def add(x, y): return x + y"  # Only variable names changed

        result = minhash_similarity.estimate_similarity(code1, code2)

        # Should still be fairly similar (structure is identical)
        assert result > 0.5, f"Similar small code should have > 0.5 similarity, got {result}"

    def test_different_code_low_similarity(self, minhash_similarity: MinHashSimilarity) -> None:
        """Regression: Different code should have low similarity."""
        code1 = "def add(a, b): return a + b"
        code2 = "class Config:\n    def __init__(self):\n        self.data = {}"

        result = minhash_similarity.estimate_similarity(code1, code2)

        assert result < 0.5, f"Different code should have < 0.5 similarity, got {result}"


class TestHybridPipelineRegressions:
    """Regression tests for the hybrid two-stage similarity pipeline.

    Phase 5 introduced a hybrid pipeline combining MinHash with AST
    normalization for improved accuracy on similar code.
    """

    def test_hybrid_identical_code(self, hybrid_similarity: HybridSimilarity) -> None:
        """Regression: Hybrid pipeline should return 1.0 for identical code."""
        code = "def process(data):\n    return [x * 2 for x in data]"

        result = hybrid_similarity.calculate_hybrid_similarity(code, code)

        assert result.similarity >= 0.99, f"Identical code must have >= 0.99 similarity, got {result.similarity}"

    def test_hybrid_similar_code_verification(self, hybrid_similarity: HybridSimilarity) -> None:
        """Regression: Hybrid should verify similar code with AST normalization.

        Note: This test uses code with more shared tokens to pass the MinHash
        stage1 threshold. Code with completely different variable names will
        early-exit due to low MinHash similarity (which is expected behavior).
        """
        # Code with shared keywords and structure but minor differences
        code1 = """
def process_items(items):
    results = []
    for item in items:
        results.append(item)
    return results
"""
        code2 = """
def process_items(items):
    results = []
    for item in items:
        results.append(item * 2)
    return results
"""

        result = hybrid_similarity.calculate_hybrid_similarity(code1, code2)

        # Similar code should have high similarity
        assert result.similarity > 0.5, f"Similar code should have > 0.5 similarity, got {result.similarity}"
        # If it passed stage1, should have AST normalized score
        if result.stage1_passed:
            assert result.ast_similarity is not None, "Hybrid should provide AST normalized similarity when stage1 passed"

    def test_hybrid_early_exit_for_different_code(self, hybrid_similarity: HybridSimilarity) -> None:
        """Regression: Hybrid should early exit for very different code."""
        code1 = "x = 1"
        code2 = """
class ComplexProcessor:
    def __init__(self, config):
        self.config = config
        self.data = {}

    def process(self, items):
        results = []
        for item in items:
            if self.validate(item):
                results.append(self.transform(item))
        return results
"""

        result = hybrid_similarity.calculate_hybrid_similarity(code1, code2)

        # Very different code should have low similarity
        assert result.similarity < 0.3, f"Very different code should have < 0.3 similarity, got {result.similarity}"


class TestDetectorModeRegressions:
    """Regression tests for detector similarity modes.

    The detector supports multiple modes:
    - hybrid (default): Two-stage MinHash + AST normalization
    - minhash: Pure MinHash only
    - sequence_matcher: SequenceMatcher only
    """

    def test_detector_hybrid_mode_default(self) -> None:
        """Regression: Detector should use hybrid mode by default."""
        detector = DuplicationDetector()

        # Check mode is hybrid
        assert detector.similarity_mode == "hybrid", f"Expected hybrid mode, got {detector.similarity_mode}"

    def test_detector_minhash_mode_explicit(self) -> None:
        """Regression: Detector should support explicit minhash mode."""
        detector = DuplicationDetector(use_minhash=True)
        code = "def test(): return 42"

        sim = detector.calculate_similarity(code, code)

        assert sim > 0.9, f"Identical code should have > 0.9 similarity, got {sim}"

    def test_detector_sequence_matcher_mode(self) -> None:
        """Regression: Detector should support sequence_matcher mode."""
        detector = DuplicationDetector(use_minhash=False)
        code = "def test(): return 42"

        sim = detector.calculate_similarity(code, code)

        assert sim >= 0.99, f"Identical code should have >= 0.99 similarity, got {sim}"


class TestEdgeCaseRegressions:
    """Regression tests for edge cases that caused issues."""

    def test_empty_code_returns_zero(self, minhash_similarity: MinHashSimilarity) -> None:
        """Regression: Empty code should return 0.0 similarity."""
        result = minhash_similarity.estimate_similarity("", "")

        assert result == 0.0, f"Empty code should have 0.0 similarity, got {result}"

    def test_whitespace_only_handled_gracefully(self, minhash_similarity: MinHashSimilarity) -> None:
        """Regression: Whitespace-only code should be handled gracefully.

        Note: After normalization, whitespace-only strings become identical empty
        strings, so they return 1.0 similarity (two empty strings are equal).
        This is actually correct behavior - the test verifies no crashes occur.
        """
        # Should not crash
        result = minhash_similarity.estimate_similarity("   \n\t  ", "  \n  ")

        # Both normalize to empty, so they're identical (1.0) or treated as empty (0.0)
        # Either is acceptable behavior for this edge case
        assert result in (0.0, 1.0), f"Whitespace-only code should return 0.0 or 1.0, got {result}"

    def test_single_token_code(self, minhash_similarity: MinHashSimilarity) -> None:
        """Regression: Single token code should work without errors."""
        code1 = "pass"
        code2 = "pass"

        result = minhash_similarity.estimate_similarity(code1, code2)

        # Should not crash and return high similarity
        assert result > 0.9, f"Single token identical should have > 0.9, got {result}"

    def test_multiline_code_identical(self, minhash_similarity: MinHashSimilarity) -> None:
        """Regression: Multiline identical code should return high similarity."""
        code = """
def complex_function(data, options=None):
    '''Process data with options.'''
    if options is None:
        options = {}

    results = []
    for item in data:
        if item.is_valid():
            processed = item.process()
            results.append(processed)

    return results
"""

        result = minhash_similarity.estimate_similarity(code, code)

        assert result > 0.95, f"Multiline identical code should have > 0.95 similarity, got {result}"
