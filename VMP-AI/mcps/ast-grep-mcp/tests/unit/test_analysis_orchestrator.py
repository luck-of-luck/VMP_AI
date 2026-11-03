"""Tests for DeduplicationAnalysisOrchestrator.

Tests cover:
- Lazy initialization of components
- Input validation
- Analysis workflow (legacy and config-based APIs)
- Progress callbacks
- Parallel vs sequential processing
- Error handling
- Edge cases
"""

import tempfile
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from ast_grep_mcp.constants import SemanticSimilarityDefaults
from ast_grep_mcp.features.deduplication.analysis_orchestrator import (
    DeduplicationAnalysisOrchestrator,
)
from ast_grep_mcp.features.deduplication.config import AnalysisConfig


@pytest.fixture
def orchestrator():
    """Provide a fresh DeduplicationAnalysisOrchestrator instance."""
    return DeduplicationAnalysisOrchestrator()


class TestOrchestratorInitialization:
    """Tests for orchestrator initialization and lazy loading."""

    def test_init_creates_logger(self, orchestrator):
        """Test that initialization creates a logger."""
        assert orchestrator.logger is not None

    def test_lazy_detector_initialization(self, orchestrator):
        """Test that detector is lazily initialized."""
        assert not hasattr(orchestrator, "_detector")
        _ = orchestrator.detector
        assert hasattr(orchestrator, "_detector")

    def test_lazy_ranker_initialization(self, orchestrator):
        """Test that ranker is lazily initialized."""
        assert not hasattr(orchestrator, "_ranker")
        _ = orchestrator.ranker
        assert hasattr(orchestrator, "_ranker")

    def test_lazy_coverage_detector_initialization(self, orchestrator):
        """Test that coverage detector is lazily initialized."""
        assert not hasattr(orchestrator, "_coverage_detector")
        _ = orchestrator.coverage_detector
        assert hasattr(orchestrator, "_coverage_detector")

    def test_lazy_recommendation_engine_initialization(self, orchestrator):
        """Test that recommendation engine is lazily initialized."""
        assert not hasattr(orchestrator, "_recommendation_engine")
        _ = orchestrator.recommendation_engine
        assert hasattr(orchestrator, "_recommendation_engine")

    def test_component_setter_injection(self, orchestrator):
        """Test that components can be injected via setters."""
        mock_detector = MagicMock()
        mock_ranker = MagicMock()
        mock_coverage = MagicMock()
        mock_recommendation = MagicMock()

        orchestrator.detector = mock_detector
        orchestrator.ranker = mock_ranker
        orchestrator.coverage_detector = mock_coverage
        orchestrator.recommendation_engine = mock_recommendation

        assert orchestrator.detector is mock_detector
        assert orchestrator.ranker is mock_ranker
        assert orchestrator.coverage_detector is mock_coverage
        assert orchestrator.recommendation_engine is mock_recommendation


class TestInputValidation:
    """Tests for input validation in analyze_candidates."""

    def test_validate_nonexistent_project_path(self, orchestrator):
        """Test validation fails for nonexistent project path."""
        with pytest.raises(ValueError, match="does not exist"):
            orchestrator._validate_analysis_inputs("/nonexistent/path", "python", 0.8, 5, 100)

    def test_validate_file_instead_of_directory(self, orchestrator):
        """Test validation fails when project path is a file."""
        with tempfile.NamedTemporaryFile() as f:
            with pytest.raises(ValueError, match="not a directory"):
                orchestrator._validate_analysis_inputs(f.name, "python", 0.8, 5, 100)

    def test_validate_min_similarity_below_zero(self, orchestrator, temp_dir):
        """Test validation fails for min_similarity below 0."""
        with pytest.raises(ValueError, match="min_similarity must be between"):
            orchestrator._validate_analysis_inputs(temp_dir, "python", -0.1, 5, 100)

    def test_validate_min_similarity_above_one(self, orchestrator, temp_dir):
        """Test validation fails for min_similarity above 1."""
        with pytest.raises(ValueError, match="min_similarity must be between"):
            orchestrator._validate_analysis_inputs(temp_dir, "python", 1.5, 5, 100)

    def test_validate_min_lines_zero(self, orchestrator, temp_dir):
        """Test validation fails for min_lines of zero."""
        with pytest.raises(ValueError, match="min_lines must be a positive"):
            orchestrator._validate_analysis_inputs(temp_dir, "python", 0.8, 0, 100)

    def test_validate_max_candidates_zero(self, orchestrator, temp_dir):
        """Test validation fails for max_candidates of zero."""
        with pytest.raises(ValueError, match="max_candidates must be a positive"):
            orchestrator._validate_analysis_inputs(temp_dir, "python", 0.8, 5, 0)

    def test_validate_valid_inputs(self, orchestrator, temp_dir):
        """Test validation passes for valid inputs."""
        orchestrator._validate_analysis_inputs(temp_dir, "python", 0.8, 5, 100)

    def test_validate_boundary_min_similarity_zero(self, orchestrator, temp_dir):
        """Test validation passes for min_similarity of 0."""
        orchestrator._validate_analysis_inputs(temp_dir, "python", 0.0, 5, 100)

    def test_validate_boundary_min_similarity_one(self, orchestrator, temp_dir):
        """Test validation passes for min_similarity of 1."""
        orchestrator._validate_analysis_inputs(temp_dir, "python", 1.0, 5, 100)


class TestAnalysisWorkflow:
    """Tests for the analysis workflow."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create an orchestrator with mocked components."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # Mock detector
        mock_detector = MagicMock()
        mock_detector.find_duplication.return_value = {
            "duplication_groups": [
                {
                    "id": "group1",
                    "files": ["/path/file1.py", "/path/file2.py"],
                    "similarity": 0.95,
                    "lines_saved": 20,
                }
            ]
        }
        orchestrator.detector = mock_detector

        # Mock ranker
        mock_ranker = MagicMock()
        mock_ranker.rank_deduplication_candidates.return_value = [
            {
                "id": "group1",
                "rank": 1,
                "score": 85,
                "complexity_score": 5,
                "files": ["/path/file1.py", "/path/file2.py"],
                "lines_saved": 20,
            }
        ]
        orchestrator.ranker = mock_ranker

        # Mock coverage detector
        mock_coverage = MagicMock()
        mock_coverage.get_test_coverage_for_files_batch.return_value = {
            "/path/file1.py": True,
            "/path/file2.py": False,
        }
        orchestrator.coverage_detector = mock_coverage

        # Mock recommendation engine
        mock_recommendation = MagicMock()
        mock_recommendation.generate_deduplication_recommendation.return_value = {
            "action": "refactor",
            "reasoning": "High value refactoring opportunity",
            "priority": "high",
        }
        orchestrator.recommendation_engine = mock_recommendation

        return orchestrator

    def test_analyze_candidates_with_config(self, mock_orchestrator, temp_dir):
        """Test analyze_candidates_with_config workflow."""
        config = AnalysisConfig(
            project_path=temp_dir,
            language="python",
            min_similarity=0.8,
            max_candidates=10,
        )
        result = mock_orchestrator.analyze_candidates_with_config(config)

        assert "candidates" in result
        assert "total_groups_analyzed" in result
        assert "top_candidates_count" in result
        assert "top_candidates_savings_potential" in result
        assert "analysis_metadata" in result

    def test_analyze_candidates_legacy_interface(self, mock_orchestrator, temp_dir):
        """Test legacy analyze_candidates method."""
        result = mock_orchestrator.analyze_candidates(
            project_path=temp_dir,
            language="python",
            min_similarity=0.8,
            max_candidates=10,
        )

        assert "candidates" in result
        assert result["analysis_metadata"]["language"] == "python"

    def test_analyze_candidates_calls_detector(self, mock_orchestrator, temp_dir):
        """Test that detector.find_duplication is called."""
        config = AnalysisConfig(project_path=temp_dir, language="python")
        mock_orchestrator.analyze_candidates_with_config(config)

        mock_orchestrator.detector.find_duplication.assert_called_once()

    def test_analyze_candidates_calls_ranker(self, mock_orchestrator, temp_dir):
        """Test that ranker.rank_deduplication_candidates is called."""
        config = AnalysisConfig(project_path=temp_dir, language="python")
        mock_orchestrator.analyze_candidates_with_config(config)

        mock_orchestrator.ranker.rank_deduplication_candidates.assert_called_once()


class TestProgressCallback:
    """Tests for progress callback functionality."""

    @pytest.fixture
    def _empty_orchestrator(self, orchestrator):
        """Orchestrator with mocked empty-result components."""
        mock_detector = MagicMock()
        mock_detector.find_duplication.return_value = {"duplication_groups": []}
        orchestrator.detector = mock_detector
        orchestrator.ranker = MagicMock()
        orchestrator.ranker.rank_deduplication_candidates.return_value = []
        return orchestrator

    def test_progress_callback_is_called(self, _empty_orchestrator, temp_dir):
        """Test that progress callback is invoked during analysis."""
        progress_stages: List[tuple] = []

        def track_progress(stage: str, percent: float) -> None:
            progress_stages.append((stage, percent))

        config = AnalysisConfig(
            project_path=temp_dir,
            language="python",
            progress_callback=track_progress,
        )
        _empty_orchestrator.analyze_candidates_with_config(config)

        assert len(progress_stages) > 0
        assert progress_stages[0][1] == 0.0
        assert progress_stages[-1][1] == 1.0

    def test_progress_callback_receives_stage_names(self, _empty_orchestrator, temp_dir):
        """Test that progress callback receives meaningful stage names."""
        stages: List[str] = []

        def track_stages(stage: str, _: float) -> None:
            stages.append(stage)

        config = AnalysisConfig(
            project_path=temp_dir,
            language="python",
            progress_callback=track_stages,
        )
        _empty_orchestrator.analyze_candidates_with_config(config)

        assert "Finding duplicate code" in stages
        assert "Analysis complete" in stages


class TestEnrichmentMethods:
    """Tests for candidate enrichment methods."""

    def test_get_top_candidates_limits_results(self, orchestrator):
        """Test that _get_top_candidates respects max_count."""
        candidates = [{"id": i} for i in range(10)]

        result = orchestrator._get_top_candidates(candidates, 5)

        assert len(result) == 5
        assert result[0]["id"] == 0

    def test_get_top_candidates_handles_fewer_than_max(self, orchestrator):
        """Test _get_top_candidates when fewer candidates than max."""
        candidates = [{"id": i} for i in range(3)]

        result = orchestrator._get_top_candidates(candidates, 10)

        assert len(result) == 3

    def test_calculate_total_savings(self, orchestrator):
        """Test total savings calculation."""
        candidates = [
            {"lines_saved": 10, "files": ["a.py", "b.py"]},  # 10 * 2 = 20
            {"lines_saved": 5, "files": ["c.py", "d.py", "e.py"]},  # 5 * 3 = 15
        ]

        total = orchestrator._calculate_total_savings(candidates)

        assert total == 35

    def test_calculate_total_savings_empty_list(self, orchestrator):
        """Test total savings calculation with empty list."""
        total = orchestrator._calculate_total_savings([])

        assert total == 0

    def test_build_analysis_metadata_from_config(self, orchestrator):
        """Test metadata building from config."""
        config = AnalysisConfig(
            project_path="/test/path",
            language="python",
            min_similarity=0.9,
            min_lines=10,
            include_test_coverage=False,
        )

        metadata = orchestrator._build_analysis_metadata_from_config(config)

        assert metadata["language"] == "python"
        assert metadata["min_similarity"] == 0.9
        assert metadata["min_lines"] == 10
        assert metadata["include_test_coverage"] is False
        assert metadata["project_path"] == "/test/path"


class TestEnrichAndSummarize:
    """Tests for _enrich_and_summarize methods."""

    def test_enrich_empty_candidates_returns_early(self, orchestrator):
        """Test that empty candidate list returns early with default structure."""
        config = AnalysisConfig(
            project_path="/test/path",
            language="python",
        )

        result = orchestrator._enrich_and_summarize_with_config([], config)

        assert result["candidates"] == []
        assert result["total_groups_analyzed"] == 0
        assert result["top_candidates_count"] == 0
        assert result["top_candidates_savings_potential"] == 0

    def test_enrich_skips_coverage_when_disabled(self, orchestrator):
        """Test that coverage check is skipped when include_test_coverage=False."""
        mock_coverage = MagicMock()
        orchestrator.coverage_detector = mock_coverage

        mock_recommendation = MagicMock()
        mock_recommendation.generate_deduplication_recommendation.return_value = {
            "action": "review",
            "priority": "low",
        }
        orchestrator.recommendation_engine = mock_recommendation

        candidates = [{"id": "1", "files": ["a.py"], "score": 50, "lines_saved": 10}]
        config = AnalysisConfig(
            project_path="/test/path",
            language="python",
            include_test_coverage=False,
        )

        orchestrator._enrich_and_summarize_with_config(candidates, config)

        # Coverage should not be called
        mock_coverage.get_test_coverage_for_files_batch.assert_not_called()


class TestTestCoverageBatch:
    """Tests for batch test coverage processing."""

    def test_add_test_coverage_batch_empty_candidates(self, orchestrator):
        """Test batch coverage with empty candidate list."""
        mock_coverage = MagicMock()
        orchestrator.coverage_detector = mock_coverage

        orchestrator._add_test_coverage_batch([], "python", "/path")

        mock_coverage.get_test_coverage_for_files_batch.assert_not_called()

    def test_add_test_coverage_batch_collects_unique_files(self, orchestrator):
        """Test that batch coverage deduplicates files."""
        mock_coverage = MagicMock()
        mock_coverage.get_test_coverage_for_files_batch.return_value = {
            "a.py": True,
            "b.py": False,
        }
        orchestrator.coverage_detector = mock_coverage

        candidates = [
            {"id": "1", "files": ["a.py", "b.py"]},
            {"id": "2", "files": ["a.py"]},  # Duplicate file
        ]

        orchestrator._add_test_coverage_batch(candidates, "python", "/path")

        # Should only call with unique files
        call_args = mock_coverage.get_test_coverage_for_files_batch.call_args
        unique_files = call_args[0][0]
        assert len(unique_files) == 2
        assert "a.py" in unique_files
        assert "b.py" in unique_files

    def test_add_test_coverage_batch_distributes_results(self, orchestrator):
        """Test that batch coverage results are distributed to candidates."""
        mock_coverage = MagicMock()
        mock_coverage.get_test_coverage_for_files_batch.return_value = {
            "a.py": True,
            "b.py": False,
        }
        orchestrator.coverage_detector = mock_coverage

        candidates = [
            {"id": "1", "files": ["a.py"]},
            {"id": "2", "files": ["b.py"]},
        ]

        orchestrator._add_test_coverage_batch(candidates, "python", "/path")

        assert candidates[0]["has_tests"] is True
        assert candidates[1]["has_tests"] is False


class TestRecommendations:
    """Tests for recommendation generation."""

    def test_enrich_with_recommendation(self, orchestrator):
        """Test single candidate recommendation enrichment."""
        mock_recommendation = MagicMock()
        mock_recommendation.generate_deduplication_recommendation.return_value = {
            "action": "refactor",
            "priority": "high",
        }
        orchestrator.recommendation_engine = mock_recommendation

        candidate = {
            "score": 80,
            "complexity_score": 5,
            "lines_saved": 20,
            "has_tests": True,
            "files": ["a.py", "b.py"],
        }

        orchestrator._enrich_with_recommendation(candidate)

        assert candidate["recommendation"]["action"] == "refactor"
        assert candidate["recommendation"]["priority"] == "high"


class TestParallelProcessing:
    """Tests for parallel processing functionality."""

    def test_parallel_enrich_sequential_for_single_candidate(self, orchestrator):
        """Test that single candidate uses sequential processing."""

        call_count = 0

        def mock_enrich(candidate: Dict[str, Any]) -> None:
            nonlocal call_count
            call_count += 1
            candidate["enriched"] = True

        candidates = [{"id": "1"}]

        orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=mock_enrich,
            operation_name="test",
            error_field="error",
            default_error_value={},
            parallel=True,
            max_workers=4,
        )

        assert call_count == 1
        assert candidates[0]["enriched"] is True

    def test_parallel_enrich_handles_exceptions(self, orchestrator):
        """Test that parallel enrichment handles exceptions gracefully."""

        def failing_enrich(candidate: Dict[str, Any]) -> None:
            raise RuntimeError("Test error")

        candidates = [{"id": "1"}, {"id": "2"}]

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=failing_enrich,
            operation_name="test",
            error_field="error",
            default_error_value={"failed": True},
            parallel=False,
        )

        assert len(failed) == 2
        assert candidates[0]["error"] == "Test error"
        assert candidates[1]["error"] == "Test error"


class TestErrorHandling:
    """Tests for error handling in enrichment."""

    def test_handle_enrichment_error_logs_and_updates_candidate(self, orchestrator):
        """Test that _handle_enrichment_error updates candidate correctly."""
        candidate: Dict[str, Any] = {"id": "test123"}
        error = ValueError("Something went wrong")

        orchestrator._handle_enrichment_error(
            candidate=candidate,
            error=error,
            operation_name="test_op",
            error_field="test_error",
            default_error_value={"fallback": True},
        )

        assert candidate["test_error"] == "Something went wrong"
        assert candidate["fallback"] is True

    def test_handle_wait_timeout_error(self, orchestrator):
        """A helper wait expiry (WaitTimeoutError) takes the timeout branch."""
        from ast_grep_mcp.utils.futures import WaitTimeoutError

        candidate: Dict[str, Any] = {"id": "test123"}
        error = WaitTimeoutError()

        orchestrator._handle_enrichment_error(
            candidate=candidate,
            error=error,
            operation_name="test_op",
            error_field="test_error",
            default_error_value={},
            timeout_seconds=30,
        )

        assert "timed out" in candidate["test_error"]
        assert "30" in candidate["test_error"]

    def test_handle_worker_raised_timeout_error_is_generic_failure(self, orchestrator):
        """A TimeoutError raised by the enrichment itself must not be
        misclassified as a wait timeout (CR-08)."""
        candidate: Dict[str, Any] = {"id": "test123"}

        orchestrator._handle_enrichment_error(
            candidate=candidate,
            error=TimeoutError("connection timed out on host"),
            operation_name="test_op",
            error_field="test_error",
            default_error_value={},
        )

        assert candidate["test_error"] == "connection timed out on host"


class TestLegacyMethods:
    """Tests for legacy interface methods to ensure backward compatibility."""

    def test_build_analysis_metadata_legacy(self, orchestrator):
        """Test legacy _build_analysis_metadata method."""

        metadata = orchestrator._build_analysis_metadata(
            language="python",
            min_similarity=SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            min_lines=10,
            include_test_coverage=True,
            project_path="/legacy/path",
        )

        assert metadata["language"] == "python"
        assert metadata["min_similarity"] == SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD
        assert metadata["min_lines"] == 10
        assert metadata["include_test_coverage"] is True
        assert metadata["project_path"] == "/legacy/path"

    def test_enrich_and_summarize_legacy(self, orchestrator):
        """Test legacy _enrich_and_summarize method."""

        mock_coverage = MagicMock()
        mock_coverage.get_test_coverage_for_files_batch.return_value = {"a.py": True}
        orchestrator.coverage_detector = mock_coverage

        mock_recommendation = MagicMock()
        mock_recommendation.generate_deduplication_recommendation.return_value = {
            "action": "refactor",
            "priority": "medium",
        }
        orchestrator.recommendation_engine = mock_recommendation

        candidates = [{"id": "1", "files": ["a.py"], "score": 60, "lines_saved": 15}]

        result = orchestrator._enrich_and_summarize(
            ranked_candidates=candidates,
            max_candidates=10,
            include_test_coverage=True,
            language="python",
            project_path="/test/path",
            min_similarity=0.8,
            min_lines=5,
        )

        assert "candidates" in result
        assert "analysis_metadata" in result
        assert result["analysis_metadata"]["language"] == "python"

    def test_add_test_coverage_legacy(self, orchestrator):
        """Test legacy _add_test_coverage method."""

        mock_coverage = MagicMock()
        mock_coverage.get_test_coverage_for_files.return_value = {"a.py": True}
        orchestrator.coverage_detector = mock_coverage

        candidates = [
            {"id": "1", "files": ["a.py"]},
        ]

        failed = orchestrator._add_test_coverage(
            candidates=candidates,
            language="python",
            project_path="/test/path",
            parallel=False,
        )

        assert len(failed) == 0
        assert candidates[0]["has_tests"] is True

    def test_enrich_with_test_coverage_single(self, orchestrator):
        """Test _enrich_with_test_coverage for single candidate."""

        mock_coverage = MagicMock()
        mock_coverage.get_test_coverage_for_files.return_value = {
            "file1.py": True,
            "file2.py": False,
        }
        orchestrator.coverage_detector = mock_coverage

        candidate = {"id": "1", "files": ["file1.py", "file2.py"]}

        orchestrator._enrich_with_test_coverage(candidate, "python", "/project")

        assert "test_coverage" in candidate
        assert candidate["test_coverage"]["file1.py"] is True
        assert candidate["has_tests"] is True


class TestUnsupportedLanguageWarning:
    """Tests for unsupported language warning."""

    def test_unsupported_language_logs_warning(self, orchestrator, temp_dir):
        """Test that unsupported language triggers a warning but doesn't fail."""
        orchestrator._validate_analysis_inputs(temp_dir, "fortran", 0.8, 5, 100)


class TestParallelProcessingAdvanced:
    """Advanced tests for parallel processing with ThreadPoolExecutor."""

    def test_parallel_enrich_uses_threadpool_for_multiple_candidates(self, orchestrator):
        """Test that parallel processing is used for multiple candidates."""

        enriched_ids: List[str] = []

        def mock_enrich(candidate: Dict[str, Any]) -> None:
            enriched_ids.append(candidate["id"])
            candidate["enriched"] = True

        candidates = [{"id": "1"}, {"id": "2"}, {"id": "3"}]

        orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=mock_enrich,
            operation_name="test",
            error_field="error",
            default_error_value={},
            parallel=True,
            max_workers=2,
        )

        assert len(enriched_ids) == 3
        assert all(c["enriched"] for c in candidates)

    def test_parallel_enrich_with_timeout(self, orchestrator):
        """Test parallel enrichment with custom timeout."""

        def fast_enrich(candidate: Dict[str, Any]) -> None:
            candidate["done"] = True

        candidates = [{"id": "1"}, {"id": "2"}]

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=fast_enrich,
            operation_name="test",
            error_field="error",
            default_error_value={},
            parallel=True,
            max_workers=2,
            timeout_per_candidate=60,
        )

        assert len(failed) == 0
        assert all(c["done"] for c in candidates)


class TestParallelErrorHandling:
    """Tests for error handling in parallel processing path."""

    def test_parallel_enrich_handles_exception_in_parallel_mode(self, orchestrator):
        """Test that exceptions in parallel mode are handled correctly."""

        def failing_enrich(candidate: Dict[str, Any]) -> None:
            raise ValueError(f"Error for {candidate['id']}")

        # Need at least 2 candidates to trigger parallel path
        candidates = [{"id": "1"}, {"id": "2"}, {"id": "3"}]

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=failing_enrich,
            operation_name="test_parallel",
            error_field="parallel_error",
            default_error_value={"failed_parallel": True},
            parallel=True,  # Force parallel mode
            max_workers=2,
        )

        # All should fail
        assert len(failed) == 3
        for candidate in candidates:
            assert "parallel_error" in candidate
            assert candidate["failed_parallel"] is True

    def test_timed_out_enrichment_marks_candidate_failed(self, orchestrator):
        """A hung enrichment marks the candidate failed with the timeout error fields.

        Replaces the direct test of the removed _process_completed_future helper;
        the timeout path now runs through utils.futures.map_with_per_item_timeout.
        """
        import threading

        release = threading.Event()
        candidate: Dict[str, Any] = {"id": "timeout_test"}

        def hung_enrich(cand):
            release.wait(timeout=30)

        try:
            failed_candidates = orchestrator._parallel_enrich(
                candidates=[candidate],
                enrich_func=hung_enrich,
                operation_name="timeout_test",
                error_field="timeout_error",
                default_error_value={"timed_out": True},
                parallel=True,
                timeout_per_candidate=1,
            )
        finally:
            release.set()

        assert len(failed_candidates) == 1
        assert candidate["timed_out"] is True
        assert "timed out" in candidate["timeout_error"]


class TestBatchCoverageEdgeCases:
    """Edge case tests for batch coverage processing."""

    def test_add_test_coverage_batch_handles_empty_files_in_candidate(self, orchestrator):
        """Test batch coverage handles candidates with empty file lists."""
        mock_coverage = MagicMock()
        mock_coverage.get_test_coverage_for_files_batch.return_value = {}
        orchestrator.coverage_detector = mock_coverage

        candidates = [
            {"id": "1", "files": []},
            {"id": "2", "files": []},
        ]

        orchestrator._add_test_coverage_batch(candidates, "python", "/path")

        # Should not call batch if no files
        mock_coverage.get_test_coverage_for_files_batch.assert_not_called()

    def test_add_test_coverage_batch_handles_missing_files_key(self, orchestrator):
        """Test batch coverage when candidate has no files key."""
        mock_coverage = MagicMock()
        mock_coverage.get_test_coverage_for_files_batch.return_value = {"a.py": True}
        orchestrator.coverage_detector = mock_coverage

        candidates = [
            {"id": "1", "files": ["a.py"]},
            {"id": "2"},  # No files key
        ]

        orchestrator._add_test_coverage_batch(candidates, "python", "/path")

        # First candidate should have coverage
        assert candidates[0]["has_tests"] is True
        # Second candidate should have empty coverage
        assert candidates[1]["test_coverage"] == {}
        assert candidates[1]["has_tests"] is False


class TestAnalysisConfig:
    """Tests for AnalysisConfig validation."""

    def test_config_validates_min_similarity_range(self):
        """Test AnalysisConfig validates min_similarity."""
        with pytest.raises(ValueError, match="min_similarity"):
            AnalysisConfig(
                project_path="/path",
                language="python",
                min_similarity=1.5,
            )

    def test_config_validates_min_lines(self):
        """Test AnalysisConfig validates min_lines."""
        with pytest.raises(ValueError, match="min_lines"):
            AnalysisConfig(
                project_path="/path",
                language="python",
                min_lines=0,
            )

    def test_config_validates_max_candidates(self):
        """Test AnalysisConfig validates max_candidates."""
        with pytest.raises(ValueError, match="max_candidates"):
            AnalysisConfig(
                project_path="/path",
                language="python",
                max_candidates=0,
            )

    def test_config_validates_max_workers(self):
        """Test AnalysisConfig validates max_workers."""
        with pytest.raises(ValueError, match="max_workers"):
            AnalysisConfig(
                project_path="/path",
                language="python",
                max_workers=0,
            )

    def test_config_to_dict(self):
        """Test AnalysisConfig.to_dict() method."""
        config = AnalysisConfig(
            project_path="/test/path",
            language="python",
            min_similarity=0.9,
        )

        result = config.to_dict()

        assert result["project_path"] == "/test/path"
        assert result["language"] == "python"
        assert result["min_similarity"] == 0.9
        assert "has_progress_callback" in result

    def test_config_normalizes_exclude_patterns(self):
        """Test that None exclude_patterns becomes empty list."""
        config = AnalysisConfig(
            project_path="/path",
            language="python",
            exclude_patterns=None,
        )

        assert config.exclude_patterns == []
