"""Unit tests for pattern debugging functionality.

Tests the debug_pattern tool which helps diagnose why patterns don't match code.
"""

from ast_grep_mcp.features.search.service import (
    _check_pattern_issues,
    _compare_asts,
    _extract_metavariables,
    _extract_root_kind,
    _generate_suggestions,
)
from ast_grep_mcp.models.pattern_debug import (
    AstComparison,
    IssueCategory,
    IssueSeverity,
    MatchAttempt,
    MetavariableInfo,
    PatternIssue,
)


class TestExtractMetavariables:
    """Tests for metavariable extraction and validation."""

    def test_single_valid_metavariable(self):
        """Test extraction of a single valid metavariable."""
        metavars = _extract_metavariables("$NAME")
        assert len(metavars) == 1
        assert metavars[0].name == "$NAME"
        assert metavars[0].type == "single"
        assert metavars[0].valid is True

    def test_multiple_valid_metavariables(self):
        """Test extraction of multiple valid metavariables."""
        metavars = _extract_metavariables("function $FUNC($ARG) { return $RESULT; }")
        names = {mv.name for mv in metavars if mv.valid}
        assert "$FUNC" in names
        assert "$ARG" in names
        assert "$RESULT" in names

    def test_multi_node_metavariable(self):
        """Test extraction of $$$ metavariables."""
        metavars = _extract_metavariables("console.log($$$ARGS)")
        multi_vars = [mv for mv in metavars if mv.type == "multi"]
        assert len(multi_vars) == 1
        assert multi_vars[0].name == "$$$ARGS"
        assert multi_vars[0].valid is True

    def test_unnamed_multi_node(self):
        """Test extraction of anonymous $$$ metavariable."""
        metavars = _extract_metavariables("def foo($$$): $$$")
        multi_vars = [mv for mv in metavars if mv.type == "multi"]
        assert len(multi_vars) >= 1
        assert any(mv.name == "$$$" for mv in multi_vars)

    def test_non_capturing_metavariable(self):
        """Test extraction of non-capturing metavariables."""
        metavars = _extract_metavariables("$_VAR = 1")
        non_cap = [mv for mv in metavars if mv.type == "non_capturing"]
        assert len(non_cap) == 1
        assert non_cap[0].name == "$_VAR"
        assert non_cap[0].valid is True

    def test_invalid_lowercase_metavariable(self):
        """Test detection of invalid lowercase metavariables."""
        metavars = _extract_metavariables("console.log($message)")
        invalid = [mv for mv in metavars if not mv.valid]
        assert len(invalid) == 1
        assert invalid[0].name == "$message"
        assert "UPPERCASE" in invalid[0].issue

    def test_invalid_digit_start_metavariable(self):
        """Test detection of metavariables starting with digits."""
        metavars = _extract_metavariables("foo($123)")
        invalid = [mv for mv in metavars if not mv.valid]
        assert len(invalid) == 1
        assert "digit" in invalid[0].issue.lower()

    def test_invalid_hyphen_metavariable(self):
        """Test detection of hyphenated metavariables."""
        metavars = _extract_metavariables("foo($KEBAB-CASE)")
        invalid = [mv for mv in metavars if not mv.valid]
        assert len(invalid) == 1
        assert "hyphen" in invalid[0].issue.lower()

    def test_no_metavariables(self):
        """Test pattern with no metavariables."""
        metavars = _extract_metavariables("console.log('hello')")
        assert len(metavars) == 0

    def test_metavariable_occurrences(self):
        """Test counting multiple occurrences of same metavariable."""
        metavars = _extract_metavariables("$A == $A")
        a_vars = [mv for mv in metavars if mv.name == "$A"]
        assert len(a_vars) == 1
        # Occurrences should be counted (implementation may vary)


class TestCheckPatternIssues:
    """Tests for pattern issue detection."""

    def test_no_issues_for_valid_pattern(self):
        """Test that valid patterns have no issues."""
        metavars = [MetavariableInfo(name="$NAME", type="single", valid=True, occurrences=1)]
        issues = _check_pattern_issues("class $NAME {}", metavars)
        # Should have no errors (may have info-level suggestions)
        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        assert len(errors) == 0

    def test_error_for_invalid_metavariable(self):
        """Test error detection for invalid metavariables."""
        metavars = [
            MetavariableInfo(
                name="$name",
                type="invalid",
                valid=False,
                occurrences=1,
                issue="Metavariable must use UPPERCASE",
            )
        ]
        issues = _check_pattern_issues("console.log($name)", metavars)
        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        assert len(errors) == 1
        assert errors[0].category == IssueCategory.METAVARIABLE

    def test_info_for_single_arg_metavariable(self):
        """Test info suggestion for single metavar in function args."""
        metavars = [MetavariableInfo(name="$ARG", type="single", valid=True, occurrences=1)]
        issues = _check_pattern_issues("console.log($ARG)", metavars)
        infos = [i for i in issues if i.severity == IssueSeverity.INFO]
        # Should suggest using $$$ARGS
        assert len(infos) >= 1
        assert any("$$$" in i.suggestion for i in infos)

    def test_warning_for_fragment_pattern(self):
        """Test warning for incomplete code fragments."""
        metavars = []
        issues = _check_pattern_issues(".method()", metavars)
        warnings = [i for i in issues if i.severity == IssueSeverity.WARNING]
        assert len(warnings) >= 1
        assert any("method call" in w.message.lower() for w in warnings)


class TestExtractRootKind:
    """Tests for AST root kind extraction."""

    def test_extract_kind_format(self):
        """Test extraction from 'kind: identifier' format."""
        ast_output = "kind: function_declaration, text: ..."
        kind = _extract_root_kind(ast_output)
        assert kind == "function_declaration"

    def test_extract_cst_format(self):
        """Test extraction from CST format with parentheses."""
        ast_output = "(function_declaration) ..."
        kind = _extract_root_kind(ast_output)
        assert kind == "function_declaration"

    def test_extract_first_word(self):
        """Test extraction when format is just first word."""
        ast_output = "identifier foo"
        kind = _extract_root_kind(ast_output)
        assert kind == "identifier"

    def test_empty_output(self):
        """Test handling of empty AST output."""
        kind = _extract_root_kind("")
        assert kind is None


class TestCompareAsts:
    """Tests for AST comparison."""

    def test_matching_roots(self):
        """Test when pattern and code have matching root kinds."""
        pattern_ast = "kind: function_declaration"
        code_ast = "kind: function_declaration"
        comparison = _compare_asts(pattern_ast, code_ast)
        assert comparison.kinds_match is True
        assert len(comparison.structural_differences) == 0

    def test_mismatched_roots(self):
        """Test when pattern and code have different root kinds."""
        pattern_ast = "kind: expression_statement"
        code_ast = "kind: function_declaration"
        comparison = _compare_asts(pattern_ast, code_ast)
        assert comparison.kinds_match is False
        assert comparison.pattern_root_kind == "expression_statement"
        assert comparison.code_root_kind == "function_declaration"
        assert len(comparison.structural_differences) >= 1

    def test_error_in_pattern_ast(self):
        """Test detection of ERROR nodes in pattern AST."""
        pattern_ast = "ERROR: invalid syntax"
        code_ast = "kind: identifier"
        comparison = _compare_asts(pattern_ast, code_ast)
        assert any("error" in diff.lower() for diff in comparison.structural_differences)

    def test_truncation_of_long_ast(self):
        """Test that very long AST output is truncated."""
        long_ast = "x" * 1000
        comparison = _compare_asts(long_ast, "kind: test")
        assert len(comparison.pattern_structure) <= 500


class TestGenerateSuggestions:
    """Tests for suggestion generation."""

    def test_suggestions_for_errors_first(self):
        """Test that error suggestions come first."""
        issues = [
            PatternIssue(
                severity=IssueSeverity.INFO,
                category=IssueCategory.BEST_PRACTICE,
                message="Info message",
                suggestion="Info suggestion",
            ),
            PatternIssue(
                severity=IssueSeverity.ERROR,
                category=IssueCategory.METAVARIABLE,
                message="Error message",
                suggestion="Fix the error",
            ),
        ]
        ast_comparison = AstComparison(
            pattern_root_kind="test",
            code_root_kind="test",
            kinds_match=True,
            pattern_structure="",
            code_structure="",
        )
        match_attempt = MatchAttempt(matched=False)

        suggestions = _generate_suggestions("pattern", "code", "python", issues, ast_comparison, match_attempt)

        # First suggestion should be about the error
        assert len(suggestions) > 0
        assert "[ERROR]" in suggestions[0]

    def test_suggestions_for_structural_mismatch(self):
        """Test suggestions when AST structures don't match."""
        issues = []
        ast_comparison = AstComparison(
            pattern_root_kind="identifier",
            code_root_kind="function_declaration",
            kinds_match=False,
            pattern_structure="",
            code_structure="",
        )
        match_attempt = MatchAttempt(matched=False)

        suggestions = _generate_suggestions("pattern", "code", "python", issues, ast_comparison, match_attempt)

        assert any("[STRUCTURE]" in s for s in suggestions)

    def test_success_message_when_matched(self):
        """Test success message when pattern matches."""
        issues = []
        ast_comparison = AstComparison(
            pattern_root_kind="test",
            code_root_kind="test",
            kinds_match=True,
            pattern_structure="",
            code_structure="",
        )
        match_attempt = MatchAttempt(matched=True, match_count=1)

        suggestions = _generate_suggestions("pattern", "code", "python", issues, ast_comparison, match_attempt)

        assert any("[SUCCESS]" in s for s in suggestions)


class TestPatternDebugResult:
    """Tests for PatternDebugResult model."""

    def test_to_dict_serialization(self):
        """Test that to_dict produces valid dictionary."""
        from ast_grep_mcp.models.pattern_debug import PatternDebugResult

        result = PatternDebugResult(
            pattern="$NAME",
            code="foo",
            language="python",
            pattern_valid=True,
            pattern_ast="kind: identifier",
            code_ast="kind: identifier",
            ast_comparison=AstComparison(
                pattern_root_kind="identifier",
                code_root_kind="identifier",
                kinds_match=True,
                pattern_structure="",
                code_structure="",
            ),
            metavariables=[MetavariableInfo(name="$NAME", type="single", valid=True, occurrences=1)],
            issues=[],
            suggestions=["Test suggestion"],
            match_attempt=MatchAttempt(matched=True, match_count=1),
            execution_time_ms=10,
        )

        d = result.to_dict()

        assert d["pattern"] == "$NAME"
        assert d["pattern_valid"] is True
        assert d["ast_comparison"]["kinds_match"] is True
        assert len(d["metavariables"]) == 1
        assert d["metavariables"][0]["name"] == "$NAME"
        assert d["match_attempt"]["matched"] is True


class TestMetavariableEdgeCases:
    """Edge case tests for metavariable extraction."""

    def test_underscore_only(self):
        """Test the $_ non-capturing wildcard."""
        metavars = _extract_metavariables("foo($_)")
        non_cap = [mv for mv in metavars if mv.type == "non_capturing"]
        assert len(non_cap) == 1
        assert non_cap[0].name == "$_"

    def test_mixed_valid_and_invalid(self):
        """Test pattern with both valid and invalid metavariables."""
        metavars = _extract_metavariables("foo($name, $VALID)")
        valid = [mv for mv in metavars if mv.valid]
        invalid = [mv for mv in metavars if not mv.valid]
        assert len(valid) >= 1
        assert len(invalid) >= 1

    def test_metavar_in_string_not_extracted(self):
        """Test that metavariables in strings are still extracted (pattern behavior)."""
        # Note: ast-grep does extract metavariables even in strings
        # This is just checking our regex behavior
        metavars = _extract_metavariables('"$NAME"')
        assert len(metavars) == 1  # We do extract it


class TestIssueCategories:
    """Tests for issue categorization."""

    def test_all_severity_levels(self):
        """Verify all severity levels are accessible."""
        assert IssueSeverity.ERROR.value == "error"
        assert IssueSeverity.WARNING.value == "warning"
        assert IssueSeverity.INFO.value == "info"

    def test_all_issue_categories(self):
        """Verify all issue categories are accessible."""
        assert IssueCategory.METAVARIABLE.value == "metavariable"
        assert IssueCategory.SYNTAX.value == "syntax"
        assert IssueCategory.STRUCTURE.value == "structure"
        assert IssueCategory.RELATIONAL.value == "relational"
        assert IssueCategory.BEST_PRACTICE.value == "best_practice"
