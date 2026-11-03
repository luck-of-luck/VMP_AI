"""
Code complexity analysis feature.

This module provides comprehensive code complexity analysis including:
- Cyclomatic complexity calculation
- Cognitive complexity calculation
- Nesting depth analysis
- Function length analysis
- Historical trend tracking
- SQLite-based storage for metrics
"""

from .analyzer import (
    analyze_file_complexity,
    extract_functions_from_file,
)
from .metrics import (
    COMPLEXITY_PATTERNS,
    calculate_cognitive_complexity,
    calculate_cyclomatic_complexity,
    calculate_nesting_depth,
    count_pattern_matches,
    get_complexity_patterns,
)
from .storage import ComplexityStorage
from .tools import register_complexity_tools

__all__ = [
    # Metrics
    "COMPLEXITY_PATTERNS",
    "calculate_cognitive_complexity",
    "calculate_cyclomatic_complexity",
    "calculate_nesting_depth",
    "count_pattern_matches",
    "get_complexity_patterns",
    # Analyzer
    "analyze_file_complexity",
    "extract_functions_from_file",
    # Storage
    "ComplexityStorage",
    # Tools
    "register_complexity_tools",
]
