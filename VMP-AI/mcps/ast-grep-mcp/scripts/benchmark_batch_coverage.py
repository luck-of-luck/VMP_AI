#!/usr/bin/env python3
"""Benchmark batch test coverage detection performance.

This script compares the performance of:
1. Legacy sequential test coverage detection
2. Legacy parallel test coverage detection
3. Optimized batch sequential detection
4. Optimized batch parallel detection

Expected Results:
- Batch sequential: 40-50% faster than legacy sequential
- Batch parallel: 60-80% faster than legacy sequential
"""

import argparse
import json
import time
from pathlib import Path
from typing import Callable, Dict, List

from ast_grep_mcp.constants import (
    BenchmarkExpectationDefaults,
    FormattingDefaults,
    ReportingDefaults,
    SemanticSimilarityDefaults,
)
from ast_grep_mcp.features.deduplication.analysis_orchestrator import DeduplicationAnalysisOrchestrator
from ast_grep_mcp.features.deduplication.coverage import CoverageDetector
from ast_grep_mcp.utils.console_logger import console


def create_test_candidates(file_count: int, files_per_candidate: int) -> List[Dict]:
    """Create mock candidates for benchmarking.

    Args:
        file_count: Total number of unique files
        files_per_candidate: Number of files per candidate

    Returns:
        List of candidate dictionaries
    """
    project_root_path = Path(__file__).parent.parent
    src_path = project_root_path / "src" / "ast_grep_mcp"

    # Get actual Python files from the project
    all_files = list(src_path.rglob("*.py"))[:file_count]

    if len(all_files) < file_count:
        console.warning(f"Warning: Only found {len(all_files)} files, requested {file_count}")
        file_count = len(all_files)

    # Create candidates with overlapping files (realistic scenario)
    candidates = []
    for i in range(0, file_count, files_per_candidate):
        file_slice = all_files[i : i + files_per_candidate]
        if file_slice:
            candidates.append(
                {
                    "id": f"candidate_{i}",
                    "files": [str(f) for f in file_slice],
                    "similarity": SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD,
                    "lines_saved": ReportingDefaults.SIGNIFICANT_LINES_SAVED_THRESHOLD,
                }
            )

    return candidates


BENCHMARK_MAX_WORKERS = 4
BENCHMARK_LANGUAGE = "python"


def _run_timed_benchmark(
    method: str,
    candidates: List[Dict],
    action: Callable[[List[Dict]], None],
) -> Dict:
    """Time `action(candidates)` and return the standard benchmark result envelope."""
    start = time.perf_counter()
    action(candidates)
    elapsed = time.perf_counter() - start
    return {
        "method": method,
        "elapsed_seconds": elapsed,
        "candidates": len(candidates),
        "total_files": sum(len(c.get("files", [])) for c in candidates),
    }


def benchmark_legacy_sequential(detector: CoverageDetector, candidates: List[Dict], project_path: str) -> Dict:
    """Benchmark legacy sequential test coverage detection."""
    def action(cs: List[Dict]) -> None:
        for candidate in cs:
            files = candidate.get("files", [])
            if files:
                coverage_map = detector.get_test_coverage_for_files(files, BENCHMARK_LANGUAGE, project_path)
                candidate["test_coverage"] = coverage_map
                candidate["has_tests"] = any(coverage_map.values())

    return _run_timed_benchmark("legacy_sequential", candidates, action)


def benchmark_legacy_parallel(orchestrator: DeduplicationAnalysisOrchestrator, candidates: List[Dict], project_path: str) -> Dict:
    """Benchmark legacy parallel test coverage detection."""
    return _run_timed_benchmark(
        "legacy_parallel",
        candidates,
        lambda cs: orchestrator._add_test_coverage(cs, BENCHMARK_LANGUAGE, project_path, parallel=True, max_workers=BENCHMARK_MAX_WORKERS),
    )


def benchmark_batch_sequential(orchestrator: DeduplicationAnalysisOrchestrator, candidates: List[Dict], project_path: str) -> Dict:
    """Benchmark optimized batch sequential detection."""
    return _run_timed_benchmark(
        "batch_sequential",
        candidates,
        lambda cs: orchestrator._add_test_coverage_batch(cs, BENCHMARK_LANGUAGE, project_path, parallel=False),
    )


def benchmark_batch_parallel(orchestrator: DeduplicationAnalysisOrchestrator, candidates: List[Dict], project_path: str) -> Dict:
    """Benchmark optimized batch parallel detection."""
    return _run_timed_benchmark(
        "batch_parallel",
        candidates,
        lambda cs: orchestrator._add_test_coverage_batch(
            cs, BENCHMARK_LANGUAGE, project_path, parallel=True, max_workers=BENCHMARK_MAX_WORKERS
        ),
    )


def run_benchmark_suite(file_count: int, files_per_candidate: int, project_path: str) -> Dict:
    """Run complete benchmark suite.

    Args:
        file_count: Number of unique files to test
        files_per_candidate: Files per candidate
        project_path: Project root path

    Returns:
        Dictionary with all benchmark results
    """
    console.log(f"\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    console.log(f"Benchmarking with {file_count} files, {files_per_candidate} files/candidate")
    console.log(f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}\n")

    detector = CoverageDetector()
    orchestrator = DeduplicationAnalysisOrchestrator()

    results = {
        "config": {"file_count": file_count, "files_per_candidate": files_per_candidate, "project_path": project_path},
        "benchmarks": [],
    }

    benchmark_plan = [
        ("legacy sequential", benchmark_legacy_sequential, detector),
        ("legacy parallel", benchmark_legacy_parallel, orchestrator),
        ("batch sequential", benchmark_batch_sequential, orchestrator),
        ("batch parallel", benchmark_batch_parallel, orchestrator),
    ]

    for idx, (label, run_benchmark, ctx) in enumerate(benchmark_plan, 1):
        console.log(f"{idx}. Testing {label} method...")
        candidates = create_test_candidates(file_count, files_per_candidate)
        result = run_benchmark(ctx, candidates, project_path)
        results["benchmarks"].append(result)
        console.log(f"   Time: {result['elapsed_seconds']:.3f}s")

    # Calculate speedups
    baseline = results["benchmarks"][0]["elapsed_seconds"]
    console.log(f"\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    console.log("Performance Summary:")
    console.log(f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    for benchmark in results["benchmarks"]:
        speedup = baseline / benchmark["elapsed_seconds"]
        improvement = ((baseline - benchmark["elapsed_seconds"]) / baseline) * 100
        console.log(
            f"{benchmark['method']:25s}: {benchmark['elapsed_seconds']:6.3f}s ({speedup:.2f}x speedup, {improvement:+5.1f}% improvement)"
        )

    results["speedups"] = {
        b["method"]: {
            "speedup": baseline / b["elapsed_seconds"],
            "improvement_percent": ((baseline - b["elapsed_seconds"]) / baseline) * 100,
        }
        for b in results["benchmarks"]
    }

    return results


def main() -> None:
    """Main benchmark runner."""
    parser = argparse.ArgumentParser(description="Benchmark batch test coverage detection performance")
    parser.add_argument("--file-count", type=int, default=50, help="Number of unique files to test (default: 50)")
    parser.add_argument("--files-per-candidate", type=int, default=5, help="Files per candidate (default: 5)")
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    parser.add_argument("--compare", type=str, help="Compare with baseline JSON file")

    args = parser.parse_args()

    project_path = str(Path(__file__).parent.parent)

    # Run benchmarks
    results = run_benchmark_suite(args.file_count, args.files_per_candidate, project_path)

    # Save results if requested
    if args.output:
        output_path = Path(args.output)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        console.log(f"\nResults saved to {output_path}")

    # Compare with baseline if requested
    if args.compare:
        baseline_path = Path(args.compare)
        if baseline_path.exists():
            with open(baseline_path, "r") as f:
                baseline_results = json.load(f)

            console.log(f"\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
            console.log("Comparison with Baseline:")
            console.log(f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")

            for method in ["legacy_sequential", "batch_parallel"]:
                baseline_bench = next((b for b in baseline_results["benchmarks"] if b["method"] == method), None)
                current_bench = next((b for b in results["benchmarks"] if b["method"] == method), None)

                if baseline_bench and current_bench:
                    baseline_time = baseline_bench["elapsed_seconds"]
                    current_time = current_bench["elapsed_seconds"]
                    change = ((current_time - baseline_time) / baseline_time) * 100

                    console.log(f"{method:25s}: {baseline_time:.3f}s -> {current_time:.3f}s ({change:+5.1f}% change)")
        else:
            console.log(f"Baseline file not found: {baseline_path}")

    # Print expected vs actual
    console.log(f"\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")
    console.log("Expected vs Actual Performance:")
    console.log(f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}")

    batch_parallel = next((b for b in results["benchmarks"] if b["method"] == "batch_parallel"), None)

    if batch_parallel:
        speedup = results["speedups"]["batch_parallel"]["speedup"]
        improvement = results["speedups"]["batch_parallel"]["improvement_percent"]

        console.log(
            "Expected: "
            f"{BenchmarkExpectationDefaults.BATCH_PARALLEL_IMPROVEMENT_MIN_PERCENT}-"
            f"{BenchmarkExpectationDefaults.BATCH_PARALLEL_IMPROVEMENT_MAX_PERCENT}% improvement"
        )
        console.log(f"Actual:   {improvement:.1f}% improvement ({speedup:.2f}x speedup)")

        if improvement >= BenchmarkExpectationDefaults.BATCH_PARALLEL_PASS_MIN_PERCENT:
            console.success("✓ PASSED: Performance goal achieved!")
        elif improvement >= BenchmarkExpectationDefaults.BATCH_PARALLEL_PARTIAL_MIN_PERCENT:
            console.log(f"⚠ PARTIAL: Good improvement, but below {BenchmarkExpectationDefaults.BATCH_PARALLEL_PASS_MIN_PERCENT}% target")
        else:
            console.error("✗ FAILED: Performance improvement below expectations")


if __name__ == "__main__":
    main()
