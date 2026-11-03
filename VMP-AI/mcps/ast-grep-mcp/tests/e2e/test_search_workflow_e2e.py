"""E2E tests for search → analysis → report workflows.

Tests complete user journeys: searching code, analyzing complexity,
detecting smells, and generating quality reports.
"""

from pathlib import Path

import pytest

from ast_grep_mcp.features.complexity.tools import (
    analyze_complexity_tool,
    detect_code_smells_tool,
)
from ast_grep_mcp.features.quality.tools import (
    enforce_standards_tool,
    generate_quality_report_tool,
)
from ast_grep_mcp.features.search.service import find_code_impl

# -- Fixtures ----------------------------------------------------------------

PYTHON_PROJECT_FILES = {
    "src/calculator.py": """\
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero")
    return a / b
""",
    "src/utils.py": """\
def format_number(n):
    return f"{n:,.2f}"

def validate_input(value):
    if value is None:
        return False
    if not isinstance(value, (int, float)):
        return False
    return True
""",
    "src/complex_module.py": """\
def process_data(data, config):
    if data is None:
        return None
    if config.get('validate'):
        if not isinstance(data, list):
            if isinstance(data, dict):
                data = [data]
            else:
                return None
    result = []
    for item in data:
        if item.get('active'):
            if item.get('score') > config.get('threshold', 0):
                if item.get('category') in config.get('categories', []):
                    result.append(item)
                elif config.get('include_uncategorized'):
                    result.append(item)
    return result
""",
    "src/duplicate_a.py": """\
def process_user_data(user_id):
    user = fetch_user(user_id)
    if user is None:
        return None
    if not user.is_active:
        return None
    name = user.first_name + ' ' + user.last_name
    email = user.email.lower()
    return {'name': name, 'email': email, 'id': user_id}
""",
    "src/duplicate_b.py": """\
def process_admin_data(admin_id):
    admin = fetch_user(admin_id)
    if admin is None:
        return None
    if not admin.is_active:
        return None
    name = admin.first_name + ' ' + admin.last_name
    email = admin.email.lower()
    return {'name': name, 'email': email, 'id': admin_id}
""",
}

TYPESCRIPT_PROJECT_FILES = {
    "src/api.ts": """\
function fetchUser(id: number): Promise<User> {
  return fetch(`/api/users/${id}`).then(r => r.json());
}

function fetchPosts(userId: number): Promise<Post[]> {
  return fetch(`/api/users/${userId}/posts`).then(r => r.json());
}

let retryCount = 0;
function retryFetch(url: string): Promise<Response> {
  retryCount++;
  return fetch(url);
}
""",
    "src/helpers.ts": """\
let debugMode = false;

function setDebugMode(enabled: boolean): void {
  debugMode = enabled;
}

const formatDate = (d: Date): string => {
  return d.toISOString().split('T')[0];
};

const MAX_RETRIES = 3;
""",
}


@pytest.fixture
def python_project(tmp_path: Path) -> str:
    """Create a Python project with multiple files."""
    for rel_path, content in PYTHON_PROJECT_FILES.items():
        full = tmp_path / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return str(tmp_path)


@pytest.fixture
def typescript_project(tmp_path: Path) -> str:
    """Create a TypeScript project with multiple files."""
    for rel_path, content in TYPESCRIPT_PROJECT_FILES.items():
        full = tmp_path / rel_path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return str(tmp_path)


# -- Tests: Search Workflow --------------------------------------------------


class TestSearchWorkflowE2E:
    """E2E: code search across project files."""

    def test_find_functions_text_format(self, python_project: str):
        result = find_code_impl(
            project_folder=python_project,
            pattern="def $NAME($$$)",
            language="python",
            output_format="text",
        )
        assert "Found" in result
        assert "add" in result
        assert "divide" in result
        assert "process_data" in result

    def test_find_functions_json_format(self, python_project: str):
        result = find_code_impl(
            project_folder=python_project,
            pattern="def $NAME($$$)",
            language="python",
            output_format="json",
        )
        assert isinstance(result, list)
        func_names = [m.get("text", "") for m in result]
        assert any("add" in name for name in func_names)
        assert any("divide" in name for name in func_names)

    def test_find_with_max_results(self, python_project: str):
        result = find_code_impl(
            project_folder=python_project,
            pattern="def $NAME($$$)",
            language="python",
            max_results=2,
            output_format="json",
        )
        assert isinstance(result, list)
        assert len(result) == 2

    def test_find_no_matches(self, python_project: str):
        result = find_code_impl(
            project_folder=python_project,
            pattern="class NonExistentXYZ",
            language="python",
            output_format="text",
        )
        assert result == "No matches found"

    def test_find_specific_pattern(self, python_project: str):
        """Search for raise statements."""
        result = find_code_impl(
            project_folder=python_project,
            pattern="raise ValueError($MSG)",
            language="python",
            output_format="text",
        )
        assert "Cannot divide by zero" in result

    def test_find_typescript_functions(self, typescript_project: str):
        result = find_code_impl(
            project_folder=typescript_project,
            pattern="function $NAME($$$): $RET { $$$BODY }",
            language="typescript",
            output_format="text",
        )
        assert "fetchUser" in result or "setDebugMode" in result


# -- Tests: Complexity Analysis Workflow ------------------------------------


class TestComplexityWorkflowE2E:
    """E2E: project-wide complexity analysis."""

    def test_analyze_complexity(self, python_project: str):
        result = analyze_complexity_tool(
            project_folder=python_project,
            language="python",
            include_patterns=["**/*.py"],
            store_results=False,
            include_trends=False,
        )
        summary = result["summary"]
        assert summary["total_functions"] > 0
        assert "avg_cyclomatic" in summary
        assert "avg_cognitive" in summary

    def test_complex_function_exceeds_thresholds(self, python_project: str):
        """process_data has deep nesting — should appear with low thresholds."""
        result = analyze_complexity_tool(
            project_folder=python_project,
            language="python",
            include_patterns=["**/*.py"],
            cyclomatic_threshold=3,
            cognitive_threshold=5,
            store_results=False,
            include_trends=False,
        )
        # With low thresholds, some functions should exceed
        assert result["summary"]["exceeding_threshold"] > 0

    def test_code_smell_detection(self, python_project: str):
        result = detect_code_smells_tool(
            project_folder=python_project,
            language="python",
            include_patterns=["**/*.py"],
        )
        assert "total_smells" in result
        assert "files_analyzed" in result
        assert result["files_analyzed"] > 0


# -- Tests: Full Analysis Pipeline ------------------------------------------


class TestFullAnalysisPipelineE2E:
    """E2E: complete analysis pipeline (search → complexity → quality)."""

    def test_search_then_complexity(self, python_project: str):
        """Find functions, then analyze their complexity."""
        # Step 1: Find all functions
        matches = find_code_impl(
            project_folder=python_project,
            pattern="def $NAME($$$)",
            language="python",
            output_format="json",
        )
        assert isinstance(matches, list)
        assert len(matches) > 5

        # Step 2: Analyze complexity
        complexity = analyze_complexity_tool(
            project_folder=python_project,
            language="python",
            include_patterns=["**/*.py"],
            store_results=False,
            include_trends=False,
        )
        assert complexity["summary"]["total_functions"] > 0

    def test_enforce_then_report(self, python_project: str):
        """Enforce standards and generate a quality report."""
        # Step 1: Enforce standards
        enforcement = enforce_standards_tool(
            project_folder=python_project,
            language="python",
            rule_set="recommended",
        )
        assert "violations" in enforcement

        # Step 2: Generate report
        report = generate_quality_report_tool(
            enforcement_result=enforcement,
            project_name="test-project",
            output_format="markdown",
        )
        assert "content" in report
        assert "Code Quality Report" in report["content"]

    def test_typescript_enforcement_with_prefer_const(self, typescript_project: str):
        """Enforce standards on TypeScript — prefer-const should find let declarations."""
        result = enforce_standards_tool(
            project_folder=typescript_project,
            language="typescript",
            rule_set="recommended",
        )
        assert "violations" in result
        violations = result.get("violations", [])
        prefer_const = [v for v in violations if v["rule_id"] == "prefer-const"]
        # Should find let declarations (retryCount, debugMode)
        assert len(prefer_const) >= 1
