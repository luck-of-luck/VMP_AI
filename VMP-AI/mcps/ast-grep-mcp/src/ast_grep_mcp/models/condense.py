"""Data models for code condensation feature."""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class LanguageCondenseStats:
    """Per-language statistics from condensation."""

    language: str
    files_processed: int
    original_lines: int
    condensed_lines: int
    patterns_matched: int
    original_bytes: int = 0
    condensed_bytes: int = 0


@dataclass
class CondenseResult:
    """Result of running the condense pipeline on a path."""

    strategy: str
    files_processed: int
    files_skipped: int
    original_bytes: int
    condensed_bytes: int
    reduction_pct: float
    original_tokens_est: int
    condensed_tokens_est: int
    normalizations_applied: int
    dead_code_removed_lines: int
    duplicates_collapsed: int
    per_language_stats: Dict[str, LanguageCondenseStats] = field(default_factory=dict)
