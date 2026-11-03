"""Code execution logic for deduplication refactoring.

This module handles the actual code modifications during
deduplication refactoring operations.
"""

import os
from typing import Any, Dict, List

from ...core.logging import get_logger


class RefactoringExecutor:
    """Executes the actual code modifications for refactoring."""

    def __init__(self) -> None:
        """Initialize the refactoring executor."""
        self.logger = get_logger("deduplication.executor")

    def apply_changes(
        self, orchestration_plan: Dict[str, Any], replacements: Dict[str, Dict[str, Any]], language: str, dry_run: bool = False
    ) -> Dict[str, Any]:
        """Apply refactoring changes to files.

        Args:
            orchestration_plan: The orchestration plan with file operations
            replacements: Dictionary of file replacements
            language: Programming language
            dry_run: If True, preview changes without applying

        Returns:
            Dictionary with:
                - modified_files: List of modified file paths
                - failed_files: List of failed operations
                - dry_run: Whether this was a dry run
        """
        self.logger.info(
            "apply_changes_start",
            dry_run=dry_run,
            create_count=len(orchestration_plan.get("create_files", [])),
            update_count=len(orchestration_plan.get("update_files", [])),
        )

        modified_files: List[str] = []
        failed_files: List[Dict[str, Any]] = []

        if dry_run:
            # Preview mode - just log what would happen
            self.logger.info("dry_run_mode", message="Preview only, no changes applied")
            return {
                "modified_files": [],
                "failed_files": [],
                "dry_run": True,
                "preview": self._generate_preview(orchestration_plan, replacements),
            }

        try:
            # Step 1: Create new files for extracted functions
            create_result = self._create_files(orchestration_plan.get("create_files", []))
            modified_files.extend(create_result["created"])
            failed_files.extend(create_result["failed"])

            # Step 2: Update duplicate location files
            update_result = self._update_files(
                orchestration_plan.get("update_files", []), replacements, orchestration_plan.get("import_additions", {}), language
            )
            modified_files.extend(update_result["updated"])
            failed_files.extend(update_result["failed"])

            self.logger.info("apply_changes_complete", modified_count=len(modified_files), failed_count=len(failed_files))

        except Exception as e:
            self.logger.error("apply_changes_failed", error=str(e), modified_count=len(modified_files), failed_count=len(failed_files))
            raise

        return {"modified_files": modified_files, "failed_files": failed_files, "dry_run": False}

    def _create_files(self, create_file_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create new files for extracted functions."""
        created: List[str] = []
        failed: List[Dict[str, Any]] = []

        for create_info in create_file_list:
            target_path = create_info.get("path", "")
            content = create_info.get("content", "")
            if not target_path or not content:
                continue
            self._create_single_file(create_info, target_path, content, created, failed)

        return {"created": created, "failed": failed}

    def _create_single_file(
        self, create_info: Dict[str, Any], target_path: str, content: str, created: List[str], failed: List[Dict[str, Any]]
    ) -> None:
        """Create or append to a single file."""
        try:
            target_dir = os.path.dirname(target_path)
            if target_dir and not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)

            mode = "a" if os.path.exists(target_path) and create_info.get("append", False) else "w"
            prefix = "\n\n" if mode == "a" else ""

            with open(target_path, mode) as f:
                f.write(prefix + content)

            created.append(target_path)
            self.logger.info("file_created", file=target_path, mode=mode)
        except Exception as e:
            failed.append({"file": target_path, "operation": "create", "error": str(e)})
            self.logger.error("file_creation_failed", file=target_path, error=str(e))
            raise  # Fail fast for atomicity

    def _update_files(
        self,
        update_file_list: List[Dict[str, Any]],
        replacements: Dict[str, Dict[str, Any]],
        import_additions: Dict[str, Dict[str, Any]],
        language: str,
    ) -> Dict[str, Any]:
        """Update duplicate location files."""
        updated: List[str] = []
        failed: List[Dict[str, Any]] = []

        for update_info in update_file_list:
            file_path = update_info.get("path", "")
            if not file_path or not os.path.exists(file_path):
                self.logger.warning("update_file_missing", file=file_path)
                failed.append({"file": file_path, "error": "file not found"})
                continue
            self._update_single_file(file_path, replacements, import_additions, language, updated, failed)

        return {"updated": updated, "failed": failed}

    def _update_single_file(
        self,
        file_path: str,
        replacements: Dict[str, Dict[str, Any]],
        import_additions: Dict[str, Dict[str, Any]],
        language: str,
        updated: List[str],
        failed: List[Dict[str, Any]],
    ) -> None:
        """Read, transform, and write a single file."""
        try:
            with open(file_path, "r") as f:
                new_content = f.read()

            replacement = replacements.get(file_path, {})
            if replacement.get("new_content"):
                new_content = replacement["new_content"]

            new_content = self._apply_import_addition(new_content, file_path, import_additions, language)

            with open(file_path, "w") as f:
                f.write(new_content)

            updated.append(file_path)
            self.logger.info("file_updated", file=file_path)
        except Exception as e:
            failed.append({"file": file_path, "operation": "update", "error": str(e)})
            self.logger.error("file_update_failed", file=file_path, error=str(e))
            raise  # Fail fast for atomicity

    def _apply_import_addition(self, content: str, file_path: str, import_additions: Dict[str, Dict[str, Any]], language: str) -> str:
        """Add import statement if one is specified for this file.

        Uses a lazy import of applicator._add_import_to_content to avoid
        a circular dependency (applicator.py imports this module at the
        top level).
        """
        import_info = import_additions.get(file_path)
        if not import_info:
            return content

        from .applicator import _add_import_to_content

        return _add_import_to_content(content=content, import_statement=import_info.get("import_statement", ""), language=language)

    def _generate_preview(self, orchestration_plan: Dict[str, Any], replacements: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Generate preview of changes for dry run."""
        create_previews = [
            {
                "path": info.get("path", ""),
                "mode": "append" if info.get("append", False) else "write",
                "content_lines": len(info.get("content", "").split("\n")),
            }
            for info in orchestration_plan.get("create_files", [])
            if info.get("path")
        ]
        update_previews = [
            {
                "path": info.get("path", ""),
                "has_replacement": bool(replacements.get(info.get("path", ""), {}).get("new_content")),
                "has_import_addition": info.get("path", "") in orchestration_plan.get("import_additions", {}),
            }
            for info in orchestration_plan.get("update_files", [])
            if info.get("path")
        ]
        return {"files_to_create": create_previews, "files_to_update": update_previews}
