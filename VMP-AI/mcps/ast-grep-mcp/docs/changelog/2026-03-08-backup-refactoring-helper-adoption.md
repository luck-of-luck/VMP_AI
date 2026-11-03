# 2026-03-08: Backup Refactoring & Helper Adoption

## Summary

Extracted shared backup primitives to `utils/backup.py`, refactored `applicator_backup.py` to reduce complexity, and adopted `tool_context` in executor/schema modules.

## Changes

### Shared Backup Utils (`c847003`)

New `src/ast_grep_mcp/utils/backup.py` with 4 primitives shared by `rewrite/backup.py` and `deduplication/applicator_backup.py`:

- `get_file_hash` — SHA-256 file hashing (moved from `rewrite/backup.py`)
- `resolve_backup_dir` — unique backup ID generation with collision handling
- `copy_file_to_backup` — single-file copy with metadata entry
- `restore_file_from_backup` — single-file restore with existence check

Eliminated ~60 lines of duplication between the two backup modules.

### Applicator Backup Complexity Reduction (`7880737`)

Extracted 6 private helpers from `DeduplicationBackupManager`:

| Method | Before | After |
|--------|--------|-------|
| `cleanup_old_backups` | cog=33 | cog=14 |
| `list_backups` | cog=23 | cog=14 |
| `create_backup` | cog=20 | cog=10 |
| `rollback` | cog=18 | cog=15 |

Added 300+ lines of tests covering all new helpers and edge cases.

### Tool Context & Exclusion Adoption (`0a679bb`)

- `core/executor.py:run_command` — wrapped with `tool_context()`, reduced ~35 lines of manual timing + Sentry boilerplate
- `schema/enhancement_service.py` — replaced hardcoded `_EXCLUDED_DIRS` with `FilePatterns.DEFAULT_EXCLUDE`
- `refactoring/extractor.py` — further decomposition of `_generate_docstring`, `_generate_function_body`, `_generate_signature`, `_apply_extraction`

### Backlog Refresh (`8d4d13a`, `306756c`)

- Added `scripts/scan_complexity_offenders.py` for automated offender scanning
- Refreshed offender table: 25 functions remain above thresholds
- Baseline progression: 434 → 407 → 100 → 80 → 25

## Commits

- `c847003` refactor(backup): extract shared backup primitives to utils/backup.py
- `7880737` refactor(dedup): extract helpers in applicator_backup to reduce complexity
- `8d4d13a` docs(backlog): refresh offender table and add scan script
- `306756c` docs(backlog): expand recently-resolved entries with commit refs and detail
- `0a679bb` refactor(executor,backup,schema): adopt tool_context, extract helpers, unify exclusions
