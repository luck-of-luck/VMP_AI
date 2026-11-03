#!/usr/bin/env python3
"""Extract all functions exceeding critical complexity thresholds."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ast_grep_mcp.constants import CriticalComplexityThresholds, FormattingDefaults
from ast_grep_mcp.features.complexity.analyzer import analyze_function_complexity

# Critical thresholds
CRITICAL_THRESHOLDS = {
    "cyclomatic": CriticalComplexityThresholds.CYCLOMATIC,
    "cognitive": CriticalComplexityThresholds.COGNITIVE,
    "nesting": CriticalComplexityThresholds.NESTING,
    "lines": CriticalComplexityThresholds.LINES,
}


def scan_all_python_files(root: Path) -> list[tuple[Path, str]]:
    """Scan all Python files and extract function names."""
    functions = []
    src_dir = root / "src"

    for py_file in src_dir.rglob("*.py"):
        if py_file.name == "__init__.py":
            continue

        try:
            with open(py_file) as f:
                content = f.read()

            # Simple function extraction (looking for 'def ' at start of line)
            for _line_num, line in enumerate(content.split("\n"), 1):
                stripped = line.lstrip()
                if stripped.startswith("def "):
                    # Extract function name
                    func_name = stripped[len("def ") :].split("(")[0].strip()
                    if func_name and not func_name.startswith("_test"):
                        functions.append((py_file, func_name))

        except Exception as e:
            print(f"Error processing {py_file}: {e}", file=sys.stderr)

    return functions


def main():
    project_root = Path(__file__).parent.parent
    all_functions = scan_all_python_files(project_root)
    violations = []

    print(f"Scanning {len(all_functions)} functions...", file=sys.stderr)

    for file_path, func_name in all_functions:
        metrics = analyze_function_complexity(str(file_path), func_name)

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
            violations.append(
                {
                    "file": str(rel_path),
                    "function": func_name,
                    "violations": ", ".join(violation_reasons),
                    "cyclomatic": metrics["cyclomatic"],
                    "cognitive": metrics["cognitive"],
                    "nesting": metrics["nesting"],
                    "lines": metrics["lines"],
                }
            )

    # Sort by severity (most violations first, then highest cognitive complexity)
    violations.sort(key=lambda v: (-len(v["violations"].split(",")), -v["cognitive"], -v["cyclomatic"]))

    separator = "=" * FormattingDefaults.WIDE_SECTION_WIDTH
    print(f"\n{separator}\nFound {len(violations)} functions exceeding CRITICAL thresholds\n{separator}\n")

    for i, v in enumerate(violations, 1):
        print(f"{i:2d}. {v['file']}:{v['function']}")
        print(f"    {v['violations']}")
        print()

    print(f"\nTotal: {len(violations)} functions need refactoring")


if __name__ == "__main__":
    main()
