"""Data models for orphan code detection.

This module provides models for representing orphan files and functions
detected during codebase analysis.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from ast_grep_mcp.constants import FilePatterns


class OrphanType(str, Enum):
    """Type of orphan artifact."""

    FILE = "file"
    FUNCTION = "function"
    CLASS = "class"
    VARIABLE = "variable"


class VerificationStatus(str, Enum):
    """Verification status for orphan detection."""

    CONFIRMED = "confirmed"  # Verified as orphan via multiple methods
    LIKELY = "likely"  # High confidence but not fully verified
    UNCERTAIN = "uncertain"  # Possible false positive
    FALSE_POSITIVE = "false_positive"  # Verified as actually used


@dataclass
class OrphanFile:
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

    file_path: str
    absolute_path: str
    lines: int
    language: str
    status: VerificationStatus = VerificationStatus.LIKELY
    reason: str = "No imports found"
    importers: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "file_path": self.file_path,
            "lines": self.lines,
            "language": self.language,
            "status": self.status.value,
            "reason": self.reason,
            "importers": self.importers,
            "exports": self.exports,
        }


@dataclass
class OrphanFunction:
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

    name: str
    file_path: str
    line_start: int
    line_end: int
    status: VerificationStatus = VerificationStatus.LIKELY
    reason: str = "No call sites found"
    callers: List[str] = field(default_factory=list)
    is_exported: bool = False
    is_private: bool = False

    @property
    def lines(self) -> int:
        """Calculate number of lines in the function."""
        return self.line_end - self.line_start + 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "lines": self.lines,
            "status": self.status.value,
            "reason": self.reason,
            "callers": self.callers,
            "is_exported": self.is_exported,
            "is_private": self.is_private,
        }


@dataclass
class DependencyEdge:
    """Represents a dependency between two files.

    Attributes:
        source: Importing file
        target: Imported file
        import_type: Type of import (absolute, relative, dynamic)
        import_statement: The actual import statement
    """

    source: str
    target: str
    import_type: str = "absolute"
    import_statement: str = ""


@dataclass
class DependencyGraph:
    """Represents the import dependency graph.

    Attributes:
        files: All files in the graph
        edges: Import relationships between files
        entry_points: Known entry points (main files, test files, etc.)
        external_imports: External package imports by file
    """

    files: Set[str] = field(default_factory=set)
    edges: List[DependencyEdge] = field(default_factory=list)
    entry_points: Set[str] = field(default_factory=set)
    external_imports: Dict[str, Set[str]] = field(default_factory=dict)
    _importers_index: Dict[str, List[str]] = field(default_factory=dict, repr=False)
    _imports_index: Dict[str, List[str]] = field(default_factory=dict, repr=False)

    def build_index(self) -> None:
        """Build reverse-lookup indexes from edges for O(1) queries."""
        importers: Dict[str, List[str]] = {}
        imports: Dict[str, List[str]] = {}
        for e in self.edges:
            importers.setdefault(e.target, []).append(e.source)
            imports.setdefault(e.source, []).append(e.target)
        self._importers_index = importers
        self._imports_index = imports

    def get_importers(self, file_path: str) -> List[str]:
        """Get all files that import the given file."""
        if self._importers_index:
            return self._importers_index.get(file_path, [])
        return [e.source for e in self.edges if e.target == file_path]

    def get_imports(self, file_path: str) -> List[str]:
        """Get all files imported by the given file."""
        if self._imports_index:
            return self._imports_index.get(file_path, [])
        return [e.target for e in self.edges if e.source == file_path]

    def is_reachable_from_entry(self, file_path: str) -> bool:
        """Check if file is reachable from any entry point."""
        visited: Set[str] = set()
        stack = list(self.entry_points)

        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)

            if current == file_path:
                return True

            stack.extend(self.get_imports(current))

        return False


@dataclass
class OrphanAnalysisConfig:
    """Configuration for orphan analysis.

    Attributes:
        include_patterns: Glob patterns for files to include
        exclude_patterns: Glob patterns for files to exclude
        entry_point_patterns: Patterns for identifying entry points
        analyze_functions: Whether to analyze function-level orphans
        verify_with_grep: Whether to double-check with grep
        languages: Languages to analyze
    """

    include_patterns: List[str] = field(default_factory=lambda: ["**/*.py", "**/*.ts", "**/*.js"])
    exclude_patterns: List[str] = field(default_factory=lambda: list(FilePatterns.DEFAULT_EXCLUDE))
    entry_point_patterns: List[str] = field(
        default_factory=lambda: [
            "**/main.py",
            "**/main.ts",
            "**/index.ts",
            "**/index.js",
            "**/__main__.py",
            "**/cli.py",
            "**/cli.ts",
            "**/app.py",
            "**/app.ts",
            "**/server.py",
            "**/server.ts",
            "**/conftest.py",
            "**/test_*.py",
            "**/*_test.py",
            "**/*.test.ts",
            "**/*.test.js",
            "**/*.spec.ts",
            "**/*.spec.js",
            "**/*-runner.ts",
            "**/*-runner.js",
        ]
    )
    analyze_functions: bool = True
    verify_with_grep: bool = True
    languages: List[str] = field(default_factory=lambda: ["python", "typescript"])


@dataclass
class OrphanAnalysisResult:
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

    orphan_files: List[OrphanFile] = field(default_factory=list)
    orphan_functions: List[OrphanFunction] = field(default_factory=list)
    total_files_analyzed: int = 0
    total_functions_analyzed: int = 0
    dependency_graph: Optional[DependencyGraph] = None
    analysis_time_ms: int = 0
    config: Optional[OrphanAnalysisConfig] = None

    @property
    def total_orphan_lines(self) -> int:
        """Calculate total lines in orphan code."""
        file_lines = sum(f.lines for f in self.orphan_files)
        func_lines = sum(f.lines for f in self.orphan_functions)
        return file_lines + func_lines

    @property
    def orphan_file_count(self) -> int:
        """Count of orphan files."""
        return len(self.orphan_files)

    @property
    def orphan_function_count(self) -> int:
        """Count of orphan functions."""
        return len(self.orphan_functions)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "summary": {
                "orphan_files": self.orphan_file_count,
                "orphan_functions": self.orphan_function_count,
                "total_orphan_lines": self.total_orphan_lines,
                "total_files_analyzed": self.total_files_analyzed,
                "total_functions_analyzed": self.total_functions_analyzed,
                "analysis_time_ms": self.analysis_time_ms,
            },
            "orphan_files": [f.to_dict() for f in self.orphan_files],
            "orphan_functions": [f.to_dict() for f in self.orphan_functions],
        }
