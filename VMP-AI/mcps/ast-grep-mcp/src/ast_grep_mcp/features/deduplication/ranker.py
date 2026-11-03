"""
Ranking module for deduplication candidates.

This module provides functionality for scoring, classifying, and ranking
duplicate code based on refactoring value, complexity, and impact.
"""

import heapq
import logging
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from ...constants import (
    CodeAnalysisDefaults,
    DeduplicationDefaults,
    ParallelProcessing,
    PriorityClassifierThresholds,
    RankerDefaults,
    RiskMultipliers,
)
from ...core.logging import get_logger
from ...utils.futures import map_with_per_item_timeout


class DeduplicationScoreCalculator:
    """Calculates component scores for deduplication priority."""

    # Scoring weights from constants
    WEIGHT_SAVINGS = DeduplicationDefaults.SAVINGS_WEIGHT
    WEIGHT_COMPLEXITY = DeduplicationDefaults.COMPLEXITY_WEIGHT
    WEIGHT_RISK = DeduplicationDefaults.RISK_WEIGHT
    WEIGHT_EFFORT = DeduplicationDefaults.EFFORT_WEIGHT

    def __init__(self) -> None:
        """Initialize the score calculator."""
        self.logger = get_logger("deduplication.score_calculator")

    def calculate_total_score(
        self,
        duplicate_group: Dict[str, Any],
        complexity: Optional[Dict[str, Any]] = None,
        test_coverage: Optional[float] = None,
        impact_analysis: Optional[Dict[str, Any]] = None,
    ) -> tuple[float, Dict[str, float]]:
        """
        Calculate total deduplication score with component breakdown.

        Scoring weights:
        - Code savings: 40% (lines saved)
        - Complexity: 20% (inverse - simpler is better)
        - Risk: 25% (inverse - lower risk is better)
        - Effort: 15% (inverse - less effort is better)

        Args:
            duplicate_group: Group of duplicate code
            complexity: Complexity analysis results
            test_coverage: Test coverage percentage (0-100)
            impact_analysis: Impact analysis results

        Returns:
            Tuple of (total_score, score_breakdown)
        """
        scores = {"savings": self.calculate_savings_score(duplicate_group)}
        scores["complexity"] = self.calculate_complexity_score(complexity)

        # Early exit: skip risk/effort calculation for low-savings candidates
        early_exit = scores["savings"] < RankerDefaults.MIN_SAVINGS_SCORE_FOR_FULL_CALC
        scores.update(
            self._default_risk_effort_scores()
            if early_exit
            else self._full_risk_effort_scores(duplicate_group, test_coverage, impact_analysis)
        )

        total_score = sum(scores.values())
        self._debug_log_total_score(early_exit, total_score, scores)

        return round(total_score, 2), scores

    def _default_risk_effort_scores(self) -> Dict[str, float]:
        """Default middle-of-range risk/effort scores for low-savings candidates."""
        return {
            "risk": RankerDefaults.DEFAULT_MIDDLE_SCORE * self.WEIGHT_RISK,
            "effort": RankerDefaults.DEFAULT_MIDDLE_SCORE * self.WEIGHT_EFFORT,
        }

    def _full_risk_effort_scores(
        self,
        duplicate_group: Dict[str, Any],
        test_coverage: Optional[float],
        impact_analysis: Optional[Dict[str, Any]],
    ) -> Dict[str, float]:
        """Full risk/effort calculation for candidates with meaningful savings."""
        return {
            "risk": self.calculate_risk_score(test_coverage, impact_analysis),
            "effort": self.calculate_effort_score(duplicate_group),
        }

    def _debug_log_total_score(self, early_exit: bool, total_score: float, scores: Dict[str, float]) -> None:
        """Log the score breakdown when debug logging is enabled."""
        if not logging.getLogger().isEnabledFor(logging.DEBUG):
            return
        event = "total_score_calculated_early_exit" if early_exit else "total_score_calculated"
        self.logger.debug(event, total_score=round(total_score, 2), breakdown=scores)

    def calculate_savings_score(self, duplicate_group: Dict[str, Any]) -> float:
        """Calculate savings score (40% weight).

        Args:
            duplicate_group: Group of duplicate code

        Returns:
            Weighted savings score
        """
        lines_saved = duplicate_group.get("potential_line_savings", 0)
        # Normalize to 0-100 (cap at 500 lines for max score)
        savings_score = min(lines_saved / RankerDefaults.SAVINGS_NORMALIZATION_DIVISOR, RankerDefaults.MAX_NORMALIZED_SCORE)
        weighted_score = savings_score * self.WEIGHT_SAVINGS

        if logging.getLogger().isEnabledFor(logging.DEBUG):
            self.logger.debug("savings_score_calculated", lines_saved=lines_saved, raw_score=savings_score, weighted_score=weighted_score)

        return float(weighted_score)

    def calculate_complexity_score(self, complexity: Optional[Dict[str, Any]] = None) -> float:
        """Calculate complexity score (20% weight).

        Lower complexity is better.

        Args:
            complexity: Complexity analysis results

        Returns:
            Weighted complexity score
        """
        if complexity:
            complexity_value = complexity.get("complexity_score", CodeAnalysisDefaults.DEFAULT_COMPLEXITY_SCORE)
            # Invert: 1 = 100, 7 = 0
            complexity_score = max(
                0,
                RankerDefaults.MAX_NORMALIZED_SCORE - (complexity_value - 1) * RankerDefaults.COMPLEXITY_INVERSION_FACTOR,
            )
        else:
            complexity_score = RankerDefaults.DEFAULT_MIDDLE_SCORE

        weighted_score = complexity_score * self.WEIGHT_COMPLEXITY

        if logging.getLogger().isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "complexity_score_calculated",
                complexity_value=complexity.get("complexity_score") if complexity else None,
                raw_score=complexity_score,
                weighted_score=weighted_score,
            )

        return float(weighted_score)

    def calculate_risk_score(self, test_coverage: Optional[float] = None, impact_analysis: Optional[Dict[str, Any]] = None) -> float:
        """Calculate risk score (25% weight).

        Based on test coverage and breaking change risk.
        Higher coverage and lower breaking risk = higher score.

        Args:
            test_coverage: Test coverage percentage (0-100)
            impact_analysis: Impact analysis results

        Returns:
            Weighted risk score
        """
        risk_score: float = RankerDefaults.DEFAULT_MIDDLE_SCORE

        # Test coverage component
        if test_coverage is not None:
            # Higher coverage = lower risk = higher score
            risk_score = float(test_coverage)

        # Breaking change risk component
        if impact_analysis:
            breaking_risk = impact_analysis.get("breaking_change_risk", "medium")
            risk_multipliers = {"low": RiskMultipliers.LOW, "medium": RiskMultipliers.MEDIUM, "high": RiskMultipliers.HIGH}
            risk_score *= risk_multipliers.get(breaking_risk, RiskMultipliers.MEDIUM)

        weighted_score = risk_score * self.WEIGHT_RISK

        if logging.getLogger().isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "risk_score_calculated",
                test_coverage=test_coverage,
                breaking_risk=impact_analysis.get("breaking_change_risk") if impact_analysis else None,
                raw_score=risk_score,
                weighted_score=weighted_score,
            )

        return float(weighted_score)

    def calculate_effort_score(self, duplicate_group: Dict[str, Any]) -> float:
        """Calculate effort score (15% weight).

        Based on number of files and instances.
        More instances and files = more effort = lower score.

        Args:
            duplicate_group: Group of duplicate code

        Returns:
            Weighted effort score
        """
        instance_count = len(duplicate_group.get("instances", []))
        file_count = len(set(inst.get("file", "") for inst in duplicate_group.get("instances", [])))

        # More instances and files = more effort = lower score
        effort_score = max(
            0,
            RankerDefaults.MAX_NORMALIZED_SCORE
            - (instance_count * RankerDefaults.EFFORT_INSTANCE_PENALTY + file_count * RankerDefaults.EFFORT_FILE_PENALTY),
        )
        weighted_score = effort_score * self.WEIGHT_EFFORT

        if logging.getLogger().isEnabledFor(logging.DEBUG):
            self.logger.debug(
                "effort_score_calculated",
                instance_count=instance_count,
                file_count=file_count,
                raw_score=effort_score,
                weighted_score=weighted_score,
            )

        return float(weighted_score)


class DeduplicationPriorityClassifier:
    """Classifies deduplication candidates by priority and generates recommendations."""

    # Priority thresholds
    THRESHOLD_CRITICAL = PriorityClassifierThresholds.CRITICAL
    THRESHOLD_HIGH = PriorityClassifierThresholds.HIGH
    THRESHOLD_MEDIUM = PriorityClassifierThresholds.MEDIUM
    THRESHOLD_LOW = PriorityClassifierThresholds.LOW

    def __init__(self) -> None:
        """Initialize the priority classifier."""
        self.logger = get_logger("deduplication.priority_classifier")
        self._priority_cache: Dict[float, str] = {}

    def get_priority_label(self, score: float) -> str:
        """Get priority label from score.

        Priority levels:
        - critical: score >= 80
        - high: score >= 60
        - medium: score >= 40
        - low: score >= 20
        - minimal: score < 20

        Args:
            score: Total deduplication score (0-100)

        Returns:
            Priority label string (cached)
        """
        # Round to 2 decimal places for cache key consistency
        rounded_score = round(score, 2)

        # Check cache first
        if rounded_score in self._priority_cache:
            return self._priority_cache[rounded_score]

        # Compute and cache
        if rounded_score >= self.THRESHOLD_CRITICAL:
            label = "critical"
        elif rounded_score >= self.THRESHOLD_HIGH:
            label = "high"
        elif rounded_score >= self.THRESHOLD_MEDIUM:
            label = "medium"
        elif rounded_score >= self.THRESHOLD_LOW:
            label = "low"
        else:
            label = "minimal"

        self._priority_cache[rounded_score] = label
        return label

    def get_score_breakdown(self, candidate: Dict[str, Any], total_score: float, score_components: Dict[str, float]) -> Dict[str, Any]:
        """Get detailed score breakdown with factors and recommendation.

        Args:
            candidate: Deduplication candidate
            total_score: Total score (0-100)
            score_components: Individual component scores

        Returns:
            Detailed breakdown dictionary
        """
        lines_saved = candidate.get("potential_line_savings", 0)
        instance_count = len(candidate.get("instances", []))

        breakdown = {
            "total_score": total_score,
            "components": score_components,
            "factors": {
                "lines_saved": lines_saved,
                "instance_count": instance_count,
                "complexity": candidate.get("complexity_analysis", {}).get("complexity_score", "N/A"),
                "test_coverage": candidate.get("test_coverage", "N/A"),
                "breaking_risk": candidate.get("impact_analysis", {}).get("breaking_change_risk", "N/A"),
            },
            "recommendation": self.get_recommendation(total_score, lines_saved, instance_count),
        }

        if logging.getLogger().isEnabledFor(logging.DEBUG):
            self.logger.debug("score_breakdown_generated", total_score=total_score, priority=self.get_priority_label(total_score))

        return breakdown

    def get_recommendation(self, score: float, lines_saved: int, instance_count: int) -> str:
        """Generate recommendation based on score and metrics.

        Args:
            score: Total deduplication score (0-100)
            lines_saved: Number of lines that would be saved
            instance_count: Number of duplicate instances

        Returns:
            Recommendation text
        """
        if score >= self.THRESHOLD_CRITICAL:
            return f"Immediate refactoring recommended. Will save {lines_saved} lines across {instance_count} instances."
        elif score >= self.THRESHOLD_HIGH:
            return "High-value refactoring opportunity. Consider prioritizing in next sprint."
        elif score >= self.THRESHOLD_MEDIUM:
            return "Moderate refactoring value. Include in technical debt backlog."
        else:
            return "Low priority. Consider deferring unless part of larger refactoring."

    def classify_batch(self, candidates: list[Dict[str, Any]], scores: list[float]) -> Dict[str, list[Dict[str, Any]]]:
        """Classify multiple candidates by priority level.

        Args:
            candidates: List of deduplication candidates
            scores: Corresponding scores for each candidate

        Returns:
            Dictionary mapping priority labels to candidate lists
        """
        classified: Dict[str, list[Dict[str, Any]]] = {"critical": [], "high": [], "medium": [], "low": [], "minimal": []}

        for candidate, score in zip(candidates, scores):
            priority = self.get_priority_label(score)
            classified[priority].append({**candidate, "score": score, "priority": priority})

        self.logger.info(
            "batch_classified",
            total_candidates=len(candidates),
            critical=len(classified["critical"]),
            high=len(classified["high"]),
            medium=len(classified["medium"]),
            low=len(classified["low"]),
            minimal=len(classified["minimal"]),
        )

        return classified

    def clear_cache(self) -> None:
        """Clear the priority label cache."""
        self._priority_cache.clear()


class DuplicationRanker:
    """Ranks duplication candidates by refactoring value with score caching."""

    def __init__(self, enable_cache: bool = True, max_workers: Optional[int] = None) -> None:
        """Initialize the ranker.

        Args:
            enable_cache: Whether to enable score caching (default: True)
            max_workers: Max thread pool workers (None=default, 0=disable parallelization)
        """
        self.logger = get_logger("deduplication.ranker")
        self.score_calculator = DeduplicationScoreCalculator()
        self.priority_classifier = DeduplicationPriorityClassifier()
        self.enable_cache = enable_cache
        self.max_workers = max_workers
        self._score_cache: OrderedDict[str, Tuple[float, Dict[str, Any]]] = OrderedDict()
        self._cache_lock = threading.Lock()

    def _generate_cache_key(self, candidate: Dict[str, Any]) -> str:
        """Generate a stable, collision-safe cache key for candidate scores.

        The key embeds the exact ``repr`` of the scoring-relevant fields rather
        than ``hash()``, which is both collision-prone and salted per-process
        for strings (BUG-12).

        Args:
            candidate: Candidate dictionary

        Returns:
            Cache key string (exact tuple encoding)
        """
        cache_tuple = (
            candidate.get("similarity", 0),
            tuple(sorted(candidate.get("files", []))),
            candidate.get("lines_saved", 0),
            candidate.get("potential_line_savings", 0),
            len(candidate.get("instances", [])),
            str(candidate.get("complexity_analysis")),
            candidate.get("test_coverage"),
            str(candidate.get("impact_analysis")),
        )
        return f"cache_{cache_tuple!r}"

    def clear_cache(self) -> None:
        """Clear the score cache."""
        with self._cache_lock:
            self._score_cache.clear()
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            self.logger.debug("score_cache_cleared")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache_size
        """
        return {"cache_size": len(self._score_cache), "cache_enabled": self.enable_cache}

    def calculate_deduplication_score(
        self,
        duplicate_group: Dict[str, Any],
        complexity: Optional[Dict[str, Any]] = None,
        test_coverage: Optional[float] = None,
        impact_analysis: Optional[Dict[str, Any]] = None,
    ) -> float:
        """
        Calculate a score for deduplication priority.

        Scoring weights:
        - Code savings: 40% (lines saved)
        - Complexity: 20% (inverse - simpler is better)
        - Risk: 25% (inverse - lower risk is better)
        - Effort: 15% (inverse - less effort is better)

        Args:
            duplicate_group: Group of duplicate code
            complexity: Complexity analysis results
            test_coverage: Test coverage percentage (0-100)
            impact_analysis: Impact analysis results

        Returns:
            Score from 0-100, higher is better for refactoring
        """
        # Delegate to score calculator
        total_score, score_components = self.score_calculator.calculate_total_score(
            duplicate_group, complexity, test_coverage, impact_analysis
        )

        # Log the result
        lines_saved = duplicate_group.get("potential_line_savings", 0)
        instance_count = len(duplicate_group.get("instances", []))

        self.logger.info(
            "deduplication_score_calculated",
            total_score=total_score,
            breakdown=score_components,
            lines_saved=lines_saved,
            instance_count=instance_count,
        )

        return total_score

    def _score_candidate(self, candidate: Dict[str, Any]) -> Tuple[float, Dict[str, float], int, int]:
        """Score a single candidate, using cache if enabled. Returns (total_score, components, hits, misses)."""
        if not self.enable_cache:
            total_score, score_components = self.score_calculator.calculate_total_score(
                candidate,
                complexity=candidate.get("complexity_analysis"),
                test_coverage=candidate.get("test_coverage"),
                impact_analysis=candidate.get("impact_analysis"),
            )
            return total_score, score_components, 0, 0

        cache_key = self._generate_cache_key(candidate)

        with self._cache_lock:
            if cache_key in self._score_cache:
                self._score_cache.move_to_end(cache_key)
                total_score, score_components = self._score_cache[cache_key]
                return total_score, score_components, 1, 0

        total_score, score_components = self.score_calculator.calculate_total_score(
            candidate,
            complexity=candidate.get("complexity_analysis"),
            test_coverage=candidate.get("test_coverage"),
            impact_analysis=candidate.get("impact_analysis"),
        )

        with self._cache_lock:
            self._score_cache[cache_key] = (total_score, score_components)
            if len(self._score_cache) > RankerDefaults.SCORE_CACHE_MAX_SIZE:
                self._score_cache.popitem(last=False)
        return total_score, score_components, 0, 1

    def _score_candidates_parallel(
        self, candidates: List[Dict[str, Any]]
    ) -> Tuple[List[Tuple[float, Dict[str, float], int, int]], int]:
        """Score candidates in parallel using daemon workers with per-item timeouts.

        Scoring is pure in-memory arithmetic (no I/O), so hangs are extremely
        unlikely in practice. The shared helper is used for consistency with
        the rest of the deduplication pipeline and to eliminate the executor's
        implicit ``shutdown(wait=True)`` which would block indefinitely if any
        worker hung (BUG-06-CR-10).

        Returns tuple of (scores_list, total_workers_used)
        """
        results: List[Any] = [None] * len(candidates)
        workers_used = min(self.max_workers or 1, len(candidates))

        def on_success(item: Tuple[int, Dict[str, Any]], score_tuple: Tuple[float, Dict[str, float], int, int]) -> None:
            idx, _ = item
            results[idx] = score_tuple

        def on_error(item: Tuple[int, Dict[str, Any]], error: Exception) -> None:
            idx, candidate = item
            self.logger.warning(
                "scoring_failed_using_default",
                candidate_id=candidate.get("id", "unknown"),
                error=str(error),
            )
            # Scoring is pure in-memory; a failure here is unexpected. Fall
            # back to score=0 (lowest priority) rather than crashing the stage.
            results[idx] = (0.0, {}, 0, 0)

        indexed = [(i, c) for i, c in enumerate(candidates)]
        map_with_per_item_timeout(
            indexed,
            lambda item: self._score_candidate(item[1]),
            timeout_seconds=float(ParallelProcessing.DEFAULT_TIMEOUT_PER_CANDIDATE_SECONDS),
            max_workers=workers_used,
            on_success=on_success,
            on_error=on_error,
        )

        return results, workers_used

    def _build_ranked_candidate(
        self,
        candidate: Dict[str, Any],
        total_score: float,
        score_components: Dict[str, float],
        include_analysis: bool,
    ) -> Dict[str, Any]:
        """Build a ranked candidate dict with optional breakdown."""
        priority = self.priority_classifier.get_priority_label(total_score)
        ranked_candidate = {**candidate, "score": total_score, "priority": priority}
        if include_analysis:
            ranked_candidate["score_breakdown"] = self.priority_classifier.get_score_breakdown(candidate, total_score, score_components)
        return ranked_candidate

    def _build_log_data(self, ranked: List[Dict[str, Any]], cache_hits: int, cache_misses: int) -> Dict[str, Any]:
        """Build log data dict for ranking results."""
        log_data: Dict[str, Any] = {
            "total_candidates": len(ranked),
            "top_score": ranked[0]["score"] if ranked else 0,
            "average_score": sum(c["score"] for c in ranked) / len(ranked) if ranked else 0,
        }
        if self.enable_cache:
            total = cache_hits + cache_misses
            log_data.update(
                {
                    "cache_hits": cache_hits,
                    "cache_misses": cache_misses,
                    "cache_hit_rate": cache_hits / total if total > 0 else 0,
                    "cache_size": len(self._score_cache),
                }
            )
        return log_data

    def rank_deduplication_candidates(
        self, candidates: List[Dict[str, Any]], include_analysis: bool = True, max_results: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Rank deduplication candidates by priority with score caching.

        Args:
            candidates: List of deduplication candidates
            include_analysis: Whether to include detailed analysis
            max_results: Maximum number of results to return (early exit optimization)

        Returns:
            Ranked list of candidates with scores
        """
        ranked = []
        cache_hits = 0
        cache_misses = 0

        if self.max_workers == 0 or len(candidates) < 2:
            for candidate in candidates:
                total_score, score_components, hits, misses = self._score_candidate(candidate)
                cache_hits += hits
                cache_misses += misses
                ranked.append(self._build_ranked_candidate(candidate, total_score, score_components, include_analysis))
        else:
            score_results, workers_used = self._score_candidates_parallel(candidates)
            for candidate, (total_score, score_components, hits, misses) in zip(candidates, score_results):
                cache_hits += hits
                cache_misses += misses
                ranked.append(self._build_ranked_candidate(candidate, total_score, score_components, include_analysis))

            if logging.getLogger().isEnabledFor(logging.DEBUG):
                self.logger.debug("parallel_scoring_used", workers=workers_used)

        if max_results is not None and max_results > 0:
            ranked = heapq.nlargest(max_results, ranked, key=lambda x: x["score"])
        else:
            ranked.sort(key=lambda x: x["score"], reverse=True)

        for i, candidate in enumerate(ranked):
            candidate["rank"] = i + 1

        self.logger.info("candidates_ranked", **self._build_log_data(ranked, cache_hits, cache_misses))

        return ranked
