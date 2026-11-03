#!/usr/bin/env python3
"""Detailed orphan analysis report with directory grouping and severity breakdown."""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from ast_grep_mcp.features.quality.tools import detect_orphans_tool  # noqa: E402

STATUS_ICON = {"confirmed": "X", "likely": "!", "uncertain": "?"}
DEFAULT_TOP = 10
MAX_IMPORTERS_SHOWN = 3  # importers listed inline per orphan-file before truncating
MAX_FN_NAMES_PER_FILE = 5  # orphan-function names shown inline per file before truncating


def main() -> None:
    parser = argparse.ArgumentParser(description="Detailed orphan analysis report")
    parser.add_argument("project", nargs="?", default=str(Path(__file__).resolve().parent.parent.parent))
    parser.add_argument("--extended", action="store_true", help="Show all orphan functions with full detail")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Output raw JSON")
    parser.add_argument("--files-only", action="store_true", help="Show only orphan files")
    parser.add_argument("--functions-only", action="store_true", help="Show only orphan functions")
    parser.add_argument("-n", "--top", type=int, default=DEFAULT_TOP, help="Top files by orphan function count")
    parser.add_argument("-o", "--output", help="Write raw JSON to file")
    args = parser.parse_args()

    result = detect_orphans_tool(project_folder=args.project)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)

    if args.as_json:
        print(json.dumps(result, indent=2, default=str))
        return

    s = result["summary"]
    total_files = s.get("total_files_analyzed", 0)
    total_funcs = s.get("total_functions_analyzed", 0)
    orphan_file_ct = s.get("orphan_files", 0)
    orphan_func_ct = s.get("orphan_functions", 0)
    orphan_lines = s.get("total_orphan_lines", 0)
    elapsed_ms = s.get("analysis_time_ms", 0)
    file_pct = (orphan_file_ct / total_files * 100) if total_files else 0
    func_pct = (orphan_func_ct / total_funcs * 100) if total_funcs else 0

    print(f"Files:     {total_files:>6}  orphan: {orphan_file_ct:>4} ({file_pct:.1f}%)")
    print(f"Functions: {total_funcs:>6}  orphan: {orphan_func_ct:>4} ({func_pct:.1f}%)")
    print(f"Orphan lines: {orphan_lines:>6}")
    print(f"Time:         {elapsed_ms / 1000:.1f}s")
    print()

    files = result.get("orphan_files", [])
    funcs = result.get("orphan_functions", [])

    if not args.functions_only:
        _print_files(files, args.project, args.extended)

    if not args.files_only:
        _print_functions(funcs, args.project, args.extended, args.top)

    _print_breakdown(files, funcs)


def _print_files(files: list, project: str, extended: bool) -> None:
    by_dir: dict[str, list] = defaultdict(list)
    for f in files:
        parent = str(Path(f.get("file_path", "")).parent)
        by_dir[parent].append(f)

    print(f"=== ORPHAN FILES ({len(files)}) ===")

    if extended:
        for d in sorted(by_dir):
            items = sorted(by_dir[d], key=lambda x: x.get("file_path", ""))
            dir_lines = sum(x.get("lines", 0) for x in items)
            print(f"\n  {d}/ — {len(items)} file{'s' if len(items) != 1 else ''}, {dir_lines:,} lines")
            for f in items:
                name = Path(f.get("file_path", "")).name
                lines = f.get("lines", 0)
                status = f.get("status", "")
                reason = f.get("reason", "")
                icon = STATUS_ICON.get(status, " ")
                print(f"    [{icon}] {lines:>5}  {name:<40} {reason}")
                for imp in f.get("importers", [])[:MAX_IMPORTERS_SHOWN]:
                    print(f"              -> {Path(imp).name}")
                if len(f.get("importers", [])) > MAX_IMPORTERS_SHOWN:
                    print(f"              ... +{len(f['importers']) - MAX_IMPORTERS_SHOWN} more")
    else:
        for f in sorted(files, key=lambda x: x.get("file_path", "")):
            fp = f.get("file_path", "").replace(project + "/", "")
            reason = f.get("reason", "")
            print(f"  {fp:<60} {f.get('lines', 0):>4} lines  [{f.get('status', '?')}] {reason}")

    print()


def _print_functions(funcs: list, project: str, extended: bool, top: int) -> None:
    by_file: dict[str, list] = defaultdict(list)
    for fn in funcs:
        by_file[fn.get("file_path", "unknown")].append(fn)

    print(f"=== ORPHAN FUNCTIONS ({len(funcs)}) ===")

    if extended:
        file_by_dir: dict[str, list] = defaultdict(list)
        for fp in sorted(by_file):
            file_by_dir[str(Path(fp).parent)].append(fp)

        for d in sorted(file_by_dir):
            count = sum(len(by_file[fp]) for fp in file_by_dir[d])
            lines = sum(fn.get("lines", 0) for fp in file_by_dir[d] for fn in by_file[fp])
            print(f"\n  {d}/ — {count} orphan func{'s' if count != 1 else ''}, {lines:,} lines")

            for fp in sorted(file_by_dir[d]):
                items = sorted(by_file[fp], key=lambda x: x.get("line_start", 0))
                file_lines = sum(x.get("lines", 0) for x in items)
                print(f"    {Path(fp).name} ({len(items)} funcs, {file_lines} lines)")
                for fn in items:
                    icon = STATUS_ICON.get(fn.get("status", ""), " ")
                    vis = "private" if fn.get("is_private") else "public"
                    print(f"      [{icon}] {fn.get('lines', 0):>5}  L{fn.get('line_start', 0):<5}  {fn['name']:<40} {vis}")
    else:
        for fp in sorted(by_file):
            fns = by_file[fp]
            short = fp.replace(project + "/", "")
            names = ", ".join(fn["name"] for fn in fns[:MAX_FN_NAMES_PER_FILE])
            suffix = f" +{len(fns) - MAX_FN_NAMES_PER_FILE} more" if len(fns) > MAX_FN_NAMES_PER_FILE else ""
            print(f"  {short:<55} ({len(fns):>3}): {names}{suffix}")

    print()
    ranked = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)[:top]
    print(f"Top {top} files by orphan function count:")
    for fp, items in ranked:
        total_lines = sum(x.get("lines", 0) for x in items)
        short = fp.replace(project + "/", "")
        print(f"  {len(items):>3} funcs  {total_lines:>5} lines  {short}")
    print()


def _print_breakdown(files: list, funcs: list) -> None:
    file_status: dict[str, int] = defaultdict(int)
    for f in files:
        file_status[f.get("status", "unknown")] += 1

    func_status: dict[str, int] = defaultdict(int)
    private_ct = public_ct = 0
    for fn in funcs:
        func_status[fn.get("status", "unknown")] += 1
        if fn.get("is_private"):
            private_ct += 1
        else:
            public_ct += 1

    print("=== BREAKDOWN ===")
    print("  File status:     " + "  ".join(f"[{STATUS_ICON.get(s, ' ')}] {s}: {c}" for s, c in sorted(file_status.items())))
    print("  Function status: " + "  ".join(f"[{STATUS_ICON.get(s, ' ')}] {s}: {c}" for s, c in sorted(func_status.items())))
    print(f"  Visibility:      public: {public_ct}  private: {private_ct}")
    print("\n  Legend: [X] confirmed  [!] likely  [?] uncertain")


if __name__ == "__main__":
    main()
