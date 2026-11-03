# 2026-02-25: Code Condensation Feature

## Added

- Added `condense_extract_surface` tool — semantic surface extraction with per-language AST patterns (830b7ed)
- Added `condense_normalize` tool — rewrite transforms (identifier shortening, whitespace, comments) (830b7ed)
- Added `condense_strip` tool — dead code removal (unreachable branches, unused imports) (830b7ed)
- Added `condense_pack` tool — full pipeline orchestration with token-aware packing (830b7ed)
- Added `condense_estimate` tool — token estimation before condensation (830b7ed)
- Added `condense_train_dictionary` tool — zstd dictionary training from codebase samples (1ffc15b)
- Polyglot strategy routing for language-specific condensation (830b7ed)
- 81+ new tests for condense feature
- Total MCP tools: 53

## Fixed

- Fixed async event loop conflict and zstd `--train` flag handling (87a1d91)
- Removed unused CondenseDefaults constants, standardized field naming (d97d782)
- Addressed code review findings and genai quality gaps (6c8b635, 9a09893)

## Changed

- Migrated magic numbers to named constants across 17 modules (b0ea4b0, dcae1ff, 9e65f55)
- Zero complexity violations maintained throughout refactoring
