# 2026-03-08: Review Follow-ups & Test Coverage

Address e74b8de code review findings and add targeted test coverage for error handling and version resolution edge cases.

## Code Fixes

### Schema Enhancement — Sentry Exception Capture

- **Restore `sentry_sdk.capture_exception` in `analyze_entity_graph`** — Re-added explicit exception capture that was lost during consolidation. Previously relied only on caller's `async_tool_context` wrapper. Now captures both directly and via wrapper for defensive coverage.
  - File: `src/ast_grep_mcp/features/schema/enhancement_service.py:768`
  - Added `import sentry_sdk` and `sentry_sdk.capture_exception(e, extras={...})` call
  - Extras include: `input_source`, `input_type`

### Tool Context — Logger Parameter Deduplication

- **Accept optional `logger` parameter in `_handle_tool_error`** — Avoid redundant `get_logger` calls when caller already has a logger. Added keyword-only `logger=None` parameter.
  - File: `src/ast_grep_mcp/utils/tool_context.py:13`
  - Callers can now pass `logger=my_logger` to skip recreation
  - Maintains backward compatibility; creates logger only when `None` provided

### Changelog Generator — Version Resolution Consistency

- **Use `_resolve_version_ref` for `from_version` in `_get_commit_range`** — Fixed asymmetry where `from_version` only tried v-prefix tag while `to_version` used full resolution (v-prefix → bare ref → HEAD fallback). Now both paths use identical `_resolve_version_ref` logic.
  - File: `src/ast_grep_mcp/features/documentation/changelog_generator.py:139`
  - Behavior change: invalid `from_version` now falls back to HEAD instead of silently passing raw string to git log
  - Resolves KNOWN_ISSUES.md: "`from_version` / `to_version` resolution asymmetry"

## Test Coverage Additions

### Tool Context Error Handling (2 new tests)

- **`test_handle_tool_error_uses_provided_logger`** — Verifies `_handle_tool_error` respects caller-supplied logger and skips `get_logger` call. Mocks both `get_logger` and `sentry_sdk.capture_exception`.
- **`test_handle_tool_error_creates_logger_when_none`** — Verifies default behavior creates logger via `get_logger("tool.{name}")` when none provided.

### Schema Enhancement Error Capture (1 new test)

- **`test_analyze_entity_graph_error_captures_sentry`** — Verifies `sentry_sdk.capture_exception` is called with correct `input_source` and `input_type` extras when `analyze_entity_graph` raises. Patches both `_load_graph_from_source` (to trigger error) and `capture_exception` (to verify).

### Changelog Generator Version Resolution (2 new tests)

- **`test_get_commit_range_from_version_uses_resolve`** — Renamed from `test_get_commit_range_from_version_asymmetry` to reflect fixed behavior. Verifies `_resolve_version_ref` is called for `from_version` with bare-ref fallback when v-prefix fails.
- **`test_get_commit_range_from_version_falls_back_to_head`** — New test covering HEAD fallback scenario when both v-prefix and bare ref resolution fail for `from_version`.

## Documentation Updates

- **BACKLOG.md** — Marked e74b8de Review Follow-ups and changelog_generator.py Hardening sections as Resolved with strikethrough notation
- **KNOWN_ISSUES.md** — Marked `from_version` / `to_version` resolution asymmetry as Resolved with implementation notes

## Summary

| Metric | Value |
|--------|-------|
| Files modified | 8 |
| Code fixes | 3 (schema, tool-context, changelog) |
| Tests added | 4 |
| Commits | 1 (`ad109ab`) |
| Test pass rate | 1625 passed, 1 skipped |
| Type | Bug fix, code quality, test coverage |

## Commit Details

- **Commit:** `ad109ab`
- **Type:** `fix(schema,changelog,tool-context)`
- **Scope:** 3 modules addressing e74b8de review follow-ups and changelog hardening
