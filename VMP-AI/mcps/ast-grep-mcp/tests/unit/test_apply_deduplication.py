"""Unit tests for apply_deduplication tool (Phase 3.1 & 3.2).

Tests cover:
- Tool registration
- Input validation
- Dry-run mode response structure
- Apply mode response structure
- Backup integration (Phase 3.2)
- Rollback functionality
- Error handling

Note: This test uses fixtures from conftest.py for MCP tool access.
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import functions from modular architecture
from ast_grep_mcp.features.deduplication.applicator import (
    DeduplicationApplicator,
    _add_import_to_content,
    _generate_import_for_extracted_function,
    _plan_file_modification_order,
)
from ast_grep_mcp.features.rewrite.backup import restore_backup


class TestApplyDeduplication:
    """Tests for apply_deduplication MCP tool."""

    def test_tool_registered(self, apply_deduplication_tool) -> None:
        """Test that apply_deduplication tool is registered."""
        assert apply_deduplication_tool is not None
        assert callable(apply_deduplication_tool)

    def test_dry_run_returns_correct_structure(  # noqa: E501
        self, project_folder, simple_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that dry_run mode returns expected response structure."""
        plan = refactoring_plan_factory(files=[simple_test_files["file1"]])
        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=True)

        assert result["status"] == "preview"
        assert result["dry_run"] is True
        assert "message" in result
        assert result["strategy"] == "extract_function"
        assert "changes_preview" in result
        assert result["group_id"] == 1

    def test_apply_mode_returns_correct_structure(  # noqa: E501
        self, project_folder, simple_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that apply mode returns expected response structure."""
        plan = refactoring_plan_factory(files=[simple_test_files["file1"]])
        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        assert result["status"] == "success"
        assert result["dry_run"] is False
        assert "message" in result
        assert "backup_id" in result
        assert result["backup_id"] is not None
        assert "files_modified" in result
        assert "validation" in result

    def test_validates_project_folder_exists(self, apply_deduplication_tool, refactoring_plan_factory) -> None:
        """Test that non-existent project folders are rejected."""
        plan = refactoring_plan_factory(files=["/some/file.py"])
        with pytest.raises(ValueError, match="does not exist"):
            apply_deduplication_tool(project_folder="/non/existent/path", group_id=1, refactoring_plan=plan, dry_run=True)

    def test_validates_refactoring_plan_required(self, project_folder, apply_deduplication_tool) -> None:
        """Test that empty refactoring plan is rejected."""
        with pytest.raises(ValueError, match="refactoring_plan is required"):
            apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan={}, dry_run=True)

    def test_no_files_affected_returns_no_changes(self, project_folder, apply_deduplication_tool) -> None:
        """Test handling when no files are affected."""
        plan = {"strategy": "extract_function", "files_affected": [], "generated_code": {}}
        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=True)
        assert result["status"] == "no_changes"


class TestBackupIntegration:
    """Tests for Phase 3.2 backup integration in apply_deduplication."""

    def test_backup_created_on_apply(self, project_folder, backup_test_files, apply_deduplication_tool, refactoring_plan_factory) -> None:
        """Test that backup is created when applying changes."""
        new_content = "def func1():\n    console.log('modified')\n"
        plan = refactoring_plan_factory(files=[backup_test_files["file1"]], new_contents=[new_content])

        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        assert result["status"] == "success"
        assert result["backup_id"] is not None
        assert result["backup_id"].startswith("dedup-backup-")

        # Verify backup directory exists
        backup_dir = os.path.join(str(project_folder), ".ast-grep-backups", result["backup_id"])
        assert os.path.isdir(backup_dir)

        # Verify metadata exists
        metadata_path = os.path.join(backup_dir, "backup-metadata.json")
        assert os.path.isfile(metadata_path)

    def test_backup_metadata_contains_deduplication_info(  # noqa: E501
        self, project_folder, backup_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that backup metadata includes deduplication-specific info."""
        new_content = "def func1():\n    console.log('modified')\n"
        plan = refactoring_plan_factory(files=[backup_test_files["file1"]], new_contents=[new_content])

        result = apply_deduplication_tool(
            project_folder=str(project_folder), group_id=42, refactoring_plan=plan, dry_run=False, backup=True
        )

        # Read and verify metadata
        metadata_path = os.path.join(str(project_folder), ".ast-grep-backups", result["backup_id"], "backup-metadata.json")
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        assert metadata["backup_type"] == "deduplication"
        assert "deduplication_metadata" in metadata
        assert metadata["deduplication_metadata"]["duplicate_group_id"] == 42
        assert metadata["deduplication_metadata"]["strategy"] == "extract_function"
        assert "original_hashes" in metadata["deduplication_metadata"]

    def test_backup_preserves_original_files(  # noqa: E501
        self, project_folder, backup_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that backup contains the original file content."""
        new_content = "def func1():\n    console.log('modified')\n"
        plan = refactoring_plan_factory(files=[backup_test_files["file1"]], new_contents=[new_content])

        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        # Find backup file
        backup_dir = os.path.join(str(project_folder), ".ast-grep-backups", result["backup_id"])
        backup_file = os.path.join(backup_dir, "file1.py")

        assert os.path.isfile(backup_file)

        # Verify backup contains original content
        with open(backup_file, "r") as f:
            backup_content = f.read()
        assert backup_content == backup_test_files["original_content1"]

    def test_rollback_restores_original_content(  # noqa: E501
        self, project_folder, backup_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that rollback restores original file content."""
        new_content = "def func1():\n    console.log('modified')\n"
        plan = refactoring_plan_factory(files=[backup_test_files["file1"]], new_contents=[new_content])

        # Apply changes
        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        backup_id = result["backup_id"]

        # Verify file was modified
        with open(backup_test_files["file1"], "r") as f:
            assert f.read() == new_content

        # Rollback
        restored = restore_backup(backup_id, str(project_folder))

        # Verify original content restored
        with open(backup_test_files["file1"], "r") as f:
            restored_content = f.read()
        assert restored_content == backup_test_files["original_content1"]
        assert backup_test_files["file1"] in restored["restored_files"]

    def test_multi_file_backup_and_rollback(  # noqa: E501
        self, project_folder, backup_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test backup and rollback with multiple files."""
        new_content1 = "# Modified file 1\n"
        new_content2 = "# Modified file 2\n"
        plan = refactoring_plan_factory(
            files=[backup_test_files["file1"], backup_test_files["file2"]], new_contents=[new_content1, new_content2]
        )

        # Apply changes
        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        # Verify both files modified
        with open(backup_test_files["file1"], "r") as f:
            assert f.read() == new_content1
        with open(backup_test_files["file2"], "r") as f:
            assert f.read() == new_content2

        # Rollback
        restored = restore_backup(result["backup_id"], str(project_folder))

        # Verify both files restored
        with open(backup_test_files["file1"], "r") as f:
            assert f.read() == backup_test_files["original_content1"]
        with open(backup_test_files["file2"], "r") as f:
            assert f.read() == backup_test_files["original_content2"]
        assert len(restored["restored_files"]) == 2

    def test_no_backup_when_backup_false(  # noqa: E501
        self, project_folder, backup_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that no backup is created when backup=False."""
        new_content = "def func1():\n    console.log('modified')\n"
        plan = refactoring_plan_factory(files=[backup_test_files["file1"]], new_contents=[new_content])

        result = apply_deduplication_tool(
            project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=False
        )

        assert result["status"] == "success"
        assert result["backup_id"] is None

        # Verify no backup directory created
        backup_dir = os.path.join(str(project_folder), ".ast-grep-backups")
        if os.path.exists(backup_dir):
            # Should be empty if exists
            assert len(os.listdir(backup_dir)) == 0

    def test_backup_id_in_rollback_command(  # noqa: E501
        self, project_folder, backup_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that response includes rollback command with backup_id."""
        new_content = "# Modified\n"
        plan = refactoring_plan_factory(files=[backup_test_files["file1"]], new_contents=[new_content])

        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        assert "rollback_command" in result
        assert result["backup_id"] in result["rollback_command"]
        assert "rollback_rewrite" in result["rollback_command"]

    def test_post_validation_failure_without_backup_returns_validation_failed(  # noqa: E501
        self, project_folder, backup_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """BUG-01: post-validation failure with backup=False must not return success.

        When backup=False the backup_id is None, so _validate_and_rollback_if_needed
        previously fell through and returned None, causing the caller to build a
        'success' response despite files on disk having syntax errors. The fix
        returns status='validation_failed' instead.
        """
        from ast_grep_mcp.features.deduplication.applicator_validator import ValidationResult

        failing_result = ValidationResult(
            is_valid=False,
            errors=[{"type": "syntax_error", "file": backup_test_files["file1"], "error": "invalid syntax", "suggestion": ""}],
        )

        new_content = "def func1():\n    pass\n"
        plan = refactoring_plan_factory(files=[backup_test_files["file1"]], new_contents=[new_content])

        with patch(
            "ast_grep_mcp.features.deduplication.applicator_post_validator.RefactoringPostValidator.validate_modified_files",
            return_value=failing_result,
        ):
            result = apply_deduplication_tool(
                project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=False
            )

        assert result["status"] == "validation_failed", f"Expected 'validation_failed', got '{result['status']}'"
        assert "errors" in result
        assert len(result["errors"]) > 0
        assert result.get("backup_id") is None


class TestPhase33MultiFileOrchestration:
    """Tests for Phase 3.3 Multi-File Orchestration in apply_deduplication."""

    def test_orchestration_creates_extracted_function_file(  # noqa: E501
        self, project_folder, orchestration_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that orchestration creates new file for extracted function."""
        extracted_func = "def get_cwd():\n    import os\n    return os.getcwd()\n"
        target_file = os.path.join(orchestration_test_files["src_dir"], "utils.py")

        new_content1 = "from utils import get_cwd\n\ndef func1():\n    return get_cwd()\n"
        new_content2 = "from utils import get_cwd\n\ndef func2():\n    return get_cwd()\n"

        plan = refactoring_plan_factory(
            files=[orchestration_test_files["file1"], orchestration_test_files["file2"]],
            new_contents=[new_content1, new_content2],
            extracted_function=extracted_func,
            extract_to_file=target_file,
            function_name="get_cwd",
        )

        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        assert result["status"] == "success"

        # Verify extracted function file was created
        assert os.path.isfile(target_file)
        with open(target_file, "r") as f:
            content = f.read()
        assert "def get_cwd():" in content

    def test_orchestration_creates_file_before_updates(  # noqa: E501
        self, project_folder, orchestration_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that extracted function file is created before updating source files."""
        extracted_func = "def common_func():\n    pass\n"
        target_file = os.path.join(orchestration_test_files["src_dir"], "_common.py")

        plan = refactoring_plan_factory(
            files=[orchestration_test_files["file1"]],
            new_contents=["# Modified\n"],
            extracted_function=extracted_func,
            extract_to_file=target_file,
        )

        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        assert result["status"] == "success"

        # Both files should be in modified list, with target first
        assert target_file in result["files_modified"]
        assert orchestration_test_files["file1"] in result["files_modified"]

    def test_orchestration_atomic_rollback_on_failure(  # noqa: E501
        self, project_folder, orchestration_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that all changes are rolled back on failure."""
        extracted_func = "def common_func():\n    pass\n"
        target_file = os.path.join(orchestration_test_files["src_dir"], "utils.py")

        # First file will succeed, second will have invalid path
        non_existent = os.path.join(str(project_folder), "nonexistent", "deep", "file.py")

        plan = refactoring_plan_factory(
            files=[orchestration_test_files["file1"]],
            new_contents=["# Modified file 1\n"],
            extracted_function=extracted_func,
            extract_to_file=target_file,
        )

        # Add a file that doesn't exist to trigger failure after first write
        plan["generated_code"]["replacements"][non_existent] = {"new_content": "# This should fail\n"}
        plan["files_affected"].append(non_existent)

        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        # Should succeed because non-existent file is skipped
        assert result["status"] == "success"

        # Verify file1 was modified
        with open(orchestration_test_files["file1"], "r") as f:
            assert "Modified" in f.read()

    def test_orchestration_appends_to_existing_file(  # noqa: E501
        self, project_folder, orchestration_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test that extracted function is appended to existing file."""
        # Create existing utils file
        target_file = os.path.join(orchestration_test_files["src_dir"], "utils.py")
        existing_content = "# Existing utilities\n\ndef existing_func():\n    pass\n"
        with open(target_file, "w") as f:
            f.write(existing_content)

        extracted_func = "def new_func():\n    pass\n"

        plan = refactoring_plan_factory(
            files=[orchestration_test_files["file1"]],
            new_contents=["# Modified\n"],
            extracted_function=extracted_func,
            extract_to_file=target_file,
        )

        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        assert result["status"] == "success"

        # Verify both existing and new content are present
        with open(target_file, "r") as f:
            content = f.read()
        assert "existing_func" in content
        assert "new_func" in content

    def test_orchestration_handles_multiple_files_atomically(  # noqa: E501
        self, project_folder, orchestration_test_files, apply_deduplication_tool, refactoring_plan_factory
    ) -> None:
        """Test atomic modification of multiple files."""
        extracted_func = "def shared_func():\n    return 42\n"
        target_file = os.path.join(orchestration_test_files["src_dir"], "_shared.py")

        new_content1 = "def func1():\n    from _shared import shared_func\n    return shared_func()\n"
        new_content2 = "def func2():\n    from _shared import shared_func\n    return shared_func()\n"

        plan = refactoring_plan_factory(
            files=[orchestration_test_files["file1"], orchestration_test_files["file2"]],
            new_contents=[new_content1, new_content2],
            extracted_function=extracted_func,
            extract_to_file=target_file,
            function_name="shared_func",
        )

        result = apply_deduplication_tool(project_folder=str(project_folder), group_id=1, refactoring_plan=plan, dry_run=False, backup=True)

        assert result["status"] == "success"
        assert len(result["files_modified"]) == 3  # target + 2 source files

        # Verify all files exist and have correct content
        assert os.path.isfile(target_file)
        with open(orchestration_test_files["file1"], "r") as f:
            assert "shared_func" in f.read()
        with open(orchestration_test_files["file2"], "r") as f:
            assert "shared_func" in f.read()


class TestOrchestrationHelperFunctions:
    """Tests for Phase 3.3 orchestration helper functions."""

    def test_plan_file_modification_order_basic(self, project_folder) -> None:
        """Test _plan_file_modification_order returns correct structure."""
        files = [os.path.join(str(project_folder), "file1.py")]
        generated_code = {
            "extracted_function": "def func():\n    pass\n",
            "function_name": "func",
            "extract_to_file": os.path.join(str(project_folder), "utils.py"),
            "replacements": {},
        }

        plan = _plan_file_modification_order(
            files_to_modify=files,
            generated_code=generated_code,
            extract_to_file=None,
            project_folder=str(project_folder),
            language="python",
        )

        assert "create_files" in plan
        assert "update_files" in plan
        assert "import_additions" in plan
        assert len(plan["create_files"]) == 1
        assert len(plan["update_files"]) == 1

    def test_add_import_to_content_python(self) -> None:
        """Test _add_import_to_content for Python files."""
        content = "import os\n\ndef main():\n    pass\n"
        import_stmt = "from utils import helper"

        result = _add_import_to_content(content, import_stmt, "python")

        assert "from utils import helper" in result
        # Should be after existing imports
        assert result.index("from utils import helper") > result.index("import os")

    def test_add_import_to_content_python_no_existing_imports(self) -> None:
        """Test _add_import_to_content when no imports exist."""
        content = "def main():\n    pass\n"
        import_stmt = "from utils import helper"

        result = _add_import_to_content(content, import_stmt, "python")

        assert result.startswith("from utils import helper")

    def test_add_import_to_content_typescript(self) -> None:
        """Test _add_import_to_content for TypeScript files."""
        content = "import { useState } from 'react';\n\nfunction App() {}\n"
        import_stmt = "import { helper } from './utils'"

        result = _add_import_to_content(content, import_stmt, "typescript")

        assert "import { helper } from './utils'" in result

    def test_add_import_to_content_skips_duplicate(self) -> None:
        """Test that duplicate imports are not added."""
        content = "import os\nfrom utils import helper\n\ndef main():\n    pass\n"
        import_stmt = "from utils import helper"

        result = _add_import_to_content(content, import_stmt, "python")

        # Should appear only once
        assert result.count("from utils import helper") == 1

    def test_add_import_ignores_function_local_import(self) -> None:
        """BUG-10: indented function-local imports must not be used as anchor."""
        content = (
            "def fetch():\n"
            "    import requests\n"
            "    return requests.get('http://example.com')\n"
        )
        import_stmt = "from utils import helper"

        result = _add_import_to_content(content, import_stmt, "python")

        # Import must appear at the top of the file (before the function def),
        # not mid-function after the indented 'import requests'.
        lines = result.splitlines()
        import_line = next(i for i, line in enumerate(lines) if "from utils import helper" in line)
        def_line = next(i for i, line in enumerate(lines) if line.startswith("def fetch"))
        assert import_line < def_line, (
            "Import was inserted inside the function body instead of at module level"
        )

    def test_add_import_preserves_module_docstring(self) -> None:
        """BUG-10: inserting import when no imports exist must not demote module docstring."""
        content = '"""Module docstring."""\n\ndef main():\n    pass\n'
        import_stmt = "from utils import helper"

        result = _add_import_to_content(content, import_stmt, "python")

        lines = result.splitlines()
        # Docstring must remain the first non-empty line
        first_nonempty = next(line for line in lines if line.strip())
        assert first_nonempty.startswith('"""'), (
            f"Module docstring was demoted; first non-empty line is: {first_nonempty!r}"
        )
        assert "from utils import helper" in result

    def test_add_import_preserves_multiline_module_docstring(self) -> None:
        """BUG-10: multi-line module docstring must also be preserved."""
        content = (
            '"""Multi-line\n'
            "module docstring.\n"
            '"""\n'
            "\n"
            "def main():\n"
            "    pass\n"
        )
        import_stmt = "from utils import helper"

        result = _add_import_to_content(content, import_stmt, "python")

        lines = result.splitlines()
        first_nonempty = next(line for line in lines if line.strip())
        assert first_nonempty.startswith('"""'), (
            f"Multi-line module docstring was demoted; first line is: {first_nonempty!r}"
        )
        assert "from utils import helper" in result

    def test_generate_import_for_extracted_function(self, project_folder) -> None:
        """Test _generate_import_for_extracted_function generates correct imports."""
        source = os.path.join(str(project_folder), "src", "file.py")
        target = os.path.join(str(project_folder), "src", "utils.py")

        result = _generate_import_for_extracted_function(
            source_file=source, target_file=target, function_name="helper", project_folder=str(project_folder), language="python"
        )

        assert "helper" in result
        assert "import" in result

    def test_generate_import_one_parent_directory_up(self, project_folder) -> None:
        """BUG-09: ../shared/utils.py must yield two dots, not four."""
        source = os.path.join(str(project_folder), "src", "pkg", "file.py")
        target = os.path.join(str(project_folder), "src", "shared", "utils.py")

        result = _generate_import_for_extracted_function(
            source_file=source, target_file=target, function_name="helper", project_folder=str(project_folder), language="python"
        )

        assert result == "from ..shared.utils import helper"

    def test_generate_import_two_parent_directories_up(self, project_folder) -> None:
        """BUG-09: ../../common/helpers.py must yield three dots."""
        source = os.path.join(str(project_folder), "src", "pkg", "sub", "file.py")
        target = os.path.join(str(project_folder), "src", "common", "helpers.py")

        result = _generate_import_for_extracted_function(
            source_file=source, target_file=target, function_name="helper", project_folder=str(project_folder), language="python"
        )

        assert result == "from ...common.helpers import helper"

    def test_generate_import_target_in_parent_directory(self, project_folder) -> None:
        """BUG-09: ../utils.py (bare parent-dir module) must yield two dots."""
        source = os.path.join(str(project_folder), "src", "pkg", "file.py")
        target = os.path.join(str(project_folder), "src", "utils.py")

        result = _generate_import_for_extracted_function(
            source_file=source, target_file=target, function_name="helper", project_folder=str(project_folder), language="python"
        )

        assert result == "from ..utils import helper"

    def test_generate_import_same_directory_unchanged(self, project_folder) -> None:
        """Same-directory targets keep their pre-BUG-09 non-relative form."""
        source = os.path.join(str(project_folder), "src", "file.py")
        target = os.path.join(str(project_folder), "src", "utils.py")

        result = _generate_import_for_extracted_function(
            source_file=source, target_file=target, function_name="helper", project_folder=str(project_folder), language="python"
        )

        assert result == "from utils import helper"

    def test_generate_import_subdirectory_unchanged(self, project_folder) -> None:
        """Subdirectory targets keep their pre-BUG-09 dotted-path form."""
        source = os.path.join(str(project_folder), "src", "file.py")
        target = os.path.join(str(project_folder), "src", "shared", "utils.py")

        result = _generate_import_for_extracted_function(
            source_file=source, target_file=target, function_name="helper", project_folder=str(project_folder), language="python"
        )

        assert result == "from shared.utils import helper"


class TestNormalizeReplacementKeys:
    """Regression tests for BUG-02: relative replacement keys must match plan paths.

    The pre-validator accepts relative replacement keys (joining with
    project_folder), but the executor looks up replacements by the absolute
    orchestration-plan path. Without normalization the lookup misses, the
    original content is written back unchanged, and the file is reported as
    successfully modified.
    """

    def test_relative_key_replacement_applied(self, apply_deduplication_tool, tmp_path) -> None:
        """Relative replacement key must actually rewrite the file content."""
        target = tmp_path / "module.py"
        target.write_text("def duplicate():\n    return 1\n")

        relative_key = "module.py"
        new_content = "def deduplicated():\n    return extracted()\n"

        plan = {
            "strategy": "extract_function",
            "language": "python",
            "files_affected": [str(target)],
            "generated_code": {
                "replacements": {
                    relative_key: {"new_content": new_content},
                }
            },
        }

        result = apply_deduplication_tool(
            project_folder=str(tmp_path),
            group_id=1,
            refactoring_plan=plan,
            dry_run=False,
            backup=False,
        )

        assert result["status"] == "success", result
        assert "deduplicated" in target.read_text(), "relative-key replacement was not applied"

    def test_absolute_key_replacement_still_works(self, apply_deduplication_tool, tmp_path) -> None:
        """Absolute replacement keys must continue to work after normalization."""
        target = tmp_path / "module.py"
        target.write_text("def duplicate():\n    return 1\n")

        new_content = "def deduplicated():\n    return extracted()\n"

        plan = {
            "strategy": "extract_function",
            "language": "python",
            "files_affected": [str(target)],
            "generated_code": {
                "replacements": {
                    str(target): {"new_content": new_content},
                }
            },
        }

        result = apply_deduplication_tool(
            project_folder=str(tmp_path),
            group_id=1,
            refactoring_plan=plan,
            dry_run=False,
            backup=False,
        )

        assert result["status"] == "success", result
        assert "deduplicated" in target.read_text()

    def test_normalize_replacement_keys_resolves_relative(self, tmp_path) -> None:
        """_normalize_replacement_keys converts relative keys to absolute."""
        applicator = DeduplicationApplicator()
        replacements = {
            "src/foo.py": {"new_content": "foo"},
            str(tmp_path / "bar.py"): {"new_content": "bar"},
        }

        normalized = applicator._normalize_replacement_keys(replacements, str(tmp_path))

        assert str(tmp_path / "src/foo.py") in normalized
        assert str(tmp_path / "bar.py") in normalized
        assert "src/foo.py" not in normalized

    def test_normalize_replacement_keys_empty(self, tmp_path) -> None:
        """_normalize_replacement_keys handles empty replacements."""
        applicator = DeduplicationApplicator()
        assert applicator._normalize_replacement_keys({}, str(tmp_path)) == {}
