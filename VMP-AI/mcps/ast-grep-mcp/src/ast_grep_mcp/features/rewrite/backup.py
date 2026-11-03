"""Backup management for code rewrites."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ast_grep_mcp.constants import BackupDefaults
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.utils.backup import (
    copy_file_to_backup,
    generate_backup_timestamp,
    get_file_hash,
    resolve_backup_dir,
    restore_file_from_backup,
)


def _create_backup_common(
    files_to_backup: List[str],
    project_folder: str,
    prefix: str,
    extra_metadata: Optional[Dict[str, Any]] = None,
    original_hashes: Optional[Dict[str, str]] = None,
    log_event: str = "backup_created",
    extra_log_fields: Optional[Dict[str, Any]] = None,
) -> str:
    logger = get_logger("rewrite.backup")
    timestamp = generate_backup_timestamp()
    backup_base_dir = Path(project_folder) / BackupDefaults.DIR_NAME
    backup_id, backup_dir = resolve_backup_dir(prefix, timestamp, backup_base_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    metadata: Dict[str, Any] = {
        "backup_id": backup_id,
        "timestamp": datetime.now().isoformat(),
        "files": [],
        "project_folder": project_folder,
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    for file_path in files_to_backup:
        entry = copy_file_to_backup(file_path, project_folder, backup_dir, original_hashes)
        if entry is None:
            logger.warning("file_not_found_for_backup", file_path=file_path)
        else:
            metadata["files"].append(entry)

    with open(backup_dir / BackupDefaults.METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=2)

    logger.info(
        log_event,
        backup_id=backup_id,
        files_backed_up=len(metadata["files"]),
        backup_dir=str(backup_dir),
        **(extra_log_fields or {}),
    )
    return backup_id


def create_backup(files_to_backup: List[str], project_folder: str) -> str:
    return _create_backup_common(files_to_backup, project_folder, BackupDefaults.REWRITE_PREFIX)


def create_deduplication_backup(
    files_to_backup: List[str], project_folder: str, duplicate_group_id: int, strategy: str, original_hashes: Dict[str, str]
) -> str:
    extra_metadata = {
        "backup_type": "deduplication",
        "deduplication_metadata": {
            "duplicate_group_id": duplicate_group_id,
            "strategy": strategy,
            "original_hashes": original_hashes,
            "affected_files": files_to_backup,
        },
    }
    return _create_backup_common(
        files_to_backup,
        project_folder,
        BackupDefaults.DEDUP_PREFIX,
        extra_metadata=extra_metadata,
        original_hashes=original_hashes,
        log_event="deduplication_backup_created",
        extra_log_fields={"duplicate_group_id": duplicate_group_id, "strategy": strategy},
    )


def _verify_backup_files_exist(metadata: Dict[str, Any], errors: List[str]) -> None:
    for file_info in metadata.get("files", []):
        backup_path = file_info.get("backup")
        if backup_path and not os.path.exists(backup_path):
            errors.append(f"Backup file missing: {backup_path}")


def _check_file_conflicts(metadata: Dict[str, Any], warnings: List[str]) -> None:
    for file_info in metadata.get("files", []):
        original_path = file_info.get("original")
        if original_path and os.path.exists(original_path):
            current_hash = get_file_hash(original_path)
            if "original_hash" in file_info and file_info["original_hash"] != current_hash:
                warnings.append(f"File has been modified since backup: {original_path}")


def _load_integrity_metadata(backup_dir: str, metadata_path: str, result: Dict[str, Any]) -> bool:
    if not os.path.exists(backup_dir):
        result["errors"].append(f"Backup directory not found: {backup_dir}")
        return False
    if not os.path.exists(metadata_path):
        result["errors"].append(f"Backup metadata not found: {metadata_path}")
        return False
    try:
        with open(metadata_path, "r") as f:
            result["metadata"] = json.load(f)
        return True
    except (json.JSONDecodeError, IOError) as e:
        result["errors"].append(f"Failed to load metadata: {e}")
        return False


def verify_backup_integrity(backup_id: str, project_folder: str) -> Dict[str, Any]:
    logger = get_logger("rewrite.backup")
    backup_dir = os.path.join(project_folder, BackupDefaults.DIR_NAME, backup_id)
    metadata_path = os.path.join(backup_dir, BackupDefaults.METADATA_FILE)
    result: Dict[str, Any] = {"valid": False, "errors": [], "warnings": [], "metadata": None}

    if not _load_integrity_metadata(backup_dir, metadata_path, result):
        return result

    _verify_backup_files_exist(result["metadata"], result["errors"])
    _check_file_conflicts(result["metadata"], result["warnings"])
    result["valid"] = len(result["errors"]) == 0

    logger.info(
        "backup_integrity_verified",
        backup_id=backup_id,
        valid=result["valid"],
        error_count=len(result["errors"]),
        warning_count=len(result["warnings"]),
    )
    return result


def _restore_single_file(file_info: Dict[str, Any], result: Dict[str, Any]) -> None:
    backup_path = file_info.get("backup")
    original_path = file_info.get("original")
    if not backup_path or not original_path:
        result["errors"].append(f"Invalid file info in metadata: {file_info}")
        return
    try:
        restored = restore_file_from_backup(backup_path, original_path, make_parents=True)
        if restored is None:
            result["errors"].append(f"Backup file missing: {backup_path}")
            return
        result["restored_files"].append(original_path)
    except Exception as e:
        result["errors"].append(f"Failed to restore {original_path}: {e}")


def restore_backup(backup_id: str, project_folder: str) -> Dict[str, Any]:
    logger = get_logger("rewrite.backup")
    verification = verify_backup_integrity(backup_id, project_folder)
    result: Dict[str, Any] = {"success": False, "restored_files": [], "errors": []}

    if not verification["valid"]:
        result["errors"].extend(verification["errors"])
        return result

    for file_info in verification["metadata"].get("files", []):
        _restore_single_file(file_info, result)

    result["success"] = len(result["errors"]) == 0
    logger.info(
        "backup_restored",
        backup_id=backup_id,
        success=result["success"],
        restored_count=len(result["restored_files"]),
        error_count=len(result["errors"]),
    )
    return result


def _calculate_backup_size(backup_dir: str) -> int:
    """Calculate total size of all files in backup directory.

    Args:
        backup_dir: Path to backup directory

    Returns:
        Total size in bytes
    """
    return sum(os.path.getsize(os.path.join(backup_dir, root, file)) for root, _, files in os.walk(backup_dir) for file in files)


def _build_backup_info(metadata: Dict[str, Any], backup_name: str, backup_size: int) -> Dict[str, Any]:
    """Build backup information dictionary from metadata.

    Args:
        metadata: Backup metadata loaded from JSON
        backup_name: Name of the backup directory
        backup_size: Total size of backup in bytes

    Returns:
        Formatted backup information dictionary
    """
    backup_info = {
        "backup_id": metadata.get("backup_id", backup_name),
        "timestamp": metadata.get("timestamp"),
        "backup_type": metadata.get("backup_type", "standard"),
        "file_count": len(metadata.get("files", [])),
        "size_bytes": backup_size,
        "project_folder": metadata.get("project_folder"),
    }

    # Add deduplication info if present
    if "deduplication_metadata" in metadata:
        dedup_meta = metadata["deduplication_metadata"]
        backup_info["deduplication_info"] = {
            "duplicate_group_id": dedup_meta.get("duplicate_group_id"),
            "strategy": dedup_meta.get("strategy"),
        }

    return backup_info


def _load_backup_info(backup_dir: str, backup_name: str, logger: Any) -> Optional[Dict[str, Any]]:
    """Load and parse backup information from a backup directory.

    Args:
        backup_dir: Full path to backup directory
        backup_name: Name of the backup
        logger: Logger instance

    Returns:
        Backup info dict or None if invalid
    """
    metadata_path = os.path.join(backup_dir, BackupDefaults.METADATA_FILE)

    # Skip if no metadata
    if not os.path.exists(metadata_path):
        return None

    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        backup_size = _calculate_backup_size(backup_dir)
        return _build_backup_info(metadata, backup_name, backup_size)

    except (json.JSONDecodeError, IOError) as e:
        logger.warning("failed_to_load_backup_metadata", backup_name=backup_name, error=str(e))
        return None


def list_available_backups(project_folder: str) -> List[Dict[str, Any]]:
    """List all available backups in the project.

    Args:
        project_folder: Project root folder

    Returns:
        List of backup information dictionaries
    """
    logger = get_logger("rewrite.backup")
    backup_base_dir = os.path.join(project_folder, BackupDefaults.DIR_NAME)

    if not os.path.exists(backup_base_dir):
        return []

    backups = []

    for backup_name in os.listdir(backup_base_dir):
        backup_dir = os.path.join(backup_base_dir, backup_name)

        # Skip if not a directory
        if not os.path.isdir(backup_dir):
            continue

        backup_info = _load_backup_info(backup_dir, backup_name, logger)
        if backup_info:
            backups.append(backup_info)

    # Sort by timestamp (newest first)
    backups.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    logger.info("listed_backups", backup_count=len(backups), project_folder=project_folder)

    return backups
