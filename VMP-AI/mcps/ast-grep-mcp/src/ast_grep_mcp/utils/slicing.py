"""Utility helpers for bounded top-N result views."""

from collections.abc import Iterable
from itertools import islice
from typing import TypeVar

T = TypeVar("T")


def take_top_n(items: Iterable[T], limit: int) -> list[T]:
    """Return the first ``limit`` items from an iterable.

    Preserves input order and gracefully handles non-positive limits.
    """
    if limit <= 0:
        return []
    return list(islice(items, limit))
