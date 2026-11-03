#!/usr/bin/env python3
"""Report orphan files and functions for a project folder."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from ast_grep_mcp.features.quality.tools import detect_orphans_tool

MAX_FN_NAMES_PER_FILE = 5  # orphan-function names shown inline before truncating


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect orphan files and functions")
    parser.add_argument("project", nargs="?", default=str(Path(__file__).resolve().parent.parent.parent))
    parser.add_argument("--extended", action="store_true", help="Show all orphan functions grouped by file")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Output raw JSON")
    parser.add_argument("--functions-only", action="store_true", help="Show only orphan functions")
    parser.add_argument("--files-only", action="store_true", help="Show only orphan files")
    args = parser.parse_args()

    result = detect_orphans_tool(project_folder=args.project)

    if args.as_json:
        print(json.dumps(result, indent=2, default=str))
        return

    s = result["summary"]
    print(f"Files analyzed:     {s['total_files_analyzed']}")
    print(f"Functions analyzed: {s['total_functions_analyzed']}")
    print(f"Orphan files:       {s['orphan_files']}")
    print(f"Orphan functions:   {s['orphan_functions']}")
    print(f"Total orphan lines: {s['total_orphan_lines']}")
    print(f"Time:               {s['analysis_time_ms']}ms")
    print()

    if not args.functions_only:
        print(f"=== ORPHAN FILES ({len(result['orphan_files'])}) ===")
        for f in result["orphan_files"]:
            reason = f.get("reason", "")
            print(f"  {f['file_path']:<60} {f['lines']:>4} lines  [{f['status']}] {reason}")
        print()

    if not args.files_only:
        orphan_fns = result["orphan_functions"]
        by_file: dict[str, list] = {}
        for fn in orphan_fns:
            fpath = fn.get("file_path", "unknown")
            by_file.setdefault(fpath, []).append(fn)

        print(f"=== ORPHAN FUNCTIONS ({len(orphan_fns)}) ===")

        if args.extended:
            for fpath in sorted(by_file):
                fns = by_file[fpath]
                short = fpath.replace(args.project + "/", "")
                print(f"  {short} ({len(fns)} orphans):")
                for fn in fns:
                    ln = fn.get("line_start", "?")
                    exported = " [exported]" if fn.get("is_exported") else ""
                    private = " [private]" if fn.get("is_private") else ""
                    print(f"    - {fn['name']} (L{ln}) [{fn.get('status', '?')}]{exported}{private}")
                print()
        else:
            for fpath in sorted(by_file):
                fns = by_file[fpath]
                short = fpath.replace(args.project + "/", "")
                names = ", ".join(fn["name"] for fn in fns[:MAX_FN_NAMES_PER_FILE])
                suffix = f" +{len(fns) - MAX_FN_NAMES_PER_FILE} more" if len(fns) > MAX_FN_NAMES_PER_FILE else ""
                print(f"  {short:<55} ({len(fns):>3}): {names}{suffix}")


if __name__ == "__main__":
    main()
