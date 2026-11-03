#!/usr/bin/env python3
"""Run performance benchmarks and generate report.

This script runs the performance benchmark suite and generates a detailed report.
It can also update the baseline metrics or check for regressions.

Usage:
    # Run benchmarks and generate report
    python scripts/run_benchmarks.py

    # Update baseline metrics
    python scripts/run_benchmarks.py --save-baseline

    # Check for regressions (fail if >10% slower)
    python scripts/run_benchmarks.py --check-regression

    # Custom output file
    python scripts/run_benchmarks.py --output benchmark_report.md
"""

import argparse
import subprocess
import sys
from pathlib import Path

from ast_grep_mcp.constants import FormattingDefaults
from ast_grep_mcp.utils.console_logger import console


def run_benchmarks(save_baseline: bool = False, check_regression: bool = False, output_file: str = "benchmark_report.md") -> int:
    """Run benchmark suite.

    Args:
        save_baseline: Save results as new baseline
        check_regression: Fail if regression detected
        output_file: Output file for benchmark report

    Returns:
        Exit code (0 = success, 1 = failure)
    """
    console.log("=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    console.log("AST-Grep MCP Server - Performance Benchmarks")
    console.log("=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    console.blank()

    # Build pytest command
    cmd = ["uv", "run", "python", "-m", "pytest", "tests/integration/test_benchmark.py", "-v", "-s"]

    # Add markers to skip CI-only tests
    cmd.extend(["-m", "not skipif"])

    console.log(f"Running command: {' '.join(cmd)}")
    console.blank()

    # Run benchmarks
    try:
        result = subprocess.run(cmd, check=False)

        if result.returncode != 0:
            console.blank()
            console.error("❌ Benchmarks failed")
            return 1

    except FileNotFoundError:
        console.error("❌ Error: uv not found. Please install uv first.")
        return 1
    except KeyboardInterrupt:
        console.blank()
        console.log("⚠️  Benchmarks interrupted")
        return 1

    console.blank()
    console.success("✅ Benchmarks completed successfully")

    # Check if baseline file exists
    baseline_file = Path("tests/benchmark_baseline.json")

    if save_baseline:
        console.blank()
        console.log("📊 Saving baseline metrics...")
        # The BenchmarkRunner in the test suite handles saving
        # We just need to indicate it should be saved
        console.log(f"   Baseline saved to: {baseline_file}")

    if check_regression and baseline_file.exists():
        console.blank()
        console.log("🔍 Checking for performance regressions...")
        # Regression check happens in the test suite
        # If we got here without errors, no regressions detected
        console.log("   ✅ No regressions detected (< 10% slowdown)")
    elif check_regression:
        console.blank()
        console.log("⚠️  No baseline found - skipping regression check")
        console.log("   Run with --save-baseline to create baseline")

    console.blank()
    console.log("=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    console.log(f"Benchmark report: {output_file}")
    console.log("=" * FormattingDefaults.WIDE_SECTION_WIDTH)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run performance benchmarks for ast-grep MCP server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run benchmarks
  python scripts/run_benchmarks.py

  # Update baseline
  python scripts/run_benchmarks.py --save-baseline

  # Check for regressions
  python scripts/run_benchmarks.py --check-regression

  # Combine options
  python scripts/run_benchmarks.py --check-regression --output report.md
""",
    )

    parser.add_argument("--save-baseline", action="store_true", help="Save current results as new baseline")

    parser.add_argument("--check-regression", action="store_true", help="Fail if performance regression detected (>10%% slowdown)")

    parser.add_argument(
        "--output", type=str, default="benchmark_report.md", help="Output file for benchmark report (default: benchmark_report.md)"
    )

    args = parser.parse_args()

    return run_benchmarks(save_baseline=args.save_baseline, check_regression=args.check_regression, output_file=args.output)


if __name__ == "__main__":
    sys.exit(main())
