"""Unit tests for DeduplicationAnalysisOrchestrator optimizations.

Tests focus on low-effort optimizations:
1. Component instance caching (1.2) - Lazy initialization
2. Input validation (3.1) - Fail-fast validation
3. Naming consistency (2.4) - Clear API naming
4. Parallel execution utility (1.3) - _parallel_enrich helper
"""

import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from ast_grep_mcp.features.deduplication.analysis_orchestrator import DeduplicationAnalysisOrchestrator


class TestComponentInstanceCaching:
    """Tests for lazy component initialization optimization (1.2)."""

    def test_components_not_initialized_on_construction(self):
        """Test that components are not instantiated immediately."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # Components should not exist yet (lazy initialization)
        assert not hasattr(orchestrator, "_detector")
        assert not hasattr(orchestrator, "_ranker")
        assert not hasattr(orchestrator, "_coverage_detector")
        assert not hasattr(orchestrator, "_recommendation_engine")

    def test_detector_lazy_initialization(self):
        """Test that detector is created on first access."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # First access creates the instance
        detector1 = orchestrator.detector
        assert hasattr(orchestrator, "_detector")
        assert detector1 is not None

        # Subsequent access returns the same instance
        detector2 = orchestrator.detector
        assert detector1 is detector2

    def test_ranker_lazy_initialization(self):
        """Test that ranker is created on first access."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # First access creates the instance
        ranker1 = orchestrator.ranker
        assert hasattr(orchestrator, "_ranker")
        assert ranker1 is not None

        # Subsequent access returns the same instance
        ranker2 = orchestrator.ranker
        assert ranker1 is ranker2

    def test_coverage_detector_lazy_initialization(self):
        """Test that coverage_detector is created on first access."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # First access creates the instance
        detector1 = orchestrator.coverage_detector
        assert hasattr(orchestrator, "_coverage_detector")
        assert detector1 is not None

        # Subsequent access returns the same instance
        detector2 = orchestrator.coverage_detector
        assert detector1 is detector2

    def test_recommendation_engine_lazy_initialization(self):
        """Test that recommendation_engine is created on first access."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # First access creates the instance
        engine1 = orchestrator.recommendation_engine
        assert hasattr(orchestrator, "_recommendation_engine")
        assert engine1 is not None

        # Subsequent access returns the same instance
        engine2 = orchestrator.recommendation_engine
        assert engine1 is engine2

    def test_property_setters_for_dependency_injection(self):
        """Test that properties can be set for testing/mocking."""

        orchestrator = DeduplicationAnalysisOrchestrator()

        # Create mocks
        mock_detector = Mock()
        mock_ranker = Mock()
        mock_coverage = Mock()
        mock_recommendations = Mock()

        # Set via properties
        orchestrator.detector = mock_detector
        orchestrator.ranker = mock_ranker
        orchestrator.coverage_detector = mock_coverage
        orchestrator.recommendation_engine = mock_recommendations

        # Verify setters work
        assert orchestrator.detector is mock_detector
        assert orchestrator.ranker is mock_ranker
        assert orchestrator.coverage_detector is mock_coverage
        assert orchestrator.recommendation_engine is mock_recommendations

    def test_initialization_performance_improvement(self):
        """Test that instantiation is faster with lazy initialization."""
        # Measure initialization time (should be very fast)
        start = time.time()
        for _ in range(100):
            DeduplicationAnalysisOrchestrator()
        elapsed = time.time() - start

        # Should complete 100 instantiations in < 0.1 seconds
        assert elapsed < 0.1, f"Initialization too slow: {elapsed:.3f}s"


class TestInputValidation:
    """Tests for input validation optimization (3.1)."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_invalid_project_path_not_exists(self):
        """Test validation fails for non-existent project path."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        with pytest.raises(ValueError, match="Project path does not exist"):
            orchestrator.analyze_candidates(project_path="/nonexistent/path", language="python")

    def test_invalid_project_path_not_directory(self, temp_project_dir):
        """Test validation fails for project path that is not a directory."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # Create a file instead of directory
        file_path = os.path.join(temp_project_dir, "test.txt")
        Path(file_path).touch()

        with pytest.raises(ValueError, match="Project path is not a directory"):
            orchestrator.analyze_candidates(project_path=file_path, language="python")

    def test_invalid_min_similarity_too_low(self, temp_project_dir):
        """Test validation fails for min_similarity < 0.0."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        with pytest.raises(ValueError, match="min_similarity must be between 0.0 and 1.0"):
            orchestrator.analyze_candidates(project_path=temp_project_dir, language="python", min_similarity=-0.1)

    def test_invalid_min_similarity_too_high(self, temp_project_dir):
        """Test validation fails for min_similarity > 1.0."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        with pytest.raises(ValueError, match="min_similarity must be between 0.0 and 1.0"):
            orchestrator.analyze_candidates(project_path=temp_project_dir, language="python", min_similarity=1.5)

    def test_invalid_min_lines_zero(self, temp_project_dir):
        """Test validation fails for min_lines = 0."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        with pytest.raises(ValueError, match="min_lines must be a positive integer"):
            orchestrator.analyze_candidates(project_path=temp_project_dir, language="python", min_lines=0)

    def test_invalid_min_lines_negative(self, temp_project_dir):
        """Test validation fails for min_lines < 0."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        with pytest.raises(ValueError, match="min_lines must be a positive integer"):
            orchestrator.analyze_candidates(project_path=temp_project_dir, language="python", min_lines=-5)

    def test_invalid_max_candidates_zero(self, temp_project_dir):
        """Test validation fails for max_candidates = 0."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        with pytest.raises(ValueError, match="max_candidates must be a positive integer"):
            orchestrator.analyze_candidates(project_path=temp_project_dir, language="python", max_candidates=0)

    def test_invalid_max_candidates_negative(self, temp_project_dir):
        """Test validation fails for max_candidates < 0."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        with pytest.raises(ValueError, match="max_candidates must be a positive integer"):
            orchestrator.analyze_candidates(project_path=temp_project_dir, language="python", max_candidates=-10)

    def test_valid_inputs_pass_validation(self, temp_project_dir, monkeypatch):
        """Test that valid inputs pass validation (but fail later due to no files)."""

        orchestrator = DeduplicationAnalysisOrchestrator()

        # Mock the detector to avoid actual analysis
        mock_detector = Mock()
        mock_detector.find_duplication.return_value = {"duplication_groups": []}
        orchestrator.detector = mock_detector

        # This should pass validation but return empty results
        orchestrator.analyze_candidates(
            project_path=temp_project_dir, language="python", min_similarity=0.8, min_lines=5, max_candidates=100
        )

        # Validation passed, detector was called
        assert mock_detector.find_duplication.called

    def test_validation_error_messages_are_clear(self, temp_project_dir):
        """Test that validation errors have clear, helpful messages."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # Test project path error message
        try:
            orchestrator.analyze_candidates("/nonexistent", "python")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "/nonexistent" in str(e)
            assert "does not exist" in str(e)

        # Test min_similarity error message
        try:
            orchestrator.analyze_candidates(temp_project_dir, "python", min_similarity=2.0)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "2.0" in str(e)
            assert "0.0 and 1.0" in str(e)

        # Test min_lines error message
        try:
            orchestrator.analyze_candidates(temp_project_dir, "python", min_lines=-1)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "-1" in str(e)
            assert "positive" in str(e)


class TestNamingConsistency:
    """Tests for naming consistency optimization (2.4)."""

    def test_result_structure_has_clear_naming(self, temp_project_dir):
        """Test that result structure uses clear, unambiguous names."""

        orchestrator = DeduplicationAnalysisOrchestrator()

        # Mock detector to return some candidates
        mock_detector = Mock()
        mock_detector.find_duplication.return_value = {
            "duplication_groups": [
                {"lines_saved": 50, "complexity_score": 5},
                {"lines_saved": 30, "complexity_score": 3},
            ]
        }
        orchestrator.detector = mock_detector

        result = orchestrator.analyze_candidates(
            project_path=temp_project_dir,
            language="python",
            max_candidates=1,  # Only return 1 candidate
        )

        # Check new naming structure
        assert "total_groups_analyzed" in result
        assert "top_candidates_count" in result
        assert "top_candidates_savings_potential" in result

        # Old ambiguous names should not be present
        assert "total_groups" not in result
        assert "total_savings_potential" not in result

    def test_top_candidates_count_reflects_actual_count(self, temp_project_dir):
        """Test that top_candidates_count matches the actual returned count."""

        orchestrator = DeduplicationAnalysisOrchestrator()

        # Mock detector to return 5 candidates
        mock_detector = Mock()
        mock_detector.find_duplication.return_value = {
            "duplication_groups": [{"lines_saved": i * 10, "complexity_score": i} for i in range(1, 6)]
        }
        orchestrator.detector = mock_detector

        # Request only top 3
        result = orchestrator.analyze_candidates(project_path=temp_project_dir, language="python", max_candidates=3)

        # Verify counts
        assert result["total_groups_analyzed"] == 3  # After early exit, only 3 ranked
        assert result["top_candidates_count"] == 3
        assert len(result["candidates"]) == 3

    def test_savings_calculated_from_top_candidates_only(self, temp_project_dir):
        """Test that savings are calculated from top candidates, not all."""

        orchestrator = DeduplicationAnalysisOrchestrator()

        # Mock detector to return candidates with known savings
        mock_detector = Mock()
        mock_detector.find_duplication.return_value = {
            "duplication_groups": [
                {"lines_saved": 100, "complexity_score": 1, "files": ["a.py"]},
                {"lines_saved": 50, "complexity_score": 2, "files": ["b.py"]},
                {"lines_saved": 25, "complexity_score": 3, "files": ["c.py"]},
            ]
        }
        orchestrator.detector = mock_detector

        # Request only top 2
        result = orchestrator.analyze_candidates(project_path=temp_project_dir, language="python", max_candidates=2)

        # top_candidates_savings_potential should only include top 2
        # Expected: 100*1 + 50*1 = 150
        assert result["top_candidates_savings_potential"] == 150

    def test_logging_uses_consistent_naming(self, temp_project_dir, capsys):
        """Test that logging also uses the new consistent naming."""

        orchestrator = DeduplicationAnalysisOrchestrator()

        # Mock detector with non-empty duplicates to test analysis_complete log
        mock_detector = Mock()
        mock_detector.find_duplication.return_value = {
            "duplication_groups": [
                {"similarity": 0.9, "lines_saved": 100, "files": ["/tmp/file1.py", "/tmp/file2.py"], "complexity_score": 3}
            ]
        }
        orchestrator.detector = mock_detector

        # Mock ranker to return the candidate
        mock_ranker = Mock()
        mock_ranker.rank_deduplication_candidates.return_value = [
            {
                "similarity": 0.9,
                "lines_saved": 100,
                "files": ["/tmp/file1.py", "/tmp/file2.py"],
                "complexity_score": 3,
                "score": 75.0,
                "rank": 1,
            }
        ]
        orchestrator.ranker = mock_ranker

        # Run analysis without test coverage to avoid file I/O
        orchestrator.analyze_candidates(project_path=temp_project_dir, language="python", include_test_coverage=False)

        # Capture stdout (structlog outputs to stdout)
        captured = capsys.readouterr()
        log_output = captured.out + captured.err

        # Check that logs use new naming
        assert "total_groups_analyzed" in log_output
        assert "top_candidates_count" in log_output
        assert "top_candidates_savings_potential" in log_output
        assert "analysis_complete" in log_output


class TestParallelEnrichUtility:
    """Tests for parallel execution utility optimization (1.3)."""

    def test_parallel_enrich_sequential_mode(self):
        """Test _parallel_enrich in sequential mode (parallel=False)."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # Create test candidates
        candidates = [{"id": "c1", "value": 0}, {"id": "c2", "value": 0}, {"id": "c3", "value": 0}]

        # Mock enrichment function
        def enrich_func(candidate, increment):
            candidate["value"] += increment

        # Call _parallel_enrich in sequential mode
        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test_enrich",
            error_field="test_error",
            default_error_value={"value": -1},
            parallel=False,
            increment=10,
        )

        # Verify all candidates enriched
        assert len(failed) == 0
        assert all(c["value"] == 10 for c in candidates)

    def test_parallel_enrich_parallel_mode(self):
        """Test _parallel_enrich in parallel mode (parallel=True)."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # Create test candidates
        candidates = [{"id": "c1", "value": 0}, {"id": "c2", "value": 0}, {"id": "c3", "value": 0}]

        # Mock enrichment function
        def enrich_func(candidate, increment):
            candidate["value"] += increment

        # Call _parallel_enrich in parallel mode
        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test_enrich",
            error_field="test_error",
            default_error_value={"value": -1},
            parallel=True,
            max_workers=2,
            increment=10,
        )

        # Verify all candidates enriched
        assert len(failed) == 0
        assert all(c["value"] == 10 for c in candidates)

    def test_parallel_enrich_single_candidate_uses_sequential(self):
        """Test that single candidate always uses sequential mode."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # Single candidate
        candidates = [{"id": "c1", "value": 0}]
        call_count = 0

        def enrich_func(candidate):
            nonlocal call_count
            call_count += 1
            candidate["value"] = 42

        # Call with parallel=True, but should use sequential
        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test",
            error_field="error",
            default_error_value={},
            parallel=True,
        )

        # Verify sequential execution
        assert call_count == 1
        assert candidates[0]["value"] == 42
        assert len(failed) == 0

    def test_parallel_enrich_error_handling_sequential(self):
        """Test error handling in sequential mode."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        candidates = [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}]

        # Enrich function that fails for c2
        def enrich_func(candidate):
            if candidate["id"] == "c2":
                raise ValueError("Simulated error")
            candidate["success"] = True

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test",
            error_field="error_msg",
            default_error_value={"success": False},
            parallel=False,
        )

        # Verify error handling
        assert len(failed) == 1
        assert failed[0]["id"] == "c2"
        assert "error_msg" in failed[0]
        assert "Simulated error" in failed[0]["error_msg"]
        assert failed[0]["success"] is False

        # Verify successful candidates
        assert candidates[0]["success"] is True
        assert candidates[2]["success"] is True
        assert "error_msg" not in candidates[0]
        assert "error_msg" not in candidates[2]

    def test_parallel_enrich_error_handling_parallel(self):
        """Test error handling in parallel mode."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        candidates = [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}, {"id": "c4"}]

        # Enrich function that fails for c2 and c4
        def enrich_func(candidate):
            if candidate["id"] in ["c2", "c4"]:
                raise ValueError(f"Error for {candidate['id']}")
            candidate["success"] = True

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test",
            error_field="error_msg",
            default_error_value={"success": False},
            parallel=True,
            max_workers=2,
        )

        # Verify error handling
        assert len(failed) == 2
        failed_ids = {c["id"] for c in failed}
        assert failed_ids == {"c2", "c4"}

        # All failed candidates have error markers
        for candidate in failed:
            assert "error_msg" in candidate
            assert "Error for" in candidate["error_msg"]
            assert candidate["success"] is False

        # Verify successful candidates
        successful = [c for c in candidates if c["id"] not in failed_ids]
        assert len(successful) == 2
        for candidate in successful:
            assert candidate["success"] is True
            assert "error_msg" not in candidate

    def test_parallel_enrich_default_error_value_dict(self):
        """Test that dict default_error_value sets multiple fields."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        candidates = [{"id": "c1"}]

        def failing_func(candidate):
            raise ValueError("Test error")

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=failing_func,
            operation_name="test",
            error_field="error",
            default_error_value={"field1": "default1", "field2": 42, "field3": False},
            parallel=False,
        )

        # Verify all default fields were set
        assert len(failed) == 1
        assert failed[0]["field1"] == "default1"
        assert failed[0]["field2"] == 42
        assert failed[0]["field3"] is False
        assert "error" in failed[0]

    def test_parallel_enrich_kwargs_passed_to_enrich_func(self):
        """Test that **kwargs are correctly passed to enrich_func."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        candidates = [{"id": "c1"}]

        def enrich_func(candidate, arg1, arg2, arg3=None):
            candidate["arg1"] = arg1
            candidate["arg2"] = arg2
            candidate["arg3"] = arg3

        orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test",
            error_field="error",
            default_error_value={},
            parallel=False,
            arg1="value1",
            arg2=123,
            arg3="optional",
        )

        # Verify kwargs were passed
        assert candidates[0]["arg1"] == "value1"
        assert candidates[0]["arg2"] == 123
        assert candidates[0]["arg3"] == "optional"

    def test_parallel_enrich_logging_success(self, capsys):
        """Test that _parallel_enrich logs success information."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        candidates = [{"id": f"c{i}"} for i in range(5)]

        def enrich_func(candidate):
            candidate["enriched"] = True

        orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test_operation",
            error_field="error",
            default_error_value={},
            parallel=True,
        )

        captured = capsys.readouterr()
        log_output = captured.out + captured.err

        # Check logging
        assert "test_operation_added" in log_output
        assert "candidate_count" in log_output
        assert "failed_count" in log_output

    def test_parallel_enrich_logging_failures(self, capsys):
        """Test that _parallel_enrich logs failure information."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        candidates = [{"id": "c1"}, {"id": "c2"}]

        def failing_func(candidate):
            if candidate["id"] == "c1":
                raise ValueError("Fail c1")
            candidate["ok"] = True

        orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=failing_func,
            operation_name="test_op",
            error_field="error",
            default_error_value={"ok": False},
            parallel=False,
        )

        captured = capsys.readouterr()
        log_output = captured.out + captured.err

        # Check error logging
        assert "test_op_enrichment_failed" in log_output
        assert "c1" in log_output or "unknown" in log_output

    def test_parallel_enrich_returns_failed_candidates(self):
        """Test that _parallel_enrich returns list of failed candidates."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        candidates = [{"id": "c1", "value": 1}, {"id": "c2", "value": 2}, {"id": "c3", "value": 3}]

        def enrich_func(candidate):
            if candidate["value"] == 2:
                raise ValueError("Even number")
            candidate["processed"] = True

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test",
            error_field="error",
            default_error_value={"processed": False},
            parallel=False,
        )

        # Verify return value
        assert isinstance(failed, list)
        assert len(failed) == 1
        assert failed[0]["id"] == "c2"
        assert failed[0]["processed"] is False

    def test_parallel_enrich_used_by_add_test_coverage(self):
        """Test that _add_test_coverage now uses _parallel_enrich."""
        from unittest.mock import patch

        orchestrator = DeduplicationAnalysisOrchestrator()
        candidates = [{"id": "c1", "files": ["/tmp/test.py"]}]

        # Patch _parallel_enrich to verify it's called
        with patch.object(orchestrator, "_parallel_enrich", return_value=[]) as mock_parallel:
            orchestrator._add_test_coverage(candidates=candidates, language="python", project_path="/tmp", parallel=True, max_workers=4)

            # Verify _parallel_enrich was called with correct arguments
            assert mock_parallel.called
            call_args = mock_parallel.call_args
            assert call_args.kwargs["operation_name"] == "test_coverage"
            assert call_args.kwargs["error_field"] == "test_coverage_error"
            assert call_args.kwargs["language"] == "python"
            assert call_args.kwargs["project_path"] == "/tmp"

    def test_parallel_enrich_used_by_add_recommendations(self):
        """Test that _add_recommendations now uses _parallel_enrich."""
        from unittest.mock import patch

        orchestrator = DeduplicationAnalysisOrchestrator()
        candidates = [{"id": "c1", "score": 75}]

        # Patch _parallel_enrich to verify it's called
        with patch.object(orchestrator, "_parallel_enrich", return_value=[]) as mock_parallel:
            orchestrator._add_recommendations(candidates=candidates, parallel=True, max_workers=4)

            # Verify _parallel_enrich was called with correct arguments
            assert mock_parallel.called
            call_args = mock_parallel.call_args
            assert call_args.kwargs["operation_name"] == "recommendations"
            assert call_args.kwargs["error_field"] == "recommendation_error"

    def test_parallel_enrich_max_workers_parameter(self):
        """Test that max_workers parameter is accepted and used."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        [{"id": f"c{i}"} for i in range(10)]

        def enrich_func(candidate):
            candidate["done"] = True

        # Just verify that different max_workers values work without errors
        for max_workers in [1, 2, 4, 8]:
            test_candidates = [{"id": f"c{i}"} for i in range(5)]

            failed = orchestrator._parallel_enrich(
                candidates=test_candidates,
                enrich_func=enrich_func,
                operation_name="test",
                error_field="error",
                default_error_value={},
                parallel=True,
                max_workers=max_workers,
            )

            # Verify execution completed successfully
            assert len(failed) == 0
            assert all(c["done"] is True for c in test_candidates)

    def test_parallel_enrich_timeout_parameter_accepted(self):
        """Test that timeout_per_candidate parameter is accepted."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        candidates = [{"id": "c1"}, {"id": "c2"}]

        def enrich_func(candidate):
            time.sleep(0.1)  # Brief delay
            candidate["done"] = True

        # Call with explicit timeout parameter
        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test",
            error_field="error",
            default_error_value={},
            parallel=True,
            timeout_per_candidate=5,  # 5 seconds should be plenty
        )

        # Verify successful execution with timeout set
        assert len(failed) == 0
        assert all(c["done"] is True for c in candidates)

    def test_parallel_enrich_timeout_uses_default(self):
        """Test that default timeout is used when not specified."""
        from ast_grep_mcp.constants import ParallelProcessing

        orchestrator = DeduplicationAnalysisOrchestrator()
        candidates = [{"id": "c1"}]

        def enrich_func(candidate):
            time.sleep(0.05)  # Brief delay
            candidate["done"] = True

        # Call without timeout parameter - should use default
        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test",
            error_field="error",
            default_error_value={},
            parallel=True,
        )

        # Verify execution completed (default timeout should be sufficient)
        assert len(failed) == 0
        assert candidates[0]["done"] is True
        # Verify default timeout constant exists
        assert ParallelProcessing.DEFAULT_TIMEOUT_PER_CANDIDATE_SECONDS > 0

    def test_parallel_enrich_timeout_constant_exists(self):
        """Test that timeout constants are properly defined."""
        from ast_grep_mcp.constants import ParallelProcessing

        # Verify timeout constants exist and have reasonable values
        assert hasattr(ParallelProcessing, "DEFAULT_TIMEOUT_PER_CANDIDATE_SECONDS")
        assert hasattr(ParallelProcessing, "MAX_TIMEOUT_SECONDS")
        assert ParallelProcessing.DEFAULT_TIMEOUT_PER_CANDIDATE_SECONDS > 0
        assert ParallelProcessing.MAX_TIMEOUT_SECONDS > ParallelProcessing.DEFAULT_TIMEOUT_PER_CANDIDATE_SECONDS

    def test_parallel_enrich_timeout_parameter_is_passed_through(self):
        """Test that timeout parameter is accepted and doesn't cause errors.

        Note: This test verifies the parameter plumbing rather than actual timeout
        behavior, since Python threads cannot be forcibly interrupted.
        """
        orchestrator = DeduplicationAnalysisOrchestrator()

        def enrich_func(candidate):
            candidate["done"] = True

        # Call with various timeout values - all should work
        for timeout_val in [None, 10, 30, 60]:
            test_candidates = [{"id": "c1"}]
            failed = orchestrator._parallel_enrich(
                candidates=test_candidates,
                enrich_func=enrich_func,
                operation_name="test",
                error_field="error",
                default_error_value={},
                parallel=True,
                timeout_per_candidate=timeout_val,
            )
            assert len(failed) == 0
            assert test_candidates[0]["done"] is True

    def test_parallel_enrich_timeout_in_method_signatures(self):
        """Test that timeout parameters exist in public method signatures."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        # Verify _parallel_enrich has timeout parameter
        import inspect

        parallel_sig = inspect.signature(orchestrator._parallel_enrich)
        assert "timeout_per_candidate" in parallel_sig.parameters

        # Verify _add_recommendations has timeout parameter
        rec_sig = inspect.signature(orchestrator._add_recommendations)
        assert "timeout_per_candidate" in rec_sig.parameters

        # Verify _add_test_coverage_batch has timeout parameter
        cov_sig = inspect.signature(orchestrator._add_test_coverage_batch)
        assert "timeout_per_candidate" in cov_sig.parameters

    def test_add_recommendations_accepts_timeout(self):
        """Test that _add_recommendations accepts timeout_per_candidate parameter."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        candidates = [{"id": "c1", "similarity": 0.9, "lines_saved": 100}]

        # Call with timeout parameter - should not raise
        failed = orchestrator._add_recommendations(
            candidates=candidates,
            parallel=False,  # Sequential to avoid actual parallelism
            timeout_per_candidate=30,
        )

        # Verify it ran without error
        assert isinstance(failed, list)
        assert "recommendation" in candidates[0]

    def test_add_test_coverage_batch_accepts_timeout(self, temp_project_dir):
        """Test that _add_test_coverage_batch accepts timeout_per_candidate parameter."""
        from pathlib import Path

        orchestrator = DeduplicationAnalysisOrchestrator()
        temp_path = Path(temp_project_dir)
        candidates = [{"id": "c1", "files": [str(temp_path / "test.py")]}]

        # Create test file
        test_file = temp_path / "test.py"
        test_file.write_text("print('hello')")

        # Call with timeout parameter - should not raise
        orchestrator._add_test_coverage_batch(
            candidates=candidates,
            language="python",
            project_path=str(temp_project_dir),
            parallel=False,  # Sequential to avoid complexity
            timeout_per_candidate=30,
        )

        # Verify it ran without error and added coverage info
        assert "test_coverage" in candidates[0] or "has_tests" in candidates[0]


class TestPerCandidateTimeoutEnforcement:
    """Regression tests for BUG-06: a hung enrichment must not block the call forever.

    Before the fix, _process_parallel_enrichment iterated as_completed(futures)
    without a timeout, so future.result(timeout=...) only ran on already-completed
    futures and TimeoutError was unreachable; one hung enrichment blocked forever
    (including at the executor's implicit shutdown(wait=True)).
    """

    TIMEOUT_SECONDS = 0.2
    HUNG_WORKER_SAFETY_NET_SECONDS = 30
    # Elapsed bound: total_timeout (300s default) caps wall-clock, so each test
    # should return well before even a single per-candidate wait expires.
    ELAPSED_BOUND_SECONDS = 10
    EXPECTED_TIMEOUT_ERROR = f"Operation timed out after {TIMEOUT_SECONDS}s"

    def test_hung_enrichment_times_out_and_marks_candidate(self):
        """A hung candidate is marked timed out while fast candidates succeed."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        release = threading.Event()
        hung = {"id": "hung"}
        fast = {"id": "fast"}

        def enrich_func(candidate):
            if candidate["id"] == "hung":
                release.wait(timeout=self.HUNG_WORKER_SAFETY_NET_SECONDS)
            else:
                candidate["done"] = True

        try:
            start = time.monotonic()
            failed = orchestrator._parallel_enrich(
                candidates=[hung, fast],
                enrich_func=enrich_func,
                operation_name="test",
                error_field="error",
                default_error_value={"enriched": False},
                parallel=True,
                max_workers=2,
                timeout_per_candidate=self.TIMEOUT_SECONDS,
            )
            elapsed = time.monotonic() - start
        finally:
            release.set()

        assert elapsed < self.ELAPSED_BOUND_SECONDS, f"call should return promptly, took {elapsed:.1f}s"
        assert failed == [hung]
        assert hung["error"] == self.EXPECTED_TIMEOUT_ERROR
        assert hung["enriched"] is False
        assert fast["done"] is True
        assert "error" not in fast

    def test_all_hung_candidates_each_marked_timed_out(self):
        """Every hung candidate is marked failed; never-started ones are marked too."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        release = threading.Event()
        candidates = [{"id": f"c{i}"} for i in range(3)]

        def enrich_func(candidate):
            release.wait(timeout=self.HUNG_WORKER_SAFETY_NET_SECONDS)

        try:
            start = time.monotonic()
            failed = orchestrator._parallel_enrich(
                candidates=candidates,
                enrich_func=enrich_func,
                operation_name="test",
                error_field="error",
                default_error_value={},
                parallel=True,
                max_workers=2,
                timeout_per_candidate=self.TIMEOUT_SECONDS,
            )
            elapsed = time.monotonic() - start
        finally:
            release.set()

        # Wall-clock is bounded by total_timeout (300s default), not N×per_item.
        assert elapsed < self.ELAPSED_BOUND_SECONDS, f"call should return promptly, took {elapsed:.1f}s"
        assert failed == candidates
        # All candidates are marked as failed with a timeout or cancellation error.
        assert all("error" in c for c in candidates)


class TestSequentialPathTimeoutEnforcement:
    """Regression tests for BUG-06-CR-02: sequential/single-candidate path must enforce timeout.

    Before the fix, _parallel_enrich routed parallel=False or len==1 to
    _process_sequential_enrichment, which called enrich_func inline with no
    timeout — timeout_per_candidate was silently ignored.
    """

    TIMEOUT_SECONDS = 0.2
    HUNG_WORKER_SAFETY_NET_SECONDS = 30
    ELAPSED_BOUND_SECONDS = 10
    EXPECTED_TIMEOUT_ERROR = f"Operation timed out after {TIMEOUT_SECONDS}s"

    def test_single_candidate_hung_enrichment_times_out(self):
        """A single hung candidate is timed out even with parallel=True (len==1 path)."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        release = threading.Event()
        hung = {"id": "hung"}

        def enrich_func(candidate):
            release.wait(timeout=self.HUNG_WORKER_SAFETY_NET_SECONDS)

        try:
            start = time.monotonic()
            failed = orchestrator._parallel_enrich(
                candidates=[hung],
                enrich_func=enrich_func,
                operation_name="test",
                error_field="error",
                default_error_value={"enriched": False},
                parallel=True,
                max_workers=4,
                timeout_per_candidate=self.TIMEOUT_SECONDS,
            )
            elapsed = time.monotonic() - start
        finally:
            release.set()

        assert elapsed < self.ELAPSED_BOUND_SECONDS, f"call should return promptly, took {elapsed:.1f}s"
        assert failed == [hung]
        assert hung["error"] == self.EXPECTED_TIMEOUT_ERROR
        assert hung["enriched"] is False

    def test_sequential_parallel_false_hung_enrichment_times_out(self):
        """A hung enrichment is timed out when parallel=False is explicitly requested."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        release = threading.Event()
        hung = {"id": "hung"}
        fast = {"id": "fast"}

        def enrich_func(candidate):
            if candidate["id"] == "hung":
                release.wait(timeout=self.HUNG_WORKER_SAFETY_NET_SECONDS)
            else:
                candidate["done"] = True

        try:
            start = time.monotonic()
            failed = orchestrator._parallel_enrich(
                candidates=[hung, fast],
                enrich_func=enrich_func,
                operation_name="test",
                error_field="error",
                default_error_value={"enriched": False},
                parallel=False,
                max_workers=4,
                timeout_per_candidate=self.TIMEOUT_SECONDS,
            )
            elapsed = time.monotonic() - start
        finally:
            release.set()

        assert elapsed < self.ELAPSED_BOUND_SECONDS, f"call should return promptly, took {elapsed:.1f}s"
        assert failed == [hung]
        assert hung["error"] == self.EXPECTED_TIMEOUT_ERROR
        assert hung["enriched"] is False
        assert fast["done"] is True
        assert "error" not in fast


class TestAbandonedWorkerIsolation:
    """Regression tests for BUG-06-CR-03: abandoned workers must not mutate returned candidates.

    Workers enrich a private deep copy that is merged back only on success, so
    a hung worker that wakes after its timeout writes into an orphaned copy —
    never into the candidate dict the caller already received (previously a
    race with downstream stages and MCP JSON serialization).
    """

    TIMEOUT_SECONDS = 1
    EXPECTED_TIMEOUT_ERROR = f"Operation timed out after {TIMEOUT_SECONDS}s"
    WORKER_JOIN_SECONDS = 10
    HUNG_WORKER_SAFETY_NET_SECONDS = 60

    def test_late_finishing_worker_cannot_mutate_returned_candidate(self):
        """Parallel path: a worker waking after timeout writes only to the orphaned copy."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        release = threading.Event()
        worker_done = threading.Event()
        hung = {"id": "hung"}
        fast = {"id": "fast"}

        def enrich_func(candidate):
            if candidate["id"] == "hung":
                release.wait(timeout=self.HUNG_WORKER_SAFETY_NET_SECONDS)
                candidate["late_write"] = True
                candidate["has_tests"] = True
                worker_done.set()
            else:
                candidate["done"] = True

        try:
            failed = orchestrator._parallel_enrich(
                candidates=[hung, fast],
                enrich_func=enrich_func,
                operation_name="test",
                error_field="error",
                default_error_value={"has_tests": False},
                parallel=True,
                max_workers=2,
                timeout_per_candidate=self.TIMEOUT_SECONDS,
            )
        finally:
            release.set()

        assert failed == [hung]
        assert hung["error"] == self.EXPECTED_TIMEOUT_ERROR
        assert hung["has_tests"] is False

        # Wake the abandoned worker and let it finish its late writes.
        assert worker_done.wait(timeout=self.WORKER_JOIN_SECONDS), "abandoned worker never finished"
        assert "late_write" not in hung, "late worker write leaked into the returned candidate"
        assert hung["has_tests"] is False
        assert fast["done"] is True

    def test_sequential_path_late_worker_cannot_mutate_returned_candidate(self):
        """Sequential (single-candidate) path gets the same isolation."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        release = threading.Event()
        worker_done = threading.Event()
        hung = {"id": "hung"}

        def enrich_func(candidate):
            release.wait(timeout=self.HUNG_WORKER_SAFETY_NET_SECONDS)
            candidate["late_write"] = True
            worker_done.set()

        try:
            failed = orchestrator._parallel_enrich(
                candidates=[hung],
                enrich_func=enrich_func,
                operation_name="test",
                error_field="error",
                default_error_value={"enriched": False},
                parallel=True,
                timeout_per_candidate=self.TIMEOUT_SECONDS,
            )
        finally:
            release.set()

        assert failed == [hung]
        assert hung["error"] == self.EXPECTED_TIMEOUT_ERROR

        assert worker_done.wait(timeout=self.WORKER_JOIN_SECONDS), "abandoned worker never finished"
        assert "late_write" not in hung, "late worker write leaked into the returned candidate"
        assert hung["enriched"] is False

    def test_successful_enrichment_merges_back_onto_original_dicts(self):
        """Success path: enrich_func mutations land on the exact dict objects passed in."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        candidates = [{"id": "c1", "files": ["a.py"]}, {"id": "c2", "files": ["b.py"]}]
        originals = list(candidates)

        def enrich_func(candidate):
            candidate["enriched"] = True
            candidate["score"] = {"value": 1}

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test",
            error_field="error",
            default_error_value={},
            parallel=True,
            max_workers=2,
            timeout_per_candidate=self.TIMEOUT_SECONDS,
        )

        assert failed == []
        for original in originals:
            assert original["enriched"] is True
            assert original["score"] == {"value": 1}
            assert "error" not in original

    def test_failed_enrichment_leaves_original_without_partial_writes(self):
        """An enrich_func that mutates then raises leaves only error fields on the original."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        candidates = [{"id": "c1"}, {"id": "c2"}]

        def enrich_func(candidate):
            candidate["partial"] = True
            raise ValueError("boom")

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test",
            error_field="error",
            default_error_value={"enriched": False},
            parallel=True,
            max_workers=2,
            timeout_per_candidate=self.TIMEOUT_SECONDS,
        )

        assert failed == candidates
        for candidate in candidates:
            assert "partial" not in candidate, "partial write from failed enrichment leaked"
            assert candidate["error"] == "boom"
            assert candidate["enriched"] is False

    def test_uncopyable_candidate_fails_alone_without_aborting_stage(self):
        """A candidate deepcopy can't handle fails alone; the rest still enrich."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        uncopyable = {"id": "bad", "lock": threading.Lock()}
        normal = {"id": "ok"}

        def enrich_func(candidate):
            candidate["enriched"] = True

        failed = orchestrator._parallel_enrich(
            candidates=[uncopyable, normal],
            enrich_func=enrich_func,
            operation_name="test",
            error_field="error",
            default_error_value={"enriched": False},
            parallel=True,
            max_workers=2,
            timeout_per_candidate=self.TIMEOUT_SECONDS,
        )

        assert failed == [uncopyable]
        assert "error" in uncopyable
        assert uncopyable["enriched"] is False
        assert normal["enriched"] is True


class TestGlobalDeadlineEnforcement:
    """Regression tests for CR-05 / CR-26: MAX_TIMEOUT_SECONDS must be enforced as a shared
    wall-clock cap in _parallel_enrich so total wall-clock is O(MAX_TIMEOUT) not O(N×per_item).

    Before the fix ParallelProcessing.MAX_TIMEOUT_SECONDS=300 was dead config — defined but never
    referenced by the actual wait loop — so N hung candidates × 30s per item = ~3000s worst case.
    """

    HUNG_WORKER_SAFETY_NET_SECONDS = 30
    PER_ITEM_TIMEOUT_SECONDS = 5
    TOTAL_TIMEOUT_SECONDS = 1.5  # well below n_candidates × PER_ITEM_TIMEOUT_SECONDS

    def test_total_timeout_bounds_wall_clock_below_n_times_per_item(self):
        """Parallel path: total wall-clock is bounded by total_timeout_seconds, not N×per_item."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        release = threading.Event()
        n_candidates = 4
        candidates = [{"id": f"c{i}"} for i in range(n_candidates)]

        def enrich_func(candidate):
            release.wait(timeout=self.HUNG_WORKER_SAFETY_NET_SECONDS)

        try:
            start = time.monotonic()
            failed = orchestrator._parallel_enrich(
                candidates=candidates,
                enrich_func=enrich_func,
                operation_name="test",
                error_field="error",
                default_error_value={"enriched": False},
                parallel=True,
                max_workers=2,
                timeout_per_candidate=self.PER_ITEM_TIMEOUT_SECONDS,
                total_timeout_seconds=self.TOTAL_TIMEOUT_SECONDS,
            )
            elapsed = time.monotonic() - start
        finally:
            release.set()

        assert elapsed < self.PER_ITEM_TIMEOUT_SECONDS, (
            f"should return in ~{self.TOTAL_TIMEOUT_SECONDS}s, not {n_candidates}×{self.PER_ITEM_TIMEOUT_SECONDS}s; "
            f"took {elapsed:.2f}s"
        )
        assert len(failed) == n_candidates
        assert all(c["enriched"] is False for c in candidates)

    def test_sequential_total_timeout_bounds_wall_clock(self):
        """Sequential path: global deadline also prevents N×per_item wait."""
        orchestrator = DeduplicationAnalysisOrchestrator()
        release = threading.Event()
        n_candidates = 3
        candidates = [{"id": f"c{i}"} for i in range(n_candidates)]

        def enrich_func(candidate):
            release.wait(timeout=self.HUNG_WORKER_SAFETY_NET_SECONDS)

        try:
            start = time.monotonic()
            failed = orchestrator._parallel_enrich(
                candidates=candidates,
                enrich_func=enrich_func,
                operation_name="test",
                error_field="error",
                default_error_value={"enriched": False},
                parallel=False,
                max_workers=1,
                timeout_per_candidate=self.PER_ITEM_TIMEOUT_SECONDS,
                total_timeout_seconds=self.TOTAL_TIMEOUT_SECONDS,
            )
            elapsed = time.monotonic() - start
        finally:
            release.set()

        assert elapsed < self.PER_ITEM_TIMEOUT_SECONDS, (
            f"should return in ~{self.TOTAL_TIMEOUT_SECONDS}s, not {n_candidates}×{self.PER_ITEM_TIMEOUT_SECONDS}s; "
            f"took {elapsed:.2f}s"
        )
        assert len(failed) == n_candidates
        assert all(c["enriched"] is False for c in candidates)

    def test_max_timeout_seconds_constant_is_enforced_as_default(self):
        """ParallelProcessing.MAX_TIMEOUT_SECONDS is the default total_timeout resolved by _parallel_enrich."""
        from ast_grep_mcp.constants import ParallelProcessing

        orchestrator = DeduplicationAnalysisOrchestrator()
        assert orchestrator._resolve_total_timeout(None) == float(ParallelProcessing.MAX_TIMEOUT_SECONDS)
        assert orchestrator._resolve_total_timeout(60.0) == 60.0


class TestWorkerRaisedTimeoutClassification:
    """CR-08/CR-09: a TimeoutError raised by the enrichment itself must be
    recorded with its real message, not misclassified as a wait timeout."""

    def test_worker_raised_os_timeout_keeps_real_message(self):
        import errno

        orchestrator = DeduplicationAnalysisOrchestrator()
        candidates = [{"id": "c1"}, {"id": "c2"}]

        def enrich_func(candidate):
            raise OSError(errno.ETIMEDOUT, "read timed out after 2s")

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test_enrich",
            error_field="test_error",
            default_error_value={"enriched": False},
            parallel=True,
            max_workers=2,
        )

        assert len(failed) == 2
        for candidate in candidates:
            assert "read timed out after 2s" in candidate["test_error"]
            assert "Operation timed out after" not in candidate["test_error"]

    def test_sequential_worker_raised_bare_timeout_never_yields_nones(self):
        orchestrator = DeduplicationAnalysisOrchestrator()
        candidates = [{"id": "c1"}]

        def enrich_func(candidate):
            raise TimeoutError()

        failed = orchestrator._parallel_enrich(
            candidates=candidates,
            enrich_func=enrich_func,
            operation_name="test_enrich",
            error_field="test_error",
            default_error_value={"enriched": False},
            parallel=False,
        )

        assert len(failed) == 1
        assert candidates[0]["test_error"] == "TimeoutError"
        assert "None" not in candidates[0]["test_error"]
