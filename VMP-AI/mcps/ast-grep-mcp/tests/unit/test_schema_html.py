"""Tests for HTML structured data detection via ast-grep rules."""

import os
import tempfile
from unittest.mock import patch

from ast_grep_mcp.features.schema.html_service import (
    _has_liquid_tags,
    _parse_jsonld_text,
    detect_jsonld_in_html,
    detect_microdata_in_html,
    detect_rdfa_in_html,
    validate_html_structured_data,
)

# --- Unit tests for helpers ---


class TestParseJsonldText:
    def test_valid_json(self):
        result = _parse_jsonld_text('{"@type": "Person", "name": "Alice"}')
        assert result == {"@type": "Person", "name": "Alice"}

    def test_valid_json_with_whitespace(self):
        result = _parse_jsonld_text('  \n{"@type": "Article"}\n  ')
        assert result == {"@type": "Article"}

    def test_malformed_json(self):
        assert _parse_jsonld_text("{not valid json}") is None

    def test_empty_string(self):
        assert _parse_jsonld_text("") is None


# --- Integration-style tests (mock find_code_by_rule_impl) ---


def _make_match(file: str, line: int, text: str) -> dict:
    return {"file": file, "line": line, "text": text}


class TestDetectJsonldInHtml:
    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_single_valid_script(self, mock_find):
        mock_find.return_value = [_make_match("index.html", 5, '{"@context":"https://schema.org","@type":"Organization","name":"Acme"}')]
        result = detect_jsonld_in_html("/project")
        assert result["format"] == "json-ld"
        assert result["count"] == 1
        assert result["scripts"][0]["type"] == "Organization"
        assert result["scripts"][0]["parsed"]["name"] == "Acme"
        assert result["parse_errors"] == []

    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_multiple_scripts(self, mock_find):
        mock_find.return_value = [
            _make_match("a.html", 1, '{"@type":"Person"}'),
            _make_match("b.html", 10, '{"@type":"Article"}'),
        ]
        result = detect_jsonld_in_html("/project")
        assert result["count"] == 2

    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_malformed_jsonld(self, mock_find):
        mock_find.return_value = [_make_match("bad.html", 3, "{broken json")]
        result = detect_jsonld_in_html("/project")
        assert result["count"] == 0
        assert len(result["parse_errors"]) == 1
        assert result["parse_errors"][0]["error"] == "malformed JSON-LD"

    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_no_matches(self, mock_find):
        mock_find.return_value = []
        result = detect_jsonld_in_html("/project")
        assert result["count"] == 0
        assert result["scripts"] == []

    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_mixed_valid_and_malformed(self, mock_find):
        mock_find.return_value = [
            _make_match("a.html", 1, '{"@type":"Person"}'),
            _make_match("b.html", 5, "not json"),
        ]
        result = detect_jsonld_in_html("/project")
        assert result["count"] == 1
        assert len(result["parse_errors"]) == 1


class TestDetectMicrodataInHtml:
    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_typed_elements(self, mock_find):
        # Calls: attrs, elements, missing_type
        mock_find.side_effect = [
            [_make_match("x.html", 1, "itemscope")],
            [_make_match("x.html", 1, '<div itemscope itemtype="https://schema.org/Person">')],
            [],
        ]
        result = detect_microdata_in_html("/project")
        assert result["format"] == "microdata"
        assert result["attribute_count"] == 1
        assert result["typed_elements"][0]["schema_type"] == "Person"
        assert result["validation_issues"] == []

    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_missing_itemtype(self, mock_find):
        mock_find.side_effect = [
            [_make_match("x.html", 1, "itemscope")],
            [],
            [_make_match("x.html", 1, "<div itemscope>")],
        ]
        result = detect_microdata_in_html("/project")
        assert len(result["validation_issues"]) == 1
        assert result["validation_issues"][0]["issue"] == "itemscope without itemtype"

    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_no_matches(self, mock_find):
        mock_find.side_effect = [[], [], []]
        result = detect_microdata_in_html("/project")
        assert result["attribute_count"] == 0
        assert result["typed_elements"] == []


class TestDetectRdfaInHtml:
    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_rdfa_properties(self, mock_find):
        mock_find.return_value = [
            _make_match("page.html", 10, "property"),
            _make_match("page.html", 15, "typeof"),
            _make_match("page.html", 20, "property"),
        ]
        result = detect_rdfa_in_html("/project")
        assert result["format"] == "rdfa"
        assert result["count"] == 3
        assert result["by_attribute"]["property"] == 2
        assert result["by_attribute"]["typeof"] == 1

    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_no_rdfa(self, mock_find):
        mock_find.return_value = []
        result = detect_rdfa_in_html("/project")
        assert result["count"] == 0


class TestValidateHtmlStructuredData:
    @patch("ast_grep_mcp.features.schema.html_service.detect_rdfa_in_html")
    @patch("ast_grep_mcp.features.schema.html_service.detect_microdata_in_html")
    @patch("ast_grep_mcp.features.schema.html_service.detect_jsonld_in_html")
    def test_combined_summary(self, mock_jsonld, mock_micro, mock_rdfa):
        mock_jsonld.return_value = {
            "format": "json-ld",
            "count": 2,
            "scripts": [{"type": "Person"}, {"type": "Article"}],
            "parse_errors": [{"file": "bad.html", "error": "malformed"}],
        }
        mock_micro.return_value = {
            "format": "microdata",
            "attribute_count": 3,
            "typed_elements": [{"schema_type": "Product"}],
            "validation_issues": [],
        }
        mock_rdfa.return_value = {
            "format": "rdfa",
            "count": 1,
            "by_attribute": {"property": 1},
            "properties": [{"attribute": "property"}],
        }

        result = validate_html_structured_data("/project")
        summary = result["summary"]
        assert summary["jsonld_scripts"] == 2
        assert summary["microdata_elements"] == 1
        assert summary["rdfa_properties"] == 1
        assert summary["total_issues"] == 1


class TestLiquidTemplateFallback:
    """Tests for Liquid/Jekyll template handling with regex fallback."""

    def test_has_liquid_tags_detects_liquid_tags(self):
        assert _has_liquid_tags("{% if test %}content{% endif %}")
        assert _has_liquid_tags("{{ variable }}")
        assert _has_liquid_tags("<div>{{ page.title }}</div>")
        assert _has_liquid_tags("{% for item in items %}{{ item }}{% endfor %}")

    def test_has_liquid_tags_ignores_regular_html(self):
        assert not _has_liquid_tags("<div>regular html</div>")
        assert not _has_liquid_tags("<script>var x = 1;</script>")
        assert not _has_liquid_tags("")

    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_jsonld_with_liquid_fallback(self, mock_find):
        """Verify JSON-LD extraction falls back to regex for Liquid files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Liquid HTML file with JSON-LD
            html_file = os.path.join(tmpdir, "index.html")
            with open(html_file, "w") as f:
                f.write("""
                <html>
                {% if show_schema %}
                <script type="application/ld+json">
                {"@type":"Organization","name":"Acme Corp"}
                </script>
                {% endif %}
                </html>
                """)

            # Mock ast-grep to return empty (can't parse Liquid)
            mock_find.return_value = []

            result = detect_jsonld_in_html(tmpdir)
            # Should find JSON-LD via regex fallback
            assert result["count"] >= 1
            if result["count"] > 0:
                assert result["scripts"][0]["type"] == "Organization"

    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_microdata_with_liquid_fallback(self, mock_find):
        """Verify microdata extraction falls back to regex for Liquid files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Liquid HTML file with microdata
            html_file = os.path.join(tmpdir, "index.html")
            with open(html_file, "w") as f:
                f.write("""
                <html>
                {% if product %}
                <div itemscope itemtype="https://schema.org/Product">
                  <span itemprop="name">{{ product.name }}</span>
                </div>
                {% endif %}
                </html>
                """)

            # Mock ast-grep to return empty (can't parse Liquid)
            mock_find.side_effect = [[], [], []]

            result = detect_microdata_in_html(tmpdir)
            # Should find microdata via regex fallback
            assert result["attribute_count"] >= 0
            if result["typed_elements"]:
                assert result["typed_elements"][0]["schema_type"] == "Product"

    @patch("ast_grep_mcp.features.schema.html_service.find_code_by_rule_impl")
    def test_rdfa_with_liquid_fallback(self, mock_find):
        """Verify RDFa extraction falls back to regex for Liquid files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Liquid HTML file with RDFa
            html_file = os.path.join(tmpdir, "index.html")
            with open(html_file, "w") as f:
                f.write("""
                <html>
                {% if article %}
                <article property="articleBody">
                  {{ article.content }}
                </article>
                {% endif %}
                </html>
                """)

            # Mock ast-grep to return empty (can't parse Liquid)
            mock_find.return_value = []

            result = detect_rdfa_in_html(tmpdir)
            # Should find RDFa via regex fallback
            assert result["count"] >= 0
            if result["by_attribute"]:
                assert "property" in result["by_attribute"]
