"""Tests for RefactoringExecutor - code execution for deduplication refactoring.

Tests cover:
- Apply changes (dry run and actual)
- File creation (new files, append mode, directory creation)
- File updates (content replacement, import additions)
- Import addition via shared _add_import_to_content
- Preview generation for dry run
- Error handling
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from ast_grep_mcp.features.deduplication.applicator import (
    _add_import_to_content,
)
from ast_grep_mcp.features.deduplication.applicator_executor import (
    RefactoringExecutor,
)


class TestRefactoringExecutorInit:
    """Tests for RefactoringExecutor initialization."""

    def test_init_creates_logger(self):
        """Test that initialization creates a logger."""
        executor = RefactoringExecutor()
        assert executor.logger is not None


class TestApplyChangesDryRun:
    """Tests for apply_changes in dry run mode."""

    def test_dry_run_returns_preview(self):
        """Test that dry run returns preview without modifying files."""
        executor = RefactoringExecutor()

        orchestration_plan = {
            "create_files": [{"path": "/tmp/new_file.py", "content": "def func(): pass"}],
            "update_files": [{"path": "/tmp/existing.py"}],
        }
        replacements = {"/tmp/existing.py": {"new_content": "updated content"}}

        result = executor.apply_changes(orchestration_plan, replacements, "python", dry_run=True)

        assert result["dry_run"] is True
        assert result["modified_files"] == []
        assert result["failed_files"] == []
        assert "preview" in result

    def test_dry_run_preview_contains_file_info(self):
        """Test that dry run preview contains file information."""
        executor = RefactoringExecutor()

        orchestration_plan = {
            "create_files": [{"path": "/tmp/new_file.py", "content": "line1\nline2\nline3", "append": False}],
            "update_files": [{"path": "/tmp/existing.py"}],
            "import_additions": {"/tmp/existing.py": {"import_statement": "from utils import func"}},
        }
        replacements = {"/tmp/existing.py": {"new_content": "updated"}}

        result = executor.apply_changes(orchestration_plan, replacements, "python", dry_run=True)

        preview = result["preview"]
        assert len(preview["files_to_create"]) == 1
        assert preview["files_to_create"][0]["path"] == "/tmp/new_file.py"
        assert preview["files_to_create"][0]["mode"] == "write"
        assert preview["files_to_create"][0]["content_lines"] == 3

        assert len(preview["files_to_update"]) == 1
        assert preview["files_to_update"][0]["has_replacement"] is True
        assert preview["files_to_update"][0]["has_import_addition"] is True


class TestApplyChangesActual:
    """Tests for apply_changes in actual (non-dry-run) mode."""

    def test_creates_new_file(self):
        """Test that apply_changes creates new files."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            new_file = os.path.join(tmpdir, "new_module.py")

            orchestration_plan = {
                "create_files": [{"path": new_file, "content": "def extracted(): pass"}],
                "update_files": [],
            }

            result = executor.apply_changes(orchestration_plan, {}, "python", dry_run=False)

            assert result["dry_run"] is False
            assert new_file in result["modified_files"]
            assert os.path.exists(new_file)

            with open(new_file) as f:
                assert "def extracted(): pass" in f.read()

    def test_creates_directory_if_needed(self):
        """Test that apply_changes creates parent directories."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            new_file = os.path.join(tmpdir, "subdir", "nested", "module.py")

            orchestration_plan = {
                "create_files": [{"path": new_file, "content": "content"}],
                "update_files": [],
            }

            result = executor.apply_changes(orchestration_plan, {}, "python", dry_run=False)

            assert new_file in result["modified_files"]
            assert os.path.exists(new_file)

    def test_updates_existing_file(self):
        """Test that apply_changes updates existing files."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            existing_file = os.path.join(tmpdir, "existing.py")
            with open(existing_file, "w") as f:
                f.write("old content")

            orchestration_plan = {
                "create_files": [],
                "update_files": [{"path": existing_file}],
            }
            replacements = {existing_file: {"new_content": "new content"}}

            result = executor.apply_changes(orchestration_plan, replacements, "python", dry_run=False)

            assert existing_file in result["modified_files"]
            with open(existing_file) as f:
                assert f.read() == "new content"

    def test_adds_import_to_updated_file(self):
        """Test that apply_changes adds imports to updated files."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            existing_file = os.path.join(tmpdir, "module.py")
            with open(existing_file, "w") as f:
                f.write("import os\n\ndef main(): pass")

            orchestration_plan = {
                "create_files": [],
                "update_files": [{"path": existing_file}],
                "import_additions": {existing_file: {"import_statement": "from utils import helper"}},
            }

            result = executor.apply_changes(orchestration_plan, {}, "python", dry_run=False)

            assert existing_file in result["modified_files"]
            with open(existing_file) as f:
                content = f.read()
                assert "from utils import helper" in content


class TestCreateFiles:
    """Tests for _create_files method."""

    def test_creates_file_with_content(self):
        """Test creating a file with content."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.py")
            create_list = [{"path": file_path, "content": "test content"}]

            result = executor._create_files(create_list)

            assert file_path in result["created"]
            assert len(result["failed"]) == 0

    def test_skips_empty_path(self):
        """Test that empty path is skipped."""
        executor = RefactoringExecutor()

        create_list = [{"path": "", "content": "content"}]
        result = executor._create_files(create_list)

        assert len(result["created"]) == 0
        assert len(result["failed"]) == 0

    def test_skips_empty_content(self):
        """Test that empty content is skipped."""
        executor = RefactoringExecutor()

        create_list = [{"path": "/tmp/file.py", "content": ""}]
        result = executor._create_files(create_list)

        assert len(result["created"]) == 0

    def test_append_mode(self):
        """Test appending to existing file."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "existing.py")
            with open(file_path, "w") as f:
                f.write("original content")

            create_list = [{"path": file_path, "content": "appended content", "append": True}]

            result = executor._create_files(create_list)

            assert file_path in result["created"]
            with open(file_path) as f:
                content = f.read()
                assert "original content" in content
                assert "appended content" in content

    def test_write_mode_overwrites(self):
        """Test write mode overwrites existing file."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "existing.py")
            with open(file_path, "w") as f:
                f.write("original content")

            create_list = [{"path": file_path, "content": "new content", "append": False}]

            executor._create_files(create_list)

            with open(file_path) as f:
                content = f.read()
                assert content == "new content"

    def test_raises_on_write_error(self):
        """Test that write errors are raised."""
        executor = RefactoringExecutor()

        with patch("builtins.open", side_effect=IOError("Permission denied")):
            with tempfile.TemporaryDirectory() as tmpdir:
                file_path = os.path.join(tmpdir, "test.py")
                create_list = [{"path": file_path, "content": "content"}]

                with pytest.raises(IOError):
                    executor._create_files(create_list)


class TestUpdateFiles:
    """Tests for _update_files method."""

    def test_updates_file_content(self):
        """Test updating file content."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "module.py")
            with open(file_path, "w") as f:
                f.write("old content")

            update_list = [{"path": file_path}]
            replacements = {file_path: {"new_content": "new content"}}

            result = executor._update_files(update_list, replacements, {}, "python")

            assert file_path in result["updated"]
            with open(file_path) as f:
                assert f.read() == "new content"

    def test_skips_nonexistent_file(self):
        """Test that nonexistent files are reported as failed, not silently skipped."""
        executor = RefactoringExecutor()

        update_list = [{"path": "/nonexistent/file.py"}]

        result = executor._update_files(update_list, {}, {}, "python")

        assert len(result["updated"]) == 0
        assert len(result["failed"]) == 1
        assert result["failed"][0]["file"] == "/nonexistent/file.py"
        assert result["failed"][0]["error"] == "file not found"

    def test_skips_empty_path(self):
        """Test that empty path is skipped."""
        executor = RefactoringExecutor()

        update_list = [{"path": ""}]

        result = executor._update_files(update_list, {}, {}, "python")

        assert len(result["updated"]) == 0

    def test_adds_import_statement(self):
        """Test adding import statement during update."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "module.py")
            with open(file_path, "w") as f:
                f.write("def main(): pass")

            update_list = [{"path": file_path}]
            import_additions = {file_path: {"import_statement": "from utils import func"}}

            result = executor._update_files(update_list, {}, import_additions, "python")

            assert file_path in result["updated"]
            with open(file_path) as f:
                content = f.read()
                assert "from utils import func" in content

    def test_raises_on_read_error(self):
        """Test that read errors are raised."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "module.py")
            with open(file_path, "w") as f:
                f.write("content")

            update_list = [{"path": file_path}]

            with patch("builtins.open", side_effect=IOError("Read error")):
                with pytest.raises(IOError):
                    executor._update_files(update_list, {}, {}, "python")


class TestAddImportToContent:
    """Tests for _add_import_to_content method."""

    def test_empty_import_returns_unchanged(self):
        """Test that empty import statement returns unchanged content."""
        content = "def main(): pass"
        result = _add_import_to_content(content, "", "python")

        assert result == content

    def test_existing_import_not_duplicated(self):
        """Test that existing import is not duplicated."""
        content = "import os\n\ndef main(): pass"
        result = _add_import_to_content(content, "import os", "python")

        assert result.count("import os") == 1

    def test_python_import_added(self):
        """Test adding Python import."""
        content = "def main(): pass"
        result = _add_import_to_content(content, "import os", "python")

        assert "import os" in result

    def test_javascript_import_added(self):
        """Test adding JavaScript import."""
        content = "function main() {}"
        result = _add_import_to_content(content, "import React from 'react'", "javascript")

        assert "import React from 'react'" in result

    def test_typescript_import_added(self):
        """Test adding TypeScript import."""
        content = "function main() {}"
        result = _add_import_to_content(content, "import { Component } from 'react'", "typescript")

        assert "import { Component } from 'react'" in result

    def test_jsx_import_added(self):
        """Test adding JSX import."""
        content = "function App() {}"
        result = _add_import_to_content(content, "import React from 'react'", "jsx")

        assert "import React from 'react'" in result

    def test_tsx_import_added(self):
        """Test adding TSX import."""
        content = "function App() {}"
        result = _add_import_to_content(content, "import React from 'react'", "tsx")

        assert "import React from 'react'" in result

    def test_java_import_added(self):
        """Test adding Java import."""
        content = "public class Main {}"
        result = _add_import_to_content(content, "import java.util.List;", "java")

        assert "import java.util.List;" in result

    def test_unknown_language_adds_at_top(self):
        """Test unknown language adds import at top."""
        content = "def main(): pass"
        result = _add_import_to_content(content, "import something", "fortran")

        lines = result.split("\n")
        assert lines[0] == "import something"
        assert lines[1] == ""


class TestGeneratePreview:
    """Tests for _generate_preview method."""

    def test_preview_empty_plan(self):
        """Test preview with empty plan."""
        executor = RefactoringExecutor()

        preview = executor._generate_preview({}, {})

        assert preview["files_to_create"] == []
        assert preview["files_to_update"] == []

    def test_preview_includes_create_files(self):
        """Test preview includes file creation info."""
        executor = RefactoringExecutor()

        plan = {
            "create_files": [
                {"path": "/tmp/new.py", "content": "line1\nline2", "append": False},
                {"path": "/tmp/append.py", "content": "content", "append": True},
            ]
        }

        preview = executor._generate_preview(plan, {})

        assert len(preview["files_to_create"]) == 2
        assert preview["files_to_create"][0]["mode"] == "write"
        assert preview["files_to_create"][0]["content_lines"] == 2
        assert preview["files_to_create"][1]["mode"] == "append"

    def test_preview_includes_update_files(self):
        """Test preview includes file update info."""
        executor = RefactoringExecutor()

        plan = {
            "update_files": [{"path": "/tmp/update.py"}],
            "import_additions": {"/tmp/update.py": {"import_statement": "import os"}},
        }
        replacements = {"/tmp/update.py": {"new_content": "new"}}

        preview = executor._generate_preview(plan, replacements)

        assert len(preview["files_to_update"]) == 1
        assert preview["files_to_update"][0]["has_replacement"] is True
        assert preview["files_to_update"][0]["has_import_addition"] is True

    def test_preview_skips_empty_paths(self):
        """Test preview skips entries with empty paths."""
        executor = RefactoringExecutor()

        plan = {
            "create_files": [{"path": "", "content": "content"}],
            "update_files": [{"path": ""}],
        }

        preview = executor._generate_preview(plan, {})

        assert len(preview["files_to_create"]) == 0
        assert len(preview["files_to_update"]) == 0


class TestApplyChangesErrorHandling:
    """Tests for error handling in apply_changes."""

    def test_propagates_exception(self):
        """Test that exceptions are propagated."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to create file in non-existent nested directory with mocked failure
            file_path = os.path.join(tmpdir, "nested", "deep", "file.py")

            plan = {
                "create_files": [{"path": file_path, "content": "content"}],
                "update_files": [],
            }

            # Mock makedirs to raise an exception
            with patch("os.makedirs", side_effect=PermissionError("No permission")):
                with pytest.raises(PermissionError):
                    executor.apply_changes(plan, {}, "python", dry_run=False)


class TestIntegration:
    """Integration tests for RefactoringExecutor."""

    def test_full_refactoring_workflow(self):
        """Test complete refactoring workflow with create and update."""
        executor = RefactoringExecutor()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create existing file
            existing_file = os.path.join(tmpdir, "module.py")
            with open(existing_file, "w") as f:
                f.write("import os\n\ndef duplicate():\n    return 42\n")

            # New file for extracted function
            new_file = os.path.join(tmpdir, "utils.py")

            plan = {
                "create_files": [{"path": new_file, "content": "def extracted():\n    return 42\n"}],
                "update_files": [{"path": existing_file}],
                "import_additions": {existing_file: {"import_statement": "from utils import extracted"}},
            }
            replacements = {existing_file: {"new_content": "import os\n\ndef duplicate():\n    return extracted()\n"}}

            result = executor.apply_changes(plan, replacements, "python", dry_run=False)

            assert result["dry_run"] is False
            assert new_file in result["modified_files"]
            assert existing_file in result["modified_files"]
            assert len(result["failed_files"]) == 0

            # Verify new file was created
            assert os.path.exists(new_file)
            with open(new_file) as f:
                assert "def extracted():" in f.read()

            # Verify existing file was updated
            with open(existing_file) as f:
                content = f.read()
                assert "from utils import extracted" in content
                assert "return extracted()" in content
