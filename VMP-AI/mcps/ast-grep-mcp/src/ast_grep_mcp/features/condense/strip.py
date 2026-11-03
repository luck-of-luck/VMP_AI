"""Dead code stripping for the condense pipeline.

Removes console.log/print debug statements and debugger calls from source.
Empty-block and commented-out-code removal are not yet implemented.
"""

from __future__ import annotations

import re
from typing import List, Tuple

from ...constants import CondenseDefaults
from ...core.logging import get_logger

logger = get_logger("condense.strip")

# JS/TS debug statement patterns
_JS_CONSOLE_LOG = re.compile(r"^\s*console\.(log|debug|warn|error|info|trace)\s*\(.*\);\s*$")
_JS_DEBUGGER = re.compile(r"^\s*debugger;\s*$")

# Python debug statement patterns
_PY_PRINT = re.compile(r"^\s*print\s*\(.*\)\s*$")
_PY_BREAKPOINT = re.compile(r"^\s*(?:breakpoint|pdb\.set_trace)\s*\(\s*\)\s*$")
_PY_IMPORT_PDB = re.compile(r"^\s*import\s+pdb\s*$")

# Note: empty-block and commented-out-code patterns are not yet applied.


def strip_dead_code(source: str, language: str) -> Tuple[str, int]:
    """Remove debug statements, empty blocks, and commented-out code.

    Args:
        source: Source code text (should be normalized first).
        language: Language identifier.

    Returns:
        Tuple of (stripped_source, lines_removed_count).
    """
    lines = source.splitlines()

    if language in ("typescript", "javascript"):
        kept, removed = _strip_js_ts(lines)
    elif language == "python":
        kept, removed = _strip_python(lines)
    else:
        kept, removed = lines, 0

    return "\n".join(kept), removed


def _strip_js_ts(lines: List[str]) -> Tuple[List[str], int]:
    """Strip JS/TS debug statements and empty blocks."""
    kept: List[str] = []
    removed = 0

    for line in lines:
        if CondenseDefaults.STRIP_CONSOLE_LOG and _JS_CONSOLE_LOG.match(line):
            removed += 1
            continue
        if CondenseDefaults.STRIP_DEBUG_STATEMENTS and _JS_DEBUGGER.match(line):
            removed += 1
            continue
        kept.append(line)

    return kept, removed


_PY_DEBUG_PATTERNS = [_PY_PRINT, _PY_BREAKPOINT, _PY_IMPORT_PDB]


def _strip_python(lines: List[str]) -> Tuple[List[str], int]:
    """Strip Python debug statements and import pdb."""
    if not CondenseDefaults.STRIP_DEBUG_STATEMENTS:
        return lines, 0

    kept: List[str] = []
    removed = 0
    for line in lines:
        if any(p.match(line) for p in _PY_DEBUG_PATTERNS):
            removed += 1
        else:
            kept.append(line)
    return kept, removed
