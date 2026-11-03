"""Unit tests for DuplicationRanker class.

Tests focus on:
- Basic ranking functionality
- Early exit optimization (max_results parameter)
- Score calculation
- Priority classification
"""

import threading
import time

import pytest

from ast_grep_mcp.features.deduplication.ranker import DuplicationRanker


class TestDuplicationRanker:
    """Tests for DuplicationRanker class."""

    @pytest.fixture
    def ranker(self):
        """Provide DuplicationRanker instance."""
        return DuplicationRanker()

    @pytest.fixture
    def sample_candidates(self):
        """Provide sample candidates for testing."""
        return [
            {"lines_saved": 100, "complexity_score": 5, "has_tests": True, "affected_files": 3, "external_call_sites": 10},
            {"lines_saved": 50, "complexity_score": 8, "has_tests": False, "affected_files": 2, "external_call_sites": 5},
            {"lines_saved": 80, "complexity_score": 3, "has_tests": True, "affected_files": 4, "external_call_sites": 8},
            {"lines_saved": 30, "complexity_score": 10, "has_tests": False, "affected_files": 1, "external_call_sites": 2},
            {"lines_saved": 60, "complexity_score": 6, "has_tests": True, "affected_files": 2, "external_call_sites": 6},
        ]

    def test_rank_all_candidates(self, ranker, sample_candidates):
        """Test ranking all candidates without max_results."""
        ranked = ranker.rank_deduplication_candidates(sample_candidates)

        # Should return all 5 candidates
        assert len(ranked) == 5

        # Should have scores
        for candidate in ranked:
            assert "score" in candidate
            assert "priority" in candidate
            assert "rank" in candidate

        # Should be sorted by score (highest first)
        scores = [c["score"] for c in ranked]
        assert scores == sorted(scores, reverse=True)

        # Ranks should be sequential starting from 1
        ranks = [c["rank"] for c in ranked]
        assert ranks == [1, 2, 3, 4, 5]

    def test_rank_with_max_results(self, ranker, sample_candidates):
        """Test early exit optimization with max_results parameter."""
        max_results = 3
        ranked = ranker.rank_deduplication_candidates(sample_candidates, max_results=max_results)

        # Should return only 3 candidates (early exit)
        assert len(ranked) == max_results

        # Should have scores and ranks
        for candidate in ranked:
            assert "score" in candidate
            assert "priority" in candidate
            assert "rank" in candidate

        # Ranks should be sequential starting from 1
        ranks = [c["rank"] for c in ranked]
        assert ranks == [1, 2, 3]

        # Should be sorted by score (highest first)
        scores = [c["score"] for c in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_max_results_greater_than_candidates(self, ranker, sample_candidates):
        """Test max_results when it exceeds number of candidates."""
        max_results = 10
        ranked = ranker.rank_deduplication_candidates(sample_candidates, max_results=max_results)

        # Should return all 5 candidates (not 10)
        assert len(ranked) == 5

        # Ranks should be sequential
        ranks = [c["rank"] for c in ranked]
        assert ranks == [1, 2, 3, 4, 5]

    def test_max_results_zero(self, ranker, sample_candidates):
        """Test max_results=0 returns all candidates."""
        ranked = ranker.rank_deduplication_candidates(sample_candidates, max_results=0)

        # max_results=0 is treated as None (return all)
        assert len(ranked) == 5

    def test_max_results_one(self, ranker, sample_candidates):
        """Test max_results=1 returns only top candidate."""
        ranked = ranker.rank_deduplication_candidates(sample_candidates, max_results=1)

        # Should return only 1 candidate
        assert len(ranked) == 1
        assert ranked[0]["rank"] == 1

        # Should be the highest scored candidate
        all_ranked = ranker.rank_deduplication_candidates(sample_candidates)
        assert ranked[0]["score"] == all_ranked[0]["score"]

    def test_empty_candidates(self, ranker):
        """Test ranking with empty candidate list."""
        ranked = ranker.rank_deduplication_candidates([])

        # Should return empty list
        assert len(ranked) == 0

    def test_empty_candidates_with_max_results(self, ranker):
        """Test ranking with empty candidate list and max_results."""
        ranked = ranker.rank_deduplication_candidates([], max_results=3)

        # Should return empty list
        assert len(ranked) == 0

    def test_include_analysis_true(self, ranker, sample_candidates):
        """Test with include_analysis=True adds score_breakdown."""
        ranked = ranker.rank_deduplication_candidates(sample_candidates, include_analysis=True, max_results=2)

        # Should include score_breakdown
        for candidate in ranked:
            assert "score_breakdown" in candidate

    def test_include_analysis_false(self, ranker, sample_candidates):
        """Test with include_analysis=False excludes score_breakdown."""
        ranked = ranker.rank_deduplication_candidates(sample_candidates, include_analysis=False, max_results=2)

        # Should not include score_breakdown
        for candidate in ranked:
            assert "score_breakdown" not in candidate

    def test_max_results_negative(self, ranker, sample_candidates):
        """Test max_results with negative value returns all candidates."""
        ranked = ranker.rank_deduplication_candidates(sample_candidates, max_results=-1)

        # Negative value should return all candidates (not trigger early exit)
        assert len(ranked) == 5


class TestEarlyExitPerformance:
    """Tests to verify early exit optimization actually improves performance."""

    def test_early_exit_processes_fewer_rank_assignments(self):
        """Verify that early exit avoids unnecessary rank assignments."""
        ranker = DuplicationRanker()

        # Create 100 candidates
        candidates = [
            {
                "lines_saved": i * 10,
                "complexity_score": (i % 10) + 1,
                "has_tests": i % 2 == 0,
                "affected_files": (i % 5) + 1,
                "external_call_sites": i * 2,
            }
            for i in range(100)
        ]

        # Rank with max_results=10
        ranked = ranker.rank_deduplication_candidates(candidates, max_results=10)

        # Should return exactly 10 candidates
        assert len(ranked) == 10

        # All 10 should have sequential ranks
        ranks = [c["rank"] for c in ranked]
        assert ranks == list(range(1, 11))

        # Verify they are the top 10 by comparing to full ranking
        all_ranked = ranker.rank_deduplication_candidates(candidates)
        top_10_scores = [c["score"] for c in all_ranked[:10]]
        returned_scores = [c["score"] for c in ranked]
        assert returned_scores == top_10_scores


class TestParallelScoring:
    """Tests for parallel scoring with ThreadPoolExecutor."""

    def test_parallel_scoring_produces_same_results(self):
        """Verify parallel scoring produces identical results to sequential."""
        ranker_seq = DuplicationRanker(max_workers=0)  # Disable parallelization
        ranker_par = DuplicationRanker(max_workers=4)   # Enable parallelization

        candidates = [
            {
                "lines_saved": i * 10,
                "complexity_score": (i % 10) + 1,
                "has_tests": i % 2 == 0,
                "affected_files": (i % 5) + 1,
                "external_call_sites": i * 2,
            }
            for i in range(20)
        ]

        ranked_seq = ranker_seq.rank_deduplication_candidates(candidates)
        ranked_par = ranker_par.rank_deduplication_candidates(candidates)

        # Should have same number of results
        assert len(ranked_seq) == len(ranked_par)

        # Scores should be identical (allowing for float precision)
        for seq, par in zip(ranked_seq, ranked_par):
            assert abs(seq["score"] - par["score"]) < 1e-9
            assert seq["rank"] == par["rank"]
            assert seq["priority"] == par["priority"]

    def test_parallel_scoring_with_small_candidate_list(self):
        """Verify parallel scoring falls back to sequential for small lists."""
        ranker = DuplicationRanker(max_workers=4)

        candidates = [
            {"lines_saved": 100, "complexity_score": 5, "has_tests": True, "affected_files": 3, "external_call_sites": 10},
        ]

        # Should not crash with single candidate
        ranked = ranker.rank_deduplication_candidates(candidates)
        assert len(ranked) == 1
        assert "score" in ranked[0]

    def test_parallel_scoring_disabled_with_max_workers_zero(self):
        """Verify max_workers=0 disables parallelization."""
        ranker = DuplicationRanker(max_workers=0)

        candidates = [
            {
                "lines_saved": i * 10,
                "complexity_score": (i % 10) + 1,
                "has_tests": i % 2 == 0,
                "affected_files": (i % 5) + 1,
                "external_call_sites": i * 2,
            }
            for i in range(20)
        ]

        ranked = ranker.rank_deduplication_candidates(candidates)
        assert len(ranked) == 20
        # Verify scoring still works correctly
        assert all("score" in c for c in ranked)

    def test_parallel_scoring_with_cache(self):
        """Verify parallel scoring with cache enabled produces correct results."""
        ranker = DuplicationRanker(enable_cache=True, max_workers=4)

        candidates = [
            {
                "lines_saved": 100,
                "complexity_score": 5,
                "has_tests": True,
                "affected_files": 3,
                "external_call_sites": 10,
            }
        ] * 5  # Duplicate candidates to test cache hits

        # First call should have cache misses
        ranked1 = ranker.rank_deduplication_candidates(candidates)
        assert len(ranked1) == 5

        # All should have same score since they're identical
        scores = [c["score"] for c in ranked1]
        assert len(set(scores)) == 1  # All scores are the same

        # Second call should hit cache
        ranked2 = ranker.rank_deduplication_candidates(candidates)
        assert len(ranked2) == 5

        # Scores should still be identical
        for r1, r2 in zip(ranked1, ranked2):
            assert abs(r1["score"] - r2["score"]) < 1e-9

    def test_parallel_scoring_assigns_score_to_correct_candidate(self):
        """Regression test for BUG-03: parallel scoring must not shuffle scores between candidates.

        Creates candidates with distinct, widely-separated savings values so each
        candidate has a unique expected score.  Verifies that the parallel-ranked
        result for each original candidate matches the score computed sequentially
        from that same candidate's own data — not a neighbour's score.
        """
        ranker_seq = DuplicationRanker(max_workers=0)
        ranker_par = DuplicationRanker(max_workers=4)

        # 10 candidates with non-overlapping scores (potential_line_savings drives 40% weight)
        candidates = [
            {
                "potential_line_savings": (i + 1) * 50,
                "complexity_score": 3,
                "has_tests": False,
                "affected_files": 1,
                "external_call_sites": 0,
            }
            for i in range(10)
        ]

        ranked_seq = ranker_seq.rank_deduplication_candidates(candidates)
        ranked_par = ranker_par.rank_deduplication_candidates(candidates)

        # Build a map from potential_line_savings → sequential score
        seq_score_by_savings = {c["potential_line_savings"]: c["score"] for c in ranked_seq}

        # Every parallel result must carry the score that matches its own savings value
        for c in ranked_par:
            savings = c["potential_line_savings"]
            assert abs(c["score"] - seq_score_by_savings[savings]) < 1e-9, (
                f"Candidate with savings={savings} got score={c['score']!r}, "
                f"expected {seq_score_by_savings[savings]!r} — score was likely misassigned"
            )


class TestParallelScoringTimeout:
    """Regression tests for BUG-06-CR-10: ranker parallel scoring must use
    map_with_per_item_timeout so a hung scorer cannot block indefinitely.

    Before the fix, _score_candidates_parallel used ThreadPoolExecutor +
    as_completed() without a timeout — the executor's implicit shutdown(wait=True)
    would block until every worker finished, including permanently hung ones.
    """

    TIMEOUT_SECONDS = 0.2
    HUNG_WORKER_SAFETY_NET_SECONDS = 30
    ELAPSED_BOUND_SECONDS = 10

    def test_hung_scorer_does_not_block_rank_call(self):
        """A scorer that blocks forever is abandoned; ranking returns promptly.

        Monkeypatches map_with_per_item_timeout to use a 0.2s timeout so the
        test completes quickly without relying on the 30s production default.
        """
        from ast_grep_mcp.features.deduplication import ranker as ranker_mod
        from ast_grep_mcp.utils.futures import map_with_per_item_timeout

        ranker = DuplicationRanker(max_workers=2)
        release = threading.Event()
        real_score = ranker._score_candidate

        def patched_score(candidate):
            if candidate.get("id") == "hung":
                release.wait(timeout=self.HUNG_WORKER_SAFETY_NET_SECONDS)
            return real_score(candidate)

        ranker._score_candidate = patched_score

        original_map = ranker_mod.map_with_per_item_timeout

        def fast_map(items, func, *, timeout_seconds, max_workers, on_success, on_error, **kw):
            return map_with_per_item_timeout(
                items, func,
                timeout_seconds=self.TIMEOUT_SECONDS,
                max_workers=max_workers,
                on_success=on_success,
                on_error=on_error,
                **kw,
            )

        ranker_mod.map_with_per_item_timeout = fast_map
        candidates = [{"id": "hung"}, {"id": "fast", "potential_line_savings": 50}]
        try:
            start = time.monotonic()
            ranked = ranker.rank_deduplication_candidates(candidates)
            elapsed = time.monotonic() - start
        finally:
            release.set()
            ranker_mod.map_with_per_item_timeout = original_map

        assert elapsed < self.ELAPSED_BOUND_SECONDS, f"ranking should return promptly, took {elapsed:.1f}s"
        assert len(ranked) == 2
        hung_ranked = next(r for r in ranked if r.get("id") == "hung")
        fast_ranked = next(r for r in ranked if r.get("id") == "fast")
        assert hung_ranked["score"] == 0.0, "hung candidate should get fallback score"
        assert fast_ranked["score"] > 0.0, "fast candidate should score normally"
