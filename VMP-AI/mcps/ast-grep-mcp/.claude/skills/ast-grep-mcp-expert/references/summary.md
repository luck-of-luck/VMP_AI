This file is a merged representation of a subset of the codebase, containing specifically included files and files not matching ignore patterns, combined into a single document by Repomix.
The content has been processed where content has been compressed (code blocks are separated by ⋮---- delimiter).

# Summary

## Purpose

This is a reference codebase organized into multiple files for AI consumption.
It is designed to be easily searchable using grep and other text-based tools.

## File Structure

This skill contains the following reference files:

| File | Contents |
|------|----------|
| `project-structure.md` | Directory tree with line counts per file |
| `files.md` | All file contents (search with `## File: <path>`) |
| `tech-stack.md` | Languages, frameworks, and dependencies |
| `summary.md` | This file - purpose and format explanation |

## Usage Guidelines

- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.

## Notes

- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Only files matching these patterns are included: src/ast_grep_mcp/**/__init__.py, src/ast_grep_mcp/core/*.py, src/ast_grep_mcp/models/*.py, src/ast_grep_mcp/server/*.py, src/ast_grep_mcp/constants.py, src/ast_grep_mcp/features/*/tools.py, main.py, pyproject.toml, CLAUDE.md
- Files matching these patterns are excluded: **/.venv/**, **/venv/**, **/__pycache__/**, **/*.pyc, **/*.egg-info/**, **/dist/**, **/build/**, **/node_modules/**, **/.git/**, **/.claude/**, **/backup*/**, **/*.bak, **/htmlcov/**, **/.mypy_cache/**, **/.ruff_cache/**, **/.pytest_cache/**, **/tests/**, **/.tox/**, **/scripts/**
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Content has been compressed - code blocks are separated by ⋮---- delimiter
- Files are sorted by Git change count (files with more changes are at the bottom)

## Statistics

52 files | 7,405 lines

| Language | Files | Lines |
|----------|------:|------:|
| Python | 50 | 7,211 |
| TOML | 1 | 122 |
| Markdown | 1 | 72 |

**Largest files:**
- `src/ast_grep_mcp/constants.py` (726 lines)
- `src/ast_grep_mcp/features/quality/tools.py` (518 lines)
- `src/ast_grep_mcp/features/search/tools.py` (492 lines)
- `src/ast_grep_mcp/core/usage_tracking.py` (412 lines)
- `src/ast_grep_mcp/models/documentation.py` (405 lines)
- `src/ast_grep_mcp/models/cross_language.py` (384 lines)
- `src/ast_grep_mcp/models/deduplication.py` (380 lines)
- `src/ast_grep_mcp/features/cross_language/tools.py` (362 lines)
- `src/ast_grep_mcp/features/complexity/tools.py` (350 lines)
- `src/ast_grep_mcp/features/documentation/tools.py` (349 lines)