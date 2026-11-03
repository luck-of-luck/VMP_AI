"""Parallel complexity analysis execution.

This module handles analyzing files in parallel and collecting
complexity metrics for all functions.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, List

from ...constants import ParallelProcessing
from ...core.logging import get_logger
from ...models.complexity import ComplexityThresholds, FunctionComplexity
from .analyzer import analyze_file_complexity


class ParallelComplexityAnalyzer:
    """Analyzes files in parallel for complexity metrics."""

    def __init__(self) -> None:
        """Initialize the parallel analyzer."""
        self.logger = get_logger("complexity.parallel_analyzer")

    def analyze_files(
        self, files: List[str], language: str, thresholds: ComplexityThresholds, max_threads: int = ParallelProcessing.DEFAULT_WORKERS
    ) -> List[FunctionComplexity]:
        """Analyze multiple files in parallel.

        Args:
            files: List of file paths to analyze
            language: Programming language
            thresholds: Complexity thresholds
            max_threads: Number of parallel threads

        Returns:
            List of all function complexity results
        """
        self.logger.info("analyze_files_start", file_count=len(files), language=language, max_threads=max_threads)

        all_functions: List[FunctionComplexity] = []
        lang = language.lower()

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = {executor.submit(analyze_file_complexity, f, lang, thresholds): f for f in files}
            for future in as_completed(futures):
                self._collect_future_result(future, futures[future], all_functions)

        self.logger.info("analyze_files_complete", total_functions=len(all_functions))

        return all_functions

    def _collect_future_result(self, future: Any, file_path: str, all_functions: List[FunctionComplexity]) -> None:
        """Collect result from a completed future into all_functions."""
        try:
            result = future.result()
            all_functions.extend(result)
        except Exception as e:
            self.logger.warning("file_analysis_failed", file=file_path, error=str(e))

    def filter_exceeding_functions(self, functions: List[FunctionComplexity]) -> List[FunctionComplexity]:
        """Filter to only functions exceeding thresholds.

        Args:
            functions: All function complexity results

        Returns:
            List of functions exceeding thresholds, sorted by complexity
        """
        exceeding = [f for f in functions if f.exceeds]

        # Sort by combined complexity score (highest first)
        exceeding.sort(key=lambda f: f.metrics.cyclomatic + f.metrics.cognitive, reverse=True)

        self.logger.info("filter_complete", total_functions=len(functions), exceeding_count=len(exceeding))

        return exceeding
