"""Quality reporting system for code standards enforcement.

This module provides functionality to generate comprehensive quality reports:
- Markdown reports (human-readable)
- JSON reports (machine-readable)
- HTML reports (future)
- Trend tracking with baseline comparison
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.models.standards import EnforcementResult, RuleViolation

logger = get_logger(__name__)

# =============================================================================
# Markdown Report Generation - Helper Functions
# =============================================================================


def _generate_report_header(project_name: str, result: EnforcementResult) -> List[str]:
    """Generate report header section.

    Args:
        project_name: Name of the project
        result: Enforcement result containing metadata

    Returns:
        List of header lines
    """
    return [
        f"# Code Quality Report: {project_name}",
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Execution Time:** {result.execution_time_ms}ms",
        f"**Files Scanned:** {result.files_scanned}",
        "\n---\n",
    ]


def _generate_summary_section(result: EnforcementResult) -> List[str]:
    """Generate summary statistics section.

    Args:
        result: Enforcement result containing summary

    Returns:
        List of summary lines
    """
    summary = result.summary
    by_severity = summary.get("by_severity", {})
    return [
        "## Summary\n",
        f"- **Total Violations:** {summary['total_violations']}",
        f"- **Error:** {by_severity.get('error', 0)}",
        f"- **Warning:** {by_severity.get('warning', 0)}",
        f"- **Info:** {by_severity.get('info', 0)}",
        f"- **Files with Violations:** {summary.get('files_scanned', 0)}",
        f"- **Rules Executed:** {len(result.rules_executed)}",
        "\n---\n",
    ]


def _format_violation_entry(violation: RuleViolation) -> str:
    """Format a single violation entry.

    Args:
        violation: Violation to format

    Returns:
        Formatted violation line
    """
    file_name = Path(violation.file).name
    return f"- **{file_name}:{violation.line}** - {violation.message}"


def _generate_rule_violations_section(
    rule_id: str, rule_violations: List[RuleViolation], include_violations: bool, max_violations_per_rule: int
) -> List[str]:
    """Generate violations section for a single rule.

    Args:
        rule_id: ID of the rule
        rule_violations: List of violations for this rule
        include_violations: Whether to include violation details
        max_violations_per_rule: Max violations to show

    Returns:
        List of formatted lines for this rule
    """
    lines = [f"#### `{rule_id}` ({len(rule_violations)} occurrences)"]

    if not include_violations:
        lines.append("")
        return lines

    # Show first N violations
    shown = min(len(rule_violations), max_violations_per_rule)
    for v in rule_violations[:shown]:
        lines.append(_format_violation_entry(v))

    # Add "...and N more" if needed
    has_more_violations = len(rule_violations) > max_violations_per_rule
    if has_more_violations:
        remaining = len(rule_violations) - max_violations_per_rule
        lines.append(f"  - *...and {remaining} more*")

    lines.append("")
    return lines


def _generate_violations_by_severity_section(
    result: EnforcementResult, include_violations: bool, max_violations_per_rule: int
) -> List[str]:
    """Generate violations grouped by severity section.

    Args:
        result: Enforcement result
        include_violations: Whether to include violation details
        max_violations_per_rule: Max violations to show per rule

    Returns:
        List of section lines
    """
    lines = ["## Violations by Severity\n"]

    for severity in ["error", "warning", "info"]:
        violations = result.violations_by_severity.get(severity, [])
        if not violations:
            continue

        lines.append(f"### {severity.upper()} ({len(violations)})\n")

        # Group by rule
        by_rule: Dict[str, List[RuleViolation]] = {}
        for v in violations:
            if v.rule_id not in by_rule:
                by_rule[v.rule_id] = []
            by_rule[v.rule_id].append(v)

        # Add each rule's violations
        for rule_id, rule_violations in sorted(by_rule.items()):
            rule_lines = _generate_rule_violations_section(rule_id, rule_violations, include_violations, max_violations_per_rule)
            lines.extend(rule_lines)

    return lines


def _get_most_common_severity(violations: List[RuleViolation]) -> str:
    """Get the most common severity from a list of violations.

    Args:
        violations: List of violations

    Returns:
        Most common severity level
    """
    severities = [v.severity for v in violations]
    return max(set(severities), key=severities.count)


def _generate_top_issues_table(result: EnforcementResult) -> List[str]:
    """Generate top issues by rule table.

    Args:
        result: Enforcement result

    Returns:
        List of table lines
    """
    lines = ["\n---\n", "## Top Issues by Rule\n", "| Rule | Count | Severity |", "|------|-------|----------|"]

    # Sort rules by violation count
    rules_sorted = sorted(result.violations_by_rule.items(), key=lambda x: len(x[1]), reverse=True)[:10]  # Top 10

    for rule_id, violations in rules_sorted:
        most_common_severity = _get_most_common_severity(violations)
        lines.append(f"| `{rule_id}` | {len(violations)} | {most_common_severity} |")

    return lines


def _count_violations_by_severity(violations: List[RuleViolation]) -> tuple[int, int, int]:
    """Count violations by severity level.

    Args:
        violations: List of violations

    Returns:
        Tuple of (error_count, warning_count, info_count)
    """
    error_count = sum(1 for v in violations if v.severity == "error")
    warning_count = sum(1 for v in violations if v.severity == "warning")
    info_count = sum(1 for v in violations if v.severity == "info")
    return error_count, warning_count, info_count


def _generate_problematic_files_table(result: EnforcementResult) -> List[str]:
    """Generate files with most violations table.

    Args:
        result: Enforcement result

    Returns:
        List of table lines
    """
    lines = [
        "\n---\n",
        "## Files with Most Violations\n",
        "| File | Violations | Errors | Warnings | Info |",
        "|------|------------|--------|----------|------|",
    ]

    # Sort files by violation count
    files_sorted = sorted(result.violations_by_file.items(), key=lambda x: len(x[1]), reverse=True)[:10]  # Top 10

    for file_path, violations in files_sorted:
        file_name = Path(file_path).name
        error_count, warning_count, info_count = _count_violations_by_severity(violations)

        lines.append(f"| `{file_name}` | {len(violations)} | {error_count} | {warning_count} | {info_count} |")

    return lines


def _generate_recommendations_section(result: EnforcementResult) -> List[str]:
    """Generate recommendations section.

    Args:
        result: Enforcement result

    Returns:
        List of recommendation lines
    """
    lines = ["\n---\n", "## Recommendations\n"]
    by_severity = result.summary.get("by_severity", {})
    error_count = by_severity.get("error", 0)
    warning_count = by_severity.get("warning", 0)
    info_count = by_severity.get("info", 0)

    # Add severity-based recommendations
    if error_count > 0:
        lines.append(f"- **{error_count} errors** require immediate attention")

    if warning_count > 0:
        lines.append(f"- **{warning_count} warnings** should be addressed")

    if info_count > 0:
        lines.append(f"- **{info_count} info items** are suggestions for improvement")

    # Add auto-fix recommendation
    fixable_count = sum(1 for v in result.violations if v.fix_suggestion is not None)
    if fixable_count > 0:
        lines.append(f"\n**💡 {fixable_count} violations have automatic fixes available.**")
        lines.append("Consider using `apply_standards_fixes` to auto-fix safe violations.")

    return lines


# =============================================================================
# Markdown Report Generation - Main Function
# =============================================================================


def generate_markdown_report(
    result: EnforcementResult, project_name: str = "Project", include_violations: bool = True, max_violations_per_rule: int = 10
) -> str:
    """Generate a Markdown-formatted quality report.

    Args:
        result: EnforcementResult from enforce_standards
        project_name: Name of the project for report header
        include_violations: Whether to include violation details
        max_violations_per_rule: Maximum violations to show per rule

    Returns:
        Markdown-formatted report as string
    """
    report_lines = []

    # Generate each section
    report_lines.extend(_generate_report_header(project_name, result))
    report_lines.extend(_generate_summary_section(result))
    report_lines.extend(_generate_violations_by_severity_section(result, include_violations, max_violations_per_rule))
    report_lines.extend(_generate_top_issues_table(result))
    report_lines.extend(_generate_problematic_files_table(result))
    report_lines.extend(_generate_recommendations_section(result))

    return "\n".join(report_lines)


# =============================================================================
# JSON Report Generation
# =============================================================================


def _serialize_violation(v: RuleViolation, include_code_snippets: bool) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "file": v.file,
        "line": v.line,
        "column": v.column,
        "end_line": v.end_line,
        "end_column": v.end_column,
        "severity": v.severity,
        "rule_id": v.rule_id,
        "message": v.message,
        "fix_available": v.fix_suggestion is not None,
    }
    if include_code_snippets:
        d["code_snippet"] = v.code_snippet
        d["fix_suggestion"] = v.fix_suggestion
    return d


def _build_top_issues(result: EnforcementResult) -> List[Dict[str, Any]]:
    top_rules = sorted(result.violations_by_rule.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    return [
        {"rule_id": rule_id, "count": len(violations), "severity": violations[0].severity if violations else "unknown"}
        for rule_id, violations in top_rules
    ]


def _build_most_violations_files(result: EnforcementResult) -> List[Dict[str, Any]]:
    top_files = sorted(result.violations_by_file.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    return [
        {
            "file": file,
            "violations": len(violations),
            "errors": sum(1 for v in violations if v.severity == "error"),
            "warnings": sum(1 for v in violations if v.severity == "warning"),
            "info": sum(1 for v in violations if v.severity == "info"),
        }
        for file, violations in top_files
    ]


def generate_json_report(result: EnforcementResult, project_name: str = "Project", include_code_snippets: bool = False) -> Dict[str, Any]:
    """Generate a JSON-formatted quality report.

    Args:
        result: EnforcementResult from enforce_standards
        project_name: Name of the project
        include_code_snippets: Whether to include code snippets in output

    Returns:
        Dictionary ready for JSON serialization
    """
    by_severity = result.summary.get("by_severity", {})
    report: Dict[str, Any] = {
        "project": project_name,
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_violations": result.summary["total_violations"],
            "error_count": by_severity.get("error", 0),
            "warning_count": by_severity.get("warning", 0),
            "info_count": by_severity.get("info", 0),
            "files_scanned": result.files_scanned,
            "files_with_violations": result.summary.get("files_scanned", 0),
            "rules_executed": len(result.rules_executed),
            "execution_time_ms": result.execution_time_ms,
        },
        "rules_executed": result.rules_executed,
        "violations_by_severity": {
            "error": len(result.violations_by_severity.get("error", [])),
            "warning": len(result.violations_by_severity.get("warning", [])),
            "info": len(result.violations_by_severity.get("info", [])),
        },
        "violations_by_rule": {rule_id: len(violations) for rule_id, violations in result.violations_by_rule.items()},
        "violations_by_file": {file: len(violations) for file, violations in result.violations_by_file.items()},
        "violations": [_serialize_violation(v, include_code_snippets) for v in result.violations],
        "top_issues": _build_top_issues(result),
        "most_violations_files": _build_most_violations_files(result),
    }
    return report


# =============================================================================
# Report Generator (Main Entry Point)
# =============================================================================


def _generate_markdown_response(
    result: EnforcementResult, project_name: str, include_violations: bool, save_to_file: Optional[str]
) -> Dict[str, Any]:
    report_content = generate_markdown_report(result=result, project_name=project_name, include_violations=include_violations)
    response: Dict[str, Any] = {"format": "markdown", "content": report_content, "summary": result.summary}
    if save_to_file:
        with open(save_to_file, "w", encoding="utf-8") as f:
            f.write(report_content)
        response["saved_to"] = save_to_file
    return response


def _generate_json_response(
    result: EnforcementResult, project_name: str, include_code_snippets: bool, save_to_file: Optional[str]
) -> Dict[str, Any]:
    json_report = generate_json_report(result=result, project_name=project_name, include_code_snippets=include_code_snippets)
    if save_to_file:
        with open(save_to_file, "w", encoding="utf-8") as f:
            json.dump(json_report, f, indent=2)
    return {"format": "json", "content": json_report, "summary": result.summary, "saved_to": save_to_file}


def generate_quality_report_impl(
    result: EnforcementResult,
    project_name: str = "Project",
    output_format: str = "markdown",
    include_violations: bool = True,
    include_code_snippets: bool = False,
    save_to_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a code quality report in various formats.

    Args:
        result: EnforcementResult from enforce_standards
        project_name: Name of the project
        output_format: Format ('markdown', 'json')
        include_violations: Whether to include violation details
        include_code_snippets: Whether to include code snippets (JSON only)
        save_to_file: Optional file path to save report

    Returns:
        Dictionary with report content and metadata
    """
    if output_format == "markdown":
        return _generate_markdown_response(result, project_name, include_violations, save_to_file)
    if output_format == "json":
        return _generate_json_response(result, project_name, include_code_snippets, save_to_file)
    raise ValueError(f"Unsupported output format: {output_format}")
