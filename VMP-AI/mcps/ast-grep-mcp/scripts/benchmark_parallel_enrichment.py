#!/usr/bin/env python3
"""Benchmark parallel vs sequential enrichment performance."""

import time
from typing import Any, Dict, List

from ast_grep_mcp.constants import FormattingDefaults, ReportingDefaults
from ast_grep_mcp.utils.console_logger import console

MOCK_CANDIDATE_SCORE = 75.5
MOCK_CANDIDATE_COMPLEXITY = 8
BENCHMARK_CANDIDATE_COUNT_SMALL = 10
BENCHMARK_CANDIDATE_COUNT_MEDIUM = 25
BENCHMARK_CANDIDATE_COUNT_LARGE = 50
BENCHMARK_CANDIDATE_COUNT_XLARGE = 100
BENCHMARK_CANDIDATE_COUNTS = [
    BENCHMARK_CANDIDATE_COUNT_SMALL,
    BENCHMARK_CANDIDATE_COUNT_MEDIUM,
    BENCHMARK_CANDIDATE_COUNT_LARGE,
    BENCHMARK_CANDIDATE_COUNT_XLARGE,
]


# Mock data for benchmarking
def create_mock_candidates(count: int) -> List[Dict[str, Any]]:
    """Create mock candidates for benchmarking."""

    return [
        {
            "group_id": i,
            "files": [f"file_{i}_1.py", f"file_{i}_2.py"],
            "lines_saved": ReportingDefaults.SIGNIFICANT_LINES_SAVED_THRESHOLD,
            "score": MOCK_CANDIDATE_SCORE,
            "complexity_score": MOCK_CANDIDATE_COMPLEXITY,
            "has_tests": False,
        }
        for i in range(count)
    ]


def benchmark_enrichment():
    """Benchmark parallel vs sequential enrichment."""
    from ast_grep_mcp.features.deduplication.analysis_orchestrator import DeduplicationAnalysisOrchestrator

    orchestrator = DeduplicationAnalysisOrchestrator()

    # Test with different candidate counts
    candidate_counts = BENCHMARK_CANDIDATE_COUNTS

    console.log("=" * FormattingDefaults.SEPARATOR_LENGTH)
    console.log("Parallel vs Sequential Enrichment Benchmark")
    console.log("=" * FormattingDefaults.SEPARATOR_LENGTH)
    console.blank()

    for count in candidate_counts:
        candidates = create_mock_candidates(count)

        # Sequential execution
        start = time.perf_counter()
        orchestrator._add_test_coverage(candidates.copy(), "python", "/tmp/test", parallel=False)
        orchestrator._add_recommendations(candidates.copy(), parallel=False)
        sequential_time = time.perf_counter() - start

        # Parallel execution
        candidates = create_mock_candidates(count)
        start = time.perf_counter()
        orchestrator._add_test_coverage(candidates.copy(), "python", "/tmp/test", parallel=True)
        orchestrator._add_recommendations(candidates.copy(), parallel=True)
        parallel_time = time.perf_counter() - start

        # Calculate speedup
        speedup = sequential_time / parallel_time if parallel_time > 0 else 0
        improvement = ((sequential_time - parallel_time) / sequential_time * 100) if sequential_time > 0 else 0

        console.log(f"Candidates: {count}")
        console.log(f"  Sequential: {sequential_time * 1000:.2f}ms")
        console.log(f"  Parallel:   {parallel_time * 1000:.2f}ms")
        console.log(f"  Speedup:    {speedup:.2f}x")
        console.log(f"  Improvement: {improvement:.1f}%")
        console.blank()

    console.log("=" * FormattingDefaults.SEPARATOR_LENGTH)
    console.log("Note: Actual speedup depends on I/O operations and CPU cores.")
    console.log("=" * FormattingDefaults.SEPARATOR_LENGTH)


if __name__ == "__main__":
    benchmark_enrichment()
