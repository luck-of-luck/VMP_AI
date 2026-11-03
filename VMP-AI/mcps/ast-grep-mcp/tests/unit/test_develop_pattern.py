"""Tests for the develop_pattern functionality."""

from ast_grep_mcp.features.search.service import (
    _extract_identifiers,
    _extract_literals,
    _generate_generalized_pattern,
    _generate_pattern_suggestions,
    _generate_refinement_steps,
    _generate_yaml_template,
    develop_pattern_impl,
)
from ast_grep_mcp.models.pattern_develop import (
    CodeAnalysis,
    PatternSuggestion,
    SuggestionType,
)


class TestExtractIdentifiers:
    """Tests for identifier extraction."""

    def test_extract_javascript_identifiers(self):
        """Should extract identifiers from JavaScript code."""
        code = "const result = calculate(value)"
        identifiers = _extract_identifiers(code, "javascript")
        assert "result" in identifiers
        assert "calculate" in identifiers
        assert "value" in identifiers
        assert "const" not in identifiers  # keyword excluded

    def test_extract_python_identifiers(self):
        """Should extract identifiers from Python code."""
        code = "def process(data):\n    return result"
        identifiers = _extract_identifiers(code, "python")
        assert "process" in identifiers
        assert "data" in identifiers
        assert "result" in identifiers
        assert "def" not in identifiers  # keyword excluded
        assert "return" not in identifiers  # keyword excluded

    def test_preserve_order(self):
        """Should preserve order of first occurrence."""
        code = "foo bar baz"
        identifiers = _extract_identifiers(code, "javascript")
        assert identifiers == ["foo", "bar", "baz"]

    def test_deduplicate(self):
        """Should deduplicate identifiers."""
        code = "foo bar foo baz bar"
        identifiers = _extract_identifiers(code, "javascript")
        assert identifiers.count("foo") == 1
        assert identifiers.count("bar") == 1


class TestExtractLiterals:
    """Tests for literal extraction."""

    def test_extract_string_literals(self):
        """Should extract string literals."""
        code = "console.log(\"hello\", 'world')"
        literals = _extract_literals(code)
        assert '"hello"' in literals
        assert "'world'" in literals

    def test_extract_number_literals(self):
        """Should extract number literals."""
        code = "const x = 42 + 3.14"
        literals = _extract_literals(code)
        assert "42" in literals
        assert "3.14" in literals

    def test_extract_template_literals(self):
        """Should extract template literals."""
        code = "const msg = `hello ${name}`"
        literals = _extract_literals(code)
        assert "`hello ${name}`" in literals


class TestGenerateGeneralizedPattern:
    """Tests for generalized pattern generation."""

    def test_replace_identifiers(self):
        """Should replace identifiers with metavariables."""
        code = "console.log(message)"
        identifiers = ["console", "log", "message"]
        literals: list[str] = []
        pattern = _generate_generalized_pattern(code, identifiers, literals)
        assert "$" in pattern  # Should have metavariables

    def test_replace_literals(self):
        """Should replace literals with metavariables."""
        code = 'print("hello")'
        identifiers = ["print"]
        literals = ['"hello"']
        pattern = _generate_generalized_pattern(code, identifiers, literals)
        assert "$LITERAL" in pattern

    def test_limit_replacements(self):
        """Should limit number of replacements."""
        code = "a b c d e f g h i j"
        identifiers = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
        literals: list[str] = []
        pattern = _generate_generalized_pattern(code, identifiers, literals)
        # Should only replace first 5 identifiers
        metavar_count = pattern.count("$")
        assert metavar_count <= 5


class TestGeneratePatternSuggestions:
    """Tests for pattern suggestion generation."""

    def test_generates_exact_suggestion(self):
        """Should always generate an exact match suggestion."""
        analysis = CodeAnalysis(
            root_kind="call_expression",
            child_kinds=["identifier", "arguments"],
            identifiers=["console", "log"],
            literals=['"hello"'],
            keywords=[],
            complexity="simple",
            ast_preview="...",
        )
        code = 'console.log("hello")'
        suggestions = _generate_pattern_suggestions(code, "javascript", analysis)

        exact = [s for s in suggestions if s.type == SuggestionType.EXACT]
        assert len(exact) >= 1
        assert exact[0].pattern == code

    def test_generates_generalized_suggestion(self):
        """Should generate generalized suggestion when identifiers exist."""
        analysis = CodeAnalysis(
            root_kind="call_expression",
            child_kinds=["identifier", "arguments"],
            identifiers=["console", "log", "message"],
            literals=[],
            keywords=[],
            complexity="simple",
            ast_preview="...",
        )
        code = "console.log(message)"
        suggestions = _generate_pattern_suggestions(code, "javascript", analysis)

        generalized = [s for s in suggestions if s.type == SuggestionType.GENERALIZED]
        assert len(generalized) >= 1
        assert "$" in generalized[0].pattern

    def test_generates_structural_suggestion(self):
        """Should generate structural suggestion when root_kind is known."""
        analysis = CodeAnalysis(
            root_kind="call_expression",
            child_kinds=["identifier"],
            identifiers=["foo"],
            literals=[],
            keywords=[],
            complexity="simple",
            ast_preview="...",
        )
        code = "foo()"
        suggestions = _generate_pattern_suggestions(code, "javascript", analysis)

        structural = [s for s in suggestions if s.type == SuggestionType.STRUCTURAL]
        assert len(structural) >= 1
        assert "call_expression" in structural[0].pattern


class TestGenerateRefinementSteps:
    """Tests for refinement step generation."""

    def test_matching_pattern_steps(self):
        """Should provide refinement steps when pattern matches."""
        analysis = CodeAnalysis(
            root_kind="call_expression",
            child_kinds=[],
            identifiers=[],
            literals=[],
            keywords=[],
            complexity="simple",
            ast_preview="...",
        )
        steps = _generate_refinement_steps("foo()", "javascript", analysis, True)
        assert len(steps) >= 1
        # Should suggest adding constraints
        actions = [s.action for s in steps]
        assert any("constraint" in a.lower() for a in actions)

    def test_non_matching_pattern_steps(self):
        """Should provide debugging steps when pattern doesn't match."""
        analysis = CodeAnalysis(
            root_kind="call_expression",
            child_kinds=[],
            identifiers=[],
            literals=[],
            keywords=[],
            complexity="simple",
            ast_preview="...",
        )
        steps = _generate_refinement_steps("foo()", "javascript", analysis, False)
        assert len(steps) >= 2
        # Should suggest checking metavariable syntax
        actions = [s.action for s in steps]
        assert any("metavariable" in a.lower() for a in actions)
        # Should suggest using dump_syntax_tree
        assert any("dump_syntax_tree" in a.lower() for a in actions)


class TestGenerateYamlTemplate:
    """Tests for YAML template generation."""

    def test_basic_template(self):
        """Should generate valid YAML template."""
        analysis = CodeAnalysis(
            root_kind="call_expression",
            child_kinds=["identifier"],
            identifiers=["foo"],
            literals=[],
            keywords=[],
            complexity="simple",
            ast_preview="...",
        )
        template = _generate_yaml_template("foo()", "javascript", analysis)
        assert "id:" in template
        assert "language: javascript" in template
        assert "rule:" in template
        assert "pattern:" in template

    def test_complex_template_has_suggestions(self):
        """Should add constraint suggestions for complex patterns."""
        analysis = CodeAnalysis(
            root_kind="function_declaration",
            child_kinds=["identifier", "parameters", "block"],
            identifiers=["foo", "bar"],
            literals=[],
            keywords=[],
            complexity="complex",
            ast_preview="...",
        )
        template = _generate_yaml_template("function foo() {}", "javascript", analysis)
        assert "inside:" in template or "Optional:" in template


class TestDevelopPatternImpl:
    """Integration tests for develop_pattern_impl."""

    def test_simple_javascript_code(self):
        """Should analyze simple JavaScript code."""
        result = develop_pattern_impl(
            code='console.log("hello")',
            language="javascript",
        )
        assert result.language == "javascript"
        assert result.code_analysis is not None
        assert result.code_analysis.root_kind != "unknown"
        assert len(result.suggested_patterns) >= 1
        assert result.best_pattern is not None
        assert result.yaml_rule_template is not None
        assert len(result.next_steps) >= 1

    def test_simple_python_code(self):
        """Should analyze simple Python code."""
        result = develop_pattern_impl(
            code='print("hello")',
            language="python",
        )
        assert result.language == "python"
        assert result.code_analysis is not None
        assert len(result.suggested_patterns) >= 1

    def test_function_declaration(self):
        """Should analyze function declaration."""
        result = develop_pattern_impl(
            code="function greet(name) { return name; }",
            language="javascript",
        )
        assert result.code_analysis is not None
        assert "greet" in result.code_analysis.identifiers or "name" in result.code_analysis.identifiers
        assert len(result.suggested_patterns) >= 1

    def test_provides_yaml_template(self):
        """Should provide a YAML template."""
        result = develop_pattern_impl(
            code="const x = 42",
            language="javascript",
        )
        assert "id:" in result.yaml_rule_template
        assert "language:" in result.yaml_rule_template
        assert "rule:" in result.yaml_rule_template

    def test_provides_next_steps(self):
        """Should provide next steps guidance."""
        result = develop_pattern_impl(
            code="foo(bar)",
            language="javascript",
        )
        assert len(result.next_steps) >= 2
        # Should mention find_code or debug_pattern
        steps_text = " ".join(result.next_steps)
        assert "find_code" in steps_text or "debug_pattern" in steps_text

    def test_with_goal_parameter(self):
        """Should accept optional goal parameter."""
        result = develop_pattern_impl(
            code="console.log(x)",
            language="javascript",
            goal="Find all console.log calls",
        )
        # Should still work with goal
        assert result.code_analysis is not None
        assert len(result.suggested_patterns) >= 1

    def test_to_dict_serialization(self):
        """Should serialize result to dict."""
        result = develop_pattern_impl(
            code="foo()",
            language="javascript",
        )
        result_dict = result.to_dict()
        assert "code" in result_dict
        assert "language" in result_dict
        assert "code_analysis" in result_dict
        assert "suggested_patterns" in result_dict
        assert "best_pattern" in result_dict
        assert "pattern_matches" in result_dict
        assert "yaml_rule_template" in result_dict
        assert "next_steps" in result_dict

    def test_code_analysis_includes_complexity(self):
        """Should determine code complexity."""
        # Simple code
        simple_result = develop_pattern_impl(
            code="x = 1",
            language="python",
        )
        assert simple_result.code_analysis.complexity in ["simple", "medium", "complex"]

    def test_multiple_suggestions(self):
        """Should provide multiple pattern suggestions."""
        result = develop_pattern_impl(
            code='calculate(value, "option")',
            language="javascript",
        )
        # Should have at least exact and possibly generalized
        assert len(result.suggested_patterns) >= 1
        types = {s.type for s in result.suggested_patterns}
        assert SuggestionType.EXACT in types


class TestPatternSuggestion:
    """Tests for PatternSuggestion model."""

    def test_to_dict(self):
        """Should serialize to dict."""
        suggestion = PatternSuggestion(
            pattern="foo($ARG)",
            description="Matches foo calls",
            type=SuggestionType.GENERALIZED,
            confidence=0.8,
            notes="Use $$$ARGS for multiple",
        )
        result = suggestion.to_dict()
        assert result["pattern"] == "foo($ARG)"
        assert result["description"] == "Matches foo calls"
        assert result["type"] == "generalized"
        assert result["confidence"] == 0.8
        assert result["notes"] == "Use $$$ARGS for multiple"


class TestCodeAnalysis:
    """Tests for CodeAnalysis model."""

    def test_to_dict(self):
        """Should serialize to dict."""
        analysis = CodeAnalysis(
            root_kind="call_expression",
            child_kinds=["identifier", "arguments"],
            identifiers=["foo", "bar"],
            literals=['"test"'],
            keywords=["const"],
            complexity="simple",
            ast_preview="...",
        )
        result = analysis.to_dict()
        assert result["root_kind"] == "call_expression"
        assert "identifier" in result["child_kinds"]
        assert "foo" in result["identifiers"]
        assert '"test"' in result["literals"]
        assert result["complexity"] == "simple"
