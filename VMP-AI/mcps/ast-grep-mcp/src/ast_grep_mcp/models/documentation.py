"""Data models for documentation generation features."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class DocstringStyle(Enum):
    """Supported docstring styles."""

    GOOGLE = "google"
    NUMPY = "numpy"
    SPHINX = "sphinx"
    JSDOC = "jsdoc"
    JAVADOC = "javadoc"
    AUTO = "auto"


class ChangeType(Enum):
    """Type of change in changelog."""

    ADDED = "Added"
    CHANGED = "Changed"
    DEPRECATED = "Deprecated"
    REMOVED = "Removed"
    FIXED = "Fixed"
    SECURITY = "Security"


@dataclass
class ParameterInfo:
    """Information about a function parameter.

    Attributes:
        name: Parameter name
        type_hint: Optional type annotation
        default_value: Optional default value
        description: Generated description
    """

    name: str
    type_hint: Optional[str] = None
    default_value: Optional[str] = None
    description: Optional[str] = None


@dataclass
class FunctionSignature:
    """Parsed function signature information.

    Attributes:
        name: Function name
        parameters: List of parameters
        return_type: Optional return type annotation
        is_async: Whether function is async
        is_method: Whether function is a class method
        decorators: List of decorator names
        file_path: Path to file containing function
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (1-indexed)
        existing_docstring: Existing docstring if any
    """

    name: str
    parameters: List[ParameterInfo]
    return_type: Optional[str] = None
    is_async: bool = False
    is_method: bool = False
    decorators: List[str] = field(default_factory=list)
    file_path: str = ""
    start_line: int = 0
    end_line: int = 0
    existing_docstring: Optional[str] = None


@dataclass
class GeneratedDocstring:
    """A generated docstring for a function.

    Attributes:
        function_name: Name of the function
        file_path: Path to file
        line_number: Line number of function definition
        docstring: Generated docstring content
        style: Docstring style used
        confidence: Confidence score (0.0-1.0)
        inferred_description: Whether description was inferred
        warnings: Any warnings about generation
    """

    function_name: str
    file_path: str
    line_number: int
    docstring: str
    style: DocstringStyle
    confidence: float = 1.0
    inferred_description: bool = False
    warnings: List[str] = field(default_factory=list)


@dataclass
class DocstringGenerationResult:
    """Result of docstring generation for a project.

    Attributes:
        total_functions: Total functions analyzed
        functions_documented: Functions that already have docstrings
        functions_generated: Functions for which docstrings were generated
        functions_skipped: Functions skipped (e.g., private, too short)
        docstrings: List of generated docstrings
        files_modified: Files that were modified (if dry_run=False)
        dry_run: Whether this was a preview only
        execution_time_ms: Execution time in milliseconds
    """

    total_functions: int
    functions_documented: int
    functions_generated: int
    functions_skipped: int
    docstrings: List[GeneratedDocstring]
    files_modified: List[str] = field(default_factory=list)
    dry_run: bool = True
    execution_time_ms: int = 0


# =============================================================================
# README Generation Models
# =============================================================================


@dataclass
class ProjectInfo:
    """Analyzed project information.

    Attributes:
        name: Project name (from package.json, setup.py, etc.)
        version: Project version if found
        description: Project description
        language: Primary programming language
        package_manager: Detected package manager (npm, pip, cargo, etc.)
        entry_points: Main entry point files
        frameworks: Detected frameworks (React, Flask, etc.)
        has_tests: Whether test directory/files exist
        has_docs: Whether docs directory exists
        dependencies: List of main dependencies
    """

    name: str
    version: Optional[str] = None
    description: Optional[str] = None
    language: str = "unknown"
    package_manager: Optional[str] = None
    entry_points: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    has_tests: bool = False
    has_docs: bool = False
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ReadmeSection:
    """A generated README section.

    Attributes:
        section_type: Type of section (installation, usage, api, etc.)
        title: Section title
        content: Markdown content
        order: Display order (lower = earlier)
    """

    section_type: str
    title: str
    content: str
    order: int = 0


@dataclass
class ReadmeGenerationResult:
    """Result of README section generation.

    Attributes:
        project_info: Analyzed project information
        sections: Generated sections
        full_readme: Complete README markdown
        execution_time_ms: Execution time in milliseconds
    """

    project_info: ProjectInfo
    sections: List[ReadmeSection]
    full_readme: str
    execution_time_ms: int = 0


# =============================================================================
# API Documentation Models
# =============================================================================


@dataclass
class RouteParameter:
    """API route parameter.

    Attributes:
        name: Parameter name
        location: Where parameter is located (path, query, body, header)
        type_hint: Parameter type
        required: Whether parameter is required
        description: Parameter description
        default_value: Default value if any
    """

    name: str
    location: str  # path, query, body, header
    type_hint: Optional[str] = None
    required: bool = True
    description: Optional[str] = None
    default_value: Optional[str] = None


@dataclass
class RouteResponse:
    """API route response schema.

    Attributes:
        status_code: HTTP status code
        description: Response description
        content_type: Response content type
        schema: Response schema (as dict)
        example: Example response
    """

    status_code: int
    description: str
    content_type: str = "application/json"
    schema: Optional[Dict[str, Any]] = None
    example: Optional[Any] = None


@dataclass
class ApiRoute:
    """Parsed API route information.

    Attributes:
        path: Route path (e.g., /api/users)
        method: HTTP method (GET, POST, etc.)
        handler_name: Handler function name
        file_path: File containing the route
        line_number: Line number of route definition
        parameters: Route parameters
        responses: Possible responses
        description: Route description from docstring
        tags: API tags/categories
        authentication: Authentication requirements
    """

    path: str
    method: str
    handler_name: str
    file_path: str
    line_number: int
    parameters: List[RouteParameter] = field(default_factory=list)
    responses: List[RouteResponse] = field(default_factory=list)
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    authentication: Optional[str] = None


@dataclass
class ApiDocsResult:
    """Result of API documentation generation.

    Attributes:
        routes: Parsed API routes
        markdown: Generated markdown documentation
        openapi_spec: Generated OpenAPI 3.0 specification
        framework: Detected framework
        execution_time_ms: Execution time
    """

    routes: List[ApiRoute]
    markdown: str
    openapi_spec: Optional[Dict[str, Any]] = None
    framework: Optional[str] = None
    execution_time_ms: int = 0


# =============================================================================
# Changelog Generation Models
# =============================================================================


@dataclass
class CommitInfo:
    """Parsed git commit information.

    Attributes:
        hash: Commit hash (short)
        full_hash: Full commit hash
        message: Commit message
        body: Commit body (additional description)
        author: Author name
        author_email: Author email
        date: Commit date (ISO format)
        change_type: Conventional commit type (feat, fix, etc.)
        scope: Conventional commit scope
        is_breaking: Whether commit is breaking change
        issues: Referenced issue numbers
        prs: Referenced PR numbers
    """

    hash: str
    full_hash: str
    message: str
    body: str = ""
    author: str = ""
    author_email: str = ""
    date: str = ""
    change_type: Optional[str] = None
    scope: Optional[str] = None
    is_breaking: bool = False
    issues: List[str] = field(default_factory=list)
    prs: List[str] = field(default_factory=list)


@dataclass
class ChangelogEntry:
    """A single changelog entry.

    Attributes:
        change_type: Type of change (Added, Changed, etc.)
        description: Change description
        commit_hash: Associated commit hash
        scope: Change scope
        is_breaking: Whether this is breaking change
        issues: Related issues
        prs: Related PRs
    """

    change_type: ChangeType
    description: str
    commit_hash: Optional[str] = None
    scope: Optional[str] = None
    is_breaking: bool = False
    issues: List[str] = field(default_factory=list)
    prs: List[str] = field(default_factory=list)


@dataclass
class ChangelogVersion:
    """Changelog entries for a specific version.

    Attributes:
        version: Version string (e.g., "2.0.0")
        date: Release date
        entries: List of entries grouped by type
        is_unreleased: Whether this is unreleased changes
    """

    version: str
    date: str
    entries: Dict[ChangeType, List[ChangelogEntry]]
    is_unreleased: bool = False


@dataclass
class ChangelogResult:
    """Result of changelog generation.

    Attributes:
        versions: Changelog grouped by version
        markdown: Generated markdown changelog
        commits_processed: Number of commits processed
        commits_skipped: Number of commits skipped
        execution_time_ms: Execution time
    """

    versions: List[ChangelogVersion]
    markdown: str
    commits_processed: int = 0
    commits_skipped: int = 0
    execution_time_ms: int = 0


# =============================================================================
# Documentation Sync Models
# =============================================================================


@dataclass
class DocSyncIssue:
    """An issue found during documentation sync.

    Attributes:
        issue_type: Type of issue (undocumented, stale, mismatch)
        file_path: File with the issue
        line_number: Line number
        function_name: Function name (if applicable)
        description: Issue description
        suggested_fix: Suggested fix
        severity: Issue severity (error, warning, info)
    """

    issue_type: str  # undocumented, stale, mismatch, broken_link
    file_path: str
    line_number: int
    function_name: Optional[str] = None
    description: str = ""
    suggested_fix: Optional[str] = None
    severity: str = "warning"


@dataclass
class DocSyncResult:
    """Result of documentation sync check.

    Attributes:
        total_functions: Total functions analyzed
        documented_functions: Functions with docstrings
        undocumented_functions: Functions without docstrings
        stale_docstrings: Docstrings that don't match signature
        issues: List of issues found
        suggestions: Auto-generated fix suggestions
        files_updated: Files that were updated (if not check_only)
        check_only: Whether this was a check-only run
        execution_time_ms: Execution time
    """

    total_functions: int
    documented_functions: int
    undocumented_functions: int
    stale_docstrings: int
    issues: List[DocSyncIssue]
    suggestions: List[Dict[str, Any]] = field(default_factory=list)
    files_updated: List[str] = field(default_factory=list)
    check_only: bool = True
    execution_time_ms: int = 0
