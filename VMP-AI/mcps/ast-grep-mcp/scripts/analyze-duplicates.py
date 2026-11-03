#!/usr/bin/env python3
"""
Analyze duplicate detection scan results.

Usage:
    python scripts/analyze-duplicates.py [report_path]

If no report path provided, uses the most recent scan report.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

MAX_GROUPS_DISPLAY = 15  # number of duplicate groups to show
MAX_FILES_DISPLAY = 4  # number of file names to show per group


def get_file_path(location):
    """Extract file path from location (handles both dict and string formats)."""
    if isinstance(location, dict):
        return location.get("file_path", "unknown")
    elif isinstance(location, str):
        return location.split(":")[0]
    return "unknown"


def analyze_report(report_path):
    """Analyze a duplicate detection report."""
    with open(report_path, "r") as f:
        data = json.load(f)

    # Group blocks by content_hash to find exact duplicates
    hash_to_blocks = defaultdict(list)
    for b in data.get("code_blocks", []):
        hash_to_blocks[b["content_hash"]].append(b)

    # Get groups with 2+ occurrences, sorted by count
    exact_dups = [(h, blocks) for h, blocks in hash_to_blocks.items() if len(blocks) >= 2]
    exact_dups.sort(key=lambda x: len(x[1]), reverse=True)

    print(f"Report: {report_path}")
    print(f"Total code blocks: {len(data.get('code_blocks', []))}")
    print(f"Exact duplicate patterns: {len(exact_dups)}")
    print()

    for i, (h, blocks) in enumerate(exact_dups[:MAX_GROUPS_DISPLAY], 1):
        files = list(set(get_file_path(b["location"]) for b in blocks))
        code = blocks[0]["source_code"]
        short_files = [Path(f).name for f in files[:MAX_FILES_DISPLAY]]

        print(f"=== Group {i}: {len(blocks)}x in {len(files)} files ===")
        print(f"Files: {', '.join(short_files)}")
        if len(files) > MAX_FILES_DISPLAY:
            print(f"       +{len(files) - MAX_FILES_DISPLAY} more")
        print(f"Code:\n{code}\n")


def find_latest_report():
    """Find the most recent scan report."""
    output_dir = Path("output/reports")
    if not output_dir.exists():
        return None

    reports = list(output_dir.glob("scan-*.json"))
    if not reports:
        return None

    return max(reports, key=lambda p: p.stat().st_mtime)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        report_path = sys.argv[1]
    else:
        report_path = find_latest_report()
        if not report_path:
            print("No scan reports found in output/reports/")
            sys.exit(1)

    analyze_report(report_path)
