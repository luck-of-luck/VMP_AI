"""Recommendation engine for deduplication refactoring."""

from typing import Any, Dict, List, cast

from ...constants import RecommendationDefaults

# Configuration-driven strategy definitions
STRATEGY_CONFIG = {
    "extract_function": {
        "base_score": RecommendationDefaults.EXTRACT_FUNCTION_BASE_SCORE,
        "description": "Extract duplicate code into a shared function",
        "scoring_rules": [
            {
                "condition": lambda c, ln, a, s, h: c <= RecommendationDefaults.EXTRACT_FN_LOW_COMPLEXITY,
                "adjustment": RecommendationDefaults.EXTRACT_FN_LOW_COMPLEXITY_BONUS,
            },
            {
                "condition": lambda c, ln, a, s, h: c > RecommendationDefaults.EXTRACT_FN_HIGH_COMPLEXITY,
                "adjustment": RecommendationDefaults.EXTRACT_FN_HIGH_COMPLEXITY_PENALTY,
            },
            {
                "condition": lambda c, ln, a, s, h: ln >= RecommendationDefaults.EXTRACT_FN_LINES_BONUS_THRESHOLD,
                "adjustment": RecommendationDefaults.EXTRACT_FN_LINES_BONUS,
            },
            {
                "condition": lambda c, ln, a, s, h: a >= RecommendationDefaults.EXTRACT_FN_FILES_THRESHOLD,
                "adjustment": RecommendationDefaults.EXTRACT_FN_FILES_BONUS,
            },
        ],
        "effort_fn": lambda c, ln, a, h: "low" if c <= RecommendationDefaults.EXTRACT_FN_LOW_COMPLEXITY else "medium",
        "risk_fn": lambda c, ln, a, h: "low" if h else "medium",
        "best_for": "Simple, stateless duplicates with clear inputs/outputs",
    },
    "extract_class": {
        "base_score": RecommendationDefaults.EXTRACT_CLASS_BASE_SCORE,
        "description": "Extract duplicate code into a shared class with state",
        "scoring_rules": [
            {
                "condition": lambda c, ln, a, s, h: c > RecommendationDefaults.EXTRACT_CLS_HIGH_COMPLEXITY,
                "adjustment": RecommendationDefaults.EXTRACT_CLS_HIGH_COMPLEXITY_BONUS,
            },
            {
                "condition": (
                    lambda c, ln, a, s, h: RecommendationDefaults.EXTRACT_CLS_MID_COMPLEXITY_LOWER
                    < c
                    <= RecommendationDefaults.EXTRACT_CLS_HIGH_COMPLEXITY
                ),
                "adjustment": RecommendationDefaults.EXTRACT_CLS_MID_COMPLEXITY_BONUS,
            },
            {
                "condition": lambda c, ln, a, s, h: ln >= RecommendationDefaults.EXTRACT_CLS_LINES_THRESHOLD,
                "adjustment": RecommendationDefaults.EXTRACT_CLS_LINES_BONUS,
            },
            {
                "condition": lambda c, ln, a, s, h: a >= RecommendationDefaults.EXTRACT_CLS_FILES_THRESHOLD,
                "adjustment": RecommendationDefaults.EXTRACT_CLS_FILES_BONUS,
            },
            {
                "condition": (
                    lambda c, ln, a, s, h: c <= RecommendationDefaults.EXTRACT_CLS_LOW_COMPLEXITY
                    and ln < RecommendationDefaults.EXTRACT_CLS_LOW_LINES
                ),
                "adjustment": RecommendationDefaults.EXTRACT_CLS_LOW_EFFORT_PENALTY,
            },
        ],
        "effort_fn": lambda c, ln, a, h: "medium" if c <= RecommendationDefaults.EXTRACT_CLS_HIGH_COMPLEXITY else "high",
        "risk_fn": lambda c, ln, a, h: "medium" if h else "high",
        "best_for": "Complex duplicates with shared state or multiple related functions",
    },
    "inline": {
        "base_score": RecommendationDefaults.INLINE_BASE_SCORE,
        "description": "Keep code duplicated (intentional duplication)",
        "scoring_rules": [
            {
                "condition": lambda c, ln, a, s, h: s < RecommendationDefaults.INLINE_LOW_SIMILARITY,
                "adjustment": RecommendationDefaults.INLINE_LOW_SIMILARITY_BONUS,
            },
            {
                "condition": (
                    lambda c, ln, a, s, h: RecommendationDefaults.INLINE_LOW_SIMILARITY
                    <= s
                    < RecommendationDefaults.INLINE_MID_SIMILARITY_UPPER
                ),
                "adjustment": RecommendationDefaults.INLINE_MID_SIMILARITY_BONUS,
            },
            {
                "condition": lambda c, ln, a, s, h: a == 1,
                "adjustment": RecommendationDefaults.INLINE_SINGLE_FILE_BONUS,
            },
            {
                "condition": lambda c, ln, a, s, h: ln < RecommendationDefaults.INLINE_SMALL_LINES_THRESHOLD,
                "adjustment": RecommendationDefaults.INLINE_SMALL_LINES_BONUS,
            },
            {
                "condition": lambda c, ln, a, s, h: s > RecommendationDefaults.INLINE_HIGH_SIMILARITY,
                "adjustment": RecommendationDefaults.INLINE_HIGH_SIMILARITY_PENALTY,
            },
        ],
        "effort_fn": lambda c, ln, a, h: "none",
        "risk_fn": lambda c, ln, a, h: "none",
        "best_for": "Intentional duplication, very small code blocks, or domain-specific variations",
    },
}


class RecommendationEngine:
    """Generates actionable recommendations for deduplication candidates."""

    def _calc_effort_value_ratio(self, complexity: int, lines_saved: int, has_tests: bool, affected_files: int) -> float:
        base_effort = (
            complexity * RecommendationDefaults.EFFORT_COMPLEXITY_WEIGHT + affected_files * RecommendationDefaults.EFFORT_FILES_WEIGHT
        )
        if not has_tests:
            base_effort *= RecommendationDefaults.NO_TESTS_EFFORT_MULTIPLIER
        value = lines_saved * RecommendationDefaults.VALUE_LINES_WEIGHT + affected_files * RecommendationDefaults.VALUE_FILES_BONUS
        return value / max(base_effort, 1)

    def _score_to_priority(self, score: float) -> tuple[str, str]:
        if score > RecommendationDefaults.HIGH_PRIORITY_SCORE_THRESHOLD:
            return "High Value: Extract to shared utility", "high"
        if score >= RecommendationDefaults.MEDIUM_PRIORITY_SCORE_THRESHOLD:
            return "Medium Value: Consider refactoring", "medium"
        return "Low Value: May not be worth refactoring", "low"

    def generate_deduplication_recommendation(
        self, score: float, complexity: int, lines_saved: int, has_tests: bool, affected_files: int
    ) -> Dict[str, Any]:
        """Generate actionable recommendations for deduplication candidates."""
        effort_value_ratio = self._calc_effort_value_ratio(complexity, lines_saved, has_tests, affected_files)
        recommendation_text, priority = self._score_to_priority(score)
        strategies = self._generate_dedup_refactoring_strategies(
            complexity=complexity, lines_saved=lines_saved, has_tests=has_tests, affected_files=affected_files, score=score
        )
        return {
            "recommendation_text": recommendation_text,
            "strategies": strategies,
            "priority": priority,
            "effort_value_ratio": round(effort_value_ratio, 2),
        }

    def _calculate_strategy_score(
        self,
        base_score: float,
        rules: List[Dict[str, Any]],
        complexity: int,
        lines_saved: int,
        affected_files: int,
        score: float,
        has_tests: bool,
    ) -> float:
        """Calculate strategy score by applying scoring rules.

        Args:
            base_score: Initial score for the strategy
            rules: List of scoring rules with conditions and adjustments
            complexity: Cyclomatic complexity
            lines_saved: Lines that would be saved
            affected_files: Number of affected files
            score: Overall duplication score
            has_tests: Whether tests exist

        Returns:
            Calculated score within range [0, 100]
        """
        current_score = base_score

        for rule in rules:
            if rule["condition"](complexity, lines_saved, affected_files, score, has_tests):
                current_score += rule["adjustment"]

        return min(100, max(0, current_score))

    def _build_strategy_dict(
        self,
        name: str,
        config: Dict[str, Any],
        suitability_score: float,
        complexity: int,
        lines_saved: int,
        affected_files: int,
        has_tests: bool,
    ) -> Dict[str, Any]:
        """Build a strategy dictionary from configuration.

        Args:
            name: Strategy name
            config: Strategy configuration
            suitability_score: Calculated suitability score
            complexity: Cyclomatic complexity
            lines_saved: Lines that would be saved
            affected_files: Number of affected files
            has_tests: Whether tests exist

        Returns:
            Complete strategy dictionary
        """
        return {
            "name": name,
            "description": config["description"],
            "suitability_score": suitability_score,
            "effort": config["effort_fn"](complexity, lines_saved, affected_files, has_tests),
            "risk": config["risk_fn"](complexity, lines_saved, affected_files, has_tests),
            "best_for": config["best_for"],
        }

    def _generate_dedup_refactoring_strategies(
        self, complexity: int, lines_saved: int, has_tests: bool, affected_files: int, score: float
    ) -> List[Dict[str, Any]]:
        """Generate ranked list of refactoring strategies for a duplication candidate.

        Evaluates multiple strategies and ranks them by suitability based on
        the characteristics of the duplicated code.

        Args:
            complexity: Cyclomatic complexity
            lines_saved: Lines that would be saved
            has_tests: Whether tests exist
            affected_files: Number of affected files
            score: Overall duplication score

        Returns:
            List of strategy dictionaries with name, description, suitability_score
        """
        strategies: List[Dict[str, Any]] = []

        # Process each strategy from configuration
        for strategy_name, config in STRATEGY_CONFIG.items():
            # Calculate score using rules
            suitability_score = self._calculate_strategy_score(
                base_score=cast(float, config["base_score"]),
                rules=cast(List[Dict[str, Any]], config["scoring_rules"]),
                complexity=complexity,
                lines_saved=lines_saved,
                affected_files=affected_files,
                score=score,
                has_tests=has_tests,
            )

            # Build strategy dictionary
            strategy = self._build_strategy_dict(
                name=strategy_name,
                config=config,
                suitability_score=suitability_score,
                complexity=complexity,
                lines_saved=lines_saved,
                affected_files=affected_files,
                has_tests=has_tests,
            )

            strategies.append(strategy)

        # Sort strategies by suitability score (highest first)
        strategies.sort(key=lambda s: s["suitability_score"], reverse=True)

        return strategies


_LANGUAGE_SUGGESTIONS: Dict[str, Dict[str, str]] = {
    "python": {"type": "decorator_pattern", "description": "Consider using a decorator pattern in python for cross-cutting concerns"},
    "ruby": {"type": "decorator_pattern", "description": "Consider using a decorator pattern in ruby for cross-cutting concerns"},
    "javascript": {"type": "higher_order_function", "description": "Consider using higher-order functions for functional composition"},
    "typescript": {"type": "higher_order_function", "description": "Consider using higher-order functions for functional composition"},
}


def _extra_suggestions(num_duplicates: int, line_count: int, language: str) -> List[Dict[str, Any]]:
    extras: List[Dict[str, Any]] = []
    if num_duplicates > RecommendationDefaults.MODULE_EXTRACTION_DUPLICATE_THRESHOLD:
        extras.append(
            {
                "type": "extract_module",
                "description": "Consider extracting to a dedicated module for reuse across files",
                "priority": "medium",
            }
        )
    if line_count > RecommendationDefaults.CLASS_EXTRACTION_LINE_THRESHOLD:
        extras.append(
            {
                "type": "extract_class",
                "description": "Extract to a class if the code has shared state or multiple related operations",
                "priority": "low",
            }
        )
    lang_hint = _LANGUAGE_SUGGESTIONS.get(language)
    if lang_hint:
        extras.append({**lang_hint, "priority": "low"})
    return extras


def generate_refactoring_suggestions(duplicates: List[Dict[str, Any]], language: str) -> List[Dict[str, Any]]:
    """Generate refactoring suggestions for duplicate code instances."""
    if not duplicates:
        return []

    num_duplicates = len(duplicates)
    avg_similarity = sum(d.get("similarity", RecommendationDefaults.DEFAULT_SIMILARITY) for d in duplicates) / max(num_duplicates, 1)
    first_code = duplicates[0].get("code", "")
    line_count = len(first_code.split("\n"))

    suggestions: List[Dict[str, Any]] = [
        {
            "type": "extract_function",
            "description": "Extract duplicate code into a shared utility function",
            "priority": "high" if avg_similarity > RecommendationDefaults.HIGH_SIMILARITY_THRESHOLD else "medium",
            "estimated_savings": f"{line_count * (num_duplicates - 1)} lines",
        }
    ]
    suggestions.extend(_extra_suggestions(num_duplicates, line_count, language))
    return suggestions
