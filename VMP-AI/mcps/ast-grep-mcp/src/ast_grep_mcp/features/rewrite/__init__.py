"""Rewrite feature - code transformation and backup management."""

from ast_grep_mcp.features.rewrite.backup import (
    create_backup,
    create_deduplication_backup,
    list_available_backups,
    restore_backup,
    verify_backup_integrity,
)
from ast_grep_mcp.features.rewrite.service import (
    list_backups_impl,
    rewrite_code_impl,
    rollback_rewrite_impl,
    validate_rewrites,
    validate_syntax,
)
from ast_grep_mcp.features.rewrite.tools import register_rewrite_tools
from ast_grep_mcp.utils.backup import get_file_hash

__all__ = [
    # Backup functions
    "create_backup",
    "create_deduplication_backup",
    "get_file_hash",
    "verify_backup_integrity",
    "restore_backup",
    "list_available_backups",
    # Service functions
    "rewrite_code_impl",
    "rollback_rewrite_impl",
    "list_backups_impl",
    "validate_syntax",
    "validate_rewrites",
    # Registration
    "register_rewrite_tools",
]
