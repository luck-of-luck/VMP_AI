"""Data models for code deduplication functionality."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ast_grep_mcp.constants import DisplayDefaults


class VariationCategory:
    """Categories for classifying variations between duplicate code blocks."""

    LITERAL = "LITERAL"  # string, number, boolean differences
    IDENTIFIER = "IDENTIFIER"  # variable/function/class name differences
    EXPRESSION = "EXPRESSION"  # operator, call, compound expression differences
    LOGIC = "LOGIC"  # control flow differences (if/else, loops)
    TYPE = "TYPE"  # type annotation differences


class VariationSeverity:
    """Severity levels for variations."""

    LOW = "low"  # Minor differences, easy to parameterize
    MEDIUM = "medium"  # Moderate differences, requires some refactoring
    HIGH = "high"  # Significant differences, complex refactoring needed


@dataclass
class AlignmentSegment:
    """Represents a segment in the alignment between two code blocks."""

    segment_type: str  # 'aligned', 'divergent', 'inserted', 'deleted'
    block1_start: int  # Line number in block 1 (0-indexed, -1 if N/A)
    block1_end: int  # End line in block 1 (exclusive)
    block2_start: int  # Line number in block 2 (0-indexed, -1 if N/A)
    block2_end: int  # End line in block 2 (exclusive)
    block1_text: str  # Text from block 1
    block2_text: str  # Text from block 2
    metadata: Optional[Dict[str, Any]] = None  # Multi-line info, construct types, etc.

    def __post_init__(self) -> None:
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


@dataclass
class AlignmentResult:
    """Result of aligning two code blocks for comparison."""

    segments: List[AlignmentSegment]
    similarity_ratio: float
    aligned_lines: int
    divergent_lines: int
    block1_total_lines: int
    block2_total_lines: int


@dataclass
class DiffTreeNode:
    """A node in a hierarchical diff tree structure.

    Represents code differences hierarchically, allowing nested structures
    to be represented with parent-child relationships.
    """

    node_type: str  # 'aligned', 'divergent', 'inserted', 'deleted', 'container'
    content: str  # The code content for this node
    children: List["DiffTreeNode"]  # Child nodes for nested structures
    metadata: Dict[str, Any]  # Additional metadata (line numbers, similarity, etc.)

    def __post_init__(self) -> None:
        """Ensure children is a mutable list."""
        if self.children is None:
            self.children = []

    def add_child(self, child: "DiffTreeNode") -> None:
        """Add a child node."""
        self.children.append(child)

    def get_all_nodes(self) -> List["DiffTreeNode"]:
        """Get all nodes in the tree (depth-first traversal)."""
        result = [self]
        for child in self.children:
            result.extend(child.get_all_nodes())
        return result

    def find_by_type(self, node_type: str) -> List["DiffTreeNode"]:
        """Find all nodes of a specific type."""
        return [node for node in self.get_all_nodes() if node.node_type == node_type]

    def get_depth(self) -> int:
        """Get the maximum depth of the tree from this node."""
        if not self.children:
            return 0
        return 1 + max(child.get_depth() for child in self.children)

    def count_by_type(self) -> Dict[str, int]:
        """Count nodes by type in the subtree."""
        counts: Dict[str, int] = {}
        for node in self.get_all_nodes():
            counts[node.node_type] = counts.get(node.node_type, 0) + 1
        return counts


@dataclass
class DiffTree:
    """Hierarchical representation of code differences.

    A tree structure that represents differences between duplicate code blocks
    in a hierarchical manner, preserving nesting and structure.
    """

    root: DiffTreeNode
    file1_path: str
    file2_path: str
    file1_lines: List[str]
    file2_lines: List[str]
    alignment_result: AlignmentResult

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the diff tree."""
        type_counts = self.root.count_by_type()
        divergent_nodes = self.root.find_by_type("divergent")

        return {
            "total_nodes": len(self.root.get_all_nodes()),
            "max_depth": self.root.get_depth(),
            "type_counts": type_counts,
            "divergent_count": len(divergent_nodes),
            "similarity_ratio": self.alignment_result.similarity_ratio,
            "aligned_lines": self.alignment_result.aligned_lines,
            "divergent_lines": self.alignment_result.divergent_lines,
        }

    _NODE_SYMBOLS = {"aligned": "=", "divergent": "≠", "inserted": "+", "deleted": "-", "container": "◊"}

    def _serialize_node_lines(self, node: DiffTreeNode, indent: str) -> List[str]:
        symbol = self._NODE_SYMBOLS.get(node.node_type, "?")
        lines = [f"{indent}{symbol} {node.node_type.upper()}"]
        if "line_nums" in node.metadata:
            lines.append(f"{indent}  Lines: {node.metadata['line_nums']}")
        if "similarity" in node.metadata:
            lines.append(f"{indent}  Similarity: {node.metadata['similarity']:.1%}")
        if node.content:
            preview = node.content.strip().split("\n")[0][: DisplayDefaults.CONTENT_PREVIEW_LENGTH]
            if preview:
                lines.append(f"{indent}  > {preview}...")
        return lines

    def serialize_for_display(self, node: Optional[DiffTreeNode] = None, depth: int = 0) -> List[str]:
        """Serialize the tree for human-readable display."""
        if node is None:
            node = self.root
        indent = "  " * depth
        lines = self._serialize_node_lines(node, indent)
        for child in node.children:
            lines.extend(self.serialize_for_display(child, depth + 1))
        return lines


@dataclass
class FunctionTemplate:
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

    name: str
    parameters: List[Tuple[str, Optional[str]]]
    body: str
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    decorators: Optional[List[str]] = None

    def __post_init__(self) -> None:
        """Validate function template after initialization."""
        # Ensure function name is a valid identifier
        if not self.name.isidentifier():
            raise ValueError(f"Function name '{self.name}' is not a valid identifier")

        # Ensure parameters have valid names
        for param_name, _ in self.parameters:
            if not param_name.isidentifier():
                raise ValueError(f"Parameter name '{param_name}' is not a valid identifier")

        # Initialize decorators list if needed
        if self.decorators is None:
            self.decorators = []

    def format_params(self) -> str:
        """Format parameters as a comma-separated string for function signature.

        Returns:
            Formatted parameter string like "a: int, b, c: str"
        """
        parts = []
        for param_name, param_type in self.parameters:
            if param_type:
                parts.append(f"{param_name}: {param_type}")
            else:
                parts.append(param_name)
        return ", ".join(parts)

    def format_decorators(self) -> str:
        """Format decorators as lines with @ prefix.

        Returns:
            Decorator lines with newlines, or empty string if no decorators
        """
        if not self.decorators:
            return ""
        return "\n".join(f"@{dec}" for dec in self.decorators) + "\n"

    def format_return_type(self) -> str:
        """Format return type annotation.

        Returns:
            Return type string like " -> int" or empty string if no return type
        """
        if self.return_type:
            return f" -> {self.return_type}"
        return ""

    def _indented_body_lines(self) -> List[str]:
        return [f"    {line}" if line.strip() else "" for line in self.body.split("\n")]

    def generate(self) -> str:
        """Generate the complete function code from the template.

        Returns:
            Formatted Python function code
        """
        lines = []
        if self.decorators:
            lines.append(self.format_decorators().rstrip())
        params = self.format_params()
        return_annotation = self.format_return_type()
        lines.append(f"def {self.name}({params}){return_annotation}:")
        if self.docstring:
            lines.append(f'    """{self.docstring}"""')
        lines.extend(self._indented_body_lines())
        return "\n".join(lines)


class ParameterType:
    """Represents an inferred type for an extracted parameter."""

    # Simple type constants for backward compatibility
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    LIST = "list"
    DICT = "dict"
    ANY = "any"

    # Common types for different languages
    PYTHON_TYPES = {"string": "str", "number": "float", "integer": "int", "boolean": "bool", "list": "List", "dict": "Dict", "any": "Any"}

    TYPESCRIPT_TYPES = {
        "string": "string",
        "number": "number",
        "integer": "number",
        "boolean": "boolean",
        "list": "Array",
        "dict": "object",
        "any": "any",
    }

    JAVA_TYPES = {
        "string": "String",
        "number": "double",
        "integer": "int",
        "boolean": "boolean",
        "list": "List",
        "dict": "Map",
        "any": "Object",
    }

    def __init__(self, base_type: str, language: str = "python") -> None:
        """Initialize parameter type.

        Args:
            base_type: Base type identifier ('string', 'number', etc.)
            language: Target language for type annotation
        """
        self.base_type = base_type
        self.language = language
        self._type_map = self._get_type_map()

    def _get_type_map(self) -> Dict[str, str]:
        """Get the appropriate type map for the language."""
        if self.language.lower() == "python":
            return self.PYTHON_TYPES
        elif self.language.lower() in ["typescript", "javascript"]:
            return self.TYPESCRIPT_TYPES
        elif self.language.lower() == "java":
            return self.JAVA_TYPES
        else:
            return self.PYTHON_TYPES  # Default to Python

    def get_type_annotation(self) -> str:
        """Get the type annotation for the current language."""
        return self._type_map.get(self.base_type, self._type_map["any"])

    def __str__(self) -> str:
        """String representation of the type."""
        return self.get_type_annotation()


class ParameterInfo:
    """Represents a parameter for code generation with type information."""

    def __init__(self, name: str, param_type: Optional[ParameterType] = None, default_value: Optional[str] = None) -> None:
        """Initialize parameter info.

        Args:
            name: Parameter name
            param_type: Optional type information
            default_value: Optional default value
        """
        self.name = name
        self.param_type = param_type
        self.default_value = default_value

    def _sig_with_type_and_default(self, include_type: bool) -> str:
        sig = self.name
        if include_type and self.param_type:
            sig += f": {self.param_type.get_type_annotation()}"
        if self.default_value:
            sig += f" = {self.default_value}"
        return sig

    def to_signature(self, language: str = "python") -> str:
        """Generate parameter signature for function declaration.

        Args:
            language: Target language

        Returns:
            Parameter signature string
        """
        lang = language.lower()
        if lang == "python":
            return self._sig_with_type_and_default(include_type=True)
        if lang in ("typescript", "javascript"):
            return self._sig_with_type_and_default(include_type=(lang == "typescript"))
        if lang == "java":
            if self.param_type:
                return f"{self.param_type.get_type_annotation()} {self.name}"
            return f"Object {self.name}"
        return self.name


@dataclass
class FileDiff:
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

    file_path: str
    original_content: str
    new_content: str
    unified_diff: str
    formatted_diff: str
    hunks: List[Dict[str, Any]]
    additions: int
    deletions: int


@dataclass
class DiffPreview:
    """Container for multi-file diff preview.

    Attributes:
        file_diffs: List of individual file diffs
        total_additions: Total lines added across all files
        total_deletions: Total lines deleted across all files
        affected_files: List of affected file paths
        summary: Human-readable summary of changes
        colorized_output: Full colorized diff output for display
    """

    file_diffs: List[FileDiff]
    total_additions: int
    total_deletions: int
    affected_files: List[str]
    summary: str
    colorized_output: str

    @staticmethod
    def _file_diff_to_dict(fd: "FileDiff") -> Dict[str, Any]:
        return {
            "file_path": fd.file_path,
            "additions": fd.additions,
            "deletions": fd.deletions,
            "unified_diff": fd.unified_diff,
            "formatted_diff": fd.formatted_diff,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "file_diffs": [self._file_diff_to_dict(fd) for fd in self.file_diffs],
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "affected_files": self.affected_files,
            "summary": self.summary,
            "colorized_output": self.colorized_output,
        }

    def get_file_diff(self, file_path: str) -> Optional[FileDiff]:
        """Get diff for a specific file."""
        for fd in self.file_diffs:
            if fd.file_path == file_path:
                return fd
        return None


@dataclass
class EnhancedDuplicationCandidate:
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

    def to_summary(self) -> Dict[str, Any]:
        """Create a summary dictionary for concise reporting."""
        return {
            "rank": self.priority_rank,
            "score": self.score,
            "risk": self.risk_level,
            "savings": self.estimated_savings,
            "instances": len(self.instances),
            "test_coverage": self.test_coverage,
            "recommended_strategy": self.strategies[0]["strategy"] if self.strategies else "unknown",
        }
