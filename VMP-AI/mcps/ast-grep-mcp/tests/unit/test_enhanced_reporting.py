"""Unit tests for Phase 5 Enhanced Reporting functions.

Tests for:
- format_diff_with_colors
- generate_before_after_example
- visualize_complexity
- create_enhanced_duplication_response
"""

import os
import sys

# Add the parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from ast_grep_mcp.features.deduplication.reporting import DuplicationReporter
from ast_grep_mcp.utils.formatters import format_diff_with_colors

# Instantiate reporter for use in tests
_reporter = DuplicationReporter()
create_enhanced_duplication_response = _reporter.create_enhanced_duplication_response
generate_before_after_example = _reporter.generate_before_after_example
visualize_complexity = _reporter.visualize_complexity


class TestFormatDiffWithColors:
    """Tests for format_diff_with_colors function."""

    def test_empty_diff(self):
        """Test with empty diff string."""
        result = format_diff_with_colors("")
        assert result == ""

    def test_colors_additions(self):
        """Test that additions are colored green."""
        diff = "+added line"
        result = format_diff_with_colors(diff)
        assert "\033[32m" in result  # Green
        assert "+added line" in result
        assert "\033[0m" in result  # Reset

    def test_colors_deletions(self):
        """Test that deletions are colored red."""
        diff = "-removed line"
        result = format_diff_with_colors(diff)
        assert "\033[31m" in result  # Red
        assert "-removed line" in result
        assert "\033[0m" in result  # Reset

    def test_colors_hunk_headers(self):
        """Test that hunk headers are colored cyan."""
        diff = "@@ -1,3 +1,4 @@"
        result = format_diff_with_colors(diff)
        assert "\033[36m" in result  # Cyan
        assert "@@ -1,3 +1,4 @@" in result

    def test_colors_file_headers(self):
        """Test that file headers are colored yellow."""
        diff = "--- a/file.py\n+++ b/file.py"
        result = format_diff_with_colors(diff)
        assert "\033[33m" in result  # Yellow
        assert "--- a/file.py" in result
        assert "+++ b/file.py" in result

    def test_context_lines_uncolored(self):
        """Test that context lines remain uncolored."""
        diff = " context line"
        result = format_diff_with_colors(diff)
        assert result == " context line"
        assert "\033[" not in result

    def test_full_diff(self):
        """Test complete diff with all line types."""
        diff = """--- a/file.py
+++ b/file.py
@@ -1,3 +1,4 @@
 context
-old
+new
+added"""
        result = format_diff_with_colors(diff)

        # Check all colors present
        assert "\033[33m" in result  # Yellow for headers
        assert "\033[36m" in result  # Cyan for hunk
        assert "\033[31m" in result  # Red for deletion
        assert "\033[32m" in result  # Green for additions


class TestGenerateBeforeAfterExample:
    """Tests for generate_before_after_example function."""

    def test_basic_example(self):
        """Test basic before/after generation."""
        original = "x = 1\ny = 2\nresult = x + y"
        replacement = "result = add(x, y)"
        function_name = "add"

        result = generate_before_after_example(original, replacement, function_name)

        assert result["function_name"] == "add"
        assert result["original_lines"] == 3
        assert result["replacement_lines"] == 1
        assert result["lines_saved"] == 2
        assert "add" in result["explanation"]

    def test_line_numbers_in_before(self):
        """Test that before section includes line numbers."""
        original = "line1\nline2"
        replacement = "single_call()"

        result = generate_before_after_example(original, replacement, "func")

        assert "  1 |" in result["before"]
        assert "  2 |" in result["before"]

    def test_line_numbers_in_after(self):
        """Test that after section includes line numbers."""
        original = "a\nb\nc"
        replacement = "x\ny"

        result = generate_before_after_example(original, replacement, "func")

        assert "  1 |" in result["after"]
        assert "  2 |" in result["after"]

    def test_raw_content_preserved(self):
        """Test that raw content is preserved without line numbers."""
        original = "def foo():\n    pass"
        replacement = "foo()"

        result = generate_before_after_example(original, replacement, "foo")

        assert result["before_raw"] == original.strip()
        assert result["after_raw"] == replacement.strip()

    def test_function_definition_generated(self):
        """Test that function definition is generated."""
        result = generate_before_after_example("a", "b", "my_func")
        assert result["function_definition"] == "def my_func(...):"

    def test_no_lines_saved(self):
        """Test when replacement is same length or longer."""
        original = "x"
        replacement = "very_long_function_call()"

        result = generate_before_after_example(original, replacement, "func")

        assert result["lines_saved"] <= 0
        assert "reusability" in result["explanation"]

    def test_explanation_content(self):
        """Test explanation includes relevant details."""
        original = "a\nb\nc\nd"
        replacement = "func()"

        result = generate_before_after_example(original, replacement, "my_func")

        assert "4 lines" in result["explanation"]
        assert "my_func" in result["explanation"]
        assert "3 line(s)" in result["explanation"]

    def test_whitespace_handling(self):
        """Test that whitespace is stripped properly."""
        original = "\n  code  \n"
        replacement = "  call()  "

        result = generate_before_after_example(original, replacement, "func")

        assert result["before_raw"] == "code"
        assert result["after_raw"] == "call()"


class TestVisualizeComplexity:
    """Tests for visualize_complexity function."""

    def test_low_complexity(self):
        """Test low complexity score (1-3)."""
        for score in [1, 2, 3]:
            result = visualize_complexity(score)
            assert result["description"] == "Low"
            assert result["color_code"] == "\033[32m"  # Green
            assert len(result["recommendations"]) > 0

    def test_medium_complexity(self):
        """Test medium complexity score (4-6)."""
        for score in [4, 5, 6]:
            result = visualize_complexity(score)
            assert result["description"] == "Medium"
            assert result["color_code"] == "\033[33m"  # Yellow

    def test_high_complexity(self):
        """Test high complexity score (7-10)."""
        for score in [7, 8, 9, 10]:
            result = visualize_complexity(score)
            assert result["description"] == "High"
            assert result["color_code"] == "\033[31m"  # Red
            assert len(result["recommendations"]) >= 4

    def test_bar_visualization(self):
        """Test ASCII bar visualization."""
        result = visualize_complexity(5)
        assert "[=====" in result["bar"]
        assert "     ]" in result["bar"]
        assert "5/10" in result["bar"]

    def test_bar_colored_version(self):
        """Test colored bar includes ANSI codes."""
        result = visualize_complexity(5)
        assert "\033[" in result["bar_colored"]
        assert "\033[0m" in result["bar_colored"]

    def test_formatted_output(self):
        """Test formatted string output."""
        result = visualize_complexity(3)
        assert "Low Complexity (3/10)" in result["formatted"]
        assert "[===" in result["formatted"]

    def test_score_clamping_low(self):
        """Test that scores below 1 are clamped."""
        result = visualize_complexity(0)
        assert result["score"] == 1

        result = visualize_complexity(-5)
        assert result["score"] == 1

    def test_score_clamping_high(self):
        """Test that scores above 10 are clamped."""
        result = visualize_complexity(15)
        assert result["score"] == 10

        result = visualize_complexity(100)
        assert result["score"] == 10

    def test_recommendations_are_actionable(self):
        """Test that recommendations contain actionable advice."""
        low = visualize_complexity(2)
        assert any("refactor" in r.lower() for r in low["recommendations"])

        high = visualize_complexity(9)
        assert any("test" in r.lower() for r in high["recommendations"])


class TestCreateEnhancedDuplicationResponse:
    """Tests for create_enhanced_duplication_response function."""

    def test_empty_candidates(self):
        """Test with empty candidate list."""
        result = create_enhanced_duplication_response([])

        assert result["candidates"] == []
        assert result["summary"]["total_candidates"] == 0
        assert result["metadata"]["version"] == "5.0"

    def test_single_candidate(self):
        """Test with single duplication candidate."""
        candidates = [
            {
                "files": ["/path/file1.py", "/path/file2.py"],
                "code": "x = 1\ny = 2",
                "replacement": "init_vars()",
                "function_name": "init_vars",
                "similarity": 95.5,
                "complexity": 3,
            }
        ]

        result = create_enhanced_duplication_response(candidates)

        assert len(result["candidates"]) == 1
        assert result["candidates"][0]["id"] == "DUP-001"
        assert result["candidates"][0]["complexity_score"] == 3
        assert "before_after" in result["candidates"][0]
        assert "complexity_viz" in result["candidates"][0]

    def test_multiple_candidates_sorted_by_priority(self):
        """Test that candidates are sorted by priority."""
        candidates = [
            {
                "files": ["/f1.py"],
                "code": "x",
                "replacement": "a()",
                "complexity": 8,  # High complexity = lower priority
            },
            {
                "files": ["/f1.py", "/f2.py", "/f3.py"],
                "code": "y\nz\nw",
                "replacement": "b()",
                "complexity": 2,  # Low complexity = higher priority
            },
        ]

        result = create_enhanced_duplication_response(candidates)

        # Second candidate should be first due to more occurrences and lower complexity
        assert result["candidates"][0]["complexity_score"] == 2
        assert len(result["candidates"][0]["files"]) == 3

    def test_summary_statistics(self):
        """Test summary statistics are calculated correctly."""
        candidates = [
            {"files": ["/a.py", "/b.py"], "code": "line1\nline2\nline3", "replacement": "call()", "complexity": 2},
            {"files": ["/c.py"], "code": "x\ny", "replacement": "other()", "complexity": 7},
        ]

        result = create_enhanced_duplication_response(candidates)

        assert result["summary"]["total_candidates"] == 2
        assert result["summary"]["total_files_affected"] == 3
        assert result["summary"]["complexity_distribution"]["low"] == 1
        assert result["summary"]["complexity_distribution"]["high"] == 1

    def test_global_recommendations_generated(self):
        """Test that global recommendations are generated."""
        # Create many high-complexity candidates
        candidates = [
            {
                "files": [f"/file{i}.py" for i in range(3)],
                "code": "\n".join([f"line{j}" for j in range(20)]),
                "replacement": "func()",
                "complexity": 8,
            }
            for _ in range(6)
        ]

        result = create_enhanced_duplication_response(candidates)

        # Should have recommendations about high complexity and many duplicates
        assert len(result["recommendations"]) > 0

    def test_include_diffs_option(self):
        """Test include_diffs parameter."""
        candidates = [{"files": ["/test.py"], "code": "old", "replacement": "new", "complexity": 5}]

        # With diffs
        result_with = create_enhanced_duplication_response(candidates, include_diffs=True)
        assert result_with["candidates"][0]["diff_preview"] is not None

        # Without diffs
        result_without = create_enhanced_duplication_response(candidates, include_diffs=False)
        assert result_without["candidates"][0]["diff_preview"] is None

    def test_include_colors_option(self):
        """Test include_colors parameter."""
        candidates = [{"files": ["/test.py"], "code": "old\ncode", "replacement": "new", "complexity": 5}]

        result_colored = create_enhanced_duplication_response(candidates, include_diffs=True, include_colors=True)

        # Should contain ANSI color codes
        diff = result_colored["candidates"][0]["diff_preview"]
        assert diff is not None
        assert "\033[" in diff

    def test_metadata_fields(self):
        """Test metadata contains required fields."""
        result = create_enhanced_duplication_response([])

        assert "version" in result["metadata"]
        assert "includes_diffs" in result["metadata"]
        assert "includes_colors" in result["metadata"]
        assert "generated_at" in result["metadata"]

    def test_before_after_included(self):
        """Test before/after examples are included for each candidate."""
        candidates = [
            {
                "files": ["/test.py"],
                "code": "a = 1\nb = 2\nc = a + b",
                "replacement": "c = add(a, b)",
                "function_name": "add",
                "complexity": 3,
            }
        ]

        result = create_enhanced_duplication_response(candidates)

        before_after = result["candidates"][0]["before_after"]
        assert "before" in before_after
        assert "after" in before_after
        assert "explanation" in before_after
        assert before_after["lines_saved"] == 2

    def test_complexity_viz_included(self):
        """Test complexity visualization is included."""
        candidates = [{"files": ["/test.py"], "code": "x", "replacement": "y", "complexity": 7}]

        result = create_enhanced_duplication_response(candidates)

        viz = result["candidates"][0]["complexity_viz"]
        assert viz["description"] == "High"
        assert "bar" in viz
        assert len(viz["recommendations"]) > 0

    def test_default_values_for_missing_fields(self):
        """Test that missing fields get default values."""
        candidates = [
            {
                "files": ["/test.py"],
                "code": "test",
                "replacement": "func()",
                # Missing: function_name, similarity, complexity
            }
        ]

        result = create_enhanced_duplication_response(candidates)

        candidate = result["candidates"][0]
        assert candidate["similarity_score"] == 100.0  # Default
        assert candidate["complexity_score"] == 5  # Default
        assert "extracted_function_0" in candidate["suggested_function_name"]

    def test_priority_calculation(self):
        """Test priority calculation formula."""
        candidates = [
            {
                "files": ["/a.py", "/b.py"],  # 2 occurrences
                "code": "line1\nline2\nline3\nline4",  # 4 lines
                "replacement": "call()",
                "complexity": 3,
            }
        ]

        result = create_enhanced_duplication_response(candidates)

        # Priority = (2 * 10) + (4 * 2) - (3 * 3) = 20 + 8 - 9 = 19
        assert result["candidates"][0]["priority"] == 19

    def test_total_lines_saveable(self):
        """Test total lines saveable calculation."""
        candidates = [
            {
                "files": ["/a.py", "/b.py"],  # 2 occurrences
                "code": "a\nb\nc",  # 3 lines
                "replacement": "x()",  # 1 line, saves 2 per occurrence
                "complexity": 3,
            }
        ]

        result = create_enhanced_duplication_response(candidates)

        # 2 lines saved * 2 occurrences = 4 total
        assert result["summary"]["total_lines_saveable"] == 4


class TestIntegration:
    """Integration tests combining multiple Phase 5 functions."""

    def test_full_workflow(self):
        """Test complete enhanced reporting workflow."""
        # Simulate real duplication detection output
        candidates = [
            {
                "files": ["/src/utils.py", "/src/helpers.py"],
                "locations": [("/src/utils.py", 10, 15), ("/src/helpers.py", 20, 25)],
                "code": """def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result""",
                "replacement": "result = process_data(data)",
                "function_name": "process_data",
                "similarity": 98.5,
                "complexity": 4,
            },
            {
                "files": ["/src/api.py", "/src/views.py", "/src/handlers.py"],
                "code": """try:
    response = fetch()
except Exception as e:
    log_error(e)
    raise""",
                "replacement": "response = safe_fetch()",
                "function_name": "safe_fetch",
                "similarity": 100.0,
                "complexity": 6,
            },
        ]

        result = create_enhanced_duplication_response(candidates, include_diffs=True, include_colors=False)

        # Verify structure
        assert len(result["candidates"]) == 2
        assert result["summary"]["total_candidates"] == 2
        assert result["summary"]["total_files_affected"] == 5

        # Verify sorting (more occurrences should be higher priority)
        assert len(result["candidates"][0]["files"]) >= len(result["candidates"][1]["files"])

        # Verify each candidate has all required fields
        for candidate in result["candidates"]:
            assert "id" in candidate
            assert "before_after" in candidate
            assert "complexity_viz" in candidate
            assert "diff_preview" in candidate
            assert "priority" in candidate

    def test_colored_output(self):
        """Test that colored output is properly formatted."""
        candidates = [
            {
                "files": ["/test.py"],
                "code": "old_value = 1\nold_calc = old_value * 2",
                "replacement": "result = calculate(1)",
                "function_name": "calculate",
                "complexity": 2,
            }
        ]

        result = create_enhanced_duplication_response(candidates, include_diffs=True, include_colors=True)

        diff = result["candidates"][0]["diff_preview"]
        viz = result["candidates"][0]["complexity_viz"]

        # Both should have color codes
        assert "\033[" in diff
        assert "\033[" in viz["bar_colored"]
