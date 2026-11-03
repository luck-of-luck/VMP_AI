"""Enhanced reporting and visualization for deduplication results."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ...constants import CodeAnalysisDefaults, DisplayDefaults, PriorityWeights, RankerDefaults, ReportingDefaults
from ...utils.formatters import generate_multi_file_diff

_DIFF_PREFIX_COLORS = [
    ("+++", "\033[33m"),
    ("---", "\033[33m"),
    ("@@", "\033[36m"),
    ("+", "\033[32m"),
    ("-", "\033[31m"),
]
_RESET = "\033[0m"


def _colorize_diff_line(line: str) -> str:
    for prefix, color in _DIFF_PREFIX_COLORS:
        if line.startswith(prefix):
            return f"{color}{line}{_RESET}"
    return line


def _number_lines(lines: List[str]) -> str:
    return "\n".join(f"{i:3d} | {line}" for i, line in enumerate(lines, 1))


def _get_complexity_level(score: int) -> Tuple[str, str, List[str]]:
    if score <= DisplayDefaults.LOW_SCORE_THRESHOLD:
        return (
            "Low",
            "\033[32m",
            [
                "Good candidate for quick refactoring",
                "Consider extracting as a simple helper function",
                "Low risk of introducing bugs during extraction",
            ],
        )
    if score <= DisplayDefaults.MEDIUM_SCORE_THRESHOLD:
        return (
            "Medium",
            "\033[33m",
            [
                "Review the code carefully before extraction",
                "Consider adding unit tests before refactoring",
                "May benefit from breaking into smaller pieces",
                "Check for hidden dependencies or side effects",
            ],
        )
    return (
        "High",
        "\033[31m",
        [
            "High complexity - proceed with caution",
            "Strongly recommend comprehensive test coverage first",
            "Consider incremental refactoring in smaller steps",
            "Review for cyclomatic complexity and reduce branches",
            "May need architectural review before extraction",
        ],
    )


@dataclass
class EnhancedDuplicationCandidate:
    """Enhanced duplication candidate with full reporting details.

    Attributes:
        id: Unique identifier for this candidate
        files: List of file paths containing the duplicate
        locations: List of (file, start_line, end_line) tuples
        original_code: The duplicate code snippet
        suggested_function_name: Suggested name for extracted function
        replacement_code: Code to replace each occurrence
        similarity_score: How similar the duplicates are (0-100)
        complexity_score: Complexity rating (1-10)
        before_after: Before/after example dict
        complexity_viz: Complexity visualization dict
        diff_preview: Diff preview for all files
        priority: Priority ranking (higher = more important)
    """

    id: str
    files: List[str]
    locations: List[Tuple[str, int, int]]
    original_code: str
    suggested_function_name: str
    replacement_code: str
    similarity_score: float
    complexity_score: int
    before_after: Dict[str, Any]
    complexity_viz: Dict[str, Any]
    diff_preview: Optional[str]
    priority: int


class DuplicationReporter:
    """Creates enhanced reports for code duplication findings."""

    def format_diff_with_colors(self, diff: str) -> str:
        """Add ANSI color codes to a unified diff for CLI display."""
        if not diff:
            return diff
        return "\n".join(_colorize_diff_line(line) for line in diff.split("\n"))

    def generate_before_after_example(self, original_code: str, replacement_code: str, function_name: str) -> Dict[str, Any]:
        """Generate before/after code examples for a duplication extraction."""
        original_lines = original_code.strip().split("\n")
        replacement_lines = replacement_code.strip().split("\n")
        original_line_count = len(original_lines)
        replacement_line_count = len(replacement_lines)
        lines_saved = original_line_count - replacement_line_count
        explanation = (
            f"Extracted {original_line_count} lines of duplicate code into "
            f"'{function_name}', reducing to {replacement_line_count} line(s). "
            f"This saves {lines_saved} line(s) per occurrence."
            if lines_saved > 0
            else f"Refactored code into '{function_name}' for better reusability and maintainability."
        )
        return {
            "before": _number_lines(original_lines),
            "after": _number_lines(replacement_lines),
            "before_raw": original_code.strip(),
            "after_raw": replacement_code.strip(),
            "function_definition": f"def {function_name}(...):",
            "function_name": function_name,
            "original_lines": original_line_count,
            "replacement_lines": replacement_line_count,
            "lines_saved": lines_saved,
            "explanation": explanation,
        }

    def visualize_complexity(self, score: int) -> Dict[str, Any]:
        """Create a visual complexity indicator with recommendations."""
        score = max(DisplayDefaults.COMPLEXITY_SCORE_MIN, min(DisplayDefaults.COMPLEXITY_SCORE_MAX, score))
        description, color_code, recommendations = _get_complexity_level(score)
        reset_code = "\033[0m"
        filled = score
        empty = DisplayDefaults.VISUALIZATION_BAR_LENGTH - score
        bar_plain = f"[{'=' * filled}{' ' * empty}] {score}/{DisplayDefaults.VISUALIZATION_BAR_LENGTH}"
        bar_colored = f"{color_code}[{'=' * filled}{' ' * empty}]{reset_code} {score}/{DisplayDefaults.VISUALIZATION_BAR_LENGTH}"
        return {
            "score": score,
            "bar": bar_plain,
            "bar_colored": bar_colored,
            "description": description,
            "color_code": color_code,
            "recommendations": recommendations,
            "formatted": f"{description} Complexity ({score}/10): {bar_plain}",
        }

    def create_enhanced_duplication_response(
        self, candidates: List[Dict[str, Any]], include_diffs: bool = True, include_colors: bool = False
    ) -> Dict[str, Any]:
        """Create an enhanced duplication detection response with before/after, diffs, and recommendations."""
        enhanced_candidates = []
        total_lines_saveable = 0
        distribution: Dict[str, int] = {"low": 0, "medium": 0, "high": 0}

        for idx, candidate in enumerate(candidates):
            ec = self._build_enhanced_candidate(candidate, idx, include_diffs, include_colors)
            enhanced_candidates.append(ec)
            total_lines_saveable += ec["before_after"]["lines_saved"] * len(ec["files"])
            self._update_distribution(distribution, ec["complexity_score"])

        enhanced_candidates.sort(key=lambda x: x["priority"], reverse=True)
        recommendations = self._build_global_recommendations(distribution, total_lines_saveable, len(enhanced_candidates))
        summary = self._build_summary(candidates, enhanced_candidates, total_lines_saveable, distribution)

        return {
            "candidates": enhanced_candidates,
            "summary": summary,
            "recommendations": recommendations,
            "metadata": {
                "version": "5.0",
                "includes_diffs": include_diffs,
                "includes_colors": include_colors,
                "generated_at": datetime.now().isoformat(),
            },
        }

    def _build_enhanced_candidate(self, candidate: Dict[str, Any], idx: int, include_diffs: bool, include_colors: bool) -> Dict[str, Any]:
        """Enrich a single raw candidate with computed fields."""
        function_name = candidate.get("function_name", "") or f"extracted_function_{idx}"
        before_after = self.generate_before_after_example(
            original_code=candidate.get("code", ""),
            replacement_code=candidate.get("replacement", ""),
            function_name=function_name,
        )
        complexity = candidate.get("complexity", CodeAnalysisDefaults.DEFAULT_COMPLEXITY_SCORE)
        occurrences = len(candidate.get("files", []))
        priority = (
            (occurrences * PriorityWeights.OCCURRENCE_WEIGHT)
            + (before_after["original_lines"] * PriorityWeights.LINE_WEIGHT)
            - (complexity * PriorityWeights.COMPLEXITY_PENALTY)
        )
        return {
            "id": f"DUP-{idx + 1:03d}",
            "files": candidate.get("files", []),
            "locations": candidate.get("locations", []),
            "original_code": candidate.get("code", ""),
            "suggested_function_name": function_name,
            "replacement_code": candidate.get("replacement", ""),
            "similarity_score": candidate.get("similarity_score", float(RankerDefaults.MAX_NORMALIZED_SCORE)),
            "complexity_score": complexity,
            "before_after": before_after,
            "complexity_viz": self.visualize_complexity(complexity),
            "diff_preview": self._generate_candidate_diff_preview(candidate, include_diffs, include_colors),
            "priority": priority,
        }

    def _generate_candidate_diff_preview(self, candidate: Dict[str, Any], include_diffs: bool, include_colors: bool) -> Optional[str]:
        """Generate a diff preview for the candidate, or None if not requested."""
        if not include_diffs or "files" not in candidate:
            return None
        original_code = candidate.get("code", "")
        replacement = candidate.get("replacement", "")
        file_changes = [
            {"file_path": fp, "original_content": original_code, "new_content": replacement} for fp in candidate.get("files", [])
        ]
        if not file_changes:
            return None
        diff_text = generate_multi_file_diff(file_changes, context_lines=3).combined_diff
        return self.format_diff_with_colors(diff_text) if include_colors else diff_text

    @staticmethod
    def _update_distribution(distribution: Dict[str, int], complexity: float) -> None:
        """Increment the appropriate complexity bucket."""
        if complexity <= DisplayDefaults.LOW_SCORE_THRESHOLD:
            distribution["low"] += 1
        elif complexity <= DisplayDefaults.MEDIUM_SCORE_THRESHOLD:
            distribution["medium"] += 1
        else:
            distribution["high"] += 1

    @staticmethod
    def _build_global_recommendations(distribution: Dict[str, int], total_lines_saveable: int, candidate_count: int) -> List[str]:
        """Build prioritized global recommendations list."""
        recs: List[str] = []
        if distribution["high"] > 0:
            recs.append(f"Found {distribution['high']} high-complexity duplicates. Consider adding tests before refactoring these.")
        if total_lines_saveable > ReportingDefaults.SIGNIFICANT_LINES_SAVED_THRESHOLD:
            recs.append(f"Potential to save {total_lines_saveable} total lines of code. Prioritize candidates by their priority score.")
        if candidate_count > ReportingDefaults.MANY_DUPLICATES_THRESHOLD:
            recs.append("Many duplicates found. Consider addressing high-priority items first to maximize impact with minimal effort.")
        return recs

    @staticmethod
    def _build_summary(
        raw_candidates: List[Dict[str, Any]],
        enhanced: List[Dict[str, Any]],
        total_lines_saveable: int,
        distribution: Dict[str, int],
    ) -> Dict[str, Any]:
        """Assemble the summary statistics dict."""
        return {
            "total_candidates": len(enhanced),
            "total_files_affected": len(set(f for c in raw_candidates for f in c.get("files", []))),
            "total_lines_saveable": total_lines_saveable,
            "complexity_distribution": distribution,
            "highest_priority_id": enhanced[0]["id"] if enhanced else None,
        }
