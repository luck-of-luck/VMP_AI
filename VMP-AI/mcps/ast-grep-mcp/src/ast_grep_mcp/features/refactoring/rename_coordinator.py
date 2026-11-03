"""Coordinator for multi-file symbol renaming operations.

Handles:
- Planning file modification order
- Atomic updates across files
- Import/export updates
- Rollback on failure
"""

import re
from typing import Dict, List, Optional

from ast_grep_mcp.core.logging import get_logger

from ...features.rewrite.backup import create_backup, restore_backup
from ...models.refactoring import (
    RenameSymbolResult,
    ScopeInfo,
    SymbolReference,
)
from ...utils.text import read_file_lines, write_file_lines
from .renamer import SymbolRenamer

logger = get_logger(__name__)


class RenameCoordinator:
    """Coordinates multi-file symbol renaming."""

    def __init__(self, language: str) -> None:
        """Initialize coordinator.

        Args:
            language: Programming language
        """
        self.language = language
        self.renamer = SymbolRenamer(language)

    def rename_symbol(
        self,
        project_folder: str,
        old_name: str,
        new_name: str,
        scope: str = "project",
        file_filter: Optional[str] = None,
        dry_run: bool = True,
    ) -> RenameSymbolResult:
        """Rename a symbol across the project.

        Args:
            project_folder: Project root folder
            old_name: Current symbol name
            new_name: New symbol name
            scope: Scope to rename in ('project', 'file', 'function')
            file_filter: Optional glob pattern to filter files
            dry_run: If True, only preview changes

        Returns:
            RenameSymbolResult with success status and details
        """
        logger.info(
            "rename_symbol_started",
            old_name=old_name,
            new_name=new_name,
            scope=scope,
            dry_run=dry_run,
        )

        try:
            result = self._resolve_rename(
                project_folder=project_folder,
                old_name=old_name,
                new_name=new_name,
                file_filter=file_filter,
                dry_run=dry_run,
            )
            return result
        except Exception as e:
            logger.error("rename_symbol_failed", error=str(e))
            return RenameSymbolResult(
                success=False,
                old_name=old_name,
                new_name=new_name,
                error=str(e),
            )

    def _resolve_rename(
        self,
        project_folder: str,
        old_name: str,
        new_name: str,
        file_filter: Optional[str],
        dry_run: bool,
    ) -> RenameSymbolResult:
        references = self.renamer.find_symbol_references(
            project_folder=project_folder,
            symbol_name=old_name,
            file_filter=file_filter,
        )

        if not references:
            return RenameSymbolResult(
                success=False,
                old_name=old_name,
                new_name=new_name,
                error=f"No references found for symbol '{old_name}'",
            )

        conflict_result = self._check_conflicts(references, old_name, new_name)
        if conflict_result is not None:
            return conflict_result

        diff_preview = self._generate_diff_preview(references, old_name, new_name)
        backup_id, files_modified = self._maybe_apply(project_folder, references, old_name, new_name, dry_run)

        return RenameSymbolResult(
            success=True,
            old_name=old_name,
            new_name=new_name,
            references_found=len(references),
            references_updated=len(references) if not dry_run else 0,
            files_modified=files_modified,
            diff_preview=diff_preview,
            backup_id=backup_id,
        )

    def _check_conflicts(
        self,
        references: List[SymbolReference],
        old_name: str,
        new_name: str,
    ) -> Optional[RenameSymbolResult]:
        scope_trees = self._build_scope_trees(references)
        conflicts = self.renamer.check_naming_conflicts(
            references=references,
            new_name=new_name,
            scopes=scope_trees,
        )
        if not conflicts:
            return None
        return RenameSymbolResult(
            success=False,
            old_name=old_name,
            new_name=new_name,
            conflicts=conflicts,
            error=f"Naming conflicts detected: {len(conflicts)} conflicts",
        )

    def _maybe_apply(
        self,
        project_folder: str,
        references: List[SymbolReference],
        old_name: str,
        new_name: str,
        dry_run: bool,
    ) -> tuple[Optional[str], List[str]]:
        if dry_run:
            return None, []
        backup_id, files_modified = self._apply_rename(
            project_folder=project_folder,
            references=references,
            old_name=old_name,
            new_name=new_name,
        )
        return backup_id, files_modified

    def _build_scope_trees(self, references: List[SymbolReference]) -> Dict[str, List[ScopeInfo]]:
        affected_files = list(set(ref.file_path for ref in references))
        return {fp: self.renamer.build_scope_tree(fp) for fp in affected_files}

    def _group_refs_by_file(self, references: List[SymbolReference]) -> Dict[str, List[SymbolReference]]:
        refs_by_file: Dict[str, List[SymbolReference]] = {}
        for ref in references:
            refs_by_file.setdefault(ref.file_path, []).append(ref)
        return refs_by_file

    def _format_file_diff_lines(
        self,
        file_path: str,
        file_refs: List[SymbolReference],
        old_name: str,
        new_name: str,
    ) -> List[str]:
        lines = [f"--- {file_path}", f"+++ {file_path}", ""]
        for ref in sorted(file_refs, key=lambda r: r.line):
            new_line = ref.context.replace(old_name, new_name)
            lines += [f"  Line {ref.line}:", f"- {ref.context}", f"+ {new_line}", ""]
        return lines

    def _generate_diff_preview(
        self,
        references: List[SymbolReference],
        old_name: str,
        new_name: str,
    ) -> str:
        """Generate unified diff preview of rename operation.

        Args:
            references: List of references to rename
            old_name: Old symbol name
            new_name: New symbol name

        Returns:
            Unified diff string
        """
        refs_by_file = self._group_refs_by_file(references)
        lines: List[str] = []
        for file_path, file_refs in sorted(refs_by_file.items()):
            lines.extend(self._format_file_diff_lines(file_path, file_refs, old_name, new_name))
        return "\n".join(lines)

    def _apply_file_renames(
        self,
        refs_by_file: Dict[str, List[SymbolReference]],
        old_name: str,
        new_name: str,
    ) -> List[str]:
        files_modified = []
        for file_path, file_refs in refs_by_file.items():
            self._rename_in_file(file_path=file_path, references=file_refs, old_name=old_name, new_name=new_name)
            files_modified.append(file_path)
        return files_modified

    def _apply_rename(
        self,
        project_folder: str,
        references: List[SymbolReference],
        old_name: str,
        new_name: str,
    ) -> tuple[str, List[str]]:
        """Apply rename operation to files.

        Args:
            project_folder: Project root
            references: References to rename
            old_name: Old symbol name
            new_name: New symbol name

        Returns:
            Tuple of (backup_id, files_modified)
        """
        refs_by_file = self._group_refs_by_file(references)
        backup_id = create_backup(list(refs_by_file.keys()), project_folder)

        try:
            files_modified = self._apply_file_renames(refs_by_file, old_name, new_name)
            logger.info("rename_applied", backup_id=backup_id, files_modified=len(files_modified))
            return backup_id, files_modified
        except Exception as e:
            logger.error("rename_failed_rolling_back", error=str(e))
            restore_backup(backup_id, project_folder)
            raise RuntimeError(f"Rename failed and was rolled back: {e}")

    def _rename_in_file(
        self,
        file_path: str,
        references: List[SymbolReference],
        old_name: str,
        new_name: str,
    ) -> None:
        """Rename symbol in a single file.

        Args:
            file_path: File to modify
            references: References in this file
            old_name: Old symbol name
            new_name: New symbol name
        """
        lines = read_file_lines(file_path)

        pattern = r"\b" + re.escape(old_name) + r"\b"
        sorted_refs = sorted(references, key=lambda r: r.line, reverse=True)

        for ref in sorted_refs:
            if ref.line <= len(lines):
                line_idx = ref.line - 1
                lines[line_idx] = re.sub(pattern, new_name, lines[line_idx])

        write_file_lines(file_path, lines)

        logger.debug(
            "file_renamed",
            file_path=file_path,
            references=len(references),
        )
