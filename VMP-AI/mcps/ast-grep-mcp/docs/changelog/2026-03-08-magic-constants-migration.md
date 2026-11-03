# 2026-03-08: Magic Constants Migration

Replaced hardcoded magic strings and numbers with named constants across executor, schema, and backup modules.

## Changes

### Executor Magic Numbers (`4976bef`)

Consolidated magic numbers in `core/executor.py` to `StreamDefaults`:

- **`timeout=2`** — Replaced 2 occurrences with `StreamDefaults.PROCESS_TERMINATE_TIMEOUT_SECONDS`
- **`timeout=5`** — Replaced 3 occurrences with `StreamDefaults.PROCESS_KILL_TIMEOUT_SECONDS`

### Executor Magic Strings (`4976bef`)

- **`"ast-grep"`** — Replaced 6 occurrences in `core/executor.py` with `ExecutorDefaults.AST_GREP_COMMAND`

### Backup Magic Strings (`f79f686`)

Migrated 13 occurrences of hardcoded backup directory prefixes across `deduplication/applicator_backup.py` and `rewrite/backup.py` to `BackupDefaults`:

- `BackupDefaults.DIR_NAME = ".ast-grep-backups"`
- `BackupDefaults.METADATA_FILE = "backup-metadata.json"`
- `BackupDefaults.DEDUP_PREFIX = "dedup-backup"`
- `BackupDefaults.REWRITE_PREFIX = "backup"`

Eliminates string duplication and centralizes backup configuration constants.

## Summary

- **Items:** 4 categories (executor numbers, executor strings, backup strings)
- **Total occurrences:** 22 magic values replaced with named constants
- **Files modified:** 3 (`executor.py`, `applicator_backup.py`, `backup.py`)
- **New constants class:** `BackupDefaults` added/expanded in `constants.py`
- **Benefit:** Improved maintainability, single source of truth for configuration values

## Commits

- `4976bef` refactor(executor): replace magic strings/numbers with constants
- `f79f686` refactor(constants): migrate backup magic strings to BackupDefaults constants
