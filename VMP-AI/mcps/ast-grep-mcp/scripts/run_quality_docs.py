#!/usr/bin/env python3
"""Run Quality (7) and Documentation (5) tools against a target directory."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tool_result_recorder import record_tool_result  # noqa: E402

TARGET = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "code" / "jobs")
LANG = sys.argv[2] if len(sys.argv) > 2 else "typescript"

results: dict[str, dict] = {}


def record(name, result=None, error=None, skipped=None):
    record_tool_result(
        results,
        name,
        result=result,
        error=error,
        skipped=skipped,
        include_string_preview=False,
        include_other_fallback=False,
    )


def main():
    start = time.time()
    print(f"Running Quality + Documentation tools against {TARGET}")
    print(f"Language: {LANG}\n")

    # ── Quality tools (7) ──
    from ast_grep_mcp.features.quality.tools import (
        create_linting_rule_tool,
        detect_orphans_tool,
        detect_security_issues_tool,
        enforce_standards_tool,
        generate_quality_report_tool,
        list_rule_templates_tool,
    )

    try:
        r = create_linting_rule_tool(
            rule_name="no-console-log",
            description="Disallow console.log",
            pattern="console.log($$$ARGS)",
            severity="warning",
            language=LANG,
        )
        record("create_linting_rule", r)
    except Exception as e:
        record("create_linting_rule", error=e)

    try:
        r = list_rule_templates_tool(language=LANG)
        record("list_rule_templates", r)
    except Exception as e:
        record("list_rule_templates", error=e)

    try:
        r = enforce_standards_tool(project_folder=TARGET, language=LANG)
        record("enforce_standards", r)
    except Exception as e:
        record("enforce_standards", error=e)

    try:
        r = detect_security_issues_tool(project_folder=TARGET, language=LANG)
        record("detect_security_issues", r)
    except Exception as e:
        record("detect_security_issues", error=e)

    try:
        r = detect_orphans_tool(project_folder=TARGET)
        record("detect_orphans", r)
    except Exception as e:
        record("detect_orphans", error=e)

    # generate_quality_report needs enforcement_result
    try:
        enforcement = enforce_standards_tool(project_folder=TARGET, language=LANG)
        r = generate_quality_report_tool(enforcement_result=enforcement, project_name="jobs")
        record("generate_quality_report", r)
    except Exception as e:
        record("generate_quality_report", error=e)

    # apply_standards_fixes requires specific violations
    record("apply_standards_fixes", skipped="Requires violations list from enforce_standards")

    # ── Documentation tools (5) ──
    from ast_grep_mcp.features.documentation.tools import (
        generate_api_docs_tool,
        generate_changelog_tool,
        generate_docstrings_tool,
        generate_readme_sections_tool,
        sync_documentation_tool,
    )

    try:
        r = generate_docstrings_tool(project_folder=TARGET, file_pattern="**/*.ts", language=LANG, dry_run=True)
        record("generate_docstrings", r)
    except Exception as e:
        record("generate_docstrings", error=e)

    try:
        r = generate_readme_sections_tool(project_folder=TARGET, language=LANG)
        record("generate_readme_sections", r)
    except Exception as e:
        record("generate_readme_sections", error=e)

    try:
        r = generate_api_docs_tool(project_folder=TARGET, language=LANG)
        record("generate_api_docs", r)
    except Exception as e:
        record("generate_api_docs", error=e)

    try:
        r = generate_changelog_tool(project_folder=TARGET)
        record("generate_changelog", r)
    except Exception as e:
        record("generate_changelog", error=e)

    try:
        r = sync_documentation_tool(project_folder=TARGET, language=LANG, check_only=True)
        record("sync_documentation", r)
    except Exception as e:
        record("sync_documentation", error=e)

    elapsed = time.time() - start
    ok = sum(1 for r in results.values() if r["status"] == "OK")
    err = sum(1 for r in results.values() if r["status"] == "ERROR")
    skip = sum(1 for r in results.values() if r["status"] == "SKIPPED")

    print(f"\n{'=' * 70}")
    print(f"RESULTS: {ok} OK | {err} ERROR | {skip} SKIPPED | {len(results)} total | {elapsed:.1f}s")
    print(f"{'=' * 70}\n")

    for name, entry in results.items():
        status = entry["status"]
        icon = {"OK": "+", "ERROR": "!", "SKIPPED": "-"}[status]
        line = f"[{icon}] {name}"
        if status == "ERROR":
            line += f"  -> {entry.get('error', '')[:120]}"
        elif status == "SKIPPED":
            line += f"  -> {entry.get('reason', '')}"
        elif status == "OK":
            extras = []
            for k, v in entry.items():
                if k in ("tool", "status", "result_keys"):
                    continue
                if k.endswith("_count"):
                    extras.append(f"{k}={v}")
                elif isinstance(v, (int, float)) and k not in ("result_length",):
                    extras.append(f"{k}={v}")
            if extras:
                line += f"  ({', '.join(extras[:5])})"
        print(line)

    out = Path(__file__).parent / "quality_docs_results.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results: {out}")


if __name__ == "__main__":
    main()
