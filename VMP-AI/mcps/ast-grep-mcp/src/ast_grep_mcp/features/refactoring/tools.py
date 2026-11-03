"""MCP tools for refactoring operations."""

from typing import Any, Dict, Optional

from pydantic import Field

from ast_grep_mcp.core.logging import get_logger

from ...models.refactoring import ExtractFunctionResult
from .analyzer import CodeSelectionAnalyzer
from .extractor import FunctionExtractor
from .rename_coordinator import RenameCoordinator

logger = get_logger(__name__)


def _format_extract_function_response(result: ExtractFunctionResult, selection: Any, language: str) -> Dict[str, Any]:
    """Format extract function result for tool response.

    Args:
        result: Extract function result
        selection: Code selection analysis
        language: Programming language

    Returns:
        Formatted response dictionary
    """
    if result.success:
        # Get function signature string based on language
        if result.function_signature and language == "python":
            signature_str = result.function_signature.to_python_signature()
        elif result.function_signature:
            signature_str = result.function_signature.to_typescript_signature()
        else:
            signature_str = None

        return {
            "success": True,
            "function_name": result.function_signature.name if result.function_signature else None,
            "function_signature": signature_str,
            "parameters": selection.parameters_needed,
            "return_values": selection.return_values,
            "diff_preview": result.diff_preview,
            "backup_id": result.backup_id,
            "warnings": result.warnings,
            "has_early_returns": selection.has_early_returns,
            "has_exceptions": selection.has_exceptions,
        }
    else:
        return {
            "success": False,
            "error": result.error,
        }


def _resolve_file_path(project_folder: str, file_path: str) -> str:
    if not file_path.startswith("/"):
        import os

        return os.path.join(project_folder, file_path)
    return file_path


def extract_function_tool(
    project_folder: str,
    file_path: str,
    start_line: int,
    end_line: int,
    language: str,
    function_name: Optional[str] = None,
    extract_location: str = "before",
    dry_run: bool = True,
) -> Dict[str, Any]:
    try:
        logger.info(
            "extract_function_tool_called",
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            language=language,
            dry_run=dry_run,
        )
        file_path = _resolve_file_path(project_folder, file_path)
        analyzer = CodeSelectionAnalyzer(language)
        selection = analyzer.analyze_selection(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            project_folder=project_folder,
        )
        extractor = FunctionExtractor(language)
        result = extractor.extract_function(
            selection=selection,
            function_name=function_name,
            extract_location=extract_location,
            dry_run=dry_run,
        )
        return _format_extract_function_response(result, selection, language)
    except Exception as e:
        logger.error("extract_function_tool_error", error=str(e))
        return {
            "success": False,
            "error": f"Extract function failed: {str(e)}",
        }


# MCP wrapper with Pydantic validation
def extract_function(
    project_folder: str = Field(description="Root folder of the project"),
    file_path: str = Field(description="Path to the file (relative or absolute)"),
    start_line: int = Field(description="Starting line of code to extract (1-indexed)", ge=1),
    end_line: int = Field(description="Ending line of code to extract (1-indexed, inclusive)", ge=1),
    language: str = Field(description="Programming language (python, typescript, javascript, java)"),
    function_name: Optional[str] = Field(None, description="Optional name for extracted function (auto-generated if None)"),
    extract_location: str = Field("before", description="Where to place function ('before', 'after', 'top')"),
    dry_run: bool = Field(True, description="If True, only preview changes without applying"),
) -> Dict[str, Any]:
    """Extract selected code into a new function with automatic parameter detection.

    MCP tool wrapper for extract_function_tool.
    """
    return extract_function_tool(
        project_folder=project_folder,
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        language=language,
        function_name=function_name,
        extract_location=extract_location,
        dry_run=dry_run,
    )


def _format_rename_symbol_response(result: Any, symbol_name: str, new_name: str) -> Dict[str, Any]:
    return {
        "success": result.success,
        "old_name": result.old_name,
        "new_name": result.new_name,
        "references_found": result.references_found,
        "references_updated": result.references_updated,
        "files_modified": result.files_modified,
        "conflicts": result.conflicts,
        "diff_preview": result.diff_preview,
        "backup_id": result.backup_id,
        "error": result.error,
    }


def rename_symbol_tool(
    project_folder: str,
    symbol_name: str,
    new_name: str,
    language: str,
    scope: str = "project",
    file_filter: Optional[str] = None,
    dry_run: bool = True,
) -> Dict[str, Any]:
    try:
        logger.info(
            "rename_symbol_tool_called",
            symbol_name=symbol_name,
            new_name=new_name,
            language=language,
            scope=scope,
            dry_run=dry_run,
        )
        coordinator = RenameCoordinator(language)
        result = coordinator.rename_symbol(
            project_folder=project_folder,
            old_name=symbol_name,
            new_name=new_name,
            scope=scope,
            file_filter=file_filter,
            dry_run=dry_run,
        )
        return _format_rename_symbol_response(result, symbol_name, new_name)
    except Exception as e:
        logger.error("rename_symbol_tool_error", error=str(e))
        return {
            "success": False,
            "old_name": symbol_name,
            "new_name": new_name,
            "error": f"Rename symbol failed: {str(e)}",
        }


# MCP wrapper with Pydantic validation
def rename_symbol(
    project_folder: str = Field(description="Root folder of the project"),
    symbol_name: str = Field(description="Current symbol name to rename"),
    new_name: str = Field(description="New symbol name"),
    language: str = Field(description="Programming language (python, typescript, javascript, java)"),
    scope: str = Field("project", description="Scope to rename in ('project', 'file', 'function')"),
    file_filter: Optional[str] = Field(None, description="Optional glob pattern to filter files (e.g., '*.py', 'src/**/*.ts')"),
    dry_run: bool = Field(True, description="If True, only preview changes without applying"),
) -> Dict[str, Any]:
    """Rename a symbol across codebase with scope awareness and conflict detection.

    MCP tool wrapper for rename_symbol_tool.
    """
    return rename_symbol_tool(
        project_folder=project_folder,
        symbol_name=symbol_name,
        new_name=new_name,
        language=language,
        scope=scope,
        file_filter=file_filter,
        dry_run=dry_run,
    )
