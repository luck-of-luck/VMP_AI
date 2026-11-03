"""Tests for condense tool-layer functions.

Tests all 6 standalone tool functions from tools.py:
- condense_extract_surface_tool
- condense_normalize_tool
- condense_strip_tool
- condense_pack_tool
- condense_estimate_tool
- condense_train_dictionary_tool

Focuses on: error handling, response structure, path validation,
strategy validation, and delegation to impl functions.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from ast_grep_mcp.features.condense.tools import (
    condense_estimate_tool,
    condense_extract_surface_tool,
    condense_normalize_tool,
    condense_pack_tool,
    condense_strip_tool,
    condense_train_dictionary_tool,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_PYTHON = """\
import os

def greet(name: str) -> str:
    \"\"\"Say hello.\"\"\"
    print(name)
    return f"hello {name}"

class Greeter:
    def run(self):
        return self.greet("world")
"""

SAMPLE_JS = """\
const x = 1;
console.log(x);
export function add(a, b) { return a + b; }
"""


def _write_project(tmp: str, files: dict[str, str]) -> None:
    """Write a dict of {filename: content} into tmp directory."""
    for name, content in files.items():
        (Path(tmp) / name).write_text(content)


# ---------------------------------------------------------------------------
# condense_extract_surface_tool
# ---------------------------------------------------------------------------


class TestExtractSurfaceTool:
    def test_nonexistent_path_returns_error(self):
        result = condense_extract_surface_tool("/nonexistent/xyz", "python")
        assert "error" in result

    def test_valid_directory_returns_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_project(tmp, {"main.py": SAMPLE_PYTHON})
            result = condense_extract_surface_tool(tmp, "python")
        assert "condensed_source" in result
        assert "files_processed" in result
        assert "reduction_pct" in result
        assert result["files_processed"] == 1

    def test_single_file_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "main.py"
            fp.write_text(SAMPLE_PYTHON)
            result = condense_extract_surface_tool(str(fp), "python")
        assert "condensed_source" in result
        assert result["files_processed"] == 1

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = condense_extract_surface_tool(tmp, "python")
        assert result["files_processed"] == 0


# ---------------------------------------------------------------------------
# condense_normalize_tool
# ---------------------------------------------------------------------------


class TestNormalizeTool:
    def test_nonexistent_path_raises(self):
        with pytest.raises(FileNotFoundError):
            condense_normalize_tool("/nonexistent/xyz.py", "python")

    def test_directory_path_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(IsADirectoryError, match="(?i)directory"):
                condense_normalize_tool(tmp, "python")

    def test_valid_file_returns_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "main.py"
            fp.write_text(SAMPLE_PYTHON)
            result = condense_normalize_tool(str(fp), "python")
        assert "normalized_source" in result
        assert "normalizations_applied" in result
        assert "original_bytes" in result
        assert "normalized_bytes" in result
        assert isinstance(result["normalizations_applied"], int)

    def test_js_normalization_applies(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "index.js"
            fp.write_text('const x = "hello";\n')
            result = condense_normalize_tool(str(fp), "javascript")
        assert "error" not in result
        assert result["original_bytes"] > 0


# ---------------------------------------------------------------------------
# condense_strip_tool
# ---------------------------------------------------------------------------


class TestStripTool:
    def test_nonexistent_path_raises(self):
        with pytest.raises(FileNotFoundError):
            condense_strip_tool("/nonexistent/xyz.py", "python")

    def test_directory_path_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(IsADirectoryError, match="(?i)directory"):
                condense_strip_tool(tmp, "python")

    def test_valid_file_returns_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "main.py"
            fp.write_text(SAMPLE_PYTHON)
            result = condense_strip_tool(str(fp), "python")
        assert "stripped_source" in result
        assert "lines_removed" in result
        assert "original_lines" in result
        assert "stripped_lines" in result

    def test_strips_print_statement(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "main.py"
            fp.write_text("print('debug')\nx = 1\n")
            result = condense_strip_tool(str(fp), "python")
        assert result["lines_removed"] >= 1
        assert result["stripped_lines"] < result["original_lines"]

    def test_js_strips_console_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "index.js"
            fp.write_text(SAMPLE_JS)
            result = condense_strip_tool(str(fp), "javascript")
        assert result["lines_removed"] >= 1


# ---------------------------------------------------------------------------
# condense_pack_tool
# ---------------------------------------------------------------------------


class TestPackTool:
    def test_invalid_strategy_returns_error_with_descriptions(self):
        result = condense_pack_tool("/tmp", strategy="banana")
        assert "error" in result
        assert "banana" in result["error"]
        assert "strategy_descriptions" in result
        assert isinstance(result["strategy_descriptions"], dict)
        assert len(result["strategy_descriptions"]) >= 4

    def test_all_valid_strategies_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_project(tmp, {"a.py": "x = 1\n"})
            for strategy in ("ai_chat", "ai_analysis", "archival", "polyglot"):
                result = condense_pack_tool(tmp, strategy=strategy)
                assert "error" not in result, f"{strategy} failed: {result}"

    def test_valid_call_returns_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_project(tmp, {"main.py": SAMPLE_PYTHON})
            result = condense_pack_tool(tmp, strategy="ai_analysis")
        for key in (
            "condensed_output",
            "strategy",
            "files_processed",
            "reduction_pct",
            "original_bytes",
            "condensed_bytes",
            "original_tokens_est",
            "condensed_tokens_est",
            "per_language_stats",
        ):
            assert key in result, f"Missing key: {key}"
        assert result["strategy"] == "ai_analysis"
        assert result["files_processed"] >= 1

    def test_nonexistent_path_returns_error(self):
        result = condense_pack_tool("/nonexistent/xyz", strategy="ai_analysis")
        assert "error" in result

    def test_default_strategy_is_ai_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_project(tmp, {"a.py": "x = 1\n"})
            result = condense_pack_tool(tmp)
        assert result["strategy"] == "ai_analysis"


# ---------------------------------------------------------------------------
# condense_estimate_tool
# ---------------------------------------------------------------------------


class TestEstimateTool:
    def test_nonexistent_path_returns_error(self):
        result = condense_estimate_tool("/nonexistent/xyz")
        assert result["total_files"] == 0

    def test_valid_directory_returns_expected_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_project(tmp, {"main.py": SAMPLE_PYTHON})
            result = condense_estimate_tool(tmp)
        for key in (
            "total_files",
            "total_lines",
            "total_bytes",
            "estimated_condensed_bytes",
            "estimated_tokens",
            "top_reduction_candidates",
        ):
            assert key in result, f"Missing key: {key}"
        assert result["total_files"] >= 1

    def test_language_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write_project(
                tmp,
                {
                    "a.py": "x = 1\n",
                    "b.ts": "const y = 2;\n",
                },
            )
            result = condense_estimate_tool(tmp, language="python")
        assert result["total_files"] == 1

    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = condense_estimate_tool(tmp)
        assert result["total_files"] == 0


# ---------------------------------------------------------------------------
# condense_train_dictionary_tool
# ---------------------------------------------------------------------------


class TestTrainDictionaryTool:
    def test_nonexistent_path_returns_error(self):
        result = condense_train_dictionary_tool("/nonexistent/xyz")
        assert "error" in result

    def test_file_path_returns_error(self):
        with tempfile.NamedTemporaryFile(suffix=".py") as f:
            result = condense_train_dictionary_tool(f.name)
        assert "error" in result

    def test_empty_directory_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = condense_train_dictionary_tool(tmp)
        assert "error" in result

    def test_successful_training_mocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(15):
                (Path(tmp) / f"m{i}.py").write_text(f"def func_{i}(x):\n    return x + {i}\n")

            def fake_write(samples: list, dict_path: Path) -> tuple[int, int]:
                dict_path.write_bytes(b"\x00" * 1024)
                return 15, 15000

            with patch(
                "ast_grep_mcp.features.condense.dictionary._write_training_result",
                side_effect=fake_write,
            ):
                result = condense_train_dictionary_tool(tmp, language="python")

        for key in ("dict_path", "dict_size_bytes", "samples_used", "estimated_improvement_pct", "language"):
            assert key in result, f"Missing key: {key}"
        assert result["samples_used"] == 15
        assert result["language"] == "python"

    def test_returns_error_dict_not_exception(self):
        """Train dictionary tool returns error dict, never raises."""
        result = condense_train_dictionary_tool("/nonexistent/path")
        assert isinstance(result, dict)
        assert "error" in result


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------


class TestRegisterCondenseTools:
    def test_all_tools_registered(self):
        from ast_grep_mcp.features.condense.tools import register_condense_tools

        class MockMCP:
            def __init__(self):
                self.tools: dict[str, object] = {}

            def tool(self):
                def decorator(func):
                    self.tools[func.__name__] = func
                    return func

                return decorator

        mcp = MockMCP()
        register_condense_tools(mcp)

        expected = {
            "condense_extract_surface",
            "condense_normalize",
            "condense_strip",
            "condense_pack",
            "condense_estimate",
            "condense_train_dictionary",
        }
        assert set(mcp.tools.keys()) == expected
