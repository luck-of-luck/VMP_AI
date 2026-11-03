"""Configuration and YAML validation utilities.

This module provides utilities for validating configuration files
and YAML structures used by ast-grep.

Note: The main validate_config_file function is already implemented in
ast_grep_mcp.core.config and should be imported from there.
"""

# Re-export validate_config_file from core.config
from ast_grep_mcp.core.config import validate_config_file

__all__ = ["validate_config_file"]
