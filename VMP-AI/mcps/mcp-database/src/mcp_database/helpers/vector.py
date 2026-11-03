from __future__ import annotations

import math
from typing import Any

from ..errors import QueryValidationError

METRICS = frozenset({"cosine", "l2", "inner_product", "l1"})
MAX_DIMENSIONS = 16000
MIN_CANDIDATES = 100
MAX_CANDIDATES = 10000


def ensure_vector(vector: Any) -> list[float]:
    """The query vector as a non-empty list of finite numbers, or a clear validation error."""
    if not isinstance(vector, list) or not vector:
        raise QueryValidationError("'vector' must be a non-empty list of numbers")
    if len(vector) > MAX_DIMENSIONS:
        raise QueryValidationError(f"'vector' has {len(vector)} dimensions (max {MAX_DIMENSIONS})")
    values: list[float] = []
    for item in vector:
        if isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item):
            raise QueryValidationError("'vector' must contain only finite numbers")
        values.append(float(item))
    return values


def ensure_metric(metric: str) -> str:
    """The metric name if it is one of the supported distance metrics."""
    if metric not in METRICS:
        supported = ", ".join(sorted(METRICS))
        raise QueryValidationError(f"Unknown metric '{metric}' (supported: {supported})")
    return metric


def clamp_candidates(
    num_candidates: int | None, limit: int, min_c: int = MIN_CANDIDATES, max_c: int = MAX_CANDIDATES
) -> int:
    """MongoDB numCandidates: caller's value bounded to [min_c, max_c], defaulting to 10x the limit."""
    if num_candidates is None:
        num_candidates = limit * 10
    if not isinstance(num_candidates, int) or isinstance(num_candidates, bool) or num_candidates <= 0:
        raise QueryValidationError("'num_candidates' must be a positive integer")
    return max(min_c, min(num_candidates, max_c))


def ensure_scalar_filter(flt: Any) -> dict[str, Any] | None:
    """A flat column->scalar equality map for SQL engines, or None."""
    if flt is None:
        return None
    if not isinstance(flt, dict):
        raise QueryValidationError("'filter' must be an object mapping columns to scalar values")
    for key, value in flt.items():
        if not isinstance(key, str) or not key:
            raise QueryValidationError("'filter' keys must be non-empty strings")
        if isinstance(value, (dict, list)):
            raise QueryValidationError(f"'filter' value for '{key}' must be a scalar (nested filters are MongoDB-only)")
    return flt
