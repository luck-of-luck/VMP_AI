"""ast-grep MCP Server - Entry point.

This module serves as the entry point for the MCP server.
All functionality is implemented in the modular architecture under src/ast_grep_mcp/.
"""

from ast_grep_mcp.server.runner import run_mcp_server

if __name__ == "__main__":
    run_mcp_server()
