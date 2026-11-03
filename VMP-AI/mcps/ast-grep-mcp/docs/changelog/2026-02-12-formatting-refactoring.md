# 2026-02-12: Formatting & Dedup Refactoring

## Changed

- Applied ruff format to 72 files (28861dd)
- Extracted `_parse_conditional_matches` to fix nesting violation in dedup analyzer (97fdb42)
- Documentation update (c369bdf)

## Dependencies

- Added pillow to project dependencies (e1ab927, 2026-02-11)
