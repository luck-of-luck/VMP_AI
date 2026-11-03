"""MCP tool definitions for code quality and standards features."""

import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import sentry_sdk
import yaml
from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ast_grep_mcp.constants import FilePatterns, ParallelProcessing, SecurityScanDefaults
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.features.quality.enforcer import enforce_standards_impl, format_violation_report
from ast_grep_mcp.features.quality.fixer import apply_fixes_batch
from ast_grep_mcp.features.quality.orphan_detector import detect_orphans_impl
from ast_grep_mcp.features.quality.reporter import generate_quality_report_impl
from ast_grep_mcp.features.quality.rules import RULE_TEMPLATES, create_rule_from_template, get_available_templates, save_rule_to_project
from ast_grep_mcp.features.quality.security_scanner import detect_security_issues_impl
from ast_grep_mcp.features.quality.validator import validate_rule_definition
from ast_grep_mcp.models.standards import (
    EnforcementResult,
    LintingRule,
    RuleValidationError,
    RuleViolation,
    SecurityIssue,
)
from ast_grep_mcp.utils.tool_context import tool_context

# Field description constants reused across MCP tool registrations
_PROJECT_FOLDER_DESC = "Absolute path to the project root directory"
_LANGUAGE_DESC = "Programming language (python, typescript, javascript, java, etc.)"
_OUTPUT_FORMAT_DESC = "Output format: 'json' (structured data) or 'text' (human-readable report)"
_SEVERITY_THRESHOLD_DESC = "Minimum severity to report: 'error', 'warning', 'info'"
_EXCLUDE_PATTERNS_DESC = "Glob patterns for files to exclude"
_INCLUDE_PATTERNS_DESC = "Glob patterns for files to include (e.g., ['src/**/*.py'])"


def _create_rule_from_params(
    rule_name: str,
    description: str,
    pattern: str,
    severity: str,
    language: str,
    suggested_fix: Optional[str],
    note: Optional[str],
    use_template: Optional[str],
) -> LintingRule:
    """Create a LintingRule from parameters or a template."""
    if use_template:
        overrides = {
            k: v
            for k, v in {
                "language": language,
                "severity": severity,
                "message": description,
                "pattern": pattern,
                "note": note,
                "fix": suggested_fix,
            }.items()
            if v is not None
        }
        return create_rule_from_template(use_template, rule_name, overrides)

    return LintingRule(
        id=rule_name, language=language, severity=severity, message=description, pattern=pattern, note=note, fix=suggested_fix
    )


def _save_rule_if_requested(
    rule: LintingRule, save_to_project: bool, project_folder: Optional[str], validation_result: Any
) -> Optional[str]:
    """Save rule to project if requested; returns saved path or None."""
    if not save_to_project:
        return None
    if not project_folder:
        raise ValueError("project_folder is required when save_to_project=True")
    if not validation_result.is_valid:
        raise RuleValidationError(f"Cannot save invalid rule. Errors: {', '.join(validation_result.errors)}")
    with sentry_sdk.start_span(op="save_rule", name="Save rule to project"):
        return save_rule_to_project(rule, project_folder)


def _format_rule_result(rule: LintingRule, validation_result: Any, saved_path: Optional[str]) -> Dict[str, Any]:
    """Format the rule creation result dict."""
    rule_dict = rule.to_yaml_dict()
    yaml_str = yaml.dump(rule_dict, default_flow_style=False, sort_keys=False)

    return {
        "rule": {
            "id": rule.id,
            "language": rule.language,
            "severity": rule.severity,
            "message": rule.message,
            "pattern": rule.pattern,
            "note": rule.note,
            "fix": rule.fix,
            "constraints": rule.constraints,
        },
        "validation": {"is_valid": validation_result.is_valid, "errors": validation_result.errors, "warnings": validation_result.warnings},
        "saved_to": saved_path,
        "yaml": yaml_str,
    }


def create_linting_rule_tool(
    rule_name: str,
    description: str,
    pattern: str,
    severity: str,
    language: str,
    suggested_fix: Optional[str] = None,
    note: Optional[str] = None,
    save_to_project: bool = False,
    project_folder: Optional[str] = None,
    use_template: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a custom linting rule using ast-grep patterns."""
    logger = get_logger("tool.create_linting_rule")
    logger.info(
        "tool_invoked",
        tool="create_linting_rule",
        rule_name=rule_name,
        language=language,
        severity=severity,
        use_template=use_template,
        save_to_project=save_to_project,
    )

    with tool_context("create_linting_rule", rule_name=rule_name, language=language) as run:
        with sentry_sdk.start_span(op="create_linting_rule", name="Create custom linting rule"):
            rule = _create_rule_from_params(rule_name, description, pattern, severity, language, suggested_fix, note, use_template)

            if use_template:
                logger.info("rule_created_from_template", template_id=use_template)

            with sentry_sdk.start_span(op="validate_rule", name="Validate rule definition"):
                validation_result = validate_rule_definition(rule)

            saved_path = _save_rule_if_requested(rule, save_to_project, project_folder, validation_result)
            result = _format_rule_result(rule, validation_result, saved_path)

            run.add_completion_fields(
                rule_id=rule.id,
                is_valid=validation_result.is_valid,
                saved=saved_path is not None,
            )

            return result


def list_rule_templates_tool(language: Optional[str] = None, category: Optional[str] = None) -> Dict[str, Any]:
    """List available pre-built rule templates, optionally filtered by language or category."""
    logger = get_logger("tool.list_rule_templates")
    logger.info("tool_invoked", tool="list_rule_templates", language=language, category=category)

    with tool_context("list_rule_templates", language=language, category=category) as run:
        with sentry_sdk.start_span(op="list_templates", name="Get rule templates"):
            templates = get_available_templates(language=language, category=category)

            all_templates = list(RULE_TEMPLATES.values())
            all_languages = sorted(set(t.language for t in all_templates))
            all_categories = sorted(set(t.category for t in all_templates))

            template_dicts = [
                {
                    "id": t.id,
                    "name": t.name,
                    "description": t.description,
                    "language": t.language,
                    "severity": t.severity,
                    "pattern": t.pattern,
                    "message": t.message,
                    "note": t.note,
                    "fix": t.fix,
                    "category": t.category,
                }
                for t in templates
            ]

            run.add_completion_fields(
                total_templates=len(template_dicts),
                filtered=bool(language or category),
            )

            return {
                "total_templates": len(template_dicts),
                "languages": all_languages,
                "categories": all_categories,
                "applied_filters": {"language": language, "category": category},
                "templates": template_dicts,
            }


def _get_default_exclude_patterns() -> List[str]:
    """Return the default file exclusion patterns for quality scans."""
    return FilePatterns.normalize_excludes(None)


def _validate_enforcement_inputs(severity_threshold: str, output_format: str) -> None:
    """Validate severity_threshold and output_format; raises ValueError if invalid."""
    if severity_threshold not in ["error", "warning", "info"]:
        raise ValueError(f"Invalid severity_threshold: {severity_threshold}. Must be 'error', 'warning', or 'info'.")

    if output_format not in ["json", "text"]:
        raise ValueError(f"Invalid output_format: {output_format}. Must be 'json' or 'text'.")


def _format_enforcement_output(result: EnforcementResult, output_format: str) -> Dict[str, Any]:
    """Format enforcement result as 'text' or structured JSON dict."""
    if output_format == "text":
        return {"summary": result.summary, "report": format_violation_report(result)}

    violations_data = []
    for v in result.violations:
        violations_data.append(
            {
                "file": v.file,
                "line": v.line,
                "column": v.column,
                "end_line": v.end_line,
                "end_column": v.end_column,
                "severity": v.severity,
                "rule_id": v.rule_id,
                "message": v.message,
                "code_snippet": v.code_snippet,
                "fix_suggestion": v.fix_suggestion,
                "meta_vars": v.meta_vars,
            }
        )

    violations_by_file_data = {}
    for file, violations in result.violations_by_file.items():
        violations_by_file_data[file] = [
            {"line": v.line, "severity": v.severity, "rule_id": v.rule_id, "message": v.message} for v in violations
        ]

    return {
        "summary": result.summary,
        "violations": violations_data,
        "violations_by_file": violations_by_file_data,
        "rules_executed": result.rules_executed,
        "execution_time_ms": result.execution_time_ms,
    }


def enforce_standards_tool(
    project_folder: str,
    language: str,
    rule_set: str = "recommended",
    custom_rules: List[str] | None = None,
    include_patterns: List[str] | None = None,
    exclude_patterns: List[str] | None = None,
    severity_threshold: str = "info",
    max_violations: int = SecurityScanDefaults.MAX_ISSUES,
    max_threads: int = ParallelProcessing.DEFAULT_WORKERS,
    output_format: str = "json",
) -> Dict[str, Any]:
    """Run linting rules against a project and return violations with statistics."""
    if custom_rules is None:
        custom_rules = []
    if include_patterns is None:
        include_patterns = ["**/*"]
    exclude_patterns = FilePatterns.normalize_excludes(exclude_patterns)

    logger = get_logger("tool.enforce_standards")
    logger.info(
        "tool_invoked",
        tool="enforce_standards",
        project_folder=project_folder,
        language=language,
        rule_set=rule_set,
        custom_rules_count=len(custom_rules),
        max_violations=max_violations,
        max_threads=max_threads,
    )

    with tool_context("enforce_standards", project_folder=project_folder, language=language, rule_set=rule_set) as run:
        _validate_enforcement_inputs(severity_threshold, output_format)

        result = enforce_standards_impl(
            project_folder=project_folder,
            language=language,
            rule_set=rule_set,
            custom_rules=custom_rules,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            severity_threshold=severity_threshold,
            max_violations=max_violations,
            max_threads=max_threads,
        )

        run.add_completion_fields(
            total_violations=result.summary["total_violations"],
            files_scanned=result.files_scanned,
        )

        return _format_enforcement_output(result, output_format)


def _convert_violations_to_objects(violations: List[Dict[str, Any]]) -> List[RuleViolation]:
    violation_objects = []
    for v_dict in violations:
        violation = RuleViolation(
            file=v_dict["file"],
            line=v_dict["line"],
            column=v_dict.get("column", 1),
            end_line=v_dict.get("end_line", v_dict["line"]),
            end_column=v_dict.get("end_column", 1),
            severity=v_dict["severity"],
            rule_id=v_dict["rule_id"],
            message=v_dict["message"],
            code_snippet=v_dict["code_snippet"],
            fix_suggestion=v_dict.get("fix_suggestion"),
            meta_vars=v_dict.get("meta_vars"),
        )
        violation_objects.append(violation)
    return violation_objects


def _infer_project_folder(violations: List[Dict[str, Any]]) -> str:
    """Infer project folder from the common prefix of violation file paths."""
    if not violations:
        return os.getcwd()
    all_files = [v.get("file", "") for v in violations if v.get("file")]
    if not all_files:
        return os.getcwd()
    common_prefix = os.path.commonprefix(all_files)
    if not os.path.isdir(common_prefix):
        return cast(str, os.path.dirname(common_prefix))
    return cast(str, common_prefix)


def _format_fix_results(result: Any, dry_run: bool) -> Dict[str, Any]:
    return {
        "summary": {
            "total_violations": result.total_violations,
            "fixes_attempted": result.fixes_attempted,
            "fixes_successful": result.fixes_successful,
            "fixes_failed": result.fixes_failed,
            "files_modified": len(result.files_modified),
            "validation_passed": result.validation_passed,
            "dry_run": dry_run,
        },
        "backup_id": result.backup_id,
        "files_modified": result.files_modified,
        "results": [
            {
                "file": r.violation.file,
                "line": r.violation.line,
                "rule_id": r.violation.rule_id,
                "success": r.success,
                "file_modified": r.file_modified,
                "original_code": r.original_code,
                "fixed_code": r.fixed_code,
                "syntax_valid": r.syntax_valid,
                "error": r.error,
                "fix_type": r.fix_type,
            }
            for r in result.results
        ],
        "execution_time_ms": result.execution_time_ms,
    }


def apply_standards_fixes_tool(
    violations: List[Dict[str, Any]], language: str, fix_types: List[str] | None = None, dry_run: bool = True, create_backup: bool = True
) -> Dict[str, Any]:
    """Apply automatic fixes for violations from enforce_standards."""
    if fix_types is None:
        fix_types = ["safe"]

    logger = get_logger("tool.apply_standards_fixes")
    logger.info(
        "tool_invoked",
        tool="apply_standards_fixes",
        violations_count=len(violations),
        language=language,
        fix_types=fix_types,
        dry_run=dry_run,
        create_backup=create_backup,
    )

    with tool_context("apply_standards_fixes", violations_count=len(violations), language=language, fix_types=fix_types) as run:
        violation_objects = _convert_violations_to_objects(violations)
        project_folder_inferred = _infer_project_folder(violations)

        result = apply_fixes_batch(
            violations=violation_objects,
            language=language,
            project_folder=project_folder_inferred,
            fix_types=fix_types,
            dry_run=dry_run,
            create_backup_flag=create_backup,
        )

        run.add_completion_fields(
            total_violations=result.total_violations,
            fixes_attempted=result.fixes_attempted,
            fixes_successful=result.fixes_successful,
            fixes_failed=result.fixes_failed,
            dry_run=dry_run,
        )

        return _format_fix_results(result, dry_run)


def generate_quality_report_tool(
    enforcement_result: Dict[str, Any],
    project_name: str = "Project",
    output_format: str = "markdown",
    include_violations: bool = True,
    include_code_snippets: bool = False,
    save_to_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a markdown or JSON quality report from enforce_standards results."""
    logger = get_logger("tool.generate_quality_report")
    logger.info(
        "tool_invoked", tool="generate_quality_report", project_name=project_name, output_format=output_format, save_to_file=save_to_file
    )

    with tool_context("generate_quality_report", project_name=project_name, output_format=output_format) as run:
        result_obj = _dict_to_enforcement_result(enforcement_result)

        if project_name == "Project":
            inferred_folder = _infer_project_folder(enforcement_result.get("violations", []))
            project_name = Path(inferred_folder).name or "Project"

        report = generate_quality_report_impl(
            result=result_obj,
            project_name=project_name,
            output_format=output_format,
            include_violations=include_violations,
            include_code_snippets=include_code_snippets,
            save_to_file=save_to_file,
        )

        run.add_completion_fields(
            output_format=output_format,
            saved=save_to_file is not None,
        )

        return report


def _group_violations(
    violations: List[RuleViolation],
) -> tuple[
    Dict[str, List[RuleViolation]],
    Dict[str, List[RuleViolation]],
    Dict[str, List[RuleViolation]],
]:
    """Group violations into by-file, by-severity, and by-rule dictionaries."""
    by_file: Dict[str, List[RuleViolation]] = defaultdict(list)
    by_severity: Dict[str, List[RuleViolation]] = defaultdict(list)
    by_rule: Dict[str, List[RuleViolation]] = defaultdict(list)

    for v in violations:
        by_file[v.file].append(v)
        by_severity[v.severity].append(v)
        by_rule[v.rule_id].append(v)

    return dict(by_file), dict(by_severity), dict(by_rule)


def _dict_to_enforcement_result(data: Dict[str, Any]) -> EnforcementResult:
    """Convert a raw enforcement result dict into a typed EnforcementResult object."""
    violations = _convert_violations_to_objects(data.get("violations", []))
    by_file, by_severity, by_rule = _group_violations(violations)

    return EnforcementResult(
        summary=data.get("summary", {}),
        violations=violations,
        violations_by_file=by_file,
        violations_by_severity=by_severity,
        violations_by_rule=by_rule,
        rules_executed=data.get("rules_executed", []),
        execution_time_ms=data.get("execution_time_ms", 0),
        files_scanned=data.get("summary", {}).get("files_scanned", 0),
    )


def _format_security_issues(issues: List[SecurityIssue]) -> List[Dict[str, Any]]:
    return [
        {
            "file": issue.file,
            "line": issue.line,
            "column": issue.column,
            "end_line": issue.end_line,
            "end_column": issue.end_column,
            "issue_type": issue.issue_type,
            "severity": issue.severity,
            "title": issue.title,
            "description": issue.description,
            "code_snippet": issue.code_snippet,
            "remediation": issue.remediation,
            "cwe_id": issue.cwe_id,
            "confidence": issue.confidence,
            "references": issue.references,
        }
        for issue in issues
    ]


def _format_issues_by_severity(result: Any) -> Dict[str, List[Dict[str, Any]]]:
    formatted = {}
    for severity, issues in result.issues_by_severity.items():
        formatted[severity] = [
            {"file": issue.file, "line": issue.line, "title": issue.title, "issue_type": issue.issue_type, "cwe_id": issue.cwe_id}
            for issue in issues
        ]
    return formatted


def detect_security_issues_tool(
    project_folder: str,
    language: str,
    issue_types: List[str] | None = None,
    severity_threshold: str = "low",
    max_issues: int = SecurityScanDefaults.MAX_ISSUES,
) -> Dict[str, Any]:
    """Scan code for security vulnerabilities (SQL injection, XSS, hardcoded secrets, etc.)."""
    if issue_types is None:
        issue_types = ["all"]

    logger = get_logger("tool.detect_security_issues")
    logger.info(
        "tool_invoked",
        tool="detect_security_issues",
        project_folder=project_folder,
        language=language,
        issue_types=issue_types,
        severity_threshold=severity_threshold,
        max_issues=max_issues,
    )

    with tool_context("detect_security_issues", project_folder=project_folder, language=language, issue_types=issue_types) as run:
        result = detect_security_issues_impl(
            project_folder=project_folder,
            language=language,
            issue_types=issue_types,
            severity_threshold=severity_threshold,
            max_issues=max_issues,
        )

        run.add_completion_fields(
            total_issues=result.summary["total_issues"],
            critical_count=result.summary["critical_count"],
            high_count=result.summary["high_count"],
            files_scanned=result.files_scanned,
        )

        return {
            "summary": result.summary,
            "issues": _format_security_issues(result.issues),
            "issues_by_severity": _format_issues_by_severity(result),
            "issues_by_type": {issue_type: len(issues) for issue_type, issues in result.issues_by_type.items()},
            "files_scanned": result.files_scanned,
            "execution_time_ms": result.execution_time_ms,
        }


def detect_orphans_tool(
    project_folder: str,
    include_patterns: List[str] | None = None,
    exclude_patterns: List[str] | None = None,
    analyze_functions: bool = True,
    verify_with_grep: bool = True,
) -> Dict[str, Any]:
    """Detect orphan files and functions never imported or called in a project."""
    logger = get_logger("tool.detect_orphans")
    logger.info(
        "tool_invoked",
        tool="detect_orphans",
        project_folder=project_folder,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
        analyze_functions=analyze_functions,
        verify_with_grep=verify_with_grep,
    )

    with tool_context("detect_orphans", project_folder=project_folder, analyze_functions=analyze_functions) as run:
        result = detect_orphans_impl(
            project_folder=project_folder,
            include_patterns=include_patterns,
            exclude_patterns=FilePatterns.normalize_excludes(exclude_patterns),
            analyze_functions=analyze_functions,
            verify_with_grep=verify_with_grep,
        )

        run.add_completion_fields(
            orphan_files=result["summary"]["orphan_files"],
            orphan_functions=result["summary"]["orphan_functions"],
            total_files=result["summary"]["total_files_analyzed"],
        )

        return result


def _register_linting_tools(mcp: FastMCP) -> None:
    """Register linting rule tools with MCP server."""

    @mcp.tool()
    def create_linting_rule(
        rule_name: str = Field(description="Unique rule identifier (e.g., 'no-console-log')"),
        description: str = Field(description="Human-readable description of what the rule checks"),
        pattern: str = Field(description="ast-grep pattern to match (e.g., 'console.log($$$)')"),
        severity: str = Field(description="Severity level: 'error', 'warning', or 'info'"),
        language: str = Field(description=_LANGUAGE_DESC),
        suggested_fix: Optional[str] = Field(default=None, description="Optional replacement pattern or fix suggestion"),
        note: Optional[str] = Field(default=None, description="Additional note or explanation"),
        save_to_project: bool = Field(default=False, description="If True, save rule to project's .ast-grep-rules/"),
        project_folder: Optional[str] = Field(default=None, description=_PROJECT_FOLDER_DESC),
        use_template: Optional[str] = Field(default=None, description="Optional template ID to use as base"),
    ) -> Dict[str, Any]:
        """Create a custom linting rule from an ast-grep pattern."""
        return create_linting_rule_tool(
            rule_name=rule_name,
            description=description,
            pattern=pattern,
            severity=severity,
            language=language,
            suggested_fix=suggested_fix,
            note=note,
            save_to_project=save_to_project,
            project_folder=project_folder,
            use_template=use_template,
        )

    @mcp.tool()
    def list_rule_templates(
        language: Optional[str] = Field(default=None, description=_LANGUAGE_DESC),
        category: Optional[str] = Field(default=None, description="Filter by category (general, security, performance, style)"),
    ) -> Dict[str, Any]:
        """List available pre-built rule templates."""
        return list_rule_templates_tool(language=language, category=category)


def _register_enforcement_tools(mcp: FastMCP) -> None:
    """Register enforcement, fix, and report tools with MCP server."""

    @mcp.tool()
    def enforce_standards(
        project_folder: str = Field(description=_PROJECT_FOLDER_DESC),
        language: str = Field(description=_LANGUAGE_DESC),
        rule_set: str = Field(
            default="recommended", description="Rule set to use: 'recommended', 'security', 'performance', 'style', 'custom', 'all'"
        ),
        custom_rules: List[str] = Field(
            default_factory=list, description="List of custom rule IDs from .ast-grep-rules/ (used with rule_set='custom')"
        ),
        include_patterns: List[str] = Field(default_factory=lambda: ["**/*"], description=_INCLUDE_PATTERNS_DESC),
        exclude_patterns: List[str] = Field(default_factory=_get_default_exclude_patterns, description=_EXCLUDE_PATTERNS_DESC),
        severity_threshold: str = Field(default="info", description=_SEVERITY_THRESHOLD_DESC),
        max_violations: int = Field(
            default=SecurityScanDefaults.MAX_ISSUES,
            description="Maximum violations to find (0 = unlimited). Stops execution early when reached.",
        ),
        max_threads: int = Field(
            default=ParallelProcessing.DEFAULT_WORKERS, description="Number of parallel threads for rule execution (default: 4)"
        ),
        output_format: str = Field(default="json", description=_OUTPUT_FORMAT_DESC),
    ) -> Dict[str, Any]:
        """Enforce coding standards using ast-grep rules."""
        return enforce_standards_tool(
            project_folder=project_folder,
            language=language,
            rule_set=rule_set,
            custom_rules=custom_rules,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            severity_threshold=severity_threshold,
            max_violations=max_violations,
            max_threads=max_threads,
            output_format=output_format,
        )

    @mcp.tool()
    def apply_standards_fixes(
        violations: List[Dict[str, Any]] = Field(description="List of violations from enforce_standards to fix"),
        language: str = Field(description=_LANGUAGE_DESC),
        fix_types: List[str] = Field(
            default_factory=lambda: ["safe"],
            description="Types of fixes to apply: 'safe' (guaranteed-safe), 'suggested' (may need review), 'all'",
        ),
        dry_run: bool = Field(default=True, description="If True, preview fixes without applying them"),
        create_backup: bool = Field(default=True, description="If True, create backup before applying fixes"),
    ) -> Dict[str, Any]:
        """Apply automatic fixes for standards violations."""
        return apply_standards_fixes_tool(
            violations=violations, language=language, fix_types=fix_types, dry_run=dry_run, create_backup=create_backup
        )

    @mcp.tool()
    def generate_quality_report(
        enforcement_result: Dict[str, Any] = Field(description="Result dictionary from enforce_standards tool"),
        project_name: str = Field(default="Project", description="Name of the project for report header"),
        output_format: str = Field(default="markdown", description="Report format ('markdown' or 'json')"),
        include_violations: bool = Field(default=True, description="Whether to include detailed violation listings"),
        include_code_snippets: bool = Field(default=False, description="Whether to include code snippets (JSON only)"),
        save_to_file: Optional[str] = Field(default=None, description="Optional file path to save the report"),
    ) -> Dict[str, Any]:
        """Generate a quality report from enforcement results."""
        return generate_quality_report_tool(
            enforcement_result=enforcement_result,
            project_name=project_name,
            output_format=output_format,
            include_violations=include_violations,
            include_code_snippets=include_code_snippets,
            save_to_file=save_to_file,
        )


def _register_scanning_tools(mcp: FastMCP) -> None:
    """Register security and orphan scanning tools with MCP server."""

    @mcp.tool()
    def detect_security_issues(
        project_folder: str = Field(description=_PROJECT_FOLDER_DESC),
        language: str = Field(description=_LANGUAGE_DESC),
        issue_types: List[str] | None = Field(
            default=None,
            description="Types: 'sql_injection', 'xss', 'command_injection', 'hardcoded_secrets', 'insecure_crypto', or None for all",
        ),
        severity_threshold: str = Field(default="low", description="Minimum severity to report: 'critical', 'high', 'medium', 'low'"),
        max_issues: int = Field(default=SecurityScanDefaults.MAX_ISSUES, description="Maximum number of issues to return (0 = unlimited)"),
    ) -> Dict[str, Any]:
        """Detect security vulnerabilities using ast-grep patterns."""
        return detect_security_issues_tool(
            project_folder=project_folder,
            language=language,
            issue_types=issue_types,
            severity_threshold=severity_threshold,
            max_issues=max_issues,
        )

    @mcp.tool()
    def detect_orphans(
        project_folder: str = Field(description=_PROJECT_FOLDER_DESC),
        include_patterns: List[str] | None = Field(
            default=None,
            description="Glob patterns for files to include (e.g., ['**/*.py', '**/*.ts']). Defaults to Python and TypeScript files.",
        ),
        exclude_patterns: List[str] | None = Field(
            default=None,
            description=_EXCLUDE_PATTERNS_DESC,
        ),
        analyze_functions: bool = Field(default=True, description="Whether to analyze function-level orphans in addition to files"),
        verify_with_grep: bool = Field(default=True, description="Whether to double-check orphans with grep to reduce false positives"),
    ) -> Dict[str, Any]:
        """Detect orphaned files and functions in a project."""
        return detect_orphans_tool(
            project_folder=project_folder,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            analyze_functions=analyze_functions,
            verify_with_grep=verify_with_grep,
        )


def register_quality_tools(mcp: FastMCP) -> None:
    """Register all quality feature tools with MCP server.

    Note: detect_code_smells is registered in register_complexity_tools() to consolidate
    code smell detection with complexity analysis.
    """
    _register_linting_tools(mcp)
    _register_enforcement_tools(mcp)
    _register_scanning_tools(mcp)
