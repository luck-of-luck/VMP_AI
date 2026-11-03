"""Tests for optimized batch test coverage detection.

This file tests the performance-optimized batch test coverage methods added
to improve deduplication analysis performance by 60-80%.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from ast_grep_mcp.constants import SemanticSimilarityDefaults
from ast_grep_mcp.features.deduplication.coverage import CoverageDetector


class TestBatchCoverageOptimization:
    """Tests for batch test coverage optimization."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project with test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = Path(tmpdir)

            # Create source files
            src_dir = project_root / "src"
            src_dir.mkdir()
            (src_dir / "module1.py").write_text("def func1(): pass")
            (src_dir / "module2.py").write_text("def func2(): pass")
            (src_dir / "module3.py").write_text("def func3(): pass")

            # Create test files
            tests_dir = project_root / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_module1.py").write_text("from src.module1 import func1")
            (tests_dir / "test_module2.py").write_text("from src.module2 import func2")
            # module3 has no test

            yield project_root

    @pytest.fixture
    def detector(self):
        """Create a CoverageDetector instance."""
        return CoverageDetector()

    def test_find_all_test_files_python(self, detector, temp_project):
        """Test finding all test files in a Python project."""
        test_files = detector._find_all_test_files("python", str(temp_project))

        assert isinstance(test_files, set)
        assert len(test_files) == 2
        # Check that paths are normalized
        assert all(os.path.isabs(f) for f in test_files)

    def test_find_all_test_files_empty_project(self, detector):
        """Test finding test files in empty project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_files = detector._find_all_test_files("python", tmpdir)
            assert isinstance(test_files, set)
            assert len(test_files) == 0

    def test_has_test_coverage_optimized_with_test(self, detector, temp_project):
        """Test optimized coverage check for file with test."""
        # Pre-compute test files
        test_files = detector._find_all_test_files("python", str(temp_project))

        # Check module1 (has test)
        module1_path = str(temp_project / "src" / "module1.py")
        has_coverage = detector._has_test_coverage_optimized(module1_path, "python", str(temp_project), test_files)

        assert has_coverage is True

    def test_has_test_coverage_optimized_without_test(self, detector, temp_project):
        """Test optimized coverage check for file without test."""
        # Pre-compute test files
        test_files = detector._find_all_test_files("python", str(temp_project))

        # Check module3 (no test)
        module3_path = str(temp_project / "src" / "module3.py")
        has_coverage = detector._has_test_coverage_optimized(module3_path, "python", str(temp_project), test_files)

        assert has_coverage is False

    def test_batch_coverage_sequential(self, detector, temp_project):
        """Test batch coverage detection in sequential mode."""
        file_paths = [
            str(temp_project / "src" / "module1.py"),
            str(temp_project / "src" / "module2.py"),
            str(temp_project / "src" / "module3.py"),
        ]

        coverage_map = detector.get_test_coverage_for_files_batch(file_paths, "python", str(temp_project), parallel=False)

        assert isinstance(coverage_map, dict)
        assert len(coverage_map) == 3
        assert coverage_map[file_paths[0]] is True  # module1 has test
        assert coverage_map[file_paths[1]] is True  # module2 has test
        assert coverage_map[file_paths[2]] is False  # module3 has no test

    def test_batch_coverage_parallel(self, detector, temp_project):
        """Test batch coverage detection in parallel mode."""
        file_paths = [
            str(temp_project / "src" / "module1.py"),
            str(temp_project / "src" / "module2.py"),
            str(temp_project / "src" / "module3.py"),
        ]

        coverage_map = detector.get_test_coverage_for_files_batch(file_paths, "python", str(temp_project), parallel=True, max_workers=2)

        assert isinstance(coverage_map, dict)
        assert len(coverage_map) == 3
        assert coverage_map[file_paths[0]] is True  # module1 has test
        assert coverage_map[file_paths[1]] is True  # module2 has test
        assert coverage_map[file_paths[2]] is False  # module3 has no test

    def test_batch_coverage_empty_list(self, detector):
        """Test batch coverage with empty file list."""
        coverage_map = detector.get_test_coverage_for_files_batch([], "python", "/tmp", parallel=True)

        assert coverage_map == {}

    def test_batch_coverage_error_handling(self, detector, temp_project):
        """Test error handling in batch coverage detection."""
        # Include a non-existent file
        file_paths = [
            str(temp_project / "src" / "module1.py"),
            str(temp_project / "src" / "nonexistent.py"),  # Doesn't exist
        ]

        # Should not raise, should handle gracefully
        coverage_map = detector.get_test_coverage_for_files_batch(file_paths, "python", str(temp_project), parallel=True)

        assert isinstance(coverage_map, dict)
        assert len(coverage_map) == 2
        # First file should have coverage
        assert coverage_map[file_paths[0]] is True
        # Non-existent file should have no coverage
        assert coverage_map[file_paths[1]] is False


class TestBatchVsSequentialEquivalence:
    """Tests verifying batch and sequential methods produce same results."""

    @pytest.fixture
    def detector(self):
        """Create a CoverageDetector instance."""
        return CoverageDetector()

    def test_batch_sequential_equivalence(self, detector):
        """Test that batch and sequential produce identical results."""
        # Use this project's own files for testing
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # Get some actual source files
        file_paths = [
            os.path.join(project_root, "src/ast_grep_mcp/core/config.py"),
            os.path.join(project_root, "src/ast_grep_mcp/core/cache.py"),
            os.path.join(project_root, "src/ast_grep_mcp/core/executor.py"),
        ]

        # Only test files that exist
        file_paths = [f for f in file_paths if os.path.exists(f)]

        if not file_paths:
            pytest.skip("No test files available")

        # Get results from legacy method
        legacy_map = detector.get_test_coverage_for_files(file_paths, "python", project_root)

        # Get results from batch method (sequential)
        batch_seq_map = detector.get_test_coverage_for_files_batch(file_paths, "python", project_root, parallel=False)

        # Get results from batch method (parallel)
        batch_par_map = detector.get_test_coverage_for_files_batch(file_paths, "python", project_root, parallel=True)

        # All methods should produce identical results
        assert legacy_map == batch_seq_map
        assert legacy_map == batch_par_map


class TestBatchCoverageIntegration:
    """Integration tests for batch coverage in orchestrator."""

    @pytest.fixture
    def mock_detector(self):
        """Create a mock CoverageDetector."""
        detector = Mock(spec=CoverageDetector)
        detector.get_test_coverage_for_files_batch = Mock(
            return_value={
                "/path/to/file1.py": True,
                "/path/to/file2.py": False,
                "/path/to/file3.py": True,
            }
        )
        return detector

    def test_orchestrator_uses_batch_method(self, mock_detector):
        """Test that orchestrator uses the batch method."""
        from ast_grep_mcp.features.deduplication.analysis_orchestrator import DeduplicationAnalysisOrchestrator

        orchestrator = DeduplicationAnalysisOrchestrator()
        orchestrator.coverage_detector = mock_detector

        candidates = [
            {"id": "dup1", "files": ["/path/to/file1.py", "/path/to/file2.py"], "similarity": 0.9},
            {
                "id": "dup2",
                "files": ["/path/to/file3.py"],
                "similarity": SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
            },
        ]

        orchestrator._add_test_coverage_batch(candidates, "python", "/path/to/project")

        # Verify batch method was called
        mock_detector.get_test_coverage_for_files_batch.assert_called_once()

        # Verify results were distributed to candidates
        assert candidates[0]["test_coverage"] == {"/path/to/file1.py": True, "/path/to/file2.py": False}
        assert candidates[0]["has_tests"] is True  # At least one file has tests

        assert candidates[1]["test_coverage"] == {"/path/to/file3.py": True}
        assert candidates[1]["has_tests"] is True

    def test_orchestrator_deduplicates_files(self, mock_detector):
        """Test that orchestrator deduplicates files before batch check."""
        from ast_grep_mcp.features.deduplication.analysis_orchestrator import DeduplicationAnalysisOrchestrator

        orchestrator = DeduplicationAnalysisOrchestrator()
        orchestrator.coverage_detector = mock_detector

        # Multiple candidates with overlapping files
        candidates = [
            {"files": ["/path/to/file1.py", "/path/to/file2.py"]},
            {"files": ["/path/to/file1.py", "/path/to/file3.py"]},  # file1 repeats
            {"files": ["/path/to/file2.py"]},  # file2 repeats
        ]

        orchestrator._add_test_coverage_batch(candidates, "python", "/path/to/project")

        # Get the actual call args
        call_args = mock_detector.get_test_coverage_for_files_batch.call_args

        # Should only check unique files
        file_list = call_args[0][0]
        assert len(file_list) == 3  # Only 3 unique files
        assert len(set(file_list)) == 3  # No duplicates


class TestBatchCoverageParallelTimeout:
    """Regression tests for BUG-06-CR-01: batch coverage parallel path must enforce timeout.

    Before the fix, _process_parallel_batch used `with ThreadPoolExecutor` (implicit
    shutdown(wait=True)) and as_completed() without a timeout, so a single hung
    _has_test_coverage_optimized call blocked the MCP call forever.
    """

    TIMEOUT_SECONDS = 1

    def test_hung_file_coverage_times_out_and_returns_false(self):
        """A hung per-file coverage check is marked False and the call returns promptly."""
        import threading
        import time

        detector = CoverageDetector()
        release = threading.Event()

        hung_path = "/virtual/hung_file.py"
        fast_path = "/virtual/fast_file.py"
        test_files: set = set()

        original_fn = detector._has_test_coverage_optimized

        def patched_coverage(file_path, language, project_root, test_files_arg):
            if file_path == hung_path:
                release.wait(timeout=60)
                return False
            return original_fn(file_path, language, project_root, test_files_arg)

        detector._has_test_coverage_optimized = patched_coverage  # type: ignore[method-assign]

        try:
            start = time.monotonic()
            coverage_map, covered_count = detector._process_parallel_batch(
                file_paths=[hung_path, fast_path],
                language="python",
                project_root="/virtual",
                test_files=test_files,
                max_workers=2,
                timeout_per_file=self.TIMEOUT_SECONDS,
            )
            elapsed = time.monotonic() - start
        finally:
            release.set()

        assert elapsed < 10, f"call should return promptly, took {elapsed:.1f}s"
        assert hung_path in coverage_map
        assert coverage_map[hung_path] is False  # timed out → False
        assert fast_path in coverage_map

    def test_timeout_threaded_through_get_test_coverage_for_files_batch(self):
        """timeout_per_file parameter reaches _process_parallel_batch."""
        import threading
        import time

        detector = CoverageDetector()
        release = threading.Event()

        hung_path = "/virtual/hung.py"
        fast_path = "/virtual/fast.py"

        original_fn = detector._has_test_coverage_optimized

        def patched_coverage(file_path, language, project_root, test_files_arg):
            if file_path == hung_path:
                release.wait(timeout=60)
                return False
            return original_fn(file_path, language, project_root, test_files_arg)

        detector._has_test_coverage_optimized = patched_coverage  # type: ignore[method-assign]
        detector._find_all_test_files = lambda lang, root: set()  # type: ignore[method-assign]

        try:
            start = time.monotonic()
            coverage_map = detector.get_test_coverage_for_files_batch(
                file_paths=[hung_path, fast_path],
                language="python",
                project_root="/virtual",
                parallel=True,
                max_workers=2,
                timeout_per_file=self.TIMEOUT_SECONDS,
            )
            elapsed = time.monotonic() - start
        finally:
            release.set()

        assert elapsed < 10, f"call should return promptly, took {elapsed:.1f}s"
        assert coverage_map[hung_path] is False
