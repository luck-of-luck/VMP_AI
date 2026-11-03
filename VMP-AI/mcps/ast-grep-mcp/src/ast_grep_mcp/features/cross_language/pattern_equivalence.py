"""Pattern equivalence lookup implementation.

This module provides functionality to find equivalent patterns
across programming languages.
"""

import time
from typing import Any, Dict, List, Optional

from ast_grep_mcp.constants import ConversionFactors, EquivalenceDefaults
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.features.cross_language.pattern_database import (
    PATTERN_CATEGORIES,
    PATTERN_DATABASE,
)
from ast_grep_mcp.features.deduplication.scoring_scales import PatternEquivalenceTopN
from ast_grep_mcp.models.cross_language import (
    SUPPORTED_LANGUAGES,
    PatternEquivalence,
    PatternEquivalenceResult,
    PatternExample,
)
from ast_grep_mcp.utils.slicing import take_top_n

logger = get_logger(__name__)


def _example_from_data(lang: str, ex_data: Any) -> Optional[PatternExample]:
    if isinstance(ex_data, dict):
        return PatternExample(
            language=lang,
            code=ex_data.get("code", ""),
            description=ex_data.get("description", ""),
            notes=ex_data.get("notes", []),
        )
    if isinstance(ex_data, str):
        return PatternExample(language=lang, code=ex_data, description="", notes=[])
    return None


def _build_examples(
    pattern_data: Dict[str, Any],
    target_languages: Optional[List[str]],
) -> List[PatternExample]:
    examples = []
    for lang, ex_data in pattern_data.get("examples", {}).items():
        if target_languages and lang not in target_languages:
            continue
        ex = _example_from_data(lang, ex_data)
        if ex is not None:
            examples.append(ex)
    return examples


def _complexity_label(lines: int) -> str:
    if lines <= EquivalenceDefaults.SIMPLE_LINE_THRESHOLD:
        return "simple"
    if lines <= EquivalenceDefaults.MODERATE_LINE_THRESHOLD:
        return "moderate"
    return "complex"


def _build_complexity_comparison(examples: List[PatternExample]) -> Dict[str, str]:
    return {ex.language: _complexity_label(len(ex.code.strip().split("\n"))) for ex in examples}


def _create_pattern_equivalence(
    pattern_id: str,
    pattern_data: Dict[str, Any],
    target_languages: Optional[List[str]] = None,
) -> PatternEquivalence:
    """Create a PatternEquivalence from database entry.

    Args:
        pattern_id: Pattern identifier
        pattern_data: Pattern data from database
        target_languages: Optional filter for target languages

    Returns:
        PatternEquivalence object
    """
    examples = _build_examples(pattern_data, target_languages)
    return PatternEquivalence(
        pattern_id=pattern_id,
        concept=pattern_data.get("concept", ""),
        category=pattern_data.get("category", ""),
        description=pattern_data.get("description", ""),
        examples=examples,
        related_patterns=pattern_data.get("related_patterns", []),
        complexity_comparison=_build_complexity_comparison(examples),
    )


def _direct_match_patterns(query_lower: str) -> List[str]:
    matches = []
    for pattern_id, pattern_data in PATTERN_DATABASE.items():
        concept = pattern_data.get("concept", "").lower()
        description = pattern_data.get("description", "").lower()
        if query_lower in concept or query_lower in description or query_lower in pattern_id.lower():
            matches.append(pattern_id)
    return matches


def _word_match_patterns(query_lower: str) -> List[str]:
    matches = []
    query_words = query_lower.split()
    for pattern_id, pattern_data in PATTERN_DATABASE.items():
        concept = pattern_data.get("concept", "").lower()
        description = pattern_data.get("description", "").lower()
        searchable = f"{concept} {description} {pattern_id}".lower()
        if any(len(w) > 2 and w in searchable for w in query_words):
            matches.append(pattern_id)
    return matches


def _fuzzy_match_pattern(query: str) -> List[str]:
    """Find pattern IDs that match a fuzzy query.

    Args:
        query: Search query

    Returns:
        List of matching pattern IDs
    """
    query_lower = query.lower()
    matches = _direct_match_patterns(query_lower)
    if not matches:
        matches = _word_match_patterns(query_lower)
    return list(set(matches))


def _related_suggestions(found_patterns: List[str]) -> List[str]:
    related: set[str] = set()
    for pattern_id in found_patterns:
        related.update(PATTERN_DATABASE.get(pattern_id, {}).get("related_patterns", []))
    return [
        f"Related: {rel_id} - {PATTERN_DATABASE[rel_id].get('concept', '')}"
        for rel_id in related
        if rel_id not in found_patterns and rel_id in PATTERN_DATABASE
    ]


def _category_suggestions(found_patterns: List[str], category: Optional[str]) -> List[str]:
    suggestions = []
    if category:
        others = [pid for pid, p in PATTERN_DATABASE.items() if p.get("category") == category and pid not in found_patterns]
        preview = take_top_n(others, PatternEquivalenceTopN.CATEGORY_RELATED_SUGGESTION)
        if preview:
            suggestions.append(f"More in '{category}': {', '.join(preview)}")
    elif len(found_patterns) < PatternEquivalenceTopN.MIN_PATTERNS_FOR_CATEGORY_HINT:
        preview = take_top_n(PATTERN_CATEGORIES, PatternEquivalenceTopN.CATEGORY_DISCOVERY)
        suggestions.append(f"Try searching by category: {', '.join(preview)}")
    return suggestions


def _get_suggestions(
    found_patterns: List[str],
    category: Optional[str] = None,
) -> List[str]:
    """Get pattern suggestions based on found patterns.

    Args:
        found_patterns: List of found pattern IDs
        category: Optional category filter

    Returns:
        List of suggestion strings
    """
    suggestions = _related_suggestions(found_patterns) + _category_suggestions(found_patterns, category)
    return take_top_n(suggestions, PatternEquivalenceTopN.MAX_SUGGESTIONS)


_DEFAULT_TARGET_LANGUAGES = ["python", "typescript", "javascript", "java", "go", "rust"]


def _resolve_target_languages(target_languages: Optional[List[str]]) -> List[str]:
    langs = target_languages or _DEFAULT_TARGET_LANGUAGES
    return [lang for lang in langs if lang in SUPPORTED_LANGUAGES]


def _build_equivalences(
    pattern_ids: List[str],
    target_languages: List[str],
) -> List[PatternEquivalence]:
    equivalences = []
    for pattern_id in pattern_ids:
        pattern_data = PATTERN_DATABASE.get(pattern_id)
        if pattern_data:
            equivalences.append(_create_pattern_equivalence(pattern_id, pattern_data, target_languages))
    return equivalences


def find_language_equivalents_impl(
    pattern_description: str,
    source_language: Optional[str] = None,
    target_languages: Optional[List[str]] = None,
) -> PatternEquivalenceResult:
    """Find equivalent patterns across languages.

    Args:
        pattern_description: Description of the pattern to find
        source_language: Optional source language to highlight
        target_languages: List of target languages to include

    Returns:
        PatternEquivalenceResult with found equivalences
    """
    start_time = time.time()

    if source_language and source_language not in SUPPORTED_LANGUAGES:
        logger.warning(
            "unsupported_source_language",
            language=source_language,
            supported=SUPPORTED_LANGUAGES,
        )

    target_languages = _resolve_target_languages(target_languages)
    pattern_ids = _fuzzy_match_pattern(pattern_description)

    logger.info("pattern_search_results", query=pattern_description, found_count=len(pattern_ids))

    equivalences = _build_equivalences(pattern_ids, target_languages)
    categories = list(set(PATTERN_DATABASE.get(pid, {}).get("category") for pid in pattern_ids))
    suggestions = _get_suggestions(pattern_ids, categories[0] if categories else None)
    execution_time = int((time.time() - start_time) * ConversionFactors.MILLISECONDS_PER_SECOND)

    return PatternEquivalenceResult(
        pattern_description=pattern_description,
        source_language=source_language,
        target_languages=target_languages,
        equivalences=equivalences,
        suggestions=suggestions,
        execution_time_ms=execution_time,
    )


def list_pattern_categories() -> List[Dict[str, Any]]:
    """List all available pattern categories with counts.

    Returns:
        List of category information dictionaries
    """
    category_counts: Dict[str, int] = {}
    category_examples: Dict[str, List[str]] = {}

    for pattern_id, pattern_data in PATTERN_DATABASE.items():
        category = pattern_data.get("category", "uncategorized")
        category_counts[category] = category_counts.get(category, 0) + 1

        if category not in category_examples:
            category_examples[category] = []
        if len(category_examples[category]) < PatternEquivalenceTopN.CATEGORY_RELATED_SUGGESTION:
            category_examples[category].append(pattern_id)

    return [
        {
            "category": cat,
            "count": count,
            "examples": category_examples.get(cat, []),
        }
        for cat, count in sorted(category_counts.items())
    ]


def get_pattern_details(pattern_id: str) -> Optional[PatternEquivalence]:
    """Get detailed information about a specific pattern.

    Args:
        pattern_id: Pattern identifier

    Returns:
        PatternEquivalence object or None if not found
    """
    pattern_data = PATTERN_DATABASE.get(pattern_id)
    if not pattern_data:
        return None

    return _create_pattern_equivalence(pattern_id, pattern_data)
