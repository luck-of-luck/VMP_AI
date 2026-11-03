# 2026-03-08: Changelog Generator Hardening & Test Quality Improvements

Hardened `changelog_generator.py` error handling and improved test suite quality by consolidating mock imports, adding validation tests, and standardizing type hints.

## Changelog Generator Hardening

- **Validate `project_folder` exists in `_run_git_command`** — Added `os.path.isdir()` check before passing directory to `subprocess.run`. Returns `(False, "Directory not found: ...")` for non-existent paths instead of raising unhandled `FileNotFoundError`.

- **Replace empty string sentinel in `_get_first_commit` with `str | None`** — Changed return type from `str` (with `""` sentinel) to `str | None`. Updated `_find_previous_tag` to return `str | None` as well. `_get_commit_range` coalesces with `or ""` for downstream compatibility.

- **Add warning log on `None` coalescion** — When `_find_previous_tag` returns `None` (both tag list and first commit queries fail), `_get_commit_range` logs `from_ref_fallback_to_full_history` at warn level to aid debugging.

- **Standardize type hints to `str | None`** — Replaced all `Optional[str]` with `str | None` throughout the module (Python 3.13+). Removed unused `Optional` import.

## Test Quality Improvements

- **Consolidate `patch` import to module level** — Moved `from unittest.mock import patch` from per-method imports to module-level. Reduced boilerplate by ~60 lines in `TestChangelogHelpers`.

- **Consolidate mock target as class constant** — Extracted repeated `patch("ast_grep_mcp.features.documentation.changelog_generator._run_git_command")` string as class constant `_MOCK_TARGET`. Applied across 16 test methods.

- **Use `tmp_path` fixture for invalid-cwd test** — Changed `test_run_git_command_invalid_cwd` to use pytest's `tmp_path` fixture instead of hardcoded `/nonexistent/path/xyz`. Creates deterministic non-existent path: `str(tmp_path / "does_not_exist")`.

- **Rename test for clarity** — `test_find_previous_tag_no_tags` → `test_find_previous_tag_empty_tag_list` to distinguish "empty output (success=True, tags="")" from "git failure (success=False)".

- **Update `test_get_first_commit_failure` assertion** — Changed from `assert _get_first_commit("/fake") == ""` to `assert _get_first_commit("/fake") is None` to match new return type.

- **Add known-issue comment to asymmetry test** — Added docstring note to `test_get_commit_range_from_version_asymmetry` linking to `KNOWN_ISSUES.md` 'from_version / to_version resolution asymmetry' to document known-broken behavior.

## Documentation Updates

- **KNOWN_ISSUES.md: Replace hardcoded line numbers with function names** — Updated all references to use function names (`_get_commit_range`, `_run_git_command`, `_get_first_commit`) instead of line numbers for durability across future edits.

- **KNOWN_ISSUES.md: Mark resolved issues with strikethrough** — Marked cwd validation and sentinel issues as resolved with descriptive resolution notes. Kept open asymmetry issue highlighted.

- **BACKLOG.md: Split Hardening section into Resolved/Open** — Separated `changelog_generator.py Hardening` into Resolved subsection (2 items) and Open subsection (1 item: `from_version` asymmetry with KNOWN_ISSUES.md link).

- **BACKLOG.md: Fully mark Test & Documentation Quality as resolved** — All 5 items struck-through with accurate descriptions of implementations.

## Summary

- **Items:** 7 (4 hardening + 1 open issue + 5 test quality fixes)
- **Files modified:** 4 (changelog_generator.py, test_documentation.py, KNOWN_ISSUES.md, BACKLOG.md)
- **Type:** Code hardening, test quality, documentation
- **Tests:** All 48 unit tests passing, mypy clean
- **Commit:** `1b5f331`
