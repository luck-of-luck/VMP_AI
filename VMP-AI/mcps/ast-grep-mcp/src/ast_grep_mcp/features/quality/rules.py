"""Rule management for linting and code quality standards.

This module provides:
- RULE_TEMPLATES: 24+ pre-built rule templates
- Rule loading/saving to .ast-grep-rules/ directory
- Template instantiation and customization
- Rule CRUD operations
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import sentry_sdk
import yaml

from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.models.standards import LintingRule, RuleStorageError, RuleTemplate

# =============================================================================
# Pre-built rule templates library (24 templates)
# =============================================================================

RULE_TEMPLATES: Dict[str, RuleTemplate] = {
    # JavaScript/TypeScript templates (13 rules)
    "no-var": RuleTemplate(
        id="no-var",
        name="No var declarations",
        description="Disallow var declarations, prefer const or let",
        language="typescript",
        severity="warning",
        pattern="var $NAME = $$$",
        message="Use const or let instead of var",
        note="var has function scope which can lead to bugs. Use const for constants or let for variables.",
        fix="Replace with const or let depending on whether the variable is reassigned",
        category="style",
    ),
    "no-double-equals": RuleTemplate(
        id="no-double-equals",
        name="No loose equality",
        description="Disallow == and !=, prefer === and !==",
        language="typescript",
        severity="warning",
        pattern="",
        message="Use === instead of == for type-safe comparison",
        note="Loose equality (==) performs type coercion which can lead to unexpected results. "
        "Exception: == null is intentional TypeScript idiom for checking both null and undefined.",
        fix="Replace == with === or != with !==",
        category="security",
        constraints={
            "all": [
                {"pattern": "$A == $B"},
                {
                    "not": {
                        "any": [
                            {"pattern": "$_ == null"},
                            {"pattern": "$_ == undefined"},
                            {"pattern": "null == $_"},
                            {"pattern": "undefined == $_"},
                        ]
                    }
                },
            ]
        },
    ),
    "no-console-log": RuleTemplate(
        id="no-console-log",
        name="No console.log",
        description="Disallow console.log in production code",
        language="typescript",
        severity="warning",
        pattern="console.log($$$)",
        message="Remove console.log before committing",
        note="Use a proper logging framework instead of console.log in production.",
        category="style",
        exclude_files=[
            "**/scripts/**",
            "**/bin/**",
            "**/cli/**",
            "**/examples/**",
            "**/pipeline-runners/**",
            "**/test_*.ts",
            "**/*_test.ts",
            "**/*.test.ts",
            "**/*.spec.ts",
            "**/tests/**",
            "**/__tests__/**",
        ],
    ),
    "prefer-const": RuleTemplate(
        id="prefer-const",
        name="Prefer const",
        description="Suggest const for variables that are never reassigned",
        language="typescript",
        severity="info",
        pattern="let $NAME = $INIT",
        message="This variable is never reassigned, use const instead",
        note="Using const makes code more predictable and prevents accidental reassignment.",
        fix="Replace let with const",
        category="style",
    ),
    "no-unused-vars": RuleTemplate(
        id="no-unused-vars",
        name="No unused variables",
        description="Detect unused variable declarations",
        language="typescript",
        severity="warning",
        pattern="const $NAME = $$$",
        message="Variable is declared but never used",
        note="Unused variables indicate dead code that should be removed.",
        category="general",
    ),
    "no-empty-catch": RuleTemplate(
        id="no-empty-catch",
        name="No empty catch blocks",
        description="Disallow empty catch blocks",
        language="typescript",
        severity="error",
        pattern="",
        message="Empty catch block detected - handle the error or add a comment explaining why it's ignored",
        note="Empty catch blocks silently swallow errors, making debugging difficult.",
        category="security",
        constraints={"kind": "catch_clause", "has": {"field": "body", "pattern": "{}"}},
    ),
    "no-any-type": RuleTemplate(
        id="no-any-type",
        name="No any type",
        description="Disallow the any type in TypeScript",
        language="typescript",
        severity="warning",
        pattern="$NAME: any",
        message="Avoid using any type - use specific types instead",
        note="Using any defeats the purpose of TypeScript's type system.",
        category="style",
    ),
    "no-magic-numbers": RuleTemplate(
        id="no-magic-numbers",
        name="No magic numbers",
        description="Disallow magic numbers, prefer named constants",
        language="typescript",
        severity="info",
        pattern="$X * 86400",
        message="Replace magic number with a named constant",
        note="Magic numbers make code harder to understand and maintain.",
        fix="Extract to a named constant (e.g., SECONDS_PER_DAY)",
        category="style",
    ),
    "no-todo-comments": RuleTemplate(
        id="no-todo-comments",
        name="No TODO comments",
        description="Detect TODO comments that should be tracked in issue tracker",
        language="typescript",
        severity="info",
        pattern="// TODO",
        message="TODO found - create a ticket to track this work",
        note="TODO comments should be tracked in your issue tracker.",
        category="general",
    ),
    "no-fixme-comments": RuleTemplate(
        id="no-fixme-comments",
        name="No FIXME comments",
        description="Detect FIXME comments that indicate problematic code",
        language="typescript",
        severity="warning",
        pattern="// FIXME",
        message="FIXME found - this indicates a known issue that needs fixing",
        note="FIXME comments indicate code that needs to be fixed before production.",
        category="general",
    ),
    "no-debugger": RuleTemplate(
        id="no-debugger",
        name="No debugger statements",
        description="Disallow debugger statements",
        language="typescript",
        severity="error",
        pattern="debugger",
        message="Remove debugger statement before committing",
        note="debugger statements should not be committed to version control.",
        category="general",
    ),
    "no-hardcoded-credentials": RuleTemplate(
        id="no-hardcoded-credentials",
        name="No hardcoded credentials",
        description="Detect potential hardcoded credentials",
        language="typescript",
        severity="error",
        pattern='password = "$$$"',
        message="Potential hardcoded credential detected - use environment variables",
        note="Never hardcode credentials in source code.",
        category="security",
    ),
    "no-sql-injection": RuleTemplate(
        id="no-sql-injection",
        name="Prevent SQL injection",
        description="Detect potential SQL injection vulnerabilities",
        language="typescript",
        severity="error",
        pattern="query($STR + $VAR)",
        message="Potential SQL injection - use parameterized queries",
        note="String concatenation in SQL queries can lead to SQL injection.",
        category="security",
    ),
    # Python templates (7 rules)
    "no-bare-except": RuleTemplate(
        id="no-bare-except",
        name="No bare except",
        description="Disallow bare except clauses",
        language="python",
        severity="error",
        pattern="except:",
        message="Use specific exception types instead of bare except",
        note="Bare except catches all exceptions including system exits and keyboard interrupts.",
        fix="Replace with except Exception: or specific exception types",
        category="security",
        constraints={"kind": "except_clause"},
    ),
    "no-mutable-defaults": RuleTemplate(
        id="no-mutable-defaults",
        name="No mutable default arguments",
        description="Disallow mutable default arguments",
        language="python",
        severity="error",
        pattern="def $FUNC($$$, $ARG=[]):",
        message="Mutable default arguments are dangerous - use None instead",
        note="Default arguments are evaluated once at function definition, not each call.",
        fix="Use None as default and create the list inside the function",
        category="security",
    ),
    "no-eval-exec": RuleTemplate(
        id="no-eval-exec",
        name="No eval or exec",
        description="Disallow eval() and exec() functions",
        language="python",
        severity="error",
        pattern="eval($$$)",
        message="Never use eval() - it poses security risks",
        note="eval() and exec() execute arbitrary code and should be avoided.",
        category="security",
    ),
    "no-print-production": RuleTemplate(
        id="no-print-production",
        name="No print statements",
        description="Disallow print() in production code",
        language="python",
        severity="warning",
        pattern="print($$$)",
        message="Use proper logging instead of print()",
        note="print() statements should be replaced with proper logging in production code.",
        fix="Replace with logger.info() or appropriate log level",
        category="style",
        exclude_files=[
            "**/console_logger.py",
            "**/cli/**",
            "**/__main__.py",
            "**/scripts/**",
            "**/bin/**",
            "**/examples/**",
            "**/pipeline-runners/**",
            "**/*_runner.py",
            "**/*_pipeline.py",
            "**/test_*.py",
            "**/*_test.py",
            "**/tests/**",
        ],
    ),
    "require-type-hints": RuleTemplate(
        id="require-type-hints",
        name="Require type hints",
        description="Require type hints on function definitions",
        language="python",
        severity="info",
        pattern="def $FUNC($ARGS):",
        message="Add type hints to function signature",
        note="Type hints improve code documentation and enable static type checking.",
        category="style",
    ),
    "no-string-exception": RuleTemplate(
        id="no-string-exception",
        name="No string exceptions",
        description="Disallow raising string exceptions",
        language="python",
        severity="error",
        pattern='raise "$MSG"',
        message="Raise proper exception classes instead of strings",
        note="String exceptions are deprecated and should not be used.",
        fix="Use raise ValueError() or other appropriate exception class",
        category="security",
    ),
    "no-assert-production": RuleTemplate(
        id="no-assert-production",
        name="No assert in production",
        description="Disallow assert statements in production code",
        language="python",
        severity="warning",
        pattern="assert $COND",
        message="Use explicit if checks and raise exceptions instead of assert",
        note="assert statements are removed when Python is run with -O optimization.",
        category="security",
    ),
    # Java templates (4 rules)
    "no-system-out": RuleTemplate(
        id="no-system-out",
        name="No System.out",
        description="Disallow System.out.println in production code",
        language="java",
        severity="warning",
        pattern="System.out.println($$$)",
        message="Use a logging framework instead of System.out.println",
        note="System.out is not suitable for production logging.",
        fix="Replace with logger.info() or appropriate log level",
        category="style",
        exclude_files=[
            "**/scripts/**",
            "**/bin/**",
            "**/cli/**",
            "**/pipeline-runners/**",
            "**/tests/**",
            "**/test/**",
            "**/*Test.java",
            "**/*Tests.java",
        ],
    ),
    "proper-exception-handling": RuleTemplate(
        id="proper-exception-handling",
        name="Proper exception handling",
        description="Disallow catching generic Exception",
        language="java",
        severity="warning",
        pattern="catch (Exception $E)",
        message="Catch specific exception types instead of generic Exception",
        note="Catching generic Exception can hide unexpected errors.",
        category="security",
    ),
    "no-empty-finally": RuleTemplate(
        id="no-empty-finally",
        name="No empty finally",
        description="Disallow empty finally blocks",
        language="java",
        severity="warning",
        pattern="finally {}",
        message="Remove empty finally block or add cleanup code",
        note="Empty finally blocks serve no purpose and should be removed.",
        category="general",
    ),
    "no-instanceof-object": RuleTemplate(
        id="no-instanceof-object",
        name="No instanceof Object",
        description="Disallow instanceof Object checks",
        language="java",
        severity="info",
        pattern="$X instanceof Object",
        message="instanceof Object is redundant - all objects are instances of Object",
        note="This check always returns true for non-null references.",
        category="general",
    ),
}


# =============================================================================
# Rule Management Functions
# =============================================================================


def get_available_templates(language: Optional[str] = None, category: Optional[str] = None) -> List[RuleTemplate]:
    """Get list of available rule templates.

    Args:
        language: Optional filter by language
        category: Optional filter by category

    Returns:
        List of matching RuleTemplate objects
    """
    templates = list(RULE_TEMPLATES.values())

    if language:
        templates = [t for t in templates if t.language == language]

    if category:
        templates = [t for t in templates if t.category == category]

    return templates


def create_rule_from_template(template_id: str, rule_id: str, overrides: Optional[Dict[str, Any]] = None) -> LintingRule:
    """Create a LintingRule from a template with optional overrides.

    Args:
        template_id: ID of template from RULE_TEMPLATES
        rule_id: New rule ID to use
        overrides: Optional dict of fields to override

    Returns:
        LintingRule instance

    Raises:
        ValueError: If template_id not found
    """
    if template_id not in RULE_TEMPLATES:
        available = ", ".join(RULE_TEMPLATES.keys())
        raise ValueError(f"Template '{template_id}' not found. Available templates: {available}")

    template = RULE_TEMPLATES[template_id]
    overrides = overrides or {}

    return LintingRule(
        id=rule_id,
        language=overrides.get("language", template.language),
        severity=overrides.get("severity", template.severity),
        message=overrides.get("message", template.message),
        pattern=overrides.get("pattern", template.pattern),
        note=overrides.get("note", template.note),
        fix=overrides.get("fix", template.fix),
        constraints=overrides.get("constraints", template.constraints),
    )


def save_rule_to_project(rule: LintingRule, project_folder: str) -> str:
    """Save rule to .ast-grep-rules/ directory.

    Creates the .ast-grep-rules directory if it doesn't exist and saves
    the rule as a YAML file named after the rule ID.

    Args:
        rule: The LintingRule to save
        project_folder: Project root directory

    Returns:
        Path to the saved rule file

    Raises:
        RuleStorageError: If saving fails
    """
    logger = get_logger("save_rule")

    try:
        project_path = Path(project_folder).resolve()
        rules_dir = project_path / ".ast-grep-rules"

        # Create rules directory if it doesn't exist
        rules_dir.mkdir(parents=True, exist_ok=True)

        # Save rule as YAML
        rule_file = rules_dir / f"{rule.id}.yml"
        rule_dict = rule.to_yaml_dict()

        with sentry_sdk.start_span(op="save_rule", name="Write rule YAML file"):
            with open(rule_file, "w") as f:
                yaml.dump(rule_dict, f, default_flow_style=False, sort_keys=False)

        logger.info("rule_saved", rule_id=rule.id, file_path=str(rule_file), language=rule.language)

        return str(rule_file)

    except Exception as e:
        error_msg = f"Failed to save rule: {str(e)}"
        logger.error("save_rule_failed", error=str(e), rule_id=rule.id)
        sentry_sdk.capture_exception(e)
        raise RuleStorageError(error_msg) from e


def load_rule_from_file(file_path: str) -> LintingRule:
    """Load rule from YAML file.

    Args:
        file_path: Path to the YAML rule file

    Returns:
        Loaded LintingRule object

    Raises:
        RuleStorageError: If loading fails
    """
    logger = get_logger("load_rule")

    try:
        with open(file_path, "r") as f:
            rule_dict = yaml.safe_load(f)

        # Extract pattern from rule dict
        pattern = rule_dict.get("rule", {}).get("pattern", "")

        rule = LintingRule(
            id=rule_dict["id"],
            language=rule_dict["language"],
            severity=rule_dict["severity"],
            message=rule_dict["message"],
            pattern=pattern,
            note=rule_dict.get("note"),
            fix=rule_dict.get("fix"),
            constraints=rule_dict.get("constraints"),
        )

        logger.info("rule_loaded", rule_id=rule.id, file_path=file_path)
        return rule

    except Exception as e:
        error_msg = f"Failed to load rule from {file_path}: {str(e)}"
        logger.error("load_rule_failed", error=str(e), file_path=file_path)
        sentry_sdk.capture_exception(e)
        raise RuleStorageError(error_msg) from e


def load_rules_from_project(project_folder: str) -> List[LintingRule]:
    """Load all rules from project's .ast-grep-rules/ directory.

    Args:
        project_folder: Project root directory

    Returns:
        List of loaded LintingRule objects
    """
    logger = get_logger("load_rules")
    project_path = Path(project_folder).resolve()
    rules_dir = project_path / ".ast-grep-rules"

    if not rules_dir.exists():
        logger.info("no_rules_directory", project_folder=project_folder)
        return []

    rules = []
    for rule_file in rules_dir.glob("*.yml"):
        try:
            rule = load_rule_from_file(str(rule_file))
            rules.append(rule)
        except RuleStorageError as e:
            logger.warning("skip_invalid_rule", file=str(rule_file), error=str(e))

    logger.info("rules_loaded", count=len(rules), project_folder=project_folder)
    return rules


def delete_rule_from_project(rule_id: str, project_folder: str) -> bool:
    """Delete a rule file from project's .ast-grep-rules/ directory.

    Args:
        rule_id: ID of rule to delete
        project_folder: Project root directory

    Returns:
        True if deleted, False if not found
    """
    logger = get_logger("delete_rule")
    project_path = Path(project_folder).resolve()
    rule_file = project_path / ".ast-grep-rules" / f"{rule_id}.yml"

    if rule_file.exists():
        rule_file.unlink()
        logger.info("rule_deleted", rule_id=rule_id, file_path=str(rule_file))
        return True
    else:
        logger.warning("rule_not_found", rule_id=rule_id, project_folder=project_folder)
        return False
