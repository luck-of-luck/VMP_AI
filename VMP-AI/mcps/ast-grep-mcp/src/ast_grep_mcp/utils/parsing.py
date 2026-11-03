"""Line-oriented parsing utilities for docstring and blank-line handling.

Shared primitives used by complexity analysis, deduplication, and other
features that need to detect triple-quoted strings or skip blank lines.
"""

from typing import List, Optional

__all__ = [
    "detect_triple_quote",
    "skip_blank_lines",
]


def detect_triple_quote(line: str) -> Optional[str]:
    """Return the triple-quote delimiter if line starts with one, else None."""
    if line.startswith('"""'):
        return '"""'
    if line.startswith("'''"):
        return "'''"
    return None


def skip_blank_lines(lines: List[str], start: int) -> int:
    """Return index of first non-blank line at or after start, or len(lines)."""
    i = start
    while i < len(lines) and not lines[i].strip():
        i += 1
    return i
