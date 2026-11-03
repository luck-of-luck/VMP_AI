"""Unit tests for _splice_fixed_code indentation-aware line replacement.

ast-grep snippets strip the leading indent from the first line but keep
absolute indentation on subsequent lines.  _splice_fixed_code must restore
the stripped indent so the replacement integrates cleanly into the file.
"""

from ast_grep_mcp.features.quality.fixer import _splice_fixed_code


def _lines(text: str) -> list[str]:
    """Convert text to lines with line endings (matching splitlines(keepends=True))."""
    return text.splitlines(keepends=True)


# ---------------------------------------------------------------------------
# Single-line replacements
# ---------------------------------------------------------------------------


class TestSingleLineSplice:
    """Single-line path: str.replace within the line preserves indent."""

    def test_simple_keyword_replace(self):
        lines = _lines("    let x = 1;\n")
        result = _splice_fixed_code(lines, 0, 0, "let x = 1;", "const x = 1;")
        assert result == _lines("    const x = 1;\n")

    def test_replace_preserves_surrounding_code(self):
        lines = _lines("  if (a == b) return;\n")
        result = _splice_fixed_code(lines, 0, 0, "a == b", "a === b")
        assert result == _lines("  if (a === b) return;\n")

    def test_replace_at_zero_indent(self):
        lines = _lines("var x = 1;\n")
        result = _splice_fixed_code(lines, 0, 0, "var x = 1;", "const x = 1;")
        assert result == _lines("const x = 1;\n")

    def test_replace_in_middle_of_file(self):
        lines = _lines("a\n    let y = 2;\nc\n")
        result = _splice_fixed_code(lines, 1, 1, "let y = 2;", "const y = 2;")
        assert result == _lines("a\n    const y = 2;\nc\n")

    def test_deep_indent(self):
        lines = _lines("            let z = 3;\n")
        result = _splice_fixed_code(lines, 0, 0, "let z = 3;", "const z = 3;")
        assert result == _lines("            const z = 3;\n")

    def test_tab_indent(self):
        lines = _lines("\t\tlet w = 4;\n")
        result = _splice_fixed_code(lines, 0, 0, "let w = 4;", "const w = 4;")
        assert result == _lines("\t\tconst w = 4;\n")


# ---------------------------------------------------------------------------
# Multi-line replacements
# ---------------------------------------------------------------------------


class TestMultiLineSplice:
    """Multi-line path: re-applies stripped first-line indent."""

    def test_bare_except_4space(self):
        """except: at 4-space indent, body at 8-space."""
        lines = _lines("    try:\n        x = 1\n    except:\n        pass\n")
        # ast-grep snippet: first-line indent stripped, body keeps absolute indent
        snippet = "except:\n        pass"
        fixed = "except Exception:\n        pass"
        result = _splice_fixed_code(lines, 2, 3, snippet, fixed)
        assert result == _lines("    try:\n        x = 1\n    except Exception:\n        pass\n")

    def test_bare_except_8space(self):
        """except: at 8-space indent, body at 12-space."""
        lines = _lines("        try:\n            x = 1\n        except:\n            pass\n")
        snippet = "except:\n            pass"
        fixed = "except Exception:\n            pass"
        result = _splice_fixed_code(lines, 2, 3, snippet, fixed)
        assert result == _lines("        try:\n            x = 1\n        except Exception:\n            pass\n")

    def test_bare_except_12space(self):
        """Deeply nested: 12-space indent."""
        lines = _lines("            try:\n                x = 1\n            except:\n                pass\n")
        snippet = "except:\n                pass"
        fixed = "except Exception:\n                pass"
        result = _splice_fixed_code(lines, 2, 3, snippet, fixed)
        assert result == _lines("            try:\n                x = 1\n            except Exception:\n                pass\n")

    def test_multi_line_body_preserved(self):
        """Multiple body lines keep their absolute indentation."""
        lines = _lines("    try:\n        x = 1\n    except:\n        log(err)\n        return None\n")
        snippet = "except:\n        log(err)\n        return None"
        fixed = "except Exception:\n        log(err)\n        return None"
        result = _splice_fixed_code(lines, 2, 4, snippet, fixed)
        assert result == _lines("    try:\n        x = 1\n    except Exception:\n        log(err)\n        return None\n")

    def test_surrounding_lines_untouched(self):
        """Lines before and after the replaced span are unchanged."""
        lines = _lines("before\n    except:\n        pass\nafter\n")
        snippet = "except:\n        pass"
        fixed = "except Exception:\n        pass"
        result = _splice_fixed_code(lines, 1, 2, snippet, fixed)
        assert result[0] == "before\n"
        assert result[-1] == "after\n"

    def test_tab_indented_multiline(self):
        """Tab-indented multi-line replacement."""
        lines = _lines("\ttry:\n\t\tx = 1\n\texcept:\n\t\tpass\n")
        snippet = "except:\n\t\tpass"
        fixed = "except Exception:\n\t\tpass"
        result = _splice_fixed_code(lines, 2, 3, snippet, fixed)
        assert result == _lines("\ttry:\n\t\tx = 1\n\texcept Exception:\n\t\tpass\n")

    def test_zero_indent_multiline(self):
        """Multi-line at column 0 — no indent to restore."""
        lines = _lines("try:\n    x = 1\nexcept:\n    pass\n")
        snippet = "except:\n    pass"
        fixed = "except Exception:\n    pass"
        result = _splice_fixed_code(lines, 2, 3, snippet, fixed)
        assert result == _lines("try:\n    x = 1\nexcept Exception:\n    pass\n")

    def test_fixed_code_fewer_lines(self):
        """Replacement with fewer lines than original span."""
        lines = _lines("    a\n    b\n    c\nd\n")
        snippet = "a\n    b\n    c"
        fixed = "combined"
        result = _splice_fixed_code(lines, 0, 2, snippet, fixed)
        assert result == _lines("    combined\nd\n")

    def test_fixed_code_more_lines(self):
        """Replacement with more lines than original span."""
        lines = _lines("    a\n    b\nc\n")
        snippet = "a\n    b"
        fixed = "x\n    y\n    z"
        result = _splice_fixed_code(lines, 0, 1, snippet, fixed)
        assert result == _lines("    x\n    y\n    z\nc\n")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestSpliceEdgeCases:
    def test_does_not_mutate_input(self):
        """The original lines list must not be modified."""
        lines = _lines("    let x = 1;\n")
        original = list(lines)
        _splice_fixed_code(lines, 0, 0, "let x = 1;", "const x = 1;")
        assert lines == original

    def test_empty_snippet_single_line(self):
        """If snippet is empty the line is unchanged (no-op replace)."""
        lines = _lines("    foo\n")
        result = _splice_fixed_code(lines, 0, 0, "", "bar")
        # str.replace("", "bar") inserts before every char — but this only
        # happens if the snippet is empty, which ast-grep won't produce.
        # We just verify it doesn't crash.
        assert len(result) == 1

    def test_last_line_no_trailing_newline(self):
        """File ending without trailing newline — each line still gets \\n."""
        lines = ["    except:\n", "        pass"]  # no final \n
        snippet = "except:\n        pass"
        fixed = "except Exception:\n        pass"
        result = _splice_fixed_code(lines, 0, 1, snippet, fixed)
        assert result == ["    except Exception:\n", "        pass\n"]
