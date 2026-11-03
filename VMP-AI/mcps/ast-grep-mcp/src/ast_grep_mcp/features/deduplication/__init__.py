"""
Deduplication feature module.

This module provides comprehensive code deduplication detection and refactoring
capabilities for the ast-grep MCP server.
"""

# Core detection and analysis
from ...models.deduplication import VariationCategory, VariationSeverity
from .analyzer import PatternAnalyzer
from .applicator import DeduplicationApplicator
from .benchmark import DeduplicationBenchmark
from .coverage import CoverageDetector
from .detector import DuplicationDetector
from .diff import (
    build_diff_tree,
    build_nested_diff_tree,
    diff_preview_to_dict,
    format_alignment_diff,
    generate_diff_from_file_paths,
    generate_file_diff,
    generate_multi_file_diff,
)
from .generator import CodeGenerator
from .impact import ImpactAnalyzer
from .ranker import (
    DeduplicationPriorityClassifier,
    DeduplicationScoreCalculator,
    DuplicationRanker,
)
from .recommendations import RecommendationEngine, generate_refactoring_suggestions
from .reporting import DuplicationReporter, EnhancedDuplicationCandidate
from .scoring_scales import SimilarityDiscreteBand, VariationScoreCutoff, VariationScoreScale

# Similarity calculation
from .similarity import (
    HybridSimilarity,
    HybridSimilarityConfig,
    HybridSimilarityResult,
    MinHashSimilarity,
    SimilarityConfig,
    SimilarityResult,
)

# MCP tool registration
from .tools import register_deduplication_tools

__all__ = [
    # Core classes
    "DuplicationDetector",
    "PatternAnalyzer",
    "CodeGenerator",
    "DuplicationRanker",
    "DeduplicationScoreCalculator",
    "DeduplicationPriorityClassifier",
    # Similarity
    "HybridSimilarity",
    "HybridSimilarityConfig",
    "HybridSimilarityResult",
    "MinHashSimilarity",
    "SimilarityConfig",
    "SimilarityResult",
    # Supporting classes
    "CoverageDetector",
    "ImpactAnalyzer",
    "RecommendationEngine",
    "DeduplicationApplicator",
    "DuplicationReporter",
    "DeduplicationBenchmark",
    "EnhancedDuplicationCandidate",
    # Enums/Constants
    "VariationCategory",
    "VariationSeverity",
    "VariationScoreScale",
    "VariationScoreCutoff",
    "SimilarityDiscreteBand",
    # Standalone functions
    "generate_refactoring_suggestions",
    # Diff utilities
    "build_diff_tree",
    "build_nested_diff_tree",
    "diff_preview_to_dict",
    "format_alignment_diff",
    "generate_diff_from_file_paths",
    "generate_file_diff",
    "generate_multi_file_diff",
    # Registration
    "register_deduplication_tools",
]
