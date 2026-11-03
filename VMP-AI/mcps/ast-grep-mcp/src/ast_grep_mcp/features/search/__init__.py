"""Search feature - code search functionality using ast-grep."""

from ast_grep_mcp.features.search.service import (
    dump_syntax_tree_impl,
    find_code_by_rule_impl,
    find_code_impl,
    test_match_code_rule_impl,
)
from ast_grep_mcp.features.search.tools import register_search_tools

__all__ = [
    # Service functions
    "dump_syntax_tree_impl",
    "test_match_code_rule_impl",
    "find_code_impl",
    "find_code_by_rule_impl",
    # Registration
    "register_search_tools",
]
