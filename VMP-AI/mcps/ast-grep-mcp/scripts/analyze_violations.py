#!/usr/bin/env python3
"""Analyze all complexity violations in the codebase."""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ast_grep_mcp.constants import CriticalComplexityThresholds


def analyze_function_complexity(file_path: Path, func_name: str) -> dict:
    """Analyze complexity of a specific function."""
    try:
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == func_name:
                    cyclomatic = calculate_cyclomatic_complexity(node)
                    cognitive = calculate_cognitive_complexity(node)
                    nesting = calculate_max_nesting(node)
                    lines = node.end_lineno - node.lineno + 1 if hasattr(node, "end_lineno") else 0

                    return {"found": True, "cyclomatic": cyclomatic, "cognitive": cognitive, "nesting": nesting, "lines": lines}

        return {"found": False}
    except Exception as e:
        return {"found": False, "error": str(e)}


def calculate_cyclomatic_complexity(node: ast.AST) -> int:
    """Calculate McCabe cyclomatic complexity."""
    complexity = 1

    for child in ast.walk(node):
        if isinstance(
            child, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler, ast.With, ast.AsyncWith, ast.Assert, ast.comprehension)
        ):
            complexity += 1
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, ast.IfExp):
            complexity += 1

    return complexity


def calculate_cognitive_complexity(node: ast.AST, depth: int = 0) -> int:
    """Calculate cognitive complexity with nesting penalties."""
    complexity = 0

    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
            complexity += 1 + depth
            complexity += calculate_cognitive_complexity(child, depth + 1)
        elif isinstance(child, ast.ExceptHandler):
            complexity += 1 + depth
            complexity += calculate_cognitive_complexity(child, depth + 1)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            complexity += 1
            complexity += calculate_cognitive_complexity(child, depth + 1)
        elif isinstance(child, ast.BoolOp):
            complexity += len(child.values) - 1
        elif isinstance(child, ast.IfExp):
            complexity += 1
        else:
            complexity += calculate_cognitive_complexity(child, depth)

    return complexity


def calculate_max_nesting(node: ast.AST, current_depth: int = 0) -> int:
    """Calculate maximum nesting depth."""
    max_depth = current_depth

    for child in ast.iter_child_nodes(node):
        child_depth = current_depth

        if isinstance(
            child,
            (
                ast.If,
                ast.While,
                ast.For,
                ast.AsyncFor,
                ast.With,
                ast.AsyncWith,
                ast.Try,
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            child_depth += 1

        max_depth = max(max_depth, calculate_max_nesting(child, child_depth))

    return max_depth


def scan_all_functions(project_root: Path):
    """Scan all Python files and functions."""
    src_path = project_root / "src"
    all_functions = []

    for py_file in src_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            with open(py_file, "r") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    all_functions.append((py_file, node.name))
        except Exception:
            pass

    return all_functions


def main():
    project_root = Path.cwd()
    all_functions = scan_all_functions(project_root)

    CRITICAL_THRESHOLDS = {
        "cyclomatic": CriticalComplexityThresholds.CYCLOMATIC,
        "cognitive": CriticalComplexityThresholds.COGNITIVE,
        "nesting": CriticalComplexityThresholds.NESTING,
        "lines": CriticalComplexityThresholds.LINES,
    }

    violations = []

    for file_path, func_name in all_functions:
        metrics = analyze_function_complexity(file_path, func_name)

        if not metrics["found"]:
            continue

        violation_reasons = []

        if metrics["cyclomatic"] > CRITICAL_THRESHOLDS["cyclomatic"]:
            violation_reasons.append(f"cyclomatic={metrics['cyclomatic']}")

        if metrics["cognitive"] > CRITICAL_THRESHOLDS["cognitive"]:
            violation_reasons.append(f"cognitive={metrics['cognitive']}")

        if metrics["nesting"] > CRITICAL_THRESHOLDS["nesting"]:
            violation_reasons.append(f"nesting={metrics['nesting']}")

        if metrics["lines"] > CRITICAL_THRESHOLDS["lines"]:
            violation_reasons.append(f"lines={metrics['lines']}")

        if violation_reasons:
            rel_path = file_path.relative_to(project_root)
            violations.append({"path": str(rel_path), "function": func_name, "reasons": violation_reasons, "metrics": metrics})

    # Sort by severity (number of violations, then by highest metric)
    violations.sort(
        key=lambda x: (
            -len(x["reasons"]),
            -max(x["metrics"]["cyclomatic"], x["metrics"]["cognitive"], x["metrics"]["nesting"], x["metrics"]["lines"]),
        )
    )

    print(f"Found {len(violations)} violations:\n")

    for i, v in enumerate(violations, 1):
        print(f"{i:2d}. {v['path']}:{v['function']}")
        print(f"    Violations: {', '.join(v['reasons'])}")
        print(
            f"    Metrics: cyc={v['metrics']['cyclomatic']}, "
            f"cog={v['metrics']['cognitive']}, "
            f"nest={v['metrics']['nesting']}, "
            f"lines={v['metrics']['lines']}"
        )
        print()


if __name__ == "__main__":
    main()
