#!/usr/bin/env python3
"""Run all ast-grep-mcp analysis tools against the codebase.

Usage:
    uv run python scripts/run_all_analysis.py [src_path]
"""

import json
import sys
import time
from pathlib import Path

MAX_COMPLEXITY_DISPLAY = 10  # top N complex functions to display
MAX_DUP_GROUPS_DISPLAY = 10  # top N duplication groups to display
MAX_DUP_INSTANCES_DISPLAY = 3  # max instances per duplication group


def run_complexity(project_folder: str) -> dict:
    """Run complexity analysis."""
    from ast_grep_mcp.features.complexity.tools import analyze_complexity_tool

    result = analyze_complexity_tool(project_folder=project_folder, language="python")
    print("\n=== COMPLEXITY ANALYSIS ===")
    print(json.dumps(result["summary"], indent=2))
    funcs = result.get("functions", [])
    print(f"Functions exceeding thresholds: {len(funcs)}")
    # Response keys: name, file, lines, cyclomatic, cognitive, nesting_depth, length, exceeds
    for f in sorted(funcs, key=lambda x: x.get("cognitive", 0), reverse=True)[:MAX_COMPLEXITY_DISPLAY]:
        rel = f.get("file", "").split("src/")[-1]
        print(f"  {rel} {f['name']} cyc={f['cyclomatic']} cog={f['cognitive']} nest={f['nesting_depth']} len={f['length']}")
    if len(funcs) > MAX_COMPLEXITY_DISPLAY:
        print(f"  ... and {len(funcs) - MAX_COMPLEXITY_DISPLAY} more")
    return result


def run_smells(project_folder: str) -> dict:
    """Run code smell detection."""
    from ast_grep_mcp.features.complexity.tools import detect_code_smells_tool

    result = detect_code_smells_tool(project_folder=project_folder, language="python")
    print("\n=== CODE SMELLS ===")
    summary = {k: v for k, v in result.items() if k != "smells"}
    print(json.dumps(summary, indent=2))
    smells = result.get("smells", [])
    for s in smells[:10]:
        rel = s.get("file", "").split("src/")[-1]
        print(f"  [{s.get('severity', '?')}] {s.get('smell_type', '?')}: {rel}:{s.get('line', '')} {s.get('message', '')[:80]}")
    if len(smells) > 10:
        print(f"  ... and {len(smells) - 10} more smells")
    return result


def run_standards(project_folder: str) -> dict:
    """Run standards enforcement."""
    from ast_grep_mcp.features.quality.tools import enforce_standards_tool

    result = enforce_standards_tool(project_folder=project_folder, language="python", rule_set="all")
    print("\n=== STANDARDS ENFORCEMENT ===")
    print(json.dumps(result["summary"], indent=2))
    violations = result.get("violations", [])
    for v in violations[:10]:
        rel = v["file"].split("src/")[-1]
        print(f"  [{v['severity']}] {v['rule_id']}: {rel}:{v['line']} {v['message'][:80]}")
    if len(violations) > 10:
        print(f"  ... and {len(violations) - 10} more violations")
    return result


def run_security(project_folder: str) -> dict:
    """Run security vulnerability scan."""
    from ast_grep_mcp.features.quality.tools import detect_security_issues_tool

    result = detect_security_issues_tool(project_folder=project_folder, language="python")
    print("\n=== SECURITY SCAN ===")
    print(json.dumps(result["summary"], indent=2))
    issues = result.get("issues", [])
    for i in issues[:10]:
        rel = i["file"].split("src/")[-1]
        print(f"  [{i['severity']}] {i['issue_type']}: {rel}:{i['line']} {i['title'][:80]}")
    if len(issues) > 10:
        print(f"  ... and {len(issues) - 10} more issues")
    return result


def run_orphans(project_folder: str) -> dict:
    """Run orphan detection."""
    from ast_grep_mcp.features.quality.tools import detect_orphans_tool

    result = detect_orphans_tool(project_folder=project_folder)
    print("\n=== ORPHAN DETECTION ===")
    print(json.dumps(result["summary"], indent=2))
    for f in result.get("orphan_files", [])[:10]:
        rel = f["file_path"].split("src/")[-1]
        print(f"  FILE: {rel} ({f.get('lines', '?')} lines) {f.get('status', '')}")
    for f in result.get("orphan_functions", [])[:10]:
        rel = f.get("file", "").split("src/")[-1]
        print(f"  FUNC: {rel}:{f.get('line', '')} {f.get('name', '')}")
    return result


def run_duplication(project_folder: str) -> dict:
    """Run duplication detection."""
    from ast_grep_mcp.features.deduplication.tools import find_duplication_tool

    result = find_duplication_tool(project_folder=project_folder, language="python")
    print("\n=== DUPLICATION DETECTION ===")
    summary = result.get("summary", {})
    print(json.dumps(summary, indent=2))
    groups = result.get("duplication_groups", [])
    for g in groups[:MAX_DUP_GROUPS_DISPLAY]:
        print(f"  Group {g.get('group_id', '?')}: sim={g.get('similarity_score', 0):.2f}")
        for inst in g.get("instances", [])[:MAX_DUP_INSTANCES_DISPLAY]:
            rel = inst.get("file", "").split("src/")[-1]
            print(f"    {rel} lines={inst.get('lines', '')}")
    if len(groups) > MAX_DUP_GROUPS_DISPLAY:
        print(f"  ... and {len(groups) - MAX_DUP_GROUPS_DISPLAY} more groups")
    return result


def run_benchmarks() -> dict:
    """Run deduplication performance benchmarks."""
    from ast_grep_mcp.features.deduplication.tools import benchmark_deduplication_tool

    result = benchmark_deduplication_tool(iterations=5)
    print("\n=== DEDUPLICATION BENCHMARKS ===")
    summary = {k: v for k, v in result.items() if k != "results"}
    print(json.dumps(summary, indent=2))
    for r in result.get("results", []):
        print(f"  {r['name']}: mean={r.get('mean_ms', 0):.2f}ms median={r.get('median_ms', 0):.2f}ms p95={r.get('p95_ms', 0):.2f}ms")
    return result


def main() -> None:
    project_folder = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parent.parent / "src")
    print(f"Analyzing: {project_folder}")
    start = time.time()

    run_complexity(project_folder)
    run_smells(project_folder)
    run_standards(project_folder)
    run_security(project_folder)
    run_orphans(project_folder)
    run_duplication(project_folder)
    run_benchmarks()

    elapsed = time.time() - start
    print(f"\n=== COMPLETE === ({elapsed:.1f}s)")


if __name__ == "__main__":
    main()
