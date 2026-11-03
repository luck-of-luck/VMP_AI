"""Shared output helpers for analysis scripts."""

from typing import Any, Callable, Iterable, Mapping, Sequence

from ast_grep_mcp.constants import FormattingDefaults

LogFn = Callable[[str], None]


def print_section_header(
    log: LogFn,
    title: str,
    *,
    width: int = FormattingDefaults.WIDE_SECTION_WIDTH,
    leading_newline: bool = True,
    trailing_newline: bool = False,
) -> None:
    """Print a banner-style section header using a provided logger function."""
    separator = "=" * width
    prefix = "\n" if leading_newline else ""
    log(f"{prefix}{separator}")
    log(f" {title}")
    suffix = "\n" if trailing_newline else ""
    log(f"{separator}{suffix}")


def count_by_key(items: Iterable[Mapping[str, Any]], key: str, *, default: str = "unknown") -> dict[str, int]:
    """Count occurrences of a mapping key in a sequence of dict-like items."""
    counts: dict[str, int] = {}
    for item in items:
        raw_value = item.get(key, default)
        normalized = str(raw_value) if raw_value else default
        counts[normalized] = counts.get(normalized, 0) + 1
    return counts


def log_count_breakdown(
    log: LogFn,
    counts: Mapping[str, int],
    *,
    order: Sequence[str] | None = None,
    indent: str = "  ",
    capitalize_labels: bool = True,
) -> None:
    """Log count mappings with optional preferred key order."""
    remaining = dict(counts)

    keys: list[str] = []
    if order:
        for key in order:
            if key in remaining:
                keys.append(key)
                remaining.pop(key, None)
    keys.extend(sorted(remaining))

    for key in keys:
        label = key.capitalize() if capitalize_labels else key
        log(f"{indent}{label}: {counts.get(key, 0)}")
