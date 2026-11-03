"""MCP tool definitions for documentation generation features.

This module registers MCP tools for:
- generate_docstrings: Auto-generate docstrings/JSDoc
- generate_readme_sections: Generate README sections
- generate_api_docs: Generate API documentation
- generate_changelog: Generate changelog from git commits
- sync_documentation: Keep docs synchronized with code
"""

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ast_grep_mcp.constants import ConversionFactors
from ast_grep_mcp.core.logging import get_logger
from ast_grep_mcp.features.documentation.api_docs_generator import generate_api_docs_impl
from ast_grep_mcp.features.documentation.changelog_generator import generate_changelog_impl
from ast_grep_mcp.features.documentation.docstring_generator import generate_docstrings_impl
from ast_grep_mcp.features.documentation.readme_generator import generate_readme_sections_impl
from ast_grep_mcp.features.documentation.sync_checker import sync_documentation_impl
from ast_grep_mcp.models.documentation import ApiRoute
from ast_grep_mcp.utils.tool_context import tool_context


def _format_docstrings_response(result: Any) -> Dict[str, Any]:
    return {
        "summary": {
            "total_functions": result.total_functions,
            "functions_documented": result.functions_documented,
            "functions_generated": result.functions_generated,
            "functions_skipped": result.functions_skipped,
            "dry_run": result.dry_run,
        },
        "docstrings": [
            {
                "function_name": d.function_name,
                "file_path": d.file_path,
                "line_number": d.line_number,
                "docstring": d.docstring,
                "style": d.style.value,
                "confidence": d.confidence,
            }
            for d in result.docstrings
        ],
        "files_modified": result.files_modified,
        "execution_time_ms": result.execution_time_ms,
    }


def _format_readme_response(result: Any) -> Dict[str, Any]:
    return {
        "project_info": {
            "name": result.project_info.name,
            "version": result.project_info.version,
            "description": result.project_info.description,
            "language": result.project_info.language,
            "package_manager": result.project_info.package_manager,
            "frameworks": result.project_info.frameworks,
            "has_tests": result.project_info.has_tests,
            "has_docs": result.project_info.has_docs,
        },
        "sections": [{"type": s.section_type, "title": s.title, "content": s.content} for s in result.sections],
        "full_readme": result.full_readme,
        "execution_time_ms": result.execution_time_ms,
    }


def _format_changelog_version(v: Any) -> Dict[str, Any]:
    entries_data = {
        change_type.value: [
            {
                "description": e.description,
                "commit_hash": e.commit_hash,
                "scope": e.scope,
                "is_breaking": e.is_breaking,
                "issues": e.issues,
                "prs": e.prs,
            }
            for e in entries
        ]
        for change_type, entries in v.entries.items()
    }
    return {
        "version": v.version,
        "date": v.date,
        "entries": entries_data,
        "is_unreleased": v.is_unreleased,
    }


def _format_sync_doc_coverage(result: Any) -> int | float:
    if result.total_functions > 0:
        return float(round(result.documented_functions / result.total_functions * ConversionFactors.PERCENT_MULTIPLIER, 1))
    return 0


def _format_sync_response(result: Any) -> Dict[str, Any]:
    return {
        "summary": {
            "total_functions": result.total_functions,
            "documented_functions": result.documented_functions,
            "undocumented_functions": result.undocumented_functions,
            "stale_docstrings": result.stale_docstrings,
            "documentation_coverage": _format_sync_doc_coverage(result),
        },
        "issues": [
            {
                "issue_type": i.issue_type,
                "file_path": i.file_path,
                "line_number": i.line_number,
                "function_name": i.function_name,
                "description": i.description,
                "suggested_fix": i.suggested_fix,
                "severity": i.severity,
            }
            for i in result.issues
        ],
        "suggestions": result.suggestions,
        "files_updated": result.files_updated,
        "check_only": result.check_only,
        "execution_time_ms": result.execution_time_ms,
    }


# =============================================================================
# Tool Implementations
# =============================================================================


def generate_docstrings_tool(
    project_folder: str,
    file_pattern: str,
    language: str,
    style: str = "auto",
    overwrite_existing: bool = False,
    dry_run: bool = True,
    skip_private: bool = True,
) -> Dict[str, Any]:
    logger = get_logger("tool.generate_docstrings")
    logger.info(
        "tool_invoked",
        tool="generate_docstrings",
        project_folder=project_folder,
        file_pattern=file_pattern,
        language=language,
        style=style,
        dry_run=dry_run,
    )

    with tool_context("generate_docstrings", project_folder=project_folder, language=language) as run:
        result = generate_docstrings_impl(
            project_folder=project_folder,
            file_pattern=file_pattern,
            language=language,
            style=style,
            overwrite_existing=overwrite_existing,
            dry_run=dry_run,
            skip_private=skip_private,
        )
        run.add_completion_fields(
            total_functions=result.total_functions,
            functions_generated=result.functions_generated,
        )
        return _format_docstrings_response(result)


def generate_readme_sections_tool(
    project_folder: str,
    language: str = "auto",
    sections: List[str] | None = None,
    include_examples: bool = True,
) -> Dict[str, Any]:
    logger = get_logger("tool.generate_readme_sections")

    if sections is None:
        sections = ["all"]

    logger.info(
        "tool_invoked",
        tool="generate_readme_sections",
        project_folder=project_folder,
        language=language,
        sections=sections,
    )

    with tool_context("generate_readme_sections", project_folder=project_folder, language=language) as run:
        result = generate_readme_sections_impl(
            project_folder=project_folder,
            language=language,
            sections=sections,
            include_examples=include_examples,
        )
        run.add_completion_fields(sections_generated=len(result.sections))
        return _format_readme_response(result)


def _format_route_for_output(route: ApiRoute) -> Dict[str, Any]:
    """Format a single route for API output.

    Args:
        route: ApiRoute object

    Returns:
        Dictionary with route details
    """
    return {
        "path": route.path,
        "method": route.method,
        "handler_name": route.handler_name,
        "file_path": route.file_path,
        "line_number": route.line_number,
        "parameters": [{"name": p.name, "location": p.location, "type": p.type_hint, "required": p.required} for p in route.parameters],
    }


def generate_api_docs_tool(
    project_folder: str,
    language: str,
    framework: Optional[str] = None,
    output_format: str = "markdown",
    include_examples: bool = True,
) -> Dict[str, Any]:
    logger = get_logger("tool.generate_api_docs")
    logger.info(
        "tool_invoked",
        tool="generate_api_docs",
        project_folder=project_folder,
        language=language,
        framework=framework,
        output_format=output_format,
    )

    with tool_context("generate_api_docs", project_folder=project_folder, language=language) as run:
        result = generate_api_docs_impl(
            project_folder=project_folder,
            language=language,
            framework=framework,
            output_format=output_format,
            include_examples=include_examples,
        )
        run.add_completion_fields(
            routes_found=len(result.routes),
            framework=result.framework,
        )
        return {
            "routes": [_format_route_for_output(r) for r in result.routes],
            "markdown": result.markdown,
            "openapi_spec": result.openapi_spec,
            "framework": result.framework,
            "execution_time_ms": result.execution_time_ms,
        }


def generate_changelog_tool(
    project_folder: str,
    from_version: Optional[str] = None,
    to_version: str = "HEAD",
    changelog_format: str = "keepachangelog",
    group_by: str = "type",
) -> Dict[str, Any]:
    logger = get_logger("tool.generate_changelog")
    logger.info(
        "tool_invoked",
        tool="generate_changelog",
        project_folder=project_folder,
        from_version=from_version,
        to_version=to_version,
        format=changelog_format,
    )

    with tool_context("generate_changelog", project_folder=project_folder) as run:
        result = generate_changelog_impl(
            project_folder=project_folder,
            from_version=from_version,
            to_version=to_version,
            changelog_format=changelog_format,
            group_by=group_by,
        )
        run.add_completion_fields(
            commits_processed=result.commits_processed,
            versions=len(result.versions),
        )
        return {
            "versions": [_format_changelog_version(v) for v in result.versions],
            "markdown": result.markdown,
            "commits_processed": result.commits_processed,
            "commits_skipped": result.commits_skipped,
            "execution_time_ms": result.execution_time_ms,
        }


def sync_documentation_tool(
    project_folder: str,
    language: str,
    doc_types: List[str] | None = None,
    check_only: bool = True,
) -> Dict[str, Any]:
    logger = get_logger("tool.sync_documentation")

    if doc_types is None:
        doc_types = ["all"]

    logger.info(
        "tool_invoked",
        tool="sync_documentation",
        project_folder=project_folder,
        language=language,
        doc_types=doc_types,
        check_only=check_only,
    )

    with tool_context("sync_documentation", project_folder=project_folder, language=language) as run:
        result = sync_documentation_impl(
            project_folder=project_folder,
            language=language,
            doc_types=doc_types,
            check_only=check_only,
        )
        run.add_completion_fields(issues_found=len(result.issues))
        return _format_sync_response(result)


# =============================================================================
# MCP Registration
# =============================================================================


def register_documentation_tools(mcp: FastMCP) -> None:
    """Register all documentation feature tools with MCP server.

    Args:
        mcp: FastMCP server instance
    """

    @mcp.tool()
    def generate_docstrings(
        project_folder: str = Field(description="Root folder of the project (absolute path)"),
        file_pattern: str = Field(description="Glob pattern for files to process (e.g., '**/*.py')"),
        language: str = Field(description="Programming language (python, typescript, javascript, java)"),
        style: str = Field(default="auto", description="Docstring style (google, numpy, sphinx, jsdoc, javadoc, auto)"),
        overwrite_existing: bool = Field(default=False, description="If True, replace existing docstrings"),
        dry_run: bool = Field(default=True, description="If True, only preview changes without applying"),
        skip_private: bool = Field(default=True, description="If True, skip private functions (starting with _)"),
    ) -> Dict[str, Any]:
        """Generate docstrings/JSDoc for undocumented functions."""
        return generate_docstrings_tool(
            project_folder=project_folder,
            file_pattern=file_pattern,
            language=language,
            style=style,
            overwrite_existing=overwrite_existing,
            dry_run=dry_run,
            skip_private=skip_private,
        )

    @mcp.tool()
    def generate_readme_sections(
        project_folder: str = Field(description="Root folder of the project (absolute path)"),
        language: str = Field(default="auto", description="Programming language (or 'auto' for detection)"),
        sections: List[str] = Field(
            default_factory=lambda: ["all"],
            description="Sections to generate (installation, usage, features, api, structure, contributing, license, or 'all')",
        ),
        include_examples: bool = Field(default=True, description="Whether to include code examples"),
    ) -> Dict[str, Any]:
        """Generate README.md sections from code analysis."""
        return generate_readme_sections_tool(
            project_folder=project_folder,
            language=language,
            sections=sections,
            include_examples=include_examples,
        )

    @mcp.tool()
    def generate_api_docs(
        project_folder: str = Field(description="Root folder of the project (absolute path)"),
        language: str = Field(description="Programming language (python, typescript, javascript)"),
        framework: Optional[str] = Field(default=None, description="Framework name (express, fastapi, flask, or None for auto-detect)"),
        output_format: str = Field(default="markdown", description="Output format ('markdown', 'openapi', 'both')"),
        include_examples: bool = Field(default=True, description="Whether to include request/response examples"),
    ) -> Dict[str, Any]:
        """Generate API documentation from route definitions."""
        return generate_api_docs_tool(
            project_folder=project_folder,
            language=language,
            framework=framework,
            output_format=output_format,
            include_examples=include_examples,
        )

    @mcp.tool()
    def generate_changelog(
        project_folder: str = Field(description="Root folder of the project (must be git repository)"),
        from_version: Optional[str] = Field(default=None, description="Starting version/tag (None = last tag or first commit)"),
        to_version: str = Field(default="HEAD", description="Ending version/tag (default: HEAD)"),
        changelog_format: str = Field(default="keepachangelog", description="Output format ('keepachangelog', 'conventional', 'json')"),
        group_by: str = Field(default="type", description="Grouping strategy ('type', 'scope')"),
    ) -> Dict[str, Any]:
        """Generate changelog from git commits."""
        return generate_changelog_tool(
            project_folder=project_folder,
            from_version=from_version,
            to_version=to_version,
            changelog_format=changelog_format,
            group_by=group_by,
        )

    @mcp.tool()
    def sync_documentation(
        project_folder: str = Field(description="Root folder of the project (absolute path)"),
        language: str = Field(description="Programming language (python, typescript, javascript, java)"),
        doc_types: List[str] = Field(default_factory=lambda: ["all"], description="Types to check ('docstrings', 'links', 'all')"),
        check_only: bool = Field(default=True, description="If True, only report issues (no changes)"),
    ) -> Dict[str, Any]:
        """Synchronize documentation with code."""
        return sync_documentation_tool(
            project_folder=project_folder,
            language=language,
            doc_types=doc_types,
            check_only=check_only,
        )
