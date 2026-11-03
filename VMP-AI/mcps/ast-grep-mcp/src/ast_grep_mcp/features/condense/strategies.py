"""Strategy implementations for the condense pipeline.

Maps strategy names to their behavior and expected token-reduction ratios.
The actual pipeline is in service.py; this module documents the contract.
"""

from typing import Dict

AI_CHAT_REDUCTION_RATIO = 0.85
AI_ANALYSIS_REDUCTION_RATIO = 0.40
ARCHIVAL_REDUCTION_RATIO = 0.30
POLYGLOT_REDUCTION_RATIO = 0.65

# Expected token reduction ratios (conservative estimates)
STRATEGY_REDUCTION_RATIOS: Dict[str, float] = {
    "ai_chat": AI_CHAT_REDUCTION_RATIO,  # Signatures + types + docstrings only (lossy)
    "ai_analysis": AI_ANALYSIS_REDUCTION_RATIO,  # Full source minus dead code (lossless)
    "archival": ARCHIVAL_REDUCTION_RATIO,  # Normalized, deduplicated (lossless)
    "polyglot": POLYGLOT_REDUCTION_RATIO,  # Per-language optimal selection
}

STRATEGY_DESCRIPTIONS: Dict[str, str] = {
    "ai_chat": (
        "Lossy: extract public API signatures, types, and docstrings only. "
        "Drops function bodies for low-complexity functions. ~85% token reduction."
    ),
    "ai_analysis": (
        "Lossless: full source minus dead code and debug statements. Normalizes formatting for better compression. ~40% token reduction."
    ),
    "archival": (
        "Lossless: full source, normalized, ready for downstream compression. "
        "~30% token reduction before statistical compression (zstd/PPMd)."
    ),
    "polyglot": (
        "Per-language optimal strategy selection. Uses ai_chat for code files, "
        "pass-through for config, strip-only for text. ~60-80% token reduction."
    ),
}

VALID_STRATEGIES = frozenset(STRATEGY_REDUCTION_RATIOS.keys())


def validate_strategy(strategy: str) -> bool:
    """Return True if strategy is a known strategy name."""
    return strategy in VALID_STRATEGIES


def describe_strategy(strategy: str) -> str:
    """Return human-readable description for a strategy."""
    return STRATEGY_DESCRIPTIONS.get(strategy, f"Unknown strategy: {strategy}")
