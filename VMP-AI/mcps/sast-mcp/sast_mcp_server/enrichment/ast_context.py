"""AST-aware context extraction for SAST findings.

Extracts the enclosing function/class source code around a finding line,
providing the AI agent with complete semantic context rather than just a
line number.

Supports:
- Python: via built-in `ast` module
- JavaScript/TypeScript: via tree-sitter (if installed)
- Fallback: ±10 lines for unsupported languages
"""

import logging
import os

logger = logging.getLogger(__name__)

# Lazy-loaded tree-sitter parsers
_js_parser = None
_ts_parser = None


def _get_js_parser():
    """Lazy-load tree-sitter JavaScript parser."""
    global _js_parser
    if _js_parser is not None:
        return _js_parser
    try:
        import tree_sitter_javascript as tsjs
        from tree_sitter import Language, Parser

        js_language = Language(tsjs.language())
        _js_parser = Parser(js_language)
        return _js_parser
    except (ImportError, Exception) as e:
        logger.debug("tree-sitter JS not available, using line fallback: %s", e)
        return None


def _get_ts_parser():
    """Lazy-load tree-sitter TypeScript parser."""
    global _ts_parser
    if _ts_parser is not None:
        return _ts_parser
    try:
        import tree_sitter_typescript as tsts  # type: ignore[import-not-found]
        from tree_sitter import Language, Parser

        ts_language = Language(tsts.language_typescript())
        _ts_parser = Parser(ts_language)
        return _ts_parser
    except (ImportError, Exception) as e:
        logger.debug("tree-sitter TS not available, using line fallback: %s", e)
        return None


def _find_enclosing_function_treesitter(
    parser, source_bytes: bytes, lines: list, target_line: int
) -> tuple[str, int, int] | None:
    """Use tree-sitter to find the enclosing function node around target_line.

    Returns (snippet, start_line, end_line) or None if not found.
    """
    tree = parser.parse(source_bytes)
    root = tree.root_node

    # tree-sitter uses 0-indexed lines
    target_line_0 = target_line - 1

    best_node = None
    best_size = float("inf")

    # Walk the tree looking for function/method/class nodes containing target_line
    function_types = {
        "function_declaration",
        "function_expression",
        "arrow_function",
        "method_definition",
        "class_declaration",
        "class_expression",
        "generator_function_declaration",
        # TypeScript
        "function_signature",
        "method_signature",
    }

    def _walk(node):
        nonlocal best_node, best_size
        if node.start_point[0] <= target_line_0 <= node.end_point[0]:
            if node.type in function_types:
                size = node.end_point[0] - node.start_point[0]
                if size < best_size:
                    best_node = node
                    best_size = size
            for child in node.children:
                _walk(child)

    _walk(root)

    if best_node is not None:
        start = best_node.start_point[0] + 1  # Back to 1-indexed
        end = best_node.end_point[0] + 1
        snippet = "".join(lines[start - 1 : end])
        return (snippet, start, end)

    return None


def get_function_context(file_path: str, target_line: int) -> tuple[str, int, int]:
    """Return the complete source code of the function containing the target_line.

    Args:
        file_path: Path to the source file.
        target_line: The 1-indexed line number of the finding.

    Returns:
        Tuple of (code_snippet, start_line, end_line).
        Falls back to ±10 lines if AST parsing fails.
    """
    if not os.path.exists(file_path):
        return ("File not found.", target_line, target_line)

    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            source_code = "".join(lines)
    except Exception as e:
        logger.warning("Could not read file %s: %s", file_path, e)
        return ("Could not read file.", target_line, target_line)

    # Python: use built-in ast module
    if file_path.endswith(".py"):
        try:
            import ast

            parsed = ast.parse(source_code)
            # Find the tightest enclosing function/class
            best = None
            best_size = float("inf")
            for node in ast.walk(parsed):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    end_line = node.end_lineno or node.lineno
                    if node.lineno <= target_line <= end_line:
                        size = end_line - node.lineno
                        if size < best_size:
                            best = node
                            best_size = size
            if best is not None:
                start = best.lineno
                end = best.end_lineno or start
                snippet = "".join(lines[start - 1 : end])
                return (snippet, start, end)
        except SyntaxError:
            logger.debug("Python AST parse failed for %s, using line fallback", file_path)

    # JavaScript: use tree-sitter
    elif file_path.endswith((".js", ".jsx", ".mjs", ".cjs")):
        parser = _get_js_parser()
        if parser is not None:
            result = _find_enclosing_function_treesitter(
                parser, source_code.encode("utf-8"), lines, target_line
            )
            if result is not None:
                return result

    # TypeScript: use tree-sitter
    elif file_path.endswith((".ts", ".tsx")):
        parser = _get_ts_parser()
        if parser is not None:
            result = _find_enclosing_function_treesitter(
                parser, source_code.encode("utf-8"), lines, target_line
            )
            if result is not None:
                return result

    # Fallback: ±10 lines around the target
    start = max(1, target_line - 10)
    end = min(len(lines), target_line + 10)
    snippet = "".join(lines[start - 1 : end])
    return (snippet, start, end)
