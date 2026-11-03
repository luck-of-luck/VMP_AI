"""Shared score scales for deduplication and top-N preview limits."""

from enum import IntEnum


class VariationScoreScale(IntEnum):
    """Discrete variation complexity score levels used in pattern analysis."""

    SCORE_3 = 3
    SCORE_4 = 4
    SCORE_5 = 5
    SCORE_6 = 6
    SCORE_7 = 7


class VariationScoreCutoff(IntEnum):
    """Cutoff thresholds for mapping variation scores to complexity labels."""

    MODERATE_MAX = VariationScoreScale.SCORE_4


class SimilarityDiscreteBand(IntEnum):
    """Discrete structural line-count bands for similarity bucketing."""

    BAND_3 = VariationScoreScale.SCORE_3
    BAND_4 = VariationScoreScale.SCORE_4
    BAND_5 = VariationScoreScale.SCORE_5
    BAND_6 = VariationScoreScale.SCORE_6


class SharedTopN(IntEnum):
    """Shared top-N list sizing values used across reporting and scripts."""

    SMALL = 3
    FOCUSED = 4
    STANDARD = 5
    PREVIEW = 10
    EXTENDED_PREVIEW = 15


class AnalyzeCodebaseTopN(IntEnum):
    """Top-N limits for analyze_codebase reporting."""

    TOP_FILES = SharedTopN.STANDARD
    WORST_OFFENDERS = SharedTopN.SMALL
    TOP_COMPLEX_FUNCTIONS = SharedTopN.PREVIEW
    TOP_SMELLS_PREVIEW = SharedTopN.PREVIEW
    TOP_SECURITY_ISSUES_PREVIEW = SharedTopN.PREVIEW
    DUPLICATION_LOCATION_PREVIEW = SharedTopN.SMALL


class PatternEquivalenceTopN(IntEnum):
    """Top-N limits for cross-language pattern equivalence suggestions."""

    CATEGORY_RELATED_SUGGESTION = SharedTopN.SMALL
    CATEGORY_DISCOVERY = SharedTopN.FOCUSED
    MIN_PATTERNS_FOR_CATEGORY_HINT = SharedTopN.SMALL
    MAX_SUGGESTIONS = SharedTopN.STANDARD


class AnalyticsBotTopN(IntEnum):
    """Top-N limits for scripts/analyze_analyticsbot.py."""

    TOP_COMPLEX_FUNCTIONS_PREVIEW = SharedTopN.SMALL
    TOP_SECURITY_TYPES_PREVIEW = SharedTopN.STANDARD


class PrintMigrationTopN(IntEnum):
    """Top-N limits for scripts/migrate_prints_smart.py."""

    MIGRATION_CHANGES_SUMMARY = SharedTopN.PREVIEW
    CLI_FILE_CHANGES_PREVIEW = SharedTopN.EXTENDED_PREVIEW
    TOP_MODIFIED_FILES = SharedTopN.STANDARD
    PER_FILE_CHANGES_PREVIEW = SharedTopN.SMALL
