"""Rule validation for linting rules.

This module provides validation functionality for LintingRule objects:
- Pattern syntax validation using ast-grep
- Rule definition validation (severity, language, ID format, message)
- Complete rule validation
"""

import re
import subprocess
from typing import Any, Dict, List

import sentry_sdk

from ast_grep_mcp.core.executor import get_supported_languages, run_ast_grep
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.models.standards import LintingRule, RuleValidationResult

_TEST_CODE_BY_LANGUAGE = {
    "python": "def test(): pass",
    "typescript": "function test() {}",
    "javascript": "function test() {}",
    "java": "class Test { void test() {} }",
    "go": "func test() {}",
    "rust": "fn test() {}",
}
_DEFAULT_TEST_CODE = "function test() {}"


def _classify_pattern_error(error_msg: str, errors: List[str], warnings: List[str], logger: Any) -> None:
    if "parse error" in error_msg.lower() or "invalid pattern" in error_msg.lower():
        errors.append(f"Pattern syntax error: {error_msg}")
        logger.warning("pattern_syntax_error", error=error_msg)
    else:
        warnings.append(f"Pattern validated but returned: {error_msg}")


def validate_rule_pattern(pattern: str, language: str) -> RuleValidationResult:
    """Validate ast-grep pattern syntax by attempting a dry-run search.

    Args:
        pattern: The ast-grep pattern to validate
        language: Target language for the pattern

    Returns:
        RuleValidationResult with validation status and any errors/warnings
    """
    logger = get_logger("validate_rule_pattern")
    errors: List[str] = []
    warnings: List[str] = []
    test_code = _TEST_CODE_BY_LANGUAGE.get(language, _DEFAULT_TEST_CODE)

    try:
        with sentry_sdk.start_span(op="validate_pattern", name="Test ast-grep pattern"):
            _ = run_ast_grep("run", ["--pattern", pattern, "--lang", language], input_text=test_code)
        logger.info("pattern_validated", language=language, pattern_length=len(pattern))
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if hasattr(e, "stderr") and e.stderr else str(e)
        _classify_pattern_error(error_msg, errors, warnings, logger)
    except Exception as e:
        errors.append(f"Failed to validate pattern: {str(e)}")
        logger.error("pattern_validation_failed", error=str(e))

    is_valid = len(errors) == 0
    return RuleValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


_VALID_SEVERITIES = {"error", "warning", "info"}


def _validate_rule_fields(rule: LintingRule, errors: List[str], warnings: List[str]) -> None:
    if rule.severity not in _VALID_SEVERITIES:
        errors.append(f"Invalid severity '{rule.severity}'. Must be one of: error, warning, info")

    supported_languages = get_supported_languages()
    if rule.language not in supported_languages:
        errors.append(f"Unsupported language '{rule.language}'. Supported: {', '.join(supported_languages)}")

    if not re.match(r"^[a-z][a-z0-9-]*$", rule.id):
        errors.append(f"Invalid rule ID '{rule.id}'. Use kebab-case (e.g., 'no-console-log')")

    if not rule.message or not rule.message.strip():
        errors.append("Rule message cannot be empty")

    if not rule.pattern or not rule.pattern.strip():
        errors.append("Rule pattern cannot be empty")
    else:
        pattern_result = validate_rule_pattern(rule.pattern, rule.language)
        errors.extend(pattern_result.errors)
        warnings.extend(pattern_result.warnings)

    if not rule.fix:
        warnings.append("No fix suggestion provided - consider adding one to help developers")


def validate_rule_definition(rule: LintingRule) -> RuleValidationResult:
    """Validate complete rule definition.

    Checks:
    - Pattern syntax is valid
    - Severity is one of: error, warning, info
    - Language is supported
    - ID follows naming conventions (kebab-case)
    - Message is not empty

    Args:
        rule: The LintingRule to validate

    Returns:
        RuleValidationResult with validation status and any errors/warnings
    """
    logger = get_logger("validate_rule_definition")
    errors: List[str] = []
    warnings: List[str] = []

    _validate_rule_fields(rule, errors, warnings)

    is_valid = len(errors) == 0
    logger.info("rule_validated", rule_id=rule.id, is_valid=is_valid, error_count=len(errors), warning_count=len(warnings))

    return RuleValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


def validate_linting_rules_impl(rules: List[LintingRule], fail_fast: bool = False) -> Dict[str, Any]:
    """Validate multiple linting rules.

    Args:
        rules: List of LintingRule objects to validate
        fail_fast: Stop validation on first error

    Returns:
        Dictionary with validation results for all rules
    """
    logger = get_logger("validate_linting_rules")
    results = []

    for rule in rules:
        validation = validate_rule_definition(rule)
        results.append({"rule_id": rule.id, "is_valid": validation.is_valid, "errors": validation.errors, "warnings": validation.warnings})

        if fail_fast and not validation.is_valid:
            break

    # Summary statistics
    total = len(results)
    valid = sum(1 for r in results if r["is_valid"])
    invalid = total - valid

    logger.info("validation_completed", total=total, valid=valid, invalid=invalid, fail_fast=fail_fast)

    return {"summary": {"total": total, "valid": valid, "invalid": invalid}, "results": results}
