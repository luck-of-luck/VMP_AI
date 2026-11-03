"""Tests for extracted reporting helper methods."""

from ast_grep_mcp.features.deduplication.reporting import DuplicationReporter


class TestUpdateDistribution:
    def test_low_complexity(self):
        dist = {"low": 0, "medium": 0, "high": 0}
        DuplicationReporter._update_distribution(dist, 2)
        assert dist == {"low": 1, "medium": 0, "high": 0}

    def test_medium_complexity(self):
        dist = {"low": 0, "medium": 0, "high": 0}
        DuplicationReporter._update_distribution(dist, 5)
        assert dist == {"low": 0, "medium": 1, "high": 0}

    def test_high_complexity(self):
        dist = {"low": 0, "medium": 0, "high": 0}
        DuplicationReporter._update_distribution(dist, 9)
        assert dist == {"low": 0, "medium": 0, "high": 1}


class TestBuildGlobalRecommendations:
    def test_no_recommendations_for_clean_results(self):
        recs = DuplicationReporter._build_global_recommendations(
            {"low": 2, "medium": 0, "high": 0}, total_lines_saveable=5, candidate_count=2
        )
        assert len(recs) == 0

    def test_high_complexity_recommendation(self):
        recs = DuplicationReporter._build_global_recommendations(
            {"low": 0, "medium": 0, "high": 3}, total_lines_saveable=5, candidate_count=2
        )
        assert any("high-complexity" in r for r in recs)

    def test_many_lines_saveable_recommendation(self):
        recs = DuplicationReporter._build_global_recommendations(
            {"low": 2, "medium": 0, "high": 0}, total_lines_saveable=500, candidate_count=2
        )
        assert any("save" in r.lower() for r in recs)

    def test_many_candidates_recommendation(self):
        recs = DuplicationReporter._build_global_recommendations(
            {"low": 2, "medium": 0, "high": 0}, total_lines_saveable=5, candidate_count=100
        )
        assert any("many duplicates" in r.lower() for r in recs)


class TestBuildSummary:
    def test_summary_structure(self):
        raw = [{"files": ["a.py", "b.py"]}, {"files": ["b.py", "c.py"]}]
        enhanced = [{"id": "DUP-001"}, {"id": "DUP-002"}]
        dist = {"low": 1, "medium": 1, "high": 0}
        summary = DuplicationReporter._build_summary(raw, enhanced, total_lines_saveable=20, distribution=dist)
        assert summary["total_candidates"] == 2
        assert summary["total_files_affected"] == 3  # a.py, b.py, c.py
        assert summary["total_lines_saveable"] == 20
        assert summary["complexity_distribution"] == dist
        assert summary["highest_priority_id"] == "DUP-001"

    def test_summary_empty_candidates(self):
        summary = DuplicationReporter._build_summary([], [], 0, {"low": 0, "medium": 0, "high": 0})
        assert summary["total_candidates"] == 0
        assert summary["highest_priority_id"] is None


class TestBuildEnhancedCandidate:
    def test_candidate_has_expected_keys(self):
        reporter = DuplicationReporter()
        candidate = {
            "code": "x = 1\ny = 2",
            "replacement": "def f():\n    x = 1\n    y = 2",
            "function_name": "f",
            "files": ["a.py", "b.py"],
            "locations": [],
            "similarity": 95.0,
            "complexity": 3,
        }
        result = reporter._build_enhanced_candidate(candidate, idx=0, include_diffs=False, include_colors=False)
        assert result["id"] == "DUP-001"
        assert result["suggested_function_name"] == "f"
        assert "before_after" in result
        assert "complexity_viz" in result
        assert "priority" in result
        assert result["diff_preview"] is None  # diffs disabled

    def test_candidate_fallback_function_name(self):
        reporter = DuplicationReporter()
        candidate = {"code": "x = 1", "replacement": "x = 1", "files": [], "locations": []}
        result = reporter._build_enhanced_candidate(candidate, idx=5, include_diffs=False, include_colors=False)
        assert result["suggested_function_name"] == "extracted_function_5"
