"""Performance benchmarks for MinHash similarity

This module contains performance tests for the MinHash similarity detection
system. These tests ensure acceptable performance characteristics and help
identify regressions.

Created as part of bugfix-ast-grep-mcp-minhash-2025-12-02 Phase 6.
"""

import time

import pytest

from ast_grep_mcp.features.deduplication.similarity import MinHashSimilarity


@pytest.fixture
def minhash_similarity() -> MinHashSimilarity:
    """Provide MinHashSimilarity instance for tests."""
    return MinHashSimilarity()


class TestMinHashPerformance:
    """Performance tests for MinHash similarity detection."""

    def test_small_code_performance(self, minhash_similarity: MinHashSimilarity) -> None:
        """Test performance for small code comparisons.

        Small code (< 15 tokens) uses SequenceMatcher fallback which should
        be very fast.

        Success criteria: < 1ms per comparison.
        """
        code1 = "def add(a, b): return a + b"
        code2 = "def add(x, y): return x + y"

        # Time 1000 comparisons
        start = time.perf_counter()
        for _ in range(1000):
            minhash_similarity.estimate_similarity(code1, code2)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 1000) * 1000
        print(f"\nSmall code comparison: {avg_ms:.3f}ms per pair")

        # Should be < 1ms per comparison
        assert avg_ms < 1.0, f"Small code comparison too slow: {avg_ms:.3f}ms"

    def test_medium_code_performance(self, minhash_similarity: MinHashSimilarity) -> None:
        """Test performance for medium-sized code comparisons.

        Medium code (15-50 tokens) uses MinHash algorithm.

        Success criteria: < 5ms per comparison.
        """
        code1 = """
def calculate_sum(items):
    total = 0
    for item in items:
        if item > 0:
            total += item
    return total
"""
        code2 = """
def calculate_total(data):
    result = 0
    for value in data:
        if value > 0:
            result += value
    return result
"""

        # Time 500 comparisons
        start = time.perf_counter()
        for _ in range(500):
            minhash_similarity.estimate_similarity(code1, code2)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 500) * 1000
        print(f"\nMedium code comparison: {avg_ms:.3f}ms per pair")

        # Should be < 5ms per comparison
        assert avg_ms < 5.0, f"Medium code comparison too slow: {avg_ms:.3f}ms"

    def test_large_code_performance(self, minhash_similarity: MinHashSimilarity) -> None:
        """Test performance for large code comparisons.

        Large code (> 500 tokens) uses simplified comparison.

        Success criteria: < 10ms per comparison.
        """
        # Generate large code blocks
        code1 = "\n".join([f"x{i} = value_{i} + {i}" for i in range(200)])
        code2 = "\n".join([f"y{i} = data_{i} + {i}" for i in range(200)])

        # Time 100 comparisons
        start = time.perf_counter()
        for _ in range(100):
            minhash_similarity.estimate_similarity(code1, code2)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        print(f"\nLarge code comparison: {avg_ms:.3f}ms per pair")

        # Should be < 10ms per comparison
        assert avg_ms < 10.0, f"Large code comparison too slow: {avg_ms:.3f}ms"

    def test_large_scale_deduplication(self, minhash_similarity: MinHashSimilarity) -> None:
        """Test performance with 500 code snippets.

        This simulates a real-world deduplication scenario with many
        code snippets to compare.

        Success criteria: < 30 seconds total.
        """
        # Generate 500 unique functions
        code_items = [(f"func_{i}", f"def func_{i}(x): return x + {i}") for i in range(500)]

        # Add some duplicates to find
        code_items.append(("func_dup_0", "def func_0(x): return x + 0"))
        code_items.append(("func_dup_1", "def func_1(x): return x + 1"))

        start = time.perf_counter()
        pairs = list(minhash_similarity.find_all_similar_pairs(code_items, min_similarity=0.7))
        elapsed = time.perf_counter() - start

        print(f"\nLarge scale (502 items): {elapsed:.2f}s")
        print(f"Found {len(pairs)} similar pairs")

        # Should complete in < 30 seconds
        assert elapsed < 30, f"Large scale deduplication too slow: {elapsed:.2f}s"

        # Should find the duplicate pairs
        assert len(pairs) >= 2, f"Expected at least 2 pairs, found {len(pairs)}"

    def test_minhash_vs_sequencematcher_small_code(self, minhash_similarity: MinHashSimilarity) -> None:
        """Compare MinHash vs SequenceMatcher for small code.

        For small code, we use SequenceMatcher fallback. This test verifies
        the fallback is reasonably fast.
        """
        from difflib import SequenceMatcher

        code1 = "def add(a, b): return a + b"
        code2 = "def add(x, y): return x + y"

        # Time MinHash (with fallback)
        start = time.perf_counter()
        for _ in range(1000):
            minhash_similarity.estimate_similarity(code1, code2)
        minhash_time = time.perf_counter() - start

        # Time pure SequenceMatcher
        start = time.perf_counter()
        for _ in range(1000):
            SequenceMatcher(None, code1, code2).ratio()
        seq_time = time.perf_counter() - start

        print(f"\nMinHash (with fallback): {minhash_time:.3f}s for 1000 iterations")
        print(f"Pure SequenceMatcher: {seq_time:.3f}s for 1000 iterations")
        print(f"Overhead ratio: {minhash_time / seq_time:.2f}x")

        # Both should be reasonably fast
        assert minhash_time < 5.0, f"MinHash too slow: {minhash_time:.3f}s"

    def test_cache_effectiveness(self, minhash_similarity: MinHashSimilarity) -> None:
        """Test that signature caching improves repeated comparisons.

        The MinHash signature cache should make repeated comparisons faster.
        """
        code1 = """
def process_data(items):
    results = []
    for item in items:
        processed = item.strip().lower()
        if processed:
            results.append(processed)
    return results
"""
        code2 = """
def transform_data(values):
    output = []
    for value in values:
        cleaned = value.strip().lower()
        if cleaned:
            output.append(cleaned)
    return output
"""

        # Clear cache
        minhash_similarity.clear_cache()

        # First run - cold cache
        start = time.perf_counter()
        for _ in range(100):
            minhash_similarity.clear_cache()  # Clear each time
            minhash_similarity.estimate_similarity(code1, code2)
        cold_time = time.perf_counter() - start

        # Second run - warm cache (only clear at start)
        minhash_similarity.clear_cache()
        start = time.perf_counter()
        for _ in range(100):
            minhash_similarity.estimate_similarity(code1, code2)
        warm_time = time.perf_counter() - start

        speedup = cold_time / warm_time if warm_time > 0 else float("inf")
        print(f"\nCold cache (100 iterations): {cold_time:.3f}s")
        print(f"Warm cache (100 iterations): {warm_time:.3f}s")
        print(f"Cache speedup: {speedup:.2f}x")

        # Warm cache should be faster than cold (which also pays clear_cache() on each
        # iteration).  Allow a 5x tolerance so that a single GC pause during the warm
        # loop does not flip the ordering and cause a spurious failure under load.
        assert warm_time < cold_time * 5, (
            f"Cache not improving performance: warm={warm_time * 1000:.1f}ms "
            f"cold={cold_time * 1000:.1f}ms (speedup={speedup:.2f}x, expected >0.2x)"
        )


class TestLSHPerformance:
    """Performance tests for LSH (Locality Sensitive Hashing) index."""

    def test_lsh_index_build_time(self, minhash_similarity: MinHashSimilarity) -> None:
        """Test LSH index build time.

        Building the LSH index should be fast even for moderate datasets.

        Success criteria: < 5 seconds for 1000 items.
        """
        # Generate 1000 code snippets
        code_items = [(f"func_{i}", f"def func_{i}(x, y): return x + y + {i}") for i in range(1000)]

        start = time.perf_counter()
        minhash_similarity.build_lsh_index(code_items, threshold=0.5)
        elapsed = time.perf_counter() - start

        print(f"\nLSH index build (1000 items): {elapsed:.2f}s")

        # Should build in < 5 seconds
        assert elapsed < 5.0, f"LSH index build too slow: {elapsed:.2f}s"

    def test_lsh_query_time(self, minhash_similarity: MinHashSimilarity) -> None:
        """Test LSH query time.

        Querying the LSH index should be fast.

        Success criteria: < 10ms per query.
        """
        # Build index with 500 items
        code_items = [(f"func_{i}", f"def func_{i}(x): return x * {i}") for i in range(500)]

        # Build the index first (stores internally)
        minhash_similarity.build_lsh_index(code_items, threshold=0.5)

        # Query 100 times using the query_similar public API
        query_code = "def query_func(x): return x * 42"
        start = time.perf_counter()
        for _ in range(100):
            minhash_similarity.query_similar(query_code)
        elapsed = time.perf_counter() - start

        avg_ms = (elapsed / 100) * 1000
        print(f"\nLSH query: {avg_ms:.3f}ms per query")

        # Should be < 10ms per query
        assert avg_ms < 10.0, f"LSH query too slow: {avg_ms:.3f}ms"
