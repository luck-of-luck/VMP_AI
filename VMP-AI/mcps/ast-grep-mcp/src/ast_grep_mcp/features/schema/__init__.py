"""Schema.org feature - structured data and knowledge graph functionality."""

from ast_grep_mcp.features.schema.client import (
    SchemaOrgClient,
    get_schema_org_client,
)
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
from ast_grep_mcp.features.schema.tools import register_schema_tools

__all__ = [
    # Client
    "SchemaOrgClient",
    "get_schema_org_client",
    # HTML detection
    "detect_jsonld_in_html",
    "detect_microdata_in_html",
    "detect_rdfa_in_html",
    "validate_html_structured_data",
    # Markdown detection
    "extract_schema_from_frontmatter",
    "suggest_frontmatter_enhancements",
    "validate_frontmatter_schema",
    # Registration
    "register_schema_tools",
]
