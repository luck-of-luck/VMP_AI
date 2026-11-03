"""Tests for markdown frontmatter Schema.org extraction and validation."""

import pytest

from ast_grep_mcp.features.schema.markdown_service import (
    _extract_frontmatter,
    _find_schema_fields,
    _get_nested,
    extract_schema_from_frontmatter,
    suggest_frontmatter_enhancements,
    validate_frontmatter_schema,
)

# --- Unit tests for helpers ---


class TestExtractFrontmatter:
    def test_valid_frontmatter(self):
        content = "---\ntitle: Hello\nauthor: Alice\n---\n# Body"
        result = _extract_frontmatter(content)
        assert result == {"title": "Hello", "author": "Alice"}

    def test_no_frontmatter(self):
        assert _extract_frontmatter("# Just a heading") is None

    def test_empty_frontmatter(self):
        # yaml.safe_load of empty string returns None
        assert _extract_frontmatter("---\n\n---\n") is None

    def test_malformed_yaml(self):
        content = "---\n: broken: yaml: [[[[\n---\n"
        assert _extract_frontmatter(content) is None

    def test_non_dict_frontmatter(self):
        # e.g. frontmatter is just a string
        content = "---\njust a string\n---\n"
        assert _extract_frontmatter(content) is None


class TestGetNested:
    def test_single_level(self):
        assert _get_nested({"a": 1}, "a") == 1

    def test_two_levels(self):
        assert _get_nested({"seo": {"schema": {"@type": "Article"}}}, "seo.schema") == {"@type": "Article"}

    def test_missing_key(self):
        assert _get_nested({"a": 1}, "b") is None

    def test_non_dict_intermediate(self):
        assert _get_nested({"a": "string"}, "a.b") is None


class TestFindSchemaFields:
    def test_direct_type(self):
        fm = {"@type": "Person", "@context": "https://schema.org", "name": "Alice"}
        result = _find_schema_fields(fm)
        assert "@type" in result
        assert "@context" in result
        assert "name" not in result  # not a schema key

    def test_nested_seo_schema(self):
        fm = {"title": "Post", "seo": {"schema": {"@type": "Article"}}}
        result = _find_schema_fields(fm)
        assert "seo.schema" in result
        assert result["seo.schema"] == {"@type": "Article"}

    def test_structured_data_key(self):
        fm = {"structured_data": {"@type": "Product"}}
        result = _find_schema_fields(fm)
        assert "structured_data" in result

    def test_no_schema_fields(self):
        fm = {"title": "Hello", "author": "Bob"}
        result = _find_schema_fields(fm)
        assert result == {}


# --- Integration tests with filesystem ---


class TestExtractSchemaFromFrontmatter:
    def test_with_schema(self, tmp_path):
        md_file = tmp_path / "post.md"
        md_file.write_text('---\n"@type": Article\n"@context": https://schema.org\nheadline: Test\n---\n# Body\n')

        result = extract_schema_from_frontmatter(str(tmp_path))
        assert result["files_scanned"] == 1
        assert len(result["with_schema"]) == 1
        assert result["with_schema"][0]["schema_fields"]["@type"] == "Article"

    def test_without_schema(self, tmp_path):
        md_file = tmp_path / "post.md"
        md_file.write_text("---\ntitle: Hello\nauthor: Bob\n---\n# Body\n")

        result = extract_schema_from_frontmatter(str(tmp_path))
        assert len(result["without_schema"]) == 1

    def test_no_frontmatter(self, tmp_path):
        md_file = tmp_path / "readme.md"
        md_file.write_text("# Just a heading\nNo frontmatter here.\n")

        result = extract_schema_from_frontmatter(str(tmp_path))
        assert len(result["no_frontmatter"]) == 1

    def test_multiple_files(self, tmp_path):
        (tmp_path / "a.md").write_text('---\n"@type": Person\n---\n# A\n')
        (tmp_path / "b.md").write_text("---\ntitle: B\n---\n# B\n")
        (tmp_path / "c.md").write_text("# C\n")

        result = extract_schema_from_frontmatter(str(tmp_path))
        assert result["files_scanned"] == 3
        assert len(result["with_schema"]) == 1
        assert len(result["without_schema"]) == 1
        assert len(result["no_frontmatter"]) == 1

    def test_custom_globs(self, tmp_path):
        (tmp_path / "doc.mdx").write_text('---\n"@type": HowTo\n---\n# Doc\n')
        (tmp_path / "other.md").write_text('---\n"@type": Article\n---\n# Other\n')

        result = extract_schema_from_frontmatter(str(tmp_path), file_globs=["**/*.mdx"])
        assert result["files_scanned"] == 1
        assert result["with_schema"][0]["schema_fields"]["@type"] == "HowTo"


class TestValidateFrontmatterSchema:
    def test_valid_schema(self, tmp_path):
        (tmp_path / "post.md").write_text('---\n"@type": Article\n"@context": https://schema.org\n---\n# Post\n')
        result = validate_frontmatter_schema(str(tmp_path))
        assert result["files_validated"] == 1
        assert result["validations"][0]["valid"] is True
        assert result["total_errors"] == 0

    def test_missing_context(self, tmp_path):
        (tmp_path / "post.md").write_text('---\n"@type": Article\n---\n# Post\n')
        result = validate_frontmatter_schema(str(tmp_path))
        assert result["total_warnings"] == 1
        assert "@context" in result["validations"][0]["warnings"][0]

    def test_bad_context(self, tmp_path):
        (tmp_path / "post.md").write_text('---\n"@type": Article\n"@context": https://example.com\n---\n# Post\n')
        result = validate_frontmatter_schema(str(tmp_path))
        assert result["total_errors"] == 1

    def test_unrecognized_type(self, tmp_path):
        (tmp_path / "post.md").write_text('---\n"@type": CustomThing\n"@context": https://schema.org\n---\n# Post\n')
        result = validate_frontmatter_schema(str(tmp_path))
        assert result["total_warnings"] == 1
        assert "Unrecognized" in result["validations"][0]["warnings"][0]


class TestSuggestFrontmatterEnhancements:
    def test_missing_properties(self, tmp_path):
        (tmp_path / "post.md").write_text('---\n"@type": Article\n---\n# Post\n')
        result = suggest_frontmatter_enhancements(str(tmp_path))
        assert result["files_with_suggestions"] == 1
        suggestion = result["suggestions"][0]
        assert "headline" in suggestion["missing_properties"]
        assert "author" in suggestion["missing_properties"]
        assert "datePublished" in suggestion["missing_properties"]

    def test_complete_article(self, tmp_path):
        (tmp_path / "post.md").write_text('---\n"@type": Article\nheadline: Test\nauthor: Alice\ndatePublished: 2024-01-01\n---\n# Post\n')
        result = suggest_frontmatter_enhancements(str(tmp_path))
        assert result["files_with_suggestions"] == 0

    def test_partial_completeness(self, tmp_path):
        (tmp_path / "post.md").write_text('---\n"@type": Article\nheadline: Test\n---\n# Post\n')
        result = suggest_frontmatter_enhancements(str(tmp_path))
        suggestion = result["suggestions"][0]
        assert suggestion["completeness"] == pytest.approx(0.33, abs=0.01)
        assert "headline" not in suggestion["missing_properties"]

    def test_non_string_type_skipped(self, tmp_path):
        (tmp_path / "post.md").write_text('---\n"@type":\n  - Article\n  - BlogPosting\n---\n# Post\n')
        result = suggest_frontmatter_enhancements(str(tmp_path))
        # list type is not a string, so skipped
        assert result["files_with_suggestions"] == 0

    def test_unknown_type_no_suggestions(self, tmp_path):
        (tmp_path / "post.md").write_text('---\n"@type": CustomThing\n---\n# Post\n')
        result = suggest_frontmatter_enhancements(str(tmp_path))
        assert result["files_with_suggestions"] == 0
