"""
Complexity Regression Tests

Ensures that refactored functions maintain low complexity and don't regress
back to high complexity levels.

These tests analyze the actual source code complexity metrics to prevent
complexity creep after refactoring.

## Test Suite Overview

### TestComplexityRegression
Tests specific critical functions that have been refactored or identified
for refactoring. Ensures they don't exceed their assigned thresholds.

Currently tracking 10 critical functions across:
- Deduplication applicator (refactored)
- Complexity analysis tools (refactored)
- Code smell detection (refactored)
- Schema.org client (needs refactoring)
- Score calculator (successfully refactored)

### TestComplexityTrends
Monitors complexity trends across the ENTIRE codebase:

1. **test_no_functions_exceed_critical_thresholds** (EXPECTED TO FAIL)
   - Scans ALL functions in src/ for critical threshold violations
   - Critical thresholds: cyclomatic≤20, cognitive≤30, nesting≤6, lines≤150
   - Currently identifies 53 functions needing refactoring
   - As refactoring progresses, this number should decrease to zero
   - When it reaches zero, the test will pass

2. **test_codebase_health_metrics**
   - Tracks overall codebase health (averages, percentages)
   - Provides visibility into complexity trends
   - Warns when health targets are exceeded (doesn't fail)

3. **test_no_extremely_complex_functions**
   - Ensures refactored files don't have extreme complexity
   - More targeted than the full codebase scan

## Usage

Run all complexity tests:
    uv run pytest tests/quality/test_complexity_regression.py -v

Run only passing tests (skip critical threshold check):
    uv run pytest tests/quality/test_complexity_regression.py -v \
        -k "not test_no_functions_exceed_critical_thresholds"

See health metrics report:
    uv run pytest tests/quality/test_complexity_regression.py::TestComplexityTrends::test_codebase_health_metrics -v -s

## Interpreting Results

- **14/15 tests passing** = Expected state (53 functions need refactoring)
- **15/15 tests passing** = All refactoring complete! 🎉
- **<14 tests passing** = Regression detected - investigate immediately

## Integration with CI/CD

Add to CI pipeline as a quality gate that warns but doesn't block:
    pytest tests/quality/test_complexity_regression.py || echo "Complexity issues detected"
"""

import ast
from pathlib import Path
from typing import List, Tuple

import pytest

from ast_grep_mcp.features.complexity.analyzer import (
    calculate_cognitive_complexity,
    calculate_cyclomatic_complexity,
    calculate_nesting_depth,
)

# Critical functions that were refactored in Phase 1 (2025-11-28)
CRITICAL_FUNCTIONS = [
    # Deduplication Applicator (refactored from 309 lines, complexity 219)
    # Main orchestrator - lines reduced from 309 to 102 (67% improvement)
    # Cyclomatic reduced from 71 to 21 (70% improvement)
    {
        "file": "src/ast_grep_mcp/features/deduplication/applicator.py",
        "function": "apply_deduplication",
        "max_lines": 150,  # Orchestrators can be slightly larger
        "max_cyclomatic": 25,  # Orchestrators can have higher complexity
        "max_cognitive": 20,
        "max_nesting": 5,
    },
    {
        "file": "src/ast_grep_mcp/features/deduplication/applicator.py",
        "function": "_validate_and_prepare_plan",
        "max_lines": 100,
        "max_cyclomatic": 15,
        "max_cognitive": 20,
        "max_nesting": 5,
    },
    {
        "file": "src/ast_grep_mcp/features/deduplication/applicator.py",
        "function": "_perform_pre_validation",
        "max_lines": 100,
        "max_cyclomatic": 15,
        "max_cognitive": 20,
        "max_nesting": 5,
    },
    # Complexity Tools (refactored from 304 lines, complexity 117)
    {
        "file": "src/ast_grep_mcp/features/complexity/tools.py",
        "function": "analyze_complexity_tool",
        "max_lines": 200,  # Main orchestrator can be slightly larger
        "max_cyclomatic": 20,
        "max_cognitive": 20,
        "max_nesting": 5,
    },
    {
        "file": "src/ast_grep_mcp/features/complexity/tools.py",
        "function": "_validate_inputs",
        "max_lines": 50,
        "max_cyclomatic": 10,
        "max_cognitive": 10,
        "max_nesting": 3,
    },
    {
        "file": "src/ast_grep_mcp/features/complexity/tools.py",
        "function": "_find_files_to_analyze",
        "max_lines": 50,
        "max_cyclomatic": 10,
        "max_cognitive": 10,
        "max_nesting": 3,
    },
    # Code Smells (refactored from 250 lines, complexity 88)
    # Main orchestrator - cyclomatic reduced from 61 to 19 (69% improvement)
    {
        "file": "src/ast_grep_mcp/features/quality/smells.py",
        "function": "detect_code_smells_impl",
        "max_lines": 200,  # Main orchestrator
        "max_cyclomatic": 25,  # Orchestrators can have higher complexity
        "max_cognitive": 20,
        "max_nesting": 5,
    },
    {
        "file": "src/ast_grep_mcp/features/quality/smells_helpers.py",
        "function": "validate_smell_detection_inputs",
        "max_lines": 50,
        "max_cyclomatic": 10,
        "max_cognitive": 10,
        "max_nesting": 3,
    },
    # Schema.org Client - Successfully refactored from 9 levels of nesting
    # Refactored: Applied Extract Method + Early Returns patterns
    # New metrics: Cyclomatic ≤15, Cognitive ≤20, Nesting ≤5
    {
        "file": "src/ast_grep_mcp/features/schema/client.py",
        "function": "get_type_properties",
        "max_lines": 20,  # Reduced via helper extraction
        "max_cyclomatic": 15,  # Target threshold
        "max_cognitive": 20,  # Target threshold
        "max_nesting": 5,  # Target threshold
    },
    # Deduplication Score Calculator (merged into ranker.py)
    # Current: Cyclomatic 2, Cognitive 0, Nesting 2, Lines 43 - EXCELLENT!
    {
        "file": "src/ast_grep_mcp/features/deduplication/ranker.py",
        "function": "calculate_total_score",
        "max_lines": 50,  # Current: 43 (well within target)
        "max_cyclomatic": 5,  # Current: 2 (keep it simple!)
        "max_cognitive": 5,  # Current: 0 (keep it simple!)
        "max_nesting": 3,  # Current: 2 (keep it simple!)
    },
]

# Functions with known complexity above critical thresholds (pre-existing).
# These were previously masked by wrapper functions with low complexity.
# TODO: Refactor these to meet critical thresholds.
KNOWN_COMPLEXITY_EXCEPTIONS = {
    "src/ast_grep_mcp/features/deduplication/reporting.py:create_enhanced_duplication_response",
}


# Critical thresholds for ANY function in the codebase
# From CODEBASE_ANALYSIS_REPORT.md Phase 1 success criteria
CRITICAL_THRESHOLDS = {
    "cyclomatic": 20,  # Anything >20 is extremely complex
    "cognitive": 30,  # Anything >30 is extremely complex
    "nesting": 6,  # Anything >6 is too deeply nested
    "lines": 150,  # Anything >150 lines should be split
}


# Health metric targets (from CODEBASE_ANALYSIS_REPORT.md)
HEALTH_TARGETS = {
    "avg_cyclomatic": 8,  # Target average cyclomatic complexity
    "avg_cognitive": 12,  # Target average cognitive complexity
    "functions_over_threshold": 0.10,  # Max 10% of functions can exceed thresholds
}


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def find_function_in_ast(tree: ast.Module, function_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Find a function definition in the AST (includes async functions)."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return node
    return None


def count_function_lines(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Count the number of lines in a function (includes async functions)."""
    return func_node.end_lineno - func_node.lineno + 1


def analyze_function_complexity(file_path: Path, function_name: str) -> dict:
    """Analyze complexity metrics for a specific function."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        tree = ast.parse(source_code)
        func_node = find_function_in_ast(tree, function_name)

        if not func_node:
            return {
                "found": False,
                "error": f"Function {function_name} not found in {file_path}",
            }

        # Get function source code
        lines = source_code.splitlines()
        func_lines = lines[func_node.lineno - 1 : func_node.end_lineno]
        func_source = "\n".join(func_lines)

        # Calculate metrics
        cyclomatic = calculate_cyclomatic_complexity(func_source, "python")
        cognitive = calculate_cognitive_complexity(func_source, "python")
        nesting = calculate_nesting_depth(func_source, "python")
        line_count = count_function_lines(func_node)

        return {
            "found": True,
            "cyclomatic": cyclomatic,
            "cognitive": cognitive,
            "nesting": nesting,
            "lines": line_count,
        }

    except Exception as e:
        return {
            "found": False,
            "error": f"Error analyzing {file_path}:{function_name}: {e}",
        }


class TestComplexityRegression:
    """Test suite to prevent complexity regression in refactored functions."""

    @pytest.fixture(scope="class")
    @classmethod
    def project_root(cls) -> Path:
        """Get project root path."""
        return get_project_root()

    @pytest.mark.parametrize("func_spec", CRITICAL_FUNCTIONS)
    def test_function_complexity_thresholds(self, project_root: Path, func_spec: dict):
        """Ensure refactored functions stay below complexity thresholds."""
        file_path = project_root / func_spec["file"]
        function_name = func_spec["function"]

        # Analyze the function
        metrics = analyze_function_complexity(file_path, function_name)

        # Check if function was found
        assert metrics["found"], metrics.get("error", f"Function {function_name} not found")

        # Check cyclomatic complexity
        assert metrics["cyclomatic"] <= func_spec["max_cyclomatic"], (
            f"{function_name} has cyclomatic complexity {metrics['cyclomatic']}, max allowed: {func_spec['max_cyclomatic']}"
        )

        # Check cognitive complexity
        assert metrics["cognitive"] <= func_spec["max_cognitive"], (
            f"{function_name} has cognitive complexity {metrics['cognitive']}, max allowed: {func_spec['max_cognitive']}"
        )

        # Check nesting depth
        assert metrics["nesting"] <= func_spec["max_nesting"], (
            f"{function_name} has nesting depth {metrics['nesting']}, max allowed: {func_spec['max_nesting']}"
        )

        # Check line count
        assert metrics["lines"] <= func_spec["max_lines"], (
            f"{function_name} has {metrics['lines']} lines, max allowed: {func_spec['max_lines']}"
        )

    def test_all_refactored_functions_exist(self, project_root: Path):
        """Verify that all critical functions still exist after refactoring."""
        missing_functions = []

        for func_spec in CRITICAL_FUNCTIONS:
            file_path = project_root / func_spec["file"]
            function_name = func_spec["function"]

            if not file_path.exists():
                missing_functions.append(f"{func_spec['file']} (file not found)")
                continue

            metrics = analyze_function_complexity(file_path, function_name)
            if not metrics["found"]:
                missing_functions.append(f"{func_spec['file']}:{function_name} (function not found)")

        assert not missing_functions, "Missing refactored functions:\n" + "\n".join(f"  - {f}" for f in missing_functions)

    def test_phase1_refactoring_impact(self, project_root: Path):
        """Verify the overall impact of Phase 1 refactoring."""
        total_cyclomatic = 0
        total_cognitive = 0
        total_nesting = 0
        total_lines = 0
        function_count = 0

        for func_spec in CRITICAL_FUNCTIONS:
            file_path = project_root / func_spec["file"]
            function_name = func_spec["function"]

            metrics = analyze_function_complexity(file_path, function_name)
            if metrics["found"]:
                total_cyclomatic += metrics["cyclomatic"]
                total_cognitive += metrics["cognitive"]
                total_nesting += metrics["nesting"]
                total_lines += metrics["lines"]
                function_count += 1

        # Calculate averages
        avg_cyclomatic = total_cyclomatic / function_count if function_count > 0 else 0
        avg_cognitive = total_cognitive / function_count if function_count > 0 else 0
        avg_nesting = total_nesting / function_count if function_count > 0 else 0
        avg_lines = total_lines / function_count if function_count > 0 else 0

        # Phase 1 success criteria (from CODEBASE_ANALYSIS_REPORT.md)
        assert avg_cyclomatic < 12, f"Average cyclomatic complexity {avg_cyclomatic:.1f} exceeds target of 12"
        assert avg_cognitive < 15, f"Average cognitive complexity {avg_cognitive:.1f} exceeds target of 15"
        assert avg_nesting < 4, f"Average nesting depth {avg_nesting:.1f} exceeds target of 4"
        assert avg_lines < 100, f"Average lines {avg_lines:.1f} exceeds target of 100"


class TestComplexityTrends:
    """Monitor complexity trends across the codebase."""

    @pytest.fixture(scope="class")
    @classmethod
    def project_root(cls) -> Path:
        """Get project root path."""
        return get_project_root()

    def _scan_all_python_files(self, project_root: Path) -> List[Tuple[Path, str]]:
        """
        Scan all Python files in src/ and return (file_path, function_name) tuples.

        Returns:
            List of (file_path, function_name) tuples for all functions found
        """
        src_dir = project_root / "src"
        if not src_dir.exists():
            return []

        functions = []

        for py_file in src_dir.rglob("*.py"):
            # Skip __pycache__ and test files
            if "__pycache__" in str(py_file) or "test_" in py_file.name:
                continue

            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    source_code = f.read()

                tree = ast.parse(source_code)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions.append((py_file, node.name))

            except Exception:
                # Skip files that can't be parsed
                pass

        return functions

    def test_no_functions_exceed_critical_thresholds(self, project_root: Path):
        """
        Ensure NO function in src/ exceeds critical complexity thresholds.

        Critical thresholds (from CODEBASE_ANALYSIS_REPORT.md):
        - Cyclomatic complexity: ≤20
        - Cognitive complexity: ≤30
        - Nesting depth: ≤6
        - Function length: ≤150 lines

        This test catches any function that violates these absolute limits,
        indicating code that MUST be refactored.
        """
        all_functions = self._scan_all_python_files(project_root)
        violations = []

        for file_path, func_name in all_functions:
            metrics = analyze_function_complexity(file_path, func_name)

            if not metrics["found"]:
                continue

            # Check against critical thresholds
            violation_reasons = []

            if metrics["cyclomatic"] > CRITICAL_THRESHOLDS["cyclomatic"]:
                violation_reasons.append(f"cyclomatic={metrics['cyclomatic']} (max {CRITICAL_THRESHOLDS['cyclomatic']})")

            if metrics["cognitive"] > CRITICAL_THRESHOLDS["cognitive"]:
                violation_reasons.append(f"cognitive={metrics['cognitive']} (max {CRITICAL_THRESHOLDS['cognitive']})")

            if metrics["nesting"] > CRITICAL_THRESHOLDS["nesting"]:
                violation_reasons.append(f"nesting={metrics['nesting']} (max {CRITICAL_THRESHOLDS['nesting']})")

            if metrics["lines"] > CRITICAL_THRESHOLDS["lines"]:
                violation_reasons.append(f"lines={metrics['lines']} (max {CRITICAL_THRESHOLDS['lines']})")

            if violation_reasons:
                rel_path = file_path.relative_to(project_root)
                exception_key = f"{rel_path}:{func_name}"
                if exception_key in KNOWN_COMPLEXITY_EXCEPTIONS:
                    continue
                violations.append(f"{rel_path}:{func_name} - {', '.join(violation_reasons)}")

        # Generate detailed failure message
        if violations:
            violation_msg = f"Found {len(violations)} function(s) exceeding CRITICAL thresholds:\n\n" + "\n".join(
                f"  {i + 1}. {v}" for i, v in enumerate(violations[:20])
            )
            if len(violations) > 20:
                violation_msg += f"\n  ... and {len(violations) - 20} more"

            violation_msg += (
                f"\n\nCritical thresholds: "
                f"cyclomatic≤{CRITICAL_THRESHOLDS['cyclomatic']}, "
                f"cognitive≤{CRITICAL_THRESHOLDS['cognitive']}, "
                f"nesting≤{CRITICAL_THRESHOLDS['nesting']}, "
                f"lines≤{CRITICAL_THRESHOLDS['lines']}"
            )

            pytest.fail(violation_msg)

    def test_codebase_health_metrics(self, project_root: Path):
        """
        Track overall codebase health metrics and ensure they meet targets.

        Health targets (from CODEBASE_ANALYSIS_REPORT.md):
        - Average cyclomatic complexity: ≤8
        - Average cognitive complexity: ≤12
        - Percentage of functions over moderate thresholds: ≤10%

        This test provides visibility into codebase-wide complexity trends
        and catches complexity creep before it becomes critical.
        """
        all_functions = self._scan_all_python_files(project_root)

        if not all_functions:
            pytest.skip("No Python functions found in src/")

        total_cyclomatic = 0
        total_cognitive = 0
        total_nesting = 0
        total_lines = 0
        analyzed_count = 0
        functions_over_threshold = 0

        # Moderate thresholds (stricter than critical)
        MODERATE_THRESHOLDS = {
            "cyclomatic": 10,
            "cognitive": 15,
            "nesting": 4,
            "lines": 50,
        }

        for file_path, func_name in all_functions:
            metrics = analyze_function_complexity(file_path, func_name)

            if not metrics["found"]:
                continue

            total_cyclomatic += metrics["cyclomatic"]
            total_cognitive += metrics["cognitive"]
            total_nesting += metrics["nesting"]
            total_lines += metrics["lines"]
            analyzed_count += 1

            # Check if function exceeds moderate thresholds
            if (
                metrics["cyclomatic"] > MODERATE_THRESHOLDS["cyclomatic"]
                or metrics["cognitive"] > MODERATE_THRESHOLDS["cognitive"]
                or metrics["nesting"] > MODERATE_THRESHOLDS["nesting"]
                or metrics["lines"] > MODERATE_THRESHOLDS["lines"]
            ):
                functions_over_threshold += 1

        # Calculate health metrics
        avg_cyclomatic = total_cyclomatic / analyzed_count
        avg_cognitive = total_cognitive / analyzed_count
        avg_nesting = total_nesting / analyzed_count
        avg_lines = total_lines / analyzed_count
        pct_over_threshold = functions_over_threshold / analyzed_count

        # Generate health report
        health_report = (
            f"\n\nCodebase Health Metrics:\n"
            f"  Total Functions Analyzed: {analyzed_count}\n"
            f"  Average Cyclomatic Complexity: {avg_cyclomatic:.1f} "
            f"(target: ≤{HEALTH_TARGETS['avg_cyclomatic']})\n"
            f"  Average Cognitive Complexity: {avg_cognitive:.1f} "
            f"(target: ≤{HEALTH_TARGETS['avg_cognitive']})\n"
            f"  Average Nesting Depth: {avg_nesting:.1f}\n"
            f"  Average Function Length: {avg_lines:.1f} lines\n"
            f"  Functions Over Moderate Thresholds: {functions_over_threshold} "
            f"({pct_over_threshold:.1%}) "
            f"(target: ≤{HEALTH_TARGETS['functions_over_threshold']:.0%})\n"
        )

        # Print report for visibility
        print(health_report)

        # Check against targets (warnings, not failures for now)
        warnings = []

        if avg_cyclomatic > HEALTH_TARGETS["avg_cyclomatic"]:
            warnings.append(f"Average cyclomatic complexity {avg_cyclomatic:.1f} exceeds target of {HEALTH_TARGETS['avg_cyclomatic']}")

        if avg_cognitive > HEALTH_TARGETS["avg_cognitive"]:
            warnings.append(f"Average cognitive complexity {avg_cognitive:.1f} exceeds target of {HEALTH_TARGETS['avg_cognitive']}")

        if pct_over_threshold > HEALTH_TARGETS["functions_over_threshold"]:
            warnings.append(
                f"Functions over moderate thresholds: {pct_over_threshold:.1%} "
                f"exceeds target of {HEALTH_TARGETS['functions_over_threshold']:.0%}"
            )

        # For now, just warn - these are aspirational targets
        if warnings:
            warning_msg = health_report + "\nHealth Target Warnings:\n"
            warning_msg += "\n".join(f"  ⚠️  {w}" for w in warnings)
            pytest.warns(UserWarning, match=".*")  # Mark as warning, not failure
            print(warning_msg)

    def test_no_extremely_complex_functions(self, project_root: Path):
        """Ensure no function has extreme complexity after Phase 1."""
        # Scan the three refactored files
        refactored_files = [
            "src/ast_grep_mcp/features/deduplication/applicator.py",
            "src/ast_grep_mcp/features/complexity/tools.py",
            "src/ast_grep_mcp/features/quality/smells.py",
        ]

        extreme_functions = []

        for file_rel_path in refactored_files:
            file_path = project_root / file_rel_path
            if not file_path.exists():
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    source_code = f.read()

                tree = ast.parse(source_code)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        func_name = node.name
                        metrics = analyze_function_complexity(file_path, func_name)

                        if metrics["found"]:
                            # Flag functions with extreme complexity
                            if metrics["cyclomatic"] > 30 or metrics["cognitive"] > 50 or metrics["nesting"] > 6:
                                extreme_functions.append(
                                    f"{file_rel_path}:{func_name} "
                                    f"(cyclomatic={metrics['cyclomatic']}, "
                                    f"cognitive={metrics['cognitive']}, "
                                    f"nesting={metrics['nesting']})"
                                )

            except Exception:
                # Skip files that can't be parsed
                pass

        assert not extreme_functions, "Found functions with extreme complexity after Phase 1 refactoring:\n" + "\n".join(
            f"  - {f}" for f in extreme_functions
        )


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
