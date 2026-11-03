"""Tests for prefer-const reassignment detection in fixer.py."""

import os
import re
import tempfile

from ast_grep_mcp.features.quality.fixer import (
    _extract_var_name_from_let,
    _is_variable_reassigned,
    _line_reassigns_var,
)


class TestExtractVarName:
    """Test variable name extraction from let declarations."""

    def test_simple_assignment(self):
        assert _extract_var_name_from_let("let x = 5") == "x"

    def test_with_type_annotation(self):
        assert _extract_var_name_from_let("let count: number = 0") == "count"

    def test_uninitialized(self):
        assert _extract_var_name_from_let("let value;") == "value"

    def test_destructuring_array_returns_none(self):
        assert _extract_var_name_from_let("let [a, b] = arr") is None

    def test_destructuring_object_returns_none(self):
        assert _extract_var_name_from_let("let {x, y} = obj") is None

    def test_with_leading_whitespace(self):
        assert _extract_var_name_from_let("  let foo = bar") == "foo"

    def test_in_for_loop(self):
        assert _extract_var_name_from_let("let i = 0") == "i"


class TestLineReassignsVar:
    """Test single-line reassignment detection."""

    def _pat(self, name: str) -> re.Pattern[str]:
        return re.compile(rf"\b{re.escape(name)}\b")

    def test_simple_assignment(self):
        assert _line_reassigns_var("  x = 10;", self._pat("x")) is True

    def test_compound_add(self):
        assert _line_reassigns_var("  x += 1;", self._pat("x")) is True

    def test_compound_sub(self):
        assert _line_reassigns_var("  x -= 1;", self._pat("x")) is True

    def test_postfix_increment(self):
        assert _line_reassigns_var("  x++;", self._pat("x")) is True

    def test_prefix_increment(self):
        assert _line_reassigns_var("  ++x;", self._pat("x")) is True

    def test_postfix_decrement(self):
        assert _line_reassigns_var("  x--;", self._pat("x")) is True

    def test_equality_check_not_reassignment(self):
        assert _line_reassigns_var("  if (x === 5) {", self._pat("x")) is False

    def test_not_equal_not_reassignment(self):
        assert _line_reassigns_var("  if (x !== 5) {", self._pat("x")) is False

    def test_declaration_line_detected_as_reassignment(self):
        # On a declaration line, the `= ...` is an assignment — _line_reassigns_var
        # returns True. The caller (_is_variable_reassigned) handles skipping
        # the initial declaration assignment on the declaration line.
        assert _line_reassigns_var("  const fn = (x) => x;", self._pat("fn")) is True

    def test_property_access_not_reassignment(self):
        assert _line_reassigns_var("  console.log(x);", self._pat("x")) is False

    def test_nullish_coalescing_assign(self):
        assert _line_reassigns_var("  x ??= defaultVal;", self._pat("x")) is True

    def test_logical_or_assign(self):
        assert _line_reassigns_var("  x ||= fallback;", self._pat("x")) is True

    def test_logical_and_assign(self):
        assert _line_reassigns_var("  x &&= value;", self._pat("x")) is True

    def test_substring_var_no_false_positive(self):
        """Variable 'i' should not match 'item'."""
        assert _line_reassigns_var("  item = 5;", self._pat("i")) is False

    def test_less_than_equal_not_reassignment(self):
        assert _line_reassigns_var("  if (x <= 5) {", self._pat("x")) is False

    def test_greater_than_equal_not_reassignment(self):
        assert _line_reassigns_var("  if (x >= 5) {", self._pat("x")) is False


class TestIsVariableReassigned:
    """Test file-level reassignment detection."""

    def _write_file(self, content: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".ts")
        os.write(fd, content.encode())
        os.close(fd)
        return path

    def test_reassigned_in_loop(self):
        path = self._write_file("let i = 0;\nwhile (i < 10) {\n  i++;\n}\n")
        try:
            assert _is_variable_reassigned(path, "i", 1) is True
        finally:
            os.unlink(path)

    def test_not_reassigned(self):
        path = self._write_file("let x = 5;\nconsole.log(x);\n")
        try:
            assert _is_variable_reassigned(path, "x", 1) is False
        finally:
            os.unlink(path)

    def test_reassigned_with_compound_operator(self):
        path = self._write_file("let total = 0;\ntotal += item.price;\n")
        try:
            assert _is_variable_reassigned(path, "total", 1) is True
        finally:
            os.unlink(path)

    def test_reassigned_plain_equals(self):
        path = self._write_file("let result = '';\nresult = computeValue();\n")
        try:
            assert _is_variable_reassigned(path, "result", 1) is True
        finally:
            os.unlink(path)

    def test_skips_comments(self):
        path = self._write_file("let x = 5;\n// x = 10;\nconsole.log(x);\n")
        try:
            assert _is_variable_reassigned(path, "x", 1) is False
        finally:
            os.unlink(path)

    def test_unreadable_file_returns_true(self):
        assert _is_variable_reassigned("/nonexistent/file.ts", "x", 1) is True

    def test_for_loop_iterator(self):
        path = self._write_file("for (let i = 0; i < 10; i++) {\n  console.log(i);\n}\n")
        try:
            assert _is_variable_reassigned(path, "i", 1) is True
        finally:
            os.unlink(path)
