"""
Tests for DuplicationRanker score caching functionality.

Tests the score caching optimization (Phase 2, Optimization 1.4) that provides
20-30% speedup for repeated analysis runs.
"""

from unittest.mock import patch

import pytest

from src.ast_grep_mcp.constants import RankerDefaults, SemanticSimilarityDefaults
from src.ast_grep_mcp.features.deduplication.ranker import DuplicationRanker


class TestScoreCaching:
    """Test score caching functionality in DuplicationRanker."""

    @pytest.fixture
    def ranker_with_cache(self):
        """Create ranker with caching enabled."""
        return DuplicationRanker(enable_cache=True)

    @pytest.fixture
    def ranker_without_cache(self):
        """Create ranker with caching disabled."""
        return DuplicationRanker(enable_cache=False)

    @pytest.fixture
    def sample_candidate(self):
        """Create a sample candidate for testing."""
        return {
            "similarity": SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            "files": ["/tmp/file1.py", "/tmp/file2.py"],
            "lines_saved": 50,
            "potential_line_savings": 100,
            "instances": [{"file": "/tmp/file1.py"}, {"file": "/tmp/file2.py"}],
            "complexity_analysis": {"cyclomatic": 5},
            "test_coverage": 80.0,  # Float percentage (0-100)
            "impact_analysis": {"call_sites": 10},
        }

    def test_cache_initialization(self, ranker_with_cache, ranker_without_cache):
        """Test that cache is initialized correctly."""
        assert ranker_with_cache.enable_cache is True
        assert ranker_with_cache._score_cache == {}

        assert ranker_without_cache.enable_cache is False
        assert ranker_without_cache._score_cache == {}

    def test_cache_key_generation_deterministic(self, ranker_with_cache, sample_candidate):
        """Test that cache key generation is deterministic."""
        key1 = ranker_with_cache._generate_cache_key(sample_candidate)
        key2 = ranker_with_cache._generate_cache_key(sample_candidate)

        assert key1 == key2
        assert isinstance(key1, str)
        assert key1.startswith("cache_")  # Exact tuple encoding (BUG-12)

    def test_cache_key_generation_different_for_different_candidates(self, ranker_with_cache, sample_candidate):
        """Test that different candidates produce different cache keys."""
        candidate2 = {**sample_candidate, "similarity": 0.90}

        key1 = ranker_with_cache._generate_cache_key(sample_candidate)
        key2 = ranker_with_cache._generate_cache_key(candidate2)

        assert key1 != key2

    def test_cache_key_generation_ignores_order_of_files(self, ranker_with_cache):
        """Test that file order doesn't affect cache key."""
        candidate1 = {
            "files": ["/tmp/a.py", "/tmp/b.py"],
            "similarity": SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            "lines_saved": 50,
        }
        candidate2 = {
            "files": ["/tmp/b.py", "/tmp/a.py"],  # Different order
            "similarity": SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            "lines_saved": 50,
        }

        key1 = ranker_with_cache._generate_cache_key(candidate1)
        key2 = ranker_with_cache._generate_cache_key(candidate2)

        assert key1 == key2  # Should be the same because files are sorted

    def test_ranking_with_cache_enabled(self, ranker_with_cache, sample_candidate):
        """Test that ranking works with caching enabled."""
        candidates = [sample_candidate]

        result = ranker_with_cache.rank_deduplication_candidates(candidates)

        assert len(result) == 1
        assert "score" in result[0]
        assert "rank" in result[0]
        assert result[0]["rank"] == 1

    def test_ranking_with_cache_disabled(self, ranker_without_cache, sample_candidate):
        """Test that ranking works with caching disabled."""
        candidates = [sample_candidate]

        result = ranker_without_cache.rank_deduplication_candidates(candidates)

        assert len(result) == 1
        assert "score" in result[0]
        assert "rank" in result[0]
        assert result[0]["rank"] == 1

    def test_cache_hit_on_identical_candidate(self, ranker_with_cache, sample_candidate):
        """Test that identical candidates hit the cache."""
        candidates = [sample_candidate, sample_candidate]  # Same candidate twice

        with patch.object(
            ranker_with_cache.score_calculator, "calculate_total_score", wraps=ranker_with_cache.score_calculator.calculate_total_score
        ) as mock_calc:
            result = ranker_with_cache.rank_deduplication_candidates(candidates)

            # Should only calculate score once (second is cache hit)
            assert mock_calc.call_count == 1

        assert len(result) == 2
        assert result[0]["score"] == result[1]["score"]

    def test_cache_miss_on_different_candidates(self, ranker_with_cache, sample_candidate):
        """Test that different candidates miss the cache."""
        # Change a field that affects scoring (lines_saved)
        candidate2 = {**sample_candidate, "lines_saved": 100, "potential_line_savings": 200}
        candidates = [sample_candidate, candidate2]

        with patch.object(
            ranker_with_cache.score_calculator, "calculate_total_score", wraps=ranker_with_cache.score_calculator.calculate_total_score
        ) as mock_calc:
            result = ranker_with_cache.rank_deduplication_candidates(candidates)

            # Should calculate score twice (both are cache misses)
            assert mock_calc.call_count == 2

        assert len(result) == 2
        assert result[0]["score"] != result[1]["score"]  # Different candidates = different scores

    def test_clear_cache(self, ranker_with_cache, sample_candidate):
        """Test that clear_cache empties the cache."""
        candidates = [sample_candidate]

        # First ranking - populates cache
        ranker_with_cache.rank_deduplication_candidates(candidates)
        assert len(ranker_with_cache._score_cache) == 1

        # Clear cache
        ranker_with_cache.clear_cache()
        assert len(ranker_with_cache._score_cache) == 0

    def test_get_cache_stats(self, ranker_with_cache, sample_candidate):
        """Test that get_cache_stats returns correct statistics."""
        # Initially empty
        stats = ranker_with_cache.get_cache_stats()
        assert stats["cache_size"] == 0
        assert stats["cache_enabled"] is True

        # After ranking
        candidates = [sample_candidate]
        ranker_with_cache.rank_deduplication_candidates(candidates)

        stats = ranker_with_cache.get_cache_stats()
        assert stats["cache_size"] == 1
        assert stats["cache_enabled"] is True

    def test_cache_preserves_score_components(self, ranker_with_cache, sample_candidate):
        """Test that cached scores preserve score components."""
        candidates = [sample_candidate, sample_candidate]

        result = ranker_with_cache.rank_deduplication_candidates(candidates, include_analysis=True)

        # Both should have identical score breakdowns
        assert result[0]["score_breakdown"] == result[1]["score_breakdown"]

    def test_repeated_ranking_uses_cache(self, ranker_with_cache, sample_candidate):
        """Test that repeated ranking of same candidates uses cache."""
        candidates = [sample_candidate]

        with patch.object(
            ranker_with_cache.score_calculator, "calculate_total_score", wraps=ranker_with_cache.score_calculator.calculate_total_score
        ) as mock_calc:
            # First ranking
            result1 = ranker_with_cache.rank_deduplication_candidates(candidates)
            first_call_count = mock_calc.call_count

            # Second ranking with same candidates
            result2 = ranker_with_cache.rank_deduplication_candidates(candidates)
            second_call_count = mock_calc.call_count

            # Second ranking should not call calculate (cache hit)
            assert second_call_count == first_call_count
            assert result1[0]["score"] == result2[0]["score"]

    def test_cache_respects_max_results(self, ranker_with_cache, sample_candidate):
        """Test that caching works with max_results parameter."""
        candidate2 = {**sample_candidate, "similarity": 0.90, "lines_saved": 100}
        candidates = [sample_candidate, candidate2]

        result = ranker_with_cache.rank_deduplication_candidates(candidates, max_results=1)

        assert len(result) == 1
        assert len(ranker_with_cache._score_cache) == 2  # Both candidates scored before slicing

    def test_no_cache_when_disabled(self, ranker_without_cache, sample_candidate):
        """Test that no caching occurs when disabled."""
        candidates = [sample_candidate, sample_candidate]

        with patch.object(
            ranker_without_cache.score_calculator,
            "calculate_total_score",
            wraps=ranker_without_cache.score_calculator.calculate_total_score,
        ) as mock_calc:
            ranker_without_cache.rank_deduplication_candidates(candidates)

            # Should calculate score twice even for identical candidates
            assert mock_calc.call_count == 2

        assert len(ranker_without_cache._score_cache) == 0  # Cache not populated

    def test_cache_key_handles_none_values(self, ranker_with_cache):
        """Test that cache key generation handles None values gracefully."""
        candidate = {
            "similarity": SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            "files": ["/tmp/file1.py"],
            "complexity_analysis": None,
            "test_coverage": None,
            "impact_analysis": None,
        }

        key = ranker_with_cache._generate_cache_key(candidate)
        assert isinstance(key, str)
        assert key.startswith("cache_")  # Exact tuple encoding (BUG-12)

    def test_cache_key_is_exact_not_hash_based(self, ranker_with_cache, sample_candidate):
        """Cache key embeds exact field values, not a collision-prone hash() (BUG-12)."""
        key = ranker_with_cache._generate_cache_key(sample_candidate)

        assert "/tmp/file1.py" in key
        assert "/tmp/file2.py" in key
        assert str(sample_candidate["lines_saved"]) in key

    def test_score_cache_lru_eviction(self, ranker_with_cache, sample_candidate, monkeypatch):
        """Score cache should evict the least-recently-used entry at the bound."""
        monkeypatch.setattr(RankerDefaults, "SCORE_CACHE_MAX_SIZE", 2)
        candidates = [{**sample_candidate, "lines_saved": i} for i in range(3)]

        for candidate in candidates:
            ranker_with_cache._score_candidate(candidate)

        assert len(ranker_with_cache._score_cache) == 2
        evicted_key = ranker_with_cache._generate_cache_key(candidates[0])
        assert evicted_key not in ranker_with_cache._score_cache


class TestCachePerformance:
    """Test cache performance characteristics."""

    @pytest.fixture
    def ranker(self):
        """Create ranker with caching enabled."""
        return DuplicationRanker(enable_cache=True)

    def test_large_cache_performance(self, ranker):
        """Test that cache works efficiently with many candidates."""
        # Create 100 unique candidates
        candidates = []
        for i in range(100):
            candidates.append(
                {
                    "similarity": 0.80 + (i * 0.001),  # Unique similarity for each
                    "files": [f"/tmp/file{i}.py"],
                    "lines_saved": 50 + i,
                    "instances": [{"file": f"/tmp/file{i}.py"}],
                }
            )

        # Rank all candidates
        result = ranker.rank_deduplication_candidates(candidates)

        # Cache should have 100 entries
        stats = ranker.get_cache_stats()
        assert stats["cache_size"] == 100
        assert len(result) == 100

    def test_cache_hit_rate_with_duplicates(self, ranker):
        """Test cache hit rate when many candidates are duplicates."""
        # Create 10 unique candidates, but repeat each 10 times (100 total)
        candidates = []
        for i in range(10):
            base_candidate = {
                "similarity": 0.80 + (i * 0.01),
                "files": [f"/tmp/file{i}.py"],
                "lines_saved": 50 + i * 5,
                "instances": [{"file": f"/tmp/file{i}.py"}],
            }
            # Add same candidate 10 times
            candidates.extend([base_candidate] * 10)

        with patch.object(
            ranker.score_calculator, "calculate_total_score", wraps=ranker.score_calculator.calculate_total_score
        ) as mock_calc:
            result = ranker.rank_deduplication_candidates(candidates)

            # Should only calculate 10 unique scores (90% cache hit rate)
            assert mock_calc.call_count == 10

        # Cache should have only 10 entries
        stats = ranker.get_cache_stats()
        assert stats["cache_size"] == 10
        assert len(result) == 100


class TestCacheEdgeCases:
    """Test edge cases for score caching."""

    @pytest.fixture
    def ranker(self):
        """Create ranker with caching enabled."""
        return DuplicationRanker(enable_cache=True)

    def test_empty_candidates_list(self, ranker):
        """Test ranking with empty candidates list."""
        result = ranker.rank_deduplication_candidates([])

        assert result == []
        assert ranker.get_cache_stats()["cache_size"] == 0

    def test_candidate_with_empty_files_list(self, ranker):
        """Test candidate with empty files list."""
        candidate = {
            "similarity": SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            "files": [],  # Empty
            "lines_saved": 50,
        }

        result = ranker.rank_deduplication_candidates([candidate])

        assert len(result) == 1
        assert "score" in result[0]

    def test_candidate_with_missing_optional_fields(self, ranker):
        """Test candidate with minimal required fields."""
        candidate = {
            "similarity": SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            "files": ["/tmp/file.py"],
            # Missing: lines_saved, complexity, test_coverage, etc.
        }

        result = ranker.rank_deduplication_candidates([candidate])

        assert len(result) == 1
        assert "score" in result[0]
        assert ranker.get_cache_stats()["cache_size"] == 1
