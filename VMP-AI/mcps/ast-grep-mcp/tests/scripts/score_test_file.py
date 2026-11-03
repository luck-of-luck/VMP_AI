#!/usr/bin/env python3
"""
Score test files for fixture migration priority.

Scoring system (0-100):
- Pain Points (40%): Maintenance burden, flakiness, duplication
- Opportunity (35%): Lines saved, complexity reduction, fixture reusability
- Risk (15% inverse): Test count, self-attributes, external dependencies
- Alignment (10%): Existing feature work, team familiarity

Usage:
    python tests/scripts/score_test_file.py tests/unit/test_cache.py
    python tests/scripts/score_test_file.py --all
    python tests/scripts/score_test_file.py --all --json > scores.json
"""

import argparse
import ast
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

from ast_grep_mcp.utils.console_logger import console


@dataclass
class TestFileMetrics:
    """Metrics collected from a test file."""

    file_path: str
    total_lines: int
    test_count: int
    class_count: int
    setup_method_count: int
    teardown_method_count: int
    setup_lines: int
    teardown_lines: int
    self_attribute_count: int
    temp_dir_usage: int
    mock_usage: int
    fixture_usage: int
    duplication_score: float  # 0-10
    complexity_score: float  # 0-10


@dataclass
class RefactoringScore:
    """Refactoring priority score with breakdown."""

    file_path: str
    total_score: float  # 0-100
    pain_points: float  # 0-40
    opportunity: float  # 0-35
    risk: float  # 0-15 (inverse)
    alignment: float  # 0-10
    recommendation: str
    metrics: TestFileMetrics


class TestFileAnalyzer:
    """Analyze test files for refactoring priority."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.content = file_path.read_text()
        self.lines = self.content.splitlines()
        try:
            self.tree = ast.parse(self.content)
        except SyntaxError:
            self.tree = None

    def analyze(self) -> TestFileMetrics:
        """Analyze test file and collect metrics."""
        if self.tree is None:
            return self._empty_metrics()

        # Compute basic metrics first
        test_count = self._count_test_functions()
        class_count = self._count_test_classes()
        setup_method_count = self._count_setup_methods()
        teardown_method_count = self._count_teardown_methods()
        setup_lines = self._count_setup_lines()
        teardown_lines = self._count_teardown_lines()
        self_attribute_count = self._count_self_attributes()
        temp_dir_usage = self._count_pattern(r"tempfile\.mkdtemp|TemporaryDirectory")
        mock_usage = self._count_pattern(r"@patch|@mock|Mock\(|MagicMock\(")
        fixture_usage = self._count_fixture_usage()

        metrics = TestFileMetrics(
            file_path=str(self.file_path),
            total_lines=len(self.lines),
            test_count=test_count,
            class_count=class_count,
            setup_method_count=setup_method_count,
            teardown_method_count=teardown_method_count,
            setup_lines=setup_lines,
            teardown_lines=teardown_lines,
            self_attribute_count=self_attribute_count,
            temp_dir_usage=temp_dir_usage,
            mock_usage=mock_usage,
            fixture_usage=fixture_usage,
            duplication_score=self._calculate_duplication_score(temp_dir_usage, mock_usage, class_count, setup_method_count),
            complexity_score=self._calculate_complexity_score(setup_lines, self_attribute_count, class_count, mock_usage),
        )

        return metrics

    def _empty_metrics(self) -> TestFileMetrics:
        """Return empty metrics for unparseable files."""
        return TestFileMetrics(
            file_path=str(self.file_path),
            total_lines=len(self.lines),
            test_count=0,
            class_count=0,
            setup_method_count=0,
            teardown_method_count=0,
            setup_lines=0,
            teardown_lines=0,
            self_attribute_count=0,
            temp_dir_usage=0,
            mock_usage=0,
            fixture_usage=0,
            duplication_score=0.0,
            complexity_score=0.0,
        )

    def _count_test_functions(self) -> int:
        """Count test functions (def test_*)."""
        count = 0
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                count += 1
        return count

    def _count_test_classes(self) -> int:
        """Count test classes (class Test*)."""
        count = 0
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                count += 1
        return count

    def _count_setup_methods(self) -> int:
        """Count setup_method definitions."""
        count = 0
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "setup_method":
                count += 1
        return count

    def _count_teardown_methods(self) -> int:
        """Count teardown_method definitions."""
        count = 0
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "teardown_method":
                count += 1
        return count

    def _count_setup_lines(self) -> int:
        """Count lines of code in setup_method functions."""
        lines = 0
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "setup_method":
                # Count non-empty, non-comment lines
                start = node.lineno
                end = node.end_lineno or start
                for i in range(start, end + 1):
                    if i <= len(self.lines):
                        line = self.lines[i - 1].strip()
                        if line and not line.startswith("#") and not line.startswith('"""'):
                            lines += 1
        return lines

    def _count_teardown_lines(self) -> int:
        """Count lines of code in teardown_method functions."""
        lines = 0
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "teardown_method":
                start = node.lineno
                end = node.end_lineno or start
                for i in range(start, end + 1):
                    if i <= len(self.lines):
                        line = self.lines[i - 1].strip()
                        if line and not line.startswith("#") and not line.startswith('"""'):
                            lines += 1
        return lines

    def _count_self_attributes(self) -> int:
        """Count unique self.attribute assignments in setup_method."""
        attributes = set()

        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name == "setup_method":
                # Find all self.attribute assignments
                for child in ast.walk(node):
                    if isinstance(child, ast.Assign):
                        for target in child.targets:
                            if isinstance(target, ast.Attribute):
                                if isinstance(target.value, ast.Name) and target.value.id == "self":
                                    attributes.add(target.attr)

        return len(attributes)

    def _count_pattern(self, pattern: str) -> int:
        """Count occurrences of regex pattern."""
        return len(re.findall(pattern, self.content))

    def _count_fixture_usage(self) -> int:
        """Count fixture parameters in test functions."""
        fixture_count = 0
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                # Count parameters (excluding self)
                params = [arg.arg for arg in node.args.args if arg.arg != "self"]
                fixture_count += len(params)
        return fixture_count

    def _calculate_duplication_score(self, temp_dir_usage: int, mock_usage: int, class_count: int, setup_method_count: int) -> float:
        """Calculate duplication score (0-10, higher = more duplication)."""
        score = 0.0

        # Check for repeated patterns
        if temp_dir_usage > 1:
            score += min(3.0, temp_dir_usage * 0.5)

        # Check for repeated mock setups
        if mock_usage > 3:
            score += min(3.0, (mock_usage - 3) * 0.3)

        # Check for repeated file creation
        file_creation = self._count_pattern(r'open\([^)]+,\s*["\']w["\']')
        if file_creation > 2:
            score += min(2.0, file_creation * 0.3)

        # Check for similar setup_method code across classes
        if class_count > 1 and setup_method_count > 1:
            score += min(2.0, setup_method_count * 0.5)

        return min(10.0, score)

    def _calculate_complexity_score(self, setup_lines: int, self_attribute_count: int, class_count: int, mock_usage: int) -> float:
        """Calculate complexity score (0-10, higher = more complex)."""
        score = 0.0

        # Long setup methods
        if setup_lines > 20:
            score += min(3.0, (setup_lines - 20) * 0.15)
        elif setup_lines > 10:
            score += min(2.0, (setup_lines - 10) * 0.1)

        # Many self attributes
        if self_attribute_count > 10:
            score += min(3.0, (self_attribute_count - 10) * 0.2)
        elif self_attribute_count > 5:
            score += min(2.0, (self_attribute_count - 5) * 0.2)

        # Multiple test classes
        if class_count > 3:
            score += min(2.0, (class_count - 3) * 0.5)

        # Heavy mocking
        if mock_usage > 10:
            score += min(2.0, (mock_usage - 10) * 0.1)

        return min(10.0, score)


class RefactoringScorer:
    """Calculate refactoring priority scores."""

    def score(self, metrics: TestFileMetrics) -> RefactoringScore:
        """Calculate total score (0-100) with breakdown."""
        pain_points = self._calculate_pain_points(metrics)
        opportunity = self._calculate_opportunity(metrics)
        risk = self._calculate_risk(metrics)
        alignment = self._calculate_alignment(metrics)

        total = pain_points + opportunity + risk + alignment
        recommendation = self._get_recommendation(total, metrics)

        return RefactoringScore(
            file_path=metrics.file_path,
            total_score=round(total, 1),
            pain_points=round(pain_points, 1),
            opportunity=round(opportunity, 1),
            risk=round(risk, 1),
            alignment=round(alignment, 1),
            recommendation=recommendation,
            metrics=metrics,
        )

    def _calculate_pain_points(self, m: TestFileMetrics) -> float:
        """Calculate pain points score (0-40)."""
        score = 0.0

        # Maintenance burden (0-15): More setup/teardown = higher burden
        setup_teardown_lines = m.setup_lines + m.teardown_lines
        score += min(15.0, setup_teardown_lines * 0.5)

        # Duplication (0-15): More duplication = higher pain
        score += m.duplication_score * 1.5

        # Complexity (0-10): More complexity = harder to maintain
        score += m.complexity_score

        return min(40.0, score)

    def _calculate_opportunity(self, m: TestFileMetrics) -> float:
        """Calculate opportunity score (0-35)."""
        score = 0.0

        # Lines saved (0-15): More setup/teardown = more lines to save
        setup_teardown_lines = m.setup_lines + m.teardown_lines
        if setup_teardown_lines > 50:
            score += 15.0
        elif setup_teardown_lines > 30:
            score += 12.0
        elif setup_teardown_lines > 15:
            score += 8.0
        elif setup_teardown_lines > 5:
            score += 4.0

        # Fixture reusability (0-10): Many tests = more reuse
        if m.test_count > 30:
            score += 10.0
        elif m.test_count > 20:
            score += 7.0
        elif m.test_count > 10:
            score += 5.0
        elif m.test_count > 5:
            score += 3.0

        # Complexity reduction (0-10): Higher complexity = more to gain
        score += m.complexity_score

        return min(35.0, score)

    def _calculate_risk(self, m: TestFileMetrics) -> float:
        """Calculate risk score (0-15, higher = lower risk)."""
        risk_penalty = 0.0

        # Many tests = higher risk of breaking something
        if m.test_count > 50:
            risk_penalty += 5.0
        elif m.test_count > 30:
            risk_penalty += 3.0
        elif m.test_count > 15:
            risk_penalty += 1.0

        # Many self attributes = harder to refactor
        if m.self_attribute_count > 15:
            risk_penalty += 5.0
        elif m.self_attribute_count > 10:
            risk_penalty += 3.0
        elif m.self_attribute_count > 5:
            risk_penalty += 1.0

        # Already using fixtures = lower risk
        if m.fixture_usage > 0:
            risk_penalty -= min(3.0, m.fixture_usage * 0.5)

        # Heavy mocking = external dependencies = higher risk
        if m.mock_usage > 20:
            risk_penalty += 2.0
        elif m.mock_usage > 10:
            risk_penalty += 1.0

        # Convert penalty to score (inverse)
        return max(0.0, 15.0 - risk_penalty)

    def _calculate_alignment(self, m: TestFileMetrics) -> float:
        """Calculate alignment score (0-10)."""
        score = 0.0

        # Already has setup_method = easier to convert
        if m.setup_method_count > 0:
            score += 5.0

        # Uses temp_dir = aligns with existing fixtures
        if m.temp_dir_usage > 0:
            score += 3.0

        # Multiple classes = good opportunity for class fixtures
        if m.class_count > 1:
            score += 2.0

        return min(10.0, score)

    def _get_recommendation(self, score: float, m: TestFileMetrics) -> str:
        """Get refactoring recommendation based on score."""
        if score >= 70:
            return "HIGH PRIORITY - Refactor soon (high value, manageable risk)"
        elif score >= 55:
            return "MEDIUM PRIORITY - Refactor when touching file"
        elif score >= 40:
            return "LOW PRIORITY - Refactor opportunistically"
        elif score >= 25:
            return "DEFER - Keep using setup_method for now"
        else:
            return "SKIP - Not worth refactoring (low value or high risk)"


def analyze_test_file(file_path: Path) -> RefactoringScore:
    """Analyze a test file and return refactoring score."""
    analyzer = TestFileAnalyzer(file_path)
    metrics = analyzer.analyze()
    scorer = RefactoringScorer()
    return scorer.score(metrics)


def find_test_files(root: Path) -> List[Path]:
    """Find all test files in project."""
    test_files = []

    # Find unit tests
    unit_dir = root / "tests" / "unit"
    if unit_dir.exists():
        test_files.extend(sorted(unit_dir.glob("test_*.py")))

    # Find integration tests
    integration_dir = root / "tests" / "integration"
    if integration_dir.exists():
        test_files.extend(sorted(integration_dir.glob("test_*.py")))

    return test_files


def format_score_table(scores: List[RefactoringScore]) -> str:
    """Format scores as a text table."""
    lines = []
    lines.append("=" * 120)
    lines.append(f"{'File':<40} {'Score':<8} {'Pain':<6} {'Opp':<6} {'Risk':<6} {'Align':<6} {'Recommendation':<30}")
    lines.append("=" * 120)

    for score in sorted(scores, key=lambda s: s.total_score, reverse=True):
        file_name = Path(score.file_path).name
        lines.append(
            f"{file_name:<40} "
            f"{score.total_score:<8.1f} "
            f"{score.pain_points:<6.1f} "
            f"{score.opportunity:<6.1f} "
            f"{score.risk:<6.1f} "
            f"{score.alignment:<6.1f} "
            f"{score.recommendation:<30}"
        )

    lines.append("=" * 120)
    lines.append(f"\nTotal files: {len(scores)}")
    lines.append(f"High priority (≥70): {len([s for s in scores if s.total_score >= 70])}")
    lines.append(f"Medium priority (55-69): {len([s for s in scores if 55 <= s.total_score < 70])}")
    lines.append(f"Low priority (40-54): {len([s for s in scores if 40 <= s.total_score < 55])}")
    lines.append(f"Defer (25-39): {len([s for s in scores if 25 <= s.total_score < 40])}")
    lines.append(f"Skip (<25): {len([s for s in scores if s.total_score < 25])}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Score test files for fixture migration priority")
    parser.add_argument("file", nargs="?", help="Test file to score")
    parser.add_argument("--all", action="store_true", help="Score all test files")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--detailed", action="store_true", help="Include detailed metrics")
    args = parser.parse_args()

    if not args.all and not args.file:
        parser.error("Either provide a file path or use --all flag")

    # Find root directory
    root = Path(__file__).parent.parent.parent

    if args.all:
        # Score all test files
        test_files = find_test_files(root)
        scores = [analyze_test_file(f) for f in test_files]

        if args.json:
            output = [asdict(s) for s in scores]
            console.json(output)
        else:
            console.log(format_score_table(scores))

            if args.detailed:
                console.log("\n\nDETAILED METRICS:")
                console.log("=" * 120)
                for score in sorted(scores, key=lambda s: s.total_score, reverse=True):
                    if score.total_score >= 55:  # Only show medium+ priority
                        console.log(f"\n{Path(score.file_path).name} (Score: {score.total_score:.1f})")
                        m = score.metrics
                        console.log(f"  Tests: {m.test_count}, Classes: {m.class_count}")
                        console.log(f"  Setup lines: {m.setup_lines}, Teardown lines: {m.teardown_lines}")
                        console.log(f"  Self attributes: {m.self_attribute_count}")
                        console.log(f"  Duplication: {m.duplication_score:.1f}/10, Complexity: {m.complexity_score:.1f}/10")
                        console.log(f"  Temp dirs: {m.temp_dir_usage}, Mocks: {m.mock_usage}, Fixtures: {m.fixture_usage}")
    else:
        # Score single file
        file_path = Path(args.file)
        if not file_path.exists():
            console.error(f"Error: File not found: {file_path}")
            return 1

        score = analyze_test_file(file_path)

        if args.json:
            console.json(asdict(score))
        else:
            console.log(f"\nFile: {score.file_path}")
            console.log(f"Total Score: {score.total_score:.1f}/100")
            console.log(f"  Pain Points: {score.pain_points:.1f}/40")
            console.log(f"  Opportunity: {score.opportunity:.1f}/35")
            console.log(f"  Risk: {score.risk:.1f}/15")
            console.log(f"  Alignment: {score.alignment:.1f}/10")
            console.log(f"\nRecommendation: {score.recommendation}")

            if args.detailed:
                m = score.metrics
                console.log("\nDetailed Metrics:")
                console.log(f"  Total lines: {m.total_lines}")
                console.log(f"  Test count: {m.test_count}")
                console.log(f"  Class count: {m.class_count}")
                console.log(f"  Setup methods: {m.setup_method_count} ({m.setup_lines} lines)")
                console.log(f"  Teardown methods: {m.teardown_method_count} ({m.teardown_lines} lines)")
                console.log(f"  Self attributes: {m.self_attribute_count}")
                console.log(f"  Temp dir usage: {m.temp_dir_usage}")
                console.log(f"  Mock usage: {m.mock_usage}")
                console.log(f"  Fixture usage: {m.fixture_usage}")
                console.log(f"  Duplication score: {m.duplication_score:.1f}/10")
                console.log(f"  Complexity score: {m.complexity_score:.1f}/10")

    return 0


if __name__ == "__main__":
    exit(main())
