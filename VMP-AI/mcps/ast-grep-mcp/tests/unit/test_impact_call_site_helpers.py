"""Tests for extracted _to_call_site_record and _search_call_sites_for_name."""

import json
import os
from unittest.mock import MagicMock, patch

from ast_grep_mcp.features.deduplication.impact import ImpactAnalyzer


class TestToCallSiteRecord:
    analyzer = ImpactAnalyzer.__new__(ImpactAnalyzer)

    def test_absolute_path_kept(self):
        match = {
            "file": "/abs/path/file.py",
            "range": {"start": {"line": 10, "column": 5}},
            "text": "foo(bar)",
        }
        result = self.analyzer._to_call_site_record(match, "foo", "/project")
        assert result["file"] == "/abs/path/file.py"
        assert result["line"] == 11  # 0-indexed + 1
        assert result["column"] == 5
        assert result["function_called"] == "foo"
        assert result["type"] == "function_call"

    def test_relative_path_joined(self):
        match = {
            "file": "src/file.py",
            "range": {"start": {"line": 0, "column": 0}},
            "text": "bar()",
        }
        result = self.analyzer._to_call_site_record(match, "bar", "/project")
        assert result["file"] == os.path.join("/project", "src/file.py")

    def test_context_truncated(self):
        match = {
            "file": "/a.py",
            "range": {"start": {"line": 0, "column": 0}},
            "text": "x" * 200,
        }
        result = self.analyzer._to_call_site_record(match, "fn", "/p")
        assert len(result["context"]) == 100

    def test_missing_range_defaults(self):
        match = {"file": "/a.py", "text": "fn()"}
        result = self.analyzer._to_call_site_record(match, "fn", "/p")
        assert result["line"] == 1
        assert result["column"] == 0


class TestSearchCallSitesForName:
    def _make_analyzer(self):
        analyzer = ImpactAnalyzer.__new__(ImpactAnalyzer)
        analyzer.logger = MagicMock()
        return analyzer

    @patch("ast_grep_mcp.features.deduplication.impact.run_ast_grep")
    def test_filters_exclude_files(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(
                [
                    {"file": "a.py", "range": {"start": {"line": 0, "column": 0}}, "text": "fn()"},
                    {"file": "excluded.py", "range": {"start": {"line": 0, "column": 0}}, "text": "fn()"},
                ]
            ),
        )
        analyzer = self._make_analyzer()
        results = analyzer._search_call_sites_for_name("fn", "/project", "python", ["excluded.py"])
        assert len(results) == 1
        assert "excluded.py" not in results[0]["file"]

    @patch("ast_grep_mcp.features.deduplication.impact.run_ast_grep")
    def test_empty_on_nonzero_return(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="")
        analyzer = self._make_analyzer()
        results = analyzer._search_call_sites_for_name("fn", "/project", "python", [])
        assert results == []

    @patch("ast_grep_mcp.features.deduplication.impact.run_ast_grep")
    def test_empty_on_no_stdout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        analyzer = self._make_analyzer()
        results = analyzer._search_call_sites_for_name("fn", "/project", "python", [])
        assert results == []
