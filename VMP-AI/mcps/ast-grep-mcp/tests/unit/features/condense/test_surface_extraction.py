"""Tests for surface extraction (extract_surface_impl)."""

import tempfile
from pathlib import Path

from ast_grep_mcp.features.condense.service import (
    _extract_generic_surface,
    _extract_js_ts_surface,
    _extract_python_surface,
    extract_surface_impl,
)


class TestExtractSurfaceImpl:
    def test_nonexistent_path_returns_error(self):
        result = extract_surface_impl("/nonexistent/xyz", "python")
        assert "error" in result

    def test_single_python_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "module.py"
            fp.write_text('def public_func(x):\n    """Docstring."""\n    return x * 2\n\ndef _private(y):\n    return y\n')
            result = extract_surface_impl(tmp, "python")
        assert result["files_processed"] == 1
        assert "condensed_source" in result
        assert "public_func" in result["condensed_source"]

    def test_reduction_pct_in_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            fp = Path(tmp) / "big.py"
            # Large file with many function bodies
            content = "\n".join(f"def func_{i}(x):\n    return x + {i}\n" for i in range(100))
            fp.write_text(content)
            result = extract_surface_impl(tmp, "python")
        assert 0.0 <= result["reduction_pct"] <= 100.0

    def test_empty_directory_returns_zero_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = extract_surface_impl(tmp, "python")
        assert result["files_processed"] == 0


class TestExtractPythonSurface:
    def test_keeps_function_definitions(self):
        lines = ["def foo(x):", "    return x", "", "def bar():", "    pass"]
        kept = _extract_python_surface(lines, include_docstrings=False)
        assert any("def foo" in line for line in kept)
        assert any("def bar" in line for line in kept)

    def test_keeps_class_definitions(self):
        lines = ["class MyClass:", "    def method(self):", "        pass"]
        kept = _extract_python_surface(lines, include_docstrings=False)
        assert any("class MyClass" in line for line in kept)

    def test_includes_docstring_when_requested(self):
        lines = [
            "def documented():",
            '    """This is a docstring."""',
            "    return 42",
        ]
        kept = _extract_python_surface(lines, include_docstrings=True)
        assert any("docstring" in line for line in kept)

    def test_excludes_body_lines(self):
        lines = [
            "def foo():",
            "    x = 1",
            "    y = 2",
            "    return x + y",
        ]
        kept = _extract_python_surface(lines, include_docstrings=False)
        # Body lines should be stripped
        joined = " ".join(kept)
        assert "x = 1" not in joined
        assert "y = 2" not in joined


class TestExtractJsTsSurface:
    def test_keeps_export_function(self):
        lines = [
            "export function add(a, b) {",
            "    return a + b;",
            "}",
            "function internal() { return 0; }",
        ]
        kept = _extract_js_ts_surface(lines, include_docstrings=False)
        joined = " ".join(kept)
        assert "export function add" in joined

    def test_internal_function_excluded(self):
        lines = [
            "export function add(a, b) {",
            "    return a + b;",
            "}",
            "function internal() { return 0; }",
        ]
        kept = _extract_js_ts_surface(lines, include_docstrings=False)
        joined = " ".join(kept)
        assert "export function add" in joined
        # Non-exported function should not be in the surface
        assert "function internal" not in joined

    def test_fallback_when_no_exports(self):
        lines = ["function foo() { return 1; }"]
        kept = _extract_js_ts_surface(lines, include_docstrings=False)
        # Should fall back to returning all lines
        assert len(kept) > 0


class TestExtractGenericSurface:
    def test_keeps_declaration_lines(self):
        lines = [
            "func Add(a, b int) int {",
            "    return a + b",
            "}",
            "type Point struct {",
            "    X, Y float64",
            "}",
        ]
        kept = _extract_generic_surface(lines)
        assert any("func Add" in line for line in kept)
        assert any("type Point" in line for line in kept)

    def test_empty_input(self):
        assert _extract_generic_surface([]) == []
