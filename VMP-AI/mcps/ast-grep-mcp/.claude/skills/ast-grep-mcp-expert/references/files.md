# Files

## File: src/ast_grep_mcp/core/__init__.py
````python
"""Core infrastructure for ast-grep MCP server."""
⋮----
# These are actually in models.config
⋮----
__all__ = [
⋮----
# Exceptions
⋮----
# Logging
⋮----
# Config
⋮----
# Sentry
⋮----
# Cache
⋮----
# Executor
````

## File: src/ast_grep_mcp/features/complexity/__init__.py
````python
"""
Code complexity analysis feature.

This module provides comprehensive code complexity analysis including:
- Cyclomatic complexity calculation
- Cognitive complexity calculation
- Nesting depth analysis
- Function length analysis
- Historical trend tracking
- SQLite-based storage for metrics
"""
⋮----
__all__ = [
⋮----
# Metrics
⋮----
# Analyzer
⋮----
# Storage
⋮----
# Tools
````

## File: src/ast_grep_mcp/features/cross_language/__init__.py
````python
"""Cross-language operations feature module.

This module provides tools for:
- Multi-language search across multiple programming languages
- Pattern equivalence mapping between languages
- Language conversion (Python <-> TypeScript, etc.)
- Polyglot refactoring across language boundaries
- API binding generation from specifications
"""
⋮----
__all__ = [
````

## File: src/ast_grep_mcp/features/documentation/__init__.py
````python
"""Documentation generation feature module.

This module provides tools for:
- Auto-generating docstrings/JSDoc from function signatures
- Creating README sections from code structure
- Building API documentation from route definitions
- Generating changelogs from git commits
- Keeping documentation synchronized with code
"""
⋮----
__all__ = [
````

## File: src/ast_grep_mcp/features/quality/__init__.py
````python
"""Code quality and standards feature.

This feature provides:
- Code smell detection (long functions, parameter bloat, deep nesting, large classes, magic numbers)
- Linting rule management (create, validate, save, load)
- Standards enforcement (execute rules in parallel, report violations)

Modules:
- smells: Code smell detection implementation
- rules: Rule templates and CRUD operations
- validator: Rule validation logic
- enforcer: Standards enforcement engine
- tools: MCP tool registrations
"""
⋮----
__all__ = [
⋮----
# Smells
⋮----
# Rules
⋮----
# Validator
⋮----
# Enforcer
⋮----
# Tools
````

## File: src/ast_grep_mcp/features/refactoring/__init__.py
````python
"""Refactoring assistants for intelligent code transformations.

This module provides tools for automated refactoring operations including:
- Function extraction with parameter detection
- Symbol renaming across codebases
- Code style conversions
- Conditional logic simplification
- Batch refactoring operations
"""
⋮----
__all__ = [
````

## File: src/ast_grep_mcp/features/refactoring/tools.py
````python
"""MCP tools for refactoring operations."""
⋮----
logger = get_logger(__name__)
⋮----
def _format_extract_function_response(result: ExtractFunctionResult, selection: Any, language: str) -> Dict[str, Any]
⋮----
"""Format extract function result for tool response.

    Args:
        result: Extract function result
        selection: Code selection analysis
        language: Programming language

    Returns:
        Formatted response dictionary
    """
⋮----
# Get function signature string based on language
⋮----
signature_str = result.function_signature.to_python_signature()
⋮----
signature_str = result.function_signature.to_typescript_signature()
⋮----
signature_str = None
⋮----
"""Extract selected code into a new function.

    This tool performs intelligent function extraction with automatic parameter
    and return value detection. It analyzes the selected code to determine:
    - Which variables need to be passed as parameters
    - Which variables need to be returned
    - Appropriate function signature with type hints
    - Proper placement of the extracted function

    Args:
        project_folder: Root folder of the project
        file_path: Path to the file (relative to project_folder or absolute)
        start_line: Starting line of code to extract (1-indexed)
        end_line: Ending line of code to extract (1-indexed, inclusive)
        language: Programming language (python, typescript, javascript, java)
        function_name: Optional name for extracted function (auto-generated if None)
        extract_location: Where to place function ('before', 'after', 'top')
        dry_run: If True, only preview changes without applying (default: True)

    Returns:
        Dict containing:
        - success (bool): Whether extraction succeeded
        - function_name (str): Name of extracted function
        - function_signature (str): Generated function signature
        - parameters (list): Parameters detected
        - return_values (list): Values to be returned
        - diff_preview (str): Unified diff of changes
        - backup_id (str): Backup ID if applied (for rollback)
        - warnings (list): Any warnings about the extraction
        - error (str): Error message if failed

    Example:
        ```python
        # Extract a code block into a function
        result = extract_function(
            project_folder="/path/to/project",
            file_path="src/utils.py",
            start_line=45,  # Example: start of code block
            end_line=52,    # Example: end of code block
            language="python",
            function_name="validate_email",  # Optional
            dry_run=True  # Preview first
        )

        if result["success"]:
            print(result["diff_preview"])
            # If satisfied, apply it:
            # result = extract_function(..., dry_run=False)
        ```

    Notes:
        - Always preview with dry_run=True first
        - The tool automatically detects parameters and return values
        - Function will be placed before/after/top of the selection
        - Original code is replaced with a function call
        - Type hints are inferred when possible
        - Backup is created automatically (use rollback_rewrite to undo)
    """
⋮----
# Build absolute file path
⋮----
file_path = os.path.join(project_folder, file_path)
⋮----
# Analyze the code selection
analyzer = CodeSelectionAnalyzer(language)
selection = analyzer.analyze_selection(
⋮----
# Extract the function
extractor = FunctionExtractor(language)
result = extractor.extract_function(
⋮----
# Format response using helper
⋮----
# MCP wrapper with Pydantic validation
⋮----
"""Extract selected code into a new function with automatic parameter detection.

    MCP tool wrapper for extract_function_tool.
    """
⋮----
"""Rename a symbol (variable, function, class) across codebase.

    This tool performs scope-aware symbol renaming with:
    - Finding all references across files
    - Respecting scope boundaries (avoiding shadowed symbols)
    - Updating import/export statements
    - Detecting naming conflicts before applying
    - Atomic multi-file updates with rollback

    Args:
        project_folder: Root folder of the project
        symbol_name: Current symbol name to rename
        new_name: New symbol name
        language: Programming language (python, typescript, javascript, java)
        scope: Scope to rename in ('project', 'file', 'function')
        file_filter: Optional glob pattern to filter files (e.g., '*.py', 'src/**/*.ts')
        dry_run: If True, only preview changes without applying (default: True)

    Returns:
        Dict containing:
        - success (bool): Whether rename succeeded
        - old_name (str): Original symbol name
        - new_name (str): New symbol name
        - references_found (int): Number of references found
        - references_updated (int): Number of references updated
        - files_modified (list): List of files modified
        - conflicts (list): List of naming conflicts (if any)
        - diff_preview (str): Unified diff of changes
        - backup_id (str): Backup ID if applied (for rollback)
        - error (str): Error message if failed

    Example:
        ```python
        # Preview renaming
        result = rename_symbol(
            project_folder="/path/to/project",
            symbol_name="processData",
            new_name="transformData",
            language="typescript",
            scope="project",
            dry_run=True  # Preview first
        )

        if result["success"] and not result.get("conflicts"):
            print(f"Found {result['references_found']} references")
            print(result["diff_preview"])

            # Apply if satisfied
            result = rename_symbol(..., dry_run=False)
        ```

    Notes:
        - Always preview with dry_run=True first
        - Checks for naming conflicts before applying
        - Respects scope boundaries (won't rename shadowed variables)
        - Updates imports/exports automatically
        - Creates backup automatically (use rollback_rewrite to undo)
        - Atomic operation: all files updated or none
    """
⋮----
# Create coordinator
coordinator = RenameCoordinator(language)
⋮----
# Perform rename
result = coordinator.rename_symbol(
⋮----
# Format response
⋮----
"""Rename a symbol across codebase with scope awareness and conflict detection.

    MCP tool wrapper for rename_symbol_tool.
    """
````

## File: src/ast_grep_mcp/features/rewrite/__init__.py
````python
"""Rewrite feature - code transformation and backup management."""
⋮----
__all__ = [
⋮----
# Backup functions
⋮----
# Service functions
⋮----
# Registration
````

## File: src/ast_grep_mcp/features/rewrite/tools.py
````python
"""Rewrite feature MCP tool definitions."""
⋮----
def register_rewrite_tools(mcp: FastMCP) -> None
⋮----
"""Register rewrite-related MCP tools.

    Args:
        mcp: FastMCP instance to register tools with
    """
⋮----
"""
        Rewrite code using ast-grep fix rules. Apply automated code transformations safely.

        SAFETY FEATURES:
        - dry_run=True by default (preview before applying)
        - Automatic backups before changes
        - Returns diff preview or list of modified files

        Example YAML Rule:
        ```yaml
        id: replace-var-with-const
        language: javascript
        rule:
          pattern: var $NAME = $VAL
        fix: const $NAME = $VAL
        ```

        Returns:
        - dry_run=True: Preview with diffs showing proposed changes
        - dry_run=False: backup_id and list of modified files
        """
⋮----
"""
        Restore files from a backup created during rewrite operations.

        Use this to undo changes from rewrite_code when:
        - Syntax validation fails
        - Changes had unintended effects
        - You need to restore previous state

        Get available backup_ids using list_backups().

        Returns:
        - success: Whether restoration was successful
        - restored_files: List of restored file paths
        - errors: Any errors encountered (if restoration failed)
        """
⋮----
@mcp.tool()
    def list_backups(project_folder: str = Field(description="The absolute path to the project folder")) -> List[Dict[str, Any]]
⋮----
"""
        List all available backups in the project.

        Shows backups created by rewrite_code and apply_deduplication operations.
        Backups are stored in .ast-grep-backups/ directory.

        Returns list of backups with:
        - backup_id: Unique identifier (use with rollback_rewrite)
        - timestamp: When backup was created
        - file_count: Number of files in backup
        - size_bytes: Total backup size
        - backup_type: 'standard' or 'deduplication'
        """
````

## File: src/ast_grep_mcp/features/schema/__init__.py
````python
"""Schema.org feature - structured data and knowledge graph functionality."""
⋮----
__all__ = [
⋮----
# Client
⋮----
# Registration
````

## File: src/ast_grep_mcp/features/search/__init__.py
````python
"""Search feature - code search functionality using ast-grep."""
⋮----
__all__ = [
⋮----
# Service functions
⋮----
# Registration
````

## File: src/ast_grep_mcp/features/__init__.py
````python

````

## File: src/ast_grep_mcp/models/base.py
````python
"""Base models and types used across features."""
⋮----
# Type alias for dump format
DumpFormat = Literal["pattern", "cst", "ast"]
````

## File: src/ast_grep_mcp/models/config.py
````python
"""Configuration models for ast-grep MCP server."""
⋮----
class CustomLanguageConfig(BaseModel)
⋮----
"""Configuration for a custom language in sgconfig.yaml."""
⋮----
model_config = ConfigDict(populate_by_name=True)
⋮----
extensions: List[str]
languageId: Optional[str] = None  # noqa: N815
expandoChar: Optional[str] = None  # noqa: N815
⋮----
@field_validator("extensions")
@classmethod
    def validate_extensions(cls, v: List[str]) -> List[str]
⋮----
"""Ensure extensions start with a dot."""
⋮----
class AstGrepConfig(BaseModel)
⋮----
"""Pydantic model for validating sgconfig.yaml structure."""
⋮----
ruleDirs: Optional[List[str]] = None  # noqa: N815
testDirs: Optional[List[str]] = None  # noqa: N815
customLanguages: Optional[Dict[str, CustomLanguageConfig]] = None  # noqa: N815
languageGlobs: Optional[List[Dict[str, Any]]] = None  # noqa: N815
⋮----
@field_validator("ruleDirs", "testDirs")
@classmethod
    def validate_dirs(cls, v: Optional[List[str]]) -> Optional[List[str]]
⋮----
"""Validate directory lists are not empty if provided."""
⋮----
@field_validator("customLanguages")
@classmethod
    def validate_custom_languages(cls, v: Optional[Dict[str, CustomLanguageConfig]]) -> Optional[Dict[str, CustomLanguageConfig]]
⋮----
"""Validate custom languages dictionary."""
````

## File: src/ast_grep_mcp/models/cross_language.py
````python
"""Data models for cross-language operations features.

This module defines data models for:
- Multi-language search results
- Pattern equivalence mapping
- Language conversion
- Polyglot refactoring
- API binding generation
"""
⋮----
class ConversionStyle(Enum)
⋮----
"""Code conversion style options."""
⋮----
LITERAL = "literal"  # Direct translation preserving structure
IDIOMATIC = "idiomatic"  # Use target language idioms
COMPATIBLE = "compatible"  # Maximum cross-platform compatibility
⋮----
class BindingStyle(Enum)
⋮----
"""API binding generation style."""
⋮----
NATIVE = "native"  # Native language style (requests, fetch, etc.)
SDK = "sdk"  # Full SDK with types and utilities
MINIMAL = "minimal"  # Minimal implementation
⋮----
class RefactoringType(Enum)
⋮----
"""Cross-language refactoring types."""
⋮----
RENAME_API = "rename_api"  # Rename API endpoint across frontend/backend
EXTRACT_CONSTANT = "extract_constant"  # Extract to shared config
UPDATE_CONTRACT = "update_contract"  # Update API contract signature
⋮----
# =============================================================================
# Multi-Language Search Models
⋮----
@dataclass
class SemanticPattern
⋮----
"""A semantic pattern that can match across languages.

    Attributes:
        description: Human-readable pattern description
        concept: The abstract concept being matched
        language_patterns: Language-specific ast-grep patterns
    """
⋮----
description: str
concept: str
language_patterns: Dict[str, str] = field(default_factory=dict)
⋮----
@dataclass
class MultiLanguageMatch
⋮----
"""A match found in multi-language search.

    Attributes:
        language: Programming language of the match
        file_path: Path to the file containing the match
        line_number: Line number (1-indexed)
        code_snippet: The matched code
        semantic_group: Semantic grouping category
        confidence: Confidence score for semantic matching
    """
⋮----
language: str
file_path: str
line_number: int
code_snippet: str
semantic_group: str = ""
confidence: float = 1.0
⋮----
@dataclass
class MultiLanguageSearchResult
⋮----
"""Result of multi-language search operation.

    Attributes:
        query: Original semantic query
        languages_searched: Languages that were searched
        matches: List of matches grouped by semantic similarity
        total_matches: Total number of matches
        matches_by_language: Count of matches per language
        semantic_groups: Distinct semantic groups found
        execution_time_ms: Execution time in milliseconds
    """
⋮----
query: str
languages_searched: List[str]
matches: List[MultiLanguageMatch]
total_matches: int = 0
matches_by_language: Dict[str, int] = field(default_factory=dict)
semantic_groups: List[str] = field(default_factory=list)
execution_time_ms: int = 0
⋮----
# Pattern Equivalence Models
⋮----
@dataclass
class PatternExample
⋮----
"""An example of a pattern in a specific language.

    Attributes:
        language: Programming language
        code: Example code
        description: Explanation of this implementation
        notes: Additional notes or caveats
    """
⋮----
code: str
description: str = ""
notes: List[str] = field(default_factory=list)
⋮----
@dataclass
class PatternEquivalence
⋮----
"""Equivalent patterns across multiple languages.

    Attributes:
        pattern_id: Unique identifier for this pattern
        concept: The abstract concept (e.g., "list comprehension")
        category: Pattern category (control_flow, data_structures, etc.)
        description: Detailed description
        examples: Examples in each supported language
        related_patterns: Related pattern IDs
        complexity_comparison: How complexity compares across languages
    """
⋮----
pattern_id: str
⋮----
category: str
⋮----
examples: List[PatternExample] = field(default_factory=list)
related_patterns: List[str] = field(default_factory=list)
complexity_comparison: Dict[str, str] = field(default_factory=dict)
⋮----
@dataclass
class PatternEquivalenceResult
⋮----
"""Result of pattern equivalence lookup.

    Attributes:
        pattern_description: The input pattern description
        source_language: Source language (if specified)
        target_languages: Target languages searched
        equivalences: Found pattern equivalences
        suggestions: Additional pattern suggestions
        execution_time_ms: Execution time
    """
⋮----
pattern_description: str
source_language: Optional[str]
target_languages: List[str]
equivalences: List[PatternEquivalence]
suggestions: List[str] = field(default_factory=list)
⋮----
# Language Conversion Models
⋮----
@dataclass
class TypeMapping
⋮----
"""Type mapping between languages.

    Attributes:
        source_type: Type in source language
        target_type: Type in target language
        needs_import: Import statement needed (if any)
        notes: Conversion notes
    """
⋮----
source_type: str
target_type: str
needs_import: Optional[str] = None
notes: Optional[str] = None
⋮----
@dataclass
class ConversionWarning
⋮----
"""Warning generated during code conversion.

    Attributes:
        severity: Warning severity (info, warning, error)
        message: Warning message
        line_number: Line number in source code
        suggestion: Suggested resolution
    """
⋮----
severity: str
message: str
line_number: Optional[int] = None
suggestion: Optional[str] = None
⋮----
@dataclass
class ConvertedCode
⋮----
"""Result of code conversion.

    Attributes:
        source_code: Original source code
        converted_code: Converted code
        from_language: Source language
        to_language: Target language
        style: Conversion style used
        type_mappings: Type mappings applied
        warnings: Conversion warnings
        imports_needed: Import statements needed
        success: Whether conversion was successful
    """
⋮----
source_code: str
converted_code: str
from_language: str
to_language: str
style: ConversionStyle
type_mappings: List[TypeMapping] = field(default_factory=list)
warnings: List[ConversionWarning] = field(default_factory=list)
imports_needed: List[str] = field(default_factory=list)
success: bool = True
⋮----
@dataclass
class ConversionResult
⋮----
"""Complete result of language conversion operation.

    Attributes:
        conversions: List of converted code blocks
        total_functions: Total functions converted
        successful_conversions: Number of successful conversions
        failed_conversions: Number of failed conversions
        execution_time_ms: Execution time
    """
⋮----
conversions: List[ConvertedCode]
total_functions: int = 0
successful_conversions: int = 0
failed_conversions: int = 0
⋮----
# Polyglot Refactoring Models
⋮----
@dataclass
class PolyglotChange
⋮----
"""A change in a specific language during polyglot refactoring.

    Attributes:
        language: Programming language
        file_path: Path to file
        line_number: Line number of change
        original_code: Original code
        new_code: New code after refactoring
        change_type: Type of change made
    """
⋮----
original_code: str
new_code: str
change_type: str = "modify"
⋮----
@dataclass
class PolyglotRefactoringPlan
⋮----
"""Plan for polyglot refactoring.

    Attributes:
        refactoring_type: Type of refactoring
        symbol_name: Symbol being refactored
        new_name: New name (if rename)
        affected_languages: Languages that will be modified
        changes: Planned changes by language
        risks: Identified risks
        requires_manual_review: Files requiring manual review
    """
⋮----
refactoring_type: RefactoringType
symbol_name: str
new_name: Optional[str]
affected_languages: List[str]
changes: List[PolyglotChange] = field(default_factory=list)
risks: List[str] = field(default_factory=list)
requires_manual_review: List[str] = field(default_factory=list)
⋮----
@dataclass
class PolyglotRefactoringResult
⋮----
"""Result of polyglot refactoring operation.

    Attributes:
        plan: The refactoring plan
        dry_run: Whether this was a preview only
        changes_made: List of changes made
        files_modified: Files that were modified
        validation_passed: Whether validation passed
        validation_errors: Any validation errors
        execution_time_ms: Execution time
    """
⋮----
plan: PolyglotRefactoringPlan
dry_run: bool
changes_made: List[PolyglotChange] = field(default_factory=list)
files_modified: List[str] = field(default_factory=list)
validation_passed: bool = True
validation_errors: List[str] = field(default_factory=list)
⋮----
# API Binding Generation Models
⋮----
@dataclass
class ApiEndpoint
⋮----
"""An API endpoint parsed from specification.

    Attributes:
        path: Endpoint path
        method: HTTP method
        operation_id: Operation identifier
        summary: Short summary
        description: Full description
        parameters: Endpoint parameters
        request_body: Request body schema
        responses: Response schemas
        tags: API tags
    """
⋮----
path: str
method: str
operation_id: str
summary: str = ""
⋮----
parameters: List[Dict[str, Any]] = field(default_factory=list)
request_body: Optional[Dict[str, Any]] = None
responses: Dict[str, Dict[str, Any]] = field(default_factory=dict)
tags: List[str] = field(default_factory=list)
⋮----
@dataclass
class GeneratedBinding
⋮----
"""A generated API client binding.

    Attributes:
        language: Target language
        file_name: Suggested file name
        code: Generated code
        imports: Required imports
        dependencies: Package dependencies needed
        types_generated: Type definitions generated
    """
⋮----
file_name: str
⋮----
imports: List[str] = field(default_factory=list)
dependencies: List[str] = field(default_factory=list)
types_generated: List[str] = field(default_factory=list)
⋮----
@dataclass
class BindingGenerationResult
⋮----
"""Result of API binding generation.

    Attributes:
        api_name: Name of the API
        api_version: API version
        base_url: Base URL of the API
        endpoints_count: Number of endpoints processed
        bindings: Generated bindings per language
        warnings: Generation warnings
        execution_time_ms: Execution time
    """
⋮----
api_name: str
api_version: str
base_url: str
endpoints_count: int
bindings: List[GeneratedBinding]
warnings: List[str] = field(default_factory=list)
⋮----
# Supported Language Pairs
⋮----
# Language pairs supported for conversion
SUPPORTED_CONVERSION_PAIRS = [
⋮----
# Languages supported for multi-language search
SUPPORTED_LANGUAGES = [
⋮----
# Languages supported for binding generation
BINDING_LANGUAGES = [
````

## File: src/ast_grep_mcp/models/documentation.py
````python
"""Data models for documentation generation features."""
⋮----
class DocstringStyle(Enum)
⋮----
"""Supported docstring styles."""
⋮----
GOOGLE = "google"
NUMPY = "numpy"
SPHINX = "sphinx"
JSDOC = "jsdoc"
JAVADOC = "javadoc"
AUTO = "auto"
⋮----
class ChangeType(Enum)
⋮----
"""Type of change in changelog."""
⋮----
ADDED = "Added"
CHANGED = "Changed"
DEPRECATED = "Deprecated"
REMOVED = "Removed"
FIXED = "Fixed"
SECURITY = "Security"
⋮----
@dataclass
class ParameterInfo
⋮----
"""Information about a function parameter.

    Attributes:
        name: Parameter name
        type_hint: Optional type annotation
        default_value: Optional default value
        description: Generated description
    """
⋮----
name: str
type_hint: Optional[str] = None
default_value: Optional[str] = None
description: Optional[str] = None
⋮----
@dataclass
class FunctionSignature
⋮----
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
⋮----
parameters: List[ParameterInfo]
return_type: Optional[str] = None
is_async: bool = False
is_method: bool = False
decorators: List[str] = field(default_factory=list)
file_path: str = ""
start_line: int = 0
end_line: int = 0
existing_docstring: Optional[str] = None
⋮----
@dataclass
class GeneratedDocstring
⋮----
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
⋮----
function_name: str
file_path: str
line_number: int
docstring: str
style: DocstringStyle
confidence: float = 1.0
inferred_description: bool = False
warnings: List[str] = field(default_factory=list)
⋮----
@dataclass
class DocstringGenerationResult
⋮----
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
⋮----
total_functions: int
functions_documented: int
functions_generated: int
functions_skipped: int
docstrings: List[GeneratedDocstring]
files_modified: List[str] = field(default_factory=list)
dry_run: bool = True
execution_time_ms: int = 0
⋮----
# =============================================================================
# README Generation Models
⋮----
@dataclass
class ProjectInfo
⋮----
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
⋮----
version: Optional[str] = None
⋮----
language: str = "unknown"
package_manager: Optional[str] = None
entry_points: List[str] = field(default_factory=list)
frameworks: List[str] = field(default_factory=list)
has_tests: bool = False
has_docs: bool = False
dependencies: List[str] = field(default_factory=list)
⋮----
@dataclass
class ReadmeSection
⋮----
"""A generated README section.

    Attributes:
        section_type: Type of section (installation, usage, api, etc.)
        title: Section title
        content: Markdown content
        order: Display order (lower = earlier)
    """
⋮----
section_type: str
title: str
content: str
order: int = 0
⋮----
@dataclass
class ReadmeGenerationResult
⋮----
"""Result of README section generation.

    Attributes:
        project_info: Analyzed project information
        sections: Generated sections
        full_readme: Complete README markdown
        execution_time_ms: Execution time in milliseconds
    """
⋮----
project_info: ProjectInfo
sections: List[ReadmeSection]
full_readme: str
⋮----
# API Documentation Models
⋮----
@dataclass
class RouteParameter
⋮----
"""API route parameter.

    Attributes:
        name: Parameter name
        location: Where parameter is located (path, query, body, header)
        type_hint: Parameter type
        required: Whether parameter is required
        description: Parameter description
        default_value: Default value if any
    """
⋮----
location: str  # path, query, body, header
⋮----
required: bool = True
⋮----
@dataclass
class RouteResponse
⋮----
"""API route response schema.

    Attributes:
        status_code: HTTP status code
        description: Response description
        content_type: Response content type
        schema: Response schema (as dict)
        example: Example response
    """
⋮----
status_code: int
description: str
content_type: str = "application/json"
schema: Optional[Dict[str, Any]] = None
example: Optional[Any] = None
⋮----
@dataclass
class ApiRoute
⋮----
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
⋮----
path: str
method: str
handler_name: str
⋮----
parameters: List[RouteParameter] = field(default_factory=list)
responses: List[RouteResponse] = field(default_factory=list)
⋮----
tags: List[str] = field(default_factory=list)
authentication: Optional[str] = None
⋮----
@dataclass
class ApiDocsResult
⋮----
"""Result of API documentation generation.

    Attributes:
        routes: Parsed API routes
        markdown: Generated markdown documentation
        openapi_spec: Generated OpenAPI 3.0 specification
        framework: Detected framework
        execution_time_ms: Execution time
    """
⋮----
routes: List[ApiRoute]
markdown: str
openapi_spec: Optional[Dict[str, Any]] = None
framework: Optional[str] = None
⋮----
# Changelog Generation Models
⋮----
@dataclass
class CommitInfo
⋮----
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
⋮----
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
⋮----
@dataclass
class ChangelogEntry
⋮----
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
⋮----
change_type: ChangeType
⋮----
commit_hash: Optional[str] = None
⋮----
@dataclass
class ChangelogVersion
⋮----
"""Changelog entries for a specific version.

    Attributes:
        version: Version string (e.g., "2.0.0")
        date: Release date
        entries: List of entries grouped by type
        is_unreleased: Whether this is unreleased changes
    """
⋮----
version: str
date: str
entries: Dict[ChangeType, List[ChangelogEntry]]
is_unreleased: bool = False
⋮----
@dataclass
class ChangelogResult
⋮----
"""Result of changelog generation.

    Attributes:
        versions: Changelog grouped by version
        markdown: Generated markdown changelog
        commits_processed: Number of commits processed
        commits_skipped: Number of commits skipped
        execution_time_ms: Execution time
    """
⋮----
versions: List[ChangelogVersion]
⋮----
commits_processed: int = 0
commits_skipped: int = 0
⋮----
# Documentation Sync Models
⋮----
@dataclass
class DocSyncIssue
⋮----
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
⋮----
issue_type: str  # undocumented, stale, mismatch, broken_link
⋮----
function_name: Optional[str] = None
description: str = ""
suggested_fix: Optional[str] = None
severity: str = "warning"
⋮----
@dataclass
class DocSyncResult
⋮----
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
⋮----
documented_functions: int
undocumented_functions: int
stale_docstrings: int
issues: List[DocSyncIssue]
suggestions: List[Dict[str, Any]] = field(default_factory=list)
files_updated: List[str] = field(default_factory=list)
check_only: bool = True
````

## File: src/ast_grep_mcp/models/refactoring.py
````python
"""Data models for refactoring operations."""
⋮----
class VariableType(Enum)
⋮----
"""Classification of variables in code selection."""
⋮----
LOCAL = "local"  # Defined and used only within selection
PARAMETER = "parameter"  # Used but not defined in selection (needs to be parameter)
MODIFIED = "modified"  # Modified within selection (needs to be returned)
GLOBAL = "global"  # Global or module-level variable
CLOSURE = "closure"  # From enclosing scope
⋮----
class RefactoringType(Enum)
⋮----
"""Types of refactoring operations."""
⋮----
EXTRACT_FUNCTION = "extract_function"
EXTRACT_METHOD = "extract_method"
RENAME_SYMBOL = "rename_symbol"
CONVERT_STYLE = "convert_style"
SIMPLIFY_CONDITIONALS = "simplify_conditionals"
⋮----
@dataclass
class VariableInfo
⋮----
"""Information about a variable in code selection."""
⋮----
name: str
variable_type: VariableType
first_use_line: int
is_read: bool = False
is_written: bool = False
inferred_type: Optional[str] = None
scope_depth: int = 0
⋮----
@dataclass
class CodeSelection
⋮----
"""Represents a selection of code for refactoring."""
⋮----
file_path: str
start_line: int
end_line: int
language: str
content: str
indentation: str = ""
⋮----
# Analysis results
variables: List[VariableInfo] = field(default_factory=list)
parameters_needed: List[str] = field(default_factory=list)
return_values: List[str] = field(default_factory=list)
has_early_returns: bool = False
has_exceptions: bool = False
⋮----
def get_variables_by_type(self, var_type: VariableType) -> List[VariableInfo]
⋮----
"""Get all variables of a specific type."""
⋮----
@dataclass
class FunctionSignature
⋮----
"""Generated function signature."""
⋮----
parameters: List[Dict[str, str]]  # [{"name": "x", "type": "int"}, ...]
return_type: Optional[str] = None
docstring: Optional[str] = None
is_async: bool = False
decorators: List[str] = field(default_factory=list)
⋮----
def to_python_signature(self) -> str
⋮----
"""Generate Python function signature."""
params = ", ".join(f"{p['name']}: {p['type']}" if p.get("type") else p["name"] for p in self.parameters)
⋮----
ret = f" -> {self.return_type}" if self.return_type else ""
async_prefix = "async " if self.is_async else ""
⋮----
def to_typescript_signature(self) -> str
⋮----
"""Generate TypeScript function signature."""
⋮----
ret = f": {self.return_type}" if self.return_type else ""
⋮----
@dataclass
class ExtractFunctionResult
⋮----
"""Result of extract function operation."""
⋮----
success: bool
function_signature: Optional[FunctionSignature] = None
function_body: Optional[str] = None
call_site_replacement: Optional[str] = None
insertion_line: Optional[int] = None
diff_preview: Optional[str] = None
backup_id: Optional[str] = None
error: Optional[str] = None
warnings: List[str] = field(default_factory=list)
⋮----
@dataclass
class ScopeInfo
⋮----
"""Information about a scope in the code."""
⋮----
scope_type: str  # 'module', 'class', 'function', 'block'
scope_name: str
⋮----
parent_scope: Optional[str] = None
defined_symbols: Set[str] = field(default_factory=set)
⋮----
@dataclass
class SymbolReference
⋮----
"""Reference to a symbol in code."""
⋮----
line: int
column: int
context: str  # Surrounding code for context
scope: str  # Function/class/module scope
is_definition: bool = False
is_import: bool = False
is_export: bool = False
import_source: Optional[str] = None  # For imports: where it's imported from
⋮----
@dataclass
class RenameSymbolResult
⋮----
"""Result of rename symbol operation."""
⋮----
old_name: str
new_name: str
references_found: int = 0
references_updated: int = 0
files_modified: List[str] = field(default_factory=list)
conflicts: List[str] = field(default_factory=list)
⋮----
@dataclass
class StyleConversion
⋮----
"""Configuration for style conversion."""
⋮----
conversion_type: str
source_language: str
target_style: Optional[str] = None
preserve_comments: bool = True
preserve_formatting: bool = True
options: Dict[str, Any] = field(default_factory=dict)
⋮----
@dataclass
class ConversionResult
⋮----
"""Result of code style conversion."""
⋮----
files_converted: int = 0
⋮----
conversion_stats: Dict[str, int] = field(default_factory=dict)
⋮----
@dataclass
class SimplificationResult
⋮----
"""Result of conditional simplification."""
⋮----
complexity_before: int = 0
complexity_after: int = 0
simplifications_applied: int = 0
⋮----
@dataclass
class RefactoringStep
⋮----
"""Single step in batch refactoring."""
⋮----
step_id: int
refactoring_type: RefactoringType
parameters: Dict[str, Any]
depends_on: List[int] = field(default_factory=list)  # Step IDs this depends on
⋮----
@dataclass
class BatchRefactoringResult
⋮----
"""Result of batch refactoring operation."""
⋮----
steps_completed: int = 0
steps_total: int = 0
results: List[Dict[str, Any]] = field(default_factory=list)
combined_diff: Optional[str] = None
⋮----
rollback_performed: bool = False
````

## File: src/ast_grep_mcp/models/schema_enhancement.py
````python
"""Data models for Schema.org entity graph enhancement features."""
⋮----
class EnhancementPriority(Enum)
⋮----
"""Priority levels for Schema.org enhancements.

    Attributes:
        CRITICAL: Required for Google Rich Results
        HIGH: Strongly recommended for SEO
        MEDIUM: Improves discoverability
        LOW: Nice to have
    """
⋮----
CRITICAL = "critical"
HIGH = "high"
MEDIUM = "medium"
LOW = "low"
⋮----
class EnhancementCategory(Enum)
⋮----
"""Categories of schema enhancement issues.

    Attributes:
        MISSING_PROPERTY: Entity is missing a recommended property
        MISSING_ENTITY: Graph is missing a recommended entity type
        INVALID_ID: Entity has an invalid or missing @id
        BROKEN_REFERENCE: Entity references a non-existent @id
    """
⋮----
MISSING_PROPERTY = "missing_property"
MISSING_ENTITY = "missing_entity"
INVALID_ID = "invalid_id"
BROKEN_REFERENCE = "broken_reference"
⋮----
@dataclass
class PropertyEnhancement
⋮----
"""Enhancement suggestion for a missing property.

    Attributes:
        property_name: Name of the property (e.g., "aggregateRating")
        expected_types: List of expected Schema.org types for the property
        priority: Priority level for adding this property
        reason: Human-readable explanation for why this property is recommended
        example_value: Example value showing proper structure
        google_rich_result: Name of Google Rich Result this enables (if any)
    """
⋮----
property_name: str
expected_types: List[str]
priority: EnhancementPriority
reason: str
example_value: Any
google_rich_result: Optional[str] = None
⋮----
@dataclass
class EntityEnhancement
⋮----
"""Enhancement suggestions for a single entity.

    Attributes:
        entity_id: The @id of the entity being analyzed
        entity_type: The @type of the entity (e.g., "Organization")
        existing_properties: List of properties the entity currently has
        suggested_properties: List of property enhancements recommended
        validation_issues: List of validation issues found (e.g., broken references)
        seo_score: SEO completeness score from 0.0 to 100.0
    """
⋮----
entity_id: str
entity_type: str
existing_properties: List[str]
suggested_properties: List[PropertyEnhancement]
validation_issues: List[str] = field(default_factory=list)
seo_score: float = 0.0
⋮----
@dataclass
class MissingEntitySuggestion
⋮----
"""Suggestion for a missing entity type in the graph.

    Attributes:
        entity_type: Schema.org type to add (e.g., "FAQPage")
        priority: Priority level for adding this entity
        reason: Human-readable explanation for why this entity is recommended
        example: Example structure for the entity with placeholder values
        google_rich_result: Name of Google Rich Result this enables (if any)
    """
⋮----
example: Dict[str, Any]
⋮----
@dataclass
class GraphEnhancementResult
⋮----
"""Complete result of entity graph enhancement analysis.

    Attributes:
        original_graph: The original JSON-LD graph as parsed
        entity_enhancements: Enhancement suggestions for each entity
        missing_entities: Suggestions for missing entity types
        global_issues: Graph-level issues (e.g., no @context)
        overall_seo_score: Overall SEO completeness score from 0.0 to 100.0
        priority_summary: Count of suggestions by priority level
        enhanced_graph: Enhanced graph with all suggestions applied (if output_mode="enhanced")
        diff: Additions needed to enhance the graph (if output_mode="diff")
        execution_time_ms: Time taken to perform analysis in milliseconds
    """
⋮----
original_graph: List[Dict[str, Any]]
entity_enhancements: List[EntityEnhancement]
missing_entities: List[MissingEntitySuggestion]
global_issues: List[str] = field(default_factory=list)
overall_seo_score: float = 0.0
priority_summary: Dict[str, int] = field(default_factory=dict)
enhanced_graph: Optional[Dict[str, Any]] = None
diff: Optional[Dict[str, Any]] = None
execution_time_ms: int = 0
````

## File: src/ast_grep_mcp/server/__init__.py
````python
"""Server components for MCP integration."""
⋮----
__all__ = ["register_all_tools", "run_mcp_server"]
````

## File: src/ast_grep_mcp/server/runner.py
````python
"""MCP server entry point."""
⋮----
# Create FastMCP instance
mcp = FastMCP("ast-grep")
⋮----
def run_mcp_server() -> None
⋮----
"""Run the MCP server.

    This function:
    1. Parses command-line arguments and loads configuration
    2. Initializes Sentry error tracking (if configured)
    3. Registers all MCP tools from all features
    4. Starts the MCP server with stdio transport
    """
parse_args_and_get_config()  # Sets CONFIG_PATH global
init_sentry()  # Initialize error tracking (no-op if not configured)
register_all_tools(mcp)  # Register all tools
````

## File: src/ast_grep_mcp/__init__.py
````python

````

## File: src/ast_grep_mcp/core/cache.py
````python
"""Query caching for ast-grep MCP server."""
⋮----
class QueryCache
⋮----
"""Simple LRU cache with TTL for ast-grep query results.

    Caches query results to avoid redundant ast-grep executions for identical queries.
    Uses OrderedDict for LRU eviction and timestamps for TTL expiration.
    """
⋮----
def __init__(self, max_size: int = CacheDefaults.DEFAULT_CACHE_SIZE, ttl_seconds: int = CacheDefaults.CLEANUP_INTERVAL_SECONDS) -> None
⋮----
"""Initialize the cache.

        Args:
            max_size: Maximum number of entries to cache (default: CacheDefaults.DEFAULT_CACHE_SIZE)
            ttl_seconds: Time-to-live for cache entries in seconds (default: CacheDefaults.CLEANUP_INTERVAL_SECONDS)
        """
⋮----
def _make_key(self, command: str, args: List[str], project_folder: str) -> str
⋮----
"""Create a cache key from query parameters.

        Args:
            command: ast-grep command (run/scan)
            args: Command arguments
            project_folder: Project folder path

        Returns:
            Hash-based cache key
        """
# Create a stable string representation
key_parts = [command, project_folder] + sorted(args)
key_str = "|".join(key_parts)
⋮----
def get(self, command: str, args: List[str], project_folder: str) -> Optional[List[Dict[str, Any]]]
⋮----
"""Get cached results if available and not expired.

        Args:
            command: ast-grep command (run/scan)
            args: Command arguments
            project_folder: Project folder path

        Returns:
            Cached results if found and valid, None otherwise
        """
key = self._make_key(command, args, project_folder)
⋮----
# Check TTL
⋮----
# Expired, remove from cache
⋮----
# Move to end (mark as recently used)
⋮----
def put(self, command: str, args: List[str], project_folder: str, results: List[Dict[str, Any]]) -> None
⋮----
"""Store results in cache.

        Args:
            command: ast-grep command (run/scan)
            args: Command arguments
            project_folder: Project folder path
            results: Query results to cache
        """
⋮----
# Remove oldest entry if at capacity
⋮----
self.cache.popitem(last=False)  # Remove oldest (first) item
⋮----
# Store with current timestamp
⋮----
def clear(self) -> None
⋮----
"""Clear all cache entries."""
⋮----
def get_stats(self) -> Dict[str, Any]
⋮----
"""Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
total = self.hits + self.misses
hit_rate = self.hits / total if total > 0 else 0
⋮----
# Global cache instance (initialized after config is parsed)
_query_cache: Optional[QueryCache] = None
⋮----
def get_query_cache() -> Optional[QueryCache]
⋮----
"""Get the global query cache instance if caching is enabled."""
⋮----
def init_query_cache(max_size: int, ttl_seconds: int) -> None
⋮----
"""Initialize the global query cache.

    Args:
        max_size: Maximum number of entries to cache
        ttl_seconds: Time-to-live for cache entries in seconds
    """
⋮----
_query_cache = QueryCache(max_size=max_size, ttl_seconds=ttl_seconds)
````

## File: src/ast_grep_mcp/core/logging.py
````python
"""Logging configuration for ast-grep MCP server."""
⋮----
def configure_logging(log_level: str = "INFO", log_file: Optional[str] = None) -> None
⋮----
"""Configure structured logging with JSON output.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for logging (stderr by default)
    """
# Convert log level string to int
level_mapping = {
numeric_level = level_mapping.get(log_level.upper(), logging.INFO)
⋮----
# Configure processors for structured logging
processors: List[Any] = [
⋮----
# Configure structlog
⋮----
logger_factory=structlog.WriteLoggerFactory(file=sys.stderr if log_file is None else open(log_file, "a")),  # noqa: SIM115 - file must stay open for logging
⋮----
def get_logger(name: str) -> Any
⋮----
"""Get a logger instance with the given name.

    Args:
        name: Logger name (typically module or tool name)

    Returns:
        Configured structlog logger
    """
````

## File: src/ast_grep_mcp/core/sentry.py
````python
"""Sentry error tracking integration for ast-grep MCP server."""
⋮----
# Re-export capture_exception for backward compatibility
⋮----
def init_sentry(service_name: str = "ast-grep-mcp") -> None
⋮----
"""Initialize Sentry with Anthropic AI integration and service tagging.

    Args:
        service_name: Unique service identifier (default: 'ast-grep-mcp')
    """
⋮----
def _tag_event(event: Any, hint: Any) -> Any
⋮----
"""Add service tags to every event for unified project."""
⋮----
# Only initialize if SENTRY_DSN is set
dsn = os.getenv("SENTRY_DSN")
⋮----
# Environment
⋮----
# Integrations - Include Anthropic AI
⋮----
include_prompts=True,  # Capture prompts and responses
⋮----
# Performance monitoring - REQUIRED for AI tracking
⋮----
# Send PII for AI context
⋮----
# Additional options
⋮----
# Tag every event with service name
⋮----
# Set global tags for all future events
⋮----
logger = get_logger("sentry")
````

## File: src/ast_grep_mcp/models/orphan.py
````python
"""Data models for orphan code detection.

This module provides models for representing orphan files and functions
detected during codebase analysis.
"""
⋮----
class OrphanType(str, Enum)
⋮----
"""Type of orphan artifact."""
⋮----
FILE = "file"
FUNCTION = "function"
CLASS = "class"
VARIABLE = "variable"
⋮----
class VerificationStatus(str, Enum)
⋮----
"""Verification status for orphan detection."""
⋮----
CONFIRMED = "confirmed"  # Verified as orphan via multiple methods
LIKELY = "likely"  # High confidence but not fully verified
UNCERTAIN = "uncertain"  # Possible false positive
FALSE_POSITIVE = "false_positive"  # Verified as actually used
⋮----
@dataclass
class OrphanFile
⋮----
"""Represents an orphan file (not imported anywhere).

    Attributes:
        file_path: Relative path from project root
        absolute_path: Absolute path to the file
        lines: Number of lines in the file
        language: Programming language
        status: Verification status
        reason: Why it was flagged as orphan
        importers: Files that import this (should be empty for orphans)
        exports: Functions/classes exported by this file
    """
⋮----
file_path: str
absolute_path: str
lines: int
language: str
status: VerificationStatus = VerificationStatus.LIKELY
reason: str = "No imports found"
importers: List[str] = field(default_factory=list)
exports: List[str] = field(default_factory=list)
⋮----
def to_dict(self) -> Dict[str, Any]
⋮----
"""Convert to dictionary for serialization."""
⋮----
@dataclass
class OrphanFunction
⋮----
"""Represents an orphan function (defined but never called).

    Attributes:
        name: Function name
        file_path: File containing the function
        line_start: Start line number
        line_end: End line number
        status: Verification status
        reason: Why it was flagged as orphan
        callers: Files/functions that call this (should be empty for orphans)
        is_exported: Whether it's exported from the module
        is_private: Whether it's a private function (starts with _)
    """
⋮----
name: str
⋮----
line_start: int
line_end: int
⋮----
reason: str = "No call sites found"
callers: List[str] = field(default_factory=list)
is_exported: bool = False
is_private: bool = False
⋮----
@property
    def lines(self) -> int
⋮----
"""Calculate number of lines in the function."""
⋮----
@dataclass
class DependencyEdge
⋮----
"""Represents a dependency between two files.

    Attributes:
        source: Importing file
        target: Imported file
        import_type: Type of import (absolute, relative, dynamic)
        import_statement: The actual import statement
    """
⋮----
source: str
target: str
import_type: str = "absolute"
import_statement: str = ""
⋮----
@dataclass
class DependencyGraph
⋮----
"""Represents the import dependency graph.

    Attributes:
        files: All files in the graph
        edges: Import relationships between files
        entry_points: Known entry points (main files, test files, etc.)
        external_imports: External package imports by file
    """
⋮----
files: Set[str] = field(default_factory=set)
edges: List[DependencyEdge] = field(default_factory=list)
entry_points: Set[str] = field(default_factory=set)
external_imports: Dict[str, Set[str]] = field(default_factory=dict)
⋮----
def get_importers(self, file_path: str) -> List[str]
⋮----
"""Get all files that import the given file."""
⋮----
def get_imports(self, file_path: str) -> List[str]
⋮----
"""Get all files imported by the given file."""
⋮----
def is_reachable_from_entry(self, file_path: str) -> bool
⋮----
"""Check if file is reachable from any entry point."""
visited: Set[str] = set()
stack = list(self.entry_points)
⋮----
current = stack.pop()
⋮----
@dataclass
class OrphanAnalysisConfig
⋮----
"""Configuration for orphan analysis.

    Attributes:
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude
        entry_point_patterns: Patterns for identifying entry points
        analyze_functions: Whether to analyze function-level orphans
        verify_with_grep: Whether to double-check with grep
        languages: Languages to analyze
    """
⋮----
include_patterns: List[str] = field(default_factory=lambda: ["**/*.py", "**/*.ts", "**/*.js"])
exclude_patterns: List[str] = field(
entry_point_patterns: List[str] = field(
analyze_functions: bool = True
verify_with_grep: bool = True
languages: List[str] = field(default_factory=lambda: ["python", "typescript"])
⋮----
@dataclass
class OrphanAnalysisResult
⋮----
"""Result of orphan code analysis.

    Attributes:
        orphan_files: List of orphan files found
        orphan_functions: List of orphan functions found
        total_files_analyzed: Total number of files analyzed
        total_functions_analyzed: Total number of functions analyzed
        dependency_graph: The built dependency graph
        analysis_time_ms: Time taken for analysis in milliseconds
        config: Configuration used for analysis
    """
⋮----
orphan_files: List[OrphanFile] = field(default_factory=list)
orphan_functions: List[OrphanFunction] = field(default_factory=list)
total_files_analyzed: int = 0
total_functions_analyzed: int = 0
dependency_graph: Optional[DependencyGraph] = None
analysis_time_ms: int = 0
config: Optional[OrphanAnalysisConfig] = None
⋮----
@property
    def total_orphan_lines(self) -> int
⋮----
"""Calculate total lines in orphan code."""
file_lines = sum(f.lines for f in self.orphan_files)
func_lines = sum(f.lines for f in self.orphan_functions)
⋮----
@property
    def orphan_file_count(self) -> int
⋮----
"""Count of orphan files."""
⋮----
@property
    def orphan_function_count(self) -> int
⋮----
"""Count of orphan functions."""
````

## File: src/ast_grep_mcp/models/pattern_debug.py
````python
"""Models for pattern debugging functionality.

This module provides dataclasses for pattern debugging results,
including AST comparison, metavariable validation, and suggestions.
"""
⋮----
class IssueSeverity(Enum)
⋮----
"""Severity level for pattern issues."""
⋮----
ERROR = "error"
WARNING = "warning"
INFO = "info"
⋮----
class IssueCategory(Enum)
⋮----
"""Category of pattern issue."""
⋮----
METAVARIABLE = "metavariable"
SYNTAX = "syntax"
STRUCTURE = "structure"
RELATIONAL = "relational"
BEST_PRACTICE = "best_practice"
⋮----
@dataclass
class PatternIssue
⋮----
"""An issue found in a pattern.

    Attributes:
        severity: How severe the issue is (error, warning, info)
        category: Category of the issue
        message: Description of the issue
        suggestion: How to fix the issue
        location: Where in the pattern the issue occurs (if applicable)
    """
⋮----
severity: IssueSeverity
category: IssueCategory
message: str
suggestion: str
location: Optional[str] = None
⋮----
@dataclass
class MetavariableInfo
⋮----
"""Information about a metavariable in a pattern.

    Attributes:
        name: The metavariable name (e.g., $NAME, $$$ARGS)
        type: Type of metavariable (single, multi, non_capturing, unnamed)
        valid: Whether the metavariable syntax is valid
        occurrences: Number of times it appears in the pattern
        issue: Any issue with this metavariable
    """
⋮----
name: str
type: str  # "single", "multi", "non_capturing", "unnamed"
valid: bool
occurrences: int = 1
issue: Optional[str] = None
⋮----
@dataclass
class AstComparison
⋮----
"""Comparison between pattern AST and code AST.

    Attributes:
        pattern_root_kind: Root node kind in pattern AST
        code_root_kind: Root node kind in code AST
        kinds_match: Whether the root kinds match
        pattern_structure: Simplified pattern AST structure
        code_structure: Simplified code AST structure
        structural_differences: List of structural differences found
    """
⋮----
pattern_root_kind: Optional[str]
code_root_kind: Optional[str]
kinds_match: bool
pattern_structure: str
code_structure: str
structural_differences: List[str] = field(default_factory=list)
⋮----
@dataclass
class MatchAttempt
⋮----
"""Result of attempting to match pattern against code.

    Attributes:
        matched: Whether any matches were found
        match_count: Number of matches found
        matches: List of match details
        partial_matches: Potential partial matches (for debugging)
    """
⋮----
matched: bool
match_count: int = 0
matches: List[Dict[str, Any]] = field(default_factory=list)
partial_matches: List[str] = field(default_factory=list)
⋮----
@dataclass
class PatternDebugResult
⋮----
"""Complete result of pattern debugging.

    Attributes:
        pattern: The original pattern
        code: The code being matched against
        language: The language used
        pattern_valid: Whether the pattern is syntactically valid
        pattern_ast: The pattern's AST structure
        code_ast: The code's AST structure
        ast_comparison: Comparison between pattern and code ASTs
        metavariables: Information about metavariables in the pattern
        issues: List of issues found
        suggestions: Prioritized list of fix suggestions
        match_attempt: Result of attempting to match
        execution_time_ms: Time taken to debug in milliseconds
    """
⋮----
pattern: str
code: str
language: str
pattern_valid: bool
pattern_ast: str
code_ast: str
ast_comparison: AstComparison
metavariables: List[MetavariableInfo]
issues: List[PatternIssue]
suggestions: List[str]
match_attempt: MatchAttempt
execution_time_ms: int
⋮----
def to_dict(self) -> Dict[str, Any]
⋮----
"""Convert to dictionary for JSON serialization."""
````

## File: src/ast_grep_mcp/models/pattern_develop.py
````python
"""Models for interactive pattern development functionality.

This module provides dataclasses for pattern development results,
including code analysis, pattern suggestions, and refinement guidance.
"""
⋮----
class SuggestionType(Enum)
⋮----
"""Type of pattern suggestion."""
⋮----
EXACT = "exact"  # Matches exactly what was provided
GENERALIZED = "generalized"  # With metavariables for flexibility
STRUCTURAL = "structural"  # Based on node kind only
⋮----
@dataclass
class PatternSuggestion
⋮----
"""A suggested pattern with explanation.

    Attributes:
        pattern: The suggested pattern string
        description: What this pattern matches
        type: Type of suggestion (exact, generalized, structural)
        confidence: How likely this pattern is correct (0.0-1.0)
        notes: Additional notes about usage
    """
⋮----
pattern: str
description: str
type: SuggestionType
confidence: float
notes: Optional[str] = None
⋮----
def to_dict(self) -> Dict[str, Any]
⋮----
"""Convert to dictionary for JSON serialization."""
⋮----
@dataclass
class CodeAnalysis
⋮----
"""Analysis of the target code structure.

    Attributes:
        root_kind: The root AST node kind
        child_kinds: List of child node kinds
        identifiers: Identified identifier names
        literals: Identified literal values
        keywords: Language keywords found
        complexity: Simple/Medium/Complex based on AST depth
        ast_preview: Simplified AST structure preview
    """
⋮----
root_kind: str
child_kinds: List[str]
identifiers: List[str]
literals: List[str]
keywords: List[str]
complexity: str  # "simple", "medium", "complex"
ast_preview: str
⋮----
@dataclass
class RefinementStep
⋮----
"""A step in the pattern refinement process.

    Attributes:
        action: What action to take
        pattern: The pattern after this step
        explanation: Why this step helps
        priority: Order to try (1 = first)
    """
⋮----
action: str
⋮----
explanation: str
priority: int
⋮----
@dataclass
class PatternDevelopResult
⋮----
"""Complete result of pattern development assistance.

    Attributes:
        code: The target code to match
        language: The programming language
        code_analysis: Analysis of the code structure
        suggested_patterns: List of pattern suggestions, ordered by recommendation
        best_pattern: The recommended pattern to start with
        pattern_matches: Whether the best pattern matches the code
        match_count: Number of matches if applicable
        refinement_steps: Steps to refine the pattern if needed
        yaml_rule_template: Ready-to-use YAML rule with the best pattern
        next_steps: Guidance on what to do next
        execution_time_ms: Time taken in milliseconds
    """
⋮----
code: str
language: str
code_analysis: CodeAnalysis
suggested_patterns: List[PatternSuggestion]
best_pattern: str
pattern_matches: bool
match_count: int
refinement_steps: List[RefinementStep]
yaml_rule_template: str
next_steps: List[str]
execution_time_ms: int
````

## File: src/ast_grep_mcp/core/config.py
````python
"""Configuration management for ast-grep MCP server."""
⋮----
# Global variable for config path (will be set by parse_args_and_get_config)
CONFIG_PATH: Optional[str] = None
⋮----
# Global cache configuration (set by parse_args_and_get_config)
CACHE_ENABLED: bool = True
CACHE_SIZE: int = CacheDefaults.DEFAULT_CACHE_SIZE
CACHE_TTL: int = CacheDefaults.CLEANUP_INTERVAL_SECONDS  # Reuse cleanup interval for TTL
⋮----
# Global cache instance (will be set after cache.py is extracted)
_query_cache: Optional[Any] = None
⋮----
def validate_config_file(config_path: str) -> AstGrepConfig
⋮----
"""Validate sgconfig.yaml file structure.

    Args:
        config_path: Path to sgconfig.yaml file

    Returns:
        Validated AstGrepConfig model

    Raises:
        ConfigurationError: If config file is invalid
    """
⋮----
config_data = yaml.safe_load(f)
⋮----
# Validate using Pydantic model
⋮----
config = AstGrepConfig(**config_data)
⋮----
def _create_argument_parser() -> argparse.ArgumentParser
⋮----
"""Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
# Determine how the script was invoked
prog = None
⋮----
# Direct execution: python main.py
prog = "python main.py"
⋮----
parser = argparse.ArgumentParser(
⋮----
def _resolve_and_validate_config_path(args: argparse.Namespace) -> Optional[str]
⋮----
"""Resolve and validate config file path from args or environment.

    Precedence: --config flag > AST_GREP_CONFIG env > None

    Args:
        args: Parsed command-line arguments.

    Returns:
        Path to config file or None if not specified.

    Note:
        Calls sys.exit(1) if validation fails.
    """
config_path = None
⋮----
config_path = args.config
⋮----
logger = get_logger("config")
⋮----
env_config = os.environ.get("AST_GREP_CONFIG")
⋮----
config_path = env_config
⋮----
def _configure_logging_from_args(args: argparse.Namespace) -> None
⋮----
"""Configure logging based on command-line arguments and environment.

    Precedence: --log-level/--log-file flags > env vars > defaults

    Args:
        args: Parsed command-line arguments.
    """
# Determine log level with precedence: --log-level flag > LOG_LEVEL env > INFO
log_level = args.log_level or os.environ.get("LOG_LEVEL", "INFO")
⋮----
# Determine log file with precedence: --log-file flag > LOG_FILE env > None (stderr)
log_file = args.log_file or os.environ.get("LOG_FILE")
⋮----
# Configure logging
⋮----
def _configure_cache_from_args(args: argparse.Namespace) -> tuple[bool, int, int]
⋮----
"""Configure cache settings from command-line arguments and environment.

    Precedence: command-line flags > env vars > defaults

    Args:
        args: Parsed command-line arguments.

    Returns:
        Tuple of (cache_enabled, cache_size, cache_ttl).
    """
cache_logger = get_logger("cache.init")
⋮----
# Check if caching is disabled
cache_enabled = True
⋮----
cache_enabled = False
⋮----
# Set cache size
cache_size = CacheDefaults.DEFAULT_CACHE_SIZE
⋮----
cache_size = args.cache_size
⋮----
cache_size = int(os.environ.get("CACHE_SIZE", str(CacheDefaults.DEFAULT_CACHE_SIZE)))
⋮----
# Set cache TTL
cache_ttl = CacheDefaults.CLEANUP_INTERVAL_SECONDS
⋮----
cache_ttl = args.cache_ttl
⋮----
cache_ttl = int(os.environ.get("CACHE_TTL", str(CacheDefaults.CLEANUP_INTERVAL_SECONDS)))
⋮----
# Log the configuration
⋮----
def parse_args_and_get_config() -> None
⋮----
"""Parse command-line arguments and determine config path."""
⋮----
# Parse arguments
parser = _create_argument_parser()
args = parser.parse_args()
⋮----
# Resolve and validate config
CONFIG_PATH = _resolve_and_validate_config_path(args)
⋮----
# Configure cache
````

## File: src/ast_grep_mcp/core/exceptions.py
````python
"""Custom exceptions for ast-grep MCP server."""
⋮----
class AstGrepError(Exception)
⋮----
"""Base exception for all ast-grep MCP server errors."""
⋮----
class AstGrepNotFoundError(AstGrepError)
⋮----
"""Raised when ast-grep binary is not found in PATH."""
⋮----
def __init__(self, message: str = "ast-grep command not found") -> None
⋮----
class InvalidYAMLError(AstGrepError)
⋮----
"""Raised when YAML rule is invalid or malformed."""
⋮----
def __init__(self, message: str, yaml_content: Optional[str] = None) -> None
⋮----
error_msg = f"Invalid YAML rule: {message}\n\n"
⋮----
class ConfigurationError(AstGrepError)
⋮----
"""Raised when configuration file is invalid."""
⋮----
def __init__(self, config_path: str, message: str) -> None
⋮----
class AstGrepExecutionError(AstGrepError)
⋮----
"""Raised when ast-grep command execution fails."""
⋮----
def __init__(self, command: List[str], returncode: int, stderr: str) -> None
⋮----
error_msg = f"ast-grep command failed with exit code {returncode}\n\n"
⋮----
class NoMatchesError(AstGrepError)
⋮----
"""Raised when no matches are found (for test_match_code_rule only)."""
⋮----
def __init__(self, message: str = "No matches found") -> None
⋮----
# These exceptions are for the quality/standards feature
class RuleValidationError(Exception)
⋮----
"""Raised when a linting rule validation fails."""
⋮----
class RuleStorageError(Exception)
⋮----
"""Raised when a linting rule cannot be stored."""
````

## File: src/ast_grep_mcp/features/condense/__init__.py
````python
"""Code condensation feature module.

Provides a semantic extraction + normalization + dead-code-strip pipeline
that achieves 30–85% token reduction depending on strategy.

Tools:
- condense_extract_surface: Extract public API surface (exports, signatures, types)
- condense_normalize: Rewrite code to canonical forms before compression
- condense_strip: Remove dead code, debug statements, unused imports
- condense_pack: Combined pipeline (normalize → strip → extract)
- condense_estimate: Estimate reduction ratio without modifying files
- condense_train_dictionary: Train a zstd dictionary for improved compression

Modules:
- service: Core condensation logic (extract_surface_impl, condense_pack_impl)
- estimator: Non-destructive reduction estimation
- normalizer: Code normalization transforms
- strip: Dead code removal
- strategies: Strategy definitions and validation
- dictionary: zstd dictionary training
- tools: MCP tool registrations
"""
⋮----
__all__ = [
````

## File: src/ast_grep_mcp/models/__init__.py
````python
"""Data models for ast-grep MCP server."""
⋮----
# Condense models
# Config models
# Complexity models
⋮----
# Deduplication models
⋮----
# Standards models
⋮----
__all__ = [
⋮----
# Condense
⋮----
# Config
⋮----
# Deduplication
⋮----
# Complexity
⋮----
# Standards
````

## File: src/ast_grep_mcp/models/complexity.py
````python
"""Data models for code complexity analysis."""
⋮----
@dataclass
class ComplexityMetrics
⋮----
"""Immutable metrics container for a single function."""
⋮----
cyclomatic: int
cognitive: int
nesting_depth: int
lines: int
parameter_count: int = 0
⋮----
@dataclass
class FunctionComplexity
⋮----
"""Complete analysis result for one function."""
⋮----
file_path: str
function_name: str
start_line: int
end_line: int
metrics: ComplexityMetrics
language: str
exceeds: List[str] = field(default_factory=list)
⋮----
@dataclass
class ComplexityThresholds
⋮----
"""Configurable thresholds with sensible defaults."""
⋮----
cyclomatic: int = ComplexityDefaults.CYCLOMATIC_THRESHOLD
cognitive: int = ComplexityDefaults.COGNITIVE_THRESHOLD
nesting_depth: int = ComplexityDefaults.NESTING_THRESHOLD
lines: int = ComplexityDefaults.LENGTH_THRESHOLD
⋮----
def get_complexity_level(score: int) -> str
⋮----
"""Get complexity level from score.

    Args:
        score: Numeric complexity score

    Returns:
        Complexity level string: "low", "medium", or "high"
    """
````

## File: src/ast_grep_mcp/models/deduplication.py
````python
"""Data models for code deduplication functionality."""
⋮----
class VariationCategory
⋮----
"""Categories for classifying variations between duplicate code blocks."""
⋮----
LITERAL = "LITERAL"  # string, number, boolean differences
IDENTIFIER = "IDENTIFIER"  # variable/function/class name differences
EXPRESSION = "EXPRESSION"  # operator, call, compound expression differences
LOGIC = "LOGIC"  # control flow differences (if/else, loops)
TYPE = "TYPE"  # type annotation differences
⋮----
class VariationSeverity
⋮----
"""Severity levels for variations."""
⋮----
LOW = "low"  # Minor differences, easy to parameterize
MEDIUM = "medium"  # Moderate differences, requires some refactoring
HIGH = "high"  # Significant differences, complex refactoring needed
⋮----
@dataclass
class AlignmentSegment
⋮----
"""Represents a segment in the alignment between two code blocks."""
⋮----
segment_type: str  # 'aligned', 'divergent', 'inserted', 'deleted'
block1_start: int  # Line number in block 1 (0-indexed, -1 if N/A)
block1_end: int  # End line in block 1 (exclusive)
block2_start: int  # Line number in block 2 (0-indexed, -1 if N/A)
block2_end: int  # End line in block 2 (exclusive)
block1_text: str  # Text from block 1
block2_text: str  # Text from block 2
metadata: Optional[Dict[str, Any]] = None  # Multi-line info, construct types, etc.
⋮----
def __post_init__(self) -> None
⋮----
"""Initialize metadata if not provided."""
⋮----
@dataclass
class AlignmentResult
⋮----
"""Result of aligning two code blocks for comparison."""
⋮----
segments: List[AlignmentSegment]
similarity_ratio: float
aligned_lines: int
divergent_lines: int
block1_total_lines: int
block2_total_lines: int
⋮----
@dataclass
class DiffTreeNode
⋮----
"""A node in a hierarchical diff tree structure.

    Represents code differences hierarchically, allowing nested structures
    to be represented with parent-child relationships.
    """
⋮----
node_type: str  # 'aligned', 'divergent', 'inserted', 'deleted', 'container'
content: str  # The code content for this node
children: List["DiffTreeNode"]  # Child nodes for nested structures
metadata: Dict[str, Any]  # Additional metadata (line numbers, similarity, etc.)
⋮----
"""Ensure children is a mutable list."""
⋮----
def add_child(self, child: "DiffTreeNode") -> None
⋮----
"""Add a child node."""
⋮----
def get_all_nodes(self) -> List["DiffTreeNode"]
⋮----
"""Get all nodes in the tree (depth-first traversal)."""
result = [self]
⋮----
def find_by_type(self, node_type: str) -> List["DiffTreeNode"]
⋮----
"""Find all nodes of a specific type."""
⋮----
def get_depth(self) -> int
⋮----
"""Get the maximum depth of the tree from this node."""
⋮----
def count_by_type(self) -> Dict[str, int]
⋮----
"""Count nodes by type in the subtree."""
counts: Dict[str, int] = {}
⋮----
@dataclass
class DiffTree
⋮----
"""Hierarchical representation of code differences.

    A tree structure that represents differences between duplicate code blocks
    in a hierarchical manner, preserving nesting and structure.
    """
⋮----
root: DiffTreeNode
file1_path: str
file2_path: str
file1_lines: List[str]
file2_lines: List[str]
alignment_result: AlignmentResult
⋮----
def get_statistics(self) -> Dict[str, Any]
⋮----
"""Get statistics about the diff tree."""
type_counts = self.root.count_by_type()
divergent_nodes = self.root.find_by_type("divergent")
⋮----
def serialize_for_display(self, node: Optional[DiffTreeNode] = None, depth: int = 0) -> List[str]
⋮----
"""Serialize the tree for human-readable display."""
⋮----
node = self.root
⋮----
lines = []
indent = "  " * depth
⋮----
# Add node information
symbol = {"aligned": "=", "divergent": "≠", "inserted": "+", "deleted": "-", "container": "◊"}.get(node.node_type, "?")
⋮----
# Add metadata if significant
⋮----
# Add content preview (first line only for brevity)
⋮----
preview = node.content.strip().split("\n")[0][: DisplayDefaults.CONTENT_PREVIEW_LENGTH]
⋮----
# Process children
⋮----
@dataclass
class FunctionTemplate
⋮----
"""Template for generating extracted functions from duplicate code.

    This dataclass holds all the components needed to generate a function
    that consolidates duplicate code patterns.

    Attributes:
        name: Function name (valid Python identifier)
        parameters: List of tuples (param_name, param_type) for function signature
        body: The function body code (properly indented)
        return_type: Optional return type annotation
        docstring: Optional docstring describing the function
        decorators: Optional list of decorator strings (without @)
    """
⋮----
name: str
parameters: List[Tuple[str, Optional[str]]]
body: str
return_type: Optional[str] = None
docstring: Optional[str] = None
decorators: Optional[List[str]] = None
⋮----
"""Validate function template after initialization."""
# Ensure function name is a valid identifier
⋮----
# Ensure parameters have valid names
⋮----
# Initialize decorators list if needed
⋮----
def format_params(self) -> str
⋮----
"""Format parameters as a comma-separated string for function signature.

        Returns:
            Formatted parameter string like "a: int, b, c: str"
        """
parts = []
⋮----
def format_decorators(self) -> str
⋮----
"""Format decorators as lines with @ prefix.

        Returns:
            Decorator lines with newlines, or empty string if no decorators
        """
⋮----
def format_return_type(self) -> str
⋮----
"""Format return type annotation.

        Returns:
            Return type string like " -> int" or empty string if no return type
        """
⋮----
def generate(self) -> str
⋮----
"""Generate the complete function code from the template.

        Returns:
            Formatted Python function code
        """
⋮----
# Add decorators
⋮----
# Add function signature
params = self.format_params()
return_annotation = self.format_return_type()
⋮----
# Add docstring
⋮----
# Multi-line docstring
⋮----
# Single-line docstring
⋮----
# Add body (ensure proper indentation)
body_lines = self.body.split("\n")
⋮----
if line.strip():  # Only indent non-empty lines
⋮----
class ParameterType
⋮----
"""Represents an inferred type for an extracted parameter."""
⋮----
# Simple type constants for backward compatibility
STRING = "string"
NUMBER = "number"
BOOLEAN = "boolean"
INTEGER = "integer"
LIST = "list"
DICT = "dict"
ANY = "any"
⋮----
# Common types for different languages
PYTHON_TYPES = {"string": "str", "number": "float", "integer": "int", "boolean": "bool", "list": "List", "dict": "Dict", "any": "Any"}
⋮----
TYPESCRIPT_TYPES = {
⋮----
JAVA_TYPES = {
⋮----
def __init__(self, base_type: str, language: str = "python") -> None
⋮----
"""Initialize parameter type.

        Args:
            base_type: Base type identifier ('string', 'number', etc.)
            language: Target language for type annotation
        """
⋮----
def _get_type_map(self) -> Dict[str, str]
⋮----
"""Get the appropriate type map for the language."""
⋮----
return self.PYTHON_TYPES  # Default to Python
⋮----
def get_type_annotation(self) -> str
⋮----
"""Get the type annotation for the current language."""
⋮----
def __str__(self) -> str
⋮----
"""String representation of the type."""
⋮----
class ParameterInfo
⋮----
"""Represents a parameter for code generation with type information."""
⋮----
def __init__(self, name: str, param_type: Optional[ParameterType] = None, default_value: Optional[str] = None) -> None
⋮----
"""Initialize parameter info.

        Args:
            name: Parameter name
            param_type: Optional type information
            default_value: Optional default value
        """
⋮----
def to_signature(self, language: str = "python") -> str
⋮----
"""Generate parameter signature for function declaration.

        Args:
            language: Target language

        Returns:
            Parameter signature string
        """
⋮----
sig = self.name
⋮----
@dataclass
class FileDiff
⋮----
"""Represents a diff for a single file.

    Attributes:
        file_path: Absolute path to the file
        original_content: Original file content
        new_content: New content after changes
        unified_diff: Raw unified diff string
        formatted_diff: Human-readable formatted diff with colors/context
        hunks: List of individual diff hunks
        additions: Number of lines added
        deletions: Number of lines deleted
    """
⋮----
file_path: str
original_content: str
new_content: str
unified_diff: str
formatted_diff: str
hunks: List[Dict[str, Any]]
additions: int
deletions: int
⋮----
@dataclass
class DiffPreview
⋮----
"""Container for multi-file diff preview.

    Attributes:
        file_diffs: List of individual file diffs
        total_additions: Total lines added across all files
        total_deletions: Total lines deleted across all files
        affected_files: List of affected file paths
        summary: Human-readable summary of changes
        colorized_output: Full colorized diff output for display
    """
⋮----
file_diffs: List[FileDiff]
total_additions: int
total_deletions: int
affected_files: List[str]
summary: str
colorized_output: str
⋮----
def to_dict(self) -> Dict[str, Any]
⋮----
"""Convert to dictionary representation."""
⋮----
def get_file_diff(self, file_path: str) -> Optional[FileDiff]
⋮----
"""Get diff for a specific file."""
⋮----
@dataclass
class EnhancedDuplicationCandidate
⋮----
"""Enhanced duplication candidate with full reporting details.

    This dataclass combines the basic duplication detection results with
    enriched analysis data including scoring, recommendations, and visualizations.

    Attributes:
        pattern: Pattern that matches the duplicate code
        language: Programming language
        instances: List of duplicate occurrences
        score: Deduplication value score (0-100)
        score_breakdown: Detailed breakdown of score components
        recommendation: Generated recommendation text
        strategies: List of refactoring strategies with details
        before_example: Example of code before refactoring
        after_example: Example of code after refactoring
        complexity_visualization: ASCII visualization of complexity
        estimated_savings: Lines of code that would be saved
        risk_level: Risk assessment (low/medium/high)
        test_coverage: Whether test coverage exists
        impact_analysis: Detailed impact analysis
        priority_rank: Priority ranking among all candidates
    """
⋮----
pattern: str
language: str
instances: List[Dict[str, Any]]
score: float
score_breakdown: Dict[str, float]
recommendation: str
strategies: List[Dict[str, Any]]
before_example: str
after_example: str
complexity_visualization: str
estimated_savings: int
risk_level: str
test_coverage: bool
impact_analysis: Dict[str, Any]
priority_rank: int = 0
⋮----
def to_summary(self) -> Dict[str, Any]
⋮----
"""Create a summary dictionary for concise reporting."""
````

## File: src/ast_grep_mcp/models/standards.py
````python
"""Data models for code quality standards and linting rules."""
⋮----
class RuleValidationError(Exception)
⋮----
"""Raised when a linting rule validation fails."""
⋮----
class RuleStorageError(Exception)
⋮----
"""Raised when saving/loading rules fails."""
⋮----
@dataclass
class LintingRule
⋮----
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
⋮----
id: str
language: str
severity: str  # 'error', 'warning', 'info'
message: str
pattern: str
note: Optional[str] = None
fix: Optional[str] = None
constraints: Optional[Dict[str, Any]] = None
exclude_files: List[str] = field(default_factory=list)
⋮----
def to_yaml_dict(self) -> Dict[str, Any]
⋮----
"""Convert to ast-grep YAML format.

        Returns:
            Dictionary ready for YAML serialization in ast-grep format
        """
yaml_dict: Dict[str, Any] = {
⋮----
# Add rule configuration
rule_config: Dict[str, Any] = {}
⋮----
# Add constraints if present
⋮----
# Add optional fields
⋮----
@dataclass
class RuleTemplate
⋮----
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
⋮----
name: str
description: str
⋮----
severity: str
⋮----
category: str = "general"
⋮----
@dataclass
class RuleValidationResult
⋮----
"""Result of rule validation.

    Attributes:
        is_valid: Whether the rule is valid
        errors: List of error messages (blocking issues)
        warnings: List of warning messages (non-blocking issues)
    """
⋮----
is_valid: bool
errors: List[str] = field(default_factory=list)
warnings: List[str] = field(default_factory=list)
⋮----
@dataclass
class RuleViolation
⋮----
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
⋮----
file: str
line: int
column: int
end_line: int
end_column: int
⋮----
rule_id: str
⋮----
code_snippet: str
fix_suggestion: Optional[str] = None
meta_vars: Optional[Dict[str, str]] = None
⋮----
@dataclass
class RuleSet
⋮----
"""Collection of linting rules with metadata.

    Attributes:
        name: Rule set identifier ('recommended', 'security', etc.)
        description: Human-readable description
        rules: List of LintingRule objects in this set
        priority: Execution priority (higher = run first)
    """
⋮----
rules: List[LintingRule]
priority: int = 0
⋮----
@dataclass
class EnforcementResult
⋮----
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
⋮----
summary: Dict[str, Any]
violations: List[RuleViolation]
violations_by_file: Dict[str, List[RuleViolation]]
violations_by_severity: Dict[str, List[RuleViolation]]
violations_by_rule: Dict[str, List[RuleViolation]]
rules_executed: List[str]
execution_time_ms: int
files_scanned: int
⋮----
@dataclass
class RuleExecutionContext
⋮----
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
⋮----
project_folder: str
⋮----
include_patterns: List[str]
exclude_patterns: List[str]
max_violations: int
max_threads: int
logger: Any  # structlog logger
⋮----
# =============================================================================
# Auto-Fix Data Models
⋮----
@dataclass
class FixResult
⋮----
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
⋮----
violation: RuleViolation
success: bool
file_modified: bool
original_code: str
fixed_code: Optional[str] = None
syntax_valid: bool = True
error: Optional[str] = None
fix_type: str = "safe"
⋮----
@dataclass
class FixValidation
⋮----
"""Result of validating a proposed fix.

    Attributes:
        is_safe: Whether the fix is safe to auto-apply
        confidence: Confidence score 0.0-1.0
        warnings: Non-blocking warnings about the fix
        errors: Blocking errors that prevent auto-fix
        requires_review: Whether manual review is recommended
    """
⋮----
is_safe: bool
confidence: float  # 0.0 to 1.0
⋮----
requires_review: bool = False
⋮----
@dataclass
class FixBatchResult
⋮----
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
⋮----
total_violations: int
fixes_attempted: int
fixes_successful: int
fixes_failed: int
files_modified: List[str]
backup_id: Optional[str] = None
validation_passed: bool = True
results: List[FixResult] = field(default_factory=list)
execution_time_ms: int = 0
⋮----
# Security Scanner Data Models
⋮----
@dataclass
class SecurityIssue
⋮----
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
⋮----
issue_type: str
severity: str  # 'critical', 'high', 'medium', 'low'
title: str
⋮----
remediation: str
cwe_id: Optional[str] = None
confidence: float = 1.0
references: List[str] = field(default_factory=list)
⋮----
@dataclass
class SecurityScanResult
⋮----
"""Result from security vulnerability scan.

    Attributes:
        summary: Summary statistics
        issues: All security issues found
        issues_by_severity: Issues grouped by severity
        issues_by_type: Issues grouped by issue type
        files_scanned: Number of files scanned
        execution_time_ms: Total execution time
    """
⋮----
issues: List[SecurityIssue]
issues_by_severity: Dict[str, List[SecurityIssue]]
issues_by_type: Dict[str, List[SecurityIssue]]
````

## File: src/ast_grep_mcp/utils/__init__.py
````python
"""Utilities module for ast-grep MCP server.

This module provides various utility functions for:
- Code generation templates
- Text formatting and display
- String manipulation and similarity
- Configuration validation
"""
⋮----
# Template utilities
# Formatting utilities
⋮----
# Templates
⋮----
# Java formatting
⋮----
# JavaScript formatting
⋮----
# Python formatting
⋮----
# TypeScript formatting
⋮----
# Text utilities
⋮----
# Validation utilities
⋮----
__all__ = [
⋮----
# Template formatting functions
⋮----
# Formatters
⋮----
# Slicing utilities
⋮----
# Validation
````

## File: main.py
````python
"""ast-grep MCP Server - Entry point.

This module serves as the entry point for the MCP server.
All functionality is implemented in the modular architecture under src/ast_grep_mcp/.
"""
````

## File: src/ast_grep_mcp/features/deduplication/__init__.py
````python
"""
Deduplication feature module.

This module provides comprehensive code deduplication detection and refactoring
capabilities for the ast-grep MCP server.
"""
⋮----
# Core detection and analysis
⋮----
# Similarity calculation
⋮----
# MCP tool registration
⋮----
__all__ = [
⋮----
# Core classes
⋮----
# Similarity
⋮----
# Supporting classes
⋮----
# Enums/Constants
⋮----
# Standalone functions
⋮----
# Diff utilities
⋮----
# Registration
````

## File: src/ast_grep_mcp/features/documentation/tools.py
````python
"""MCP tool definitions for documentation generation features.

This module registers MCP tools for:
- generate_docstrings: Auto-generate docstrings/JSDoc
- generate_readme_sections: Generate README sections
- generate_api_docs: Generate API documentation
- generate_changelog: Generate changelog from git commits
- sync_documentation: Keep docs synchronized with code
"""
⋮----
# =============================================================================
# Tool Implementations
⋮----
"""
    Generate docstrings/JSDoc for undocumented functions.

    This tool analyzes function signatures and automatically generates documentation
    using intelligent name inference. It supports multiple languages and docstring styles.

    **Styles:**
    - `google`: Google-style docstrings (Python)
    - `numpy`: NumPy-style docstrings (Python)
    - `sphinx`: Sphinx/reStructuredText style (Python)
    - `jsdoc`: JSDoc format (JavaScript/TypeScript)
    - `javadoc`: Javadoc format (Java)
    - `auto`: Auto-detect from existing code

    **Features:**
    - Intelligent description inference from function names
    - Parameter descriptions from parameter names and types
    - Return value documentation from return types
    - Preserves existing docstrings (unless overwrite_existing=True)
    - Skips private functions by default

    Args:
        project_folder: Root folder of the project (absolute path)
        file_pattern: Glob pattern for files to process (e.g., "**/*.py", "src/**/*.ts")
        language: Programming language (python, typescript, javascript, java)
        style: Docstring style (google, numpy, sphinx, jsdoc, javadoc, auto)
        overwrite_existing: If True, replace existing docstrings
        dry_run: If True, only preview changes without applying
        skip_private: If True, skip private functions (starting with _)

    Returns:
        Dictionary containing:
        - summary: Statistics about generation
        - docstrings: List of generated docstrings with preview
        - files_modified: Files that were modified (if dry_run=False)

    Example usage:
        # Preview docstring generation
        result = generate_docstrings(
            project_folder="/path/to/project",
            file_pattern="**/*.py",
            language="python",
            style="google",
            dry_run=True
        )

        # Apply docstrings
        result = generate_docstrings(
            project_folder="/path/to/project",
            file_pattern="src/**/*.ts",
            language="typescript",
            style="jsdoc",
            dry_run=False
        )
    """
logger = get_logger("tool.generate_docstrings")
start_time = time.time()
⋮----
result = generate_docstrings_impl(
⋮----
execution_time = time.time() - start_time
⋮----
# Format response
⋮----
"""
    Generate README.md sections from code analysis.

    This tool analyzes your project structure, package files, and code to generate
    professional README sections including installation instructions, usage examples,
    API documentation, and more.

    **Sections:**
    - `installation`: Package manager install commands
    - `usage`: Basic usage examples with code
    - `features`: Feature list from code analysis
    - `api`: API reference table
    - `structure`: Project directory structure
    - `contributing`: Contributing guidelines
    - `license`: License section

    Args:
        project_folder: Root folder of the project (absolute path)
        language: Programming language (or 'auto' for detection)
        sections: Which sections to generate (['all'] for all sections)
        include_examples: Whether to include code examples

    Returns:
        Dictionary containing:
        - project_info: Detected project metadata
        - sections: List of generated sections
        - full_readme: Complete README markdown

    Example usage:
        # Generate all sections
        result = generate_readme_sections(
            project_folder="/path/to/project",
            language="auto",
            sections=["all"]
        )
        print(result["full_readme"])

        # Generate specific sections
        result = generate_readme_sections(
            project_folder="/path/to/project",
            language="python",
            sections=["installation", "usage", "api"]
        )
    """
logger = get_logger("tool.generate_readme_sections")
⋮----
sections = ["all"]
⋮----
result = generate_readme_sections_impl(
⋮----
def _format_route_for_output(route: ApiRoute) -> Dict[str, Any]
⋮----
"""Format a single route for API output.

    Args:
        route: ApiRoute object

    Returns:
        Dictionary with route details
    """
⋮----
"""
    Generate API documentation from route definitions.

    This tool parses your web framework route definitions and generates comprehensive
    API documentation in Markdown or OpenAPI format.

    **Supported Frameworks:**
    - Express (JavaScript/TypeScript)
    - FastAPI (Python)
    - Flask (Python)
    - Fastify (JavaScript/TypeScript)
    - Starlette (Python)

    **Output Formats:**
    - `markdown`: Human-readable Markdown documentation
    - `openapi`: OpenAPI 3.0 specification (JSON)
    - `both`: Both formats

    **Features:**
    - Automatic route path extraction
    - HTTP method detection
    - Path parameter parsing
    - Query/body parameter detection (where available)
    - Grouping by path prefix

    Args:
        project_folder: Root folder of the project (absolute path)
        language: Programming language (python, typescript, javascript)
        framework: Framework name (or None for auto-detection)
        output_format: Output format ('markdown', 'openapi', 'both')
        include_examples: Whether to include request/response examples

    Returns:
        Dictionary containing:
        - routes: List of parsed API routes
        - markdown: Generated Markdown documentation
        - openapi_spec: OpenAPI spec (if requested)
        - framework: Detected framework

    Example usage:
        # Generate Markdown API docs
        result = generate_api_docs(
            project_folder="/path/to/project",
            language="python",
            framework="fastapi",
            output_format="markdown"
        )
        print(result["markdown"])

        # Generate OpenAPI spec
        result = generate_api_docs(
            project_folder="/path/to/project",
            language="typescript",
            framework="express",
            output_format="openapi"
        )
        print(json.dumps(result["openapi_spec"], indent=2))
    """
logger = get_logger("tool.generate_api_docs")
⋮----
result = generate_api_docs_impl(
⋮----
"""
    Generate changelog from git commits.

    This tool parses git commits (preferably using conventional commit format)
    and generates a structured changelog grouped by change type.

    **Conventional Commit Format:**
    - `feat(scope): description` - New feature
    - `fix(scope): description` - Bug fix
    - `docs(scope): description` - Documentation
    - `refactor(scope): description` - Code refactoring
    - `BREAKING CHANGE:` in body - Breaking change

    **Changelog Formats:**
    - `keepachangelog`: Keep a Changelog format (https://keepachangelog.com)
    - `conventional`: Conventional Changelog format
    - `json`: Structured JSON output

    **Change Types:**
    - Added: New features
    - Changed: Changes to existing functionality
    - Deprecated: Soon-to-be removed features
    - Removed: Removed features
    - Fixed: Bug fixes
    - Security: Security fixes

    Args:
        project_folder: Root folder of the project (must be git repository)
        from_version: Starting version/tag (None = last tag or first commit)
        to_version: Ending version/tag (default: HEAD)
        changelog_format: Output format ('keepachangelog', 'conventional', 'json')
        group_by: Grouping strategy ('type', 'scope')

    Returns:
        Dictionary containing:
        - versions: List of version entries
        - markdown: Generated changelog markdown
        - commits_processed: Number of commits processed
        - commits_skipped: Commits without conventional format

    Example usage:
        # Generate changelog for unreleased changes
        result = generate_changelog(
            project_folder="/path/to/project",
            from_version=None,
            to_version="HEAD",
            changelog_format="keepachangelog"
        )
        print(result["markdown"])

        # Generate changelog between versions
        result = generate_changelog(
            project_folder="/path/to/project",
            from_version="1.0.0",
            to_version="2.0.0",
            changelog_format="conventional"
        )
    """
logger = get_logger("tool.generate_changelog")
⋮----
result = generate_changelog_impl(
⋮----
# Convert versions to serializable format
versions_data = []
⋮----
entries_data = {}
⋮----
"""
    Synchronize documentation with code.

    This tool checks that documentation is in sync with code:
    - Finds undocumented functions
    - Detects stale docstrings (parameters don't match signature)
    - Checks for broken links in markdown files
    - Suggests fixes for issues found

    **Check Types:**
    - `docstrings`: Check function documentation sync
    - `links`: Check markdown link validity
    - `all`: All checks

    **Issue Types:**
    - `undocumented`: Function has no docstring
    - `stale`: Docstring doesn't match function signature
    - `mismatch`: Parameter/return not documented
    - `broken_link`: Link target doesn't exist

    Args:
        project_folder: Root folder of the project (absolute path)
        language: Programming language (python, typescript, javascript, java)
        doc_types: Types of documentation to check (['all'] for all)
        check_only: If True, only report issues (no changes)

    Returns:
        Dictionary containing:
        - summary: Statistics about documentation status
        - issues: List of issues found
        - suggestions: Auto-fix suggestions

    Example usage:
        # Check all documentation
        result = sync_documentation(
            project_folder="/path/to/project",
            language="python",
            doc_types=["all"],
            check_only=True
        )

        # Check only docstrings
        result = sync_documentation(
            project_folder="/path/to/project",
            language="typescript",
            doc_types=["docstrings"]
        )

        print(f"Found {len(result['issues'])} issues")
        for issue in result['issues']:
            print(f"{issue['severity']}: {issue['description']}")
    """
logger = get_logger("tool.sync_documentation")
⋮----
doc_types = ["all"]
⋮----
result = sync_documentation_impl(
⋮----
# MCP Registration
⋮----
def _create_mcp_field_definitions() -> Dict[str, Dict[str, Any]]
⋮----
"""Create field definitions for MCP tool registration."""
⋮----
def register_documentation_tools(mcp: FastMCP) -> None
⋮----
"""Register all documentation feature tools with MCP server.

    Args:
        mcp: FastMCP server instance
    """
fields = _create_mcp_field_definitions()
⋮----
"""Generate docstrings/JSDoc for undocumented functions."""
⋮----
"""Generate README.md sections from code analysis."""
⋮----
"""Generate API documentation from route definitions."""
⋮----
"""Generate changelog from git commits."""
⋮----
"""Synchronize documentation with code."""
````

## File: src/ast_grep_mcp/models/condense.py
````python
"""Data models for code condensation feature."""
⋮----
@dataclass
class LanguageCondenseStats
⋮----
"""Per-language statistics from condensation."""
⋮----
language: str
files_processed: int
original_lines: int
condensed_lines: int
patterns_matched: int
original_bytes: int = 0
condensed_bytes: int = 0
⋮----
@dataclass
class CondenseResult
⋮----
"""Result of running the condense pipeline on a path."""
⋮----
strategy: str
⋮----
files_skipped: int
original_bytes: int
condensed_bytes: int
reduction_pct: float
original_tokens_est: int
condensed_tokens_est: int
normalizations_applied: int
dead_code_removed_lines: int
duplicates_collapsed: int
per_language_stats: Dict[str, LanguageCondenseStats] = field(default_factory=dict)
````

## File: src/ast_grep_mcp/server/registry.py
````python
"""Central tool registration for MCP server."""
⋮----
def register_all_tools(mcp: FastMCP) -> None
⋮----
"""Register all MCP tools from all features.

    This is the central registration point for all tools in the system.
    Tools are organized by feature and registered in order:
    1. Search (4 tools after consolidation)
    2. Rewrite (3 tools)
    3. Refactoring (2 tools: extract_function, rename_symbol)
    4. Deduplication (4 tools)
    5. Complexity (2 tools)
    6. Quality (4 tools - detect_smells, create_rule, list_templates, enforce_rules)
    7. Schema.org (8 tools)
    8. Documentation (5 tools - generate_docstrings, generate_readme_sections,
       generate_api_docs, generate_changelog, sync_documentation)
    9. Cross-Language (5 tools - search_multi_language, find_language_equivalents,
       convert_code_language, refactor_polyglot, generate_language_bindings)
    10. Condense (6 tools - condense_extract_surface, condense_normalize,
        condense_strip, condense_pack, condense_estimate, condense_train_dictionary)

    Total: 48 tools
    """
````

## File: src/ast_grep_mcp/features/cross_language/tools.py
````python
"""MCP tool definitions for cross-language operations features.

This module registers MCP tools for:
- search_multi_language: Search across multiple programming languages
- find_language_equivalents: Find equivalent patterns across languages
- convert_code_language: Convert code between languages
- refactor_polyglot: Refactor across language boundaries
- generate_language_bindings: Generate API client bindings
"""
⋮----
# =============================================================================
# Response Formatting Helpers
⋮----
def _format_example(ex: PatternExample) -> Dict[str, Any]
⋮----
"""Format a single pattern example."""
⋮----
def _format_equivalence(e: PatternEquivalence) -> Dict[str, Any]
⋮----
"""Format a single pattern equivalence."""
⋮----
def _format_equivalents_result(result: PatternEquivalenceResult) -> Dict[str, Any]
⋮----
"""Format find_language_equivalents result."""
⋮----
def _format_type_mapping(t: TypeMapping) -> Dict[str, str]
⋮----
"""Format a single type mapping."""
⋮----
def _format_warning(w: ConversionWarning) -> Dict[str, Any]
⋮----
"""Format a single conversion warning."""
⋮----
def _format_conversion(c: ConvertedCode) -> Dict[str, Any]
⋮----
"""Format a single code conversion."""
⋮----
def _format_conversion_result(result: ConversionResult) -> Dict[str, Any]
⋮----
"""Format convert_code_language result."""
⋮----
# Tool Implementations
⋮----
"""
    Search across multiple programming languages for semantically equivalent patterns.

    This tool enables polyglot search by finding similar code patterns across different
    programming languages simultaneously. It supports semantic grouping to cluster
    related results together.

    **Semantic Patterns:**
    - "async function" - Find async functions across languages
    - "try catch" - Find error handling patterns
    - "class" - Find class definitions
    - "function" - Find function definitions
    - "import" - Find import/require statements
    - "for loop" - Find iteration patterns

    **Supported Languages:**
    Python, TypeScript, JavaScript, Java, Kotlin, Go, Rust, C, C++, C#, Ruby, PHP, Swift

    Args:
        project_folder: Root folder of the project (absolute path)
        semantic_pattern: Semantic pattern to search for (e.g., "async function")
        languages: Languages to search (["auto"] for auto-detection)
        group_by: Grouping strategy ("semantic", "language", "file")
        max_results_per_language: Maximum results per language

    Returns:
        Dictionary containing:
        - query: The semantic query used
        - languages_searched: Languages that were searched
        - matches: List of matches with file, line, code
        - total_matches: Total number of matches
        - matches_by_language: Count per language
        - semantic_groups: Distinct semantic groups found

    Example usage:
        # Search for async functions across all languages
        result = search_multi_language(
            project_folder="/path/to/project",
            semantic_pattern="async function",
            languages=["auto"]
        )

        # Search specific languages
        result = search_multi_language(
            project_folder="/path/to/project",
            semantic_pattern="try catch",
            languages=["python", "typescript", "java"]
        )
    """
logger = get_logger("tool.search_multi_language")
start_time = time.time()
⋮----
languages = ["auto"]
⋮----
result = search_multi_language_impl(
⋮----
execution_time = time.time() - start_time
⋮----
"""
    Find equivalent patterns across programming languages.

    This tool provides a knowledge base of equivalent programming patterns
    across different languages. It helps developers understand how to
    express the same concept in different languages.

    **Pattern Categories:**
    - control_flow: if/else, switch, loops
    - functions: function definitions, lambdas, async
    - data_structures: lists, dictionaries, comprehensions
    - error_handling: try/catch, error propagation
    - async: async/await, promises
    - classes: class definitions, interfaces

    **Example Patterns:**
    - "list comprehension" - Array transformation patterns
    - "async await" - Asynchronous programming
    - "try catch" - Exception handling
    - "destructuring" - Value extraction
    - "arrow function" - Lambda expressions

    Args:
        pattern_description: Description of the pattern to find
        source_language: Optional source language to highlight
        target_languages: Languages to include in results

    Returns:
        Dictionary containing:
        - pattern_description: The input query
        - equivalences: List of pattern equivalences
        - suggestions: Related pattern suggestions

    Example usage:
        # Find list comprehension equivalents
        result = find_language_equivalents(
            pattern_description="list comprehension",
            target_languages=["python", "typescript", "java"]
        )

        # Find async patterns from Python perspective
        result = find_language_equivalents(
            pattern_description="async await",
            source_language="python",
            target_languages=["typescript", "javascript", "rust"]
        )
    """
logger = get_logger("tool.find_language_equivalents")
⋮----
result = find_language_equivalents_impl(
⋮----
"""
        Convert code from one programming language to another.

        This tool converts code snippets between supported language pairs,
        handling syntax transformation, type conversion, and idiomatic patterns.

        **Supported Conversions:**
        - Python <-> TypeScript
        - Python <-> JavaScript
        - JavaScript -> TypeScript
        - Java -> Kotlin

        **Conversion Styles:**
        - literal: Direct translation preserving structure
        - idiomatic: Use target language idioms and best practices
        - compatible: Maximum cross-platform compatibility

        **Features:**
        - Syntax transformation (control flow, functions, classes)
        - Type mapping (Python types -> TypeScript types)
        - Idiom conversion (list comprehensions -> map/filter)
        - Warnings for features that don't convert cleanly

        Args:
            code_snippet: Code to convert
            from_language: Source language
            to_language: Target language
            conversion_style: Conversion style (literal, idiomatic, compatible)
            include_comments: Whether to include conversion comments

        Returns:
            Dictionary containing:
            - conversions: List of converted code blocks
            - successful_conversions: Number of successful conversions
            - warnings: Any conversion warnings

        Example usage:
            # Convert Python to TypeScript
            result = convert_code_language(
                code_snippet=\"\"\"
    def calculate_total(items: List[float], tax_rate: float = 0.08) -> float:
        subtotal = sum(items)
        return subtotal * (1 + tax_rate)
    \"\"\",
                from_language="python",
                to_language="typescript",
                conversion_style="idiomatic"
            )

            # Convert JavaScript to Python
            result = convert_code_language(
                code_snippet=\"\"\"
    const fetchData = async (url) => {
        const response = await fetch(url);
        return response.json();
    };
    \"\"\",
                from_language="javascript",
                to_language="python"
            )
    """
logger = get_logger("tool.convert_code_language")
⋮----
result = convert_code_language_impl(
⋮----
"""
    Refactor across multiple programming languages atomically.

    This tool enables refactoring operations that span multiple languages,
    such as renaming an API endpoint that exists in both backend and frontend code.

    **Refactoring Types:**
    - rename_api: Rename API endpoint/symbol across all languages
    - extract_constant: Extract to shared configuration
    - update_contract: Update API contract signature

    **Features:**
    - Cross-language symbol tracking
    - Atomic multi-file changes
    - Risk analysis
    - Manual review identification
    - Validation before applying

    Args:
        project_folder: Root folder of the project
        refactoring_type: Type of refactoring (rename_api, extract_constant, update_contract)
        symbol_name: Symbol being refactored
        new_name: New name (required for rename operations)
        affected_languages: Languages to include (["all"] for all)
        dry_run: If True, only preview changes

    Returns:
        Dictionary containing:
        - plan: The refactoring plan
        - changes: List of changes (made or preview)
        - files_modified: Files that were modified
        - risks: Identified risks
        - requires_manual_review: Files needing manual review

    Example usage:
        # Preview renaming an API endpoint
        result = refactor_polyglot(
            project_folder="/path/to/project",
            refactoring_type="rename_api",
            symbol_name="getUserProfile",
            new_name="fetchUserProfile",
            dry_run=True
        )

        # Apply the rename
        result = refactor_polyglot(
            project_folder="/path/to/project",
            refactoring_type="rename_api",
            symbol_name="getUserProfile",
            new_name="fetchUserProfile",
            affected_languages=["python", "typescript"],
            dry_run=False
        )
    """
logger = get_logger("tool.refactor_polyglot")
⋮----
affected_languages = ["all"]
⋮----
result = refactor_polyglot_impl(
⋮----
"""
    Generate API client bindings for multiple languages from specifications.

    This tool parses API specifications (OpenAPI/Swagger) and generates
    client code in multiple programming languages.

    **Supported Input Formats:**
    - OpenAPI 3.0 (JSON or YAML)
    - Swagger 2.0 (JSON or YAML)

    **Supported Output Languages:**
    - Python (using requests)
    - TypeScript (using fetch)
    - JavaScript (using fetch)
    - Java (planned)
    - Go (planned)

    **Binding Styles:**
    - native: Use native language HTTP libraries
    - sdk: Full SDK with utilities and types
    - minimal: Minimal implementation

    **Generated Features:**
    - Type-safe method signatures
    - Request/response type definitions
    - Authentication handling
    - Error handling

    Args:
        api_definition_file: Path to API spec file (OpenAPI/Swagger)
        target_languages: Languages to generate bindings for
        binding_style: Binding style (native, sdk, minimal)
        include_types: Whether to include type definitions

    Returns:
        Dictionary containing:
        - api_name: Name of the API
        - api_version: API version
        - endpoints_count: Number of endpoints
        - bindings: Generated bindings per language
        - warnings: Generation warnings

    Example usage:
        # Generate Python and TypeScript clients
        result = generate_language_bindings(
            api_definition_file="/path/to/openapi.json",
            target_languages=["python", "typescript"],
            binding_style="native"
        )

        # Save generated code
        for binding in result["bindings"]:
            with open(binding["file_name"], "w") as f:
                f.write(binding["code"])
    """
logger = get_logger("tool.generate_language_bindings")
⋮----
target_languages = ["python", "typescript", "javascript"]
⋮----
result = generate_language_bindings_impl(
⋮----
# MCP Registration
⋮----
def _create_mcp_field_definitions() -> Dict[str, Dict[str, Any]]
⋮----
"""Create field definitions for MCP tool registration."""
⋮----
def register_cross_language_tools(mcp: FastMCP) -> None
⋮----
"""Register all cross-language feature tools with MCP server.

    Args:
        mcp: FastMCP server instance
    """
fields = _create_mcp_field_definitions()
⋮----
"""Search across multiple programming languages for semantically equivalent patterns."""
⋮----
"""Find equivalent patterns across programming languages."""
⋮----
"""Convert code from one programming language to another."""
⋮----
"""Refactor across multiple programming languages atomically."""
⋮----
"""Generate API client bindings for multiple languages from specifications."""
````

## File: src/ast_grep_mcp/features/search/tools.py
````python
"""Search feature MCP tool definitions."""
⋮----
def _register_dump_syntax_tree(mcp: FastMCP) -> None
⋮----
"""Register dump_syntax_tree tool."""
⋮----
"""
        Dump code's syntax structure or dump a query's pattern structure.
        This is useful to discover correct syntax kind and syntax tree structure. Call it when debugging a rule.
        The tool requires three arguments: code, language and format. The first two are self-explanatory.
        `format` is the output format of the syntax tree.
        use `format=cst` to inspect the code's concrete syntax tree structure, useful to debug target code.
        use `format=pattern` to inspect how ast-grep interprets a pattern, useful to debug pattern rule.

        Internally calls: ast-grep run --pattern <code> --lang <language> --debug-query=<format>
        """
⋮----
def _register_test_match_code_rule(mcp: FastMCP) -> None
⋮----
"""Register test_match_code_rule tool."""
⋮----
"""
        Test a code against an ast-grep YAML rule.
        This is useful to test a rule before using it in a project.

        Internally calls: ast-grep scan --inline-rules <yaml> --json --stdin
        """
⋮----
def _register_find_code(mcp: FastMCP) -> None
⋮----
"""Register find_code tool."""
⋮----
"""
        Find code in a project folder that matches the given ast-grep pattern.
        Pattern is good for simple and single-AST node result.
        For more complex usage, please use YAML by `find_code_by_rule`.

        Internally calls: ast-grep run --pattern <pattern> [--json] <project_folder>

        Output formats:
        - text (default): Compact text format with file:line-range headers and complete match text
          Example:
            Found 2 matches:

            path/to/file.py:10-15
            def example_function():
                # function body
                return result

            path/to/file.py:20-22
            def another_function():
                pass

        - json: Full match objects with metadata including ranges, meta-variables, etc.

        The max_results parameter limits the number of complete matches returned (not individual lines).
        When limited, the header shows "Found X matches (showing first Y of Z)".

        Example usage:
          find_code(pattern="class $NAME", max_results=20)  # Returns text format
          find_code(pattern="class $NAME", output_format="json")  # Returns JSON with metadata
        """
⋮----
output_format,  # type: ignore[arg-type]
⋮----
def _register_find_code_by_rule(mcp: FastMCP) -> None
⋮----
"""Register find_code_by_rule tool."""
⋮----
"""
        Find code in a project folder using a custom YAML rule.
        This is more powerful than find_code as it supports complex rules like:
        - any/all conditions
        - regex/inside/precedes/follows
        - multiple patterns in one rule
        - constraints and relations

        Internally calls: ast-grep scan --inline-rules <yaml> [--json] <project_folder>

        ⚠️  CRITICAL: The stopBy Parameter  ⚠️

        Relational rules (inside, has, follows, precedes) have a `stopBy` parameter:
        - `neighbor` (DEFAULT): Only checks immediate parent/sibling - often NOT what you want!
        - `end`: Searches to tree boundaries - usually what you need
        - Custom rule: Stops when surrounding nodes match

        COMMON MISTAKE - This often fails because it only checks immediate parent:
        ```yaml
        rule:
          pattern: $CALL
          inside:
            kind: function_declaration  # Missing stopBy: end!
        ```

        CORRECT - Add stopBy: end to search the entire tree:
        ```yaml
        rule:
          pattern: $CALL
          inside:
            stopBy: end  # Searches up the entire tree
            kind: function_declaration
        ```

        Minimal Rule Template:
        ```yaml
        id: my-rule
        language: python
        rule:
          pattern: |
            def $NAME($$$PARAMS):
              $$$BODY
        ```

        With Relational Rules:
        ```yaml
        id: my-rule
        language: python
        rule:
          pattern: $CALL
          inside:
            stopBy: end  # Don't forget this!
            kind: function_definition
        ```

        Composite Rules (all/any):
        - `all`: Matches a SINGLE node satisfying ALL sub-rules (not multiple nodes!)
        - `any`: Matches nodes satisfying ANY sub-rule

        ```yaml
        rule:
          any:
            - pattern: console.log($$$)
            - pattern: console.warn($$$)
            - pattern: console.error($$$)
        ```

        Output formats:
        - text (default): Compact text format with file:line-range headers and complete match text
        - json: Full match objects with metadata including ranges, rule ID, matched text etc.

        The max_results parameter limits the number of complete matches returned.

        Example usage:
          find_code_by_rule(project_folder="/path/to/project", yaml_rule=rule_str)
        """
⋮----
def _register_debug_pattern(mcp: FastMCP) -> None
⋮----
"""Register debug_pattern tool."""
⋮----
"""
        Debug why a pattern doesn't match code.

        This tool provides comprehensive analysis when a pattern fails to match:

        **What it checks:**
        1. **Metavariable validation**: Detects invalid syntax like $name (must be $NAME),
           $123 (can't start with digit), $KEBAB-CASE (no hyphens allowed)
        2. **AST comparison**: Compares the pattern's AST with the code's AST to find
           structural mismatches
        3. **Match attempt**: Actually tries to match and reports results
        4. **Best practices**: Warns about common issues like using $ARG instead of $$$ARGS
           for multiple function arguments

        **Metavariable Quick Reference:**
        | Syntax     | Meaning                          | Example                    |
        |------------|----------------------------------|----------------------------|
        | `$NAME`    | Match single AST node (UPPERCASE)| `function $NAME()`         |
        | `$$$ARGS`  | Match zero or more nodes         | `foo($$$ARGS)`             |
        | `$_NAME`   | Non-capturing (performance)      | `$_FUNC($_ARG)`            |
        | `$$VAR`    | Match unnamed nodes (advanced)   | For tree-sitter internals  |

        **Valid metavariable names:** `$META`, `$META_VAR`, `$META_VAR1`, `$_`, `$_123`
        **Invalid:** `$name` (lowercase), `$123` (digit start), `$KEBAB-CASE` (hyphens)

        **Common Mistakes Detected:**
        - `$name` → Should be `$NAME` (uppercase required)
        - `$123` → Can't start with digit
        - `$KEBAB-CASE` → No hyphens allowed
        - `console.log($GREETING)` → May need `$$$ARGS` for multiple arguments
        - Incomplete code fragments that aren't valid syntax

        **Output includes:**
        - `pattern_valid`: Whether pattern parses correctly
        - `pattern_ast`: How ast-grep interpreted the pattern
        - `code_ast`: How ast-grep parsed the code
        - `ast_comparison`: Side-by-side comparison with differences
        - `metavariables`: All metavars found with validation status
        - `issues`: List of problems found (errors, warnings, tips)
        - `suggestions`: Prioritized list of fixes
        - `match_attempt`: Whether matching succeeded

        **Example usage:**
        ```python
        # Debug why a pattern doesn't match
        result = debug_pattern(
            pattern="console.log($message)",  # Invalid! $message should be $MESSAGE
            code="console.log('hello')",
            language="javascript"
        )
        # Result will show:
        # - issues: [{"severity": "error", "message": "Metavariable must use UPPERCASE..."}]
        # - suggestions: ["[ERROR] Use uppercase letters: $MESSAGE"]
        ```

        **When to use:**
        - Pattern returns no matches when you expect matches
        - You're unsure if your metavariable syntax is correct
        - You want to understand how ast-grep parses your pattern vs code
        - You're learning ast-grep pattern syntax
        """
result = debug_pattern_impl(pattern, code, language)
⋮----
def _register_get_ast_grep_docs(mcp: FastMCP) -> None
⋮----
"""Register get_ast_grep_docs tool."""
⋮----
"""
        Get ast-grep documentation for the specified topic.

        Use this tool when you need guidance on:
        - Pattern syntax and metavariables
        - YAML rule configuration
        - Relational rules (inside, has, follows, precedes)
        - Strictness modes for matching
        - Best practices and workflows

        This provides accurate, up-to-date documentation to help you write
        correct patterns and rules, reducing trial-and-error.

        **Available Topics:**

        - `pattern`: Pattern syntax, metavariables ($NAME, $$$ARGS), matching rules,
          common patterns by language

        - `rules`: YAML rule structure, required fields (id, language, rule),
          optional fields (message, severity, fix), stopBy configuration

        - `relational`: inside/has/follows/precedes rules, the critical stopBy
          parameter, combining relational rules, common patterns

        - `metavariables`: Complete reference for $NAME, $$$, $_NAME, $$VAR,
          valid/invalid naming, common mistakes

        - `strictness`: Pattern matching modes (cst, smart, ast, relaxed, signature),
          when to use each, behavior differences, best practices

        - `workflow`: Recommended development workflow, tool selection guide,
          troubleshooting checklist

        - `all`: Complete documentation (all topics combined)

        **Example Usage:**
        ```
        # Get help with pattern syntax
        get_ast_grep_docs(topic="pattern")

        # Understand relational rules and stopBy
        get_ast_grep_docs(topic="relational")

        # Get the complete reference
        get_ast_grep_docs(topic="all")
        ```

        **When to Use:**
        - Before writing a complex pattern or rule
        - When a pattern doesn't match as expected
        - To understand metavariable syntax
        - To learn about relational rules and stopBy
        - As a reference while iterating on rules
        """
⋮----
def _register_build_rule(mcp: FastMCP) -> None
⋮----
"""Register build_rule tool."""
⋮----
"""
        Build a properly structured YAML rule from components.

        This tool helps you construct valid ast-grep YAML rules without worrying
        about syntax details. It automatically:
        - Adds all required fields (id, language, rule)
        - Sets `stopBy: end` on relational rules (preventing the #1 mistake!)
        - Formats YAML correctly

        **Why Use This Tool?**
        Building YAML rules by hand is error-prone. Common mistakes include:
        - Forgetting `stopBy: end` (causes rules to not match)
        - Missing required fields
        - YAML formatting issues

        This tool eliminates these issues by construction.

        **Relational Rules:**
        - `inside`: Match must be INSIDE this pattern (e.g., inside a function)
        - `has`: Match must CONTAIN this pattern (e.g., has a return statement)
        - `follows`: Match must come AFTER this pattern
        - `precedes`: Match must come BEFORE this pattern

        Use `inside_kind` or `has_kind` for node-type matching instead of patterns.

        **Examples:**

        1. Find console.log inside functions:
        ```
        build_rule(
            pattern="console.log($$$ARGS)",
            language="javascript",
            inside_kind="function_declaration"
        )
        ```

        2. Find functions that have return statements:
        ```
        build_rule(
            pattern="function $NAME($$$) { $$$BODY }",
            language="javascript",
            has="return $VALUE"
        )
        ```

        3. Find variable usage after declaration:
        ```
        build_rule(
            pattern="$VAR",
            language="javascript",
            follows="const $VAR = $VALUE"
        )
        ```

        4. Find and fix console.log calls:
        ```
        build_rule(
            pattern="console.log($$$ARGS)",
            language="javascript",
            message="Remove console.log before production",
            severity="warning",
            fix=""  # Empty string = delete the match
        )
        ```

        **Output:**
        Returns a YAML string ready to use with `find_code_by_rule` or
        `test_match_code_rule`.
        """
⋮----
def _register_get_pattern_examples(mcp: FastMCP) -> None
⋮----
"""Register get_pattern_examples tool."""
⋮----
"""
        Get common ast-grep pattern examples for a language.

        Returns ready-to-use patterns organized by category with descriptions.
        Use these as starting points for your searches - patterns are verified
        to work with ast-grep and follow best practices.

        **Categories:**

        - `function`: Function declarations, arrow functions, methods, lambdas
        - `class`: Class definitions, inheritance, constructors, interfaces
        - `import`: Import/require statements, module imports
        - `variable`: Variable declarations, destructuring, type annotations
        - `control_flow`: If/else, loops, switch, ternary expressions
        - `error_handling`: Try/catch, throw, error patterns
        - `async`: Async/await, promises, goroutines, threads

        **Supported Languages:**

        JavaScript, TypeScript, Python, Go, Rust, Java, Ruby, C, C++

        **Example Usage:**

        ```
        # Get all JavaScript patterns
        get_pattern_examples(language="javascript")

        # Get only function patterns for Python
        get_pattern_examples(language="python", category="function")

        # Get error handling patterns for Go
        get_pattern_examples(language="go", category="error_handling")
        ```

        **Output Format:**

        Each pattern includes:
        - Description of what it matches
        - The pattern itself (ready to use with find_code)
        - Optional notes about usage

        **Tips:**

        1. Start with these patterns and customize for your needs
        2. Use $$$PARAMS for function parameters (matches 0+ args)
        3. Use $NAME for single captures, $$$ARGS for multiple
        4. Combine with YAML rules for more complex matching
        """
⋮----
def _register_develop_pattern(mcp: FastMCP) -> None
⋮----
"""Register develop_pattern tool."""
⋮----
"""
        Interactive pattern development assistant.

        This tool helps you develop ast-grep patterns by analyzing your sample code
        and suggesting patterns that will match it. It's the recommended starting
        point when you're not sure how to write a pattern.

        **How It Works:**

        1. **Analyzes your code**: Examines the AST structure, identifies node kinds,
           extracts identifiers and literals

        2. **Suggests patterns**: Generates multiple pattern options:
           - Exact match: The code itself as a pattern
           - Generalized: With metavariables ($NAME) for flexibility
           - Structural: Using node kinds for YAML rules

        3. **Tests patterns**: Verifies if suggested patterns actually match

        4. **Provides guidance**: Gives you next steps and refinement suggestions

        **When to Use:**

        - You have sample code and want to find similar patterns
        - You're new to ast-grep and don't know the pattern syntax
        - You want to quickly bootstrap a pattern without trial-and-error
        - You need to understand the AST structure of your code

        **Example:**

        ```python
        # You want to find all console.log calls
        result = develop_pattern(
            code="console.log('hello')",
            language="javascript",
            goal="Find all console.log calls"
        )

        # Result includes:
        # - code_analysis: root_kind, identifiers, complexity
        # - suggested_patterns: exact, generalized ($ARG), structural
        # - best_pattern: The recommended pattern to use
        # - pattern_matches: True/False - does it work?
        # - yaml_rule_template: Ready-to-use YAML rule
        # - next_steps: What to do next
        ```

        **Output Fields:**

        - `code_analysis`: AST structure analysis
          - `root_kind`: The AST node type (e.g., "call_expression")
          - `identifiers`: Variables and function names found
          - `literals`: String and number literals found
          - `complexity`: "simple", "medium", or "complex"
          - `ast_preview`: First lines of the AST

        - `suggested_patterns`: List of patterns with:
          - `pattern`: The pattern string
          - `description`: What it matches
          - `type`: "exact", "generalized", or "structural"
          - `confidence`: How likely to work (0-1)

        - `best_pattern`: The recommended pattern to start with

        - `pattern_matches`: Whether best_pattern matches the code

        - `yaml_rule_template`: Complete YAML rule ready for find_code_by_rule

        - `next_steps`: Guidance on what to do next

        - `refinement_steps`: If pattern doesn't match, how to fix it

        **Workflow Integration:**

        1. Start here with develop_pattern() to get a working pattern
        2. Use find_code() to search your project
        3. Use build_rule() to add constraints (inside, has)
        4. Use debug_pattern() if matches aren't working
        5. Use test_match_code_rule() to verify edge cases
        """
result = develop_pattern_impl(code, language, goal)
⋮----
def register_search_tools(mcp: FastMCP) -> None
⋮----
"""Register search-related MCP tools.

    Args:
        mcp: FastMCP instance to register tools with
    """
````

## File: pyproject.toml
````toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ast-grep-mcp"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "pydantic>=2.11.0",
    "mcp[cli]>=1.6.0",
    "pyyaml>=6.0.2",
    "structlog>=24.1.0",
    "httpx>=0.28.0",
    "sentry-sdk[anthropic]>=2.0.0",
    "datasketch>=1.6.0", # MinHash + LSH for O(n) similarity detection
    "pillow>=12.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=5.0.0",
    "pytest-mock>=3.14.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.7.0",
    "mypy>=1.13.0",
    "types-pyyaml>=6.0.12.20250809",
]

# Phase 5: CodeBERT semantic similarity (optional)
# Enables Type-4 (semantic) clone detection using transformer embeddings
# Note: Requires ~400MB model download on first use
semantic = [
    "transformers>=4.35.0",
    "torch>=2.0.0",
]

# All optional features
all = [
    "transformers>=4.35.0",
    "torch>=2.0.0",
]

[project.scripts]
ast-grep-server = "main:run_mcp_server"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v"
asyncio_mode = "auto"
markers = [
    "unit: Unit tests (fast, mocked dependencies)",
    "integration: Integration tests (requires ast-grep binary)",
    "slow: Slow tests that may take longer to run",
    "semantic: Tests requiring transformers and torch (Phase 5 CodeBERT)",
]

[tool.coverage.run]
source = ["main"]
omit = ["tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "if __name__ == .__main__.:",
    "raise NotImplementedError",
    "pass",
    "except ImportError:",
    "@mcp.tool\\(\\)",
]

[tool.ruff]
line-length = 140
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
ignore = ["N806"]  # Non-lowercase variable in function - intentional for config patterns

[tool.ruff.lint.per-file-ignores]
"src/ast_grep_mcp/features/cross_language/pattern_database.py" = ["E501"]  # Long template strings

[tool.mypy]
python_version = "3.13"
strict = true
warn_return_any = true
warn_unused_configs = true
ignore_missing_imports = true
mypy_path = "$MYPY_CONFIG_FILE_DIR/src"
namespace_packages = false
exclude = [
    "^tests/",
    "^scripts/",
    "^dev/",
    "^analyze_codebase\\.py$",
]

[[tool.mypy.overrides]]
module = "ast_grep_mcp.*"
ignore_missing_imports = false

[[tool.mypy.overrides]]
module = "yaml"
ignore_missing_imports = true

[dependency-groups]
dev = [
    "mypy>=1.17.1",
    "pytest>=8.4.1",
    "pytest-asyncio>=1.3.0",
    "types-pyyaml>=6.0.12.20250809",
]
````

## File: src/ast_grep_mcp/core/executor.py
````python
"""Command execution and ast-grep interface for ast-grep MCP server."""
⋮----
def get_supported_languages() -> List[str]
⋮----
"""Get all supported languages as a field description string."""
languages = [  # https://ast-grep.github.io/reference/languages.html
⋮----
# Check for custom languages in config file
# https://ast-grep.github.io/advanced/custom-language.html#register-language-in-sgconfig-yml
⋮----
config = yaml.safe_load(f)
⋮----
custom_langs = list(config["customLanguages"].keys())
⋮----
def run_command(args: List[str], input_text: Optional[str] = None, *, allow_nonzero: bool = False) -> subprocess.CompletedProcess[str]
⋮----
"""Execute a command with proper error handling.

    Args:
        args: Command arguments list
        input_text: Optional stdin input
        allow_nonzero: If True, don't raise on non-zero exit codes

    Returns:
        CompletedProcess instance

    Raises:
        AstGrepNotFoundError: If command binary not found
        AstGrepExecutionError: If command execution fails (unless allow_nonzero)
    """
logger = get_logger("subprocess")
start_time = time.time()
⋮----
# Sanitize command for logging (don't log code content)
sanitized_args = args.copy()
has_stdin = input_text is not None
⋮----
# On Windows, if ast-grep is installed via npm, it's a batch file
# that requires shell=True to execute properly
use_shell = sys.platform == "win32" and args[0] == "ast-grep"
⋮----
result = subprocess.run(
⋮----
execution_time = time.time() - start_time
⋮----
stderr_msg = e.stderr.strip() if e.stderr else ""
⋮----
stderr=stderr_msg[: DisplayDefaults.ERROR_OUTPUT_PREVIEW_LENGTH],  # Truncate stderr in logs
⋮----
error = AstGrepExecutionError(command=args, returncode=e.returncode, stderr=stderr_msg)
⋮----
not_found_error = AstGrepNotFoundError()
⋮----
not_found_error = AstGrepNotFoundError(f"Command '{args[0]}' not found")
⋮----
def _get_language_extensions(language: str) -> Optional[List[str]]
⋮----
"""Get file extensions for a language.

    Args:
        language: Programming language name

    Returns:
        List of extensions or None if language not found
    """
lang_map = {
⋮----
def _should_skip_directory(dirname: str) -> bool
⋮----
"""Check if directory should be skipped.

    Args:
        dirname: Directory name

    Returns:
        True if should skip, False otherwise
    """
⋮----
"""Process a single file for size filtering.

    Args:
        file: File name
        root: Root directory path
        lang_extensions: Language-specific extensions
        max_size_bytes: Maximum size in bytes
        logger: Logger instance

    Returns:
        Tuple of (file_to_search, skipped_file) - only one will be non-None
    """
# Skip hidden files
⋮----
# Check language filter
⋮----
file_path = os.path.join(root, file)
⋮----
file_size = os.path.getsize(file_path)
⋮----
def filter_files_by_size(directory: str, max_size_mb: Optional[int] = None, language: Optional[str] = None) -> Tuple[List[str], List[str]]
⋮----
"""Filter files in directory by size.

    Args:
        directory: Directory to search
        max_size_mb: Maximum file size in megabytes (None = unlimited)
        language: Optional language filter for file extensions

    Returns:
        Tuple of (files_to_search, skipped_files)
        - files_to_search: List of file paths under size limit
        - skipped_files: List of file paths that were skipped
    """
logger = get_logger("file_filter")
⋮----
# No filtering needed
⋮----
max_size_bytes = max_size_mb * FileConstants.BYTES_PER_MB
files_to_search: List[str] = []
skipped_files: List[str] = []
⋮----
# Get language extensions if specified
lang_extensions = _get_language_extensions(language) if language else None
⋮----
# Walk directory and check file sizes
⋮----
# Filter directories in-place
⋮----
def run_ast_grep(command: str, args: List[str], input_text: Optional[str] = None) -> subprocess.CompletedProcess[str]
⋮----
"""Execute ast-grep command with optional config.

    Args:
        command: ast-grep subcommand (run, scan, etc.)
        args: Command arguments
        input_text: Optional stdin input

    Returns:
        CompletedProcess instance
    """
⋮----
args = ["--config", CONFIG_PATH] + args
# --debug-query outputs to stderr and returns exit code 1 even on success
allow_nonzero = any(arg.startswith("--debug-query") for arg in args)
⋮----
def _prepare_stream_command(command: str, args: List[str]) -> List[str]
⋮----
"""Prepare the full ast-grep command with optional config.

    Args:
        command: ast-grep subcommand
        args: Command arguments

    Returns:
        Full command list
    """
final_args = args.copy()
⋮----
final_args = ["--config", CONFIG_PATH] + final_args
⋮----
def _create_stream_process(full_command: List[str]) -> subprocess.Popen[str]
⋮----
"""Create and start the subprocess for streaming.

    Args:
        full_command: Complete command list

    Returns:
        Started Popen process

    Raises:
        FileNotFoundError: If command not found
    """
use_shell = sys.platform == "win32" and full_command[0] == "ast-grep"
⋮----
def _parse_json_line(line: str, logger: Any) -> Optional[Dict[str, Any]]
⋮----
"""Parse a line of JSON output.

    Args:
        line: Line to parse
        logger: Logger instance

    Returns:
        Parsed JSON dict or None if invalid
    """
line = line.strip()
⋮----
def _should_log_progress(match_count: int, last_progress_log: int, progress_interval: int) -> bool
⋮----
"""Check if progress should be logged.

    Args:
        match_count: Current match count
        last_progress_log: Last logged count
        progress_interval: Interval for logging

    Returns:
        True if should log progress
    """
⋮----
def _terminate_process(process: subprocess.Popen[str], logger: Any, reason: str) -> None
⋮----
"""Terminate a process gracefully, then forcefully if needed.

    Args:
        process: Process to terminate
        logger: Logger instance
        reason: Reason for termination
    """
⋮----
"""Handle non-zero return codes from the process.

    Args:
        returncode: Process return code
        process: Process instance
        full_command: Command that was run
        start_time: Start time for execution
        match_count: Number of matches found
        logger: Logger instance

    Raises:
        AstGrepExecutionError: If process failed
    """
# SIGTERM from early termination is not an error
⋮----
stderr_output = process.stderr.read() if process.stderr else ""
⋮----
# Exit code 1 means "scan succeeded, found error-level diagnostics" or
# "no matches found" — neither is an execution error.
⋮----
error = AstGrepExecutionError(command=full_command, returncode=returncode, stderr=stderr_output)
⋮----
def _cleanup_process(process: Optional[subprocess.Popen[str]]) -> None
⋮----
"""Ensure subprocess is properly cleaned up.

    Args:
        process: Process to cleanup (may be None)
    """
⋮----
"""Stream ast-grep JSON results line-by-line with early termination support.

    This function uses subprocess.Popen to read ast-grep output incrementally,
    parsing each JSON object as it arrives. This approach:
    - Reduces memory usage for large result sets
    - Enables early termination when max_results is reached
    - Provides progress logging during long searches

    Args:
        command: ast-grep subcommand (run, scan, etc.)
        args: Command arguments (must include --json=stream flag)
        max_results: Maximum results to yield (0 = unlimited)
        progress_interval: Log progress every N matches

    Yields:
        Individual match dictionaries from ast-grep JSON output

    Raises:
        AstGrepNotFoundError: If ast-grep binary not found
        AstGrepExecutionError: If ast-grep execution fails
    """
logger = get_logger("stream_results")
⋮----
# Prepare command
full_command = _prepare_stream_command(command, args)
⋮----
process = None
match_count = 0
last_progress_log = 0
⋮----
# Start subprocess
process = _create_stream_process(full_command)
⋮----
# Process output lines
⋮----
# Parse JSON from line
match = _parse_json_line(line, logger)
⋮----
# Log progress if needed
⋮----
last_progress_log = match_count
⋮----
# Check for early termination
⋮----
# Wait for process completion
returncode = process.wait()
⋮----
# Handle any errors
⋮----
# Log completion
⋮----
not_found_error = AstGrepNotFoundError(f"Command '{full_command[0]}' not found")
````

## File: src/ast_grep_mcp/features/schema/tools.py
````python
"""Schema.org feature MCP tool definitions."""
⋮----
async def get_schema_type_tool(type_name: str) -> Dict[str, Any]
⋮----
"""
    Get detailed information about a schema.org type.
    Returns the type's name, description, URL, parent types, and metadata.

    Args:
        type_name: The schema.org type name (e.g., 'Person', 'Organization', 'Article')

    Returns:
        Dictionary with type details including properties and parent types

    Example:
        get_schema_type_tool('Person') returns details about the Person type
    """
logger = get_logger("tool.get_schema_type")
start_time = time.time()
⋮----
client = get_schema_org_client()
result = await client.get_schema_type(type_name)
⋮----
execution_time = time.time() - start_time
⋮----
async def search_schemas_tool(query: str, limit: int = 10) -> List[Dict[str, Any]]
⋮----
"""
    Search for schema.org types by keyword.
    Searches through type names and descriptions, returns matching types sorted by relevance.

    Args:
        query: Search query to find schema types
        limit: Maximum number of results to return (1-100)

    Returns:
        List of matching schema types

    Example:
        search_schemas_tool('blog') finds types like BlogPosting, Blog, etc.
    """
logger = get_logger("tool.search_schemas")
⋮----
results = await client.search_schemas(query, limit)
⋮----
async def get_type_hierarchy_tool(type_name: str) -> Dict[str, Any]
⋮----
"""
    Get the inheritance hierarchy for a schema.org type.
    Returns the type's parent types (super types) and child types (sub types).

    Args:
        type_name: The schema.org type name

    Returns:
        Dictionary with parent and child type information

    Example:
        get_type_hierarchy_tool('NewsArticle') shows inheritance from Article, CreativeWork, etc.
    """
logger = get_logger("tool.get_type_hierarchy")
⋮----
result = await client.get_type_hierarchy(type_name)
⋮----
async def get_type_properties_tool(type_name: str, include_inherited: bool = True) -> List[Dict[str, Any]]
⋮----
"""
    Get all properties available for a schema.org type.
    Returns property names, descriptions, and expected value types.

    Args:
        type_name: The schema.org type name
        include_inherited: Include properties inherited from parent types

    Returns:
        List of property definitions

    Example:
        get_type_properties_tool('Organization') returns properties like name, url, address, etc.
    """
logger = get_logger("tool.get_type_properties")
⋮----
results = await client.get_type_properties(type_name, include_inherited)
⋮----
async def generate_schema_example_tool(type_name: str, custom_properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]
⋮----
"""
    Generate an example JSON-LD structured data for a schema.org type.
    Creates a valid schema.org JSON-LD object with common properties and any custom values provided.

    Args:
        type_name: The schema.org type name
        custom_properties: Custom property values to include in the example

    Returns:
        Dictionary containing JSON-LD example

    Example:
        generate_schema_example_tool('Recipe', {'name': 'Chocolate Cake', 'prepTime': 'PT30M'})
    """
logger = get_logger("tool.generate_schema_example")
⋮----
result = await client.generate_example(type_name, custom_properties)
⋮----
def generate_entity_id_tool(base_url: str, entity_type: str, entity_slug: Optional[str] = None) -> str
⋮----
"""
    Generate a proper @id value following Schema.org and SEO best practices.

    Creates stable, unique identifiers for entities that can be referenced across your knowledge graph.
    Based on best practices from https://momenticmarketing.com/blog/id-schema-for-seo-llms-knowledge-graphs

    Args:
        base_url: The canonical URL (e.g., 'https://example.com')
        entity_type: The Schema.org type (e.g., 'Organization', 'Person')
        entity_slug: Optional URL slug for specific entity instances

    Returns:
        Generated @id string

    Examples:
        - generate_entity_id_tool('https://example.com', 'Organization')
          → 'https://example.com/#organization'
        - generate_entity_id_tool('https://example.com', 'Product', 'products/widget-a')
          → 'https://example.com/products/widget-a#product'
    """
logger = get_logger("tool.generate_entity_id")
⋮----
result = client.generate_entity_id(base_url, entity_type, entity_slug)
⋮----
def validate_entity_id_tool(entity_id: str) -> Dict[str, Any]
⋮----
"""
    Validate an @id value against Schema.org and SEO best practices.

    Checks for common issues and provides actionable suggestions for improvement.
    Based on best practices from https://momenticmarketing.com/blog/id-schema-for-seo-llms-knowledge-graphs

    Args:
        entity_id: The @id value to validate

    Returns:
        Dictionary with validation results:
        - valid: Whether the @id follows all best practices
        - warnings: List of issues found
        - suggestions: Specific improvements to make
        - best_practices: Key principles to follow

    Example:
        validate_entity_id_tool('https://example.com/#organization')
        → { "valid": true, "warnings": [], "suggestions": [] }
    """
logger = get_logger("tool.validate_entity_id")
⋮----
result = client.validate_entity_id(entity_id)
⋮----
async def build_entity_graph_tool(entities: List[Dict[str, Any]], base_url: str) -> Dict[str, Any]
⋮----
"""
    Build a knowledge graph of related entities with proper @id references.

    Creates a complete @graph structure where entities can reference each other using @id,
    enabling you to build a relational knowledge base over time.
    Based on best practices from https://momenticmarketing.com/blog/id-schema-for-seo-llms-knowledge-graphs

    Args:
        entities: List of entity definitions with type, properties, and relationships
        base_url: Base canonical URL for generating @id values

    Returns:
        Complete JSON-LD @graph with all entities properly connected via @id references

    Entity Definition Format:
        {
            "type": "Organization",           # Required: Schema.org type
            "slug": "about",                  # Optional: URL path segment
            "id_fragment": "org-acme",        # Optional: Custom fragment for referencing
            "properties": {                   # Required: Entity properties
                "name": "Acme Corp",
                "url": "https://example.com"
            },
            "relationships": {                # Optional: References to other entities
                "founder": "person-john"      # References id_fragment of another entity
            }
        }
    """
logger = get_logger("tool.build_entity_graph")
⋮----
result = await client.build_entity_graph(entities, base_url)
⋮----
async def enhance_entity_graph_tool(input_source: str, input_type: str = "file", output_mode: str = "analysis") -> Dict[str, Any]
⋮----
"""
    Analyze existing Schema.org JSON-LD graphs and suggest enhancements.

    Examines JSON-LD structured data and provides recommendations based on:
    - Schema.org vocabulary standards
    - Google Rich Results guidelines
    - SEO best practices

    Args:
        input_source: File path or directory path containing JSON-LD Schema.org markup
        input_type: Input source type: 'file' for single file, 'directory' for scanning all .json files
        output_mode: Output mode: 'analysis' for enhancement suggestions, 'enhanced' for complete graph, 'diff' for additions only

    Returns:
        Entity-level analysis with:
        - Missing property suggestions with priorities (critical/high/medium)
        - Missing entity type suggestions (FAQPage, BreadcrumbList, etc.)
        - SEO completeness scores (0-100)
        - Validation issues (broken @id references)
        - Example values for all suggestions

    Output Modes:
        - analysis: Detailed suggestions with priorities and examples
        - enhanced: Complete graph with all suggestions applied (placeholder values)
        - diff: Only the additions needed (for merging with existing markup)
    """
logger = get_logger("tool.enhance_entity_graph")
⋮----
result = await analyze_entity_graph(input_source=input_source, input_type=input_type, output_mode=output_mode)
⋮----
def register_schema_tools(mcp: FastMCP) -> None
⋮----
"""Register Schema.org-related MCP tools.

    Args:
        mcp: FastMCP instance to register tools with
    """
⋮----
"""Wrapper that calls the standalone get_schema_type_tool function."""
⋮----
"""Wrapper that calls the standalone search_schemas_tool function."""
⋮----
@mcp.tool()
    async def get_type_hierarchy(type_name: str = Field(description="The schema.org type name")) -> Dict[str, Any]
⋮----
"""Wrapper that calls the standalone get_type_hierarchy_tool function."""
⋮----
"""Wrapper that calls the standalone get_type_properties_tool function."""
⋮----
"""Wrapper that calls the standalone generate_schema_example_tool function."""
⋮----
"""Wrapper that calls the standalone generate_entity_id_tool function."""
⋮----
"""Wrapper that calls the standalone validate_entity_id_tool function."""
⋮----
"""Wrapper that calls the standalone build_entity_graph_tool function."""
⋮----
"""Wrapper that calls the standalone enhance_entity_graph_tool function."""
````

## File: src/ast_grep_mcp/core/usage_tracking.py
````python
"""
API/Tool Usage Tracking and Cost Monitoring.

This module provides comprehensive tracking for MCP tool executions including:
- Execution counts and timing
- Operation cost estimation
- Success/failure rates
- Performance metrics
- Usage alerts and thresholds

Storage: SQLite database for lightweight, file-based persistence.
"""
⋮----
logger = get_logger("usage_tracking")
⋮----
# =============================================================================
# Pricing Configuration
⋮----
class OperationType(str, Enum)
⋮----
"""Types of operations tracked for cost estimation."""
⋮----
# Search operations
SEARCH_CODE = "search_code"
FIND_DUPLICATION = "find_duplication"
SIMILARITY_CALCULATION = "similarity_calculation"
⋮----
# Analysis operations
ANALYZE_COMPLEXITY = "analyze_complexity"
DETECT_CODE_SMELLS = "detect_code_smells"
SECURITY_SCAN = "security_scan"
⋮----
# Refactoring operations
RENAME_SYMBOL = "rename_symbol"
EXTRACT_FUNCTION = "extract_function"
APPLY_REWRITE = "apply_rewrite"
⋮----
# Documentation operations
GENERATE_DOCS = "generate_docs"
SYNC_CHECK = "sync_check"
⋮----
# Schema operations
VALIDATE_SCHEMA = "validate_schema"
ENHANCE_SCHEMA = "enhance_schema"
⋮----
# Generic
UNKNOWN = "unknown"
⋮----
@dataclass
class OperationPricing
⋮----
"""Cost estimation for an operation type.

    Costs are in "compute units" - abstract units representing
    computational effort. Can be mapped to actual costs if needed.
    """
⋮----
base_cost: float  # Base cost per operation
per_file_cost: float = 0.0  # Additional cost per file processed
per_line_cost: float = 0.0  # Additional cost per line analyzed
per_match_cost: float = 0.0  # Additional cost per match found
⋮----
# Operation pricing table (compute units)
# Calibrated based on typical execution times and resource usage
OPERATION_PRICING: Dict[OperationType, OperationPricing] = {
⋮----
# Search operations (relatively cheap)
⋮----
# Analysis operations (moderate cost)
⋮----
# Refactoring operations (higher cost - modifies files)
⋮----
# Unknown/generic
⋮----
"""Calculate the estimated cost for an operation.

    Args:
        operation: Type of operation performed
        files_processed: Number of files processed
        lines_analyzed: Number of lines analyzed
        matches_found: Number of matches/results found

    Returns:
        Estimated cost in compute units
    """
pricing = OPERATION_PRICING.get(operation, OPERATION_PRICING[OperationType.UNKNOWN])
⋮----
cost = pricing.base_cost
⋮----
# Pydantic Models
⋮----
class UsageLogEntry(BaseModel)
⋮----
"""A single usage log entry."""
⋮----
id: str = Field(
timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
tool_name: str
operation_type: OperationType = OperationType.UNKNOWN
success: bool = True
error_message: Optional[str] = None
response_time_ms: int = 0
estimated_cost: float = 0.0
files_processed: int = 0
lines_analyzed: int = 0
matches_found: int = 0
metadata: Dict[str, Any] = Field(default_factory=dict)
⋮----
class UsageStats(BaseModel)
⋮----
"""Aggregated usage statistics."""
⋮----
period_start: datetime
period_end: datetime
total_calls: int = 0
successful_calls: int = 0
failed_calls: int = 0
success_rate: float = 0.0
total_cost: float = 0.0
average_cost: float = 0.0
total_response_time_ms: int = 0
average_response_time_ms: float = 0.0
calls_by_tool: Dict[str, int] = Field(default_factory=dict)
calls_by_operation: Dict[str, int] = Field(default_factory=dict)
cost_by_tool: Dict[str, float] = Field(default_factory=dict)
⋮----
class UsageAlert(BaseModel)
⋮----
"""A usage alert/warning."""
⋮----
level: str  # "info", "warning", "critical"
message: str
metric: str
current_value: float
threshold: float
⋮----
class AlertThresholds(BaseModel)
⋮----
"""Configurable alert thresholds."""
⋮----
# Daily thresholds
daily_calls_warning: int = UsageTrackingDefaults.DAILY_CALLS_WARNING
daily_calls_critical: int = UsageTrackingDefaults.DAILY_CALLS_CRITICAL
daily_cost_warning: float = UsageTrackingDefaults.DAILY_COST_WARNING
daily_cost_critical: float = UsageTrackingDefaults.DAILY_COST_CRITICAL
⋮----
# Error thresholds
hourly_failures_warning: int = UsageTrackingDefaults.HOURLY_FAILURES_WARNING
hourly_failures_critical: int = UsageTrackingDefaults.HOURLY_FAILURES_CRITICAL
failure_rate_warning: float = UsageTrackingDefaults.FAILURE_RATE_WARNING
failure_rate_critical: float = UsageTrackingDefaults.FAILURE_RATE_CRITICAL
⋮----
# Performance thresholds
avg_response_time_warning_ms: int = UsageTrackingDefaults.AVG_RESPONSE_TIME_WARNING_MS
avg_response_time_critical_ms: int = UsageTrackingDefaults.AVG_RESPONSE_TIME_CRITICAL_MS
⋮----
# SQLite Storage
⋮----
class UsageDatabase
⋮----
"""SQLite-based usage tracking database."""
⋮----
def __init__(self, db_path: Optional[str] = None)
⋮----
"""Initialize the database.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.ast-grep-mcp/usage.db
        """
⋮----
config_dir = Path.home() / ".ast-grep-mcp"
⋮----
db_path = str(config_dir / "usage.db")
⋮----
def _get_connection(self) -> sqlite3.Connection
⋮----
"""Get thread-local database connection."""
⋮----
def _init_schema(self) -> None
⋮----
"""Initialize database schema."""
conn = self._get_connection()
⋮----
def log_usage(self, entry: UsageLogEntry) -> None
⋮----
"""Log a usage entry to the database.

        Args:
            entry: Usage log entry to persist
        """
⋮----
# Never fail the main operation due to logging
⋮----
"""Get aggregated usage statistics.

        Args:
            start_time: Start of period (default: 7 days ago)
            end_time: End of period (default: now)

        Returns:
            Aggregated usage statistics
        """
⋮----
start_time = datetime.now(UTC) - timedelta(days=UsageTrackingDefaults.DEFAULT_STATS_LOOKBACK_DAYS)
⋮----
end_time = datetime.now(UTC)
⋮----
# Get basic aggregates
row = conn.execute(
⋮----
total_calls = row["total_calls"] or 0
successful_calls = row["successful_calls"] or 0
⋮----
# Get calls by tool
calls_by_tool: Dict[str, int] = {}
⋮----
# Get calls by operation
calls_by_operation: Dict[str, int] = {}
⋮----
# Get cost by tool
cost_by_tool: Dict[str, float] = {}
⋮----
"""Check for usage alerts based on thresholds.

        Args:
            thresholds: Alert thresholds (uses defaults if not provided)

        Returns:
            List of active alerts
        """
⋮----
thresholds = AlertThresholds()
⋮----
alerts: List[UsageAlert] = []
now = datetime.now(UTC)
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
hour_ago = now - timedelta(hours=1)
⋮----
# Check daily calls
daily_calls = conn.execute(
⋮----
# Check daily cost
daily_cost = (
⋮----
# Check hourly failures
hourly_failures = conn.execute(
⋮----
# Check failure rate (last hour)
hourly_total = conn.execute(
⋮----
failure_rate = hourly_failures / hourly_total
⋮----
"""Get recent usage logs.

        Args:
            limit: Maximum number of logs to return
            tool_name: Filter by tool name
            success: Filter by success status

        Returns:
            List of recent usage log entries
        """
⋮----
query = "SELECT * FROM usage_logs WHERE 1=1"
params: List[Any] = []
⋮----
entries = []
⋮----
# Global Tracker Instance
⋮----
_usage_db: Optional[UsageDatabase] = None
_db_lock = threading.Lock()
⋮----
def get_usage_database() -> UsageDatabase
⋮----
"""Get the global usage database instance."""
⋮----
_usage_db = UsageDatabase()
⋮----
# Tracking Decorator
⋮----
F = TypeVar("F", bound=Callable[..., Any])
⋮----
"""Decorator to track usage of a function/tool.

    Args:
        tool_name: Name of the tool being tracked
        operation_type: Type of operation for cost calculation

    Returns:
        Decorated function with usage tracking
    """
⋮----
def decorator(func: F) -> F
⋮----
@wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any
⋮----
start_time = time.perf_counter()
success = True
⋮----
result: Any = None
⋮----
result = func(*args, **kwargs)
⋮----
success = False
error_message = str(e)[: DisplayDefaults.ERROR_MESSAGE_MAX_LENGTH]
⋮----
response_time_ms = int((time.perf_counter() - start_time) * 1000)
⋮----
# Extract metrics from result if available
files_processed = 0
lines_analyzed = 0
matches_found = 0
⋮----
files_processed = result.get("files_processed", 0)
lines_analyzed = result.get("lines_analyzed", 0)
matches_found = result.get("matches_found", len(result.get("matches", [])))
⋮----
# Check for summary stats
summary = result.get("summary", {})
⋮----
files_processed = summary.get("total_files", files_processed)
matches_found = summary.get("total_matches", matches_found)
⋮----
# Calculate cost
estimated_cost = calculate_operation_cost(
⋮----
# Log usage
entry = UsageLogEntry(
⋮----
# Never fail the main operation
⋮----
"""Context manager for tracking an operation.

    Usage:
        with track_operation("find_duplication", OperationType.FIND_DUPLICATION) as tracker:
            # perform operation
            tracker.files_processed = 10
            tracker.matches_found = 5

    Args:
        tool_name: Name of the tool
        operation_type: Type of operation
        metadata: Additional metadata to log
    """
tracker = _OperationTracker(
⋮----
@dataclass
class _OperationTracker
⋮----
"""Helper class for track_operation context manager."""
⋮----
operation_type: OperationType
metadata: Dict[str, Any] = field(default_factory=dict)
⋮----
_start_time: float = 0.0
⋮----
def _finalize(self) -> None
⋮----
"""Finalize and log the operation."""
response_time_ms = int((time.perf_counter() - self._start_time) * 1000)
⋮----
# Convenience Functions
⋮----
def get_usage_stats(days: int = UsageTrackingDefaults.DEFAULT_STATS_LOOKBACK_DAYS) -> UsageStats
⋮----
"""Get usage statistics for the last N days.

    Args:
        days: Number of days to look back

    Returns:
        Usage statistics
    """
start_time = datetime.now(UTC) - timedelta(days=days)
⋮----
def get_usage_alerts(thresholds: Optional[AlertThresholds] = None) -> List[UsageAlert]
⋮----
"""Get current usage alerts.

    Args:
        thresholds: Custom alert thresholds

    Returns:
        List of active alerts
    """
⋮----
"""Get recent usage logs.

    Args:
        limit: Maximum entries to return
        tool_name: Filter by tool
        success: Filter by success status

    Returns:
        Recent usage log entries
    """
⋮----
def format_usage_report(stats: UsageStats) -> str
⋮----
"""Format usage statistics as a human-readable report.

    Args:
        stats: Usage statistics to format

    Returns:
        Formatted report string
    """
lines = [
⋮----
cost = stats.cost_by_tool.get(tool, 0.0)
````

## File: src/ast_grep_mcp/features/quality/tools.py
````python
"""MCP tool definitions for code quality and standards features.

This module registers MCP tools for:
- detect_code_smells: Code smell detection
- create_linting_rule: Create custom linting rules
- list_rule_templates: Browse pre-built rule templates
- enforce_standards: Standards enforcement engine
- detect_orphans: Detect orphan files and functions not imported/called anywhere
"""
⋮----
"""Helper to create a rule from parameters."""
⋮----
overrides = {
# Remove None values
overrides = {k: v for k, v in overrides.items() if v is not None}
⋮----
"""Helper to save rule to project if requested."""
⋮----
def _format_rule_result(rule: LintingRule, validation_result: Any, saved_path: Optional[str]) -> Dict[str, Any]
⋮----
"""Helper to format the rule creation result."""
rule_dict = rule.to_yaml_dict()
yaml_str = yaml.dump(rule_dict, default_flow_style=False, sort_keys=False)
⋮----
"""
    Create a custom linting rule using ast-grep patterns.

    This function allows you to define custom code quality rules that can be enforced
    across your codebase. Rules can detect code smells, anti-patterns, security
    vulnerabilities, or enforce style guidelines.

    **Templates:** Use `use_template` parameter to start from a pre-built template
    (see list_rule_templates_tool).

    **Pattern Syntax Examples:**
    - `console.log($$$)` - matches any console.log call
    - `var $NAME = $$$` - matches var declarations
    - `except:` - matches bare except clauses in Python

    Args:
        rule_name: Unique rule identifier (e.g., 'no-console-log')
        description: Human-readable description of what the rule checks
        pattern: ast-grep pattern to match (e.g., 'console.log($$$)')
        severity: Severity level: 'error', 'warning', or 'info'
        language: Target language (python, typescript, javascript, java, etc.)
        suggested_fix: Optional replacement pattern or fix suggestion
        note: Additional note or explanation
        save_to_project: If True, save rule to project's .ast-grep-rules/
        project_folder: Project folder (required if save_to_project=True)
        use_template: Optional template ID to use as base

    Returns:
        Dictionary containing rule definition, validation results, saved path, and YAML
    """
logger = get_logger("tool.create_linting_rule")
start_time = time.time()
⋮----
# Create rule using helper
rule = _create_rule_from_params(rule_name, description, pattern, severity, language, suggested_fix, note, use_template)
⋮----
# Validate the rule
⋮----
validation_result = validate_rule_definition(rule)
⋮----
# Save if requested
saved_path = _save_rule_if_requested(rule, save_to_project, project_folder, validation_result)
⋮----
# Format result
result = _format_rule_result(rule, validation_result, saved_path)
⋮----
execution_time = time.time() - start_time
⋮----
def list_rule_templates_tool(language: Optional[str] = None, category: Optional[str] = None) -> Dict[str, Any]
⋮----
"""
    List available pre-built rule templates.

    This function returns a library of pre-built linting rules that can be used
    as-is or customized for your needs. Templates cover common patterns across
    multiple languages including JavaScript/TypeScript, Python, and Java.

    **Template Categories:**
    - `general`: General code quality and best practices
    - `security`: Security vulnerabilities and risks
    - `performance`: Performance anti-patterns
    - `style`: Code style and consistency

    Args:
        language: Filter by language (python, typescript, javascript, java, etc.)
        category: Filter by category (general, security, performance, style)

    Returns:
        Dictionary with total count, available languages/categories, and template list
    """
logger = get_logger("tool.list_rule_templates")
⋮----
templates = get_available_templates(language=language, category=category)
⋮----
# Get unique languages and categories from all templates
all_templates = list(RULE_TEMPLATES.values())
all_languages = sorted(set(t.language for t in all_templates))
all_categories = sorted(set(t.category for t in all_templates))
⋮----
# Convert templates to dict format
template_dicts = [
⋮----
def _get_default_exclude_patterns() -> List[str]
⋮----
"""Get default exclude patterns for file scanning."""
⋮----
def _normalize_exclude_patterns(exclude_patterns: List[str] | None) -> List[str]
⋮----
"""Normalize exclude patterns and enforce virtualenv exclusions."""
⋮----
exclude_patterns = _get_default_exclude_patterns()
⋮----
def _validate_enforcement_inputs(severity_threshold: str, output_format: str) -> None
⋮----
"""Validate input parameters for enforce_standards.

    Args:
        severity_threshold: Severity threshold to validate
        output_format: Output format to validate

    Raises:
        ValueError: If parameters are invalid
    """
⋮----
def _format_enforcement_output(result: EnforcementResult, output_format: str) -> Dict[str, Any]
⋮----
"""Format enforcement result based on output format."""
⋮----
# JSON format - return structured data
violations_data = []
⋮----
violations_by_file_data = {}
⋮----
"""
    Enforce coding standards by executing linting rules against a project.

    This function runs a set of linting rules (built-in or custom) against your codebase
    and reports all violations with file locations, severity levels, and fix suggestions.

    **Rule Sets:**
    - `recommended`: General best practices (10 rules)
    - `security`: Security-focused rules (9 rules)
    - `performance`: Performance anti-patterns
    - `style`: Code style and formatting rules (9 rules)
    - `custom`: Load custom rules from .ast-grep-rules/
    - `all`: All built-in rules for the language

    Args:
        project_folder: The absolute path to the project folder to scan
        language: The programming language (python, typescript, javascript, java)
        rule_set: Rule set to use: 'recommended', 'security', 'performance', 'style', 'custom', 'all'
        custom_rules: List of custom rule IDs from .ast-grep-rules/ (used with rule_set='custom')
        include_patterns: Glob patterns for files to include (e.g., ['src/**/*.py'])
        exclude_patterns: Glob patterns for files to exclude
        severity_threshold: Only report violations >= this severity ('error', 'warning', 'info')
        max_violations: Maximum violations to find (0 = unlimited). Stops execution early when reached.
        max_threads: Number of parallel threads for rule execution (default: 4)
        output_format: Output format: 'json' (structured data) or 'text' (human-readable report)

    Returns:
        Dictionary with summary, violations, and execution statistics

    Example usage:
        enforce_standards_tool(project_folder="/path/to/project", language="python")
        enforce_standards_tool(project_folder="/path/to/project", language="typescript", rule_set="security")
    """
# Set defaults
⋮----
custom_rules = []
⋮----
include_patterns = ["**/*"]
exclude_patterns = _normalize_exclude_patterns(exclude_patterns)
⋮----
logger = get_logger("tool.enforce_standards")
⋮----
# Validate inputs using helper
⋮----
# Execute enforcement
result = enforce_standards_impl(
⋮----
# Format output using helper
⋮----
def _convert_violations_to_objects(violations: List[Dict[str, Any]]) -> List[RuleViolation]
⋮----
"""Convert violation dictionaries to RuleViolation objects."""
violation_objects = []
⋮----
violation = RuleViolation(
⋮----
def _infer_project_folder(violations: List[Dict[str, Any]]) -> str
⋮----
"""Infer project folder from violation file paths."""
⋮----
all_files = [v.get("file", "") for v in violations if v.get("file")]
⋮----
common_prefix = os.path.commonprefix(all_files)
# Get the directory part
⋮----
def _format_fix_results(result: Any, dry_run: bool) -> Dict[str, Any]
⋮----
"""Format fix results for output."""
⋮----
"""
    Automatically fix code quality violations detected by enforce_standards.

    This function takes violations from enforce_standards and applies fixes automatically.
    It supports safe fixes (guaranteed-safe), suggested fixes (may need review), or all fixes.

    **Fix Types:**
    - `safe`: Only apply guaranteed-safe fixes (e.g., var → const, console.log removal)
    - `suggested`: Apply fixes that may need review (e.g., exception handling changes)
    - `all`: Apply all available fixes

    **Safety:**
    - All fixes are validated with syntax checking
    - Backup is created automatically (unless disabled)
    - Dry-run mode previews changes without applying
    - Failed fixes are rolled back automatically

    Args:
        violations: List of violations from enforce_standards (each must have 'file', 'line', 'rule_id', etc.)
        language: Programming language for syntax validation
        fix_types: Types of fixes to apply ('safe', 'suggested', 'all')
        dry_run: If True, preview fixes without applying them
        create_backup: If True, create backup before applying fixes

    Returns:
        Dictionary with fix results, backup ID, and statistics

    Example usage:
        # First, find violations
        result = enforce_standards_tool(project_folder="/path", language="python")

        # Preview fixes (dry run)
        preview = apply_standards_fixes_tool(
            violations=result["violations"],
            language="python",
            fix_types=["safe"],
            dry_run=True
        )

        # Apply safe fixes
        fixed = apply_standards_fixes_tool(
            violations=result["violations"],
            language="python",
            fix_types=["safe"],
            dry_run=False,
            create_backup=True
        )
    """
⋮----
fix_types = ["safe"]
⋮----
logger = get_logger("tool.apply_standards_fixes")
⋮----
# Convert violations using helper
violation_objects = _convert_violations_to_objects(violations)
⋮----
# Infer project folder using helper
project_folder_inferred = _infer_project_folder(violations)
⋮----
# Apply fixes
result = apply_fixes_batch(
⋮----
"""
    Generate a comprehensive code quality report from enforcement results.

    This function creates professional quality reports in Markdown or JSON format,
    summarizing violations, top issues, and providing actionable recommendations.

    **Output Formats:**
    - `markdown`: Human-readable report with tables and sections
    - `json`: Machine-readable structured data

    **Report Sections:**
    - Summary statistics (violations by severity)
    - Violations by severity level
    - Top issues by rule
    - Files with most violations
    - Recommendations and auto-fix suggestions

    Args:
        enforcement_result: Result dictionary from enforce_standards tool
        project_name: Name of the project for report header
        output_format: Report format ('markdown' or 'json')
        include_violations: Whether to include detailed violation listings
        include_code_snippets: Whether to include code snippets (JSON only)
        save_to_file: Optional file path to save the report

    Returns:
        Dictionary with report content and metadata

    Example usage:
        # Run enforcement
        result = enforce_standards(project_folder="/path", language="python")

        # Generate Markdown report
        report = generate_quality_report(
            enforcement_result=result,
            project_name="My Project",
            output_format="markdown",
            save_to_file="quality-report.md"
        )

        print(report["content"])
    """
logger = get_logger("tool.generate_quality_report")
⋮----
# Convert dictionary to EnforcementResult
result_obj = _dict_to_enforcement_result(enforcement_result)
⋮----
# Generate report
report = generate_quality_report_impl(
⋮----
def _dict_to_enforcement_result(data: Dict[str, Any]) -> EnforcementResult
⋮----
"""Convert enforcement result dictionary to EnforcementResult object.

    Args:
        data: Dictionary from enforce_standards tool

    Returns:
        EnforcementResult object
    """
# Convert violations
violations = []
⋮----
# Group violations
violations_by_file: Dict[str, List[RuleViolation]] = {}
violations_by_severity: Dict[str, List[RuleViolation]] = {}
violations_by_rule: Dict[str, List[RuleViolation]] = {}
⋮----
# By file
⋮----
# By severity
⋮----
# By rule
⋮----
def _format_security_issues(issues: List[SecurityIssue]) -> List[Dict[str, Any]]
⋮----
"""Format security issues for output."""
⋮----
def _format_issues_by_severity(result: Any) -> Dict[str, List[Dict[str, Any]]]
⋮----
"""Format issues grouped by severity."""
formatted = {}
⋮----
"""
    Scan code for security vulnerabilities and common weaknesses.

    This function performs comprehensive security scanning using ast-grep patterns
    and regex-based detection to identify vulnerabilities like SQL injection, XSS,
    command injection, hardcoded secrets, and insecure cryptography.

    **Vulnerability Types:**
    - `sql_injection`: SQL injection via f-strings, .format(), concatenation
    - `xss`: Cross-site scripting via innerHTML, document.write
    - `command_injection`: Command injection via os.system, subprocess, eval/exec
    - `hardcoded_secrets`: API keys, tokens, passwords in source code
    - `insecure_crypto`: Weak hash algorithms (MD5, SHA-1)

    **Severity Levels:**
    - `critical`: Immediate security risk requiring urgent fix
    - `high`: Serious security weakness
    - `medium`: Moderate security concern
    - `low`: Minor security issue or code smell

    **CWE References:**
    Each issue includes CWE (Common Weakness Enumeration) IDs for standardized
    vulnerability classification.

    Args:
        project_folder: Absolute path to project root directory
        language: Programming language (python, javascript, typescript, java)
        issue_types: Types to scan for, or None for all types
        severity_threshold: Minimum severity to report (critical/high/medium/low)
        max_issues: Maximum number of issues to return (0 = unlimited)

    Returns:
        Dictionary containing security scan results with summary and issues

    Example usage:
        # Scan for all security issues
        result = detect_security_issues(
            project_folder="/path/to/project",
            language="python",
            issue_types=["all"],
            severity_threshold="medium"
        )

        # Scan for specific vulnerability types
        result = detect_security_issues(
            project_folder="/path/to/project",
            language="javascript",
            issue_types=["sql_injection", "xss"],
            severity_threshold="high",
            max_issues=50
        )

        print(f"Found {result['summary']['total_issues']} security issues")
        for issue in result['issues']:
            print(f"{issue['severity']}: {issue['title']} at {issue['file']}:{issue['line']}")
    """
logger = get_logger("tool.detect_security_issues")
⋮----
# Default to all types if not specified
⋮----
issue_types = ["all"]
⋮----
# Run security scan
result = detect_security_issues_impl(
⋮----
# Convert to JSON-serializable format using helpers
⋮----
"""
    Detect orphan files and functions in a codebase.

    This function identifies code that is never imported or called, helping to find
    dead code that can be safely removed. It builds a dependency graph, identifies
    entry points, and verifies orphan status using multiple methods.

    **What it detects:**
    - **Orphan Files**: Files that are not imported by any other file
    - **Orphan Functions**: Functions that are defined but never called

    **How it works:**
    1. Builds a dependency graph from import statements
    2. Identifies entry points (main.py, test files, __init__.py, etc.)
    3. Finds files not reachable from any entry point
    4. Optionally verifies with grep to reduce false positives
    5. Analyzes function-level orphans within non-orphan files

    **Supported Languages:**
    - Python: AST-based import parsing (handles relative imports)
    - TypeScript/JavaScript: Regex-based import parsing

    **Entry Points (automatically detected):**
    - main.py, __main__.py, cli.py, app.py, server.py
    - index.ts, index.js
    - conftest.py, test_*.py, *_test.py, *.test.ts, *.spec.ts

    Args:
        project_folder: Absolute path to project root directory
        include_patterns: Glob patterns for files to include (default: ['**/*.py', '**/*.ts', '**/*.js'])
        exclude_patterns: Glob patterns to exclude (default: node_modules, __pycache__, .git, etc.)
        analyze_functions: Whether to analyze function-level orphans (default: True)
        verify_with_grep: Whether to double-check with grep for string references (default: True)

    Returns:
        Dictionary containing:
        - summary: Statistics about orphan detection
        - orphan_files: List of orphan files with details
        - orphan_functions: List of orphan functions with details

    Example usage:
        # Basic orphan detection
        result = detect_orphans(
            project_folder="/path/to/project"
        )

        # Focus on Python files only
        result = detect_orphans(
            project_folder="/path/to/project",
            include_patterns=["**/*.py"],
            analyze_functions=True
        )

        # Quick scan without function analysis
        result = detect_orphans(
            project_folder="/path/to/project",
            analyze_functions=False,
            verify_with_grep=False
        )

        print(f"Found {result['summary']['orphan_files']} orphan files")
        print(f"Found {result['summary']['orphan_functions']} orphan functions")
        for f in result['orphan_files']:
            print(f"  {f['file_path']} ({f['lines']} lines) - {f['status']}")
    """
logger = get_logger("tool.detect_orphans")
⋮----
# Run orphan detection
result = detect_orphans_impl(
⋮----
def _create_mcp_field_definitions() -> Dict[str, Dict[str, Any]]
⋮----
"""Create field definitions for MCP tool registration."""
⋮----
def register_quality_tools(mcp: FastMCP) -> None
⋮----
"""Register all quality feature tools with MCP server.

    Args:
        mcp: FastMCP server instance

    Note:
        detect_code_smells is registered in the complexity module's register_complexity_tools() function
        to consolidate code smell detection with complexity analysis.
    """
fields = _create_mcp_field_definitions()
⋮----
"""Wrapper that calls the standalone create_linting_rule_tool function."""
⋮----
"""Wrapper that calls the standalone list_rule_templates_tool function."""
⋮----
"""Wrapper that calls the standalone enforce_standards_tool function."""
⋮----
"""Wrapper that calls the standalone apply_standards_fixes_tool function."""
⋮----
"""Wrapper that calls the standalone generate_quality_report_tool function."""
⋮----
"""Wrapper that calls the standalone detect_security_issues_tool function."""
⋮----
"""Wrapper that calls the standalone detect_orphans_tool function."""
````

## File: src/ast_grep_mcp/features/deduplication/tools.py
````python
"""MCP tool wrappers for deduplication features.

This module provides the high-level tool interfaces exposed via MCP.
These functions wrap the underlying deduplication modules to provide
a clean API for the MCP server.
"""
⋮----
_MANDATORY_ENV_EXCLUDE_PATTERNS = ["site-packages", ".venv", "venv", "virtualenv"]
⋮----
def _normalize_exclude_patterns(exclude_patterns: Optional[List[str]]) -> List[str]
⋮----
"""Normalize exclude patterns and enforce virtualenv exclusions."""
⋮----
exclude_patterns = ["site-packages", "node_modules", ".venv", "venv", "vendor", "__pycache__", ".git"]
⋮----
normalized = list(exclude_patterns)
⋮----
"""Find duplicate functions/classes/methods in a codebase.

    This is the main entry point for the find_duplication MCP tool.

    Args:
        project_folder: Path to the project folder
        language: Programming language
        min_similarity: Minimum similarity threshold (0-1)
        min_lines: Minimum lines to consider
        exclude_patterns: Path patterns to exclude

    Returns:
        Dictionary with duplication results
    """
logger = get_logger("deduplication.tool.find")
⋮----
exclude_patterns = _normalize_exclude_patterns(exclude_patterns)
⋮----
detector = DuplicationDetector(language=language)
results = detector.find_duplication(
⋮----
construct_type="function_definition",  # Default to functions
⋮----
"""Analyze a project for deduplication candidates and return ranked results.

    This tool extends find_duplication by:
    1. Scoring duplicates by complexity, frequency, and maintainability impact
    2. Optionally checking test coverage to prioritize well-tested code
    3. Ranking candidates by refactoring value (highest savings + lowest risk first)
    4. Providing actionable recommendations for each candidate group

    Args:
        project_path: The absolute path to the project folder to analyze
        language: The target language
        min_similarity: Minimum similarity threshold (0.0-1.0)
        include_test_coverage: Whether to check test coverage for prioritization
        min_lines: Minimum number of lines to consider for duplication
        max_candidates: Maximum number of candidates to return
        exclude_patterns: Path patterns to exclude from analysis

    Returns:
        Dictionary with:
        - candidates: List of duplicate groups with scores and rankings
        - total_groups: Number of duplication groups found
        - total_savings_potential: Total lines that could be saved
        - analysis_metadata: Timing and configuration info
    """
logger = get_logger("deduplication.tool.analyze")
⋮----
# Delegate to orchestrator
orchestrator = DeduplicationAnalysisOrchestrator()
result = orchestrator.analyze_candidates(
⋮----
"""Apply automated deduplication refactoring with comprehensive syntax validation.

    Phase 3.5 VALIDATION PIPELINE:
    1. PRE-VALIDATION: Validate all generated code before applying
    2. APPLICATION: Create backup and apply changes
    3. POST-VALIDATION: Validate modified files
    4. AUTO-ROLLBACK: Restore from backup if validation fails

    Args:
        project_folder: The absolute path to the project folder
        group_id: The duplication group ID from find_duplication results
        refactoring_plan: The refactoring plan with generated_code, files_affected, strategy, language
        dry_run: Preview changes without applying (default: true for safety)
        backup: Create backup before applying changes (default: true)
        extract_to_file: Where to place extracted function (auto-detect if None)

    Returns:
        Dictionary with:
        - status: "preview" | "success" | "failed" | "rolled_back"
        - validation: Pre and post validation results with detailed errors
        - errors: Detailed error info with file, line, message, and suggested fix
    """
logger = get_logger("deduplication.tool.apply")
⋮----
applicator = DeduplicationApplicator()
result = applicator.apply_deduplication(
⋮----
def benchmark_deduplication_tool(iterations: int = 10, save_baseline: bool = False, check_regression: bool = True) -> Dict[str, Any]
⋮----
"""Run performance benchmarks for deduplication functions.

    Benchmarks the following operations:
    - **scoring**: calculate_deduplication_score (should be < 1ms)
    - **pattern_analysis**: rank_deduplication_candidates and analyze variations
    - **code_generation**: generate_deduplication_recommendation
    - **full_workflow**: create_enhanced_duplication_response

    Args:
        iterations: Number of iterations per benchmark (default: 10)
        save_baseline: Save results as new baseline for regression detection
        check_regression: Check results against baseline for performance regressions

    Returns:
        Dictionary with benchmark results including:
        - total_benchmarks: Number of benchmarks run
        - results: List of benchmark results with statistics
        - regression_detected: Whether any regressions were found
        - regression_errors: List of specific regression failures
    """
logger = get_logger("deduplication.tool.benchmark")
⋮----
benchmark = DeduplicationBenchmark()
results = benchmark.benchmark_deduplication(iterations=iterations, save_baseline=save_baseline, check_regression=check_regression)
⋮----
def register_deduplication_tools(mcp: FastMCP) -> None
⋮----
"""Register all deduplication tools with the MCP server.

    This function creates MCP tool wrappers that call the standalone *_tool functions.
    The wrappers use clean names (without _tool suffix) for consistency with other
    refactored tools (complexity, quality, schema).

    Args:
        mcp: FastMCP instance to register tools with
    """
⋮----
"""Wrapper that calls the standalone find_duplication_tool function."""
⋮----
"""Wrapper that calls the standalone analyze_deduplication_candidates_tool function."""
⋮----
"""Wrapper that calls the standalone apply_deduplication_tool function."""
⋮----
"""Wrapper that calls the standalone benchmark_deduplication_tool function."""
````

## File: src/ast_grep_mcp/features/condense/tools.py
````python
"""MCP tool definitions for code condensation features.

Registers 6 tools:
- condense_extract_surface
- condense_normalize
- condense_strip
- condense_pack
- condense_estimate
- condense_train_dictionary
"""
⋮----
logger = get_logger("condense.tools")
⋮----
def _resolve_file_path(path: str) -> Path
⋮----
"""Resolve and validate that path is an existing file (not a directory).

    Raises FileNotFoundError or IsADirectoryError with structured messages.
    """
p = Path(path).resolve()
⋮----
# ---------------------------------------------------------------------------
# Standalone tool functions (testable without MCP)
⋮----
"""Extract public API surface from source files."""
⋮----
start = time.time()
⋮----
result = extract_surface_impl(
⋮----
"""Normalize source code to canonical forms for better downstream compression."""
⋮----
resolved = _resolve_file_path(path)
source = resolved.read_text(encoding="utf-8", errors="replace")
⋮----
result: Dict[str, Any] = {
⋮----
"""Remove dead code, debug statements, and empty blocks."""
⋮----
"""Run the full normalize → strip → extract condensation pipeline."""
⋮----
result = condense_pack_impl(
⋮----
"""Estimate condensation reduction ratios without modifying any files."""
⋮----
result = estimate_condensation_impl(path=path, language=language)
⋮----
"""Train a zstd dictionary on representative code samples from a codebase."""
⋮----
result = train_dictionary_impl(
⋮----
# MCP registration
⋮----
def register_condense_tools(mcp: FastMCP) -> None
⋮----
"""Register all condense tools with the MCP server.

    Args:
        mcp: FastMCP instance to register tools with.
    """
⋮----
"""Extract public API surface (exports, signatures, types) from source files.

        Returns condensed source with only the public interface, stripping
        function bodies for low-complexity functions when complexity_guided=True.
        Achieves ~70-85% token reduction in ai_chat mode.
        """
⋮----
"""Normalize source code to canonical forms before compression.

        Applies language-specific transforms: consistent string quotes,
        trailing semicolon removal (JS/TS), trailing comma cleanup.
        Returns normalized_source, normalizations_applied, and byte counts.
        """
⋮----
"""Remove dead code, debug statements, and empty blocks from source.

        Strips console.log/print, debugger, pdb.set_trace, and similar.
        Returns stripped_source and lines_removed count.
        """
⋮----
"""Run the full condensation pipeline: normalize → strip → extract.

        Chains all condense operations into a single pass over a directory.
        Returns condensed_output, reduction_pct, token estimates, and per-language stats.
        """
⋮----
"""Estimate condensation reduction ratios without modifying any files.

        Returns projected token/byte counts for all four strategies plus
        top_reduction_candidates ranked by line count.
        Safe to run on any codebase — read-only, no modifications.
        """
⋮----
"""Train a zstd dictionary on representative code samples.

        A per-codebase dictionary improves zstd compression 10-30% for
        small-to-medium files (<100KB) with consistent coding patterns.
        Use the resulting dict_path with: zstd -D <dict_path> to compress.
        Returns dict_path, dict_size_bytes, samples_used, and estimated improvement.
        """
````

## File: src/ast_grep_mcp/features/complexity/tools.py
````python
"""
Complexity analysis MCP tools.

This module provides MCP tool definitions for code complexity analysis
and Sentry integration testing.
"""
⋮----
# Note: detect_code_smells_impl is imported inside detect_code_smells_tool()
# to avoid circular import (quality.smells imports from complexity.analyzer)
⋮----
# Helper functions extracted from analyze_complexity_tool
⋮----
def _validate_inputs(language: str) -> None
⋮----
"""Validate input parameters for complexity analysis.

    Args:
        language: The programming language to validate

    Raises:
        ValueError: If the language is not supported
    """
supported_langs = ["python", "typescript", "javascript", "java"]
⋮----
def _get_default_complexity_exclude_patterns() -> List[str]
⋮----
"""Get default exclude patterns for complexity analysis."""
⋮----
def _normalize_complexity_exclude_patterns(exclude_patterns: List[str] | None) -> List[str]
⋮----
"""Normalize exclude patterns and enforce virtualenv exclusions."""
⋮----
exclude_patterns = _get_default_complexity_exclude_patterns()
⋮----
"""Find files to analyze based on patterns.

    Args:
        project_folder: The project folder to analyze
        language: The programming language
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude
        logger: Logger instance

    Returns:
        Tuple of (files to analyze, file finder instance)
    """
file_finder = ComplexityFileFinder()
files_to_analyze = file_finder.find_files(project_folder, language, include_patterns, exclude_patterns)
⋮----
"""Analyze files in parallel for complexity metrics.

    Args:
        files_to_analyze: List of files to analyze
        language: The programming language
        thresholds: Complexity thresholds
        max_threads: Number of parallel threads

    Returns:
        Tuple of (all functions, exceeding functions, analyzer instance)
    """
analyzer = ParallelComplexityAnalyzer()
⋮----
# Analyze files in parallel
all_functions = analyzer.analyze_files(files_to_analyze, language, thresholds, max_threads)
⋮----
# Filter exceeding functions
exceeding_functions = analyzer.filter_exceeding_functions(all_functions)
⋮----
"""Calculate summary statistics from analysis results.

    Args:
        all_functions: All analyzed functions
        exceeding_functions: Functions exceeding thresholds
        total_files: Total number of files analyzed
        execution_time: Analysis execution time

    Returns:
        Tuple of (summary dictionary, statistics instance)
    """
statistics = ComplexityStatisticsAggregator()
summary = statistics.calculate_summary(all_functions, exceeding_functions, total_files, execution_time)
⋮----
"""Store results and generate trends if requested.

    Args:
        store_results: Whether to store results
        include_trends: Whether to include trends
        project_folder: The project folder
        summary: Summary statistics
        all_functions: All analyzed functions
        statistics: Statistics aggregator instance

    Returns:
        Tuple of (run_id, stored_at, trends)
    """
run_id = None
stored_at = None
trends = None
⋮----
trends = statistics.get_trends(project_folder, days=ComplexityStorageDefaults.TRENDS_LOOKBACK_DAYS)
⋮----
"""Format the final response dictionary.

    Args:
        summary: Summary statistics
        thresholds_dict: Complexity thresholds used
        exceeding_functions: Functions exceeding thresholds
        run_id: Storage run ID
        stored_at: Storage location
        trends: Trend data
        statistics: Statistics aggregator instance

    Returns:
        Formatted response dictionary
    """
⋮----
def _handle_no_files_found(language: str, execution_time: float) -> Dict[str, Any]
⋮----
"""Handle the case when no files are found to analyze.

    Args:
        language: The programming language
        execution_time: Time taken for the analysis attempt

    Returns:
        Response dictionary for no files found case
    """
⋮----
"""Create thresholds dictionary for response.

    Args:
        cyclomatic_threshold: Cyclomatic complexity threshold
        cognitive_threshold: Cognitive complexity threshold
        nesting_threshold: Maximum nesting depth threshold
        length_threshold: Function length threshold in lines

    Returns:
        Dictionary of threshold values
    """
⋮----
"""Execute the main analysis workflow.

    Args:
        project_folder: Project folder to analyze
        language: Programming language
        thresholds: Complexity thresholds
        files_to_analyze: List of files to analyze
        store_results: Whether to store results
        include_trends: Whether to include trends
        max_threads: Number of parallel threads
        start_time: Analysis start time
        logger: Logger instance

    Returns:
        Analysis response dictionary
    """
⋮----
# Calculate summary statistics
execution_time = time.time() - start_time
⋮----
# Store results and generate trends
⋮----
# Create thresholds dict from the thresholds object
thresholds_dict = {
⋮----
# Format and return response
⋮----
"""
    Analyze code complexity metrics for functions in a project.

    Calculates cyclomatic complexity, cognitive complexity, nesting depth, and function length
    for all functions in the specified project. Returns a summary with only functions that
    exceed the configured thresholds.

    Metrics:
    - Cyclomatic Complexity: McCabe's cyclomatic complexity (decision points + 1)
    - Cognitive Complexity: SonarSource cognitive complexity with nesting penalties
    - Nesting Depth: Maximum indentation depth within a function
    - Function Length: Number of lines in the function

    Args:
        project_folder: The absolute path to the project folder to analyze
        language: The programming language (python, typescript, javascript, java)
        include_patterns: Glob patterns for files to include (e.g., ['src/**/*.py'])
        exclude_patterns: Glob patterns for files to exclude
        cyclomatic_threshold: Cyclomatic complexity threshold (default: 10)
        cognitive_threshold: Cognitive complexity threshold (default: 15)
        nesting_threshold: Maximum nesting depth threshold (default: 4)
        length_threshold: Function length threshold in lines (default: 50)
        store_results: Store results in database for trend tracking
        include_trends: Include historical trend data in response
        max_threads: Number of parallel threads for analysis (default: 4)

    Returns:
        Dictionary with analysis results including summary and functions exceeding thresholds

    Example usage:
        analyze_complexity_tool(project_folder="/path/to/project", language="python")
        analyze_complexity_tool(project_folder="/path/to/project", language="typescript", cyclomatic_threshold=15)
    """
# Set defaults
⋮----
include_patterns = ["**/*"]
exclude_patterns = _normalize_complexity_exclude_patterns(exclude_patterns)
⋮----
logger = get_logger("tool.analyze_complexity")
start_time = time.time()
⋮----
# Validate inputs
⋮----
# Set up thresholds
thresholds = ComplexityThresholds(
⋮----
# Find files to analyze
⋮----
# Handle no files found case
⋮----
# Execute the main analysis workflow
⋮----
def _sentry_test_error(message: str, result: Dict[str, Any]) -> None
⋮----
"""Trigger a test exception for Sentry."""
⋮----
def _sentry_test_warning(message: str, result: Dict[str, Any]) -> None
⋮----
"""Send a test warning message to Sentry."""
⋮----
def _sentry_test_breadcrumb(message: str, result: Dict[str, Any]) -> None
⋮----
"""Add test breadcrumbs and send to Sentry."""
⋮----
def _sentry_test_span(message: str, result: Dict[str, Any]) -> None
⋮----
"""Create a test performance span in Sentry."""
⋮----
_SENTRY_TEST_HANDLERS: Dict[str, Callable[[str, Dict[str, Any]], None]] = {
⋮----
"""
    Test Sentry integration by triggering different event types.

    Used to verify that Sentry error tracking is properly configured and working.
    Only works when SENTRY_DSN environment variable is set.

    Test Types:
    - error: Triggers a test exception that gets captured by Sentry
    - warning: Sends a warning message to Sentry
    - breadcrumb: Adds test breadcrumbs (check Sentry dashboard for context)
    - span: Creates a performance span

    Args:
        test_type: Type of Sentry test ('error', 'warning', 'breadcrumb', or 'span')
        message: Custom test message

    Returns:
        Information about what was sent to Sentry
    """
logger = get_logger("tool.test_sentry_integration")
⋮----
result: Dict[str, Any] = {"status": "success", "test_type": test_type}
handler = _SENTRY_TEST_HANDLERS[test_type]
⋮----
def _get_default_smell_exclude_patterns() -> List[str]
⋮----
"""Get default exclude patterns for code smell detection."""
⋮----
def _prepare_smell_detection_params(include_patterns: List[str] | None, exclude_patterns: List[str] | None) -> tuple[List[str], List[str]]
⋮----
"""Prepare and validate parameters for smell detection.

    Args:
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude

    Returns:
        Tuple of (include_patterns, exclude_patterns) with defaults applied
    """
⋮----
exclude_patterns = _get_default_smell_exclude_patterns()
exclude_patterns = FilePatterns.merge_with_venv_excludes(exclude_patterns)
⋮----
def _process_smell_detection_result(result: Dict[str, Any], start_time: float, logger: Any) -> Dict[str, Any]
⋮----
"""Add execution time and log completion metrics.

    Args:
        result: Smell detection result dictionary
        start_time: Start time of the analysis
        logger: Logger instance

    Returns:
        Result dictionary with execution_time_ms added
    """
⋮----
"""
    Detect common code smells, anti-patterns in a project.

    Identifies patterns that indicate potential design, maintainability issues:
    - Long Functions: Functions exceeding line count threshold
    - Parameter Bloat: Functions having too many parameters (>5)
    - Deep Nesting: Excessive nesting depth (>4 levels)
    - Large Classes: Classes having too many methods, lines
    - Magic Numbers: Hard-coded literals (excludes 0, 1, -1, 2, 10, 100)

    Each smell is rated by severity (high/medium/low) based on how far it exceeds thresholds,
    includes actionable suggestions to improve code.

    Args:
        project_folder: Absolute path to the project folder to analyze
        language: Programming language (python, typescript, javascript, java)
        include_patterns: Glob patterns selecting files to include (e.g., ['src/**/*.py'])
        exclude_patterns: Glob patterns selecting files to exclude
        long_function_lines: Line count threshold detecting long function smell (default: 50)
        parameter_count: Parameter count threshold detecting parameter bloat (default: 5)
        nesting_depth: Nesting depth threshold detecting deep nesting smell (default: 4)
        class_lines: Line count threshold detecting large class smell (default: 300)
        class_methods: Method count threshold detecting large class smell (default: 20)
        detect_magic_numbers: Whether to detect magic number smells
        severity_filter: Filter by severity: 'all', 'high', 'medium', 'low'
        max_threads: Number of parallel threads used in analysis (default: 4)

    Returns:
        Dictionary containing analysis results including summary, detected smells by severity

    Example usage:
        detect_code_smells_tool(project_folder="/path/to/project", language="python")
        detect_code_smells_tool(project_folder="/path/to/project", language="typescript", severity_filter="high")
    """
# Import here to avoid circular import with quality.smells
⋮----
logger = get_logger("tool.detect_code_smells")
⋮----
# Prepare parameters with defaults
⋮----
result = detect_code_smells_impl(
⋮----
# Process result and add execution time
⋮----
def register_complexity_tools(mcp: FastMCP) -> None
⋮----
"""Register complexity analysis tools with the MCP server.

    Args:
        mcp: FastMCP server instance
    """
⋮----
"""Wrapper that calls the standalone analyze_complexity_tool function."""
⋮----
"""Wrapper that calls the standalone test_sentry_integration_tool function."""
⋮----
"""Wrapper that calls the standalone detect_code_smells_tool function."""
````

## File: CLAUDE.md
````markdown
# CLAUDE.md

## Quick Start

```bash
uv sync                          # Install dependencies
uv run pytest                    # Run all tests (1,469 collected)
uv run ruff check . && uv run mypy src/ # Lint and type check
uv run main.py                   # Run MCP server locally
doppler run -- uv run main.py    # Run with Doppler secrets
```

## Overview

Modular MCP server (120 modules) with ast-grep structural code search, Schema.org tools, refactoring, deduplication, quality, documentation generation, and semantic code condensation.

**53 Tools:** Search (9), Rewrite (3), Refactoring (2), Deduplication (4), Schema.org (9), Complexity (3), Quality (7), Documentation (5), Cross-Language (5), Condense (6)

**Deps:** ast-grep CLI (required), Doppler CLI (optional), Python 3.13+, uv

## Architecture

```
src/ast_grep_mcp/
├── core/           # Config, cache, executor, logging, sentry, usage tracking
├── models/         # Data models
├── utils/          # Templates, formatters, validation
├── features/       # search, rewrite, refactoring, schema, deduplication, complexity, quality, documentation, cross_language, condense
└── server/         # MCP server registry
```

**Import:** `from ast_grep_mcp.features.search.service import find_code_impl`

## Code Quality

Quality gates: Ruff + mypy + pytest + analyze_codebase.py

```bash
uv run pytest tests/quality/test_complexity_regression.py -v
```

## Recent Maintenance (2026-03-04)

- Consolidated repeated scoring/confidence literals into shared constants and scales.
- Reduced magic-number false positives by ignoring one-off constant declarations in smell detection.
- Enforced venv and backup exclusions across analyzer/search scans.
- Fixed unified diff hunk parsing to match shared capture-group constants.

## Config

**Environment:** `AST_GREP_CONFIG`, `LOG_LEVEL`, `SENTRY_DSN`, `CACHE_DISABLED`/`CACHE_SIZE`/`CACHE_TTL`

## Notes

- YAML rules support `kind`-based matching (e.g., `kind: catch_clause` with `has`); add `stopBy: end` to relational rules
- Windows: use `shell=True` for npm-installed ast-grep
- **All tool functions are synchronous** — call directly, do NOT wrap in `asyncio.run()`
- CLI invocation: `uv run python -c "from ast_grep_mcp.features.X.tools import Y; print(Y(...))"`
- Codebase analyzer: `uv run python analyze_codebase.py <path> -l <language> [--fix]`
- ast-grep supported languages: python, javascript, typescript, tsx, html, css, json, yaml, rust, go, java, kotlin, c, cpp, csharp, swift, ruby, lua, scala — **not** dart

## Docs

- [CHANGELOG.md](CHANGELOG.md) - Version history
- [docs/PATTERNS.md](docs/PATTERNS.md) - Refactoring patterns
- [docs/DEDUPLICATION-GUIDE.md](docs/DEDUPLICATION-GUIDE.md) - Deduplication workflow
- [docs/CONFIGURATION.md](docs/CONFIGURATION.md) - Configuration options
- [docs/SENTRY-INTEGRATION.md](docs/SENTRY-INTEGRATION.md) - Error tracking
- [docs/BENCHMARKING.md](docs/BENCHMARKING.md) - Performance benchmarking
- [docs/CODE-CONDENSE-PREP.md](docs/CODE-CONDENSE-PREP.md) - Condense feature design
- [docs/CODE-CONDENSE-PHASE-2.md](docs/CODE-CONDENSE-PHASE-2.md) - Condense phase 2 design
- [docs/BACKLOG.md](docs/BACKLOG.md) - Open backlog items
````

## File: src/ast_grep_mcp/constants.py
````python
"""Shared constants across the ast-grep-mcp codebase.

This module centralizes magic numbers and configuration values
to improve maintainability and reduce code duplication.
"""
⋮----
class ComplexityDefaults
⋮----
"""Default thresholds for complexity analysis."""
⋮----
CYCLOMATIC_THRESHOLD = 10
COGNITIVE_THRESHOLD = 15
NESTING_THRESHOLD = 4
LENGTH_THRESHOLD = 50
⋮----
class CriticalComplexityThresholds
⋮----
"""Critical complexity thresholds for script-level audit/report tools."""
⋮----
CYCLOMATIC = 20
COGNITIVE = 30
NESTING = 6
LINES = 150
⋮----
class ParallelProcessing
⋮----
"""Parallel processing configuration."""
⋮----
DEFAULT_WORKERS = 4
MAX_WORKERS = 16
⋮----
# Timeout configuration for parallel operations
DEFAULT_TIMEOUT_PER_CANDIDATE_SECONDS = 30  # 30 seconds per candidate
MAX_TIMEOUT_SECONDS = 300  # 5 minutes max total timeout
⋮----
@staticmethod
    def get_optimal_workers(max_threads: int = 0) -> int
⋮----
"""Calculate optimal worker count based on CPU cores.

        Args:
            max_threads: Maximum threads to use (0 = auto-detect)

        Returns:
            Optimal number of worker threads (1 to MAX_WORKERS)
        """
⋮----
cpu_count = os.cpu_count() or 4
# Reserve 1 core for system, cap at MAX_WORKERS
⋮----
class BackupDefaults
⋮----
"""Defaults for backup retention and lifecycle management."""
⋮----
RETENTION_DAYS = 30
⋮----
class CacheDefaults
⋮----
"""Cache configuration defaults."""
⋮----
TTL_SECONDS = 3600  # 1 hour
MAX_SIZE_MB = 100
CLEANUP_INTERVAL_SECONDS = 300  # 5 minutes
DEFAULT_CACHE_SIZE = 100  # Number of cached items
CACHE_KEY_LENGTH = 16  # Length of truncated SHA256 hash for cache keys
⋮----
class FilePatterns
⋮----
"""Common file patterns for analysis."""
⋮----
VENV_EXCLUDE = [
⋮----
DEFAULT_EXCLUDE = [
⋮----
MINIFIED_EXCLUDE = [
⋮----
TEST_EXCLUDE = [
⋮----
@staticmethod
    def merge_with_venv_excludes(exclude_patterns: list[str] | None) -> list[str]
⋮----
"""Ensure virtualenv/site-packages paths are always excluded.

        This is intentionally applied even when callers provide custom exclude
        patterns, so environment directories never enter analysis scope.
        """
merged = list(exclude_patterns or [])
⋮----
class StreamDefaults
⋮----
"""Defaults for streaming operations."""
⋮----
DEFAULT_TIMEOUT_MS = 120000  # 2 minutes
MAX_TIMEOUT_MS = 600000  # 10 minutes
PROGRESS_INTERVAL = 100  # Log progress every N matches
SIGTERM_RETURN_CODE = -15  # Return code for SIGTERM signal
⋮----
class ValidationDefaults
⋮----
"""Defaults for validation operations."""
⋮----
MAX_FILE_SIZE_MB = 10  # Skip files larger than this
SYNTAX_CHECK_TIMEOUT_SECONDS = 5
⋮----
class FileConstants
⋮----
"""Constants for file operations."""
⋮----
BYTES_PER_KB = 1024
BYTES_PER_MB = 1024 * 1024
BYTES_PER_GB = 1024 * 1024 * 1024
LINE_PREVIEW_LENGTH = 100  # Maximum characters to show in line preview
⋮----
class DeduplicationDefaults
⋮----
"""Defaults for deduplication analysis."""
⋮----
MIN_SIMILARITY = 0.8  # Minimum similarity threshold (0-1)
MIN_LINES = 5  # Minimum lines to consider for duplication
MAX_CANDIDATES = 100  # Maximum candidate pairs to analyze
⋮----
# Scoring weights (must sum to 1.0)
SAVINGS_WEIGHT = 0.40
COMPLEXITY_WEIGHT = 0.20
RISK_WEIGHT = 0.25
EFFORT_WEIGHT = 0.15
⋮----
# Regression thresholds for performance benchmarks
REGRESSION_PATTERN_ANALYSIS = 0.15  # 15% slowdown allowed
REGRESSION_CODE_GENERATION = 0.10  # 10% slowdown allowed
REGRESSION_FULL_WORKFLOW = 0.20  # 20% slowdown allowed
REGRESSION_SCORING = 0.05  # 5% slowdown allowed
REGRESSION_TEST_COVERAGE = 0.15  # 15% slowdown allowed
DEFAULT_COMPLEXITY_SCORE = 5
⋮----
# Analysis pipeline progress stages
PROGRESS_RANKING = 0.25
PROGRESS_ENRICHING = 0.40
PROGRESS_SELECTION = 0.50
PROGRESS_COVERAGE_CHECK = 0.60
PROGRESS_COVERAGE_COMPLETE = 0.75
PROGRESS_RECOMMENDATIONS = 0.85
PROGRESS_STATISTICS = 0.90
⋮----
class HybridSimilarityDefaults
⋮----
"""Defaults for hybrid two-stage similarity pipeline.

    Scientific basis: TACC (Token and AST-based Code Clone detector)
    from ICSE 2023 demonstrates that combining MinHash filtering with
    AST verification yields optimal precision/recall balance.
    """
⋮----
# Stage 1: MinHash filter threshold for early exit
# Code pairs below this threshold skip Stage 2 (AST verification)
MINHASH_EARLY_EXIT_THRESHOLD = 0.5
⋮----
# Stage 2 weights for combining MinHash and AST similarity
# Must sum to 1.0. AST gets higher weight due to structural precision.
MINHASH_WEIGHT = 0.4
AST_WEIGHT = 0.6
⋮----
# Weight validation
WEIGHT_SUM_TARGET = 1.0
WEIGHT_SUM_TOLERANCE = 0.001
⋮----
# LSH threshold floor to prevent overly aggressive filtering
LSH_THRESHOLD_FLOOR = 0.1
⋮----
# Minimum token count to use hybrid approach
# Very short code snippets may not benefit from AST analysis
MIN_TOKENS_FOR_AST = 10
⋮----
# Maximum code length (lines) for AST analysis
# Very long code may be too expensive for detailed AST comparison
MAX_LINES_FOR_FULL_AST = 500
⋮----
# AST tree edit distance normalization factor
# Used to convert raw edit distance to 0-1 similarity score
TREE_EDIT_DISTANCE_NORMALIZATION = 100
⋮----
class SemanticSimilarityDefaults
⋮----
"""Defaults for CodeBERT-based semantic similarity (Phase 5).

    Scientific basis: GraphCodeBERT (2024) produces 768-dimensional
    embeddings capturing semantic meaning for Type-4 clone detection.

    Note: Semantic similarity is OPTIONAL and requires:
    - transformers library
    - torch (PyTorch)
    - GPU recommended for performance

    Install with: pip install ast-grep-mcp[semantic]
    """
⋮----
# Whether semantic similarity is enabled by default
# Set to False to require explicit opt-in
ENABLE_SEMANTIC = False
⋮----
# Weight for semantic similarity in three-stage hybrid score
# When enabled, weights are rebalanced: MinHash (0.2), AST (0.5), Semantic (0.3)
SEMANTIC_WEIGHT = 0.3
⋮----
# Rebalanced weights when semantic is enabled (must sum to 1.0)
MINHASH_WEIGHT_WITH_SEMANTIC = 0.2
AST_WEIGHT_WITH_SEMANTIC = 0.5
⋮----
# Minimum similarity from Stage 2 (AST) to proceed to Stage 3 (Semantic)
# This provides a second early-exit point to avoid expensive model inference
SEMANTIC_STAGE_THRESHOLD = 0.6
⋮----
# Medium semantic similarity baseline used for heuristic comparisons/reporting
MEDIUM_SIMILARITY_THRESHOLD = 0.85
⋮----
# Default model for CodeBERT embeddings
MODEL_NAME = "microsoft/codebert-base"
⋮----
# Maximum token length for CodeBERT input
MAX_TOKEN_LENGTH = 512
⋮----
# Device selection: 'auto', 'cpu', 'cuda', or 'mps'
DEFAULT_DEVICE = "auto"
⋮----
# Whether to cache embeddings for repeated comparisons
CACHE_EMBEDDINGS = True
⋮----
# Whether to L2-normalize embeddings (recommended for cosine similarity)
NORMALIZE_EMBEDDINGS = True
⋮----
# Embedding vector dimensionality for CodeBERT
EMBEDDING_DIM = 768
⋮----
class SecurityScanDefaults
⋮----
"""Defaults for security scanning."""
⋮----
MAX_ISSUES = 100  # Maximum issues to return
DEFAULT_SEVERITY_THRESHOLD = "low"  # Minimum severity to report
⋮----
# Confidence thresholds
VERY_HIGH_CONFIDENCE = 0.95
HIGH_CONFIDENCE = 0.9
ELEVATED_CONFIDENCE = 0.85  # High confidence with moderate residual uncertainty
DEFAULT_CONFIDENCE = 0.8
MEDIUM_CONFIDENCE = 0.7
LOW_CONFIDENCE = 0.5
⋮----
class SemanticVolumeDefaults
⋮----
"""Shared list-volume limits from high-overlap magic-number clusters."""
⋮----
TOP_RESULTS_LIMIT = 5
DETAIL_RESULTS_LIMIT = 20
SUMMARY_PREVIEW_LIMIT = 50
MAGIC_NUMBER_SAMPLE_LIMIT = 50
⋮----
class CodeQualityDefaults
⋮----
"""Defaults for code quality analysis."""
⋮----
# Code smell thresholds
LONG_FUNCTION_LINES = 50
PARAMETER_COUNT = 5
NESTING_DEPTH = 4
CLASS_LINES = 300
CLASS_METHODS = 20
⋮----
# Magic numbers to ignore
ALLOWED_MAGIC_NUMBERS = {0, 1, -1, 2, 10, 100, 1000}
⋮----
class LoggingDefaults
⋮----
"""Logging configuration defaults."""
⋮----
DEFAULT_LEVEL = "INFO"
MAX_LOG_SIZE_MB = 10
BACKUP_COUNT = 5  # Number of log files to keep
MAX_BREADCRUMBS = 50  # Maximum Sentry breadcrumbs to keep
⋮----
# Language-specific extensions mapping
LANGUAGE_EXTENSIONS = {
⋮----
# Schema.org constants
SCHEMA_ORG_BASE_URL = "https://schema.org"
SCHEMA_ORG_CONTEXT = "https://schema.org"
⋮----
class FormattingDefaults
⋮----
"""Defaults for code formatting."""
⋮----
ROUNDING_PRECISION = 3  # Decimal places for execution times, hit rates
SIMILARITY_PRECISION = 4  # Decimal places for similarity scores
BENCHMARK_PRECISION = 6  # Decimal places for benchmark timing
DEFAULT_DIFF_CONTEXT_LINES = 3  # Context lines in unified diffs
BLACK_LINE_LENGTH = 88  # Black formatter default
PRETTIER_LINE_LENGTH = 80  # Prettier formatter default
SEPARATOR_LENGTH = 70  # Default CLI separator line length
USAGE_REPORT_WIDTH = 50  # Separator width for usage summary reports
SECTION_DIVIDER_WIDTH = 30  # Subsection divider width in reports
WIDE_SECTION_WIDTH = 80  # Wide separator for enforcement/audit reports
TABLE_SEPARATOR_WIDTH = 40  # Table row separator width
⋮----
class UnifiedDiffRegexGroups
⋮----
"""Capture group indices for unified diff hunk header parsing."""
⋮----
OLD_START = 1
OLD_COUNT = 2
NEW_START = 3
NEW_COUNT = 4
CONTEXT = 5
⋮----
class RegexCaptureGroups
⋮----
"""Generic regex capture group indices for parser helpers."""
⋮----
FIRST = 1
SECOND = 2
THIRD = 3
FOURTH = 4
FIFTH = 5
⋮----
class SeverityRankingDefaults
⋮----
"""Shared severity ranking maps and fallback rank values."""
⋮----
FALLBACK_RANK = 3
SECURITY_SCAN_ORDER = {"critical": 3, "high": 2, "medium": 1, "low": 0}
SMELL_SORT_ORDER = {"high": 0, "medium": 1, "low": 2}
DOC_SYNC_SORT_ORDER = {"error": 0, "warning": 1, "info": 2}
ENFORCER_THRESHOLD_ORDER = {"info": 0, "warning": 1, "error": 2}
⋮----
class DisplayDefaults
⋮----
"""Constants for display and UI elements."""
⋮----
VISUALIZATION_BAR_LENGTH = 10  # Length of ASCII score bars
LOW_SCORE_THRESHOLD = 3  # Score <= this is "low"
MEDIUM_SCORE_THRESHOLD = 6  # Score <= this is "medium"
CONTENT_PREVIEW_LENGTH = 50  # Characters in content previews
ERROR_OUTPUT_PREVIEW_LENGTH = 200  # Characters in error output previews
ERROR_MESSAGE_MAX_LENGTH = 500  # Max characters for stored error messages
AST_TRUNCATION_LENGTH = 500  # Characters for AST structure previews
AST_PREVIEW_MAX_LINES = 15  # Lines in AST preview output
MAX_CHILD_KINDS = 10  # Max child kinds to return in analysis
MAX_LITERALS = 5  # Max literals to return in analysis
MAX_IDENTIFIERS = 10  # Max identifiers to return in analysis
MAX_PATTERN_REPLACEMENTS = 3  # Max literal replacements in patterns
MAX_PATTERN_IDENTIFIERS = 5  # Max identifier replacements in patterns
SHORT_IDENTIFIER_THRESHOLD = 4  # Length threshold for short identifiers
⋮----
class PerformanceDefaults
⋮----
"""Defaults for performance monitoring."""
⋮----
SLOW_EXECUTION_THRESHOLD_MS = 5000  # 5 seconds
DEFAULT_SLOW_THRESHOLD_MS = 1000  # 1 second default for track_slow_operations
DATABASE_TIMEOUT_SECONDS = 30.0  # SQLite/HTTP connection timeout
⋮----
class BenchmarkExpectationDefaults
⋮----
"""Expected performance-improvement thresholds for benchmark scripts."""
⋮----
BATCH_SEQUENTIAL_IMPROVEMENT_MIN_PERCENT = 40
BATCH_SEQUENTIAL_IMPROVEMENT_MAX_PERCENT = 50
BATCH_PARALLEL_IMPROVEMENT_MIN_PERCENT = 60
BATCH_PARALLEL_IMPROVEMENT_MAX_PERCENT = 80
⋮----
# Classification thresholds for reporting benchmark outcomes
BATCH_PARALLEL_PARTIAL_MIN_PERCENT = 40
BATCH_PARALLEL_PASS_MIN_PERCENT = 60
⋮----
class CodeAnalysisDefaults
⋮----
"""Defaults for code structure analysis."""
⋮----
SIMPLE_CODE_DEPTH_THRESHOLD = 3
SIMPLE_CODE_LINES_THRESHOLD = 3
MEDIUM_CODE_DEPTH_THRESHOLD = 6
MEDIUM_CODE_LINES_THRESHOLD = 10
DEFAULT_COMPLEXITY_SCORE = 5  # Default complexity when unknown
⋮----
class ComplexityLevelDefaults
⋮----
"""Thresholds for classifying complexity into low/medium/high."""
⋮----
LOW_THRESHOLD = 5  # Score below this is "low"
MEDIUM_THRESHOLD = 10  # Score below this is "medium"
⋮----
class SmellSeverityDefaults
⋮----
"""Thresholds for code smell severity classification."""
⋮----
HIGH_RATIO_THRESHOLD = 2.0  # metric/threshold ratio above this is "high"
MEDIUM_RATIO_THRESHOLD = 1.5  # metric/threshold ratio above this is "medium"
⋮----
class UsageTrackingDefaults
⋮----
"""Defaults for usage tracking and alerting."""
⋮----
DAILY_CALLS_WARNING = 1000
DAILY_CALLS_CRITICAL = 5000
DAILY_COST_WARNING = 1.0
DAILY_COST_CRITICAL = 5.0
HOURLY_FAILURES_WARNING = 10
HOURLY_FAILURES_CRITICAL = 50
FAILURE_RATE_WARNING = 0.1  # 10%
FAILURE_RATE_CRITICAL = 0.25  # 25%
USAGE_ID_HASH_LENGTH = 16
AVG_RESPONSE_TIME_WARNING_MS = 5000
AVG_RESPONSE_TIME_CRITICAL_MS = 30000
DEFAULT_PAGINATION_LIMIT = 100
DEFAULT_STATS_LOOKBACK_DAYS = 7
⋮----
class ReportingDefaults
⋮----
"""Defaults for deduplication reporting."""
⋮----
SIGNIFICANT_LINES_SAVED_THRESHOLD = 50
MANY_DUPLICATES_THRESHOLD = 5
⋮----
class SEODefaults
⋮----
"""Defaults for SEO scoring in schema enhancement."""
⋮----
BASE_SCORE = 100.0
BONUS_INCREMENT = 5.0
FALLBACK_AVG_ENTITY_SCORE = 50.0
DEFAULT_PRIORITY_ORDER = 4
⋮----
class SentryDefaults
⋮----
"""Defaults for Sentry monitoring configuration."""
⋮----
PRODUCTION_TRACES_SAMPLE_RATE = 0.1
PRODUCTION_PROFILES_SAMPLE_RATE = 0.1
⋮----
class DocstringDefaults
⋮----
"""Defaults for docstring generation."""
⋮----
BASIC_INFERENCE_CONFIDENCE = 0.8
⋮----
class IndentationDefaults
⋮----
"""Indentation analysis defaults."""
⋮----
SPACES_PER_LEVEL = 4
ALT_SPACES_PER_LEVEL = 2
NORMALIZATION_DIVISOR = 2
⋮----
class MinHashDefaults
⋮----
"""MinHash algorithm configuration."""
⋮----
NUM_PERMUTATIONS = 128
SHINGLE_SIZE = 3
SMALL_CODE_TOKEN_THRESHOLD = 20
SEQUENCEMATCHER_TOKEN_THRESHOLD = 15  # Below this, use SequenceMatcher instead of MinHash
LSH_RECALL_MARGIN = 0.2  # LSH threshold margin below min_similarity for recall
MAX_FALLBACK_ITEMS = 100  # Max items before all-pairs O(n²) becomes too expensive
⋮----
class ASTFingerprintDefaults
⋮----
"""AST structural fingerprinting configuration."""
⋮----
MAX_NODE_SEQUENCE_LENGTH = 20
MAX_COMPLEXITY_HEX_VALUE = 15
MAX_NESTING_DEPTH_DIGIT = 9
HASH_MODULO = 10000
HASH_BUCKET_MULTIPLIER = 100
MAX_UNIQUE_CALLS = 10
CALL_SIGNATURE_BITMASK = 0xFFFF
CALL_SIGNATURE_HEX_WIDTH = 4
⋮----
class RankerDefaults
⋮----
"""Deduplication ranker scoring configuration."""
⋮----
SAVINGS_NORMALIZATION_DIVISOR = 5
MAX_NORMALIZED_SCORE = 100
COMPLEXITY_INVERSION_FACTOR = 16.67
DEFAULT_MIDDLE_SCORE = 50.0
EFFORT_INSTANCE_PENALTY = 5
EFFORT_FILE_PENALTY = 10
⋮----
class RiskMultipliers
⋮----
"""Risk score multipliers for deduplication."""
⋮----
LOW = 1.0
MEDIUM = 0.7
HIGH = 0.3
⋮----
class RecommendationDefaults
⋮----
"""Deduplication recommendation configuration."""
⋮----
EXTRACT_FUNCTION_BASE_SCORE = 70.0
EXTRACT_CLASS_BASE_SCORE = 50.0
INLINE_BASE_SCORE = 30.0
EFFORT_COMPLEXITY_WEIGHT = 0.3
EFFORT_FILES_WEIGHT = 0.5
NO_TESTS_EFFORT_MULTIPLIER = 1.5
VALUE_LINES_WEIGHT = 0.4
VALUE_FILES_BONUS = 10
HIGH_PRIORITY_SCORE_THRESHOLD = 80
MEDIUM_PRIORITY_SCORE_THRESHOLD = 50
HIGH_SIMILARITY_THRESHOLD = 0.85
DEFAULT_SIMILARITY = 0.9
MODULE_EXTRACTION_DUPLICATE_THRESHOLD = 3
CLASS_EXTRACTION_LINE_THRESHOLD = 20
⋮----
# Extract function scoring thresholds
EXTRACT_FN_LOW_COMPLEXITY = 5
EXTRACT_FN_LOW_COMPLEXITY_BONUS = 20
EXTRACT_FN_HIGH_COMPLEXITY = 10
EXTRACT_FN_HIGH_COMPLEXITY_PENALTY = -20
EXTRACT_FN_LINES_BONUS_THRESHOLD = 10
EXTRACT_FN_LINES_BONUS = 10
EXTRACT_FN_FILES_THRESHOLD = 3
EXTRACT_FN_FILES_BONUS = 10
⋮----
# Extract class scoring thresholds
EXTRACT_CLS_HIGH_COMPLEXITY = 10
EXTRACT_CLS_HIGH_COMPLEXITY_BONUS = 30
EXTRACT_CLS_MID_COMPLEXITY_LOWER = 5
EXTRACT_CLS_MID_COMPLEXITY_BONUS = 15
EXTRACT_CLS_LINES_THRESHOLD = 20
EXTRACT_CLS_LINES_BONUS = 15
EXTRACT_CLS_FILES_THRESHOLD = 2
EXTRACT_CLS_FILES_BONUS = 10
EXTRACT_CLS_LOW_COMPLEXITY = 3
EXTRACT_CLS_LOW_LINES = 10
EXTRACT_CLS_LOW_EFFORT_PENALTY = -20
⋮----
# Inline scoring thresholds
INLINE_LOW_SIMILARITY = 40
INLINE_LOW_SIMILARITY_BONUS = 40
INLINE_MID_SIMILARITY_UPPER = 60
INLINE_MID_SIMILARITY_BONUS = 20
INLINE_SINGLE_FILE_BONUS = 20
INLINE_SMALL_LINES_THRESHOLD = 5
INLINE_SMALL_LINES_BONUS = 20
INLINE_HIGH_SIMILARITY = 80
INLINE_HIGH_SIMILARITY_PENALTY = -30
⋮----
class ChangelogDefaults
⋮----
"""Changelog generator configuration."""
⋮----
COMMIT_PARTS_COUNT = 6
⋮----
class ReadmeSectionOrder
⋮----
"""Section ordering for README generation."""
⋮----
FEATURES = 5
INSTALLATION = 10
USAGE = 20
API_REFERENCE = 30
PROJECT_STRUCTURE = 40
CONTRIBUTING = 50
LICENSE = 60
⋮----
class ReadmeDefaults
⋮----
"""README generation defaults."""
⋮----
MAX_DEPENDENCIES = 10
⋮----
class SyntaxValidationDefaults
⋮----
"""Syntax validation timeouts and limits."""
⋮----
NODE_TIMEOUT_SECONDS = 5
TSC_TIMEOUT_SECONDS = 10
JAVAC_TIMEOUT_SECONDS = 10
JAVAC_ERROR_PREVIEW_LENGTH = 500
TSC_SYNTAX_ERROR_PATTERN = r"error TS1\d{3}:"
⋮----
class SubprocessDefaults
⋮----
"""Default timeouts for subprocess operations."""
⋮----
GREP_TIMEOUT_SECONDS = 10
AST_GREP_TIMEOUT_SECONDS = 30
⋮----
class LogBucketThresholds
⋮----
"""Logarithmic bucket boundaries for code size classification."""
⋮----
TINY = 5
SMALL = 10
MEDIUM = 20
LARGE = 40
VERY_LARGE = 80
HUGE = 160
MASSIVE = 320
OVERFLOW_BASE_BUCKET = 7
MAX_BUCKET = 9
⋮----
class DifficultyThresholds
⋮----
"""Complexity-based difficulty classification thresholds."""
⋮----
SIMPLE = 3
MODERATE = 4
COMPLEX = 5
⋮----
class PriorityWeights
⋮----
"""Weights for priority calculation in deduplication reporting."""
⋮----
OCCURRENCE_WEIGHT = 10
LINE_WEIGHT = 2
COMPLEXITY_PENALTY = 3
⋮----
class CrossLanguageDefaults
⋮----
"""Defaults for cross-language analysis."""
⋮----
MAX_RESULTS_PER_LANGUAGE = 100  # Maximum results returned per language in multi-language search
⋮----
class EquivalenceDefaults
⋮----
"""Cross-language pattern equivalence defaults."""
⋮----
SIMPLE_LINE_THRESHOLD = 2
MODERATE_LINE_THRESHOLD = 5
⋮----
class ExampleDataDefaults
⋮----
"""Shared sample data values used in cross-language examples."""
⋮----
PERSON_AGE = 30
NUMERIC_EXAMPLE = 42
⋮----
class DetectorDefaults
⋮----
"""Deduplication detector defaults."""
⋮----
UTILITY_FUNCTION_LINE_THRESHOLD = 10
⋮----
class ComplexityStorageDefaults
⋮----
"""Defaults for complexity trend storage and queries."""
⋮----
TRENDS_LOOKBACK_DAYS = 30  # Default lookback period for trend queries
⋮----
class RuleSetPriority
⋮----
"""Execution priority ordering for rule sets (higher = runs first)."""
⋮----
SECURITY = 200  # Security rules run first
CUSTOM = 150  # Custom rules after security
RECOMMENDED = 100  # Recommended/all rules
PERFORMANCE = 50  # Performance rules
STYLE = 10  # Style rules run last
⋮----
class PatternSuggestionConfidence
⋮----
"""Confidence scores for pattern suggestion types."""
⋮----
EXACT_SIMPLE = 0.9  # Exact match for simple code
EXACT_COMPLEX = 0.7  # Exact match for complex code
GENERALIZED = 0.8  # Generalized pattern with metavariables
STRUCTURAL = 0.6  # Structural (kind-based) pattern
PATTERN_MATCH = SecurityScanDefaults.ELEVATED_CONFIDENCE  # Security pattern match confidence
UNKNOWN_FIX = 0.5  # Unknown fix pattern (conservative)
⋮----
class CondenseDefaults
⋮----
"""Defaults for code condensation pipeline."""
⋮----
DEFAULT_STRATEGY = "ai_analysis"
⋮----
# Extraction
INCLUDE_DOCSTRINGS = True
⋮----
# Normalization
NORMALIZE_STRING_QUOTES = True
NORMALIZE_TRAILING_COMMAS = True
⋮----
# Strip targets
STRIP_CONSOLE_LOG = True
STRIP_DEBUG_STATEMENTS = True
STRIP_EMPTY_LINES = True
⋮----
# Limits
MAX_FILE_SIZE_BYTES = 1_048_576  # 1 MB; skip larger files
MAX_FILES_PER_RUN = 500
⋮----
# Estimation
AVG_TOKENS_PER_BYTE = 0.25  # Rough approximation for token counting
⋮----
# Complexity-guided extraction thresholds (cyclomatic)
COMPLEXITY_STRIP_THRESHOLD = 10  # ≤10 cyclomatic → signature + docstring only
# >10 cyclomatic → keep full body
⋮----
class CondenseDictionaryDefaults
⋮----
"""Defaults for zstd dictionary training."""
⋮----
SAMPLE_COUNT = 200
MAX_SAMPLE_SIZE_BYTES = 102_400  # 100 KB per sample
DICT_SIZE_BYTES = 112_640  # 110 KB (zstd default)
DICT_OUTPUT_DIR = ".condense/dictionaries"
⋮----
class CondenseFileRouting
⋮----
"""File-type routing for polyglot condensation."""
⋮----
CODE_EXTENSIONS = frozenset(
CONFIG_EXTENSIONS = frozenset(
TEXT_EXTENSIONS = frozenset({".md", ".txt", ".rst", ".adoc"})
IMAGE_EXTENSIONS = frozenset(
EXCLUDE_PATTERNS = [
TEST_PATTERNS = [
⋮----
# HTTP constants
DEFAULT_USER_AGENT = "ast-grep-mcp/1.0"
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1
````