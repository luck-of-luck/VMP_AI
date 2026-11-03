"""Central tool registration for MCP server."""

from mcp.server.fastmcp import FastMCP

from ast_grep_mcp.features.complexity.tools import register_complexity_tools
from ast_grep_mcp.features.condense.tools import register_condense_tools
from ast_grep_mcp.features.cross_language.tools import register_cross_language_tools
from ast_grep_mcp.features.deduplication.tools import register_deduplication_tools
from ast_grep_mcp.features.documentation.tools import register_documentation_tools
from ast_grep_mcp.features.quality.tools import register_quality_tools
from ast_grep_mcp.features.refactoring.tools import extract_function, rename_symbol
from ast_grep_mcp.features.rewrite.tools import register_rewrite_tools
from ast_grep_mcp.features.schema.tools import register_schema_tools
from ast_grep_mcp.features.search.tools import register_search_tools


def register_all_tools(mcp: FastMCP) -> None:
    """Register all MCP tools from all features.

    This is the central registration point for all tools in the system.
    Tools are organized by feature and registered in order:
    1. Search (9 tools)
    2. Rewrite (5 tools)
    3. Refactoring (2 tools)
    4. Deduplication (6 tools)
    5. Complexity (3 tools)
    6. Quality (7 tools)
    7. Schema.org (11 tools)
    8. Documentation (5 tools)
    9. Cross-Language (5 tools)
    10. Condense (6 tools)

    Total: 59 tools
    """
    register_search_tools(mcp)
    register_rewrite_tools(mcp)
    mcp.tool()(extract_function)
    mcp.tool()(rename_symbol)
    register_deduplication_tools(mcp)
    register_complexity_tools(mcp)
    register_quality_tools(mcp)
    register_schema_tools(mcp)
    register_documentation_tools(mcp)
    register_cross_language_tools(mcp)
    register_condense_tools(mcp)
