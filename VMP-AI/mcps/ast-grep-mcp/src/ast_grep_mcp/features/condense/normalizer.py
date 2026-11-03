"""Code normalization transforms for the condense pipeline.

Rewrites source code to canonical forms that increase downstream compression
ratios by reducing redundancy (consistent quotes, removing trailing semicolons,
collapsing single-line if blocks where safe).
"""

from __future__ import annotations

import re
from typing import List, Tuple

from ...constants import CondenseDefaults
from ...core.logging import get_logger

logger = get_logger("condense.normalizer")

# Patterns for JS/TS normalization
_DOUBLE_QUOTE_STRING = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
_TRAILING_COMMA_OBJ = re.compile(r",(\s*[}\]])")
_MULTI_BLANK_LINES = re.compile(r"\n{3,}")


def normalize_source(source: str, language: str) -> Tuple[str, int]:
    """Apply normalization transforms to source for a given language.

    Args:
        source: Raw source code text.
        language: Language identifier (e.g. "python", "typescript").

    Returns:
        Tuple of (normalized_source, normalizations_applied_count).
    """
    count = 0
    result = source

    if language in ("typescript", "javascript"):
        result, n = _normalize_js_ts(result)
        count += n
    elif language == "python":
        result, n = _normalize_python(result)
        count += n
    else:
        result, n = _normalize_generic(result)
        count += n

    if CondenseDefaults.STRIP_EMPTY_LINES:
        collapsed = _MULTI_BLANK_LINES.sub("\n\n", result)
        if collapsed != result:
            count += 1
            result = collapsed

    return result, count


def _normalize_js_ts(source: str) -> Tuple[str, int]:
    """JS/TS-specific normalizations."""
    count = 0
    result = source

    if CondenseDefaults.NORMALIZE_STRING_QUOTES:
        normalized, n = _normalize_quotes_js(result)
        if n:
            result = normalized
            count += n

    if CondenseDefaults.NORMALIZE_TRAILING_COMMAS:
        new = _TRAILING_COMMA_OBJ.sub(r"\1", result)
        if new != result:
            count += result.count(",") - new.count(",")
            result = new

    return result, count


def _normalize_quotes_js(source: str) -> Tuple[str, int]:
    """Convert double-quoted strings to single quotes in JS/TS when safe.

    Skips strings that contain single quotes to avoid escaping issues.
    """
    count = 0
    lines = source.splitlines(keepends=True)
    result_lines: List[str] = []

    for line in lines:
        new_line = _double_to_single_quotes(line)
        if new_line != line:
            count += 1
        result_lines.append(new_line)

    return "".join(result_lines), count


def _double_to_single_quotes(line: str) -> str:
    """Replace double-quoted strings with single-quoted in one line."""

    def replacer(m: re.Match[str]) -> str:
        inner = m.group(1)
        # Skip if already contains single quote (would need escaping)
        if "'" in inner:
            return str(m.group(0))
        return f"'{inner}'"

    return _DOUBLE_QUOTE_STRING.sub(replacer, line)


def _normalize_python(source: str) -> Tuple[str, int]:
    """Python-specific normalizations (minimal — Python style is stable)."""
    # Remove trailing whitespace per line
    lines = source.splitlines()
    cleaned = [line.rstrip() for line in lines]
    count = sum(1 for orig, new in zip(lines, cleaned) if orig != new)
    return "\n".join(cleaned), count


def _normalize_generic(source: str) -> Tuple[str, int]:
    """Generic normalization: trailing whitespace removal only."""
    lines = source.splitlines()
    cleaned = [line.rstrip() for line in lines]
    count = sum(1 for orig, new in zip(lines, cleaned) if orig != new)
    return "\n".join(cleaned), count
