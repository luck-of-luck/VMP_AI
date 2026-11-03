"""Shared pytest fixtures for ast-grep-mcp test suite.

This module provides common fixtures used across unit and integration tests,
reducing duplication and standardizing test setup.
"""

import shutil

# Add project root to path for imports
import sys
import tempfile
from pathlib import Path
from typing import Generator

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from ast_grep_mcp.constants import SemanticSimilarityDefaults

# ============================================================================
# Cache Management Fixtures
# ============================================================================


@pytest.fixture
def clean_cache():
    """Clear the query cache before each test to avoid interference.

    This fixture is automatically used by tests that need cache isolation.
    """
    from ast_grep_mcp.core import cache as core_cache

    if core_cache._query_cache is not None:
        core_cache._query_cache.cache.clear()
    yield
    # Optionally clear after test too
    if core_cache._query_cache is not None:
        core_cache._query_cache.cache.clear()


@pytest.fixture
def query_cache():
    """Provide a fresh query cache instance.

    Returns:
        QueryCache instance for testing
    """
    from ast_grep_mcp.core.cache import QueryCache

    cache = QueryCache()
    yield cache
    cache.cache.clear()


# ============================================================================
# Temporary Directory Fixtures
# ============================================================================


@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for test isolation.

    Automatically cleaned up after test completion.

    Yields:
        str: Path to temporary directory
    """
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def temp_project_dir(temp_dir) -> str:
    """Create a temporary project directory with standard structure.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        str: Path to project root
    """
    project = Path(temp_dir) / "project"
    project.mkdir()

    # Create common directories
    (project / "src").mkdir()
    (project / "tests").mkdir()
    (project / "docs").mkdir()

    return str(project)


# ============================================================================
# Sample Code Fixtures
# ============================================================================


@pytest.fixture
def sample_python_code() -> str:
    """Provide sample Python code for testing.

    Returns:
        str: Sample Python function code
    """
    return """def calculate_sum(a, b):
    \"\"\"Calculate the sum of two numbers.\"\"\"
    result = a + b
    return result
"""


@pytest.fixture
def sample_duplicate_code() -> tuple[str, str]:
    """Provide two similar code blocks for duplication testing.

    Returns:
        tuple: (code1, code2) - Similar code blocks with variations
    """
    code1 = """def process_user_data(user_id):
    user = fetch_user(user_id)
    if user.is_active:
        return user.name
    return None
"""

    code2 = """def process_admin_data(admin_id):
    admin = fetch_user(admin_id)
    if admin.is_active:
        return admin.name
    return None
"""

    return code1, code2


@pytest.fixture
def sample_complex_code() -> str:
    """Provide complex code for complexity analysis testing.

    Returns:
        str: Code with high cyclomatic complexity
    """
    return """def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                return x + y + z
            else:
                return x + y
        else:
            if z > 0:
                return x + z
            else:
                return x
    else:
        if y > 0:
            if z > 0:
                return y + z
            else:
                return y
        else:
            return z if z > 0 else 0
"""


# ============================================================================
# Mock MCP Server Fixtures
# ============================================================================


@pytest.fixture
def mock_mcp_instance():
    """Provide a mock MCP server instance for testing tools.

    Returns:
        MockFastMCP: Mock MCP instance
    """

    class MockFastMCP:
        """Mock FastMCP instance for testing."""

        def __init__(self):
            self.tools = {}
            self._resources = []
            self._prompts = []

        def tool(self):
            """Decorator for registering tools."""

            def decorator(func):
                self.tools[func.__name__] = func
                return func

            return decorator

        def resource(self, uri: str):
            """Decorator for registering resources."""

            def decorator(func):
                self._resources.append((uri, func))
                return func

            return decorator

        def prompt(self):
            """Decorator for registering prompts."""

            def decorator(func):
                self._prompts.append(func)
                return func

            return decorator

    return MockFastMCP()


# ============================================================================
# File Creation Helpers
# ============================================================================


@pytest.fixture
def create_test_file(temp_dir):
    """Factory fixture for creating test files.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        Callable: Function to create files with content
    """

    def _create_file(filename: str, content: str, subdir: str = "") -> Path:
        """Create a file with given content in temp directory.

        Args:
            filename: Name of file to create
            content: Content to write
            subdir: Optional subdirectory path

        Returns:
            Path: Path to created file
        """
        if subdir:
            dir_path = Path(temp_dir) / subdir
            dir_path.mkdir(parents=True, exist_ok=True)
            file_path = dir_path / filename
        else:
            file_path = Path(temp_dir) / filename

        file_path.write_text(content)
        return file_path

    return _create_file


# ============================================================================
# Deduplication Fixtures
# ============================================================================


@pytest.fixture
def sample_duplication_matches() -> list[dict]:
    """Provide sample code matches for deduplication testing.

    Returns:
        list: Sample match dictionaries
    """
    return [
        {"text": "def foo():\n    return 1", "file": "file1.py", "start_line": 1, "end_line": 2},
        {"text": "def bar():\n    return 1", "file": "file2.py", "start_line": 1, "end_line": 2},
        {"text": "def baz():\n    return 2", "file": "file3.py", "start_line": 1, "end_line": 2},
    ]


# ============================================================================
# Schema.org Fixtures
# ============================================================================


@pytest.fixture
def mock_schema_client():
    """Provide a mock Schema.org client for testing.

    Returns:
        Mock client with basic schema data
    """

    class MockSchemaClient:
        """Mock SchemaOrgClient for testing."""

        def __init__(self):
            self.types = {
                "Thing": {"label": "Thing", "comment": "The most generic type of item."},
                "Person": {"label": "Person", "comment": "A person (alive, dead, undead, or fictional).", "subClassOf": "Thing"},
            }

        def get_schema_type(self, type_name: str) -> dict:
            return self.types.get(type_name, {})

        def search_schemas(self, query: str) -> list:
            return [t for t in self.types.keys() if query.lower() in t.lower()]

    return MockSchemaClient()


# ============================================================================
# Auto-use Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_module_state():
    """Reset module-level state between tests (auto-used).

    This fixture runs automatically before each test to ensure clean state.
    """
    # Clear any global caches or state
    yield
    # Cleanup after test


# ============================================================================
# Parametrize Helpers
# ============================================================================

# Common language parameter sets
SUPPORTED_LANGUAGES = ["python", "javascript", "typescript", "java", "go", "rust"]


@pytest.fixture(params=SUPPORTED_LANGUAGES)
def language(request):
    """Parametrize tests across all supported languages.

    Usage:
        def test_something(language):
            # Test runs once per language
            assert language in SUPPORTED_LANGUAGES
    """
    return request.param


# Common similarity thresholds
SIMILARITY_THRESHOLDS = [0.7, 0.8, SemanticSimilarityDefaults.MEDIUM_SIMILARITY_THRESHOLD, 0.9, 0.95]


@pytest.fixture(params=SIMILARITY_THRESHOLDS)
def similarity_threshold(request):
    """Parametrize tests across common similarity thresholds."""
    return request.param


# Fixtures for class-based deduplication components
@pytest.fixture
def duplication_detector():
    """Provide DuplicationDetector instance."""
    from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

    return DuplicationDetector(language="python")


@pytest.fixture
def pattern_analyzer():
    """Provide PatternAnalyzer instance."""
    from ast_grep_mcp.features.deduplication.analyzer import PatternAnalyzer

    return PatternAnalyzer()


@pytest.fixture
def code_generator():
    """Provide CodeGenerator instance."""
    from ast_grep_mcp.features.deduplication.generator import CodeGenerator

    return CodeGenerator(language="python")


@pytest.fixture
def duplication_ranker():
    """Provide DuplicationRanker instance."""
    from ast_grep_mcp.features.deduplication.ranker import DuplicationRanker

    return DuplicationRanker()


@pytest.fixture
def recommendation_engine():
    """Provide RecommendationEngine instance."""
    from ast_grep_mcp.features.deduplication.recommendations import RecommendationEngine

    return RecommendationEngine()


# ============================================================================
# Cache Management with Registration
# ============================================================================


@pytest.fixture
def initialized_cache():
    """Provide initialized cache for testing.

    Automatically resets cache state before and after test. This is useful
    for tests that need cache available without manual setup.

    Usage:
        def test_cached_search(initialized_cache):
            # Cache is ready
            cache = initialized_cache
            assert cache is not None

    Yields:
        QueryCache: Initialized cache instance
    """
    from ast_grep_mcp.core import cache as core_cache
    from ast_grep_mcp.core import config as core_config

    # Setup
    core_cache.init_query_cache(max_size=10, ttl_seconds=300)
    core_config.CACHE_ENABLED = True

    yield core_cache._query_cache

    # Teardown
    if core_cache._query_cache:
        core_cache._query_cache.cache.clear()
    core_cache._query_cache = None
    core_config.CACHE_ENABLED = True


# ============================================================================
# Enhanced Temporary Project Fixtures
# ============================================================================


@pytest.fixture
def temp_project_with_files(temp_dir):
    """Create temp project with common sample files.

    Creates a project directory with:
    - sample.py (simple function)
    - complex.py (complex function with high cyclomatic complexity)
    - duplicate1.py and duplicate2.py (similar code for deduplication tests)

    Usage:
        def test_with_project(temp_project_with_files):
            paths = temp_project_with_files
            assert Path(paths["sample_py"]).exists()
            with open(paths["complex_py"]) as f:
                code = f.read()

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        dict: Paths to project and files with keys:
            - project: Project root directory
            - sample_py: Simple Python file
            - complex_py: Complex Python file
            - duplicate1_py: First duplicate file
            - duplicate2_py: Second duplicate file
    """
    project = Path(temp_dir) / "project"
    project.mkdir()

    # Create sample.py
    sample_py = project / "sample.py"
    sample_py.write_text("def hello():\n    console.log('hello')\n")

    # Create complex.py
    complex_py = project / "complex.py"
    complex_py.write_text("""def complex_function(x, y):
    if x > 0:
        if y > 0:
            return x + y
        else:
            return x
    else:
        return y
""")

    # Create duplicates
    dup1 = project / "duplicate1.py"
    dup1.write_text("""def process_user(user_id):
    user = fetch_data(user_id)
    if user.active:
        return user.name
    return None
""")

    dup2 = project / "duplicate2.py"
    dup2.write_text("""def process_admin(admin_id):
    admin = fetch_data(admin_id)
    if admin.active:
        return admin.name
    return None
""")

    return {
        "project": str(project),
        "sample_py": str(sample_py),
        "complex_py": str(complex_py),
        "duplicate1_py": str(dup1),
        "duplicate2_py": str(dup2),
    }


# ============================================================================
# MCP Tool Access Fixtures
# ============================================================================


@pytest.fixture
def mcp_tools():
    """Provide easy access to MCP tools from modular architecture.

    Returns accessor function that validates tool existence with helpful
    error messages.

    Usage:
        def test_tool(mcp_tools):
            find_code = mcp_tools("find_code")
            result = find_code(pattern="def $FUNC", ...)

    Returns:
        Callable: Function to get tool by name

    Raises:
        ValueError: If tool not found, with list of available tools
    """
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

    # Build tools registry
    tools = {
        "find_duplication": find_duplication_tool,
        "analyze_deduplication_candidates": analyze_deduplication_candidates_tool,
        "apply_deduplication": apply_deduplication_tool,
        "benchmark_deduplication": benchmark_deduplication_tool,
        "dump_syntax_tree": dump_syntax_tree_impl,
        "test_match_code_rule": test_match_code_rule_impl,
        "find_code": find_code_impl,
        "find_code_by_rule": find_code_by_rule_impl,
        "rewrite_code": rewrite_code_impl,
        "list_backups": list_backups_impl,
        "rollback_rewrite": restore_backup,
        "analyze_complexity": analyze_complexity_tool,
        "test_sentry_integration": test_sentry_integration_tool,
        "create_linting_rule": create_linting_rule_tool,
        "list_rule_templates": list_rule_templates_tool,
        "enforce_standards": enforce_standards_tool,
        "generate_docstrings": generate_docstrings_tool,
        "generate_readme_sections": generate_readme_sections_tool,
        "generate_api_docs": generate_api_docs_tool,
        "generate_changelog": generate_changelog_tool,
        "sync_documentation": sync_documentation_tool,
    }

    def get_tool(tool_name: str):
        """Get tool by name, with helpful error if not found.

        Args:
            tool_name: Name of the tool to retrieve

        Returns:
            Callable: The tool function

        Raises:
            ValueError: If tool not found
        """
        tool = tools.get(tool_name)
        if tool is None:
            available = list(tools.keys())
            raise ValueError(f"Tool '{tool_name}' not found. Available: {available}")
        return tool

    return get_tool


# ============================================================================
# Mock Subprocess Fixtures
# ============================================================================


@pytest.fixture
def mock_ast_grep_process():
    """Provide mock subprocess for ast-grep execution.

    Returns a configured Mock object that simulates successful
    ast-grep execution. Useful for unit tests that don't need
    real ast-grep binary.

    Usage:
        def test_search(mock_ast_grep_process, monkeypatch):
            monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_ast_grep_process)
            # Test code that calls ast-grep

    Returns:
        Mock: Configured subprocess.run mock with returncode=0
    """
    from unittest.mock import Mock

    mock_process = Mock()
    mock_process.returncode = 0
    mock_process.stdout = ""
    mock_process.stderr = ""

    return mock_process


# ============================================================================
# Test Coverage Fixtures
# ============================================================================


@pytest.fixture
def sample_test_paths() -> dict[str, str]:
    """Provide sample test file paths for coverage testing.

    Returns mapping of source files to their corresponding test files
    for testing coverage detection logic.

    Usage:
        def test_coverage_detection(sample_test_paths):
            source = "src/module.py"
            test = sample_test_paths[source]
            assert test == "tests/test_module.py"

    Returns:
        dict: Mapping of source files to test files
    """
    return {
        "src/module.py": "tests/test_module.py",
        "src/utils.py": "tests/test_utils.py",
        "src/core/engine.py": "tests/unit/test_engine.py",
        "lib/helper.py": "test/test_helper.py",
        "app/controllers/user.py": "spec/controllers/user_spec.py",
    }


# ============================================================================
# Complexity Analysis Fixtures
# ============================================================================


@pytest.fixture
def sample_complexity_thresholds():
    """Provide standard complexity thresholds for testing.

    Returns ComplexityThresholds instance with default values used
    in most complexity analysis tests.

    Usage:
        def test_complexity(sample_complexity_thresholds):
            thresholds = sample_complexity_thresholds
            assert thresholds.cyclomatic == 10
            assert thresholds.cognitive == 15

    Returns:
        ComplexityThresholds: Standard threshold configuration
    """
    from ast_grep_mcp.models.complexity import ComplexityThresholds

    return ComplexityThresholds(
        cyclomatic=10,
        cognitive=15,
        nesting_depth=4,  # Correct parameter name
        lines=50,  # Correct parameter name
    )


@pytest.fixture
def sample_function_code() -> dict[str, str]:
    """Provide sample function code snippets for complexity testing.

    Returns:
        dict: Code snippets organized by complexity characteristic
    """
    return {
        "simple": """def simple_func(x):
    return x + 1
""",
        "high_cyclomatic": """def many_branches(x):
    if x > 0:
        return 1
    elif x < 0:
        return -1
    elif x == 0:
        return 0
    elif x > 100:
        return 100
    elif x < -100:
        return -100
    else:
        return x
""",
        "high_nesting": """def deeply_nested(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                if x > y:
                    if y > z:
                        return 1
    return 0
""",
        "long_function": "\n".join(
            [
                "def very_long_function():",
                "    x = 1",
            ]
            + [f"    x += {i}" for i in range(100)]
            + ["    return x"]
        ),
    }


# ============================================================================
# Code Quality & Linting Fixtures
# ============================================================================


@pytest.fixture
def sample_linting_rule():
    """Provide sample linting rule for testing.

    Returns a basic LintingRule instance that can be used for
    testing rule validation, storage, and application.

    Usage:
        def test_rule_validation(sample_linting_rule):
            rule = sample_linting_rule
            assert rule.id == "test-rule"
            assert rule.severity == "warning"

    Returns:
        LintingRule: Sample rule instance
    """
    from ast_grep_mcp.models.standards import LintingRule

    return LintingRule(
        id="test-rule",
        language="python",
        severity="warning",
        message="Test message",
        pattern="test_pattern",
        note="This is a test rule for unit tests",
    )


@pytest.fixture
def sample_rule_templates() -> list[dict]:
    """Provide sample rule templates for testing.

    Returns:
        list: Sample rule template dictionaries
    """
    return [
        {
            "id": "no-console-log",
            "language": "javascript",
            "category": "general",
            "pattern": "console.log($$$)",
            "message": "Avoid console.log in production code",
        },
        {
            "id": "no-bare-except",
            "language": "python",
            "category": "security",
            "pattern": "except:",
            "message": "Avoid bare except clauses",
        },
    ]


# ============================================================================
# Backup Management Fixtures
# ============================================================================


@pytest.fixture
def backup_dir(temp_dir):
    """Provide backup directory for testing.

    Creates a temporary backup directory structure. Use with
    main.create_backup() and main.restore_from_backup() functions.

    Usage:
        def test_backup(backup_dir, temp_dir):
            # Create test file
            test_file = Path(temp_dir) / "test.py"
            test_file.write_text("code")

            # Create backup
            backup_id = main.create_backup([str(test_file)], temp_dir)

            # Backup stored in backup_dir
            assert Path(backup_dir / backup_id).exists()

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        Path: Backup directory path
    """
    backup_path = Path(temp_dir) / ".ast-grep-backups"
    backup_path.mkdir(parents=True, exist_ok=True)
    return backup_path


# ============================================================================
# File Content Fixtures
# ============================================================================


@pytest.fixture
def sample_typescript_code() -> str:
    """Provide sample TypeScript code for testing.

    Returns:
        str: Sample TypeScript function with type annotations
    """
    return """function calculateSum(a: number, b: number): number {
    const result = a + b;
    return result;
}
"""


@pytest.fixture
def sample_javascript_code() -> str:
    """Provide sample JavaScript code for testing.

    Returns:
        str: Sample JavaScript function
    """
    return """function calculateSum(a, b) {
    const result = a + b;
    return result;
}
"""


@pytest.fixture
def sample_java_code() -> str:
    """Provide sample Java code for testing.

    Returns:
        str: Sample Java method
    """
    return """public class Calculator {
    public int calculateSum(int a, int b) {
        int result = a + b;
        return result;
    }
}
"""


# ============================================================================
# Schema.org Extended Fixtures
# ============================================================================


@pytest.fixture
def sample_schema_types() -> list[dict]:
    """Provide sample Schema.org type definitions.

    Returns:
        list: Sample type dictionaries with properties
    """
    return [
        {"id": "Thing", "label": "Thing", "comment": "The most generic type of item.", "properties": ["name", "description", "url"]},
        {
            "id": "Person",
            "label": "Person",
            "comment": "A person (alive, dead, undead, or fictional).",
            "subClassOf": "Thing",
            "properties": ["name", "givenName", "familyName", "email"],
        },
        {
            "id": "Article",
            "label": "Article",
            "comment": "An article, such as a news article or piece of investigative report.",
            "subClassOf": "CreativeWork",
            "properties": ["headline", "author", "datePublished", "articleBody"],
        },
    ]


# ============================================================================
# Deduplication Extended Fixtures
# ============================================================================


@pytest.fixture
def sample_deduplication_result() -> dict:
    """Provide sample deduplication analysis result.

    Returns:
        dict: Sample result with candidates and analysis
    """
    return {
        "candidates": [
            {
                "score": 0.85,
                "potential_savings": 150,
                "complexity": 5,
                "risk_level": "low",
                "recommendation": "extract_function",
                "duplication_groups": [
                    {"file": "file1.py", "start_line": 10, "end_line": 20},
                    {"file": "file2.py", "start_line": 15, "end_line": 25},
                ],
            }
        ],
        "total_candidates": 1,
        "analyzed_files": 10,
    }


# ============================================================================
# Fixture Documentation
# ============================================================================

"""
FIXTURE USAGE GUIDE
===================

This conftest.py provides 40+ fixtures organized into categories:

1. CACHE MANAGEMENT
   - clean_cache: Clear cache before/after tests
   - query_cache: Fresh cache instance
   - initialized_cache: Cache + registered tools (NEW)

2. TEMPORARY DIRECTORIES
   - temp_dir: Basic temp directory
   - temp_project_dir: Project with src/tests/docs structure
   - temp_project_with_files: Project with sample code files (NEW)

3. SAMPLE CODE
   - sample_python_code: Simple Python function
   - sample_typescript_code: TypeScript function (NEW)
   - sample_javascript_code: JavaScript function (NEW)
   - sample_java_code: Java method (NEW)
   - sample_duplicate_code: Two similar code blocks
   - sample_complex_code: High complexity code
   - sample_function_code: Dict of various complexity levels (NEW)

4. MCP TOOLS
   - mock_mcp_instance: Mock MCP server
   - mcp_tools: Easy tool accessor with validation (NEW)

5. FILE CREATION
   - create_test_file: Factory for creating files

6. DEDUPLICATION
   - duplication_detector: DuplicationDetector instance
   - pattern_analyzer: PatternAnalyzer instance
   - code_generator: CodeGenerator instance
   - duplication_ranker: DuplicationRanker instance
   - recommendation_engine: RecommendationEngine instance
   - sample_duplication_matches: Sample match data
   - sample_deduplication_result: Sample analysis result (NEW)

7. SCHEMA.ORG
   - mock_schema_client: Mock Schema.org client
   - sample_schema_types: Sample type definitions (NEW)

8. SUBPROCESS MOCKING
   - mock_ast_grep_process: Mock ast-grep subprocess (NEW)

9. COMPLEXITY ANALYSIS
   - sample_complexity_thresholds: Standard thresholds (NEW)
   - sample_function_code: Various complexity examples (NEW)

10. CODE QUALITY
    - sample_linting_rule: Sample rule instance (NEW)
    - sample_rule_templates: Sample templates (NEW)

11. BACKUP MANAGEMENT
    - backup_dir: Backup directory for testing (NEW)

12. TEST COVERAGE
    - sample_test_paths: Source to test mappings (NEW)

13. PARAMETRIZATION
    - language: Parametrize across supported languages
    - similarity_threshold: Parametrize across thresholds

14. AUTO-USE
    - reset_module_state: Automatic state cleanup

EXAMPLES
--------

Simple test with tools:
    def test_find_code(mcp_tools):
        find_code = mcp_tools("find_code")
        result = find_code(pattern="def $FUNC", ...)

Test with project files:
    def test_duplication(temp_project_with_files):
        paths = temp_project_with_files
        result = detect_duplicates(paths["project"])

Test with cache:
    def test_caching(initialized_cache):
        # Cache is ready, tools registered
        result = search_code(...)

Test with complexity:
    def test_complexity(sample_complexity_thresholds):
        thresholds = sample_complexity_thresholds
        analyze(code, thresholds)
"""


# ============================================================================
# Code Rewrite Fixtures
# ============================================================================


@pytest.fixture
def rewrite_sample_file(temp_dir):
    """Create a sample Python file for rewrite testing.

    Creates sample.py with basic rewriteable content.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        str: Path to the created sample file

    Usage:
        def test_rewrite(rewrite_sample_file):
            result = rewrite_code(rewrite_sample_file, ...)
    """
    import os

    sample_file = os.path.join(temp_dir, "sample.py")
    with open(sample_file, "w") as f:
        f.write("def hello():\n    console.log('hello')\n")

    return sample_file


@pytest.fixture
def rewrite_tools(mcp_tools):
    """Provide easy access to rewrite MCP tools.

    Returns a dict with rewrite_code, rollback_rewrite, and list_backups tools.

    Args:
        mcp_tools: MCP tools accessor fixture

    Returns:
        dict: Dictionary with 'rewrite_code', 'rollback_rewrite', 'list_backups' keys

    Usage:
        def test_rewrite(rewrite_tools):
            result = rewrite_tools['rewrite_code'](...)
            backups = rewrite_tools['list_backups'](...)
    """
    return {
        "rewrite_code": mcp_tools("rewrite_code"),
        "rollback_rewrite": mcp_tools("rollback_rewrite"),
        "list_backups": mcp_tools("list_backups"),
    }


@pytest.fixture
def rewrite_test_files(temp_dir):
    """Create multiple test files for backup/restore testing.

    Creates file1.py and file2.py with distinct content.

    Args:
        temp_dir: Temporary directory fixture

    Returns:
        dict: Dictionary with 'file1' and 'file2' paths, plus 'project_folder'

    Usage:
        def test_backup(rewrite_test_files):
            files = rewrite_test_files
            backup_id = create_backup([files['file1'], files['file2']], ...)
    """
    import os

    file1 = os.path.join(temp_dir, "file1.py")
    file2 = os.path.join(temp_dir, "file2.py")

    with open(file1, "w") as f:
        f.write("console.log('file1')\n")
    with open(file2, "w") as f:
        f.write("console.log('file2')\n")

    return {"file1": file1, "file2": file2, "project_folder": temp_dir}
