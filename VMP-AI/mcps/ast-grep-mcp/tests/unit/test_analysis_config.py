"""Tests for AnalysisConfig dataclass.

This test suite validates the configuration object pattern implementation
for deduplication analysis, ensuring proper validation, defaults, and
serialization.
"""

import pytest

from src.ast_grep_mcp.features.deduplication.config import AnalysisConfig


class TestAnalysisConfigCreation:
    """Test AnalysisConfig creation and initialization."""

    def test_minimal_config(self):
        """Should create config with only required fields."""
        config = AnalysisConfig(project_path="/path/to/project", language="python")

        assert config.project_path == "/path/to/project"
        assert config.language == "python"
        assert config.min_similarity == 0.8  # Default
        assert config.include_test_coverage is True  # Default
        assert config.min_lines == 5  # Default
        assert config.max_candidates == 100  # Default
        assert config.exclude_patterns == []  # Normalized from None
        assert config.parallel is True  # Default
        assert config.max_workers == 4  # Default
        assert config.progress_callback is None  # Default

    def test_full_config(self):
        """Should create config with all fields specified."""

        def callback(stage, pct):
            pass

        config = AnalysisConfig(
            project_path="/custom/path",
            language="typescript",
            min_similarity=0.9,
            include_test_coverage=False,
            min_lines=10,
            max_candidates=50,
            exclude_patterns=["*.test.ts", "*.spec.ts"],
            parallel=False,
            max_workers=8,
            progress_callback=callback,
        )

        assert config.project_path == "/custom/path"
        assert config.language == "typescript"
        assert config.min_similarity == 0.9
        assert config.include_test_coverage is False
        assert config.min_lines == 10
        assert config.max_candidates == 50
        assert config.exclude_patterns == ["*.test.ts", "*.spec.ts"]
        assert config.parallel is False
        assert config.max_workers == 8
        assert config.progress_callback is callback


class TestAnalysisConfigValidation:
    """Test AnalysisConfig validation in __post_init__."""

    def test_invalid_min_similarity_too_low(self):
        """Should raise ValueError for min_similarity < 0.0."""
        with pytest.raises(ValueError, match="min_similarity must be between 0.0 and 1.0"):
            AnalysisConfig(project_path="/path", language="python", min_similarity=-0.1)

    def test_invalid_min_similarity_too_high(self):
        """Should raise ValueError for min_similarity > 1.0."""
        with pytest.raises(ValueError, match="min_similarity must be between 0.0 and 1.0"):
            AnalysisConfig(project_path="/path", language="python", min_similarity=1.1)

    def test_valid_min_similarity_boundaries(self):
        """Should accept min_similarity at boundaries (0.0, 1.0)."""
        config_zero = AnalysisConfig(project_path="/path", language="python", min_similarity=0.0)
        assert config_zero.min_similarity == 0.0

        config_one = AnalysisConfig(project_path="/path", language="python", min_similarity=1.0)
        assert config_one.min_similarity == 1.0

    def test_invalid_min_lines_zero(self):
        """Should raise ValueError for min_lines = 0."""
        with pytest.raises(ValueError, match="min_lines must be a positive integer"):
            AnalysisConfig(project_path="/path", language="python", min_lines=0)

    def test_invalid_min_lines_negative(self):
        """Should raise ValueError for min_lines < 0."""
        with pytest.raises(ValueError, match="min_lines must be a positive integer"):
            AnalysisConfig(project_path="/path", language="python", min_lines=-5)

    def test_invalid_max_candidates_zero(self):
        """Should raise ValueError for max_candidates = 0."""
        with pytest.raises(ValueError, match="max_candidates must be a positive integer"):
            AnalysisConfig(project_path="/path", language="python", max_candidates=0)

    def test_invalid_max_candidates_negative(self):
        """Should raise ValueError for max_candidates < 0."""
        with pytest.raises(ValueError, match="max_candidates must be a positive integer"):
            AnalysisConfig(project_path="/path", language="python", max_candidates=-10)

    def test_invalid_max_workers_zero(self):
        """Should raise ValueError for max_workers = 0."""
        with pytest.raises(ValueError, match="max_workers must be positive"):
            AnalysisConfig(project_path="/path", language="python", max_workers=0)

    def test_invalid_max_workers_negative(self):
        """Should raise ValueError for max_workers < 0."""
        with pytest.raises(ValueError, match="max_workers must be positive"):
            AnalysisConfig(project_path="/path", language="python", max_workers=-4)


class TestAnalysisConfigNormalization:
    """Test AnalysisConfig normalization in __post_init__."""

    def test_exclude_patterns_none_normalized_to_empty_list(self):
        """Should normalize None exclude_patterns to empty list."""
        config = AnalysisConfig(project_path="/path", language="python", exclude_patterns=None)
        assert config.exclude_patterns == []
        assert isinstance(config.exclude_patterns, list)

    def test_exclude_patterns_empty_list_preserved(self):
        """Should preserve empty list for exclude_patterns."""
        config = AnalysisConfig(project_path="/path", language="python", exclude_patterns=[])
        assert config.exclude_patterns == []

    def test_exclude_patterns_with_values_preserved(self):
        """Should preserve exclude_patterns with values."""
        patterns = ["*.test.py", "node_modules/**"]
        config = AnalysisConfig(project_path="/path", language="python", exclude_patterns=patterns)
        assert config.exclude_patterns == patterns


class TestAnalysisConfigSerialization:
    """Test AnalysisConfig to_dict() serialization."""

    def test_to_dict_minimal_config(self):
        """Should serialize minimal config to dict."""
        config = AnalysisConfig(project_path="/path/to/project", language="python")

        result = config.to_dict()

        assert result == {
            "project_path": "/path/to/project",
            "language": "python",
            "min_similarity": 0.8,
            "include_test_coverage": True,
            "min_lines": 5,
            "max_candidates": 100,
            "exclude_patterns": [],
            "parallel": True,
            "max_workers": 4,
            "timeout_per_candidate": None,
            "has_progress_callback": False,
        }

    def test_to_dict_full_config(self):
        """Should serialize full config to dict."""

        def callback(stage, pct):
            pass

        config = AnalysisConfig(
            project_path="/custom/path",
            language="typescript",
            min_similarity=0.9,
            include_test_coverage=False,
            min_lines=10,
            max_candidates=50,
            exclude_patterns=["*.test.ts"],
            parallel=False,
            max_workers=8,
            timeout_per_candidate=60,
            progress_callback=callback,
        )

        result = config.to_dict()

        assert result == {
            "project_path": "/custom/path",
            "language": "typescript",
            "min_similarity": 0.9,
            "include_test_coverage": False,
            "min_lines": 10,
            "max_candidates": 50,
            "exclude_patterns": ["*.test.ts"],
            "parallel": False,
            "max_workers": 8,
            "timeout_per_candidate": 60,
            "has_progress_callback": True,  # Callback present but not serialized
        }

    def test_to_dict_excludes_callback_function(self):
        """Should not include progress_callback function in dict."""

        def callback(stage, pct):
            pass

        config = AnalysisConfig(project_path="/path", language="python", progress_callback=callback)

        result = config.to_dict()

        # Should have has_progress_callback flag but not the function itself
        assert "has_progress_callback" in result
        assert result["has_progress_callback"] is True
        assert "progress_callback" not in result


class TestAnalysisConfigEdgeCases:
    """Test AnalysisConfig edge cases and boundary conditions."""

    def test_very_high_max_candidates(self):
        """Should accept very high max_candidates value."""
        config = AnalysisConfig(project_path="/path", language="python", max_candidates=1000000)
        assert config.max_candidates == 1000000

    def test_very_high_max_workers(self):
        """Should accept very high max_workers value."""
        config = AnalysisConfig(project_path="/path", language="python", max_workers=128)
        assert config.max_workers == 128

    def test_many_exclude_patterns(self):
        """Should handle many exclude patterns."""
        patterns = [f"pattern_{i}" for i in range(100)]
        config = AnalysisConfig(project_path="/path", language="python", exclude_patterns=patterns)
        assert len(config.exclude_patterns) == 100
        assert config.exclude_patterns == patterns

    def test_unicode_in_project_path(self):
        """Should handle unicode characters in project path."""
        config = AnalysisConfig(project_path="/path/to/プロジェクト", language="python")
        assert config.project_path == "/path/to/プロジェクト"

    def test_unicode_in_language(self):
        """Should handle unicode characters in language."""
        config = AnalysisConfig(project_path="/path", language="日本語")
        assert config.language == "日本語"


class TestAnalysisConfigCallbackIntegration:
    """Test AnalysisConfig integration with progress callbacks."""

    def test_callback_invocation_tracking(self):
        """Should track callback invocations properly."""
        invocations = []

        def callback(stage, pct):
            invocations.append((stage, pct))

        config = AnalysisConfig(project_path="/path", language="python", progress_callback=callback)

        # Simulate progress reporting
        config.progress_callback("step1", 0.25)
        config.progress_callback("step2", 0.50)
        config.progress_callback("step3", 1.0)

        assert len(invocations) == 3
        assert invocations[0] == ("step1", 0.25)
        assert invocations[1] == ("step2", 0.50)
        assert invocations[2] == ("step3", 1.0)

    def test_no_callback_none_check(self):
        """Should handle None callback gracefully."""
        config = AnalysisConfig(project_path="/path", language="python", progress_callback=None)

        # Should not raise when callback is None
        if config.progress_callback:
            config.progress_callback("test", 0.5)  # Should never execute

        assert config.progress_callback is None
