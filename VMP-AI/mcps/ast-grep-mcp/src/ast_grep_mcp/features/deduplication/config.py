"""Configuration dataclasses for deduplication analysis.

This module provides strongly-typed configuration objects that replace
excessive parameter passing throughout the deduplication workflow.
"""

from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from ...constants import DeduplicationDefaults, ParallelProcessing


def _require_positive(value: int, name: str) -> None:
    if value < 1:
        raise ValueError(f"{name} must be a positive integer, got {value}")


def _require_positive_workers(value: int) -> None:
    if value < 1:
        raise ValueError(f"max_workers must be positive, got {value}")


@dataclass
class AnalysisConfig:
    """Configuration for deduplication candidate analysis.

    This config object consolidates all analysis parameters into a single
    strongly-typed structure, replacing methods with 6-8 parameters.

    Examples:
        >>> # Simple usage
        >>> config = AnalysisConfig(
        ...     project_path="/path/to/project",
        ...     language="python"
        ... )

        >>> # With custom thresholds
        >>> config = AnalysisConfig(
        ...     project_path="/path/to/project",
        ...     language="python",
        ...     min_similarity=0.9,
        ...     max_candidates=50,
        ...     include_test_coverage=False
        ... )

        >>> # With progress tracking
        >>> def show_progress(stage, percent):
        ...     print(f"[{percent*100:.0f}%] {stage}")
        >>>
        >>> config = AnalysisConfig(
        ...     project_path="/path/to/project",
        ...     language="python",
        ...     progress_callback=show_progress
        ... )

    Attributes:
        project_path: Project folder path to analyze
        language: Programming language (python, javascript, typescript, etc.)
        min_similarity: Minimum similarity threshold (0.0-1.0). Default: 0.8
        include_test_coverage: Whether to check test coverage. Default: True
        min_lines: Minimum lines to consider for duplication. Default: 5
        max_candidates: Maximum candidates to return. Default: 100
        exclude_patterns: Path patterns to exclude from analysis. Default: None
        parallel: Enable parallel execution for enrichment. Default: True
        max_workers: Maximum worker threads for parallel execution. Default: 4
        timeout_per_candidate: Per-candidate enrichment timeout in seconds
            (float). None uses the default (30s). Raise this if legitimate
            enrichment operations are spuriously marked timed-out. Default: None
        progress_callback: Optional callback for progress reporting.
            Signature: (stage_name: str, progress_percent: float) -> None
    """

    # Required fields
    project_path: str
    language: str

    # Analysis thresholds with defaults
    min_similarity: float = DeduplicationDefaults.MIN_SIMILARITY
    include_test_coverage: bool = True
    min_lines: int = DeduplicationDefaults.MIN_LINES
    max_candidates: int = DeduplicationDefaults.MAX_CANDIDATES

    # Optional fields
    exclude_patterns: Optional[List[str]] = None

    # Parallel execution settings
    parallel: bool = True
    max_workers: int = ParallelProcessing.DEFAULT_WORKERS
    timeout_per_candidate: Optional[float] = None

    # Progress tracking
    progress_callback: Optional[Callable[[str, float], None]] = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization.

        Raises:
            ValueError: If any configuration value is invalid
        """
        if self.exclude_patterns is None:
            self.exclude_patterns = []

        if not 0.0 <= self.min_similarity <= 1.0:
            raise ValueError(f"min_similarity must be between 0.0 and 1.0, got {self.min_similarity}")

        _require_positive(self.min_lines, "min_lines")
        _require_positive(self.max_candidates, "max_candidates")
        _require_positive_workers(self.max_workers)

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for logging/serialization.

        Returns:
            Dictionary representation (excludes progress_callback)
        """
        return {
            "project_path": self.project_path,
            "language": self.language,
            "min_similarity": self.min_similarity,
            "include_test_coverage": self.include_test_coverage,
            "min_lines": self.min_lines,
            "max_candidates": self.max_candidates,
            "exclude_patterns": self.exclude_patterns,
            "parallel": self.parallel,
            "max_workers": self.max_workers,
            "timeout_per_candidate": self.timeout_per_candidate,
            "has_progress_callback": self.progress_callback is not None,
        }
