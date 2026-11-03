#!/usr/bin/env python3
"""
Track fixture adoption and usage metrics.

Metrics tracked:
- Fixture adoption rate (% of tests using fixtures)
- Per-fixture usage counts
- Test files by category (fixture-based, setup_method, mixed)
- Trend tracking over time

Usage:
    python tests/scripts/track_fixture_metrics.py
    python tests/scripts/track_fixture_metrics.py --detailed
    python tests/scripts/track_fixture_metrics.py --history
    python tests/scripts/track_fixture_metrics.py --json
"""

import argparse
import ast
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

from ast_grep_mcp.constants import FormattingDefaults
from ast_grep_mcp.utils.console_logger import console


@dataclass
class FixtureUsageMetrics:
    """Metrics for fixture usage."""

    fixture_name: str
    usage_count: int
    files_used_in: List[str]
    tests_using_it: int


@dataclass
class TestFileCategory:
    """Categorize test files by testing approach."""

    fixture_based: List[str]  # Uses only fixtures
    setup_method_based: List[str]  # Uses setup_method
    mixed: List[str]  # Uses both
    neither: List[str]  # Uses neither (simple tests)


@dataclass
class AdoptionMetrics:
    """Overall fixture adoption metrics."""

    date: str
    total_test_files: int
    total_test_functions: int
    tests_using_fixtures: int
    tests_using_setup_method: int
    fixture_adoption_rate: float  # Percentage
    fixture_usage: Dict[str, int]  # fixture_name -> usage_count
    file_categories: TestFileCategory


class FixtureMetricsTracker:
    """Track fixture usage metrics across test suite."""

    def __init__(self, root: Path):
        self.root = root
        self.test_files: List[Path] = []
        self.fixture_usage: Dict[str, FixtureUsageMetrics] = {}
        self.test_file_categories = TestFileCategory([], [], [], [])

    def find_test_files(self) -> List[Path]:
        """Find all test files."""
        test_files = []

        # Unit tests
        unit_dir = self.root / "tests" / "unit"
        if unit_dir.exists():
            test_files.extend(sorted(unit_dir.glob("test_*.py")))

        # Integration tests
        integration_dir = self.root / "tests" / "integration"
        if integration_dir.exists():
            test_files.extend(sorted(integration_dir.glob("test_*.py")))

        self.test_files = test_files
        return test_files

    def extract_fixtures_from_conftest(self) -> Set[str]:
        """Extract fixture names from conftest.py."""
        conftest = self.root / "tests" / "conftest.py"
        if not conftest.exists():
            return set()

        fixtures = set()
        try:
            tree = ast.parse(conftest.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check for @pytest.fixture decorator
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Name) and decorator.id == "fixture":
                            fixtures.add(node.name)
                        elif isinstance(decorator, ast.Attribute):
                            if decorator.attr == "fixture":
                                fixtures.add(node.name)
                        elif isinstance(decorator, ast.Call):
                            if isinstance(decorator.func, ast.Name) and decorator.func.id == "fixture":
                                fixtures.add(node.name)
                            elif isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "fixture":
                                fixtures.add(node.name)
        except SyntaxError:
            pass

        return fixtures

    def analyze_test_file(self, file_path: Path, known_fixtures: Set[str]) -> Dict[str, any]:
        """Analyze a single test file."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except SyntaxError:
            return {"test_count": 0, "fixtures_used": set(), "has_setup_method": False, "category": "neither"}

        test_count = 0
        fixtures_used = set()
        has_setup_method = False

        # Find test functions and their fixtures
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("test_"):
                    test_count += 1

                    # Check parameters for fixtures
                    for arg in node.args.args:
                        if arg.arg in known_fixtures:
                            fixtures_used.add(arg.arg)

                elif node.name == "setup_method":
                    has_setup_method = True

        # Categorize file
        if fixtures_used and not has_setup_method:
            category = "fixture_based"
        elif has_setup_method and not fixtures_used:
            category = "setup_method_based"
        elif fixtures_used and has_setup_method:
            category = "mixed"
        else:
            category = "neither"

        return {"test_count": test_count, "fixtures_used": fixtures_used, "has_setup_method": has_setup_method, "category": category}

    def track_metrics(self) -> AdoptionMetrics:
        """Track current fixture adoption metrics."""
        self.find_test_files()
        known_fixtures = self.extract_fixtures_from_conftest()

        total_test_functions = 0
        tests_using_fixtures = 0
        tests_using_setup_method = 0
        fixture_usage_counts: Dict[str, int] = defaultdict(int)
        fixture_files: Dict[str, List[str]] = defaultdict(list)

        for test_file in self.test_files:
            analysis = self.analyze_test_file(test_file, known_fixtures)

            total_test_functions += analysis["test_count"]

            # Track fixture usage
            if analysis["fixtures_used"]:
                tests_using_fixtures += analysis["test_count"]
                for fixture in analysis["fixtures_used"]:
                    fixture_usage_counts[fixture] += analysis["test_count"]
                    fixture_files[fixture].append(str(test_file.name))

            # Track setup_method usage
            if analysis["has_setup_method"]:
                tests_using_setup_method += analysis["test_count"]

            # Categorize file
            category = analysis["category"]
            file_name = str(test_file.name)
            if category == "fixture_based":
                self.test_file_categories.fixture_based.append(file_name)
            elif category == "setup_method_based":
                self.test_file_categories.setup_method_based.append(file_name)
            elif category == "mixed":
                self.test_file_categories.mixed.append(file_name)
            else:
                self.test_file_categories.neither.append(file_name)

        # Build fixture usage details
        for fixture_name, count in fixture_usage_counts.items():
            self.fixture_usage[fixture_name] = FixtureUsageMetrics(
                fixture_name=fixture_name, usage_count=count, files_used_in=fixture_files[fixture_name], tests_using_it=count
            )

        # Calculate adoption rate
        if total_test_functions > 0:
            adoption_rate = (tests_using_fixtures / total_test_functions) * 100
        else:
            adoption_rate = 0.0

        return AdoptionMetrics(
            date=datetime.now().isoformat(),
            total_test_files=len(self.test_files),
            total_test_functions=total_test_functions,
            tests_using_fixtures=tests_using_fixtures,
            tests_using_setup_method=tests_using_setup_method,
            fixture_adoption_rate=round(adoption_rate, 1),
            fixture_usage=dict(fixture_usage_counts),
            file_categories=self.test_file_categories,
        )


def save_metrics_history(metrics: AdoptionMetrics, history_file: Path):
    """Append metrics to history file."""
    history = []

    if history_file.exists():
        try:
            with open(history_file) as f:
                history = json.load(f)
        except json.JSONDecodeError:
            pass

    history.append(asdict(metrics))

    with open(history_file, "w") as f:
        json.dump(history, f, indent=2)


def format_metrics_report(metrics: AdoptionMetrics, detailed: bool = False) -> str:
    """Format metrics as readable report."""
    lines = []

    lines.append("=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    lines.append("FIXTURE ADOPTION METRICS")
    lines.append("=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    lines.append(f"Date: {metrics.date}")
    lines.append("")

    # Overall stats
    lines.append("OVERALL STATISTICS")
    lines.append("-" * FormattingDefaults.WIDE_SECTION_WIDTH)
    lines.append(f"Total test files: {metrics.total_test_files}")
    lines.append(f"Total test functions: {metrics.total_test_functions}")
    lines.append(f"Tests using fixtures: {metrics.tests_using_fixtures}")
    lines.append(f"Tests using setup_method: {metrics.tests_using_setup_method}")
    lines.append(f"Fixture adoption rate: {metrics.fixture_adoption_rate}%")
    lines.append("")

    # File categories
    lines.append("FILE CATEGORIES")
    lines.append("-" * FormattingDefaults.WIDE_SECTION_WIDTH)
    lines.append(f"Fixture-based: {len(metrics.file_categories.fixture_based)} files")
    lines.append(f"Setup-method-based: {len(metrics.file_categories.setup_method_based)} files")
    lines.append(f"Mixed: {len(metrics.file_categories.mixed)} files")
    lines.append(f"Neither: {len(metrics.file_categories.neither)} files")
    lines.append("")

    # Top fixtures
    lines.append("TOP 10 MOST-USED FIXTURES")
    lines.append("-" * FormattingDefaults.WIDE_SECTION_WIDTH)
    sorted_fixtures = sorted(metrics.fixture_usage.items(), key=lambda x: x[1], reverse=True)
    for fixture, count in sorted_fixtures[:10]:
        lines.append(f"{fixture:<30} {count:>5} uses")
    lines.append("")

    if detailed:
        # Detailed breakdown
        lines.append("DETAILED FIXTURE USAGE")
        lines.append("-" * FormattingDefaults.WIDE_SECTION_WIDTH)
        for fixture, count in sorted_fixtures:
            lines.append(f"\n{fixture}: {count} uses")

        lines.append("\n\nFIXTURE-BASED FILES")
        lines.append("-" * FormattingDefaults.WIDE_SECTION_WIDTH)
        for file in sorted(metrics.file_categories.fixture_based):
            lines.append(f"  ✓ {file}")

        lines.append("\n\nSETUP-METHOD-BASED FILES")
        lines.append("-" * FormattingDefaults.WIDE_SECTION_WIDTH)
        for file in sorted(metrics.file_categories.setup_method_based):
            lines.append(f"  ✗ {file}")

        lines.append("\n\nMIXED FILES (needs migration)")
        lines.append("-" * FormattingDefaults.WIDE_SECTION_WIDTH)
        for file in sorted(metrics.file_categories.mixed):
            lines.append(f"  ~ {file}")

    lines.append("=" * FormattingDefaults.WIDE_SECTION_WIDTH)

    return "\n".join(lines)


def format_history_report(history: List[Dict]) -> str:
    """Format metrics history as trend report."""
    if not history:
        return "No historical data available."

    lines = []
    lines.append("=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    lines.append("FIXTURE ADOPTION TREND")
    lines.append("=" * FormattingDefaults.WIDE_SECTION_WIDTH)
    lines.append("")

    # Extract trend data
    lines.append(f"{'Date':<20} {'Tests':<8} {'Fixtures':<10} {'Adoption':<10} {'Change':<10}")
    lines.append("-" * FormattingDefaults.WIDE_SECTION_WIDTH)

    prev_rate = None
    for entry in history:
        date = entry["date"][:10]  # Just date, not time
        total = entry["total_test_functions"]
        using_fixtures = entry["tests_using_fixtures"]
        rate = entry["fixture_adoption_rate"]

        if prev_rate is not None:
            change = rate - prev_rate
            change_str = f"{change:+.1f}%"
        else:
            change_str = "-"

        lines.append(f"{date:<20} {total:<8} {using_fixtures:<10} {rate:<10.1f}% {change_str:<10}")
        prev_rate = rate

    lines.append("=" * FormattingDefaults.WIDE_SECTION_WIDTH)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Track fixture adoption metrics")
    parser.add_argument("--detailed", action="store_true", help="Show detailed breakdown")
    parser.add_argument("--history", action="store_true", help="Show historical trend")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--save", action="store_true", help="Save to history file")
    args = parser.parse_args()

    # Find root directory
    root = Path(__file__).parent.parent.parent

    # Track current metrics
    tracker = FixtureMetricsTracker(root)
    metrics = tracker.track_metrics()

    # Save to history if requested
    history_file = root / "tests" / "fixture_metrics_history.json"
    if args.save:
        save_metrics_history(metrics, history_file)

    # Output
    if args.json:
        console.json(asdict(metrics))
    elif args.history:
        if history_file.exists():
            with open(history_file) as f:
                history = json.load(f)
            console.log(format_history_report(history))
        else:
            console.log("No historical data available. Run with --save to start tracking.")
    else:
        console.log(format_metrics_report(metrics, detailed=args.detailed))

    return 0


if __name__ == "__main__":
    exit(main())
