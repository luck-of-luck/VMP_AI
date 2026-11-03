# Maintenance + Quality Updates - 2026-03-04

Summary of recent repository maintenance based on commit history.

## Highlights

### H1: Constants consolidation and magic-number migration
**Source commits**: `662578b`, `5194d99`, `646364b`, `460722b`, `20f3a87`, `d94b80f`, `fe005d8`, `0cf6cd3`

Consolidated repeated literals into shared constants and scoring scales, then migrated semantically matching call sites across source, scripts, and tests.

### H2: Analyzer false-positive reduction for constants
**Source commit**: `3440fc1`

Updated magic-number detection logic to skip one-off constant declarations (for example, `UPPER_CASE = 123`) so constant definitions are not reported as smells.

### H3: Exclusion hardening for virtual environments and backups
**Source commits**: `7a96e4d`, `24840be`, `00f2223`, `2a6282b`

Enforced consistent exclude patterns in analysis tools for `venv/.venv/virtualenv/site-packages` and `.ast-grep-backups` plus generated/build artifacts.

### H4: Quality gate cleanup and parser correctness
**Source commits**: `af1db42`, `3b9b5fc`, `f40d1f2`, `4ffabc3`

- Resolved Ruff and mypy issues in MCP tool wrappers and line-length violations.
- Cleared standards-enforcement violations in baseline quality runs.
- Fixed unified diff hunk parsing to align regex capture groups with shared constants.
- Current test baseline after fix: `1468 passed, 1 skipped`.
