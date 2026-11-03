"""MCP tool definitions for code condensation features.

Registers 6 tools:
- condense_extract_surface
- condense_normalize
- condense_strip
- condense_pack
- condense_estimate
- condense_train_dictionary
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from ...constants import CondenseDefaults, CondenseDictionaryDefaults
from ...core.logging import get_logger
from ...utils.tool_context import tool_context
from .dictionary import train_dictionary_impl
from .estimator import estimate_condensation_impl
from .normalizer import normalize_source
from .service import condense_pack_impl, extract_surface_impl
from .strategies import VALID_STRATEGIES, describe_strategy
from .strip import strip_dead_code

logger = get_logger("condense.tools")


def _resolve_file_path(path: str) -> Path:
    """Resolve and validate that path is an existing file (not a directory).

    Raises FileNotFoundError or IsADirectoryError with structured messages.
    """
    p = Path(path).resolve()
    if not p.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    if p.is_dir():
        raise IsADirectoryError(f"Expected a file path, got a directory: {path}")
    return p


# ---------------------------------------------------------------------------
# Standalone tool functions (testable without MCP)
# ---------------------------------------------------------------------------


def condense_extract_surface_tool(
    path: str,
    language: str,
    include_docstrings: bool = CondenseDefaults.INCLUDE_DOCSTRINGS,
    complexity_guided: bool = False,
    complexity_threshold: int = CondenseDefaults.COMPLEXITY_STRIP_THRESHOLD,
) -> Dict[str, Any]:
    """Extract public API surface from source files."""
    logger.info("tool_invoked", tool="condense_extract_surface", path=path, language=language)

    with tool_context("condense_extract_surface", path=path, language=language) as run:
        result = extract_surface_impl(
            path=path,
            language=language,
            include_docstrings=include_docstrings,
            complexity_guided=complexity_guided,
            complexity_threshold=complexity_threshold,
        )
        run.add_completion_fields(
            files_processed=result.get("files_processed", 0),
            reduction_pct=result.get("reduction_pct", 0.0),
        )
        return result


def condense_normalize_tool(
    path: str,
    language: str,
) -> Dict[str, Any]:
    """Normalize source code to canonical forms for better downstream compression."""
    logger.info("tool_invoked", tool="condense_normalize", path=path, language=language)

    with tool_context("condense_normalize", path=path, language=language) as run:
        resolved = _resolve_file_path(path)
        source = resolved.read_text(encoding="utf-8", errors="replace")
        normalized, count = normalize_source(source, language)

        result: Dict[str, Any] = {
            "normalized_source": normalized,
            "normalizations_applied": count,
            "original_bytes": len(source.encode("utf-8")),
            "normalized_bytes": len(normalized.encode("utf-8")),
        }
        run.add_completion_fields(normalizations_applied=count)
        return result


def condense_strip_tool(
    path: str,
    language: str,
) -> Dict[str, Any]:
    """Remove dead code, debug statements, and empty blocks."""
    logger.info("tool_invoked", tool="condense_strip", path=path, language=language)

    with tool_context("condense_strip", path=path, language=language) as run:
        resolved = _resolve_file_path(path)
        source = resolved.read_text(encoding="utf-8", errors="replace")
        stripped, removed = strip_dead_code(source, language)

        result: Dict[str, Any] = {
            "stripped_source": stripped,
            "lines_removed": removed,
            "original_lines": source.count("\n") + 1,
            "stripped_lines": stripped.count("\n") + 1,
        }
        run.add_completion_fields(lines_removed=removed)
        return result


def condense_pack_tool(
    path: str,
    language: Optional[str] = None,
    strategy: str = CondenseDefaults.DEFAULT_STRATEGY,
    file_type_routing: bool = True,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run the full normalize → strip → extract condensation pipeline."""
    if strategy not in VALID_STRATEGIES:
        return {
            "error": f"Unknown strategy '{strategy}'. Valid: {sorted(VALID_STRATEGIES)}",
            "strategy_descriptions": {s: describe_strategy(s) for s in VALID_STRATEGIES},
        }

    logger.info(
        "tool_invoked",
        tool="condense_pack",
        path=path,
        strategy=strategy,
        language=language,
    )

    with tool_context("condense_pack", path=path, strategy=strategy, language=language) as run:
        result = condense_pack_impl(
            path=path,
            language=language,
            strategy=strategy,
            file_type_routing=file_type_routing,
            exclude_patterns=exclude_patterns,
        )
        run.add_completion_fields(
            files_processed=result.get("files_processed", 0),
            reduction_pct=result.get("reduction_pct", 0.0),
        )
        return result


def condense_estimate_tool(
    path: str,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Estimate condensation reduction ratios without modifying any files."""
    logger.info("tool_invoked", tool="condense_estimate", path=path, language=language)

    with tool_context("condense_estimate", path=path, language=language) as run:
        result = estimate_condensation_impl(path=path, language=language)
        run.add_completion_fields(total_files=result.get("total_files", 0))
        return result


def condense_train_dictionary_tool(
    path: str,
    language: Optional[str] = None,
    sample_count: int = CondenseDictionaryDefaults.SAMPLE_COUNT,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Train a zstd dictionary on representative code samples from a codebase."""
    logger.info(
        "tool_invoked",
        tool="condense_train_dictionary",
        path=path,
        language=language,
        sample_count=sample_count,
    )

    with tool_context("condense_train_dictionary", path=path, language=language, sample_count=sample_count) as run:
        result = train_dictionary_impl(
            path=path,
            language=language,
            sample_count=sample_count,
            output_dir=output_dir,
        )
        run.add_completion_fields(
            samples_used=result.get("samples_used", 0),
            dict_size_bytes=result.get("dict_size_bytes", 0),
        )
        return result


# ---------------------------------------------------------------------------
# MCP registration helpers
# ---------------------------------------------------------------------------


def _register_extract_surface(mcp: FastMCP) -> None:
    @mcp.tool()
    def condense_extract_surface(
        path: str = Field(description="Directory or file path to analyze"),
        language: str = Field(description="Programming language (e.g. 'python', 'typescript')"),
        include_docstrings: bool = Field(
            default=CondenseDefaults.INCLUDE_DOCSTRINGS,
            description="Whether to include docstrings in the extracted surface",
        ),
        complexity_guided: bool = Field(
            default=False,
            description="Reserved for future use: will integrate complexity analysis for depth selection",
        ),
        complexity_threshold: int = Field(
            default=CondenseDefaults.COMPLEXITY_STRIP_THRESHOLD,
            description="Cyclomatic threshold; functions above this keep full body",
        ),
    ) -> Dict[str, Any]:
        """Extract public API surface (exports, signatures, types) from source files.

        Returns condensed source with only the public interface, stripping
        function bodies for low-complexity functions when complexity_guided=True.
        Achieves ~70-85% token reduction in ai_chat mode.
        """
        return condense_extract_surface_tool(
            path=path,
            language=language,
            include_docstrings=include_docstrings,
            complexity_guided=complexity_guided,
            complexity_threshold=complexity_threshold,
        )


def _register_normalize(mcp: FastMCP) -> None:
    @mcp.tool()
    def condense_normalize(
        path: str = Field(description="Path to a single source file to normalize"),
        language: str = Field(description="Programming language"),
    ) -> Dict[str, Any]:
        """Normalize source code to canonical forms before compression.

        Applies language-specific transforms: consistent string quotes,
        trailing semicolon removal (JS/TS), trailing comma cleanup.
        Returns normalized_source, normalizations_applied, and byte counts.
        """
        return condense_normalize_tool(path=path, language=language)


def _register_strip(mcp: FastMCP) -> None:
    @mcp.tool()
    def condense_strip(
        path: str = Field(description="Path to a single source file"),
        language: str = Field(description="Programming language"),
    ) -> Dict[str, Any]:
        """Remove dead code, debug statements, and empty blocks from source.

        Strips console.log/print, debugger, pdb.set_trace, and similar.
        Returns stripped_source and lines_removed count.
        """
        return condense_strip_tool(path=path, language=language)


def _register_pack(mcp: FastMCP) -> None:
    @mcp.tool()
    def condense_pack(
        path: str = Field(description="Directory or file path to condense"),
        language: Optional[str] = Field(
            default=None,
            description="Optional language filter. If omitted, all code files are processed.",
        ),
        strategy: str = Field(
            default=CondenseDefaults.DEFAULT_STRATEGY,
            description=(
                "Condensation strategy: 'ai_chat' (~85% reduction, lossy), "
                "'ai_analysis' (~40% reduction, lossless), "
                "'archival' (~30% reduction, lossless), "
                "'polyglot' (~60-80% reduction, per-file-type routing)."
            ),
        ),
        file_type_routing: bool = Field(
            default=True,
            description="Auto-select strategy per file type (code vs config vs text vs test)",
        ),
        exclude_patterns: Optional[List[str]] = Field(
            default=None,
            description="Additional glob patterns to exclude (e.g. ['*.generated.ts'])",
        ),
    ) -> Dict[str, Any]:
        """Run the full condensation pipeline: normalize → strip → extract.

        Chains all condense operations into a single pass over a directory.
        Returns condensed_output, reduction_pct, token estimates, and per-language stats.
        """
        return condense_pack_tool(
            path=path,
            language=language,
            strategy=strategy,
            file_type_routing=file_type_routing,
            exclude_patterns=exclude_patterns,
        )


def _register_estimate(mcp: FastMCP) -> None:
    @mcp.tool()
    def condense_estimate(
        path: str = Field(description="Directory or file path to estimate"),
        language: Optional[str] = Field(
            default=None,
            description="Optional language filter",
        ),
    ) -> Dict[str, Any]:
        """Estimate condensation reduction ratios without modifying any files.

        Returns projected token/byte counts for all four strategies plus
        top_reduction_candidates ranked by line count.
        Safe to run on any codebase — read-only, no modifications.
        """
        return condense_estimate_tool(path=path, language=language)


def _register_train_dictionary(mcp: FastMCP) -> None:
    @mcp.tool()
    def condense_train_dictionary(
        path: str = Field(description="Root directory to collect code samples from"),
        language: Optional[str] = Field(
            default=None,
            description="Optional language filter (e.g. 'python', 'typescript')",
        ),
        sample_count: int = Field(
            default=CondenseDictionaryDefaults.SAMPLE_COUNT,
            description="Maximum number of sample files to use for training",
        ),
        output_dir: Optional[str] = Field(
            default=None,
            description=("Directory to write the dictionary file. Defaults to .condense/dictionaries/ inside path."),
        ),
    ) -> Dict[str, Any]:
        """Train a zstd dictionary on representative code samples.

        A per-codebase dictionary improves zstd compression 10-30% for
        small-to-medium files (<100KB) with consistent coding patterns.
        Use the resulting dict_path with: zstd -D <dict_path> to compress.
        Returns dict_path, dict_size_bytes, samples_used, and estimated improvement.
        """
        return condense_train_dictionary_tool(
            path=path,
            language=language,
            sample_count=sample_count,
            output_dir=output_dir,
        )


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------


def register_condense_tools(mcp: FastMCP) -> None:
    """Register all condense tools with the MCP server.

    Args:
        mcp: FastMCP instance to register tools with.
    """
    _register_extract_surface(mcp)
    _register_normalize(mcp)
    _register_strip(mcp)
    _register_pack(mcp)
    _register_estimate(mcp)
    _register_train_dictionary(mcp)
