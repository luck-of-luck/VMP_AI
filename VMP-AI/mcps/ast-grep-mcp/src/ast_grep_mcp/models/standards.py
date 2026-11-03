"""Data models for code quality standards and linting rules."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class RuleValidationError(Exception):
    """Raised when a linting rule validation fails."""

    pass


class RuleStorageError(Exception):
    """Raised when saving/loading rules fails."""

    pass


@dataclass
class LintingRule:
    """Represents a custom linting rule.

    Attributes:
        id: Unique rule identifier (e.g., 'no-console-log')
        language: Target language (python, typescript, javascript, java, etc.)
        severity: Severity level ('error', 'warning', or 'info')
        message: Human-readable error message shown when rule is violated
        pattern: ast-grep pattern to match (e.g., 'console.log($$$)')
        note: Optional additional note or explanation
        fix: Optional replacement pattern or fix suggestion
        constraints: Optional additional ast-grep constraints
    """

    id: str
    language: str
    severity: str  # 'error', 'warning', 'info'
    message: str
    pattern: str
    note: Optional[str] = None
    fix: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    exclude_files: List[str] = field(default_factory=list)

    def to_yaml_dict(self) -> Dict[str, Any]:
        """Convert to ast-grep YAML format.

        Returns:
            Dictionary ready for YAML serialization in ast-grep format
        """
        yaml_dict: Dict[str, Any] = {
            "id": self.id,
            "language": self.language,
            "severity": self.severity,
            "message": self.message,
        }

        # Add rule configuration
        rule_config: Dict[str, Any] = {}
        if self.pattern:
            rule_config["pattern"] = self.pattern

        # Add constraints if present
        if self.constraints:
            rule_config.update(self.constraints)

        yaml_dict["rule"] = rule_config

        # Add optional fields
        if self.note:
            yaml_dict["note"] = self.note
        if self.fix:
            yaml_dict["fix"] = self.fix

        return yaml_dict


@dataclass
class RuleTemplate:
    """Pre-built rule template.

    Attributes:
        id: Template identifier
        name: Human-readable name
        description: What the rule checks for
        language: Target language
        severity: Default severity level
        pattern: ast-grep pattern
        message: Error message
        note: Optional additional explanation
        fix: Optional fix suggestion
        category: Rule category (general, security, performance, style)
        constraints: Optional additional ast-grep constraints (e.g., kind field)
    """

    id: str
    name: str
    description: str
    language: str
    severity: str
    pattern: str
    message: str
    note: Optional[str] = None
    fix: Optional[str] = None
    category: str = "general"
    constraints: Optional[Dict[str, Any]] = None
    exclude_files: List[str] = field(default_factory=list)


@dataclass
class RuleValidationResult:
    """Result of rule validation.

    Attributes:
        is_valid: Whether the rule is valid
        errors: List of error messages (blocking issues)
        warnings: List of warning messages (non-blocking issues)
    """

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class RuleViolation:
    """Single violation of a linting rule.

    Attributes:
        file: Absolute path to file containing violation
        line: Line number where violation occurs (1-indexed)
        column: Column number (1-indexed)
        end_line: End line of violation range
        end_column: End column of violation range
        severity: 'error', 'warning', or 'info'
        rule_id: ID of the rule that was violated
        message: Human-readable error message
        code_snippet: Actual code that violated the rule
        fix_suggestion: Optional fix suggestion from rule definition
        meta_vars: Optional metavariables captured by pattern
    """

    file: str
    line: int
    column: int
    end_line: int
    end_column: int
    severity: str
    rule_id: str
    message: str
    code_snippet: str
    fix_suggestion: Optional[str] = None
    meta_vars: Optional[Dict[str, "str | list[str]"]] = None


@dataclass
class RuleSet:
    """Collection of linting rules with metadata.

    Attributes:
        name: Rule set identifier ('recommended', 'security', etc.)
        description: Human-readable description
        rules: List of LintingRule objects in this set
        priority: Execution priority (higher = run first)
    """

    name: str
    description: str
    rules: List[LintingRule]
    priority: int = 0


@dataclass
class EnforcementResult:
    """Complete results from standards enforcement scan.

    Attributes:
        summary: Summary statistics
        violations: All violations found
        violations_by_file: Violations grouped by file path
        violations_by_severity: Violations grouped by severity level
        violations_by_rule: Violations grouped by rule ID
        rules_executed: List of rule IDs that were executed
        execution_time_ms: Total execution time in milliseconds
        files_scanned: Number of files scanned
    """

    summary: Dict[str, Any]
    violations: List[RuleViolation]
    violations_by_file: Dict[str, List[RuleViolation]]
    violations_by_severity: Dict[str, List[RuleViolation]]
    violations_by_rule: Dict[str, List[RuleViolation]]
    rules_executed: List[str]
    execution_time_ms: int
    files_scanned: int


@dataclass
class RuleExecutionContext:
    """Context for executing rules (internal use).

    Attributes:
        project_folder: Absolute path to project
        language: Target language
        include_patterns: File patterns to include
        exclude_patterns: File patterns to exclude
        max_violations: Stop after this many violations (0 = unlimited)
        max_threads: Number of parallel threads
        logger: Structured logger instance
    """

    project_folder: str
    language: str
    include_patterns: List[str]
    exclude_patterns: List[str]
    max_violations: int
    max_threads: int
    logger: Any  # structlog logger


# =============================================================================
# Auto-Fix Data Models
# =============================================================================


@dataclass
class FixResult:
    """Result of applying a single fix to a violation.

    Attributes:
        violation: The original violation that was fixed
        success: Whether the fix was applied successfully
        file_modified: Whether the file was actually changed
        original_code: Code before the fix
        fixed_code: Code after the fix
        syntax_valid: Whether syntax validation passed after fix
        error: Error message if fix failed
        fix_type: Type of fix applied ('safe', 'suggested', 'pattern')
    """

    violation: RuleViolation
    success: bool
    file_modified: bool
    original_code: str
    fixed_code: Optional[str] = None
    syntax_valid: bool = True
    error: Optional[str] = None
    fix_type: str = "safe"


@dataclass
class FixValidation:
    """Result of validating a proposed fix.

    Attributes:
        is_safe: Whether the fix is safe to auto-apply
        confidence: Confidence score 0.0-1.0
        warnings: Non-blocking warnings about the fix
        errors: Blocking errors that prevent auto-fix
        requires_review: Whether manual review is recommended
    """

    is_safe: bool
    confidence: float  # 0.0 to 1.0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    requires_review: bool = False


@dataclass
class FixBatchResult:
    """Result of applying multiple fixes.

    Attributes:
        total_violations: Total number of violations processed
        fixes_attempted: Number of fixes attempted
        fixes_successful: Number of fixes applied successfully
        fixes_failed: Number of fixes that failed
        files_modified: List of file paths that were modified
        backup_id: Backup identifier for rollback
        validation_passed: Whether all fixes passed syntax validation
        results: Individual fix results
        execution_time_ms: Total execution time
    """

    total_violations: int
    fixes_attempted: int
    fixes_successful: int
    fixes_failed: int
    files_modified: List[str]
    backup_id: Optional[str] = None
    validation_passed: bool = True
    results: List[FixResult] = field(default_factory=list)
    execution_time_ms: int = 0


# =============================================================================
# Security Scanner Data Models
# =============================================================================


@dataclass
class SecurityIssue:
    """Represents a detected security vulnerability.

    Attributes:
        file: Absolute path to file containing the issue
        line: Line number where issue occurs (1-indexed)
        column: Column number (1-indexed)
        end_line: End line of issue range
        end_column: End column of issue range
        issue_type: Type of security issue (sql_injection, xss, etc.)
        severity: Severity level ('critical', 'high', 'medium', 'low')
        title: Short title of the issue
        description: Detailed description of the vulnerability
        code_snippet: Code that contains the vulnerability
        remediation: How to fix the issue
        cwe_id: Optional CWE (Common Weakness Enumeration) ID
        confidence: Confidence score 0.0-1.0 (1.0 = definitely vulnerable)
        references: Optional list of reference URLs
    """

    file: str
    line: int
    column: int
    end_line: int
    end_column: int
    issue_type: str
    severity: str  # 'critical', 'high', 'medium', 'low'
    title: str
    description: str
    code_snippet: str
    remediation: str
    cwe_id: Optional[str] = None
    confidence: float = 1.0
    references: List[str] = field(default_factory=list)


@dataclass
class SecurityScanResult:
    """Result from security vulnerability scan.

    Attributes:
        summary: Summary statistics
        issues: All security issues found
        issues_by_severity: Issues grouped by severity
        issues_by_type: Issues grouped by issue type
        files_scanned: Number of files scanned
        execution_time_ms: Total execution time
    """

    summary: Dict[str, Any]
    issues: List[SecurityIssue]
    issues_by_severity: Dict[str, List[SecurityIssue]]
    issues_by_type: Dict[str, List[SecurityIssue]]
    files_scanned: int
    execution_time_ms: int
