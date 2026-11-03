"""Documentation generation feature module.

This module provides tools for:
- Auto-generating docstrings/JSDoc from function signatures
- Creating README sections from code structure
- Building API documentation from route definitions
- Generating changelogs from git commits
- Keeping documentation synchronized with code
"""

from .api_docs_generator import generate_api_docs_impl
from .changelog_generator import generate_changelog_impl
from .docstring_generator import generate_docstrings_impl
from .readme_generator import generate_readme_sections_impl
from .sync_checker import sync_documentation_impl

__all__ = [
    "generate_docstrings_impl",
    "generate_readme_sections_impl",
    "generate_api_docs_impl",
    "generate_changelog_impl",
    "sync_documentation_impl",
]
