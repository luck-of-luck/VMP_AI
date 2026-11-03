#!/usr/bin/env python3
"""
Validate that refactored tests work correctly.

Validation checks:
- Tests collect successfully
- All tests pass
- Same number of tests as before
- Performance within acceptable range
- No new warnings

Usage:
    python tests/scripts/validate_refactoring.py tests/unit/test_cache.py
    python tests/scripts/validate_refactoring.py tests/unit/test_cache.py --baseline baseline.json
    python tests/scripts/validate_refactoring.py tests/unit/test_cache.py --performance
"""

import argparse
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional

from ast_grep_mcp.constants import FormattingDefaults
from ast_grep_mcp.utils.console_logger import console

ALLOWED_PERFORMANCE_SLOWDOWN_FACTOR = 1.2
ALLOWED_PERFORMANCE_SLOWDOWN_PERCENT = 20


@dataclass
class ValidationResult:
    """Result of validation checks."""

    file_path: str
    passed: bool
    checks: Dict[str, bool]
    messages: list[str]
    test_count: int
    pass_count: int
    fail_count: int
    skip_count: int
    duration: float
    warnings: int


class RefactoringValidator:
    """Validate refactored test files."""

    def __init__(self, test_file: Path, baseline: Optional[Dict] = None):
        self.test_file = test_file
        self.baseline = baseline
        self.result = ValidationResult(
            file_path=str(test_file),
            passed=True,
            checks={},
            messages=[],
            test_count=0,
            pass_count=0,
            fail_count=0,
            skip_count=0,
            duration=0.0,
            warnings=0,
        )

    def check_collection(self) -> bool:
        """Check that tests collect successfully."""
        try:
            result = subprocess.run(["pytest", str(self.test_file), "--collect-only", "-q"], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                # Count collected tests
                output = result.stdout
                for line in output.splitlines():
                    if "test session starts" in line.lower():
                        continue
                    if line.strip().startswith("test_"):
                        self.result.test_count += 1

                self.result.checks["collection"] = True
                self.result.messages.append(f"✓ Collection: {self.result.test_count} tests collected")
                return True
            else:
                self.result.checks["collection"] = False
                self.result.passed = False
                self.result.messages.append(f"✗ Collection failed: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            self.result.checks["collection"] = False
            self.result.passed = False
            self.result.messages.append("✗ Collection timeout")
            return False
        except Exception as e:
            self.result.checks["collection"] = False
            self.result.passed = False
            self.result.messages.append(f"✗ Collection error: {e}")
            return False

    def check_execution(self) -> bool:
        """Check that tests execute successfully."""
        try:
            start = time.time()
            result = subprocess.run(["pytest", str(self.test_file), "-v", "--tb=short"], capture_output=True, text=True, timeout=120)
            self.result.duration = time.time() - start

            # Parse output
            output = result.stdout + result.stderr

            # Count results
            for line in output.splitlines():
                if " PASSED" in line:
                    self.result.pass_count += 1
                elif " FAILED" in line:
                    self.result.fail_count += 1
                elif " SKIPPED" in line:
                    self.result.skip_count += 1
                elif "warning" in line.lower():
                    self.result.warnings += 1

            if result.returncode == 0:
                self.result.checks["execution"] = True
                self.result.messages.append(
                    f"✓ Execution: {self.result.pass_count} passed, {self.result.fail_count} failed, {self.result.skip_count} skipped"
                )
                return True
            else:
                self.result.checks["execution"] = False
                self.result.passed = False
                self.result.messages.append(f"✗ Execution failed: {self.result.pass_count} passed, {self.result.fail_count} failed")

                # Show failures
                for line in output.splitlines():
                    if "FAILED" in line or "ERROR" in line:
                        self.result.messages.append(f"  {line}")

                return False

        except subprocess.TimeoutExpired:
            self.result.checks["execution"] = False
            self.result.passed = False
            self.result.messages.append("✗ Execution timeout (>120s)")
            return False
        except Exception as e:
            self.result.checks["execution"] = False
            self.result.passed = False
            self.result.messages.append(f"✗ Execution error: {e}")
            return False

    def check_baseline(self) -> bool:
        """Check against baseline if provided."""
        if not self.baseline:
            self.result.checks["baseline"] = True
            self.result.messages.append("⊘ Baseline: No baseline provided")
            return True

        baseline_count = self.baseline.get("test_count", 0)

        if self.result.test_count == baseline_count:
            self.result.checks["baseline"] = True
            self.result.messages.append(f"✓ Baseline: Same test count ({baseline_count})")
            return True
        else:
            self.result.checks["baseline"] = False
            self.result.passed = False
            self.result.messages.append(f"✗ Baseline: Test count changed (was {baseline_count}, now {self.result.test_count})")
            return False

    def check_performance(self) -> bool:
        """Check performance against baseline."""
        if not self.baseline:
            self.result.checks["performance"] = True
            self.result.messages.append(f"⊘ Performance: {self.result.duration:.2f}s (no baseline)")
            return True

        baseline_duration = self.baseline.get("duration", 0.0)
        if baseline_duration == 0.0:
            self.result.checks["performance"] = True
            self.result.messages.append(f"⊘ Performance: {self.result.duration:.2f}s (no baseline)")
            return True

        # Allow bounded slowdown versus baseline.
        threshold = baseline_duration * ALLOWED_PERFORMANCE_SLOWDOWN_FACTOR

        if self.result.duration <= threshold:
            percent_change = ((self.result.duration - baseline_duration) / baseline_duration) * 100
            self.result.checks["performance"] = True
            self.result.messages.append(
                f"✓ Performance: {self.result.duration:.2f}s (baseline: {baseline_duration:.2f}s, {percent_change:+.1f}%)"
            )
            return True
        else:
            percent_change = ((self.result.duration - baseline_duration) / baseline_duration) * 100
            self.result.checks["performance"] = False
            self.result.passed = False
            self.result.messages.append(
                f"✗ Performance: {self.result.duration:.2f}s "
                f"(baseline: {baseline_duration:.2f}s, {percent_change:+.1f}% - exceeded {ALLOWED_PERFORMANCE_SLOWDOWN_PERCENT}% threshold)"
            )
            return False

    def check_warnings(self) -> bool:
        """Check for new warnings."""
        if not self.baseline:
            self.result.checks["warnings"] = True
            self.result.messages.append(f"⊘ Warnings: {self.result.warnings} warnings (no baseline)")
            return True

        baseline_warnings = self.baseline.get("warnings", 0)

        if self.result.warnings <= baseline_warnings:
            self.result.checks["warnings"] = True
            self.result.messages.append(f"✓ Warnings: {self.result.warnings} warnings (baseline: {baseline_warnings})")
            return True
        else:
            # Allow warnings, just warn user
            self.result.checks["warnings"] = True
            self.result.messages.append(
                f"⚠ Warnings: {self.result.warnings} warnings "
                f"(baseline: {baseline_warnings}, increased by {self.result.warnings - baseline_warnings})"
            )
            return True

    def validate(self, check_performance: bool = False) -> ValidationResult:
        """Run all validation checks."""
        # Collection
        if not self.check_collection():
            return self.result

        # Execution
        if not self.check_execution():
            return self.result

        # Baseline
        self.check_baseline()

        # Performance (optional)
        if check_performance:
            self.check_performance()

        # Warnings
        self.check_warnings()

        return self.result


def format_result_report(result: ValidationResult) -> str:
    """Format validation result as readable report."""
    lines = []

    lines.append("=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    lines.append("REFACTORING VALIDATION RESULT")
    lines.append("=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    lines.append(f"File: {result.file_path}")
    lines.append("")

    # Overall status
    if result.passed:
        lines.append("✓ VALIDATION PASSED")
    else:
        lines.append("✗ VALIDATION FAILED")
    lines.append("")

    # Checks
    lines.append("CHECKS:")
    lines.append("-" * FormattingDefaults.WIDE_SECTION_WIDTH)
    for message in result.messages:
        lines.append(message)
    lines.append("")

    # Summary
    lines.append("SUMMARY:")
    lines.append("-" * FormattingDefaults.WIDE_SECTION_WIDTH)
    lines.append(f"Tests collected: {result.test_count}")
    lines.append(f"Tests passed: {result.pass_count}")
    lines.append(f"Tests failed: {result.fail_count}")
    lines.append(f"Tests skipped: {result.skip_count}")
    lines.append(f"Duration: {result.duration:.2f}s")
    lines.append(f"Warnings: {result.warnings}")
    lines.append("=" * FormattingDefaults.WIDE_SECTION_WIDTH)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Validate refactored test file")
    parser.add_argument("file", help="Test file to validate")
    parser.add_argument("--baseline", help="Baseline JSON file for comparison")
    parser.add_argument("--performance", action="store_true", help="Check performance")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--save-baseline", help="Save results as new baseline")
    args = parser.parse_args()

    # Load baseline if provided
    baseline = None
    if args.baseline:
        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            with open(baseline_path) as f:
                baseline = json.load(f)

    # Validate
    test_file = Path(args.file)
    if not test_file.exists():
        console.error(f"Error: File not found: {test_file}")
        return 1

    validator = RefactoringValidator(test_file, baseline)
    result = validator.validate(check_performance=args.performance or args.baseline is not None)

    # Save baseline if requested
    if args.save_baseline:
        baseline_data = {
            "file_path": result.file_path,
            "test_count": result.test_count,
            "pass_count": result.pass_count,
            "duration": result.duration,
            "warnings": result.warnings,
        }
        with open(args.save_baseline, "w") as f:
            json.dump(baseline_data, f, indent=2)

    # Output
    if args.json:
        console.json(asdict(result))
    else:
        console.log(format_result_report(result))

    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
