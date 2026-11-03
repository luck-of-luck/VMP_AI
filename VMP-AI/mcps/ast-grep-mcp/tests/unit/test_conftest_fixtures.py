"""Test suite demonstrating usage of enhanced conftest.py fixtures.

This module showcases how to use the new fixtures added to conftest.py,
serving as both tests and documentation.
"""

from pathlib import Path

import pytest


class TestCacheFixtures:
    """Test cache-related fixtures."""

    def test_initialized_cache(self, initialized_cache):
        """Test initialized_cache fixture provides ready-to-use cache."""
        # Cache should be initialized
        assert initialized_cache is not None
        assert initialized_cache.cache is not None

        # Cache should have correct config
        assert initialized_cache.max_size == 10
        assert initialized_cache.ttl_seconds == 300

    def test_cache_with_tools(self, initialized_cache, mcp_tools):
        """Test that initialized_cache works with mcp_tools."""
        # Tools should be registered
        find_code = mcp_tools("find_code")
        assert find_code is not None

        # Cache should be available
        assert initialized_cache is not None


class TestProjectFixtures:
    """Test project and file fixtures."""

    def test_temp_project_with_files(self, temp_project_with_files):
        """Test temp_project_with_files creates expected structure."""
        paths = temp_project_with_files

        # Check all expected keys exist
        assert "project" in paths
        assert "sample_py" in paths
        assert "complex_py" in paths
        assert "duplicate1_py" in paths
        assert "duplicate2_py" in paths

        # Check files exist
        assert Path(paths["sample_py"]).exists()
        assert Path(paths["complex_py"]).exists()
        assert Path(paths["duplicate1_py"]).exists()
        assert Path(paths["duplicate2_py"]).exists()

    def test_sample_py_content(self, temp_project_with_files):
        """Test sample.py has expected content."""
        paths = temp_project_with_files
        content = Path(paths["sample_py"]).read_text()

        assert "def hello():" in content
        assert "console.log('hello')" in content

    def test_duplicate_files_similar(self, temp_project_with_files):
        """Test duplicate files have similar structure."""
        paths = temp_project_with_files

        dup1 = Path(paths["duplicate1_py"]).read_text()
        dup2 = Path(paths["duplicate2_py"]).read_text()

        # Both should have similar patterns
        assert "fetch_data" in dup1
        assert "fetch_data" in dup2
        assert "if" in dup1 and "if" in dup2
        assert "active" in dup1 and "active" in dup2


class TestMCPToolFixtures:
    """Test MCP tool access fixtures."""

    def test_mcp_tools_accessor(self, mcp_tools):
        """Test mcp_tools fixture provides tool accessor."""
        # Should be able to get known tools
        find_code = mcp_tools("find_code")
        assert find_code is not None
        assert callable(find_code)

    def test_mcp_tools_error_handling(self, mcp_tools):
        """Test mcp_tools raises helpful error for unknown tools."""
        with pytest.raises(ValueError) as exc_info:
            mcp_tools("nonexistent_tool")

        # Error should mention tool name and list available tools
        assert "nonexistent_tool" in str(exc_info.value)
        assert "Available:" in str(exc_info.value)


class TestComplexityFixtures:
    """Test complexity analysis fixtures."""

    def test_sample_complexity_thresholds(self, sample_complexity_thresholds):
        """Test sample_complexity_thresholds has expected values."""
        thresholds = sample_complexity_thresholds

        assert thresholds.cyclomatic == 10
        assert thresholds.cognitive == 15
        assert thresholds.nesting_depth == 4
        assert thresholds.lines == 50

    def test_sample_function_code(self, sample_function_code):
        """Test sample_function_code provides various complexity levels."""
        code = sample_function_code

        # Check all expected keys
        assert "simple" in code
        assert "high_cyclomatic" in code
        assert "high_nesting" in code
        assert "long_function" in code

        # Verify content
        assert "def simple_func" in code["simple"]
        assert "def many_branches" in code["high_cyclomatic"]
        assert "def deeply_nested" in code["high_nesting"]
        assert "def very_long_function" in code["long_function"]


class TestCodeQualityFixtures:
    """Test code quality and linting fixtures."""

    def test_sample_linting_rule(self, sample_linting_rule):
        """Test sample_linting_rule has expected properties."""
        rule = sample_linting_rule

        assert rule.id == "test-rule"
        assert rule.language == "python"
        assert rule.severity == "warning"
        assert rule.pattern == "test_pattern"

    def test_sample_rule_templates(self, sample_rule_templates):
        """Test sample_rule_templates provides template data."""
        templates = sample_rule_templates

        assert len(templates) >= 2

        # Check structure of first template
        template = templates[0]
        assert "id" in template
        assert "language" in template
        assert "category" in template
        assert "pattern" in template
        assert "message" in template


class TestBackupFixtures:
    """Test backup management fixtures."""

    def test_backup_dir(self, backup_dir, temp_dir):
        """Test backup_dir provides functional backup directory."""
        # Backup dir should exist
        assert backup_dir.exists()
        assert backup_dir.is_dir()

        # Should be in temp directory
        assert str(backup_dir).startswith(temp_dir)

        # Should have expected name
        assert backup_dir.name == ".ast-grep-backups"


class TestCoverageFixtures:
    """Test test coverage fixtures."""

    def test_sample_test_paths(self, sample_test_paths):
        """Test sample_test_paths provides source-to-test mappings."""
        paths = sample_test_paths

        # Check expected mappings exist
        assert "src/module.py" in paths
        assert paths["src/module.py"] == "tests/test_module.py"

        assert "src/utils.py" in paths
        assert paths["src/utils.py"] == "tests/test_utils.py"


class TestLanguageCodeFixtures:
    """Test multi-language code fixtures."""

    def test_sample_python_code(self, sample_python_code):
        """Test sample_python_code provides Python code."""
        assert "def calculate_sum" in sample_python_code
        assert "a + b" in sample_python_code

    def test_sample_typescript_code(self, sample_typescript_code):
        """Test sample_typescript_code provides TypeScript code."""
        assert "function calculateSum" in sample_typescript_code
        assert ": number" in sample_typescript_code
        assert "const result" in sample_typescript_code

    def test_sample_javascript_code(self, sample_javascript_code):
        """Test sample_javascript_code provides JavaScript code."""
        assert "function calculateSum" in sample_javascript_code
        assert "const result" in sample_javascript_code
        # Should NOT have type annotations
        assert ": number" not in sample_javascript_code

    def test_sample_java_code(self, sample_java_code):
        """Test sample_java_code provides Java code."""
        assert "public class Calculator" in sample_java_code
        assert "public int calculateSum" in sample_java_code


class TestSchemaFixtures:
    """Test Schema.org fixtures."""

    def test_sample_schema_types(self, sample_schema_types):
        """Test sample_schema_types provides type definitions."""
        types = sample_schema_types

        assert len(types) >= 3

        # Find Thing type
        thing = next(t for t in types if t["id"] == "Thing")
        assert thing["label"] == "Thing"
        assert "properties" in thing

        # Find Person type
        person = next(t for t in types if t["id"] == "Person")
        assert person["subClassOf"] == "Thing"


class TestDeduplicationFixtures:
    """Test deduplication fixtures."""

    def test_sample_deduplication_result(self, sample_deduplication_result):
        """Test sample_deduplication_result provides analysis result."""
        result = sample_deduplication_result

        assert "candidates" in result
        assert "total_candidates" in result
        assert "analyzed_files" in result

        # Check candidate structure
        candidate = result["candidates"][0]
        assert "score" in candidate
        assert "potential_savings" in candidate
        assert "complexity" in candidate
        assert "risk_level" in candidate
        assert "recommendation" in candidate
        assert "duplication_groups" in candidate


class TestSubprocessFixtures:
    """Test subprocess mocking fixtures."""

    def test_mock_ast_grep_process(self, mock_ast_grep_process):
        """Test mock_ast_grep_process provides configured mock."""
        mock = mock_ast_grep_process

        assert mock.returncode == 0
        assert mock.stdout == ""
        assert mock.stderr == ""


class TestFixtureCombinations:
    """Test combining multiple fixtures in realistic scenarios."""

    def test_cache_with_project_files(self, initialized_cache, temp_project_with_files):
        """Test using cache with project files."""
        # This would be used when testing cached code searches
        paths = temp_project_with_files
        cache = initialized_cache

        assert cache is not None
        assert Path(paths["project"]).exists()

    def test_tools_with_thresholds(self, mcp_tools, sample_complexity_thresholds):
        """Test using tools with complexity thresholds."""
        # This would be used when testing complexity analysis tools
        thresholds = sample_complexity_thresholds

        # Get complexity tool
        analyze = mcp_tools("analyze_complexity")
        assert analyze is not None
        assert thresholds.cyclomatic == 10

    def test_backup_with_project(self, backup_dir, temp_project_with_files):
        """Test backup directory with project files."""
        # This would be used when testing rewrite operations
        paths = temp_project_with_files

        assert backup_dir is not None
        assert backup_dir.exists()
        assert Path(paths["sample_py"]).exists()
