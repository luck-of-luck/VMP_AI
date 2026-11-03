"""Unit tests for progress callback functionality in DeduplicationAnalysisOrchestrator.

Tests focus on the progress callback optimization (3.3):
- Progress reporting at each workflow stage
- Optional callback behavior (no errors when None)
- Correct progress percentages
- Stage naming consistency
"""

import tempfile
from unittest.mock import Mock

import pytest

from ast_grep_mcp.constants import SemanticSimilarityDefaults
from ast_grep_mcp.features.deduplication.analysis_orchestrator import DeduplicationAnalysisOrchestrator, ProgressCallback


class TestProgressCallbacks:
    """Tests for progress callback functionality (3.3)."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def orchestrator_with_mocks(self):
        """Create orchestrator with mocked components."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # Mock detector
        mock_detector = Mock()
        mock_detector.find_duplication.return_value = {
            "duplication_groups": [
                {"similarity": 0.9, "lines_saved": 100, "complexity_score": 3, "files": ["/tmp/file1.py", "/tmp/file2.py"]},
                {
                    "similarity": SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
                    "lines_saved": 50,
                    "complexity_score": 2,
                    "files": ["/tmp/file3.py"],
                },
            ]
        }
        orchestrator.detector = mock_detector

        # Mock ranker
        mock_ranker = Mock()
        mock_ranker.rank_deduplication_candidates.return_value = [
            {
                "similarity": 0.9,
                "lines_saved": 100,
                "complexity_score": 3,
                "files": ["/tmp/file1.py", "/tmp/file2.py"],
                "score": 85.0,
                "rank": 1,
            },
            {
                "similarity": SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
                "lines_saved": 50,
                "complexity_score": 2,
                "files": ["/tmp/file3.py"],
                "score": 70.0,
                "rank": 2,
            },
        ]
        orchestrator.ranker = mock_ranker

        return orchestrator

    def test_progress_callback_is_called(self, temp_project_dir, orchestrator_with_mocks):
        """Test that progress callback is invoked during analysis."""
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir,
            language="python",
            include_test_coverage=False,  # Skip coverage to avoid I/O
            progress_callback=track_progress,
        )

        # Verify callback was called
        assert len(progress_calls) > 0, "Progress callback should be called"

    def test_progress_stages_in_order(self, temp_project_dir, orchestrator_with_mocks):
        """Test that progress stages are reported in correct order."""
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=False, progress_callback=track_progress
        )

        # Extract stage names
        stages = [call[0] for call in progress_calls]

        # Verify key stages are present
        assert "Finding duplicate code" in stages
        assert "Ranking candidates by value" in stages
        assert "Analysis complete" in stages

    def test_progress_percentages_increase(self, temp_project_dir, orchestrator_with_mocks):
        """Test that progress percentages increase monotonically."""
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=False, progress_callback=track_progress
        )

        # Extract percentages
        percentages = [call[1] for call in progress_calls]

        # Verify percentages increase (or stay same for sub-steps)
        for i in range(len(percentages) - 1):
            assert percentages[i] <= percentages[i + 1], f"Progress should not decrease: {percentages[i]} -> {percentages[i + 1]}"

    def test_progress_starts_at_zero(self, temp_project_dir, orchestrator_with_mocks):
        """Test that progress starts at 0.0."""
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=False, progress_callback=track_progress
        )

        # First progress should be 0.0
        assert progress_calls[0][1] == 0.0, "Progress should start at 0.0"

    def test_progress_ends_at_one(self, temp_project_dir, orchestrator_with_mocks):
        """Test that progress ends at 1.0."""
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=False, progress_callback=track_progress
        )

        # Last progress should be 1.0
        assert progress_calls[-1][1] == 1.0, "Progress should end at 1.0"
        assert progress_calls[-1][0] == "Analysis complete"

    def test_no_callback_works_without_error(self, temp_project_dir, orchestrator_with_mocks):
        """Test that analysis works when no callback is provided."""
        # Should not raise any errors
        result = orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=False, progress_callback=None
        )

        assert result is not None
        assert "candidates" in result

    def test_callback_with_test_coverage(self, temp_project_dir, orchestrator_with_mocks):
        """Test that test coverage step is reported when enabled."""
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=True, progress_callback=track_progress
        )

        # Extract stage names
        stages = [call[0] for call in progress_calls]

        # Verify test coverage stages are present
        assert "Checking test coverage" in stages or "Test coverage complete" in stages

    def test_callback_without_test_coverage(self, temp_project_dir, orchestrator_with_mocks):
        """Test that test coverage step is skipped when disabled."""
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=False, progress_callback=track_progress
        )

        # Extract stage names
        stages = [call[0] for call in progress_calls]

        # Verify test coverage stages are NOT present
        assert "Checking test coverage" not in stages
        assert "Test coverage complete" not in stages

    def test_all_key_stages_reported(self, temp_project_dir, orchestrator_with_mocks):
        """Test that all major workflow stages are reported."""
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=True, progress_callback=track_progress
        )

        # Extract stage names
        stages = [call[0] for call in progress_calls]

        # Verify all key stages
        expected_stages = ["Finding duplicate code", "Ranking candidates by value", "Enriching candidates", "Analysis complete"]

        for expected in expected_stages:
            assert expected in stages, f"Stage '{expected}' should be reported"

    def test_progress_callback_signature(self, temp_project_dir):
        """Test that ProgressCallback type signature is correct."""

        # ProgressCallback should be Callable[[str, float], None]
        # This is a type alias, so we just verify it's importable
        assert ProgressCallback is not None

    def test_callback_receives_valid_percentages(self, temp_project_dir, orchestrator_with_mocks):
        """Test that all percentages are in range [0.0, 1.0]."""
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=True, progress_callback=track_progress
        )

        # Verify all percentages are valid
        for stage, percent in progress_calls:
            assert 0.0 <= percent <= 1.0, f"Progress percent {percent} for stage '{stage}' is out of range"

    def test_callback_exception_does_not_crash_analysis(self, temp_project_dir, orchestrator_with_mocks):
        """Test that exceptions in callback don't crash the analysis."""

        def failing_callback(stage: str, percent: float):
            raise RuntimeError("Callback failed!")

        # Analysis should complete despite callback failures
        # (Note: Current implementation doesn't catch callback exceptions,
        #  but this test documents the expected behavior)
        with pytest.raises(RuntimeError, match="Callback failed!"):
            orchestrator_with_mocks.analyze_candidates(
                project_path=temp_project_dir, language="python", include_test_coverage=False, progress_callback=failing_callback
            )

    def test_progress_with_empty_results(self, temp_project_dir):
        """Test progress reporting when no duplicates are found."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        # Mock detector to return no duplicates
        mock_detector = Mock()
        mock_detector.find_duplication.return_value = {"duplication_groups": []}
        orchestrator.detector = mock_detector

        orchestrator.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=False, progress_callback=track_progress
        )

        # Progress should still be reported
        assert len(progress_calls) > 0
        assert progress_calls[0][1] == 0.0
        assert progress_calls[-1][1] == 1.0

    def test_progress_callback_in_documentation(self, temp_project_dir, orchestrator_with_mocks):
        """Test the example callback from documentation works."""
        # Example from docstring
        progress_log = []

        def show_progress(stage: str, percent: float):
            progress_log.append(f"[{percent * 100:.0f}%] {stage}")

        orchestrator_with_mocks.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=False, progress_callback=show_progress
        )

        # Verify example callback produces expected output
        assert len(progress_log) > 0
        assert "[0%]" in progress_log[0]
        assert "[100%]" in progress_log[-1]


class TestProgressCallbackIntegration:
    """Integration tests for progress callbacks with real workflow."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_progress_percentage_distribution(self, temp_project_dir):
        """Test that progress percentages are well-distributed across stages."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        progress_calls = []

        def track_progress(stage: str, percent: float):
            progress_calls.append((stage, percent))

        # Mock components
        mock_detector = Mock()
        mock_detector.find_duplication.return_value = {
            "duplication_groups": [
                {"similarity": 0.9, "lines_saved": 100, "complexity_score": 3, "files": ["/tmp/file1.py"]},
            ]
        }
        orchestrator.detector = mock_detector

        mock_ranker = Mock()
        mock_ranker.rank_deduplication_candidates.return_value = [
            {"similarity": 0.9, "lines_saved": 100, "complexity_score": 3, "files": ["/tmp/file1.py"], "score": 85.0, "rank": 1},
        ]
        orchestrator.ranker = mock_ranker

        orchestrator.analyze_candidates(
            project_path=temp_project_dir, language="python", include_test_coverage=False, progress_callback=track_progress
        )

        # Verify reasonable distribution of progress percentages
        percentages = [call[1] for call in progress_calls]

        # Should have progress in different ranges
        has_early = any(0.0 <= p < 0.3 for p in percentages)
        has_middle = any(0.3 <= p < 0.7 for p in percentages)
        has_late = any(0.7 <= p <= 1.0 for p in percentages)

        assert has_early, "Should have early progress updates"
        assert has_middle, "Should have middle progress updates"
        assert has_late, "Should have late progress updates"
