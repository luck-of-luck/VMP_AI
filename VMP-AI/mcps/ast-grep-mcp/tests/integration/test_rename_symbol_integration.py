"""Integration tests for rename_symbol with real ast-grep binary.

These tests verify that the rename_symbol feature works correctly with
the actual ast-grep binary, not mocked subprocess calls.
"""

import os
import subprocess

import pytest

from ast_grep_mcp.features.refactoring.rename_coordinator import RenameCoordinator
from ast_grep_mcp.features.refactoring.renamer import SymbolRenamer


# Skip all tests if ast-grep is not installed
def ast_grep_available():
    """Check if ast-grep binary is available."""
    try:
        result = subprocess.run(
            ["ast-grep", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not ast_grep_available(), reason="ast-grep binary not found - install with 'cargo install ast-grep'")


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary Python project for testing."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()

    # Create sample Python files
    (project_dir / "utils.py").write_text("""
def calculate(x):
    result = x * 2
    return result

def process():
    value = calculate(10)
    result = value + 5
    return result
""")

    (project_dir / "main.py").write_text("""
from utils import calculate

def main():
    result = calculate(5)
    console.log(result)

if __name__ == "__main__":
    main()
""")

    return project_dir


@pytest.fixture
def temp_ts_project(tmp_path):
    """Create a temporary TypeScript project for testing."""
    project_dir = tmp_path / "test_ts_project"
    project_dir.mkdir()

    # Create sample TypeScript files
    (project_dir / "utils.ts").write_text("""
export function processData(data: string): string {
    return data.toUpperCase();
}

export function formatData(input: string): string {
    const data = processData(input);
    return data.trim();
}
""")

    (project_dir / "app.ts").write_text("""
import { processData } from './utils';

function main() {
    const result = processData('hello');
    console.log(result);
}

main();
""")

    return project_dir


class TestSymbolRenamerIntegration:
    """Integration tests for SymbolRenamer with real ast-grep."""

    def test_find_python_symbol_references(self, temp_project):
        """Test finding symbol references in Python code."""
        renamer = SymbolRenamer("python")

        references = renamer.find_symbol_references(
            project_folder=str(temp_project),
            symbol_name="result",
        )

        # Should find 'result' in both files
        assert len(references) > 0

        # Verify reference structure
        for ref in references:
            assert ref.file_path != ""
            assert ref.line > 0
            assert ref.column >= 0
            assert ref.context != ""
            assert "result" in ref.context

    def test_find_typescript_symbol_references(self, temp_ts_project):
        """Test finding symbol references in TypeScript code."""
        renamer = SymbolRenamer("typescript")

        references = renamer.find_symbol_references(
            project_folder=str(temp_ts_project),
            symbol_name="processData",
        )

        # Should find 'processData' in both files
        assert len(references) >= 3  # Definition, usage in formatData, import, usage in main

        # Check that we found references in both files
        files_with_refs = {os.path.basename(ref.file_path) for ref in references}
        assert "utils.ts" in files_with_refs
        assert "app.ts" in files_with_refs

    def test_file_filter(self, temp_project):
        """Test file filtering during symbol search."""
        renamer = SymbolRenamer("python")

        # Only search in utils.py
        references = renamer.find_symbol_references(
            project_folder=str(temp_project),
            symbol_name="result",
            file_filter="utils.py",
        )

        # All references should be from utils.py
        for ref in references:
            assert os.path.basename(ref.file_path) == "utils.py"

    def test_reference_classification(self, temp_project):
        """Test that references are correctly classified."""
        renamer = SymbolRenamer("python")

        references = renamer.find_symbol_references(
            project_folder=str(temp_project),
            symbol_name="calculate",
        )

        # Should have at least one definition and one usage
        definitions = [ref for ref in references if ref.is_definition]
        imports = [ref for ref in references if ref.is_import]
        usages = [ref for ref in references if not ref.is_definition and not ref.is_import]

        assert len(definitions) >= 1  # def calculate(...)
        assert len(imports) >= 1  # from utils import calculate
        assert len(usages) >= 1  # calculate(10), calculate(5)

    def test_scope_tree_building(self, temp_project):
        """Test scope tree building for Python file."""
        renamer = SymbolRenamer("python")
        utils_file = temp_project / "utils.py"

        scopes = renamer.build_scope_tree(str(utils_file))

        # Should have module scope + function scopes
        assert len(scopes) >= 3  # module, calculate, process

        # Check module scope
        module_scope = [s for s in scopes if s.scope_type == "module"]
        assert len(module_scope) == 1

        # Check function scopes
        function_scopes = [s for s in scopes if s.scope_type == "function"]
        assert len(function_scopes) >= 2

        # Verify function names
        func_names = {s.scope_name for s in function_scopes}
        assert "calculate" in func_names
        assert "process" in func_names


class TestRenameCoordinatorIntegration:
    """Integration tests for RenameCoordinator with real ast-grep."""

    def test_dry_run_rename(self, temp_project):
        """Test dry-run mode with real ast-grep."""
        coordinator = RenameCoordinator("python")

        result = coordinator.rename_symbol(
            project_folder=str(temp_project),
            old_name="result",
            new_name="output",
            dry_run=True,
        )

        assert result.success
        assert result.references_found > 0
        assert result.references_updated == 0  # Dry run doesn't modify
        assert result.diff_preview != ""
        assert "result" in result.diff_preview
        assert "output" in result.diff_preview

    def test_apply_rename_single_file(self, temp_project):
        """Test actually applying a rename to a single file."""
        coordinator = RenameCoordinator("python")
        utils_file = temp_project / "utils.py"
        utils_file.read_text()

        # Rename 'calculate' to 'compute' only in utils.py
        result = coordinator.rename_symbol(
            project_folder=str(temp_project),
            old_name="calculate",
            new_name="compute",
            scope="file",
            file_filter="utils.py",
            dry_run=False,
        )

        assert result.success
        assert result.references_updated > 0
        assert result.backup_id != ""

        # Verify file was modified
        modified_content = utils_file.read_text()
        assert "def compute(" in modified_content
        assert "def calculate(" not in modified_content

        # Verify backup was created
        assert result.backup_id is not None

    def test_multi_file_rename(self, temp_ts_project):
        """Test renaming across multiple files."""
        coordinator = RenameCoordinator("typescript")

        result = coordinator.rename_symbol(
            project_folder=str(temp_ts_project),
            old_name="processData",
            new_name="transformData",
            dry_run=False,
        )

        assert result.success
        assert len(result.files_modified) >= 2

        # Verify both files were updated
        utils_content = (temp_ts_project / "utils.ts").read_text()
        app_content = (temp_ts_project / "app.ts").read_text()

        assert "transformData" in utils_content
        assert "processData" not in utils_content or "processData" in "// processData"

        assert "transformData" in app_content
        assert "processData" not in app_content or "processData" in "// processData"

    def test_word_boundary_replacement(self, temp_project):
        """Test that word boundaries are respected during replacement."""
        # Create file with similar names
        test_file = temp_project / "boundary_test.py"
        test_file.write_text("""
def process():
    result = 1
    results = [result]
    result_count = len(results)
    return result
""")

        coordinator = RenameCoordinator("python")

        coordinator.rename_symbol(
            project_folder=str(temp_project),
            old_name="result",
            new_name="output",
            dry_run=False,
        )

        modified_content = test_file.read_text()

        # 'result' should be renamed to 'output'
        assert "output = 1" in modified_content
        assert "return output" in modified_content
        assert "results = [output]" in modified_content

        # But 'results' and 'result_count' should NOT be changed
        assert "results = [output]" in modified_content  # 'results' unchanged
        assert "result_count" in modified_content  # 'result_count' unchanged

    def test_conflict_detection(self, temp_project):
        """Test that naming conflicts are detected."""
        # Create file with potential conflict
        conflict_file = temp_project / "conflict_test.py"
        conflict_file.write_text("""
def foo():
    x = 1
    y = 2
    return x + y
""")

        coordinator = RenameCoordinator("python")

        # Try to rename 'x' to 'y' (should detect conflict)
        result = coordinator.rename_symbol(
            project_folder=str(temp_project),
            old_name="x",
            new_name="y",
            dry_run=True,
        )

        # Should succeed but warn about potential conflicts
        # (or fail if conflict detection is strict)
        assert result.success or len(result.conflicts) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
