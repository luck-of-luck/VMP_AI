"""Helpers for normalizing scanner-native metadata into Finding fields.

Different scanners express CWE / OWASP / references in different shapes (a bare
string, a list, or a dict). These helpers coerce those into the consistent forms
the :class:`~sast_mcp_server.models.Finding` metadata fields expect.
"""

from typing import Any


def to_str_list(value: Any) -> list[str]:
    """Coerce a string / list / scalar into a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def join_values(value: Any, separator: str = ", ") -> str:
    """Join a string/list/scalar into a single display string."""
    return separator.join(to_str_list(value))


def extract_cvss_score(value: Any) -> float | None:
    """Best-effort parse of a CVSS base score (0.0-10.0) from a scalar."""
    if value is None:
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= score <= 10.0:
        return score
    return None
