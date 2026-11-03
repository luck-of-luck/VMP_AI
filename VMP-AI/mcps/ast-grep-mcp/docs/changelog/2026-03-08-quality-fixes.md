# 2026-03-08: Code Quality Fixes

Minor fixes for code quality issues identified during analysis refresh.

## Code Quality Fixes

- **Magic number `3` in `utils/formatters.py:229`** — Replaced hardcoded tuple indices `last[1], last[2], last[3]` with explicit tuple unpacking to destructure the `_COMPLEXITY_LEVELS` tuple. Improves clarity and aligns with existing pattern at line 225.

- **Assert in `features/deduplication/applicator_post_validator.py:137`** — Replaced production-code `assert content is not None` with explicit guard `if content is None: return []`. Asserts should only be used for development checks, not runtime validation.

## Summary

- **Items:** 2
- **Files modified:** 2
- **Type:** Code quality / standards enforcement
