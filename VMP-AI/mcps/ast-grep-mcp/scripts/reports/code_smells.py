#!/usr/bin/env python3
"""Report code smells for a project folder."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from ast_grep_mcp.features.complexity.tools import detect_code_smells_tool


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect code smells")
    parser.add_argument("project", nargs="?", default=str(Path(__file__).resolve().parent.parent.parent))
    parser.add_argument("-l", "--language", default="python")
    parser.add_argument("--extended", action="store_true", help="Show full detail per smell")
    parser.add_argument("--json", dest="as_json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    result = detect_code_smells_tool(project_folder=args.project, language=args.language)

    if args.as_json:
        print(json.dumps(result, indent=2, default=str))
        return

    summary = result["summary"]
    smells = result["smells"]

    print(f"Files analyzed: {result['files_analyzed']}")
    print(f"Total smells:   {result['total_smells']}")
    print(f"By type:        {summary['by_type']}")
    sev = summary["by_severity"]
    print(f"By severity:    high={sev['high']}  medium={sev['medium']}  low={sev['low']}")
    print(f"Time:           {result['execution_time_ms']}ms")
    print()

    if not smells:
        print("No smells detected.")
        return

    if args.extended:
        for s in smells:
            print(f"  [{s['severity']}] {s['type']} in {s['file']}:{s['line']} — {s['message']}")
            print(f"         suggestion: {s['suggestion']}")
    else:
        by_file: dict[str, list] = {}
        for s in smells:
            by_file.setdefault(s["file"], []).append(s)
        for fpath in sorted(by_file):
            items = by_file[fpath]
            values = ", ".join(f"{s['name']}(L{s['line']})" for s in items)
            print(f"  {fpath} [{len(items)}]: {values}")


if __name__ == "__main__":
    main()
