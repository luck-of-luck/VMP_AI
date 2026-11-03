from __future__ import annotations

from pymongo.errors import (
    OperationFailure,
)

from ...errors import GuidanceError

_SEARCH_UNAVAILABLE_CODES = {40324, 31082, 6047401, 115}  # unrecognized stage/command, search not enabled


def _is_search_unavailable(exc: OperationFailure) -> bool:
    """Whether the failure means this server has no mongot, as opposed to a bad query or missing privilege."""
    if exc.code in _SEARCH_UNAVAILABLE_CODES:
        return True
    message = (exc.details or {}).get("errmsg", "") or str(exc)
    lowered = message.lower()
    return "$vectorsearch" in lowered or "$search" in lowered or "search index" in lowered or "mongot" in lowered


def _search_guidance(exc: OperationFailure, feature: str) -> GuidanceError:
    """Map 'search is not available here' driver errors to the enabling guidance, keeping the rest raw."""
    message = exc.details.get("errmsg", str(exc)) if exc.details else str(exc)
    return GuidanceError(
        f"{feature} is not available on this server ({message}). "
        "It requires MongoDB Atlas or a local deployment with mongot (mongodb/mongodb-atlas-local image)."
    )
