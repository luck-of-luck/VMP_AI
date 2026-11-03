# 2026-02-10: Test Stability & Documentation Improvements

## Added

- Added `develop_pattern` tool for iterative pattern development with strictness levels (63613b0)
- Added `matches` rule documentation to `get_ast_grep_docs` (9641374)
- Added pattern objects, lazy metavariables, and playground link to search docs (691e344)
- Added comprehensive deduplication tests for all submodules: analysis orchestrator, coverage detector, applicator executor, backup manager, duplication detector (9b08989..a08936e)

## Fixed

- Fixed integration tests to use modular API (4a7992a)
- Fixed pydantic.Field mock pollution in test state (2e81ccf)
- Relaxed benchmark performance thresholds for CI stability (ee11e9e)
- Added missing dev dependencies and fixed ast-grep exit code handling (4e47157)
- Updated MCP tools cache to 47 tools (039ca7e)

## Changed

- Removed module-level wrapper functions and slimmed dedup `__init__.py` (105cc32)
