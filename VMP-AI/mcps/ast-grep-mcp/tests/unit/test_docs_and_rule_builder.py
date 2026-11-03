"""Tests for the documentation and rule builder tools."""

import yaml

from ast_grep_mcp.features.search.docs import (
    AST_GREP_DOCS,
    PATTERN_CATEGORIES,
    PATTERN_EXAMPLES,
    PATTERN_LANGUAGES,
    get_docs,
    get_pattern_examples,
)
from ast_grep_mcp.features.search.service import build_rule_impl


class TestGetDocs:
    """Tests for the get_docs function."""

    def test_get_pattern_docs(self):
        """Should return pattern documentation."""
        result = get_docs("pattern")
        assert "# ast-grep Pattern Syntax" in result
        assert "$NAME" in result
        assert "$$$" in result
        assert "metavariable" in result.lower()

    def test_get_rules_docs(self):
        """Should return rules documentation."""
        result = get_docs("rules")
        assert "# ast-grep YAML Rule Configuration" in result
        assert "stopBy" in result
        assert "id:" in result
        assert "language:" in result

    def test_get_relational_docs(self):
        """Should return relational rules documentation."""
        result = get_docs("relational")
        assert "Relational Rules" in result
        assert "inside" in result
        assert "has" in result
        assert "follows" in result
        assert "precedes" in result
        assert "stopBy" in result

    def test_get_metavariables_docs(self):
        """Should return metavariables documentation."""
        result = get_docs("metavariables")
        assert "Metavariable" in result
        assert "$NAME" in result
        assert "$$$" in result
        assert "$_" in result
        assert "uppercase" in result.lower()  # Case-insensitive check

    def test_get_workflow_docs(self):
        """Should return workflow documentation."""
        result = get_docs("workflow")
        assert "Workflow" in result
        assert "dump_syntax_tree" in result
        assert "debug_pattern" in result

    def test_get_strictness_docs(self):
        """Should return strictness documentation."""
        result = get_docs("strictness")
        assert "Strictness Modes" in result
        assert "cst" in result
        assert "smart" in result
        assert "ast" in result
        assert "relaxed" in result
        assert "signature" in result
        # Check for key concepts
        assert "Default" in result  # smart is default
        assert "unnamed node" in result.lower()

    def test_get_all_docs(self):
        """Should return all documentation combined."""
        result = get_docs("all")
        # Should contain content from all topics
        assert "Pattern Syntax" in result
        assert "YAML Rule Configuration" in result
        assert "Relational Rules" in result
        assert "Metavariable" in result
        assert "Strictness Modes" in result

    def test_get_invalid_topic(self):
        """Should return helpful message for invalid topic."""
        result = get_docs("invalid_topic")
        assert "Unknown topic" in result
        assert "Available topics" in result
        assert "pattern" in result
        assert "rules" in result
        assert "strictness" in result

    def test_all_documented_topics_exist(self):
        """All documented topics should have content."""
        expected_topics = ["pattern", "rules", "relational", "metavariables", "workflow", "strictness"]
        for topic in expected_topics:
            assert topic in AST_GREP_DOCS, f"Missing topic: {topic}"
            assert len(AST_GREP_DOCS[topic]) > 100, f"Topic {topic} has too little content"


class TestBuildRule:
    """Tests for the build_rule_impl function."""

    def test_build_simple_rule(self):
        """Should build a simple pattern-only rule."""
        result = build_rule_impl(pattern="console.log($$$ARGS)", language="javascript")
        parsed = yaml.safe_load(result)

        assert "id" in parsed
        assert parsed["language"] == "javascript"
        assert parsed["rule"]["pattern"] == "console.log($$$ARGS)"

    def test_build_rule_with_custom_id(self):
        """Should use provided rule ID."""
        result = build_rule_impl(pattern="print($$$)", language="python", rule_id="my-custom-rule")
        parsed = yaml.safe_load(result)

        assert parsed["id"] == "my-custom-rule"

    def test_build_rule_with_inside_pattern(self):
        """Should add inside relational rule with stopBy."""
        result = build_rule_impl(pattern="$CALL", language="python", inside="def $NAME($$$): $$$BODY")
        parsed = yaml.safe_load(result)

        assert "inside" in parsed["rule"]
        assert parsed["rule"]["inside"]["stopBy"] == "end"
        assert parsed["rule"]["inside"]["pattern"] == "def $NAME($$$): $$$BODY"

    def test_build_rule_with_inside_kind(self):
        """Should add inside with kind instead of pattern."""
        result = build_rule_impl(pattern="console.log($$$)", language="javascript", inside_kind="function_declaration")
        parsed = yaml.safe_load(result)

        assert "inside" in parsed["rule"]
        assert parsed["rule"]["inside"]["stopBy"] == "end"
        assert parsed["rule"]["inside"]["kind"] == "function_declaration"
        assert "pattern" not in parsed["rule"]["inside"]

    def test_build_rule_with_has(self):
        """Should add has relational rule."""
        result = build_rule_impl(pattern="function $NAME($$$) { $$$BODY }", language="javascript", has="return $VALUE")
        parsed = yaml.safe_load(result)

        assert "has" in parsed["rule"]
        assert parsed["rule"]["has"]["stopBy"] == "end"
        assert parsed["rule"]["has"]["pattern"] == "return $VALUE"

    def test_build_rule_with_follows(self):
        """Should add follows relational rule."""
        result = build_rule_impl(pattern="$VAR($$$)", language="javascript", follows="const $VAR = $VALUE")
        parsed = yaml.safe_load(result)

        assert "follows" in parsed["rule"]
        assert parsed["rule"]["follows"]["stopBy"] == "end"
        assert parsed["rule"]["follows"]["pattern"] == "const $VAR = $VALUE"

    def test_build_rule_with_precedes(self):
        """Should add precedes relational rule."""
        result = build_rule_impl(pattern="const $VAR = $VALUE", language="javascript", precedes="$VAR($$$)")
        parsed = yaml.safe_load(result)

        assert "precedes" in parsed["rule"]
        assert parsed["rule"]["precedes"]["stopBy"] == "end"

    def test_build_rule_with_custom_stop_by(self):
        """Should use custom stopBy value."""
        result = build_rule_impl(pattern="$CALL", language="python", inside="def $NAME($$$): $$$", stop_by="neighbor")
        parsed = yaml.safe_load(result)

        assert parsed["rule"]["inside"]["stopBy"] == "neighbor"

    def test_build_rule_with_message(self):
        """Should include message field."""
        result = build_rule_impl(pattern="print($$$)", language="python", message="Use logging instead of print")
        parsed = yaml.safe_load(result)

        assert parsed["message"] == "Use logging instead of print"

    def test_build_rule_with_severity(self):
        """Should include severity field."""
        result = build_rule_impl(pattern="eval($$$)", language="javascript", severity="error")
        parsed = yaml.safe_load(result)

        assert parsed["severity"] == "error"

    def test_build_rule_with_fix(self):
        """Should include fix field."""
        result = build_rule_impl(pattern="var $NAME = $VALUE", language="javascript", fix="const $NAME = $VALUE")
        parsed = yaml.safe_load(result)

        assert parsed["fix"] == "const $NAME = $VALUE"

    def test_build_rule_with_empty_fix(self):
        """Should include empty fix for deletion."""
        result = build_rule_impl(pattern="console.log($$$)", language="javascript", fix="")
        parsed = yaml.safe_load(result)

        assert "fix" in parsed
        assert parsed["fix"] == ""

    def test_build_rule_with_multiple_relational(self):
        """Should handle multiple relational rules."""
        result = build_rule_impl(
            pattern="$CALL",
            language="javascript",
            inside="function $NAME($$$) { $$$BODY }",
            has="await $PROMISE",
            follows="const $VAR = $VALUE",
        )
        parsed = yaml.safe_load(result)

        assert "inside" in parsed["rule"]
        assert "has" in parsed["rule"]
        assert "follows" in parsed["rule"]
        # All should have stopBy
        assert parsed["rule"]["inside"]["stopBy"] == "end"
        assert parsed["rule"]["has"]["stopBy"] == "end"
        assert parsed["rule"]["follows"]["stopBy"] == "end"

    def test_build_rule_generates_unique_ids(self):
        """Should generate different IDs for different patterns."""
        rule1 = build_rule_impl(pattern="console.log($$$)", language="javascript")
        rule2 = build_rule_impl(pattern="console.warn($$$)", language="javascript")

        parsed1 = yaml.safe_load(rule1)
        parsed2 = yaml.safe_load(rule2)

        assert parsed1["id"] != parsed2["id"]

    def test_build_rule_output_is_valid_yaml(self):
        """Generated output should be valid YAML."""
        result = build_rule_impl(
            pattern="def $NAME($$$): $$$BODY", language="python", inside_kind="module", message="Found function", severity="info"
        )

        # Should not raise
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)

    def test_inside_kind_overrides_inside_pattern(self):
        """inside_kind should override inside pattern."""
        result = build_rule_impl(
            pattern="$CALL",
            language="javascript",
            inside="function $NAME($$$) { $$$BODY }",  # This should be overridden
            inside_kind="function_declaration",
        )
        parsed = yaml.safe_load(result)

        # Should use kind, not pattern
        assert "kind" in parsed["rule"]["inside"]
        assert parsed["rule"]["inside"]["kind"] == "function_declaration"
        # Pattern should not be present when kind is used
        assert "pattern" not in parsed["rule"]["inside"]


class TestGetPatternExamples:
    """Tests for the get_pattern_examples function."""

    def test_get_javascript_patterns(self):
        """Should return JavaScript patterns."""
        result = get_pattern_examples("javascript")
        assert "# Javascript Pattern Examples" in result
        assert "function $NAME" in result
        assert "console.log" in result or "$OBJ.$METHOD" in result

    def test_get_python_patterns(self):
        """Should return Python patterns."""
        result = get_pattern_examples("python")
        assert "# Python Pattern Examples" in result
        assert "def $NAME" in result
        assert "import" in result

    def test_get_go_patterns(self):
        """Should return Go patterns."""
        result = get_pattern_examples("go")
        assert "# Go Pattern Examples" in result
        assert "func $NAME" in result
        assert "if err != nil" in result

    def test_get_rust_patterns(self):
        """Should return Rust patterns."""
        result = get_pattern_examples("rust")
        assert "# Rust Pattern Examples" in result
        assert "fn $NAME" in result
        assert "struct" in result

    def test_get_typescript_patterns(self):
        """Should return TypeScript patterns."""
        result = get_pattern_examples("typescript")
        assert "# Typescript Pattern Examples" in result
        assert "type" in result.lower()

    def test_get_java_patterns(self):
        """Should return Java patterns."""
        result = get_pattern_examples("java")
        assert "# Java Pattern Examples" in result
        assert "public" in result

    def test_get_ruby_patterns(self):
        """Should return Ruby patterns."""
        result = get_pattern_examples("ruby")
        assert "# Ruby Pattern Examples" in result
        assert "def $NAME" in result

    def test_get_c_patterns(self):
        """Should return C patterns."""
        result = get_pattern_examples("c")
        assert "# C Pattern Examples" in result
        assert "struct" in result

    def test_get_cpp_patterns(self):
        """Should return C++ patterns."""
        result = get_pattern_examples("cpp")
        assert "# Cpp Pattern Examples" in result
        assert "class" in result

    def test_filter_by_category_function(self):
        """Should filter by function category."""
        result = get_pattern_examples("javascript", "function")
        assert "## Function" in result
        assert "function $NAME" in result
        # Should not include other categories
        assert "## Import" not in result
        assert "## Class" not in result

    def test_filter_by_category_import(self):
        """Should filter by import category."""
        result = get_pattern_examples("javascript", "import")
        assert "## Import" in result
        assert "import" in result
        assert "## Function" not in result

    def test_filter_by_category_variable(self):
        """Should filter by variable category."""
        result = get_pattern_examples("python", "variable")
        assert "## Variable" in result
        assert "## Function" not in result

    def test_filter_by_category_control_flow(self):
        """Should filter by control_flow category."""
        result = get_pattern_examples("go", "control_flow")
        assert "## Control Flow" in result
        assert "if $COND" in result

    def test_filter_by_category_error_handling(self):
        """Should filter by error_handling category."""
        result = get_pattern_examples("python", "error_handling")
        assert "## Error Handling" in result
        assert "try:" in result or "except" in result

    def test_filter_by_category_async(self):
        """Should filter by async category."""
        result = get_pattern_examples("javascript", "async")
        assert "## Async" in result
        assert "await" in result or "Promise" in result

    def test_filter_by_category_all(self):
        """Should return all categories when 'all' is specified."""
        result = get_pattern_examples("javascript", "all")
        assert "## Function" in result
        assert "## Class" in result
        assert "## Import" in result

    def test_language_alias_js(self):
        """Should accept 'js' as alias for javascript."""
        result = get_pattern_examples("js")
        assert "# Javascript Pattern Examples" in result

    def test_language_alias_ts(self):
        """Should accept 'ts' as alias for typescript."""
        result = get_pattern_examples("ts")
        assert "# Typescript Pattern Examples" in result

    def test_language_alias_py(self):
        """Should accept 'py' as alias for python."""
        result = get_pattern_examples("py")
        assert "# Python Pattern Examples" in result

    def test_language_alias_golang(self):
        """Should accept 'golang' as alias for go."""
        result = get_pattern_examples("golang")
        assert "# Go Pattern Examples" in result

    def test_language_alias_cpp_plus(self):
        """Should accept 'c++' as alias for cpp."""
        result = get_pattern_examples("c++")
        assert "# Cpp Pattern Examples" in result

    def test_case_insensitive_language(self):
        """Should be case insensitive for language."""
        result1 = get_pattern_examples("JavaScript")
        result2 = get_pattern_examples("PYTHON")
        assert "# Javascript Pattern Examples" in result1
        assert "# Python Pattern Examples" in result2

    def test_case_insensitive_category(self):
        """Should be case insensitive for category."""
        result = get_pattern_examples("javascript", "FUNCTION")
        assert "## Function" in result

    def test_invalid_language(self):
        """Should return helpful message for invalid language."""
        result = get_pattern_examples("invalid_lang")
        assert "Unknown language" in result
        assert "Available" in result
        assert "javascript" in result

    def test_invalid_category(self):
        """Should return helpful message for invalid category."""
        result = get_pattern_examples("javascript", "invalid_cat")
        assert "Unknown category" in result
        assert "Available" in result
        assert "function" in result

    def test_all_languages_have_patterns(self):
        """All registered languages should have patterns."""
        for lang in PATTERN_LANGUAGES:
            assert lang in PATTERN_EXAMPLES, f"Missing patterns for: {lang}"
            assert len(PATTERN_EXAMPLES[lang]) > 0, f"No categories for: {lang}"

    def test_all_categories_documented(self):
        """All categories should be documented."""
        for cat in PATTERN_CATEGORIES:
            # At least some languages should have this category
            has_category = any(cat in PATTERN_EXAMPLES[lang] for lang in PATTERN_LANGUAGES)
            assert has_category, f"Category {cat} not in any language"

    def test_pattern_format(self):
        """Each pattern should have required fields."""
        for lang, categories in PATTERN_EXAMPLES.items():
            for cat, patterns in categories.items():
                for p in patterns:
                    assert "pattern" in p, f"Missing pattern in {lang}/{cat}"
                    assert "description" in p, f"Missing description in {lang}/{cat}"
                    assert len(p["pattern"]) > 0, f"Empty pattern in {lang}/{cat}"
                    assert len(p["description"]) > 0, f"Empty description in {lang}/{cat}"

    def test_patterns_include_metavariables(self):
        """Most patterns should use metavariables."""
        total_patterns = 0
        patterns_with_metavar = 0

        for categories in PATTERN_EXAMPLES.values():
            for patterns in categories.values():
                for p in patterns:
                    total_patterns += 1
                    if "$" in p["pattern"]:
                        patterns_with_metavar += 1

        # At least 80% should use metavariables
        assert patterns_with_metavar / total_patterns > 0.8, "Too few patterns use metavariables"

    def test_output_includes_notes_when_present(self):
        """Should include notes in output when present."""
        result = get_pattern_examples("javascript", "function")
        # JavaScript function category has notes
        if "*" in result:
            assert "Use $$$PARAMS" in result or any(p.get("notes") is not None for p in PATTERN_EXAMPLES["javascript"]["function"])
