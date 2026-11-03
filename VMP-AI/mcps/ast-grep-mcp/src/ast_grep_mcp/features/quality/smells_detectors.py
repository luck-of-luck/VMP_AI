"""Smell detector implementations using strategy pattern.

This module contains individual detector classes for each type of code smell,
following the strategy pattern for extensibility and maintainability.
"""

import ast
import json
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List

from ast_grep_mcp.constants import SemanticVolumeDefaults, SubprocessDefaults
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.features.complexity.analyzer import calculate_nesting_depth, extract_functions_from_file
from ast_grep_mcp.features.quality.smells_helpers import calculate_smell_severity


@dataclass
class SmellInfo:
    """Information about a detected code smell."""

    type: str
    file: str
    name: str
    line: int
    severity: str
    metric: Any
    threshold: Any
    message: str
    suggestion: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type,
            "file": self.file,
            "name": self.name,
            "line": self.line,
            "severity": self.severity,
            "metric": self.metric,
            "threshold": self.threshold,
            "message": self.message,
            "suggestion": self.suggestion,
        }


class SmellDetector(ABC):
    """Base class for smell detectors."""

    def __init__(self, threshold: int | None, logger_name: str) -> None:
        self.threshold = threshold
        self.logger = get_logger(logger_name)

    @abstractmethod
    def detect(self, file_path: str, content: str, language: str, project_path: Path) -> List[SmellInfo]:
        """Detect smells in the given file.

        Args:
            file_path: Path to the file being analyzed
            content: File content
            language: Programming language
            project_path: Root project path for relative path calculation

        Returns:
            List of detected smell information
        """
        pass


class LongFunctionDetector(SmellDetector):
    """Detects functions that are too long."""

    threshold: int

    def __init__(self, threshold: int) -> None:
        super().__init__(threshold, "smell_detector.long_function")

    def detect(self, file_path: str, content: str, language: str, project_path: Path) -> List[SmellInfo]:
        """Detect long functions in the file."""
        rel_path = str(Path(file_path).relative_to(project_path))
        try:
            funcs = extract_functions_from_file(file_path, language)
            return [s for s in (self._check_func(f, rel_path) for f in funcs) if s]
        except Exception as e:
            self.logger.warning("detection_failed", file=file_path, error=str(e))
            return []

    def _check_func(self, func: Dict[str, Any], rel_path: str) -> SmellInfo | None:
        func_name = func.get("name", "unknown")
        func_start = func.get("start_line", 1)
        func_lines = func.get("end_line", func_start) - func_start + 1
        if func_lines <= self.threshold:
            return None
        severity = calculate_smell_severity(func_lines, self.threshold, "long_function")
        return SmellInfo(
            type="long_function",
            file=rel_path,
            name=func_name,
            line=func_start,
            severity=severity,
            metric=func_lines,
            threshold=self.threshold,
            message=f"Function '{func_name}' has {func_lines} lines (threshold: {self.threshold})",
            suggestion="Consider splitting into smaller, focused functions",
        )


class ParameterBloatDetector(SmellDetector):
    """Detects functions with too many parameters."""

    threshold: int

    def __init__(self, threshold: int) -> None:
        super().__init__(threshold, "smell_detector.parameter_bloat")

    def detect(self, file_path: str, content: str, language: str, project_path: Path) -> List[SmellInfo]:
        """Detect parameter bloat in functions."""
        rel_path = str(Path(file_path).relative_to(project_path))
        try:
            funcs = extract_functions_from_file(file_path, language)
            return [s for s in (self._check_func(f, rel_path, language) for f in funcs) if s]
        except Exception as e:
            self.logger.warning("detection_failed", file=file_path, error=str(e))
            return []

    def _check_func(self, func: Dict[str, Any], rel_path: str, language: str) -> SmellInfo | None:
        func_name = func.get("name", "unknown")
        func_start = func.get("start_line", 1)
        param_count = self._count_parameters(func.get("code", ""), language)
        if param_count <= self.threshold:
            return None
        severity = calculate_smell_severity(param_count, self.threshold, "parameter_bloat")
        return SmellInfo(
            type="parameter_bloat",
            file=rel_path,
            name=func_name,
            line=func_start,
            severity=severity,
            metric=param_count,
            threshold=self.threshold,
            message=f"Function '{func_name}' has {param_count} parameters (threshold: {self.threshold})",
            suggestion="Consider using a parameter object or builder pattern",
        )

    def _count_parameters(self, code: str, language: str) -> int:
        """Count the number of parameters in a function."""
        params = self._extract_param_string(code, language)
        if not params:
            return 0
        return self._count_params_by_depth(params)

    def _extract_param_string(self, code: str, language: str) -> str:
        """Extract and normalize the parameter string from function code."""
        is_python = language.lower() == "python"
        pattern = r"def\s+\w+\s*\(([^)]*)\)" if is_python else r"(?:function\s+\w+|\w+)\s*\(([^)]*)\)"
        match = re.search(pattern, code)
        if not match:
            return ""
        params = match.group(1).strip()
        if not params:
            return ""
        if is_python:
            params = re.sub(r"\bself\b\s*,?\s*", "", params)
            params = re.sub(r"\bcls\b\s*,?\s*", "", params)
        return params.strip()

    @staticmethod
    def _count_params_by_depth(params: str) -> int:
        """Count comma-separated params respecting bracket nesting depth."""
        depth = 0
        count = 1
        for char in params:
            if char in "([{<":
                depth += 1
            elif char in ")]}>":
                depth -= 1
            elif char == "," and depth == 0:
                count += 1
        return count


class DeepNestingDetector(SmellDetector):
    """Detects excessive nesting depth in functions."""

    threshold: int

    def __init__(self, threshold: int) -> None:
        super().__init__(threshold, "smell_detector.deep_nesting")

    def detect(self, file_path: str, content: str, language: str, project_path: Path) -> List[SmellInfo]:
        """Detect deep nesting in functions."""
        rel_path = str(Path(file_path).relative_to(project_path))
        try:
            funcs = extract_functions_from_file(file_path, language)
            return [s for s in (self._check_func(f, rel_path, language) for f in funcs) if s]
        except Exception as e:
            self.logger.warning("detection_failed", file=file_path, error=str(e))
            return []

    def _check_func(self, func: Dict[str, Any], rel_path: str, language: str) -> SmellInfo | None:
        func_name = func.get("name", "unknown")
        func_start = func.get("start_line", 1)
        max_nesting = calculate_nesting_depth(func.get("code", ""), language)
        if max_nesting <= self.threshold:
            return None
        severity = calculate_smell_severity(max_nesting, self.threshold, "deep_nesting")
        return SmellInfo(
            type="deep_nesting",
            file=rel_path,
            name=func_name,
            line=func_start,
            severity=severity,
            metric=max_nesting,
            threshold=self.threshold,
            message=f"Function '{func_name}' has nesting depth {max_nesting} (threshold: {self.threshold})",
            suggestion="Use early returns, extract nested logic, or apply guard clauses",
        )


class LargeClassDetector(SmellDetector):
    """Detects classes that are too large."""

    threshold: int

    def __init__(self, lines_threshold: int, methods_threshold: int) -> None:
        super().__init__(lines_threshold, "smell_detector.large_class")
        self.methods_threshold = methods_threshold

    def detect(self, file_path: str, content: str, language: str, project_path: Path) -> List[SmellInfo]:
        """Detect large classes in the file."""
        rel_path = str(Path(file_path).relative_to(project_path))
        try:
            classes = self._extract_classes(file_path, language)
            return [s for s in (self._check_class(c, rel_path) for c in classes) if s]
        except Exception as e:
            self.logger.warning("detection_failed", file=file_path, error=str(e))
            return []

    def _build_reason(self, lines_count: int, method_count: int) -> str:
        parts = []
        if lines_count > self.threshold:
            parts.append(f"{lines_count} lines (threshold: {self.threshold})")
        if method_count > self.methods_threshold:
            parts.append(f"{method_count} methods (threshold: {self.methods_threshold})")
        return " and ".join(parts)

    def _check_class(self, cls: Dict[str, Any], rel_path: str) -> SmellInfo | None:
        cls_name = cls.get("name", "unknown")
        cls_start = cls.get("start_line", 1)
        cls_lines = cls.get("end_line", cls_start) - cls_start + 1
        method_count = cls.get("method_count", 0)
        lines_over = cls_lines > self.threshold
        methods_over = method_count > self.methods_threshold
        if not lines_over and not methods_over:
            return None
        reason = self._build_reason(cls_lines, method_count)
        severity = calculate_smell_severity(cls_lines, self.threshold, "large_class")
        return SmellInfo(
            type="large_class",
            file=rel_path,
            name=cls_name,
            line=cls_start,
            severity=severity,
            metric={"lines": cls_lines, "methods": method_count},
            threshold={"lines": self.threshold, "methods": self.methods_threshold},
            message=f"Class '{cls_name}' is too large: {reason}",
            suggestion="Consider splitting into smaller classes following Single Responsibility Principle",
        )

    def _extract_classes(self, file_path: str, language: str) -> List[Dict[str, Any]]:
        """Extract all classes from a file using ast-grep."""
        pattern = self._get_class_pattern(language)

        try:
            matches = self._run_ast_grep_for_classes(file_path, language, pattern)
            return self._process_class_matches(matches, language)
        except Exception as e:
            self.logger.warning("extract_classes_failed", file=file_path, error=str(e))
            return []

    def _get_class_pattern(self, language: str) -> str:
        """Get the ast-grep pattern for class detection based on language.

        Args:
            language: Programming language

        Returns:
            Pattern string for ast-grep
        """
        class_patterns = {
            "python": "class $NAME($$$): $$$",
            "typescript": "class $NAME { $$$ }",
            "javascript": "class $NAME { $$$ }",
            "java": "class $NAME { $$$ }",
        }
        return class_patterns.get(language.lower(), class_patterns["python"])

    def _run_ast_grep_for_classes(self, file_path: str, language: str, pattern: str) -> List[Dict[str, Any]]:
        """Run ast-grep to find class matches.

        Args:
            file_path: Path to file to analyze
            language: Programming language
            pattern: ast-grep pattern to use

        Returns:
            List of match dictionaries from ast-grep output
        """
        result = subprocess.run(
            ["ast-grep", "run", "--pattern", pattern, "--lang", language, "--json", file_path],
            capture_output=True,
            text=True,
            timeout=SubprocessDefaults.AST_GREP_TIMEOUT_SECONDS,
        )

        # Early return for failed or empty results
        if result.returncode != 0 or not result.stdout.strip():
            return []

        matches = json.loads(result.stdout)
        return matches if isinstance(matches, list) else []

    def _process_class_matches(self, matches: List[Dict[str, Any]], language: str) -> List[Dict[str, Any]]:
        """Process ast-grep matches into class information.

        Args:
            matches: Raw match data from ast-grep
            language: Programming language

        Returns:
            List of class information dictionaries
        """
        classes = []
        for match in matches:
            cls_info = self._extract_class_info(match, language)
            classes.append(cls_info)
        return classes

    def _extract_class_info(self, match: Dict[str, Any], language: str) -> Dict[str, Any]:
        """Extract class information from a single ast-grep match.

        Args:
            match: Single match dictionary from ast-grep
            language: Programming language

        Returns:
            Dictionary with class name, lines, and method count
        """
        cls_name = self._extract_class_name(match)
        start_line, end_line = self._extract_line_range(match)
        method_count = self._count_methods_in_class(match.get("text", ""), language)

        return {"name": cls_name, "start_line": start_line, "end_line": end_line, "method_count": method_count}

    def _extract_class_name(self, match: Dict[str, Any]) -> str:
        """Extract class name from ast-grep match metavariables.

        Args:
            match: Match dictionary from ast-grep

        Returns:
            Class name or "unknown" if not found
        """
        meta_vars = match.get("metaVariables", {})
        if "NAME" not in meta_vars:
            return "unknown"

        name_data = meta_vars["NAME"]

        # Handle both dict and string formats
        if isinstance(name_data, dict):
            result = name_data.get("text", "unknown")
            return str(result) if result is not None else "unknown"
        elif isinstance(name_data, str):
            return name_data
        else:
            return "unknown"

    def _extract_line_range(self, match: Dict[str, Any]) -> tuple[int, int]:
        """Extract start and end line numbers from ast-grep match.

        Args:
            match: Match dictionary from ast-grep

        Returns:
            Tuple of (start_line, end_line), 1-indexed
        """
        range_info = match.get("range", {})
        start_line = range_info.get("start", {}).get("line", 0) + 1
        end_line = range_info.get("end", {}).get("line", 0) + 1
        return start_line, end_line

    def _count_methods_in_class(self, code: str, language: str) -> int:
        """Count the number of methods in a class.

        Args:
            code: Class code as string
            language: Programming language

        Returns:
            Number of methods found
        """
        if language.lower() == "python":
            return len(re.findall(r"^\s+def\s+", code, re.MULTILINE))
        else:
            return len(re.findall(r"^\s+\w+\s*\([^)]*\)\s*\{", code, re.MULTILINE))


class MagicNumberDetector(SmellDetector):
    """Detects magic numbers in code."""

    DEFAULT_EXCLUDE_FILES = ["**/constants.py", "**/constants.ts", "**/constants/**"]

    def __init__(self, enabled: bool = True, exclude_files: List[str] | None = None) -> None:
        super().__init__(None, "smell_detector.magic_number")
        self.enabled = enabled
        self.exclude_files = exclude_files if exclude_files is not None else self.DEFAULT_EXCLUDE_FILES

    def _is_excluded(self, file_path: str) -> bool:
        """Check if file matches any exclude pattern."""
        name = Path(file_path).name
        for pattern in self.exclude_files:
            if fnmatch(file_path, pattern) or fnmatch(name, pattern.replace("**/", "")):
                return True
        return False

    def detect(self, file_path: str, content: str, language: str, project_path: Path) -> List[SmellInfo]:
        """Detect magic numbers in the code."""
        if not self.enabled or self._is_excluded(file_path):
            return []
        rel_path = str(Path(file_path).relative_to(project_path))
        try:
            lines = content.split("\n")
            magic_numbers = self._find_magic_numbers(content, lines, language)
            return [self._make_smell(m, rel_path) for m in magic_numbers]
        except Exception as e:
            self.logger.warning("detection_failed", file=file_path, error=str(e))
            return []

    def _make_smell(self, magic: Dict[str, Any], rel_path: str) -> SmellInfo:
        value = magic.get("value")
        line = magic.get("line", 0)
        return SmellInfo(
            type="magic_number",
            file=rel_path,
            name=str(value),
            line=line,
            severity="low",
            metric=value,
            threshold="N/A",
            message=f"Magic number '{value}' on line {line}",
            suggestion="Extract to a named constant with meaningful name",
        )

    # Regex matching a digit sequence preceded by a standard prefix,
    # e.g. SHA-256, ISO 8601, UTF-8, RFC 2616, ISO-17442
    _STANDARD_ID_RE = re.compile(r"(?:SHA|ISO|RFC|UTF|IEEE|ANSI|IEC|ECMA)-?\s*(\d+)", re.IGNORECASE)

    # Patterns for lines to skip entirely (comments, imports, etc.)
    _LINE_EXCLUDE_PATTERNS = [
        r"^\s*#",  # Python comments
        r"^\s*//",  # JS/Java comments
        r"^\s*\*",  # Multi-line comment continuation
        r"^\s*import",  # Import statements
        r"^\s*from",  # Python from imports
        r"=\s*\d+\s*$",  # Variable assignment (likely a constant definition)
        r"range\(",  # Range calls
        r"sleep\(",  # Sleep calls
        r"timeout",  # Timeout settings
        r"port\s*=",  # Port assignments
        r"version",  # Version numbers
    ]

    # Common values that aren't magic
    _ALLOWED_VALUES = frozenset({"0", "1", "-1", "2", "10", "100", "1000", "0.0", "1.0", "0.5"})

    def _find_magic_numbers(self, content: str, lines: List[str], language: str) -> List[Dict[str, Any]]:
        """Find magic numbers in code."""
        magic_numbers: List[Dict[str, Any]] = []
        docstring_lines = self._find_docstring_lines(content, language)

        for line_num, line in enumerate(lines, 1):
            if line_num in docstring_lines:
                continue
            if self._should_skip_line(line):
                continue

            found = self._extract_magic_from_line(line)
            for num in found:
                magic_numbers.append({"line": line_num, "value": num})

        return magic_numbers[: SemanticVolumeDefaults.MAGIC_NUMBER_SAMPLE_LIMIT]

    def _should_skip_line(self, line: str) -> bool:
        """Check if the entire line should be skipped."""
        if self._is_uppercase_numeric_constant_assignment(line):
            return True
        for pattern in self._LINE_EXCLUDE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True
        return False

    @staticmethod
    def _is_uppercase_numeric_constant_assignment(line: str) -> bool:
        """Return True for UPPER_CASE assignments to number/list/tuple values."""
        stripped_line = line.strip()
        if not stripped_line:
            return False
        code_only = stripped_line.split("#", 1)[0].strip()
        match = re.match(r"^([A-Z][A-Z0-9_]*)(?:\s*:\s*[^=]+)?\s*=\s*(.+)$", code_only)
        if not match:
            return False
        rhs = match.group(2).strip()
        try:
            value = ast.literal_eval(rhs)
        except (SyntaxError, ValueError):
            return False
        return MagicNumberDetector._is_numeric_constant_value(value)

    @staticmethod
    def _is_numeric_constant_value(value: object) -> bool:
        """Return True if value is a plain number or a sequence of plain numbers."""
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, (list, tuple)):
            return all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
        return False

    def _extract_magic_from_line(self, line: str) -> List[str]:
        """Extract magic number values from a single line."""
        standard_id_numbers = {m.group(1) for m in self._STANDARD_ID_RE.finditer(line)}
        numbers = re.findall(r"\b(\d+\.?\d*)\b", line)
        result: List[str] = []

        for num in numbers:
            if num in self._ALLOWED_VALUES or num in standard_id_numbers:
                continue
            idx = line.find(num)
            if self._is_false_positive(line, num, idx):
                continue
            result.append(num)

        return result

    @staticmethod
    def _is_false_positive(line: str, num: str, idx: int) -> bool:
        """Check if a numeric literal at idx is a false positive."""
        # Preceded by '-' → part of hyphenated identifier (sha-256)
        if idx > 0 and line[idx - 1] == "-":
            return True
        before_num = line[:idx]
        # Named keyword argument (cost_per_unit=0.001)
        if re.search(r"\w+=\s*$", before_num):
            return True
        # Inside a string (odd quote count before the number)
        quote_count = before_num.count('"') + before_num.count("'")
        if quote_count % 2 != 0:
            return True
        return False

    @staticmethod
    def _find_docstring_lines(content: str, language: str) -> set[int]:
        """Return the set of 1-based line numbers inside triple-quoted strings."""
        lines_in_docstrings: set[int] = set()
        if language.lower() not in ("python",):
            return lines_in_docstrings

        for match in re.finditer(r"(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\')", content):
            start_line = content[: match.start()].count("\n") + 1
            end_line = content[: match.end()].count("\n") + 1
            for ln in range(start_line, end_line + 1):
                lines_in_docstrings.add(ln)

        return lines_in_docstrings


class SmellAnalyzer:
    """Orchestrates smell detection across files."""

    def __init__(self, detectors: List[SmellDetector]) -> None:
        """Initialize with a list of detectors.

        Args:
            detectors: List of smell detector instances
        """
        self.detectors = detectors
        self.logger = get_logger("smell_analyzer")

    def analyze_file(self, file_path: str, language: str, project_path: Path) -> List[Dict[str, Any]]:
        """Analyze a single file for all configured smells.

        Args:
            file_path: Path to file to analyze
            language: Programming language
            project_path: Root project path

        Returns:
            List of detected smells as dictionaries
        """
        smells = []

        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="ignore")

            for detector in self.detectors:
                detected = detector.detect(file_path, content, language, project_path)
                smells.extend([smell.to_dict() for smell in detected])

        except Exception as e:
            self.logger.error("file_analysis_failed", file=file_path, error=str(e))

        return smells
