"""Backup management for deduplication operations.

This module handles creating, storing, and restoring backups
during deduplication refactoring operations.
"""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from ...constants import BackupDefaults
from ...core.logging import get_logger
from ...utils.backup import (
    copy_file_to_backup,
    generate_backup_timestamp,
    get_file_hash,
    resolve_backup_dir,
    restore_file_from_backup,
)


class DeduplicationBackupManager:
    """Manages backups for deduplication operations."""

    def __init__(self, project_folder: str) -> None:
        """Initialize backup manager.

        Args:
            project_folder: Project root folder
        """
        self.project_folder = project_folder
        self.backup_base_dir = Path(project_folder) / BackupDefaults.DIR_NAME
        self.logger = get_logger("deduplication.backup")

    def create_backup(self, files: List[str], metadata: Dict[str, Any], created_files: List[str] | None = None) -> str:
        """Create backup of files before modification.

        Args:
            files: List of file paths to backup (must already exist)
            metadata: Additional metadata to store with backup
            created_files: Paths of files that will be newly created (not yet
                existing) so rollback can delete them instead of trying to
                restore them.

        Returns:
            Backup ID for later restoration
        """
        self.logger.info("create_backup_start", file_count=len(files))

        backup_id, backup_dir = self._generate_backup_id()
        backup_dir.mkdir(parents=True, exist_ok=True)

        original_hashes = self._compute_file_hashes(files)
        metadata_with_hashes = {**metadata, "original_hashes": original_hashes}

        backup_metadata: Dict[str, Any] = {
            "backup_id": backup_id,
            "backup_type": "deduplication",
            "timestamp": datetime.now().isoformat(),
            "project_folder": self.project_folder,
            "files": [],
            "created_files": created_files or [],
            "deduplication_metadata": metadata_with_hashes,
        }

        for file_path in files:
            entry = copy_file_to_backup(file_path, self.project_folder, backup_dir, original_hashes)
            if entry is None:
                self.logger.warning("file_not_found_for_backup", file=file_path)
            else:
                backup_metadata["files"].append(entry)

        metadata_path = backup_dir / BackupDefaults.METADATA_FILE
        with open(metadata_path, "w") as f:
            json.dump(backup_metadata, f, indent=2)

        self.logger.info("create_backup_complete", backup_id=backup_id, files_backed_up=len(backup_metadata["files"]))
        return backup_id

    def rollback(self, backup_id: str) -> List[str]:
        """Rollback changes using backup.

        Args:
            backup_id: Backup ID to restore from

        Returns:
            List of restored file paths
        """
        self.logger.info("rollback_start", backup_id=backup_id)

        backup_dir = self.backup_base_dir / backup_id
        metadata_path = backup_dir / BackupDefaults.METADATA_FILE

        if not metadata_path.exists():
            raise ValueError(f"Backup '{backup_id}' not found or invalid")

        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        restored_files = [path for file_info in metadata.get("files", []) if (path := self._restore_single_file(file_info)) is not None]

        deleted_files = self._delete_created_files(metadata.get("created_files", []))

        self.logger.info("rollback_complete", backup_id=backup_id, files_restored=len(restored_files), files_deleted=len(deleted_files))
        return restored_files

    def cleanup_old_backups(self, days: int = BackupDefaults.RETENTION_DAYS) -> int:
        """Remove backups older than specified days.

        Args:
            days: Number of days to keep backups

        Returns:
            Number of backups removed
        """
        if not self.backup_base_dir.exists():
            return 0

        cutoff_date = datetime.now() - timedelta(days=days)
        removed_count = 0

        for backup_dir in self.backup_base_dir.iterdir():
            if not backup_dir.is_dir():
                continue
            if self._try_cleanup_backup(backup_dir, cutoff_date):
                removed_count += 1

        return removed_count

    def get_file_hash(self, file_path: str) -> str:
        """Calculate SHA-256 hash of a file's contents.

        Args:
            file_path: Path to file

        Returns:
            SHA-256 hash as hexadecimal string
        """
        result = get_file_hash(file_path)
        if not result:
            self.logger.warning("hash_calculation_failed", file=file_path)
        return result

    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups.

        Returns:
            List of backup metadata dictionaries
        """
        if not self.backup_base_dir.exists():
            return []

        backups = []

        for backup_dir in self.backup_base_dir.iterdir():
            if not backup_dir.is_dir():
                continue

            metadata = self._load_backup_metadata(backup_dir)
            if metadata is not None:
                backups.append(metadata)

        backups.sort(key=lambda b: b.get("timestamp", ""), reverse=True)
        return backups

    # -- Private helpers --

    def _generate_backup_id(self) -> tuple[str, Path]:
        """Generate a unique backup ID with timestamp, handling collisions."""
        timestamp = generate_backup_timestamp()
        return resolve_backup_dir(BackupDefaults.DEDUP_PREFIX, timestamp, self.backup_base_dir)

    def _compute_file_hashes(self, files: List[str]) -> Dict[str, str]:
        """Compute SHA-256 hashes for all existing files."""
        return {fp: get_file_hash(fp) for fp in files if os.path.exists(fp)}

    def _delete_created_files(self, created_files: List[str]) -> List[str]:
        """Delete files that were newly created during the refactoring operation.

        These files did not exist at backup time, so they cannot be restored —
        they must be removed to return the project to its pre-operation state.

        Args:
            created_files: Absolute paths of files to delete

        Returns:
            List of paths that were successfully deleted
        """
        deleted: List[str] = []
        for file_path in created_files:
            if not os.path.exists(file_path):
                self.logger.debug("created_file_already_gone", file=file_path)
                continue
            try:
                os.remove(file_path)
                self.logger.debug("created_file_deleted", file=file_path)
                deleted.append(file_path)
            except Exception as e:
                self.logger.error("created_file_delete_failed", file=file_path, error=str(e))
        return deleted

    def _restore_single_file(self, file_info: Dict[str, str]) -> str | None:
        """Restore a single file from backup.

        Returns:
            Original file path if restored, or None on skip/error.
        """
        original_path = file_info["original"]
        backup_path = file_info["backup"]

        try:
            result = restore_file_from_backup(backup_path, original_path)
            if result is None:
                self.logger.warning("backup_file_not_found", original=original_path, backup=backup_path)
                return None
            self.logger.debug("file_restored", file=original_path)
            return result
        except Exception as e:
            self.logger.error("restore_failed", file=original_path, error=str(e))
            return None

    def _load_backup_metadata(self, backup_dir: Path) -> Dict[str, Any] | None:
        """Load and parse backup-metadata.json from a backup directory.

        Returns:
            Parsed metadata dict, or None if missing/unreadable.
        """
        metadata_path = backup_dir / BackupDefaults.METADATA_FILE
        if not metadata_path.exists():
            return None
        try:
            with open(metadata_path, "r") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except Exception as e:
            self.logger.warning("metadata_read_failed", backup_dir=str(backup_dir), error=str(e))
            return None

    def _try_cleanup_backup(self, backup_dir: Path, cutoff_date: datetime) -> bool:
        """Attempt to remove a single backup if older than cutoff.

        Returns:
            True if the backup was removed.
        """
        metadata = self._load_backup_metadata(backup_dir)
        if metadata is None:
            return False

        timestamp_str = metadata.get("timestamp", "")
        if not timestamp_str:
            return False

        try:
            backup_date = datetime.fromisoformat(timestamp_str)
            if backup_date >= cutoff_date:
                return False
            shutil.rmtree(backup_dir)
            self.logger.info(
                "old_backup_removed",
                backup_id=metadata.get("backup_id"),
                age_days=(datetime.now() - backup_date).days,
            )
            return True
        except Exception as e:
            self.logger.warning("cleanup_failed", backup_dir=str(backup_dir), error=str(e))
            return False
