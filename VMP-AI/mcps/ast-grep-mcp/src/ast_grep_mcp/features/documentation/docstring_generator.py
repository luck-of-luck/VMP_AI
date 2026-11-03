"""Docstring generation service.

This module provides functionality for auto-generating docstrings
from function signatures and names across multiple languages.
"""

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import sentry_sdk

from ast_grep_mcp.constants import ConversionFactors, DocstringDefaults
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.models.documentation import (
    DocstringGenerationResult,
    DocstringStyle,
    FunctionSignature,
    GeneratedDocstring,
    ParameterInfo,
)
from ast_grep_mcp.utils.text import read_file_lines, write_file_lines

logger = get_logger(__name__)


# =============================================================================
# Name Inference Utilities
# =============================================================================


def _split_camel_case(name: str) -> List[str]:
    """Split camelCase or PascalCase into words."""
    result = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    result = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", result)
    return result.split()


def _split_snake_case(name: str) -> List[str]:
    """Split snake_case into words."""
    return name.split("_")


_VERB_PREFIX_MEANINGS: Dict[str, str] = {
    "get": "Get",
    "set": "Set",
    "is": "Check if",
    "has": "Check if has",
    "can": "Check if can",
    "should": "Determine if should",
    "will": "Determine if will",
    "create": "Create",
    "make": "Create",
    "build": "Build",
    "generate": "Generate",
    "compute": "Compute",
    "calculate": "Calculate",
    "find": "Find",
    "search": "Search for",
    "fetch": "Fetch",
    "load": "Load",
    "save": "Save",
    "store": "Store",
    "write": "Write",
    "read": "Read",
    "parse": "Parse",
    "format": "Format",
    "convert": "Convert",
    "transform": "Transform",
    "validate": "Validate",
    "check": "Check",
    "verify": "Verify",
    "process": "Process",
    "handle": "Handle",
    "update": "Update",
    "delete": "Delete",
    "remove": "Remove",
    "add": "Add",
    "insert": "Insert",
    "append": "Append",
    "init": "Initialize",
    "initialize": "Initialize",
    "setup": "Set up",
    "configure": "Configure",
    "render": "Render",
    "display": "Display",
    "show": "Show",
    "hide": "Hide",
    "enable": "Enable",
    "disable": "Disable",
    "start": "Start",
    "stop": "Stop",
    "begin": "Begin",
    "end": "End",
    "open": "Open",
    "close": "Close",
    "connect": "Connect to",
    "disconnect": "Disconnect from",
    "send": "Send",
    "receive": "Receive",
    "emit": "Emit",
    "dispatch": "Dispatch",
    "trigger": "Trigger",
    "fire": "Fire",
    "on": "Handle",
    "do": "Perform",
    "run": "Run",
    "execute": "Execute",
    "apply": "Apply",
    "merge": "Merge",
    "split": "Split",
    "join": "Join",
    "sort": "Sort",
    "filter": "Filter",
    "map": "Map",
    "reduce": "Reduce",
    "extract": "Extract",
    "export": "Export",
    "import": "Import",
}


def _infer_description_from_name(name: str) -> str:
    """Infer a human-readable description from a function name using verb prefix patterns."""
    words = _function_name_words(name)
    if not words:
        return "Perform operation."
    first_word = words[0]
    if first_word in _VERB_PREFIX_MEANINGS:
        return _build_prefix_description(first_word, words[1:], _VERB_PREFIX_MEANINGS)
    return f"{' '.join(words).capitalize()}."


_ARTICLE_VERBS = frozenset({"get", "find", "fetch", "load", "read", "create", "make", "build", "generate"})


def _build_prefix_description(first_word: str, rest_words: List[str], prefix_meanings: Dict[str, str]) -> str:
    verb = prefix_meanings[first_word]
    if not rest_words:
        return f"{verb}."
    noun = " ".join(rest_words)
    if first_word in _ARTICLE_VERBS:
        return f"{verb} the {noun}."
    return f"{verb} {noun}."


# Configuration for parameter name inference
_COMMON_PARAMS: Dict[str, str] = {
    "self": "The instance",
    "cls": "The class",
    "args": "Positional arguments",
    "kwargs": "Keyword arguments",
    "path": "The file or directory path",
    "file_path": "Path to the file",
    "dir_path": "Path to the directory",
    "folder": "The folder path",
    "directory": "The directory path",
    "name": "The name",
    "value": "The value",
    "key": "The key",
    "data": "The data",
    "content": "The content",
    "text": "The text content",
    "message": "The message",
    "config": "Configuration settings",
    "options": "Options dictionary",
    "settings": "Settings dictionary",
    "params": "Parameters dictionary",
    "callback": "Callback function",
    "handler": "Handler function",
    "func": "The function",
    "fn": "The function",
    "items": "List of items",
    "elements": "List of elements",
    "values": "List of values",
    "result": "The result",
    "response": "The response",
    "request": "The request",
    "req": "The request",
    "res": "The response",
    "ctx": "The context",
    "context": "The context",
    "index": "The index",
    "idx": "The index",
    "i": "The index",
    "j": "Secondary index",
    "k": "Tertiary index",
    "n": "The count or number",
    "count": "The count",
    "size": "The size",
    "length": "The length",
    "width": "The width",
    "height": "The height",
    "x": "The x coordinate",
    "y": "The y coordinate",
    "z": "The z coordinate",
    "start": "The start value",
    "end": "The end value",
    "begin": "The beginning value",
    "limit": "The limit",
    "offset": "The offset",
    "timeout": "Timeout in seconds",
    "delay": "Delay in milliseconds",
    "interval": "Interval duration",
    "id": "The unique identifier",
    "user_id": "The user identifier",
    "user": "The user object",
    "username": "The username",
    "password": "The password",
    "email": "The email address",
    "url": "The URL",
    "uri": "The URI",
    "host": "The host address",
    "port": "The port number",
    "language": "The programming language",
    "lang": "The language code",
    "locale": "The locale",
    "format": "The format string",
    "pattern": "The pattern",
    "regex": "The regular expression",
    "template": "The template",
    "style": "The style",
    "mode": "The mode",
    "type": "The type",
    "kind": "The kind",
    "level": "The level",
    "severity": "The severity level",
    "priority": "The priority",
    "status": "The status",
    "state": "The state",
    "flag": "Boolean flag",
    "enabled": "Whether enabled",
    "disabled": "Whether disabled",
    "active": "Whether active",
    "visible": "Whether visible",
    "hidden": "Whether hidden",
    "readonly": "Whether read-only",
    "required": "Whether required",
    "optional": "Whether optional",
    "force": "Whether to force the operation",
    "recursive": "Whether to process recursively",
    "verbose": "Whether to output verbose information",
    "debug": "Whether in debug mode",
    "quiet": "Whether to suppress output",
    "silent": "Whether to be silent",
    "dry_run": "Whether to perform a dry run only",
    "overwrite": "Whether to overwrite existing",
    "append": "Whether to append",
    "include": "Items to include",
    "exclude": "Items to exclude",
    "filter": "Filter function or criteria",
    "sort": "Sort criteria",
    "order": "Sort order",
    "ascending": "Whether ascending order",
    "descending": "Whether descending order",
    "reverse": "Whether to reverse",
    "max": "Maximum value",
    "min": "Minimum value",
    "default": "Default value",
    "fallback": "Fallback value",
    "encoding": "Character encoding",
    "charset": "Character set",
    "separator": "The separator",
    "delimiter": "The delimiter",
    "prefix": "The prefix",
    "suffix": "The suffix",
    "header": "The header",
    "footer": "The footer",
    "title": "The title",
    "label": "The label",
    "description": "The description",
    "error": "The error",
    "exception": "The exception",
    "logger": "The logger instance",
    "log": "The log",
}

# Suffix patterns: (suffix, template) - template uses {base} placeholder
_SUFFIX_PATTERNS: List[Tuple[str, str]] = [
    ("_id", "The {base} identifier"),
    ("_name", "The {base} name"),
    ("_path", "Path to the {base}"),
    ("_file", "The {base} file"),
    ("_directory", "The {base} directory"),
    ("_dir", "The {base} directory"),
    ("_list", "List of {base}"),
    ("_array", "List of {base}"),
    ("_dict", "Dictionary of {base}"),
    ("_map", "Dictionary of {base}"),
    ("_count", "Number of {base}"),
    ("_num", "Number of {base}"),
    ("_callback", "Callback for {base}"),
    ("_handler", "Callback for {base}"),
    ("_config", "Configuration for {base}"),
    ("_options", "Configuration for {base}"),
]

# Prefix patterns: (prefix, template) - template uses {rest} placeholder
_PREFIX_PATTERNS: List[Tuple[str, str]] = [
    ("is_", "Whether {rest}"),
    ("has_", "Whether {rest}"),
    ("can_", "Whether {rest}"),
    ("num_", "Number of {rest}"),
    ("n_", "Number of {rest}"),
    ("max_", "Maximum {rest}"),
    ("min_", "Minimum {rest}"),
]


def _check_suffix_pattern(name: str) -> Optional[str]:
    """Return description from _SUFFIX_PATTERNS if name matches, else None."""
    for suffix, template in _SUFFIX_PATTERNS:
        if name.endswith(suffix):
            base = name[: -len(suffix)].replace("_", " ")
            return template.format(base=base)
    return None


def _check_prefix_pattern(name: str) -> Optional[str]:
    """Return description from _PREFIX_PATTERNS if name matches, else None."""
    for prefix, template in _PREFIX_PATTERNS:
        if name.startswith(prefix):
            rest = name[len(prefix) :].replace("_", " ")
            return template.format(rest=rest)
    return None


def _infer_parameter_description(param: ParameterInfo, function_context: str = "") -> str:
    """Infer a description for a parameter from its name using lookup tables and patterns."""
    name = param.name.lower()
    result = _COMMON_PARAMS.get(name) or _check_suffix_pattern(name) or _check_prefix_pattern(name)
    if result:
        return result
    return f"The {param.name.replace('_', ' ')}"


# Return description patterns based on function prefix
_RETURN_PREFIX_HANDLERS: Dict[str, str] = {
    "get": "The {rest}",
    "fetch": "The {rest}",
    "load": "The {rest}",
    "read": "The {rest}",
    "find": "The {rest}",
    "search": "The {rest}",
    "create": "The created {rest}",
    "make": "The created {rest}",
    "build": "The created {rest}",
    "generate": "The created {rest}",
    "calculate": "The calculated {rest}",
    "compute": "The calculated {rest}",
    "count": "The number of {rest}",
}

_BOOLEAN_PREFIXES = frozenset({"is", "has", "can", "should", "will"})

# Return type to description mapping
_RETURN_TYPE_DESCRIPTIONS: Dict[str, str] = {
    "list": "List of results",
    "array": "List of results",
    "dict": "Dictionary with results",
    "bool": "True if successful, False otherwise",
    "str": "The resulting string",
    "int": "The resulting integer",
    "float": "The resulting number",
}


def _get_return_from_type(return_type: str) -> str:
    """Get return description from type annotation."""
    type_lower = return_type.lower()
    for key, desc in _RETURN_TYPE_DESCRIPTIONS.items():
        if key in type_lower:
            return desc
    return f"The {return_type}"


def _apply_return_prefix_handler(template: str, rest: str, return_type: Optional[str]) -> str:
    """Apply a return prefix template with best available rest value."""
    if rest:
        return template.format(rest=rest)
    return template.format(rest=return_type.lower() if return_type else "result")


def _function_name_words(function_name: str) -> List[str]:
    """Split a function name into lowercase words."""
    splitter = _split_snake_case if "_" in function_name else _split_camel_case
    return [w.lower() for w in splitter(function_name) if w]


def _infer_return_description(return_type: Optional[str], function_name: str) -> str:
    """Infer a return value description from the function name prefix and return type."""
    words = _function_name_words(function_name)
    if not words:
        return "The result"
    first_word, rest = words[0], " ".join(words[1:])
    if first_word in _BOOLEAN_PREFIXES:
        return f"True if {rest}, False otherwise" if rest else "Boolean result"
    template = _RETURN_PREFIX_HANDLERS.get(first_word)
    if template:
        return _apply_return_prefix_handler(template, rest, return_type)
    return _get_return_from_type(return_type) if return_type else "The result"


def _parse_single_python_param(part: str) -> Optional[ParameterInfo]:
    """Parse a single Python parameter string into a ParameterInfo."""
    if part.startswith("**"):
        return ParameterInfo(name=part[2:], type_hint="Dict[str, Any]")
    if part.startswith("*"):
        return ParameterInfo(name=part[1:], type_hint="Tuple[Any, ...]")
    name_type, default = (part.rsplit("=", 1)[0], part.rsplit("=", 1)[1].strip()) if "=" in part else (part, None)
    if ":" in name_type:
        name, type_hint = name_type.split(":", 1)
        name, type_hint = name.strip(), type_hint.strip()
    else:
        name, type_hint = name_type.strip(), None
    if not name:
        return None
    return ParameterInfo(name=name, type_hint=type_hint, default_value=default)


def _split_params(params_str: str, open_brackets: str) -> List[str]:
    """Split a params string by comma, respecting nested brackets.

    Args:
        params_str: Raw parameter string
        open_brackets: Characters that increase nesting depth (closing chars are inferred)
    """
    close_map = {"(": ")", "[": "]", "{": "}", "<": ">"}
    close_brackets = "".join(close_map[c] for c in open_brackets if c in close_map)
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for char in params_str:
        if char in open_brackets:
            depth += 1
        elif char in close_brackets:
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        # Bracket chars fall through here intentionally: depth has already been adjusted
        # above, and the character itself must still be appended to the current token.
        current.append(char)
    if current:
        parts.append("".join(current).strip())
    return parts


def _split_python_params(params_str: str) -> List[str]:
    """Split Python params string by comma, respecting nested brackets."""
    return _split_params(params_str, "([{")


def _split_js_ts_params(params_str: str) -> List[str]:
    """Split JS/TS params string by commas, respecting angle brackets, braces, and parens."""
    return _split_params(params_str, "<{(")


# =============================================================================
# Function Signature Parser
# =============================================================================


class FunctionSignatureParser:
    """Parse function signatures from source code."""

    _split_params = staticmethod(_split_js_ts_params)

    def __init__(self, language: str) -> None:
        """Initialize parser for specific language.

        Args:
            language: Programming language
        """
        self.language = language

    def parse_file(self, file_path: str) -> List[FunctionSignature]:
        """Parse all function signatures from a file.

        Args:
            file_path: Path to source file

        Returns:
            List of parsed function signatures
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        if self.language == "python":
            return self._parse_python_functions(content, file_path)
        elif self.language in ("typescript", "javascript"):
            return self._parse_js_ts_functions(content, file_path)
        elif self.language == "java":
            return self._parse_java_functions(content, file_path)

        return []

    def _collect_decorators(self, lines: List[str], func_idx: int) -> List[str]:
        """Collect decorator names above a function definition."""
        decorators: list[str] = []
        j = func_idx - 1
        while j >= 0 and lines[j].strip().startswith("@"):
            decorator = lines[j].strip()[1:].split("(")[0]
            decorators.insert(0, decorator)
            j -= 1
        return decorators

    def _build_python_sig(self, lines: List[str], func_idx: int, match: re.Match[str], file_path: str) -> FunctionSignature:
        indent, is_async, name, params_str, return_type = match.groups()
        return FunctionSignature(
            name=name,
            parameters=self._parse_python_params(params_str),
            return_type=return_type.strip() if return_type else None,
            is_async=bool(is_async),
            is_method=bool(indent),
            decorators=self._collect_decorators(lines, func_idx),
            file_path=file_path,
            start_line=func_idx + 1,
            end_line=self._find_python_function_end(lines, func_idx, indent),
            existing_docstring=self._find_python_docstring(lines, func_idx + 1),
        )

    def _parse_python_functions(self, content: str, file_path: str) -> List[FunctionSignature]:
        """Parse Python function signatures."""
        functions = []
        lines = content.split("\n")
        func_pattern = re.compile(r"^(\s*)(async\s+)?def\s+(\w+)\s*\((.*?)\)\s*(?:->\s*(.+?))?\s*:")

        for i, line in enumerate(lines):
            match = func_pattern.match(line)
            if match:
                functions.append(self._build_python_sig(lines, i, match, file_path))

        return functions

    def _parse_python_params(self, params_str: str) -> List[ParameterInfo]:
        """Parse Python function parameters."""
        if not params_str.strip():
            return []
        params_str = re.sub(r"\s+", " ", params_str)
        params: list[ParameterInfo] = []
        for part in _split_python_params(params_str):
            if not part:
                continue
            param = self._parse_single_python_param(part)
            if param:
                params.append(param)
        return params

    def _parse_single_python_param(self, part: str) -> Optional[ParameterInfo]:
        return _parse_single_python_param(part)

    def _collect_python_multiline_docstring(self, lines: List[str], start_idx: int, quote: str, first_line: str) -> str:
        """Collect lines of a multi-line docstring."""
        docstring_lines = [first_line]
        i = start_idx
        while i < len(lines):
            line = lines[i]
            if quote in line:
                docstring_lines.append(line[: line.index(quote)])
                break
            docstring_lines.append(line)
            i += 1
        return "\n".join(docstring_lines).strip()

    def _find_first_nonempty(self, lines: List[str], start: int) -> int:
        """Return index of first non-empty line at or after start, or len(lines)."""
        for i in range(start, len(lines)):
            if lines[i].strip():
                return i
        return len(lines)

    def _find_python_docstring(self, lines: List[str], func_line: int) -> Optional[str]:
        """Find existing docstring after function definition."""
        if func_line >= len(lines):
            return None
        next_idx = self._find_first_nonempty(lines, func_line)
        if next_idx >= len(lines):
            return None
        next_line = lines[next_idx].strip()
        q = DocstringDefaults.QUOTE_LENGTH
        if not (next_line.startswith('"""') or next_line.startswith("'''")):
            return None
        quote = next_line[:q]
        if next_line.endswith(quote) and len(next_line) > DocstringDefaults.MIN_ONELINER_LENGTH:
            return next_line[q:-q]
        return self._collect_python_multiline_docstring(lines, next_idx + 1, quote, next_line[q:])

    def _find_python_function_end(self, lines: List[str], start: int, indent: str) -> int:
        """Find the end line of a Python function."""
        indent_len = len(indent)
        i = start + 1
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            if len(line) - len(line.lstrip()) <= indent_len:
                return i
            i += 1
        return len(lines)

    _JS_TS_PATTERNS = [
        re.compile(r"^\s*(export\s+)?(async\s+)?function\s+(\w+)\s*\((.*?)\)(?:\s*:\s*(.+?))?\s*\{"),
        re.compile(r"^\s*(export\s+)?(const|let|var)\s+(\w+)\s*=\s*(async\s+)?\((.*?)\)(?:\s*:\s*(.+?))?\s*=>"),
        re.compile(r"^\s*(async\s+)?(\w+)\s*\((.*?)\)(?:\s*:\s*(.+?))?\s*\{"),
    ]
    _JS_CONTROL_KEYWORDS = frozenset({"if", "for", "while", "switch", "catch"})

    # Maps group count to (is_async_idx, name_idx, params_idx, return_type_idx)
    _JS_TS_GROUP_INDICES: Dict[int, Tuple[int, int, int, int]] = {
        DocstringDefaults.REGULAR_FUNCTION_GROUP_COUNT: (1, 2, 3, 4),  # export, async, name, params, ret
        DocstringDefaults.ARROW_FUNCTION_GROUP_COUNT: (3, 2, 4, 5),  # export, kw, name, async, params, ret
        4: (0, 1, 2, 3),  # async, name, params, ret
    }

    def _unpack_js_ts_groups(self, groups: tuple[Any, ...]) -> tuple[Any, ...]:
        """Unpack match groups based on pattern type."""
        indices = self._JS_TS_GROUP_INDICES.get(len(groups), (0, 1, 2, 3))
        ai, ni, pi, ri = indices
        return groups[ai], groups[ni], groups[pi], groups[ri]

    def _match_js_ts_line(self, line: str, lines: List[str], i: int, file_path: str) -> Optional[FunctionSignature]:
        """Try to match a line as a JS/TS function and return its signature."""
        for pattern in self._JS_TS_PATTERNS:
            match = pattern.match(line)
            if not match:
                continue
            is_async, name, params_str, return_type = self._unpack_js_ts_groups(match.groups())
            if name in self._JS_CONTROL_KEYWORDS:
                return None
            return FunctionSignature(
                name=name,
                parameters=self._parse_js_ts_params(params_str or ""),
                return_type=return_type.strip() if return_type else None,
                is_async=bool(is_async),
                is_method=False,
                file_path=file_path,
                start_line=i + 1,
                end_line=i + 1,
                existing_docstring=self._find_js_ts_docstring(lines, i),
            )
        return None

    def _parse_js_ts_functions(self, content: str, file_path: str) -> List[FunctionSignature]:
        """Parse JavaScript/TypeScript function signatures."""
        lines = content.split("\n")
        functions = []
        for i, line in enumerate(lines):
            func = self._match_js_ts_line(line, lines, i, file_path)
            if func:
                functions.append(func)
        return functions

    def _collect_jsdoc_multiline(self, lines: List[str], end_idx: int, last_line: str) -> Optional[str]:
        """Collect lines of a multi-line JSDoc comment."""
        doc_lines = [last_line[:-2]]
        j = end_idx - 1
        while j >= 0:
            curr_line = lines[j].strip()
            if "/**" in curr_line:
                doc_lines.append(curr_line[curr_line.find("/**") + 3 :])
                break
            doc_lines.append(curr_line[1:].strip() if curr_line.startswith("*") else curr_line)
            j -= 1
        if j < 0:
            return None
        doc_lines.reverse()
        return "\n".join(doc_lines).strip()

    def _find_last_nonempty(self, lines: List[str], end: int) -> int:
        """Return index of last non-empty line at or before end, or -1."""
        for i in range(end, -1, -1):
            if lines[i].strip():
                return i
        return -1

    def _find_js_ts_docstring(self, lines: List[str], func_idx: int) -> Optional[str]:
        """Find existing JSDoc before function definition."""
        if func_idx <= 0:
            return None
        j = self._find_last_nonempty(lines, func_idx - 1)
        if j < 0:
            return None
        line = lines[j].strip()
        if not line.endswith("*/"):
            return None
        if "/**" in line:
            return line[line.find("/**") + 3 : -2].strip()
        return self._collect_jsdoc_multiline(lines, j, line)

    @staticmethod
    def _parse_single_js_ts_param(part: str) -> Optional[ParameterInfo]:
        """Parse a single JS/TS parameter string into a ParameterInfo."""
        if "=" in part:
            name_type, default = part.split("=", 1)
            default = default.strip()
        else:
            name_type = part
            default = None
        if ":" in name_type:
            name, type_hint = name_type.split(":", 1)
            name = name.strip().lstrip("...")
            type_hint = type_hint.strip()
        else:
            name = name_type.strip().lstrip("...")
            type_hint = None
        if not name:
            return None
        return ParameterInfo(name=name, type_hint=type_hint, default_value=default)

    def _parse_js_ts_params(self, params_str: str) -> List[ParameterInfo]:
        """Parse JavaScript/TypeScript function parameters."""
        if not params_str.strip():
            return []
        params: list[ParameterInfo] = []
        for part in _split_js_ts_params(params_str):
            part = part.strip()
            if not part:
                continue
            param = self._parse_single_js_ts_param(part)
            if param:
                params.append(param)
        return params

    _JAVA_PATTERN = re.compile(
        r"^\s*(public|private|protected)?\s*(static\s+)?([\w<>,\s]+)\s+(\w+)\s*\((.*?)\)\s*(throws\s+[\w,\s]+)?\s*\{"
    )
    _JAVA_CONTROL_KEYWORDS = frozenset({"if", "for", "while", "switch", "catch", "try"})

    def _build_java_sig(self, lines: List[str], i: int, match: re.Match[str], file_path: str) -> Optional[FunctionSignature]:
        _, _, return_type, name, params_str, _ = match.groups()
        if name in self._JAVA_CONTROL_KEYWORDS:
            return None
        return FunctionSignature(
            name=name,
            parameters=self._parse_java_params(params_str or ""),
            return_type=return_type.strip() if return_type else None,
            is_method=True,
            file_path=file_path,
            start_line=i + 1,
            end_line=i + 1,
            existing_docstring=self._find_js_ts_docstring(lines, i),
        )

    def _parse_java_functions(self, content: str, file_path: str) -> List[FunctionSignature]:
        """Parse Java method signatures."""
        lines = content.split("\n")
        matches = ((i, self._JAVA_PATTERN.match(line)) for i, line in enumerate(lines))
        return [sig for i, m in matches if m for sig in [self._build_java_sig(lines, i, m, file_path)] if sig]

    def _parse_java_params(self, params_str: str) -> List[ParameterInfo]:
        """Parse Java method parameters (format: Type name or final Type name)."""
        if not params_str.strip():
            return []
        params: list[ParameterInfo] = []
        for part in params_str.split(","):
            part = part.strip()
            if not part:
                continue
            tokens = part.split()
            if len(tokens) >= 2:
                params.append(ParameterInfo(name=tokens[-1], type_hint=" ".join(tokens[:-1])))
        return params


# =============================================================================
# Docstring Templates
# =============================================================================


_SKIP_PARAM_NAMES = frozenset({"self", "cls"})
_SKIP_RETURN_VALUES = frozenset({"none", "void"})


def _non_self_params(func: FunctionSignature) -> List[ParameterInfo]:
    return [p for p in func.parameters if p.name not in _SKIP_PARAM_NAMES]


def _has_return(func: FunctionSignature) -> bool:
    return bool(func.return_type and func.return_type.lower() not in _SKIP_RETURN_VALUES)


def _google_param_line(param: ParameterInfo, func_name: str) -> str:
    desc = _infer_parameter_description(param, func_name)
    if param.type_hint:
        return f"    {param.name} ({param.type_hint}): {desc}"
    return f"    {param.name}: {desc}"


def _generate_google_docstring(func: FunctionSignature) -> str:
    """Generate Google-style docstring."""
    lines = [f'"""{_infer_description_from_name(func.name)}']
    non_self = _non_self_params(func)
    if non_self:
        lines += ["", "Args:"] + [_google_param_line(p, func.name) for p in non_self]
    if _has_return(func):
        return_desc = _infer_return_description(func.return_type, func.name)
        lines += ["", "Returns:", f"    {func.return_type}: {return_desc}"]
    lines.append('"""')
    return "\n".join(lines)


def _numpy_param_lines(param: ParameterInfo, func_name: str) -> List[str]:
    desc = _infer_parameter_description(param, func_name)
    return [f"{param.name} : {param.type_hint or 'any'}", f"    {desc}"]


def _generate_numpy_docstring(func: FunctionSignature) -> str:
    """Generate NumPy-style docstring."""
    lines: List[str] = ['"""', _infer_description_from_name(func.name)]
    non_self = _non_self_params(func)
    if non_self:
        lines += ["", "Parameters", "----------"]
        for param in non_self:
            lines += _numpy_param_lines(param, func.name)
    if _has_return(func):
        return_desc = _infer_return_description(func.return_type, func.name)
        lines += ["", "Returns", "-------", f"{func.return_type}", f"    {return_desc}"]
    lines.append('"""')
    return "\n".join(lines)


def _sphinx_param_lines(param: ParameterInfo, func_name: str) -> List[str]:
    desc = _infer_parameter_description(param, func_name)
    entry = [f":param {param.name}: {desc}"]
    if param.type_hint:
        entry.append(f":type {param.name}: {param.type_hint}")
    return entry


def _generate_sphinx_docstring(func: FunctionSignature) -> str:
    """Generate Sphinx-style docstring."""
    lines = [f'"""{_infer_description_from_name(func.name)}']
    non_self = _non_self_params(func)
    if non_self:
        lines.append("")
        for param in non_self:
            lines += _sphinx_param_lines(param, func.name)
    if _has_return(func):
        return_desc = _infer_return_description(func.return_type, func.name)
        lines += ["", f":return: {return_desc}", f":rtype: {func.return_type}"]
    lines.append('"""')
    return "\n".join(lines)


def _generate_jsdoc(func: FunctionSignature) -> str:
    """Generate JSDoc-style documentation."""
    lines = ["/**", f" * {_infer_description_from_name(func.name)}"]

    if func.parameters:
        lines.append(" *")
        for param in func.parameters:
            desc = _infer_parameter_description(param, func.name)
            type_str = param.type_hint or "*"
            if param.default_value is not None:
                lines.append(f" * @param {{{type_str}}} [{param.name}={param.default_value}] - {desc}")
            else:
                lines.append(f" * @param {{{type_str}}} {param.name} - {desc}")

    if func.return_type and func.return_type.lower() not in ("void", "undefined"):
        lines.append(" *")
        lines.append(f" * @returns {{{func.return_type}}} {_infer_return_description(func.return_type, func.name)}")

    if func.is_async:
        lines.append(" * @async")

    lines.append(" */")
    return "\n".join(lines)


def _generate_javadoc(func: FunctionSignature) -> str:
    """Generate Javadoc-style documentation."""
    lines = ["/**", f" * {_infer_description_from_name(func.name)}"]

    if func.parameters:
        lines.append(" *")
        for param in func.parameters:
            lines.append(f" * @param {param.name} {_infer_parameter_description(param, func.name)}")

    if func.return_type and func.return_type.lower() != "void":
        lines.append(" *")
        lines.append(f" * @return {_infer_return_description(func.return_type, func.name)}")

    lines.append(" */")
    return "\n".join(lines)


# =============================================================================
# Main Generator Helpers
# =============================================================================


def _process_file_for_docstrings(
    file_path: str,
    parser: "FunctionSignatureParser",
    doc_style: DocstringStyle,
    language: str,
    overwrite_existing: bool,
    skip_private: bool,
) -> Tuple[int, int, int, int, List[GeneratedDocstring]]:
    """Process a single file and generate docstrings for its functions.

    Args:
        file_path: Path to the source file
        parser: FunctionSignatureParser instance
        doc_style: Docstring style to use
        language: Programming language
        overwrite_existing: Whether to overwrite existing docstrings
        skip_private: Whether to skip private functions

    Returns:
        Tuple of (total, documented, generated, skipped, docstrings)
    """
    total = 0
    documented = 0
    generated = 0
    skipped = 0
    docstrings: List[GeneratedDocstring] = []

    functions = parser.parse_file(file_path)
    total = len(functions)

    for func in functions:
        should_skip, _ = _should_skip_function(func, skip_private)
        if should_skip:
            skipped += 1
            continue

        if func.existing_docstring and not overwrite_existing:
            documented += 1
            continue

        docstring = _generate_docstring_for_function(func, doc_style, language)
        docstrings.append(docstring)
        generated += 1

    return total, documented, generated, skipped, docstrings


def _apply_docstrings_to_files(
    docstrings_by_file: Dict[str, List[GeneratedDocstring]],
    language: str,
) -> List[str]:
    """Apply generated docstrings to files.

    Args:
        docstrings_by_file: Docstrings grouped by file path
        language: Programming language

    Returns:
        List of modified file paths
    """
    files_modified = []
    for file_path, docstrings in docstrings_by_file.items():
        try:
            if _apply_docstring_to_file(file_path, docstrings, language):
                files_modified.append(file_path)
        except Exception as e:
            logger.error("file_write_error", file=file_path, error=str(e))
            sentry_sdk.capture_exception(e)
    return files_modified


# =============================================================================
# Main Generator
# =============================================================================


def _detect_project_style(project_folder: str, language: str) -> DocstringStyle:
    """Auto-detect docstring style from existing code.

    Args:
        project_folder: Project root
        language: Programming language

    Returns:
        Detected style or default for language
    """
    defaults = {
        "python": DocstringStyle.GOOGLE,
        "typescript": DocstringStyle.JSDOC,
        "javascript": DocstringStyle.JSDOC,
        "java": DocstringStyle.JAVADOC,
    }
    return defaults.get(language, DocstringStyle.GOOGLE)


def _generate_docstring_for_function(
    func: FunctionSignature,
    style: DocstringStyle,
    language: str,
) -> GeneratedDocstring:
    """Select a style-appropriate generator and return a GeneratedDocstring for func."""
    generators = {
        DocstringStyle.GOOGLE: _generate_google_docstring,
        DocstringStyle.NUMPY: _generate_numpy_docstring,
        DocstringStyle.SPHINX: _generate_sphinx_docstring,
        DocstringStyle.JSDOC: _generate_jsdoc,
        DocstringStyle.JAVADOC: _generate_javadoc,
    }

    generator = generators.get(style, _generate_google_docstring)
    docstring = generator(func)

    return GeneratedDocstring(
        function_name=func.name,
        file_path=func.file_path,
        line_number=func.start_line,
        docstring=docstring,
        style=style,
        confidence=DocstringDefaults.BASIC_INFERENCE_CONFIDENCE,
        inferred_description=True,
    )


def _should_skip_function(func: FunctionSignature, skip_private: bool = True) -> Tuple[bool, str]:
    """Check if function should be skipped.

    Args:
        func: Function signature
        skip_private: Whether to skip private functions

    Returns:
        Tuple of (should_skip, reason)
    """
    if skip_private and func.name.startswith("_") and not func.name.startswith("__"):
        return True, "private function"
    if func.name.startswith("__") and func.name.endswith("__") and func.name != "__init__":
        return True, "dunder method"
    return False, ""


def _format_docstring_block(doc: GeneratedDocstring, func_line: str, language: str) -> tuple[str, int]:
    """Format a docstring block and return (formatted_text, insert_idx)."""
    indent = len(func_line) - len(func_line.lstrip())
    indent_str = func_line[:indent]
    if language == "python":
        body_indent = indent_str + "    "
        insert_idx_offset = 1
    else:
        body_indent = indent_str
        insert_idx_offset = 0
    docstring_lines = doc.docstring.split("\n")
    indented = [body_indent + ln if ln else ln for ln in docstring_lines]
    return "\n".join(indented) + "\n", insert_idx_offset


def _apply_docstring_to_file(
    file_path: str,
    docstrings: List[GeneratedDocstring],
    language: str,
) -> bool:
    """Apply generated docstrings to a file.

    Args:
        file_path: Path to file
        docstrings: Docstrings to apply (sorted by line number descending)
        language: Programming language

    Returns:
        True if file was modified
    """
    lines = read_file_lines(file_path)

    sorted_docstrings = sorted(docstrings, key=lambda d: d.line_number, reverse=True)
    modified = False
    for doc in sorted_docstrings:
        line_idx = doc.line_number - 1
        if line_idx >= len(lines):
            continue
        formatted, offset = _format_docstring_block(doc, lines[line_idx], language)
        lines.insert(line_idx + offset, formatted)
        modified = True

    if modified:
        write_file_lines(file_path, lines)

    return modified


def _process_files_batch(
    files: List[str],
    parser: "FunctionSignatureParser",
    doc_style: DocstringStyle,
    language: str,
    overwrite_existing: bool,
    skip_private: bool,
) -> Tuple[int, int, int, int, List[GeneratedDocstring], Dict[str, List[GeneratedDocstring]]]:
    """Process a batch of files and accumulate docstring results."""
    total_functions = 0
    functions_documented = 0
    functions_generated = 0
    functions_skipped = 0
    all_docstrings: List[GeneratedDocstring] = []
    docstrings_by_file: Dict[str, List[GeneratedDocstring]] = {}

    for file_path in files:
        try:
            total, documented, generated, skipped, docstrings = _process_file_for_docstrings(
                file_path, parser, doc_style, language, overwrite_existing, skip_private
            )
        except Exception as e:
            logger.warning("file_parse_error", file=file_path, error=str(e))
            sentry_sdk.capture_exception(e)
            continue
        total_functions += total
        functions_documented += documented
        functions_generated += generated
        functions_skipped += skipped
        all_docstrings.extend(docstrings)
        if docstrings:
            docstrings_by_file[file_path] = docstrings

    return total_functions, functions_documented, functions_generated, functions_skipped, all_docstrings, docstrings_by_file


def _log_and_build_result(
    totals: Tuple[int, int, int, int, List[GeneratedDocstring], Dict[str, List[GeneratedDocstring]]],
    dry_run: bool,
    language: str,
    start_time: float,
) -> DocstringGenerationResult:
    """Apply docstrings, log completion, and build the result object."""
    total_functions, functions_documented, functions_generated, functions_skipped, all_docstrings, docstrings_by_file = totals
    files_modified = _apply_docstrings_to_files(docstrings_by_file, language) if not dry_run else []
    execution_time = int((time.time() - start_time) * ConversionFactors.MILLISECONDS_PER_SECOND)
    logger.info(
        "generate_docstrings_completed",
        total_functions=total_functions,
        functions_generated=functions_generated,
        functions_documented=functions_documented,
        functions_skipped=functions_skipped,
        files_modified=len(files_modified),
        execution_time_ms=execution_time,
    )
    return DocstringGenerationResult(
        total_functions=total_functions,
        functions_documented=functions_documented,
        functions_generated=functions_generated,
        functions_skipped=functions_skipped,
        docstrings=all_docstrings,
        files_modified=files_modified,
        dry_run=dry_run,
        execution_time_ms=execution_time,
    )


def generate_docstrings_impl(
    project_folder: str,
    file_pattern: str,
    language: str,
    style: str = "auto",
    overwrite_existing: bool = False,
    dry_run: bool = True,
    skip_private: bool = True,
) -> DocstringGenerationResult:
    """Generate docstrings for undocumented functions.

    Args:
        project_folder: Root folder of the project
        file_pattern: Glob pattern for files to process (e.g., "**/*.py")
        language: Programming language
        style: Docstring style (google, numpy, sphinx, jsdoc, javadoc, auto)
        overwrite_existing: Whether to overwrite existing docstrings
        dry_run: If True, only preview without applying
        skip_private: Whether to skip private functions

    Returns:
        DocstringGenerationResult with generated docstrings
    """
    import glob

    start_time = time.time()
    logger.info(
        "generate_docstrings_started",
        project_folder=project_folder,
        file_pattern=file_pattern,
        language=language,
        style=style,
        dry_run=dry_run,
    )
    doc_style = _detect_project_style(project_folder, language) if style == "auto" else DocstringStyle(style)
    files = glob.glob(os.path.join(project_folder, file_pattern), recursive=True)
    totals = _process_files_batch(files, FunctionSignatureParser(language), doc_style, language, overwrite_existing, skip_private)
    return _log_and_build_result(totals, dry_run, language, start_time)
