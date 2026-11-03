"""Integration tests for ast-grep MCP server"""

import json
import os
from typing import Any, List
from unittest.mock import Mock, patch

import pytest

# Import implementation functions directly (bypasses MCP decorator)
from ast_grep_mcp.features.search.service import find_code_by_rule_impl, find_code_impl

# Alias to match original test names
find_code = find_code_impl
find_code_by_rule = find_code_by_rule_impl


@pytest.fixture
def fixtures_dir() -> str:
    """Get the path to the fixtures directory"""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))


class TestIntegration:
    """Integration tests for ast-grep MCP functions"""

    def test_find_code_text_format(self, fixtures_dir: str) -> None:
        """Test find_code with text format"""
        result = find_code(
            project_folder=fixtures_dir,
            pattern="def $NAME($$$)",
            language="python",
            output_format="text",
        )

        assert "hello" in result
        assert "add" in result
        assert "Found" in result and "matches" in result

    def test_find_code_json_format(self, fixtures_dir: str) -> None:
        """Test find_code with JSON format"""
        result = find_code(
            project_folder=fixtures_dir,
            pattern="def $NAME($$$)",
            language="python",
            output_format="json",
        )

        assert len(result) >= 2
        assert any("hello" in str(match) for match in result)
        assert any("add" in str(match) for match in result)

    @patch("ast_grep_mcp.features.search.service.run_ast_grep")
    def test_find_code_by_rule(self, mock_run: Any, fixtures_dir: str) -> None:
        """Test find_code_by_rule with mocked ast-grep"""
        # Mock the response with JSON format (since we always use JSON internally)
        mock_result = Mock()
        mock_matches: List[Any] = [
            {"text": "class Calculator:\n    pass", "file": "fixtures/example.py", "range": {"start": {"line": 6}, "end": {"line": 7}}}
        ]
        mock_result.stdout = json.dumps(mock_matches)
        mock_run.return_value = mock_result

        yaml_rule = """id: test
language: Python
rule:
  kind: class_definition
  pattern: class $NAME"""

        result = find_code_by_rule(project_folder=fixtures_dir, yaml_rule=yaml_rule, output_format="text")

        # Verify the result contains expected class name
        # Note: find_code_by_rule with text output returns raw ast-grep output,
        # not "Found X matches" format (that's only for find_code with formatted output)
        assert "Calculator" in result
        assert isinstance(result, str) and len(result) > 0

    def test_find_code_with_max_results(self, fixtures_dir: str) -> None:
        """Test find_code with max_results parameter"""
        result = find_code(
            project_folder=fixtures_dir,
            pattern="def $NAME($$$)",
            language="python",
            max_results=1,
            output_format="text",
        )

        # The new format says "showing first X of Y" instead of "limited to X"
        assert "showing first 1 of" in result or "Found 1 match" in result
        # Should only have one match in the output
        assert result.count("def ") == 1

    def test_find_code_no_matches(self, fixtures_dir: str) -> None:
        """Test find_code when no matches are found"""
        result = find_code(
            project_folder=fixtures_dir,
            pattern="nonexistent_pattern_xyz",
            output_format="text",
        )

        assert result == "No matches found"
