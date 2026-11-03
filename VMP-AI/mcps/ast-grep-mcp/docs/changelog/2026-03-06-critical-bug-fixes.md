# 2026-03-06: Critical Bug Fixes

## Fixed

- Fixed duplicate exception classes: consolidated `RuleValidationError` and `RuleStorageError` definitions from `core.exceptions` into single canonical location in `models.standards` to fix silent catch failures (b492180)
- Fixed stderr pipe deadlock in `stream_ast_grep_results`: added background thread to drain stderr concurrently while reading stdout, preventing mutual deadlock when ast-grep writes large error messages (99dec84)
- Added timeout to `kill() + wait()` sequence in process cleanup to prevent indefinite hangs on unkillable processes (D-state on Linux, network filesystems) (99dec84)
