"""Code selection analyzer for refactoring operations.

This module analyzes selected code regions to determine:
- Variables used and their classification (local, parameter, global)
- Parameters needed for extracted functions
- Return values required
- Scope and dependencies
"""

import re
from typing import Dict, FrozenSet, List

from ast_grep_mcp.core.logging import get_logger

from ...models.refactoring import (
    CodeSelection,
    VariableInfo,
    VariableType,
)
from ...utils.text import read_file_lines

logger = get_logger(__name__)


class CodeSelectionAnalyzer:
    """Analyzes code selections for refactoring operations."""

    def __init__(self, language: str) -> None:
        """Initialize analyzer for specific language.

        Args:
            language: Programming language (python, typescript, javascript, java)
        """
        self.language = language
        self._variable_patterns = self._get_variable_patterns(language)

    def _build_code_selection(self, file_path: str, start_line: int, end_line: int) -> tuple[List[str], CodeSelection]:
        """Read file and construct a CodeSelection for the given line range.

        Returns:
            (all_lines, selection) tuple
        """
        lines = read_file_lines(file_path)
        selection_lines = lines[start_line - 1 : end_line]
        content = "".join(selection_lines)
        indentation = self._detect_indentation(selection_lines)
        selection = CodeSelection(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            language=self.language,
            content=content,
            indentation=indentation,
        )
        return lines, selection

    def analyze_selection(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        project_folder: str,
    ) -> CodeSelection:
        """Analyze a code selection for refactoring.

        Args:
            file_path: Path to the file containing selection
            start_line: Starting line of selection (1-indexed)
            end_line: Ending line of selection (1-indexed)
            project_folder: Project root folder

        Returns:
            CodeSelection with analysis results
        """
        logger.info(
            "analyzing_code_selection",
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            language=self.language,
        )
        lines, selection = self._build_code_selection(file_path, start_line, end_line)
        self._analyze_variables(selection, lines, project_folder)
        self._determine_parameters_and_returns(selection)
        selection.has_early_returns = self._has_early_returns(selection.content)
        selection.has_exceptions = self._has_exception_handling(selection.content)
        logger.info(
            "code_selection_analyzed",
            variables_found=len(selection.variables),
            parameters_needed=len(selection.parameters_needed),
            return_values=len(selection.return_values),
        )
        return selection

    def _detect_indentation(self, lines: List[str]) -> str:
        """Detect indentation style from code lines.

        Args:
            lines: Lines of code

        Returns:
            Indentation string (spaces or tabs)
        """
        for line in lines:
            if line.strip() and line[0] in (" ", "\t"):
                # Extract leading whitespace
                indent = len(line) - len(line.lstrip())
                return line[:indent]

        return ""  # No indentation detected

    def _analyze_variables(
        self,
        selection: CodeSelection,
        all_lines: List[str],
        project_folder: str,
    ) -> None:
        """Analyze variables in selection.

        Identifies:
        - Variables read (used)
        - Variables written (assigned)
        - Variable scope (local, parameter, global)

        Args:
            selection: CodeSelection to populate with variable info
            all_lines: All lines in the file (for context)
            project_folder: Project root for ast-grep search
        """
        _content = selection.content  # noqa: F841
        variables: Dict[str, VariableInfo] = {}

        # Find all variable references using ast-grep patterns
        if self.language == "python":
            self._analyze_python_variables(selection, variables, all_lines, project_folder)
        elif self.language in ("typescript", "javascript"):
            self._analyze_js_ts_variables(selection, variables, all_lines, project_folder)
        elif self.language == "java":
            self._analyze_java_variables(selection, variables, all_lines, project_folder)

        selection.variables = list(variables.values())

    # Python keywords set - shared across multiple methods
    _PYTHON_KEYWORDS = frozenset(
        {
            "False",
            "None",
            "True",
            "and",
            "as",
            "assert",
            "async",
            "await",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "nonlocal",
            "not",
            "or",
            "pass",
            "raise",
            "return",
            "try",
            "while",
            "with",
            "yield",
        }
    )

    _JS_TS_KEYWORDS = frozenset(
        {
            "await",
            "break",
            "case",
            "catch",
            "class",
            "const",
            "continue",
            "debugger",
            "default",
            "delete",
            "do",
            "else",
            "enum",
            "export",
            "extends",
            "false",
            "finally",
            "for",
            "function",
            "if",
            "import",
            "in",
            "instanceof",
            "let",
            "new",
            "null",
            "return",
            "super",
            "switch",
            "this",
            "throw",
            "true",
            "try",
            "typeof",
            "var",
            "void",
            "while",
            "with",
            "yield",
            "async",
            "of",
        }
    )

    _JAVA_KEYWORDS = frozenset(
        {
            "abstract",
            "assert",
            "boolean",
            "break",
            "byte",
            "case",
            "catch",
            "char",
            "class",
            "const",
            "continue",
            "default",
            "do",
            "double",
            "else",
            "enum",
            "extends",
            "final",
            "finally",
            "float",
            "for",
            "goto",
            "if",
            "implements",
            "import",
            "instanceof",
            "int",
            "interface",
            "long",
            "native",
            "new",
            "package",
            "private",
            "protected",
            "public",
            "return",
            "short",
            "static",
            "strictfp",
            "super",
            "switch",
            "synchronized",
            "this",
            "throw",
            "throws",
            "transient",
            "try",
            "void",
            "volatile",
            "while",
            "true",
            "false",
            "null",
        }
    )

    def _register_variable(
        self,
        variables: Dict[str, VariableInfo],
        name: str,
        start_line: int,
        var_type: VariableType = VariableType.LOCAL,
        *,
        is_read: bool = False,
        is_written: bool = False,
    ) -> None:
        """Register or update a variable in the variables dict.

        Args:
            variables: Dict to populate with variable info
            name: Variable name
            start_line: First use line number
            var_type: Variable type classification
            is_read: Whether variable is read
            is_written: Whether variable is written
        """
        if name not in variables:
            variables[name] = VariableInfo(
                name=name,
                variable_type=var_type,
                first_use_line=start_line,
                is_read=is_read,
                is_written=is_written,
            )
        else:
            if is_read:
                variables[name].is_read = True
            if is_written:
                variables[name].is_written = True

    def _scan_and_register_identifiers(
        self,
        content: str,
        pattern: str,
        keywords: FrozenSet[str],
        variables: Dict[str, VariableInfo],
        selection: CodeSelection,
    ) -> None:
        """Scan content with regex and register non-keyword identifiers as reads.

        Shared by JS/TS and Java analyzers.

        Args:
            content: Source code content
            pattern: Regex pattern with one capture group for identifier
            keywords: Language keyword set to exclude
            variables: Dict to populate with variable info
            selection: Code selection metadata
        """
        for var_name in (m.group(1) for m in re.finditer(pattern, content) if m.group(1) not in keywords):
            self._register_variable(
                variables,
                var_name,
                selection.start_line,
                var_type=VariableType.PARAMETER,
                is_read=True,
            )

    def _find_python_assignments(
        self,
        content: str,
        selection: CodeSelection,
        variables: Dict[str, VariableInfo],
    ) -> None:
        """Find variable assignments in Python code.

        Args:
            content: Source code content
            selection: Code selection metadata
            variables: Dict to populate with variable info
        """
        assignment_pattern = r"\b(\w+)\s*="
        for match in re.finditer(assignment_pattern, content):
            self._register_variable(
                variables,
                match.group(1),
                selection.start_line,
                var_type=VariableType.LOCAL,
                is_written=True,
            )

    # Patterns for base variable detection: subscript, attribute, non-method call
    _PYTHON_BASE_VAR_PATTERNS = (
        r"\b([a-zA-Z_]\w*)\s*\[",  # var[...]
        r"\b([a-zA-Z_]\w*)\s*\.",  # var.attr
        r"(?<!\.)\b([a-zA-Z_]\w*)\s*\(",  # var(...) not method calls
    )

    def _collect_python_identifiers(self, content: str, pattern: str) -> set[str]:
        """Return non-keyword identifiers matching a regex capture group."""
        return {m.group(1) for m in re.finditer(pattern, content) if m.group(1) not in self._PYTHON_KEYWORDS}

    def _find_python_base_variables(
        self,
        content: str,
        selection: CodeSelection,
        variables: Dict[str, VariableInfo],
    ) -> None:
        """Find base variables used in subscripts, attributes, and calls."""
        base_vars: set[str] = set()
        for pattern in self._PYTHON_BASE_VAR_PATTERNS:
            base_vars |= self._collect_python_identifiers(content, pattern)
        for var_name in base_vars:
            self._register_variable(
                variables,
                var_name,
                selection.start_line,
                var_type=VariableType.PARAMETER,
                is_read=True,
            )

    def _is_in_string_or_comment(self, content: str, match_pos: int) -> bool:
        """Check if a match position is inside a string literal or comment.

        Args:
            content: Source code content
            match_pos: Position of the match

        Returns:
            True if inside string or comment, False otherwise
        """
        # Check if inside string (simple heuristic using quote counts)
        before_text = content[:match_pos]
        if before_text.count("'") % 2 == 1 or before_text.count('"') % 2 == 1:
            return True

        # Check if in a comment (appears after # on same line)
        line_start = content.rfind("\n", 0, match_pos) + 1
        line_to_match = content[line_start:match_pos]
        if "#" in line_to_match:
            return True

        return False

    def _find_python_standalone_identifiers(
        self,
        content: str,
        selection: CodeSelection,
        variables: Dict[str, VariableInfo],
    ) -> None:
        """Find standalone identifiers not part of subscript/attribute/call.

        Matches identifiers that:
        - Aren't preceded by a dot (not method names)
        - Aren't followed by [, ., or ( (not being accessed)
        - Aren't keywords or in strings/comments

        Args:
            content: Source code content
            selection: Code selection metadata
            variables: Dict to populate with variable info
        """
        identifier_pattern = r"(?<!\.)(?<!\#)\b([a-zA-Z_]\w*)(?!\s*[\[\.\(])\b"
        for match in re.finditer(identifier_pattern, content):
            var_name = match.group(1)

            # Skip keywords
            if var_name in self._PYTHON_KEYWORDS:
                continue

            # Skip if in string or comment
            if self._is_in_string_or_comment(content, match.start()):
                continue

            # Register identifier as read
            self._register_variable(
                variables,
                var_name,
                selection.start_line,
                var_type=VariableType.PARAMETER,
                is_read=True,
            )

    def _analyze_python_variables(
        self,
        selection: CodeSelection,
        variables: Dict[str, VariableInfo],
        all_lines: List[str],
        project_folder: str,
    ) -> None:
        """Analyze Python variables in selection.

        Uses regex patterns to identify:
        - Assignments (x = ...)
        - Function calls (func(...))
        - Attribute access (obj.attr)
        - Variable references

        Args:
            selection: Code selection
            variables: Dict to populate with variable info
            all_lines: All file lines
            project_folder: Project root
        """
        content = selection.content

        # Find assignments (variables being written)
        self._find_python_assignments(content, selection, variables)

        # Find base variables (subscripts, attributes, calls)
        self._find_python_base_variables(content, selection, variables)

        # Find standalone identifiers
        self._find_python_standalone_identifiers(content, selection, variables)

        # Classify variables based on scope analysis
        self._classify_variable_types(selection, variables, all_lines)

    def _is_variable_defined_before(
        self,
        var_name: str,
        before_lines: List[str],
    ) -> bool:
        """Check if variable is defined before selection.

        Args:
            var_name: Variable name to check
            before_lines: Lines before the selection

        Returns:
            True if variable is assigned before selection
        """
        return any(re.search(rf"\b{re.escape(var_name)}\s*=", line) for line in before_lines)

    def _is_variable_used_after(
        self,
        var_name: str,
        after_lines: List[str],
    ) -> bool:
        """Check if variable is used after selection.

        Args:
            var_name: Variable name to check
            after_lines: Lines after the selection

        Returns:
            True if variable is referenced after selection
        """
        return any(re.search(rf"\b{re.escape(var_name)}\b", line) for line in after_lines)

    def _get_variable_classification(
        self,
        var_info: VariableInfo,
        defined_before: bool,
        used_after: bool,
    ) -> VariableType:
        """Classify variable type based on usage pattern."""
        is_written = var_info.is_written
        is_read = var_info.is_read

        if is_written and used_after:
            return VariableType.MODIFIED
        if is_written and not defined_before:
            return VariableType.LOCAL
        if is_read and not is_written:
            return VariableType.PARAMETER
        return var_info.variable_type

    def _analyze_js_ts_variables(
        self,
        selection: CodeSelection,
        variables: Dict[str, VariableInfo],
        all_lines: List[str],
        project_folder: str,
    ) -> None:
        """Analyze JavaScript/TypeScript variables in selection.

        Args:
            selection: Code selection
            variables: Dict to populate with variable info
            all_lines: All file lines
            project_folder: Project root
        """
        content = selection.content

        # Find variable declarations and assignments
        # Matches: const x = ..., let y = ..., var z = ..., x = ...
        declaration_pattern = r"\b(?:const|let|var)?\s*(\w+)\s*="
        for match in re.finditer(declaration_pattern, content):
            self._register_variable(
                variables,
                match.group(1),
                selection.start_line,
                var_type=VariableType.LOCAL,
                is_written=True,
            )

        # Find variable reads
        self._scan_and_register_identifiers(
            content,
            r"\b([a-zA-Z_$]\w*)\b",
            self._JS_TS_KEYWORDS,
            variables,
            selection,
        )

        self._classify_variable_types(selection, variables, all_lines)

    def _analyze_java_variables(
        self,
        selection: CodeSelection,
        variables: Dict[str, VariableInfo],
        all_lines: List[str],
        project_folder: str,
    ) -> None:
        """Analyze Java variables in selection.

        Args:
            selection: Code selection
            variables: Dict to populate with variable info
            all_lines: All file lines
            project_folder: Project root
        """
        content = selection.content

        # Find variable declarations and assignments
        # Matches: Type var = ..., var = ...
        declaration_pattern = r"\b(?:\w+\s+)?(\w+)\s*="
        for match in re.finditer(declaration_pattern, content):
            self._register_variable(
                variables,
                match.group(1),
                selection.start_line,
                var_type=VariableType.LOCAL,
                is_written=True,
            )

        # Find variable reads
        self._scan_and_register_identifiers(
            content,
            r"\b([a-zA-Z_]\w*)\b",
            self._JAVA_KEYWORDS,
            variables,
            selection,
        )

        self._classify_variable_types(selection, variables, all_lines)

    def _classify_variable_types(
        self,
        selection: CodeSelection,
        variables: Dict[str, VariableInfo],
        all_lines: List[str],
    ) -> None:
        """Classify variables by type based on scope analysis.

        Updates variable_type in variables dict:
        - LOCAL: Defined within selection, not used outside
        - PARAMETER: Used but not defined in selection
        - MODIFIED: Modified in selection, needs to be returned
        - GLOBAL: Module or global scope
        - CLOSURE: From enclosing function scope

        Args:
            selection: Code selection
            variables: Dict of variables to classify
            all_lines: All file lines for context
        """
        # Get lines before and after selection for context
        before_lines = all_lines[: selection.start_line - 1]
        after_lines = all_lines[selection.end_line :]

        for var_name, var_info in variables.items():
            # Detect scope context
            defined_before = self._is_variable_defined_before(var_name, before_lines)
            used_after = self._is_variable_used_after(var_name, after_lines)

            # Classify based on usage pattern
            var_info.variable_type = self._get_variable_classification(
                var_info,
                defined_before,
                used_after,
            )

    def _determine_parameters_and_returns(self, selection: CodeSelection) -> None:
        """Determine which variables should be parameters and return values.

        Args:
            selection: Code selection to update
        """
        # Parameters: Variables that need to be passed in
        parameters = selection.get_variables_by_type(VariableType.PARAMETER)
        selection.parameters_needed = [v.name for v in parameters if v.is_read]

        # Return values: Variables that need to be returned
        modified_vars = selection.get_variables_by_type(VariableType.MODIFIED)
        selection.return_values = [v.name for v in modified_vars]

    def _has_early_returns(self, content: str) -> bool:
        """Check if selection contains early return statements.

        Args:
            content: Code content

        Returns:
            True if early returns detected
        """
        return bool(re.search(r"\breturn\b", content))

    def _has_exception_handling(self, content: str) -> bool:
        """Check if selection contains exception handling.

        Args:
            content: Code content

        Returns:
            True if try/except/throw detected
        """
        if self.language == "python":
            return bool(re.search(r"\b(try|except|raise)\b", content))
        elif self.language in ("typescript", "javascript", "java"):
            return bool(re.search(r"\b(try|catch|throw)\b", content))

        return False

    def _get_variable_patterns(self, language: str) -> Dict[str, str]:
        """Get language-specific variable patterns.

        Args:
            language: Programming language

        Returns:
            Dict of ast-grep patterns for variable detection
        """
        patterns = {
            "python": {
                "assignment": "$VAR = $VALUE",
                "variable_ref": "$VAR",
            },
            "typescript": {
                "declaration": "const $VAR = $VALUE",
                "variable_ref": "$VAR",
            },
            "javascript": {
                "declaration": "const $VAR = $VALUE",
                "variable_ref": "$VAR",
            },
            "java": {
                "declaration": "$TYPE $VAR = $VALUE",
                "variable_ref": "$VAR",
            },
        }

        return patterns.get(language, patterns["python"])
