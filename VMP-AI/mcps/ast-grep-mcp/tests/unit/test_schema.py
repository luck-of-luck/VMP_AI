"""Tests for Schema.org client and tools.

Migrated to pytest fixtures on 2025-11-26.
Fixtures used: schema_client (function-scoped), reset_schema_client (autouse)
"""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from ast_grep_mcp.features.schema.client import (
    SchemaOrgClient,
    get_schema_org_client,
)

# Mock Schema.org data for testing
MOCK_SCHEMA_DATA = {
    "@context": {"@vocab": "https://schema.org/"},
    "@graph": [
        {"@id": "schema:Thing", "@type": "rdfs:Class", "rdfs:label": "Thing", "rdfs:comment": "The most generic type of item."},
        {
            "@id": "schema:Person",
            "@type": "rdfs:Class",
            "rdfs:label": "Person",
            "rdfs:comment": "A person (alive, dead, undead, or fictional).",
            "rdfs:subClassOf": {"@id": "schema:Thing"},
        },
        {
            "@id": "schema:Organization",
            "@type": "rdfs:Class",
            "rdfs:label": "Organization",
            "rdfs:comment": "An organization such as a school, NGO, corporation, club, etc.",
            "rdfs:subClassOf": {"@id": "schema:Thing"},
        },
        {
            "@id": "schema:Article",
            "@type": "rdfs:Class",
            "rdfs:label": "Article",
            "rdfs:comment": "An article, such as a news article or piece of investigative report.",
            "rdfs:subClassOf": {"@id": "schema:CreativeWork"},
        },
        {
            "@id": "schema:CreativeWork",
            "@type": "rdfs:Class",
            "rdfs:label": "CreativeWork",
            "rdfs:comment": "The most generic kind of creative work.",
            "rdfs:subClassOf": {"@id": "schema:Thing"},
        },
        {
            "@id": "schema:name",
            "@type": "rdf:Property",
            "rdfs:label": "name",
            "rdfs:comment": "The name of the item.",
            "schema:domainIncludes": {"@id": "schema:Thing"},
            "schema:rangeIncludes": {"@id": "schema:Text"},
        },
        {
            "@id": "schema:description",
            "@type": "rdf:Property",
            "rdfs:label": "description",
            "rdfs:comment": "A description of the item.",
            "schema:domainIncludes": {"@id": "schema:Thing"},
            "schema:rangeIncludes": {"@id": "schema:Text"},
        },
        {
            "@id": "schema:url",
            "@type": "rdf:Property",
            "rdfs:label": "url",
            "rdfs:comment": "URL of the item.",
            "schema:domainIncludes": {"@id": "schema:Thing"},
            "schema:rangeIncludes": {"@id": "schema:URL"},
        },
        {
            "@id": "schema:email",
            "@type": "rdf:Property",
            "rdfs:label": "email",
            "rdfs:comment": "Email address.",
            "schema:domainIncludes": [{"@id": "schema:Person"}, {"@id": "schema:Organization"}],
            "schema:rangeIncludes": {"@id": "schema:Text"},
        },
        {
            "@id": "schema:author",
            "@type": "rdf:Property",
            "rdfs:label": "author",
            "rdfs:comment": "The author of this content.",
            "schema:domainIncludes": {"@id": "schema:CreativeWork"},
            "schema:rangeIncludes": [{"@id": "schema:Person"}, {"@id": "schema:Organization"}],
        },
        {"@id": "schema:Text", "@type": "rdfs:Class", "rdfs:label": "Text"},
        {"@id": "schema:URL", "@type": "rdfs:Class", "rdfs:label": "URL"},
        {"@id": "schema:Date", "@type": "rdfs:Class", "rdfs:label": "Date"},
        {"@id": "schema:DateTime", "@type": "rdfs:Class", "rdfs:label": "DateTime"},
        {"@id": "schema:Number", "@type": "rdfs:Class", "rdfs:label": "Number"},
        {"@id": "schema:Boolean", "@type": "rdfs:Class", "rdfs:label": "Boolean"},
        {"@id": "schema:ImageObject", "@type": "rdfs:Class", "rdfs:label": "ImageObject", "rdfs:subClassOf": {"@id": "schema:MediaObject"}},
    ],
}


class TestSchemaOrgClient:
    """Tests for SchemaOrgClient class."""

    @pytest.mark.asyncio
    async def test_initialization_success(self, schema_client) -> None:
        """Test successful initialization with schema data."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await schema_client.initialize()

            assert schema_client.initialized is True
            assert len(schema_client.schema_data) > 0
            # Check that both @id and label indexing works
            assert "schema:Person" in schema_client.schema_data
            assert schema_client.schema_data["schema:Person"]["rdfs:label"] == "Person"

    @pytest.mark.asyncio
    async def test_initialization_no_graph(self, schema_client) -> None:
        """Test initialization fails when @graph is missing."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = {"@context": {}}  # No @graph
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError, match="Invalid schema.org data format"):
                await schema_client.initialize()

    @pytest.mark.asyncio
    async def test_initialization_empty_data(self, schema_client) -> None:
        """Test initialization fails with empty data."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = None
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError, match="No data received"):
                await schema_client.initialize()

    @pytest.mark.asyncio
    async def test_initialization_http_error(self, schema_client) -> None:
        """Test initialization handles HTTP errors."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.HTTPError("Connection failed")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(RuntimeError, match="Failed to initialize"):
                await schema_client.initialize()

            assert schema_client.initialized is False

    @pytest.mark.asyncio
    async def test_initialization_idempotent(self, schema_client) -> None:
        """Test that initialize() can be called multiple times safely."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            await schema_client.initialize()
            first_call_count = mock_client.get.call_count

            # Second call should not fetch data again
            await schema_client.initialize()
            assert mock_client.get.call_count == first_call_count  # No additional call

    def test_normalize_to_array(self, schema_client) -> None:
        """Test _normalize_to_array helper."""
        # Single value
        assert schema_client._normalize_to_array("value") == ["value"]

        # List
        assert schema_client._normalize_to_array(["a", "b"]) == ["a", "b"]

        # None/empty
        assert schema_client._normalize_to_array(None) == []
        assert schema_client._normalize_to_array("") == []
        assert schema_client._normalize_to_array([]) == []

    @pytest.mark.asyncio
    async def test_get_schema_type_success(self, schema_client) -> None:
        """Test getting type information."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await schema_client.get_schema_type("Person")

            assert result["name"] == "Person"
            assert result["description"] == "A person (alive, dead, undead, or fictional)."
            assert result["id"] == "schema:Person"
            assert result["url"] == "https://schema.org/Person"
            assert len(result["superTypes"]) == 1
            assert result["superTypes"][0]["name"] == "Thing"

    @pytest.mark.asyncio
    async def test_get_schema_type_not_found(self, schema_client) -> None:
        """Test getting non-existent type."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            with pytest.raises(ValueError, match="Type 'NonExistent' not found"):
                await schema_client.get_schema_type("NonExistent")

    @pytest.mark.asyncio
    async def test_get_schema_type_invalid_input(self, schema_client) -> None:
        """Test get_schema_type with invalid inputs."""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            await schema_client.get_schema_type("")

        with pytest.raises(ValueError, match="must be a non-empty string"):
            await schema_client.get_schema_type(None)  # type: ignore

    @pytest.mark.asyncio
    async def test_search_schemas_by_label(self, schema_client) -> None:
        """Test searching for schemas by label."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            results = await schema_client.search_schemas("person")

            assert len(results) >= 1
            assert any(r["name"] == "Person" for r in results)

    @pytest.mark.asyncio
    async def test_search_schemas_by_description(self, schema_client) -> None:
        """Test searching schemas by description text."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            results = await schema_client.search_schemas("organization")

            assert len(results) >= 1
            assert any(r["name"] == "Organization" for r in results)

    @pytest.mark.asyncio
    async def test_search_schemas_limit(self, schema_client) -> None:
        """Test search result limiting."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            results = await schema_client.search_schemas("thing", limit=2)

            assert len(results) <= 2

    @pytest.mark.asyncio
    async def test_search_schemas_invalid_query(self, schema_client) -> None:
        """Test search with invalid queries."""
        with pytest.raises(ValueError, match="Query must be a non-empty string"):
            await schema_client.search_schemas("")

        with pytest.raises(ValueError, match="Query cannot be empty"):
            await schema_client.search_schemas("   ")

    @pytest.mark.asyncio
    async def test_get_type_hierarchy(self, schema_client) -> None:
        """Test getting type hierarchy."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await schema_client.get_type_hierarchy("Person")

            assert result["name"] == "Person"
            assert result["id"] == "schema:Person"
            assert len(result["parents"]) == 1
            assert result["parents"][0]["name"] == "Thing"
            assert "children" in result

    @pytest.mark.asyncio
    async def test_get_type_properties_direct(self, schema_client) -> None:
        """Test getting direct properties of a type."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await schema_client.get_type_properties("Person", include_inherited=False)

            # Should have direct property 'email'
            assert any(p["name"] == "email" for p in result)
            # Should not have 'inheritedFrom' key
            for prop in result:
                assert "inheritedFrom" not in prop or prop.get("inheritedFrom") is None

    @pytest.mark.asyncio
    async def test_get_type_properties_inherited(self, schema_client) -> None:
        """Test getting inherited properties."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await schema_client.get_type_properties("Person", include_inherited=True)

            # Should include properties from Thing (name, description, url)
            prop_names = [p["name"] for p in result]
            assert "name" in prop_names  # From Thing
            assert "description" in prop_names  # From Thing
            assert "email" in prop_names  # Direct property

            # Check for inheritedFrom marker
            inherited_props = [p for p in result if "inheritedFrom" in p]
            assert len(inherited_props) > 0

    @pytest.mark.asyncio
    async def test_generate_example(self, schema_client) -> None:
        """Test generating example JSON-LD."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            result = await schema_client.generate_example("Person")

            assert result["@context"] == "https://schema.org"
            assert result["@type"] == "Person"
            # Should have some common properties
            assert "@type" in result

    @pytest.mark.asyncio
    async def test_generate_example_with_custom_props(self, schema_client) -> None:
        """Test generating example with custom properties."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            custom = {"jobTitle": "Software Engineer", "worksFor": "Example Corp"}
            result = await schema_client.generate_example("Person", custom_properties=custom)

            assert result["@type"] == "Person"
            assert result["jobTitle"] == "Software Engineer"
            assert result["worksFor"] == "Example Corp"

    def test_generate_example_value_text(self, schema_client) -> None:
        """Test example value generation for Text type."""
        prop = {"name": "description", "expectedTypes": ["Text"]}
        value = schema_client._generate_example_value(prop)
        assert isinstance(value, str)
        assert "description" in value.lower()

    def test_generate_example_value_url(self, schema_client) -> None:
        """Test example value generation for URL type."""
        prop = {"name": "url", "expectedTypes": ["URL"]}
        value = schema_client._generate_example_value(prop)
        assert value == "https://example.com"

    def test_generate_example_value_date(self, schema_client) -> None:
        """Test example value generation for Date type."""
        prop = {"name": "datePublished", "expectedTypes": ["Date"]}
        value = schema_client._generate_example_value(prop)
        assert value == "2024-01-01"

    def test_generate_example_value_datetime(self, schema_client) -> None:
        """Test example value generation for DateTime type."""
        prop = {"name": "startTime", "expectedTypes": ["DateTime"]}
        value = schema_client._generate_example_value(prop)
        assert value == "2024-01-01T12:00:00Z"

    def test_generate_example_value_number(self, schema_client) -> None:
        """Test example value generation for Number type."""
        prop = {"name": "price", "expectedTypes": ["Number"]}
        value = schema_client._generate_example_value(prop)
        assert value == 42

    def test_generate_example_value_boolean(self, schema_client) -> None:
        """Test example value generation for Boolean type."""
        prop = {"name": "isAccessibleForFree", "expectedTypes": ["Boolean"]}
        value = schema_client._generate_example_value(prop)
        assert value is True

    def test_generate_example_value_image_object(self, schema_client) -> None:
        """Test example value generation for ImageObject type."""
        prop = {"name": "image", "expectedTypes": ["ImageObject"]}
        value = schema_client._generate_example_value(prop)
        assert isinstance(value, dict)
        assert value["@type"] == "ImageObject"
        assert "url" in value

    def test_generate_entity_id_simple(self, schema_client) -> None:
        """Test generating simple entity @id."""
        entity_id = schema_client.generate_entity_id("https://example.com", "Organization")
        assert entity_id == "https://example.com#organization"

    def test_generate_entity_id_with_slug(self, schema_client) -> None:
        """Test generating entity @id with slug."""
        entity_id = schema_client.generate_entity_id("https://example.com", "Person", "team/john-doe")
        assert entity_id == "https://example.com/team/john-doe#person"

    def test_generate_entity_id_trailing_slash(self, schema_client) -> None:
        """Test entity @id generation removes trailing slash."""
        entity_id = schema_client.generate_entity_id("https://example.com/", "Product")
        assert entity_id == "https://example.com#product"

    def test_generate_entity_id_slug_leading_slash(self, schema_client) -> None:
        """Test entity @id generation removes leading slash from slug."""
        entity_id = schema_client.generate_entity_id("https://example.com", "Article", "/blog/my-post")
        assert entity_id == "https://example.com/blog/my-post#article"

    def test_validate_entity_id_valid(self, schema_client) -> None:
        """Test validating a properly formatted @id."""
        result = schema_client.validate_entity_id("https://example.com#organization")

        assert result["valid"] is True
        assert result["entity_id"] == "https://example.com#organization"
        assert len(result["warnings"]) == 0
        assert len(result["suggestions"]) == 0

    def test_validate_entity_id_no_protocol(self, schema_client) -> None:
        """Test validation catches missing http/https."""
        result = schema_client.validate_entity_id("example.com/#organization")

        assert result["valid"] is False
        assert any("full URL" in w for w in result["warnings"])

    def test_validate_entity_id_no_hash(self, schema_client) -> None:
        """Test validation catches missing hash fragment."""
        result = schema_client.validate_entity_id("https://example.com/organization")

        assert result["valid"] is False
        assert any("hash fragment" in w for w in result["warnings"])
        assert any("Add a descriptive fragment" in s for s in result["suggestions"])

    def test_validate_entity_id_unstable_components(self, schema_client) -> None:
        """Test validation catches unstable ID patterns."""
        result = schema_client.validate_entity_id("https://example.com/timestamp-123#org")

        assert result["valid"] is False
        assert any("unstable" in w for w in result["warnings"])

    def test_validate_entity_id_numeric_fragment(self, schema_client) -> None:
        """Test validation warns about numeric-only fragments."""
        result = schema_client.validate_entity_id("https://example.com/#123")

        assert result["valid"] is False
        assert any("numeric-only" in w for w in result["warnings"])

    def test_validate_entity_id_query_parameters(self, schema_client) -> None:
        """Test validation catches query parameters."""
        result = schema_client.validate_entity_id("https://example.com/?id=123#org")

        assert result["valid"] is False
        assert any("query parameters" in w for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_build_entity_graph_simple(self, schema_client) -> None:
        """Test building a simple entity graph."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            entities = [{"type": "Organization", "slug": None, "properties": {"name": "Acme Corp"}}]

            result = await schema_client.build_entity_graph(entities, "https://example.com")

            assert result["@context"] == "https://schema.org"
            assert "@graph" in result
            assert len(result["@graph"]) == 1
            assert result["@graph"][0]["@type"] == "Organization"
            assert result["@graph"][0]["name"] == "Acme Corp"
            assert result["@graph"][0]["@id"] == "https://example.com#organization"

    @pytest.mark.asyncio
    async def test_build_entity_graph_with_relationships(self, schema_client) -> None:
        """Test building entity graph with relationships."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            entities = [
                {
                    "type": "Organization",
                    "id_fragment": "org-acme",
                    "properties": {"name": "Acme Corp"},
                    "relationships": {"founder": "person-john"},
                },
                {"type": "Person", "slug": "team/john", "id_fragment": "person-john", "properties": {"name": "John Doe"}},
            ]

            result = await schema_client.build_entity_graph(entities, "https://example.com")

            assert len(result["@graph"]) == 2

            # Find organization entity
            org = [e for e in result["@graph"] if e["@type"] == "Organization"][0]
            person = [e for e in result["@graph"] if e["@type"] == "Person"][0]

            # Check relationship uses @id reference
            assert "founder" in org
            assert org["founder"] == {"@id": person["@id"]}

    @pytest.mark.asyncio
    async def test_build_entity_graph_with_slug(self, schema_client) -> None:
        """Test entity graph includes URL for entities with slugs."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            entities = [{"type": "Article", "slug": "blog/my-post", "properties": {"name": "My Article"}}]

            result = await schema_client.build_entity_graph(entities, "https://example.com")

            article = result["@graph"][0]
            assert article["url"] == "https://example.com/blog/my-post"

    @pytest.mark.asyncio
    async def test_build_entity_graph_dict_relationship_target(self, schema_client) -> None:
        """Test that dict relationship targets pass through without unhashable type error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            entities = [
                {
                    "type": "Organization",
                    "id_fragment": "org-acme",
                    "properties": {"name": "Acme Corp"},
                    "relationships": {
                        "founder": {"@id": "https://example.com/#person-john"},
                    },
                },
            ]

            result = await schema_client.build_entity_graph(entities, "https://example.com")

            org = result["@graph"][0]
            assert org["founder"] == {"@id": "https://example.com/#person-john"}

    @pytest.mark.asyncio
    async def test_build_entity_graph_list_with_dict_relationship_targets(self, schema_client) -> None:
        """Test that list relationship targets containing dicts don't raise unhashable type error."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            entities = [
                {
                    "type": "Organization",
                    "id_fragment": "org-acme",
                    "properties": {"name": "Acme Corp"},
                    "relationships": {
                        "member": [
                            {"@id": "https://example.com/#person-john"},
                            "person-jane",
                        ],
                    },
                },
                {
                    "type": "Person",
                    "id_fragment": "person-jane",
                    "properties": {"name": "Jane Doe"},
                },
            ]

            result = await schema_client.build_entity_graph(entities, "https://example.com")

            org = [e for e in result["@graph"] if e["@type"] == "Organization"][0]
            jane = [e for e in result["@graph"] if e["@type"] == "Person"][0]

            # Dict target passes through, string target resolves to @id ref
            assert org["member"][0] == {"@id": "https://example.com/#person-john"}
            assert org["member"][1] == {"@id": jane["@id"]}


class TestSchemaOrgTools:
    """Tests for Schema.org MCP tools."""

    @pytest.mark.asyncio
    async def test_get_schema_type_tool(self) -> None:
        """Test get_schema_type MCP tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            # Import tools after patching

            # We need to test the tools through the client
            client = SchemaOrgClient()
            result = await client.get_schema_type("Person")

            assert result["name"] == "Person"
            assert "description" in result

    @pytest.mark.asyncio
    async def test_search_schemas_tool(self) -> None:
        """Test search_schemas MCP tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            client = SchemaOrgClient()
            result = await client.search_schemas("person", limit=5)

            assert isinstance(result, list)
            assert len(result) <= 5

    @pytest.mark.asyncio
    async def test_get_type_hierarchy_tool(self) -> None:
        """Test get_type_hierarchy MCP tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            client = SchemaOrgClient()
            result = await client.get_type_hierarchy("Person")

            assert "parents" in result
            assert "children" in result

    @pytest.mark.asyncio
    async def test_get_type_properties_tool(self) -> None:
        """Test get_type_properties MCP tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            client = SchemaOrgClient()
            result = await client.get_type_properties("Person", include_inherited=True)

            assert isinstance(result, list)
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_generate_schema_example_tool(self) -> None:
        """Test generate_example MCP tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            client = SchemaOrgClient()
            result = await client.generate_example("Organization")

            assert result["@context"] == "https://schema.org"
            assert result["@type"] == "Organization"

    def test_generate_entity_id_tool(self) -> None:
        """Test generate_entity_id tool (non-async)."""
        client = SchemaOrgClient()
        result = client.generate_entity_id("https://example.com", "Organization")

        assert result == "https://example.com#organization"

    def test_validate_entity_id_tool(self) -> None:
        """Test validate_entity_id tool (non-async)."""
        client = SchemaOrgClient()
        result = client.validate_entity_id("https://example.com#organization")

        assert result["valid"] is True
        assert "warnings" in result
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_build_entity_graph_tool(self) -> None:
        """Test build_entity_graph MCP tool."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = Mock()
            mock_response.json.return_value = MOCK_SCHEMA_DATA
            mock_response.raise_for_status = Mock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            client = SchemaOrgClient()
            entities = [{"type": "Organization", "properties": {"name": "Test"}}]
            result = await client.build_entity_graph(entities, "https://example.com")

            assert "@graph" in result
            assert len(result["@graph"]) == 1


class TestSchemaOrgClientHelpers:
    """Tests for SchemaOrgClient helper methods."""

    def test_extract_super_types(self, schema_client) -> None:
        """Test extracting super types from type data."""
        type_data = {"@id": "schema:Person", "rdfs:subClassOf": {"@id": "schema:Thing"}}

        result = schema_client._extract_super_types(type_data)

        assert len(result) == 1
        assert result[0]["name"] == "Thing"
        assert result[0]["id"] == "schema:Thing"

    def test_extract_super_types_multiple(self, schema_client) -> None:
        """Test extracting multiple super types."""
        type_data = {"@id": "schema:Test", "rdfs:subClassOf": [{"@id": "schema:Thing"}, {"@id": "schema:Person"}]}

        result = schema_client._extract_super_types(type_data)

        assert len(result) == 2

    def test_find_sub_types(self, schema_client) -> None:
        """Test finding subtypes of a type."""
        # Populate base schema data
        schema_client.schema_data = {
            "schema:Person": {
                "@id": "schema:Person",
                "@type": "rdfs:Class",
                "rdfs:label": "Person",
                "rdfs:subClassOf": {"@id": "schema:Thing"},
            },
            "schema:Thing": {"@id": "schema:Thing", "@type": "rdfs:Class", "rdfs:label": "Thing"},
        }
        # Add a subtype to test data
        schema_client.schema_data["schema:Student"] = {
            "@id": "schema:Student",
            "@type": "rdfs:Class",
            "rdfs:label": "Student",
            "rdfs:subClassOf": {"@id": "schema:Person"},
        }

        result = schema_client._find_sub_types("schema:Person")

        assert len(result) >= 1
        assert any(st["name"] == "Student" for st in result)

    def test_format_property(self, schema_client) -> None:
        """Test formatting a property for output."""
        prop_data = {
            "@id": "schema:name",
            "@type": "rdf:Property",
            "rdfs:label": "name",
            "rdfs:comment": "The name of the item",
            "schema:rangeIncludes": {"@id": "schema:Text"},
        }

        # Add Text type to schema_data
        schema_client.schema_data["schema:Text"] = {"@id": "schema:Text", "rdfs:label": "Text"}

        result = schema_client._format_property(prop_data)

        assert result["name"] == "name"
        assert result["description"] == "The name of the item"
        assert result["id"] == "schema:name"
        assert "Text" in result["expectedTypes"]


class TestGetSchemaOrgClient:
    """Tests for get_schema_org_client singleton."""

    def test_get_schema_org_client_singleton(self) -> None:
        """Test that get_schema_org_client returns singleton."""
        client1 = get_schema_org_client()
        client2 = get_schema_org_client()

        assert client1 is client2

    def test_get_schema_org_client_creates_instance(self) -> None:
        """Test that get_schema_org_client creates new instance if None."""
        client = get_schema_org_client()

        assert client is not None
        assert isinstance(client, SchemaOrgClient)
