"""Shared pytest fixtures for unit tests.

This module provides reusable fixtures for all unit test modules, including:
- Core fixtures (MockFastMCP, mock_field, mcp_main)
- Tool access fixtures (apply_deduplication_tool, rewrite_code_tool, etc.)
- File setup fixtures (simple_test_files, backup_test_files, orchestration_test_files)
- Factory fixtures (refactoring_plan_factory, match_factory, query_factory, etc.)
- State management fixtures (reset_cache, reset_schema_client)
- Mock object factories (mock_popen_factory, mock_httpx_client)
"""

from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock

import pytest


# Mock FastMCP before importing main
class MockFastMCP:
    """Mock FastMCP class for testing."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.tools: Dict[str, Any] = {}
        self._registered = False

    def tool(self, **kwargs: Any) -> Any:
        def decorator(func: Any) -> Any:
            self.tools[func.__name__] = func
            return func

        return decorator

    def run(self, **kwargs: Any) -> None:
        pass

    def get(self, name: str) -> Any:
        """Get a tool by name (for backward compatibility)."""
        return self.tools.get(name)


def mock_field(*args: Any, **kwargs: Any) -> Any:
    """Mock pydantic Field function - accepts both positional and keyword args."""
    # If positional arg provided (e.g., Field(None, ...)), use it as default
    if args:
        return args[0]
    return kwargs.get("default")


# Tool Access Fixtures


@pytest.fixture(scope="module")
def mcp_main():
    """Initialize MCP tools using the modular architecture.

    This fixture sets up a mock MCP instance with tools registered
    from the modular architecture.
    """
    # Create a mock MCP instance
    mock_mcp = MockFastMCP("ast-grep")

    # Import tool implementations from modular architecture
    from ast_grep_mcp.features.complexity.tools import (
        analyze_complexity_tool,
        test_sentry_integration_tool,
    )
    from ast_grep_mcp.features.deduplication.tools import (
        analyze_deduplication_candidates_tool,
        apply_deduplication_tool,
        benchmark_deduplication_tool,
        find_duplication_tool,
    )
    from ast_grep_mcp.features.documentation.tools import (
        generate_api_docs_tool,
        generate_changelog_tool,
        generate_docstrings_tool,
        generate_readme_sections_tool,
        sync_documentation_tool,
    )
    from ast_grep_mcp.features.quality.tools import (
        create_linting_rule_tool,
        enforce_standards_tool,
        list_rule_templates_tool,
    )
    from ast_grep_mcp.features.rewrite.backup import restore_backup
    from ast_grep_mcp.features.rewrite.service import (
        list_backups_impl,
        rewrite_code_impl,
    )
    from ast_grep_mcp.features.search.service import (
        dump_syntax_tree_impl,
        find_code_by_rule_impl,
        find_code_impl,
        test_match_code_rule_impl,
    )

    # Register tools
    mock_mcp.tools["find_duplication"] = find_duplication_tool
    mock_mcp.tools["analyze_deduplication_candidates"] = analyze_deduplication_candidates_tool
    mock_mcp.tools["apply_deduplication"] = apply_deduplication_tool
    mock_mcp.tools["benchmark_deduplication"] = benchmark_deduplication_tool
    mock_mcp.tools["dump_syntax_tree"] = dump_syntax_tree_impl
    mock_mcp.tools["test_match_code_rule"] = test_match_code_rule_impl
    mock_mcp.tools["find_code"] = find_code_impl
    mock_mcp.tools["find_code_by_rule"] = find_code_by_rule_impl
    mock_mcp.tools["rewrite_code"] = rewrite_code_impl
    mock_mcp.tools["list_backups"] = list_backups_impl
    mock_mcp.tools["rollback_rewrite"] = restore_backup
    mock_mcp.tools["analyze_complexity"] = analyze_complexity_tool
    mock_mcp.tools["test_sentry_integration"] = test_sentry_integration_tool
    mock_mcp.tools["create_linting_rule"] = create_linting_rule_tool
    mock_mcp.tools["list_rule_templates"] = list_rule_templates_tool
    mock_mcp.tools["enforce_standards"] = enforce_standards_tool
    mock_mcp.tools["generate_docstrings"] = generate_docstrings_tool
    mock_mcp.tools["generate_readme_sections"] = generate_readme_sections_tool
    mock_mcp.tools["generate_api_docs"] = generate_api_docs_tool
    mock_mcp.tools["generate_changelog"] = generate_changelog_tool
    mock_mcp.tools["sync_documentation"] = sync_documentation_tool

    # Create a namespace object to hold mcp
    class MCPNamespace:
        mcp = mock_mcp

    return MCPNamespace()


@pytest.fixture(scope="module")
def apply_deduplication_tool(mcp_main):
    """Get apply_deduplication tool function."""
    tool = mcp_main.mcp.tools.get("apply_deduplication")
    assert tool is not None, "apply_deduplication tool not registered"
    return tool


@pytest.fixture(scope="module")
def find_duplication_tool(mcp_main):
    """Get find_duplication tool function."""
    tool = mcp_main.mcp.tools.get("find_duplication")
    assert tool is not None, "find_duplication tool not registered"
    return tool


@pytest.fixture(scope="module")
def analyze_deduplication_candidates_tool(mcp_main):
    """Get analyze_deduplication_candidates tool function."""
    tool = mcp_main.mcp.tools.get("analyze_deduplication_candidates")
    assert tool is not None, "analyze_deduplication_candidates tool not registered"
    return tool


@pytest.fixture(scope="module")
def benchmark_deduplication_tool(mcp_main):
    """Get benchmark_deduplication tool function."""
    tool = mcp_main.mcp.tools.get("benchmark_deduplication")
    assert tool is not None, "benchmark_deduplication tool not registered"
    return tool


@pytest.fixture(scope="module")
def rewrite_code_tool(mcp_main):
    """Get rewrite_code tool function."""
    tool = mcp_main.mcp.tools.get("rewrite_code")
    assert tool is not None, "rewrite_code tool not registered"
    return tool


@pytest.fixture
def schema_client():
    """Create a fresh SchemaOrgClient instance for testing."""
    from ast_grep_mcp.features.schema.client import SchemaOrgClient

    return SchemaOrgClient()


@pytest.fixture(scope="module")
def enforce_standards_tool(mcp_main):
    """Get enforce_standards tool function."""
    tool = mcp_main.mcp.tools.get("enforce_standards")
    assert tool is not None, "enforce_standards tool not registered"
    return tool


@pytest.fixture(scope="module")
def list_backups_tool(mcp_main):
    """Get list_backups tool function."""
    tool = mcp_main.mcp.tools.get("list_backups")
    assert tool is not None, "list_backups tool not registered"
    return tool


@pytest.fixture(scope="module")
def rollback_rewrite_tool(mcp_main):
    """Get rollback_rewrite tool function."""
    tool = mcp_main.mcp.tools.get("rollback_rewrite")
    assert tool is not None, "rollback_rewrite tool not registered"
    return tool


@pytest.fixture(scope="module")
def analyze_complexity_tool(mcp_main):
    """Get analyze_complexity tool function."""
    tool = mcp_main.mcp.tools.get("analyze_complexity")
    assert tool is not None, "analyze_complexity tool not registered"
    return tool


@pytest.fixture(scope="module")
def test_sentry_integration_tool(mcp_main):
    """Get test_sentry_integration tool function."""
    tool = mcp_main.mcp.tools.get("test_sentry_integration")
    assert tool is not None, "test_sentry_integration tool not registered"
    return tool


# File Setup Fixtures


@pytest.fixture
def project_folder(tmp_path):
    """Temporary project folder for testing.

    Uses pytest's tmp_path fixture which automatically creates a unique
    temporary directory for each test and cleans it up afterward.

    Returns:
        pathlib.Path: Path to temporary project folder
    """
    return tmp_path


@pytest.fixture
def simple_test_files(project_folder):
    """Create simple test files for basic testing.

    Creates two simple Python files with minimal content, suitable for
    tests that don't need complex file structures.

    Args:
        project_folder: Temporary project folder fixture

    Returns:
        dict: Dictionary with file paths:
            - file1: Path to sample.py
            - file2: Path to sample2.py
    """
    file1 = project_folder / "sample.py"
    file2 = project_folder / "sample2.py"
    file1.write_text("def hello():\n    console.log('hello')\n")
    file2.write_text("def world():\n    console.log('world')\n")
    return {
        "file1": str(file1),
        "file2": str(file2),
    }


@pytest.fixture
def backup_test_files(project_folder):
    """Create test files with original content tracking for backup tests.

    Creates two Python files and tracks their original content, suitable for
    tests that need to verify backup and rollback functionality.

    Args:
        project_folder: Temporary project folder fixture

    Returns:
        dict: Dictionary with file paths and original content:
            - file1: Path to file1.py
            - file2: Path to file2.py
            - original_content1: Original content of file1
            - original_content2: Original content of file2
    """
    original_content1 = "def func1():\n    pass\n"
    original_content2 = "def func2():\n    pass\n"

    file1 = project_folder / "file1.py"
    file2 = project_folder / "file2.py"
    file1.write_text(original_content1)
    file2.write_text(original_content2)

    return {
        "file1": str(file1),
        "file2": str(file2),
        "original_content1": original_content1,
        "original_content2": original_content2,
    }


@pytest.fixture
def orchestration_test_files(project_folder):
    """Create test files in subdirectory with complex content.

    Creates a subdirectory structure with Python files containing imports
    and function definitions, suitable for testing multi-file orchestration.

    Args:
        project_folder: Temporary project folder fixture

    Returns:
        dict: Dictionary with directory and file information:
            - src_dir: Path to src subdirectory
            - file1: Path to src/file1.py
            - file2: Path to src/file2.py
            - original_content1: Original content of file1
            - original_content2: Original content of file2
    """
    src_dir = project_folder / "src"
    src_dir.mkdir()

    original_content1 = "import os\n\ndef func1():\n    return os.getcwd()\n"
    original_content2 = "import os\n\ndef func2():\n    return os.getcwd()\n"

    file1 = src_dir / "file1.py"
    file2 = src_dir / "file2.py"
    file1.write_text(original_content1)
    file2.write_text(original_content2)

    return {
        "src_dir": str(src_dir),
        "file1": str(file1),
        "file2": str(file2),
        "original_content1": original_content1,
        "original_content2": original_content2,
    }


# Factory Fixtures


@pytest.fixture
def refactoring_plan_factory():
    """Factory for creating refactoring plans with various configurations.

    This factory fixture creates refactoring plans with flexible options,
    reducing duplication of plan creation logic across test modules.

    Returns:
        function: Factory function that creates refactoring plans

    Example:
        >>> plan = refactoring_plan_factory(
        ...     files=["file1.py", "file2.py"],
        ...     new_contents=["# new content 1", "# new content 2"],
        ...     strategy="extract_function"
        ... )
    """

    def _create_plan(
        files: list[str],
        new_contents: list[str] = None,
        strategy: str = "extract_function",
        extracted_function: str = "",
        extract_to_file: str = "",
        function_name: str = "extracted_func",
        language: str = "python",
    ) -> Dict[str, Any]:
        """Create a refactoring plan.

        Args:
            files: List of file paths to refactor
            new_contents: List of new file contents (one per file)
            strategy: Refactoring strategy (default: "extract_function")
            extracted_function: Code for extracted function
            extract_to_file: File to extract function to
            function_name: Name of extracted function
            language: Programming language (default: "python")

        Returns:
            dict: Refactoring plan dictionary
        """
        if new_contents is None:
            new_contents = [f"# Modified: {f}\n" for f in files]

        replacements = {}
        for f, content in zip(files, new_contents):
            replacements[f] = {"new_content": content, "changes": [{"line": 1, "old": "original", "new": "modified"}]}

        plan = {
            "strategy": strategy,
            "files_affected": files,
            "generated_code": {"extracted_function": extracted_function, "replacements": replacements},
            "language": language,
        }

        if extract_to_file:
            plan["generated_code"]["extract_to_file"] = extract_to_file
            plan["generated_code"]["function_name"] = function_name

        return plan

    return _create_plan


# Additional Tool Access Fixtures


@pytest.fixture(scope="module")
def batch_search_tool(mcp_main):
    """Get batch_search tool function."""
    tool = mcp_main.mcp.tools.get("batch_search")
    assert tool is not None, "batch_search tool not registered"
    return tool


@pytest.fixture(scope="module")
def find_code_tool(mcp_main):
    """Get find_code tool function."""
    tool = mcp_main.mcp.tools.get("find_code")
    assert tool is not None, "find_code tool not registered"
    return tool


@pytest.fixture(scope="module")
def find_code_by_rule_tool(mcp_main):
    """Get find_code_by_rule tool function."""
    tool = mcp_main.mcp.tools.get("find_code_by_rule")
    assert tool is not None, "find_code_by_rule tool not registered"
    return tool


# Data Factory Fixtures


@pytest.fixture
def match_factory():
    """Factory for creating ast-grep match dictionaries.

    Returns:
        function: Factory function that creates match dictionaries

    Example:
        >>> match = match_factory(text="hello", file="test.py", line=10)
    """

    def _factory(text: str = "match", file: str = "test.py", line: int = 1, column: int = 0, **kwargs) -> Dict[str, Any]:
        """Create a match dictionary.

        Args:
            text: Matched text content
            file: Source file path
            line: Line number
            column: Column number
            **kwargs: Additional match properties

        Returns:
            dict: ast-grep match dictionary
        """
        match_dict = {
            "text": text,
            "file": file,
            "range": {"start": {"line": line, "column": column}, "end": {"line": line, "column": column + len(text)}},
        }
        match_dict.update(kwargs)
        return match_dict

    return _factory


@pytest.fixture
def query_factory():
    """Factory for creating batch search query dictionaries.

    Returns:
        function: Factory function that creates query dictionaries

    Example:
        >>> query = query_factory(id="q1", pattern="def $FUNC", language="python")
    """

    def _factory(id: str = "query1", type: str = "pattern", pattern: str = "test", language: str = "python", **kwargs) -> Dict[str, Any]:
        """Create a query dictionary.

        Args:
            id: Query identifier
            type: Query type (pattern or rule)
            pattern: Search pattern
            language: Programming language
            **kwargs: Additional query properties

        Returns:
            dict: Batch search query dictionary
        """
        query_dict = {"id": id, "type": type, "pattern": pattern, "language": language}
        query_dict.update(kwargs)
        return query_dict

    return _factory


@pytest.fixture
def yaml_rule_factory():
    """Factory for creating YAML rule strings.

    Returns:
        function: Factory function that creates YAML rules

    Example:
        >>> rule = yaml_rule_factory(id="test-rule", pattern="console.log($$$)")
    """

    def _factory(
        id: str = "test", language: str = "python", pattern: str = "test", message: str = "Test message", severity: str = "error", **kwargs
    ) -> str:
        """Create a YAML rule string.

        Args:
            id: Rule identifier
            language: Programming language
            pattern: Search pattern
            message: Rule message
            severity: Rule severity
            **kwargs: Additional rule properties

        Returns:
            str: YAML rule string
        """
        rule = f"""id: {id}
language: {language}
rule:
  pattern: {pattern}
message: {message}
severity: {severity}
"""
        if kwargs:
            for key, value in kwargs.items():
                rule += f"{key}: {value}\n"
        return rule

    return _factory


# Complex Object Factory Fixtures


@pytest.fixture
def rule_violation_factory():
    """Factory for creating RuleViolation instances.

    Requires importing from main module in tests.

    Returns:
        function: Factory function that creates RuleViolation instances

    Example:
        >>> violation = rule_violation_factory(
        ...     file="test.py", line=10, severity="error", rule_id="test-rule"
        ... )
    """

    def _factory(
        file: str = "/test.py", line: int = 1, severity: str = "error", rule_id: str = "test-rule", message: str = "Test message", **kwargs
    ) -> Dict[str, Any]:
        """Create a RuleViolation dictionary.

        Args:
            file: File path
            line: Line number
            severity: Violation severity
            rule_id: Rule identifier
            message: Violation message
            **kwargs: Additional violation properties

        Returns:
            dict: RuleViolation dictionary (matches dataclass structure)
        """
        defaults = {"column": 0, "end_line": line, "end_column": 10, "code_snippet": "test code", "suggested_fix": None}
        defaults.update(kwargs)

        return {"file": file, "line": line, "severity": severity, "rule_id": rule_id, "message": message, **defaults}

    return _factory


@pytest.fixture
def linting_rule_factory():
    """Factory for creating LintingRule dictionaries.

    Returns:
        function: Factory function that creates LintingRule dictionaries

    Example:
        >>> rule = linting_rule_factory(
        ...     id="no-console", language="javascript", severity="warning"
        ... )
    """

    def _factory(
        id: str = "test", language: str = "python", severity: str = "error", pattern: str = "test", message: str = "Test message", **kwargs
    ) -> Dict[str, Any]:
        """Create a LintingRule dictionary.

        Args:
            id: Rule identifier
            language: Programming language
            severity: Rule severity
            pattern: Search pattern
            message: Rule message
            **kwargs: Additional rule properties

        Returns:
            dict: LintingRule dictionary (matches dataclass structure)
        """
        rule_dict = {
            "id": id,
            "language": language,
            "severity": severity,
            "pattern": pattern,
            "message": message,
            "note": kwargs.get("note", ""),
            "fix_template": kwargs.get("fix_template", None),
        }
        rule_dict.update({k: v for k, v in kwargs.items() if k not in ["note", "fix_template"]})
        return rule_dict

    return _factory


# Mock Object Factory Fixtures


@pytest.fixture
def mock_popen_factory():
    """Factory for creating Mock Popen process objects.

    Returns:
        function: Factory function that creates Mock Popen instances

    Example:
        >>> mock_proc = mock_popen_factory(
        ...     stdout_lines=['{"text": "match"}'], returncode=0
        ... )
    """

    def _factory(stdout_lines: List[str] = None, returncode: int = 0, **kwargs) -> Mock:
        """Create a Mock Popen process.

        Args:
            stdout_lines: List of stdout lines to return
            returncode: Process return code
            **kwargs: Additional mock properties

        Returns:
            Mock: Configured Mock Popen process
        """
        mock_process = Mock()

        # Configure stdout
        if stdout_lines is None:
            stdout_lines = []
        mock_process.stdout = iter(stdout_lines)

        # Configure process methods
        mock_process.poll.return_value = returncode
        mock_process.wait.return_value = returncode
        mock_process.returncode = returncode
        mock_process.communicate.return_value = ("\n".join(stdout_lines).encode() if stdout_lines else b"", b"")

        # Apply any additional kwargs
        for key, value in kwargs.items():
            setattr(mock_process, key, value)

        return mock_process

    return _factory


@pytest.fixture
def mock_httpx_client():
    """Pre-configured AsyncMock for httpx client.

    Returns:
        AsyncMock: Configured httpx client mock

    Example:
        >>> async with mock_httpx_client as client:
        ...     response = await client.get("https://schema.org")
    """
    mock_client = AsyncMock()
    mock_response = Mock()

    # Configure response
    mock_response.json.return_value = {}
    mock_response.text = ""
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()

    # Configure client
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    return mock_client


# State Management Fixtures


@pytest.fixture(autouse=True)
def reset_cache(mcp_main):
    """Auto-reset cache before each test.

    This fixture automatically resets the query cache and its statistics
    before each test to ensure test isolation.
    """
    from ast_grep_mcp.core import cache as core_cache

    # Reset cache if it exists
    if core_cache._query_cache is not None:
        core_cache._query_cache.cache.clear()
        core_cache._query_cache.hits = 0
        core_cache._query_cache.misses = 0

    yield

    # Optional cleanup after test
    if core_cache._query_cache is not None:
        core_cache._query_cache.cache.clear()


@pytest.fixture(autouse=True)
def reset_schema_client(mcp_main):
    """Auto-reset Schema.org client before each test.

    This fixture automatically resets the Schema.org client instance
    before each test to ensure test isolation.
    """
    # Reset client if it exists
    if hasattr(mcp_main, "_schema_org_client"):
        mcp_main._schema_org_client = None

    yield

    # Optional cleanup after test
    if hasattr(mcp_main, "_schema_org_client"):
        mcp_main._schema_org_client = None
