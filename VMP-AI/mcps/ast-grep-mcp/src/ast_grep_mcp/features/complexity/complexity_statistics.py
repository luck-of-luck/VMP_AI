"""Statistics aggregation and result formatting for complexity analysis.

This module handles calculating summary statistics, storing results,
retrieving trends, and formatting the final response.
"""

import subprocess
from typing import Any, Dict, List, Optional

from ...constants import ComplexityStorageDefaults, ConversionFactors, FormattingDefaults, ValidationDefaults
from ...core.logging import get_logger
from ...models.complexity import FunctionComplexity
from .storage import ComplexityStorage


class ComplexityStatisticsAggregator:
    """Aggregates statistics and formats complexity analysis results."""

    def __init__(self) -> None:
        """Initialize the statistics aggregator."""
        self.logger = get_logger("complexity.statistics")

    def calculate_summary(
        self,
        all_functions: List[FunctionComplexity],
        exceeding_functions: List[FunctionComplexity],
        total_files: int,
        execution_time: float,
    ) -> Dict[str, Any]:
        """Calculate summary statistics from analysis results.

        Args:
            all_functions: All analyzed functions
            exceeding_functions: Functions exceeding thresholds
            total_files: Total number of files analyzed
            execution_time: Analysis execution time in seconds

        Returns:
            Summary statistics dictionary
        """
        total_functions = len(all_functions)
        avg_cyclomatic, avg_cognitive, max_cyclomatic, max_cognitive, max_nesting = self._compute_metrics(all_functions, total_functions)

        return {
            "total_functions": total_functions,
            "total_files": total_files,
            "exceeding_threshold": len(exceeding_functions),
            "avg_cyclomatic": round(avg_cyclomatic, 2),
            "avg_cognitive": round(avg_cognitive, 2),
            "max_cyclomatic": max_cyclomatic,
            "max_cognitive": max_cognitive,
            "max_nesting": max_nesting,
            "analysis_time_seconds": round(execution_time, FormattingDefaults.ROUNDING_PRECISION),
        }

    def _compute_metrics(self, all_functions: List[FunctionComplexity], total_functions: int) -> tuple[float, float, int, int, int]:
        """Return (avg_cyc, avg_cog, max_cyc, max_cog, max_nest) or zeros if empty."""
        if not total_functions:
            return 0.0, 0.0, 0, 0, 0
        cyclomatic_vals = [f.metrics.cyclomatic for f in all_functions]
        cognitive_vals = [f.metrics.cognitive for f in all_functions]
        nesting_vals = [f.metrics.nesting_depth for f in all_functions]
        return (
            sum(cyclomatic_vals) / total_functions,
            sum(cognitive_vals) / total_functions,
            max(cyclomatic_vals),
            max(cognitive_vals),
            max(nesting_vals),
        )

    def _run_git_command(self, args: list[str], cwd: str) -> Optional[str]:
        """Run a git command and return stdout stripped, or None on failure."""
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=ValidationDefaults.SYNTAX_CHECK_TIMEOUT_SECONDS,
        )
        return result.stdout.strip() or None if result.returncode == 0 else None

    def get_git_info(self, project_folder: str) -> tuple[Optional[str], Optional[str]]:
        """Get current git commit and branch information.

        Args:
            project_folder: Project root folder

        Returns:
            Tuple of (commit_hash, branch_name) or (None, None) if not a git repo
        """
        try:
            commit_hash = self._run_git_command(["git", "rev-parse", "HEAD"], project_folder)
            branch_name = self._run_git_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], project_folder)
        except Exception as e:
            self.logger.debug("git_info_failed", error=str(e))
            return None, None

        return commit_hash, branch_name

    def store_results(
        self, project_folder: str, summary: Dict[str, Any], all_functions: List[FunctionComplexity]
    ) -> tuple[Optional[str], Optional[str]]:
        """Store analysis results in database.

        Args:
            project_folder: Project root folder
            summary: Summary statistics
            all_functions: All analyzed functions

        Returns:
            Tuple of (run_id, stored_at) or (None, None) if storage failed
        """
        try:
            storage = ComplexityStorage()
            commit_hash, branch_name = self.get_git_info(project_folder)

            # Build results data for storage
            results_data = {
                "total_functions": summary["total_functions"],
                "total_files": summary["total_files"],
                "avg_cyclomatic": summary["avg_cyclomatic"],
                "avg_cognitive": summary["avg_cognitive"],
                "max_cyclomatic": summary["max_cyclomatic"],
                "max_cognitive": summary["max_cognitive"],
                "max_nesting": summary["max_nesting"],
                "violation_count": summary["exceeding_threshold"],
                "duration_ms": int(summary["analysis_time_seconds"] * ConversionFactors.MILLISECONDS_PER_SECOND),
            }

            run_id = storage.store_analysis_run(project_folder, results_data, all_functions, commit_hash, branch_name)

            self.logger.info("results_stored", run_id=run_id)
            return str(run_id), str(storage.db_path)

        except Exception as e:
            self.logger.warning("storage_failed", error=str(e))
            return None, None

    def get_trends(self, project_folder: str, days: int = ComplexityStorageDefaults.TRENDS_LOOKBACK_DAYS) -> Optional[List[Dict[str, Any]]]:
        """Get historical trend data for project.

        Args:
            project_folder: Project root folder
            days: Number of days of history to include

        Returns:
            Trend data dictionary or None if failed
        """
        try:
            storage = ComplexityStorage()
            trends = storage.get_project_trends(project_folder, days=days)
            self.logger.info("trends_retrieved", days=days)
            return trends
        except Exception as e:
            self.logger.warning("trends_failed", error=str(e))
            return None

    @staticmethod
    def _function_to_dict(f: FunctionComplexity) -> Dict[str, Any]:
        return {
            "name": f.function_name,
            "file": f.file_path,
            "lines": f"{f.start_line}-{f.end_line}",
            "cyclomatic": f.metrics.cyclomatic,
            "cognitive": f.metrics.cognitive,
            "nesting_depth": f.metrics.nesting_depth,
            "length": f.metrics.lines,
            "exceeds": f.exceeds,
        }

    def format_response(
        self,
        summary: Dict[str, Any],
        thresholds: Dict[str, int],
        exceeding_functions: List[FunctionComplexity],
        run_id: Optional[str] = None,
        stored_at: Optional[str] = None,
        trends: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Format final analysis response."""
        response: Dict[str, Any] = {
            "summary": summary,
            "thresholds": thresholds,
            "functions": [self._function_to_dict(f) for f in exceeding_functions],
            "message": (f"Found {len(exceeding_functions)} function(s) exceeding thresholds out of {summary['total_functions']} total"),
        }

        if run_id:
            response["storage"] = {"run_id": run_id, "stored_at": stored_at}
        if trends:
            response["trends"] = trends

        return response
