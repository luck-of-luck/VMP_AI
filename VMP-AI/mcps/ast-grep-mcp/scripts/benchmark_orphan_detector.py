#!/usr/bin/env python3
"""Benchmark detect_orphans against a target directory.

Usage:
    uv run python scripts/benchmark_orphan_detector.py [target_dir] [baseline_seconds]

Examples:
    uv run python scripts/benchmark_orphan_detector.py ~/code/jobs 764
    uv run python scripts/benchmark_orphan_detector.py ~/code/jobs
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ast_grep_mcp.features.quality.orphan_detector import detect_orphans_impl

DEFAULT_BASELINE_S = 764.0  # historical baseline runtime for the detect_orphans_impl benchmark

TARGET = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "code" / "jobs")
BASELINE_S = float(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BASELINE_S

print(f"Target: {TARGET}")
print(f"Baseline: {BASELINE_S:.0f}s")
print("Running detect_orphans_impl ...")

start = time.time()
result = detect_orphans_impl(project_folder=TARGET)
elapsed = time.time() - start

summary = result.get("summary", {})
orphan_files = summary.get("orphan_files", 0)
orphan_functions = summary.get("orphan_functions", 0)
total_files = summary.get("total_files_analyzed", 0)
total_functions = summary.get("total_functions_analyzed", 0)

print(f"\n{'=' * 60}")
print(f"Time:             {elapsed:.1f}s (baseline: {BASELINE_S:.0f}s)")
print(f"Speedup:          {BASELINE_S / elapsed:.1f}x")
print(f"Orphan files:     {orphan_files}")
print(f"Orphan functions: {orphan_functions}")
print(f"Total files:      {total_files}")
print(f"Total functions:  {total_functions}")
print(f"{'=' * 60}")

out_path = Path("/tmp/benchmark_orphans.json")
with open(out_path, "w") as f:
    json.dump(
        {
            "target": TARGET,
            "elapsed_s": round(elapsed, 2),
            "baseline_s": BASELINE_S,
            "speedup": round(BASELINE_S / elapsed, 1),
            "summary": summary,
            "orphan_files": result.get("orphan_files", []),
            "orphan_functions": result.get("orphan_functions", []),
        },
        f,
        indent=2,
    )
print(f"\nResults saved: {out_path}")
