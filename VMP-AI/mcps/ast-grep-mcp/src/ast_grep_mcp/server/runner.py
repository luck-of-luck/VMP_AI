"""MCP server entry point."""

from mcp.server.fastmcp import FastMCP

from ast_grep_mcp.core.config import parse_args_and_get_config
from ast_grep_mcp.core.sentry import init_sentry
from ast_grep_mcp.server.registry import register_all_tools

# Create FastMCP instance
mcp = FastMCP("ast-grep")


def run_mcp_server() -> None:
    """Run the MCP server.

    This function:
    1. Parses command-line arguments and loads configuration
    2. Initializes Sentry error tracking (if configured)
    3. Registers all MCP tools from all features
    4. Starts the MCP server with stdio transport
    """
    parse_args_and_get_config()  # Sets CONFIG_PATH global
    init_sentry()  # Initialize error tracking (no-op if not configured)
    register_all_tools(mcp)  # Register all tools
    mcp.run(transport="stdio")
