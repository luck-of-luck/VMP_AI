"""Unit tests for Schema.org entity graph enhancement feature."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ast_grep_mcp.constants import SEODefaults
from ast_grep_mcp.features.schema.enhancement_rules import (
    get_all_properties_for_entity,
    get_property_example,
    get_property_priority,
    get_rich_results_for_entity,
    get_rich_results_for_property,
)
from ast_grep_mcp.features.schema.enhancement_service import (
    _build_priority_summary,
    _build_property_reason,
    _calculate_entity_seo_score,
    _calculate_overall_seo_score,
    _extract_entities_from_data,
    _extract_entity_type,
    _find_id_references,
    _generate_diff,
    _generate_enhanced_graph,
    _generate_example_entity,
    _load_graph_from_source,
    _parse_suggestion_rule,
    _suggest_missing_entities,
    _validate_entity_references,
    _validate_graph_structure,
)
from ast_grep_mcp.models.schema_enhancement import (
    EnhancementPriority,
    EntityEnhancement,
    MissingEntitySuggestion,
    PropertyEnhancement,
)

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def simple_organization_graph() -> List[Dict[str, Any]]:
    """Simple organization entity with minimal properties."""
    return [
        {
            "@type": "Organization",
            "@id": "https://example.com#organization",
            "name": "Example Corp",
            "url": "https://example.com",
        }
    ]


@pytest.fixture
def complete_organization_graph() -> List[Dict[str, Any]]:
    """Complete organization with FAQPage and WebSite."""
    return [
        {
            "@type": "Organization",
            "@id": "https://example.com#organization",
            "name": "Example Corp",
            "url": "https://example.com",
            "aggregateRating": {"@type": "AggregateRating"},
            "review": [{"@type": "Review"}],
            "contactPoint": {"@type": "ContactPoint"},
        },
        {
            "@type": "FAQPage",
            "@id": "https://example.com/faq#faqpage",
            "mainEntity": [],
        },
        {
            "@type": "WebSite",
            "@id": "https://example.com#website",
            "name": "Example Corp",
        },
    ]


@pytest.fixture
def sample_entity_enhancement() -> EntityEnhancement:
    """Sample entity enhancement with suggestions."""
    return EntityEnhancement(
        entity_id="https://example.com#org",
        entity_type="Organization",
        existing_properties=["name", "url"],
        suggested_properties=[
            PropertyEnhancement(
                property_name="aggregateRating",
                expected_types=["AggregateRating"],
                priority=EnhancementPriority.CRITICAL,
                reason="Critical for review snippets",
                example_value={"@type": "AggregateRating"},
            ),
            PropertyEnhancement(
                property_name="contactPoint",
                expected_types=["ContactPoint"],
                priority=EnhancementPriority.HIGH,
                reason="Improves local SEO",
                example_value={"@type": "ContactPoint"},
            ),
        ],
        validation_issues=[],
        seo_score=75.0,
    )


# =============================================================================
# Enhancement Rules Tests
# =============================================================================


class TestEnhancementRules:
    """Tests for enhancement_rules.py functions."""

    def test_get_property_priority_known_property(self):
        """Test getting priority for known property."""
        priority = get_property_priority("Organization", "aggregateRating")
        assert priority == EnhancementPriority.CRITICAL

    def test_get_property_priority_unknown_property(self):
        """Test getting priority for unknown property defaults to LOW."""
        priority = get_property_priority("Organization", "unknownProperty")
        assert priority == EnhancementPriority.LOW

    def test_get_property_priority_unknown_entity(self):
        """Test getting priority for unknown entity type."""
        priority = get_property_priority("UnknownType", "name")
        assert priority == EnhancementPriority.LOW

    def test_get_rich_results_for_property(self):
        """Test getting rich results for property."""
        results = get_rich_results_for_property("aggregateRating")
        assert "Organization reviews" in results
        assert "Product reviews" in results

    def test_get_rich_results_for_property_unknown(self):
        """Test getting rich results for unknown property."""
        results = get_rich_results_for_property("unknownProperty")
        assert results == []

    def test_get_rich_results_for_entity(self):
        """Test getting rich results for entity type."""
        results = get_rich_results_for_entity("FAQPage")
        assert "FAQ rich results" in results

    def test_get_all_properties_for_entity(self):
        """Test getting all properties for entity type."""
        props = get_all_properties_for_entity("Organization")
        assert "aggregateRating" in props
        assert props["aggregateRating"] == EnhancementPriority.CRITICAL

    def test_get_property_example_known(self):
        """Test getting example for known property."""
        example = get_property_example("aggregateRating")
        assert example is not None
        assert "@type" in example
        assert example["@type"] == "AggregateRating"

    def test_get_property_example_unknown(self):
        """Test getting example for unknown property returns None."""
        example = get_property_example("unknownProperty")
        assert example is None


# =============================================================================
# Graph Loading Tests
# =============================================================================


class TestGraphLoading:
    """Tests for graph loading functions."""

    def test_extract_entities_from_graph_array(self):
        """Test extracting entities from @graph array."""
        data = {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "Organization", "name": "Test"},
                {"@type": "Person", "name": "John"},
            ],
        }
        entities = _extract_entities_from_data(data)
        assert len(entities) == 2
        assert entities[0]["@type"] == "Organization"
        assert entities[1]["@type"] == "Person"

    def test_extract_entities_from_single_entity(self):
        """Test extracting single entity without @graph."""
        data = {"@type": "Organization", "name": "Test"}
        entities = _extract_entities_from_data(data)
        assert len(entities) == 1
        assert entities[0]["@type"] == "Organization"

    def test_extract_entities_from_array(self):
        """Test extracting entities from raw array."""
        data = [
            {"@type": "Organization", "name": "Test"},
            {"@type": "Person", "name": "John"},
        ]
        entities = _extract_entities_from_data(data)
        assert len(entities) == 2

    def test_load_graph_from_file(self):
        """Test loading graph from JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "@context": "https://schema.org",
                    "@graph": [{"@type": "Organization", "name": "Test"}],
                },
                f,
            )
            f.flush()

            entities = _load_graph_from_source(f.name, "file")
            assert len(entities) == 1
            assert entities[0]["@type"] == "Organization"

            os.unlink(f.name)

    def test_load_graph_from_directory(self):
        """Test loading graphs from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two JSON files
            file1 = Path(tmpdir) / "org.json"
            file2 = Path(tmpdir) / "person.json"

            file1.write_text(json.dumps({"@context": "https://schema.org", "@graph": [{"@type": "Organization"}]}))
            file2.write_text(json.dumps({"@context": "https://schema.org", "@graph": [{"@type": "Person"}]}))

            entities = _load_graph_from_source(tmpdir, "directory")
            assert len(entities) == 2

    def test_load_graph_invalid_type(self):
        """Test loading with invalid input type raises error."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"@type": "Organization"}, f)
            f.flush()
            try:
                with pytest.raises(ValueError, match="Invalid input_type"):
                    _load_graph_from_source(f.name, "invalid")
            finally:
                os.unlink(f.name)

    def test_load_graph_nonexistent_file(self):
        """Test loading nonexistent file raises error."""
        with pytest.raises(ValueError, match="does not exist"):
            _load_graph_from_source("/nonexistent/file.json", "file")


# =============================================================================
# Entity Analysis Tests
# =============================================================================


class TestEntityAnalysis:
    """Tests for entity analysis functions."""

    def test_extract_entity_type_string(self):
        """Test extracting entity type from string @type."""
        entity = {"@type": "Organization", "name": "Test"}
        assert _extract_entity_type(entity) == "Organization"

    def test_extract_entity_type_array(self):
        """Test extracting entity type from array @type."""
        entity = {"@type": ["Organization", "LocalBusiness"], "name": "Test"}
        assert _extract_entity_type(entity) == "Organization"

    def test_extract_entity_type_missing(self):
        """Test extracting entity type when missing."""
        entity = {"name": "Test"}
        assert _extract_entity_type(entity) is None

    def test_build_property_reason_critical(self):
        """Test building reason for critical property."""
        reason = _build_property_reason(EnhancementPriority.CRITICAL, "Review snippets")
        assert "Critical for Review snippets" in reason

    def test_build_property_reason_high_no_rich_result(self):
        """Test building reason for high property without rich result."""
        reason = _build_property_reason(EnhancementPriority.HIGH, None)
        assert "Strongly recommended for SEO" in reason


# =============================================================================
# Reference Validation Tests
# =============================================================================


class TestReferenceValidation:
    """Tests for reference validation functions."""

    def test_find_id_references_simple(self):
        """Test finding @id references in simple structure."""
        entity = {
            "@type": "Organization",
            "founder": {"@id": "https://example.com#person"},
        }
        refs = _find_id_references(entity)
        assert len(refs) == 1
        assert refs[0][0] == "https://example.com#person"
        assert refs[0][1] == "founder"

    def test_find_id_references_nested(self):
        """Test finding @id references in nested structure."""
        entity = {
            "@type": "Organization",
            "member": [
                {"@id": "https://example.com#person1"},
                {"@id": "https://example.com#person2"},
            ],
        }
        refs = _find_id_references(entity)
        assert len(refs) == 2

    def test_validate_entity_references_valid(self):
        """Test validation with valid references."""
        entity = {
            "@type": "Organization",
            "@id": "https://example.com#org",
            "founder": {"@id": "https://example.com#person"},
        }
        all_ids = {"https://example.com#org", "https://example.com#person"}
        issues = _validate_entity_references(entity, all_ids)
        assert len(issues) == 0

    def test_validate_entity_references_broken(self):
        """Test validation with broken references."""
        entity = {
            "@type": "Organization",
            "@id": "https://example.com#org",
            "founder": {"@id": "https://example.com#missing"},
        }
        all_ids = {"https://example.com#org"}
        issues = _validate_entity_references(entity, all_ids)
        assert len(issues) == 1
        assert "missing" in issues[0]


# =============================================================================
# Missing Entity Detection Tests
# =============================================================================


class TestMissingEntityDetection:
    """Tests for missing entity detection functions."""

    def test_parse_suggestion_rule_has(self):
        """Test parsing 'has:Type' rule."""
        result = _parse_suggestion_rule("has:Organization", {"Organization"}, {"Organization": 1})
        assert result is True

    def test_parse_suggestion_rule_not_has(self):
        """Test parsing 'NOT has:Type' rule."""
        result = _parse_suggestion_rule("NOT has:FAQPage", {"Organization"}, {"Organization": 1})
        assert result is True

    def test_parse_suggestion_rule_count(self):
        """Test parsing 'count:Type>N' rule."""
        result = _parse_suggestion_rule("count:WebPage>1", {"WebPage"}, {"WebPage": 3})
        assert result is True

    def test_parse_suggestion_rule_count_not_met(self):
        """Test parsing count rule when threshold not met."""
        result = _parse_suggestion_rule("count:WebPage>5", {"WebPage"}, {"WebPage": 3})
        assert result is False

    def test_parse_suggestion_rule_complex_and(self):
        """Test parsing complex AND rule."""
        result = _parse_suggestion_rule(
            "has:Organization AND NOT has:FAQPage",
            {"Organization"},
            {"Organization": 1},
        )
        assert result is True

    def test_suggest_missing_entities_faq_page(self, simple_organization_graph: List[Dict[str, Any]]):
        """Test suggesting FAQPage for organization."""
        mock_client = MagicMock()
        suggestions = _suggest_missing_entities(simple_organization_graph, mock_client)

        # Should suggest FAQPage and WebSite
        entity_types = [s.entity_type for s in suggestions]
        assert "FAQPage" in entity_types
        assert "WebSite" in entity_types

    def test_suggest_missing_entities_complete_graph(self, complete_organization_graph: List[Dict[str, Any]]):
        """Test no FAQPage/WebSite suggestion for complete graph."""
        mock_client = MagicMock()
        suggestions = _suggest_missing_entities(complete_organization_graph, mock_client)

        # Should NOT suggest FAQPage or WebSite
        entity_types = [s.entity_type for s in suggestions]
        assert "FAQPage" not in entity_types
        assert "WebSite" not in entity_types

    def test_suggest_missing_entities_dict_type_skipped(self):
        """Test that dict @type values are skipped without unhashable type error."""
        entities = [
            {"@type": "Organization", "name": "Acme"},
            {"@type": {"@id": "https://schema.org/Person"}, "name": "John"},
        ]
        mock_client = MagicMock()
        # Should not raise "unhashable type: 'dict'"
        suggestions = _suggest_missing_entities(entities, mock_client)
        assert isinstance(suggestions, list)

    def test_suggest_missing_entities_list_with_dict_type_skipped(self):
        """Test that list @type containing dicts skips non-string entries."""
        entities = [
            {"@type": ["Organization", {"@id": "https://schema.org/LocalBusiness"}], "name": "Acme"},
        ]
        mock_client = MagicMock()
        # Should not raise, and should still process the string "Organization"
        suggestions = _suggest_missing_entities(entities, mock_client)
        assert isinstance(suggestions, list)

    def test_generate_example_entity_faqpage(self):
        """Test generating FAQPage example."""
        example = _generate_example_entity("FAQPage")
        assert example["@type"] == "FAQPage"
        assert "mainEntity" in example
        assert "@id" in example

    def test_generate_example_entity_website(self):
        """Test generating WebSite example."""
        example = _generate_example_entity("WebSite")
        assert example["@type"] == "WebSite"
        assert "potentialAction" in example

    def test_generate_example_entity_breadcrumblist(self):
        """Test generating BreadcrumbList example."""
        example = _generate_example_entity("BreadcrumbList")
        assert example["@type"] == "BreadcrumbList"
        assert "itemListElement" in example


# =============================================================================
# SEO Scoring Tests
# =============================================================================


class TestSEOScoring:
    """Tests for SEO scoring functions."""

    def test_calculate_entity_seo_score_perfect(self):
        """Test perfect score with no missing properties."""
        entity = EntityEnhancement(
            entity_id="test",
            entity_type="Organization",
            existing_properties=["name", "url", "logo"],
            suggested_properties=[],
            validation_issues=[],
            seo_score=0.0,
        )
        score = _calculate_entity_seo_score(entity)
        assert score == SEODefaults.BASE_SCORE  # Perfect + validation bonus capped

    def test_calculate_entity_seo_score_critical_missing(self, sample_entity_enhancement: EntityEnhancement):
        """Test score with critical property missing."""
        score = _calculate_entity_seo_score(sample_entity_enhancement)
        # 100 - 20 (CRITICAL) - 10 (HIGH) + 5 (no validation issues)
        assert score == 75.0

    def test_calculate_entity_seo_score_with_validation_issues(self):
        """Test score penalty for validation issues."""
        entity = EntityEnhancement(
            entity_id="test",
            entity_type="Organization",
            existing_properties=["name"],
            suggested_properties=[],
            validation_issues=["Broken reference"],
            seo_score=0.0,
        )
        score = _calculate_entity_seo_score(entity)
        assert score == SEODefaults.BASE_SCORE  # No bonus for validation issues

    def test_calculate_overall_seo_score(self, sample_entity_enhancement: EntityEnhancement):
        """Test overall score calculation."""
        sample_entity_enhancement.seo_score = 80.0
        missing = [
            MissingEntitySuggestion(
                entity_type="FAQPage",
                priority=EnhancementPriority.HIGH,
                reason="Enable FAQ rich results",
                example={},
            )
        ]
        score = _calculate_overall_seo_score([sample_entity_enhancement], missing)
        # 80.0 (entity avg) - 10 (HIGH missing entity)
        assert score == 70.0

    def test_build_priority_summary(self, sample_entity_enhancement: EntityEnhancement):
        """Test building priority summary."""
        missing = [
            MissingEntitySuggestion(
                entity_type="FAQPage",
                priority=EnhancementPriority.HIGH,
                reason="Test",
                example={},
            )
        ]
        summary = _build_priority_summary([sample_entity_enhancement], missing)
        assert summary["critical"] == 1  # aggregateRating
        assert summary["high"] == 2  # contactPoint + FAQPage
        assert summary["medium"] == 0
        assert summary["low"] == 0


# =============================================================================
# Graph Structure Validation Tests
# =============================================================================


class TestGraphStructureValidation:
    """Tests for graph structure validation."""

    def test_validate_graph_structure_valid(self):
        """Test validation of valid graph structure."""
        graph = {
            "@context": "https://schema.org",
            "@graph": [{"@type": "Organization"}],
        }
        issues = _validate_graph_structure(graph)
        assert len(issues) == 0

    def test_validate_graph_structure_missing_context(self):
        """Test validation with missing @context."""
        graph = {"@graph": [{"@type": "Organization"}]}
        issues = _validate_graph_structure(graph)
        assert any("@context" in issue for issue in issues)

    def test_validate_graph_structure_invalid_context(self):
        """Test validation with invalid @context."""
        graph = {
            "@context": "https://invalid.org",
            "@graph": [{"@type": "Organization"}],
        }
        issues = _validate_graph_structure(graph)
        assert any("Invalid @context" in issue for issue in issues)

    def test_validate_graph_structure_empty_graph(self):
        """Test validation with empty @graph array."""
        graph = {"@context": "https://schema.org", "@graph": []}
        issues = _validate_graph_structure(graph)
        assert any("no entities" in issue for issue in issues)

    def test_validate_graph_structure_single_entity(self):
        """Test validation with single entity (no @graph)."""
        graph = {"@context": "https://schema.org", "@type": "Organization"}
        issues = _validate_graph_structure(graph)
        assert len(issues) == 0


# =============================================================================
# Output Generation Tests
# =============================================================================


class TestOutputGeneration:
    """Tests for output generation functions."""

    def test_generate_enhanced_graph(self, simple_organization_graph: List[Dict[str, Any]]):
        """Test generating enhanced graph with suggestions."""
        enhancements = [
            EntityEnhancement(
                entity_id="https://example.com#organization",
                entity_type="Organization",
                existing_properties=["name", "url"],
                suggested_properties=[
                    PropertyEnhancement(
                        property_name="logo",
                        expected_types=["URL"],
                        priority=EnhancementPriority.HIGH,
                        reason="Branding",
                        example_value="https://example.com/logo.png",
                    )
                ],
            )
        ]
        missing = [
            MissingEntitySuggestion(
                entity_type="FAQPage",
                priority=EnhancementPriority.HIGH,
                reason="Enable FAQ",
                example={"@type": "FAQPage", "mainEntity": []},
            )
        ]

        result = _generate_enhanced_graph(simple_organization_graph, enhancements, missing)

        assert "@context" in result
        assert "@graph" in result
        assert len(result["@graph"]) == 2  # Original + FAQPage

        # Check logo was added
        org = result["@graph"][0]
        assert "logo" in org
        assert org["logo"] == "https://example.com/logo.png"

    def test_generate_diff(self, simple_organization_graph: List[Dict[str, Any]]):
        """Test generating diff output."""
        enhancements = [
            EntityEnhancement(
                entity_id="https://example.com#organization",
                entity_type="Organization",
                existing_properties=["name", "url"],
                suggested_properties=[
                    PropertyEnhancement(
                        property_name="logo",
                        expected_types=["URL"],
                        priority=EnhancementPriority.HIGH,
                        reason="Branding",
                        example_value="https://example.com/logo.png",
                    )
                ],
            )
        ]
        missing = [
            MissingEntitySuggestion(
                entity_type="FAQPage",
                priority=EnhancementPriority.HIGH,
                reason="Enable FAQ",
                example={"@type": "FAQPage"},
            )
        ]

        diff = _generate_diff(simple_organization_graph, enhancements, missing)

        assert "property_additions" in diff
        assert "new_entities" in diff
        assert "summary" in diff

        assert diff["summary"]["properties_to_add"] == 1
        assert diff["summary"]["entities_to_add"] == 1

        # Check property additions
        assert "https://example.com#organization" in diff["property_additions"]
        assert "logo" in diff["property_additions"]["https://example.com#organization"]

    def test_generate_diff_no_changes(self, simple_organization_graph: List[Dict[str, Any]]):
        """Test diff with no changes needed."""
        diff = _generate_diff(simple_organization_graph, [], [])

        assert diff["summary"]["properties_to_add"] == 0
        assert diff["summary"]["entities_to_add"] == 0
        assert len(diff["property_additions"]) == 0
        assert len(diff["new_entities"]) == 0


# =============================================================================
# Integration Tests (Mocked)
# =============================================================================


class TestIntegration:
    """Integration tests with mocked Schema.org client."""

    @pytest.mark.asyncio
    async def test_analyze_entity_graph_error_captures_sentry(self):
        """Test that analyze_entity_graph calls sentry_sdk.capture_exception on error."""
        from ast_grep_mcp.features.schema.enhancement_service import (
            analyze_entity_graph,
        )

        with (
            patch("ast_grep_mcp.features.schema.enhancement_service._load_graph_from_source") as mock_load,
            patch("ast_grep_mcp.features.schema.enhancement_service.sentry_sdk.capture_exception") as mock_capture,
        ):
            mock_load.side_effect = RuntimeError("kaboom")
            with pytest.raises(RuntimeError, match="kaboom"):
                await analyze_entity_graph(input_source="/bad", input_type="file")
            mock_capture.assert_called_once()
            exc_arg = mock_capture.call_args[0][0]
            assert isinstance(exc_arg, RuntimeError)
            extras = mock_capture.call_args[1]["extras"]
            assert extras["input_source"] == "/bad"
            assert extras["input_type"] == "file"

    @pytest.mark.asyncio
    async def test_analyze_entity_graph_simple(self):
        """Test full analysis flow with simple organization."""
        from ast_grep_mcp.features.schema.enhancement_service import (
            analyze_entity_graph,
        )

        # Create temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "@context": "https://schema.org",
                    "@graph": [
                        {
                            "@type": "Organization",
                            "@id": "https://example.com#org",
                            "name": "Test Corp",
                        }
                    ],
                },
                f,
            )
            f.flush()

            try:
                # Mock the Schema.org client
                with patch("ast_grep_mcp.features.schema.enhancement_service.get_schema_org_client") as mock_client:
                    client_instance = MagicMock()
                    client_instance.get_type_properties = AsyncMock(return_value=[])
                    mock_client.return_value = client_instance

                    result = await analyze_entity_graph(
                        input_source=f.name,
                        input_type="file",
                        output_mode="analysis",
                    )

                    assert "entity_enhancements" in result
                    assert "missing_entities" in result
                    assert "overall_seo_score" in result
                    assert "priority_summary" in result
                    assert "execution_time_ms" in result

            finally:
                os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_analyze_entity_graph_enhanced_mode(self):
        """Test analysis with enhanced output mode."""
        from ast_grep_mcp.features.schema.enhancement_service import (
            analyze_entity_graph,
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "@context": "https://schema.org",
                    "@graph": [
                        {
                            "@type": "Organization",
                            "@id": "https://example.com#org",
                            "name": "Test",
                        }
                    ],
                },
                f,
            )
            f.flush()

            try:
                with patch("ast_grep_mcp.features.schema.enhancement_service.get_schema_org_client") as mock_client:
                    client_instance = MagicMock()
                    client_instance.get_type_properties = AsyncMock(return_value=[])
                    mock_client.return_value = client_instance

                    result = await analyze_entity_graph(
                        input_source=f.name,
                        input_type="file",
                        output_mode="enhanced",
                    )

                    assert "enhanced_graph" in result
                    assert "@context" in result["enhanced_graph"]
                    assert "@graph" in result["enhanced_graph"]

            finally:
                os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_analyze_entity_graph_diff_mode(self):
        """Test analysis with diff output mode."""
        from ast_grep_mcp.features.schema.enhancement_service import (
            analyze_entity_graph,
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "@context": "https://schema.org",
                    "@graph": [
                        {
                            "@type": "Organization",
                            "@id": "https://example.com#org",
                            "name": "Test",
                        }
                    ],
                },
                f,
            )
            f.flush()

            try:
                with patch("ast_grep_mcp.features.schema.enhancement_service.get_schema_org_client") as mock_client:
                    client_instance = MagicMock()
                    client_instance.get_type_properties = AsyncMock(return_value=[])
                    mock_client.return_value = client_instance

                    result = await analyze_entity_graph(
                        input_source=f.name,
                        input_type="file",
                        output_mode="diff",
                    )

                    assert "diff" in result
                    assert "property_additions" in result["diff"]
                    assert "new_entities" in result["diff"]
                    assert "summary" in result["diff"]

            finally:
                os.unlink(f.name)
