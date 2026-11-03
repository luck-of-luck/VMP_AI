"""Schema.org feature MCP tool definitions."""

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.features.schema.client import get_schema_org_client
from ast_grep_mcp.features.schema.enhancement_service import analyze_entity_graph
from ast_grep_mcp.features.schema.html_service import (
    detect_jsonld_in_html,
    detect_microdata_in_html,
    detect_rdfa_in_html,
    validate_html_structured_data,
)
from ast_grep_mcp.features.schema.markdown_service import (
    extract_schema_from_frontmatter,
    suggest_frontmatter_enhancements,
    validate_frontmatter_schema,
)
from ast_grep_mcp.utils.tool_context import async_tool_context, tool_context


async def get_schema_type_tool(type_name: str) -> Dict[str, Any]:
    """
    Get detailed information about a schema.org type.
    Returns the type's name, description, URL, parent types, and metadata.

    Args:
        type_name: The schema.org type name (e.g., 'Person', 'Organization', 'Article')

    Returns:
        Dictionary with type details including properties and parent types

    Example:
        get_schema_type_tool('Person') returns details about the Person type
    """
    logger = get_logger("tool.get_schema_type")
    logger.info("tool_invoked", tool="get_schema_type", type_name=type_name)
    async with async_tool_context("get_schema_type", type_name=type_name):
        return await get_schema_org_client().get_schema_type(type_name)


async def search_schemas_tool(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for schema.org types by keyword.
    Searches through type names and descriptions, returns matching types sorted by relevance.

    Args:
        query: Search query to find schema types
        limit: Maximum number of results to return (1-100)

    Returns:
        List of matching schema types

    Example:
        search_schemas_tool('blog') finds types like BlogPosting, Blog, etc.
    """
    logger = get_logger("tool.search_schemas")
    logger.info("tool_invoked", tool="search_schemas", query=query, limit=limit)
    async with async_tool_context("search_schemas", query=query, limit=limit) as run:
        results = await get_schema_org_client().search_schemas(query, limit)
        run.add_completion_fields(result_count=len(results))
        return results


async def get_type_hierarchy_tool(type_name: str) -> Dict[str, Any]:
    """
    Get the inheritance hierarchy for a schema.org type.
    Returns the type's parent types (super types) and child types (sub types).

    Args:
        type_name: The schema.org type name

    Returns:
        Dictionary with parent and child type information

    Example:
        get_type_hierarchy_tool('NewsArticle') shows inheritance from Article, CreativeWork, etc.
    """
    logger = get_logger("tool.get_type_hierarchy")
    logger.info("tool_invoked", tool="get_type_hierarchy", type_name=type_name)
    async with async_tool_context("get_type_hierarchy", type_name=type_name):
        return await get_schema_org_client().get_type_hierarchy(type_name)


async def get_type_properties_tool(type_name: str, include_inherited: bool = True) -> List[Dict[str, Any]]:
    """
    Get all properties available for a schema.org type.
    Returns property names, descriptions, and expected value types.

    Args:
        type_name: The schema.org type name
        include_inherited: Include properties inherited from parent types

    Returns:
        List of property definitions

    Example:
        get_type_properties_tool('Organization') returns properties like name, url, address, etc.
    """
    logger = get_logger("tool.get_type_properties")
    logger.info("tool_invoked", tool="get_type_properties", type_name=type_name, include_inherited=include_inherited)
    async with async_tool_context("get_type_properties", type_name=type_name, include_inherited=include_inherited) as run:
        results = await get_schema_org_client().get_type_properties(type_name, include_inherited)
        run.add_completion_fields(property_count=len(results))
        return results


async def generate_schema_example_tool(type_name: str, custom_properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Generate an example JSON-LD structured data for a schema.org type.
    Creates a valid schema.org JSON-LD object with common properties and any custom values provided.

    Args:
        type_name: The schema.org type name
        custom_properties: Custom property values to include in the example

    Returns:
        Dictionary containing JSON-LD example

    Example:
        generate_schema_example_tool('Recipe', {'name': 'Chocolate Cake', 'prepTime': 'PT30M'})
    """
    logger = get_logger("tool.generate_schema_example")
    logger.info("tool_invoked", tool="generate_schema_example", type_name=type_name)
    async with async_tool_context("generate_schema_example", type_name=type_name):
        return await get_schema_org_client().generate_example(type_name, custom_properties)


def generate_entity_id_tool(base_url: str, entity_type: str, entity_slug: Optional[str] = None) -> str:
    """
    Generate a proper @id value following Schema.org and SEO best practices.

    Creates stable, unique identifiers for entities that can be referenced across your knowledge graph.
    Based on best practices from https://momenticmarketing.com/blog/id-schema-for-seo-llms-knowledge-graphs

    Args:
        base_url: The canonical URL (e.g., 'https://example.com')
        entity_type: The Schema.org type (e.g., 'Organization', 'Person')
        entity_slug: Optional URL slug for specific entity instances

    Returns:
        Generated @id string

    Examples:
        - generate_entity_id_tool('https://example.com', 'Organization')
          → 'https://example.com/#organization'
        - generate_entity_id_tool('https://example.com', 'Product', 'products/widget-a')
          → 'https://example.com/products/widget-a#product'
    """
    logger = get_logger("tool.generate_entity_id")
    logger.info("tool_invoked", tool="generate_entity_id", base_url=base_url, entity_type=entity_type)
    with tool_context("generate_entity_id", base_url=base_url, entity_type=entity_type) as run:
        result = get_schema_org_client().generate_entity_id(base_url, entity_type, entity_slug)
        run.add_completion_fields(generated_id=result)
        return result


def validate_entity_id_tool(entity_id: str) -> Dict[str, Any]:
    """
    Validate an @id value against Schema.org and SEO best practices.

    Checks for common issues and provides actionable suggestions for improvement.
    Based on best practices from https://momenticmarketing.com/blog/id-schema-for-seo-llms-knowledge-graphs

    Args:
        entity_id: The @id value to validate

    Returns:
        Dictionary with validation results:
        - valid: Whether the @id follows all best practices
        - warnings: List of issues found
        - suggestions: Specific improvements to make
        - best_practices: Key principles to follow

    Example:
        validate_entity_id_tool('https://example.com/#organization')
        → { "valid": true, "warnings": [], "suggestions": [] }
    """
    logger = get_logger("tool.validate_entity_id")
    logger.info("tool_invoked", tool="validate_entity_id", entity_id=entity_id)
    with tool_context("validate_entity_id", entity_id=entity_id) as run:
        result = get_schema_org_client().validate_entity_id(entity_id)
        run.add_completion_fields(is_valid=result["valid"], warning_count=len(result["warnings"]))
        return result


async def build_entity_graph_tool(entities: List[Dict[str, Any]], base_url: str) -> Dict[str, Any]:
    """
    Build a knowledge graph of related entities with proper @id references.

    Args:
        entities: List of entity definitions (type, slug, id_fragment, properties, relationships)
        base_url: Base canonical URL for generating @id values

    Returns:
        Complete JSON-LD @graph with all entities properly connected via @id references
    """
    logger = get_logger("tool.build_entity_graph")
    logger.info("tool_invoked", tool="build_entity_graph", entity_count=len(entities), base_url=base_url)
    async with async_tool_context("build_entity_graph", entity_count=len(entities), base_url=base_url) as run:
        result = await get_schema_org_client().build_entity_graph(entities, base_url)
        run.add_completion_fields(entity_count=len(result.get("@graph", [])))
        return result


async def enhance_entity_graph_tool(input_source: str, input_type: str = "file", output_mode: str = "analysis") -> Dict[str, Any]:
    """
    Analyze existing Schema.org JSON-LD graphs and suggest enhancements.

    Args:
        input_source: File path or directory path containing JSON-LD Schema.org markup
        input_type: 'file' (single file) or 'directory' (scan all .json files)
        output_mode: 'analysis' (suggestions), 'enhanced' (complete graph), 'diff' (additions only)

    Returns:
        Entity-level analysis: missing properties, missing types, SEO scores, validation issues
    """
    logger = get_logger("tool.enhance_entity_graph")
    logger.info("tool_invoked", tool="enhance_entity_graph", input_source=input_source, input_type=input_type, output_mode=output_mode)
    async with async_tool_context(
        "enhance_entity_graph", input_source=input_source, input_type=input_type, output_mode=output_mode
    ) as run:
        result = await analyze_entity_graph(input_source=input_source, input_type=input_type, output_mode=output_mode)
        run.add_completion_fields(
            entity_count=len(result.get("entity_enhancements", [])),
            seo_score=result.get("overall_seo_score", 0),
        )
        return result


def _reg_get_search(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_schema_type(
        type_name: str = Field(description="The schema.org type name (e.g., 'Person', 'Organization', 'Article')"),
    ) -> Dict[str, Any]:
        """Look up a Schema.org type definition with its properties and parent types."""
        return await get_schema_type_tool(type_name=type_name)

    @mcp.tool()
    async def search_schemas(
        query: str = Field(description="Search query to find schema types (searches in names and descriptions)"),
        limit: int = Field(default=10, description="Maximum number of results to return (1-100)"),
    ) -> List[Dict[str, Any]]:
        """Search Schema.org vocabulary by keyword, returning matching types sorted by relevance."""
        return await search_schemas_tool(query=query, limit=limit)


def _reg_hierarchy_properties(mcp: FastMCP) -> None:
    @mcp.tool()
    async def get_type_hierarchy(type_name: str = Field(description="The schema.org type name")) -> Dict[str, Any]:
        """Get parent (superTypes) and child (subTypes) types for a Schema.org type."""
        return await get_type_hierarchy_tool(type_name=type_name)

    @mcp.tool()
    async def get_type_properties(
        type_name: str = Field(description="The schema.org type name"),
        include_inherited: bool = Field(default=True, description="Include properties inherited from parent types"),
    ) -> List[Dict[str, Any]]:
        """List all properties for a Schema.org type, optionally including inherited ones."""
        return await get_type_properties_tool(type_name=type_name, include_inherited=include_inherited)


def _reg_example_entity_id(mcp: FastMCP) -> None:
    @mcp.tool()
    async def generate_schema_example(
        type_name: str = Field(description="The schema.org type name"),
        custom_properties: Optional[Dict[str, Any]] = Field(
            default=None, description="Custom property values to include in the example (JSON object)"
        ),
    ) -> Dict[str, Any]:
        """Generate a valid JSON-LD example for a Schema.org type with optional custom properties."""
        return await generate_schema_example_tool(type_name=type_name, custom_properties=custom_properties)

    @mcp.tool()
    def generate_entity_id(
        base_url: str = Field(description="The canonical URL (e.g., 'https://example.com' or 'https://example.com/page')"),
        entity_type: str = Field(description="The Schema.org type (e.g., 'Organization', 'Person', 'Product')"),
        entity_slug: Optional[str] = Field(
            default=None, description="Optional URL slug for specific entity instances (e.g., 'john-doe', 'products/widget-a')"
        ),
    ) -> str:
        """Generate a Schema.org @id value following SEO best practices for entity identification."""
        return generate_entity_id_tool(base_url=base_url, entity_type=entity_type, entity_slug=entity_slug)


def _reg_validate_build(mcp: FastMCP) -> None:
    @mcp.tool()
    def validate_entity_id(
        entity_id: str = Field(description="The @id value to validate (e.g., 'https://example.com/#organization')"),
    ) -> Dict[str, Any]:
        """Validate a Schema.org @id value against best practices, returning warnings and suggestions."""
        return validate_entity_id_tool(entity_id=entity_id)

    @mcp.tool()
    async def build_entity_graph(
        entities: List[Dict[str, Any]] = Field(description="List of entity definitions with type, properties, and relationships"),
        base_url: str = Field(description="Base canonical URL for generating @id values"),
    ) -> Dict[str, Any]:
        """Build a complete JSON-LD @graph from entity definitions with proper @id references."""
        return await build_entity_graph_tool(entities=entities, base_url=base_url)


def detect_structured_data_tool(
    project_folder: str,
    file_globs: Optional[List[str]] = None,
    formats: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Detect Schema.org structured data in HTML and markdown files.

    Args:
        project_folder: Project root path
        file_globs: File patterns to scan (default: **/*.html, **/*.md)
        formats: Formats to detect: json-ld, microdata, rdfa, frontmatter (default: all)

    Returns:
        Detection results grouped by format
    """
    logger = get_logger("tool.detect_structured_data")
    logger.info("tool_invoked", tool="detect_structured_data", project_folder=project_folder)
    with tool_context("detect_structured_data", project_folder=project_folder) as run:
        all_formats = {"json-ld", "microdata", "rdfa", "frontmatter"}
        active = set(formats) & all_formats if formats else all_formats

        results: Dict[str, Any] = {}
        if "json-ld" in active:
            results["json_ld"] = detect_jsonld_in_html(project_folder, file_globs)
        if "microdata" in active:
            results["microdata"] = detect_microdata_in_html(project_folder, file_globs)
        if "rdfa" in active:
            results["rdfa"] = detect_rdfa_in_html(project_folder, file_globs)
        if "frontmatter" in active:
            results["frontmatter"] = extract_schema_from_frontmatter(project_folder, file_globs)

        run.add_completion_fields(formats_scanned=list(active))
        return results


def validate_structured_data_tool(
    project_folder: str,
    file_globs: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Validate Schema.org structured data in HTML/markdown against schema.org vocabulary.

    Returns validation errors, warnings, and enhancement suggestions.

    Args:
        project_folder: Project root path
        file_globs: File patterns to scan

    Returns:
        Validation results with errors, warnings, and suggestions
    """
    logger = get_logger("tool.validate_structured_data")
    logger.info("tool_invoked", tool="validate_structured_data", project_folder=project_folder)
    with tool_context("validate_structured_data", project_folder=project_folder):
        html_validation = validate_html_structured_data(project_folder, file_globs)
        md_validation = validate_frontmatter_schema(project_folder, file_globs)
        md_suggestions = suggest_frontmatter_enhancements(project_folder, file_globs)

        return {
            "html": html_validation,
            "markdown": md_validation,
            "suggestions": md_suggestions,
            "summary": {
                "html_issues": html_validation["summary"]["total_issues"],
                "markdown_errors": md_validation["total_errors"],
                "markdown_warnings": md_validation["total_warnings"],
                "enhancement_suggestions": md_suggestions["files_with_suggestions"],
            },
        }


def _reg_enhance(mcp: FastMCP) -> None:
    @mcp.tool()
    async def enhance_entity_graph(
        input_source: str = Field(description="File path or directory path containing JSON-LD Schema.org markup"),
        input_type: str = Field(
            default="file", description="Input source type: 'file' for single file, 'directory' for scanning all .json files"
        ),
        output_mode: str = Field(
            default="analysis",
            description=("Output: 'analysis' for suggestions, 'enhanced' for complete graph, 'diff' for additions only"),
        ),
    ) -> Dict[str, Any]:
        """Analyze a JSON-LD entity graph for missing properties, types, and SEO improvements."""
        return await enhance_entity_graph_tool(input_source=input_source, input_type=input_type, output_mode=output_mode)


def _reg_structured_data(mcp: FastMCP) -> None:
    @mcp.tool()
    def detect_structured_data(
        project_folder: str = Field(description="Project root path"),
        file_globs: Optional[List[str]] = Field(default=None, description="File patterns to scan (default: **/*.html, **/*.md)"),
        formats: Optional[List[str]] = Field(
            default=None,
            description="Formats to detect: json-ld, microdata, rdfa, frontmatter (default: all)",
        ),
    ) -> Dict[str, Any]:
        """Detect structured data (JSON-LD, microdata, RDFa, frontmatter) in a project's HTML and markdown files."""
        return detect_structured_data_tool(project_folder=project_folder, file_globs=file_globs, formats=formats)

    @mcp.tool()
    def validate_structured_data(
        project_folder: str = Field(description="Project root path"),
        file_globs: Optional[List[str]] = Field(default=None, description="File patterns to scan (default: **/*.html, **/*.md)"),
    ) -> Dict[str, Any]:
        """Validate structured data in HTML files, checking JSON-LD, microdata, and RDFa for errors."""
        return validate_structured_data_tool(project_folder=project_folder, file_globs=file_globs)


def register_schema_tools(mcp: FastMCP) -> None:
    """Register Schema.org-related MCP tools.

    Args:
        mcp: FastMCP instance to register tools with
    """
    _reg_get_search(mcp)
    _reg_hierarchy_properties(mcp)
    _reg_example_entity_id(mcp)
    _reg_validate_build(mcp)
    _reg_enhance(mcp)
    _reg_structured_data(mcp)
