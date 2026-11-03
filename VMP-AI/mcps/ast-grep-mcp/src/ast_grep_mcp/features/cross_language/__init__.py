"""Cross-language operations feature module.

This module provides tools for:
- Multi-language search across multiple programming languages
- Pattern equivalence mapping between languages
- Language conversion (Python <-> TypeScript, etc.)
- Polyglot refactoring across language boundaries
- API binding generation from specifications
"""

from .binding_generator import generate_language_bindings_impl
from .language_converter import convert_code_language_impl
from .multi_language_search import search_multi_language_impl
from .pattern_equivalence import find_language_equivalents_impl
from .polyglot_refactoring import refactor_polyglot_impl

__all__ = [
    "search_multi_language_impl",
    "find_language_equivalents_impl",
    "convert_code_language_impl",
    "refactor_polyglot_impl",
    "generate_language_bindings_impl",
]
