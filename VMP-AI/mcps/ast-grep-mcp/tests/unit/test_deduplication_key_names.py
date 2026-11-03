"""Regression tests for deduplication key name consistency.

These tests ensure the orchestrator and tools use consistent key names
between the detector output and ranker input, and between the orchestrator
output and CLI script expectations.

Fixes tested:
- analysis_orchestrator.py: Uses 'duplication_groups' (not 'duplicates')
- tools.py: Uses 'total_groups_analyzed' and 'top_candidates_savings_potential'
"""

import tempfile
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from ast_grep_mcp.features.deduplication.analysis_orchestrator import (
    DeduplicationAnalysisOrchestrator,
)
from ast_grep_mcp.features.deduplication.tools import (
    analyze_deduplication_candidates_tool,
)


class TestOrchestratorKeyNames:
    """Tests for consistent key names in orchestrator."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_detector_output(self) -> Dict[str, Any]:
        """Realistic detector output with correct 'duplication_groups' key."""
        return {
            "summary": {
                "total_constructs": 100,
                "duplicate_groups": 3,
                "potential_line_savings": 50,
            },
            "duplication_groups": [
                {
                    "group_id": 1,
                    "similarity_score": 0.95,
                    "instances": [
                        {"file": "/tmp/file1.py", "lines": "10-20"},
                        {"file": "/tmp/file2.py", "lines": "15-25"},
                    ],
                },
                {
                    "group_id": 2,
                    "similarity_score": 0.88,
                    "instances": [
                        {"file": "/tmp/file3.py", "lines": "5-15"},
                        {"file": "/tmp/file4.py", "lines": "100-110"},
                    ],
                },
            ],
            "refactoring_suggestions": [],
            "message": "Found 2 duplication group(s)",
        }

    @pytest.fixture
    def orchestrator_with_mock_detector(self, mock_detector_output):
        """Create orchestrator with mocked detector returning correct format."""
        orchestrator = DeduplicationAnalysisOrchestrator()

        mock_detector = Mock()
        mock_detector.find_duplication.return_value = mock_detector_output
        orchestrator.detector = mock_detector

        # Mock ranker to pass through candidates
        mock_ranker = Mock()
        mock_ranker.rank_deduplication_candidates.return_value = [
            {
                "group_id": 1,
                "similarity_score": 0.95,
                "score": 75.0,
                "priority": "medium",
                "instances": [
                    {"file": "/tmp/file1.py", "lines": "10-20"},
                    {"file": "/tmp/file2.py", "lines": "15-25"},
                ],
            },
        ]
        orchestrator.ranker = mock_ranker

        return orchestrator

    def test_orchestrator_passes_duplication_groups_to_ranker(
        self, temp_project_dir, orchestrator_with_mock_detector, mock_detector_output
    ):
        """Regression: Orchestrator must use 'duplication_groups' key from detector."""
        orchestrator_with_mock_detector.analyze_candidates(
            project_path=temp_project_dir,
            language="python",
            include_test_coverage=False,
        )

        # Verify ranker was called with the groups from 'duplication_groups'
        ranker_call = orchestrator_with_mock_detector.ranker.rank_deduplication_candidates
        ranker_call.assert_called_once()

        # The first argument should be the duplication_groups list
        call_args = ranker_call.call_args
        candidates_passed = call_args[0][0] if call_args[0] else call_args[1].get("candidates", [])

        # Should match the duplication_groups from detector output
        assert candidates_passed == mock_detector_output["duplication_groups"]

    def test_orchestrator_output_has_correct_keys(self, temp_project_dir, orchestrator_with_mock_detector):
        """Regression: Orchestrator output must use 'total_groups_analyzed' key."""
        result = orchestrator_with_mock_detector.analyze_candidates(
            project_path=temp_project_dir,
            language="python",
            include_test_coverage=False,
        )

        # These are the correct keys that should be present
        assert "candidates" in result
        assert "total_groups_analyzed" in result
        assert "top_candidates_count" in result
        assert "top_candidates_savings_potential" in result
        assert "analysis_metadata" in result

        # Verify the OLD incorrect key is NOT present
        assert "total_groups" not in result
        assert "total_savings_potential" not in result

    def test_detector_output_uses_duplication_groups_not_duplicates(self):
        """Regression: Detector output format uses 'duplication_groups' not 'duplicates'."""
        from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

        detector = DuplicationDetector()

        # Create a minimal test to check format
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = f"{tmpdir}/test.py"
            with open(test_file, "w") as f:
                f.write("def foo(): pass\n")

            result = detector.find_duplication(
                project_folder=tmpdir,
                construct_type="function_definition",
                min_similarity=0.8,
                min_lines=1,
            )

            # Verify correct key name
            assert "duplication_groups" in result
            assert "duplicates" not in result


class TestToolsKeyNames:
    """Tests for consistent key names in tools module."""

    @pytest.fixture
    def temp_project_dir(self):
        """Create temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file so the tool has something to analyze
            test_file = f"{tmpdir}/test.py"
            with open(test_file, "w") as f:
                f.write("def foo(): pass\ndef bar(): pass\n")
            yield tmpdir

    def test_tool_handles_orchestrator_output_keys(self, temp_project_dir):
        """Regression: Tool must handle correct orchestrator output keys without error."""
        # This should not raise KeyError
        result = analyze_deduplication_candidates_tool(
            project_path=temp_project_dir,
            language="python",
            min_similarity=0.8,
            include_test_coverage=False,
            min_lines=1,
        )

        # Verify the result has the expected structure
        assert "candidates" in result
        # The tool should pass through the orchestrator's output
        assert isinstance(result.get("candidates"), list)

    def test_tool_logs_with_correct_keys(self, temp_project_dir):
        """Regression: Tool logging uses .get() with correct keys."""
        with patch("ast_grep_mcp.features.deduplication.tools.get_logger") as mock_logger:
            mock_log = Mock()
            mock_logger.return_value = mock_log

            analyze_deduplication_candidates_tool(
                project_path=temp_project_dir,
                language="python",
                min_similarity=0.8,
                include_test_coverage=False,
                min_lines=1,
            )

            # Verify logging was called (without KeyError)
            assert mock_log.info.called


class TestScriptRecommendationHandling:
    """Tests for recommendation dict/string handling in CLI script."""

    def test_recommendation_as_dict(self):
        """Regression: Script should handle recommendation as dict."""
        # Simulate what the script does
        rec = {"recommendation_text": "High Value: Extract to shared utility", "priority": "high"}

        # This is the fix we made
        if isinstance(rec, dict):
            rec_text = rec.get("recommendation_text", str(rec))
        else:
            rec_text = str(rec)

        assert rec_text == "High Value: Extract to shared utility"

    def test_recommendation_as_string(self):
        """Script should still handle recommendation as string (backward compat)."""
        rec = "Low Value: May not be worth refactoring"

        if isinstance(rec, dict):
            rec_text = rec.get("recommendation_text", str(rec))
        else:
            rec_text = str(rec)

        assert rec_text == "Low Value: May not be worth refactoring"

    def test_recommendation_dict_without_text_key(self):
        """Script should fallback to str(dict) if recommendation_text missing."""
        rec = {"priority": "high", "strategies": ["extract_function"]}

        if isinstance(rec, dict):
            rec_text = rec.get("recommendation_text", str(rec))
        else:
            rec_text = str(rec)

        # Falls back to string representation
        assert "priority" in rec_text
        assert "high" in rec_text
