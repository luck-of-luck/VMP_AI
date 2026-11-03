"""Data models for refactoring operations."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class VariableType(Enum):
    """Classification of variables in code selection."""

    LOCAL = "local"  # Defined and used only within selection
    PARAMETER = "parameter"  # Used but not defined in selection (needs to be parameter)
    MODIFIED = "modified"  # Modified within selection (needs to be returned)
    GLOBAL = "global"  # Global or module-level variable
    CLOSURE = "closure"  # From enclosing scope


class RefactoringType(Enum):
    """Types of refactoring operations."""

    EXTRACT_FUNCTION = "extract_function"
    EXTRACT_METHOD = "extract_method"
    RENAME_SYMBOL = "rename_symbol"
    CONVERT_STYLE = "convert_style"
    SIMPLIFY_CONDITIONALS = "simplify_conditionals"


@dataclass
class VariableInfo:
    """Information about a variable in code selection."""

    name: str
    variable_type: VariableType
    first_use_line: int
    is_read: bool = False
    is_written: bool = False
    inferred_type: Optional[str] = None
    scope_depth: int = 0


@dataclass
class CodeSelection:
    """Represents a selection of code for refactoring."""

    file_path: str
    start_line: int
    end_line: int
    language: str
    content: str
    indentation: str = ""

    # Analysis results
    variables: List[VariableInfo] = field(default_factory=list)
    parameters_needed: List[str] = field(default_factory=list)
    return_values: List[str] = field(default_factory=list)
    has_early_returns: bool = False
    has_exceptions: bool = False

    def get_variables_by_type(self, var_type: VariableType) -> List[VariableInfo]:
        """Get all variables of a specific type."""
        return [v for v in self.variables if v.variable_type == var_type]


@dataclass
class FunctionSignature:
    """Generated function signature."""

    name: str
    parameters: List[Dict[str, str]]  # [{"name": "x", "type": "int"}, ...]
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    is_async: bool = False
    decorators: List[str] = field(default_factory=list)

    def to_python_signature(self) -> str:
        """Generate Python function signature."""
        params = ", ".join(f"{p['name']}: {p['type']}" if p.get("type") else p["name"] for p in self.parameters)

        ret = f" -> {self.return_type}" if self.return_type else ""
        async_prefix = "async " if self.is_async else ""

        return f"{async_prefix}def {self.name}({params}){ret}:"

    def to_typescript_signature(self) -> str:
        """Generate TypeScript function signature."""
        params = ", ".join(f"{p['name']}: {p['type']}" if p.get("type") else p["name"] for p in self.parameters)

        ret = f": {self.return_type}" if self.return_type else ""
        async_prefix = "async " if self.is_async else ""

        return f"{async_prefix}function {self.name}({params}){ret} {{"


@dataclass
class ExtractFunctionResult:
    """Result of extract function operation."""

    success: bool
    function_signature: Optional[FunctionSignature] = None
    function_body: Optional[str] = None
    call_site_replacement: Optional[str] = None
    insertion_line: Optional[int] = None
    diff_preview: Optional[str] = None
    backup_id: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class ScopeInfo:
    """Information about a scope in the code."""

    scope_type: str  # 'module', 'class', 'function', 'block'
    scope_name: str
    start_line: int
    end_line: int
    parent_scope: Optional[str] = None
    defined_symbols: Set[str] = field(default_factory=set)


@dataclass
class SymbolReference:
    """Reference to a symbol in code."""

    file_path: str
    line: int
    column: int
    context: str  # Surrounding code for context
    scope: str  # Function/class/module scope
    is_definition: bool = False
    is_import: bool = False
    is_export: bool = False
    import_source: Optional[str] = None  # For imports: where it's imported from


@dataclass
class RenameSymbolResult:
    """Result of rename symbol operation."""

    success: bool
    old_name: str
    new_name: str
    references_found: int = 0
    references_updated: int = 0
    files_modified: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    diff_preview: Optional[str] = None
    backup_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class StyleConversion:
    """Configuration for style conversion."""

    conversion_type: str
    source_language: str
    target_style: Optional[str] = None
    preserve_comments: bool = True
    preserve_formatting: bool = True
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversionResult:
    """Result of code style conversion."""

    success: bool
    files_converted: int = 0
    files_modified: List[str] = field(default_factory=list)
    diff_preview: Optional[str] = None
    backup_id: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    conversion_stats: Dict[str, int] = field(default_factory=dict)


@dataclass
class SimplificationResult:
    """Result of conditional simplification."""

    success: bool
    complexity_before: int = 0
    complexity_after: int = 0
    simplifications_applied: int = 0
    files_modified: List[str] = field(default_factory=list)
    diff_preview: Optional[str] = None
    backup_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class RefactoringStep:
    """Single step in batch refactoring."""

    step_id: int
    refactoring_type: RefactoringType
    parameters: Dict[str, Any]
    depends_on: List[int] = field(default_factory=list)  # Step IDs this depends on


@dataclass
class BatchRefactoringResult:
    """Result of batch refactoring operation."""

    success: bool
    steps_completed: int = 0
    steps_total: int = 0
    results: List[Dict[str, Any]] = field(default_factory=list)
    combined_diff: Optional[str] = None
    backup_id: Optional[str] = None
    error: Optional[str] = None
    rollback_performed: bool = False
