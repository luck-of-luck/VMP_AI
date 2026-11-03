#!/usr/bin/env python3
"""Report function complexity for a project folder."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from ast_grep_mcp.features.complexity.tools import analyze_complexity_tool

DEFAULT_TOP = 15
NAME_COL_WIDTH = 40
FILE_COL_WIDTH = 55


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze function complexity")
    parser.add_argument("project", nargs="?", default=str(Path(__file__).resolve().parent.parent.parent))
    parser.add_argument("-l", "--language", default="python")
    parser.add_argument("-n", "--top", type=int, default=DEFAULT_TOP, help="Number of top functions to show")
    parser.add_argument("--extended", action="store_true", help="Show all exceeding functions")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    result = analyze_complexity_tool(project_folder=args.project, language=args.language)

    if args.as_json:
        print(json.dumps(result, indent=2, default=str))
        return

    s = result["summary"]
    print(f"Total functions: {s['total_functions']}  |  Total files: {s['total_files']}")
    print(f"Exceeding:       {s['exceeding_threshold']} ({s['exceeding_threshold'] / max(s['total_functions'], 1) * 100:.1f}%)")
    print(f"Avg cyclomatic:  {s['avg_cyclomatic']}  |  Avg cognitive: {s['avg_cognitive']}")
    print(f"Max cyclomatic:  {s['max_cyclomatic']}  |  Max cognitive: {s['max_cognitive']}  |  Max nesting: {s['max_nesting']}")
    print(f"Time:            {s['analysis_time_seconds']:.2f}s")
    print()

    functions = result["functions"]
    ranked = sorted(functions, key=lambda f: f["cyclomatic"], reverse=True)

    show = ranked if args.extended else ranked[: args.top]
    label = "ALL exceeding" if args.extended else f"Top {args.top}"
    print(f"{label} by cyclomatic complexity:")
    print(f"  {'Name':<40} {'File':<55} {'Lines':<12} {'Cyc':>4} {'Cog':>4} {'Nest':>5} {'Len':>4}")
    print(f"  {'-' * 40} {'-' * 55} {'-' * 12} {'-' * 4} {'-' * 4} {'-' * 5} {'-' * 4}")

    for f in show:
        name = f["name"][:NAME_COL_WIDTH]
        filepath = f["file"].replace(args.project + "/", "")[:FILE_COL_WIDTH]
        lines = f["lines"] if isinstance(f["lines"], str) else f"{f['lines']}"
        print(f"  {name:<40} {filepath:<55} {lines:<12} {f['cyclomatic']:>4} {f['cognitive']:>4} {f['nesting_depth']:>5} {f['length']:>4}")


if __name__ == "__main__":
    main()
