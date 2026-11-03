"""Code condensation feature module.

Provides a semantic extraction + normalization + dead-code-strip pipeline
that achieves 30–85% token reduction depending on strategy.

Tools:
- condense_extract_surface: Extract public API surface (exports, signatures, types)
- condense_normalize: Rewrite code to canonical forms before compression
- condense_strip: Remove dead code, debug statements, unused imports
- condense_pack: Combined pipeline (normalize → strip → extract)
- condense_estimate: Estimate reduction ratio without modifying files
- condense_train_dictionary: Train a zstd dictionary for improved compression

Modules:
- service: Core condensation logic (extract_surface_impl, condense_pack_impl)
- estimator: Non-destructive reduction estimation
- normalizer: Code normalization transforms
- strip: Dead code removal
- strategies: Strategy definitions and validation
- dictionary: zstd dictionary training
- tools: MCP tool registrations
"""

from ast_grep_mcp.features.condense.dictionary import train_dictionary_impl
from ast_grep_mcp.features.condense.estimator import estimate_condensation_impl
from ast_grep_mcp.features.condense.normalizer import normalize_source
from ast_grep_mcp.features.condense.service import condense_pack_impl, extract_surface_impl
from ast_grep_mcp.features.condense.strip import strip_dead_code
from ast_grep_mcp.features.condense.tools import register_condense_tools

__all__ = [
    "train_dictionary_impl",
    "estimate_condensation_impl",
    "normalize_source",
    "condense_pack_impl",
    "extract_surface_impl",
    "strip_dead_code",
    "register_condense_tools",
]
