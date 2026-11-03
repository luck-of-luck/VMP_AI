# Complexity Refactoring + Code Review Fixes — 2026-03-06

Batch completion of complexity reduction queue (C1-C10) and high-priority code review issues (BR1-BR8). All items committed 2026-03-06.

## Complexity Refactoring (C1-C10)

### C1: Split file-migration orchestration in `migrate_file`
**Commit**: `70f78ef` | **Priority**: P1
Split `migrate_file` (cyclomatic 26, cognitive 76, nesting 9) into focused helpers: `_load_file_lines`, `_create_backup_if_needed`, `_replace_print_statements`, `_ensure_import_present`, `_persist_changes_if_needed`. Main orchestrator now linear and branch-light.

### C2: Replace brittle orphan-import repair flow in `fix_file`
**Commit**: `63d5873` | **Priority**: P1
Decomposed `fix_file` (cyclomatic 29, cognitive 56, nesting 6) from index/skip state mutation into explicit phases: detect candidate orphan ranges, validate, rebuild by range exclusion. No in-loop index mutation.

### C3: Decompose end-to-end analytics script `analyze_project`
**Commit**: `fb4bf17` | **Priority**: P1
Extracted scan-specific steps from orchestrator (cyclomatic 19, cognitive 49, nesting 5): `_run_complexity_scan`, `_run_smell_scan`, `_run_security_scan`, plus `_format_*_summary` helpers. Output payload backward-compatible.

### C4: Split reporting + summary extraction in `generate_summary_report`
**Commit**: `2794f06` | **Priority**: P2
Bundled function (cyclomatic 14, cognitive 43, nesting 7) split into: `_run_enforcement`, `_generate_markdown_report`, `_print_report_summary`. Simplified happy-path flow; summary extraction isolated.

### C5: Break up enhanced dedup response builder
**Commit**: `16a5ac1` | **Priority**: P2
Decomposed `create_enhanced_duplication_response` (cyclomatic 23, cognitive 40, nesting 6) into `_build_enhanced_candidate`, `_generate_candidate_diff_preview`, `_update_distribution`, `_build_global_recommendations`, `_build_summary`. No regression in candidate ordering.

### C6: Simplify hybrid config validation in `__post_init__`
**Commit**: `5e6b3de` | **Priority**: P2
Split validator (cyclomatic 19, cognitive 37, nesting 5) into `_apply_semantic_rebalance_if_needed`, `_validate_weight_bounds`, `_validate_weight_sum`. Validation semantics unchanged.

### C7: Refactor Flask route parser loop in `parse_file`
**Commit**: `6874996` | **Priority**: P2
Extracted decorator matching, method parsing, and route creation into `_parse_decorator_match`, `_find_next_handler_name`, `_build_routes_for_methods`. No duplicate or missing routes in support of `@app.route`/`@blueprint.route`.

### C8: Decompose external call-site discovery
**Commit**: `426b938` | **Priority**: P2
Split `_find_external_call_sites` (cyclomatic 14, cognitive 36, nesting 7) into `_search_call_sites_for_name`, `_normalize_match_file_path`, `_to_call_site_record`. Deterministic unit tests with mocked responses.

### C9: Replace heuristic-heavy orphan detection monolith
**Commit**: `e7a51e3` | **Priority**: P2
Decomposed `find_orphaned_imports` (cyclomatic 23, cognitive 35, nesting 6) into composable predicates (`_is_orphan_close_paren`, `_is_orphan_import_item_start`) and single range scanner. Clearer predicate-focused tests.

### C10: Modularize normalization pipeline in `_normalize_for_ast`
**Commit**: `029b7b2` | **Priority**: P2
Extracted per-line transforms (`_strip_inline_python_comment`, `_strip_inline_js_comment`, `_normalize_indentation`) from main loop. Composed in small pipeline. Normalized output unchanged; table-driven tests for edge cases.

## Code Review Fixes (BR1-BR8)

### BR1: Fix indentation normalization for 4-space code
**Commit**: `590b4d1`, `029b7b2` | **Priority**: P1
`NORMALIZATION_DIVISOR = 2` caused 4-space-indented code to normalize incorrectly. Switched to adaptive indent divisor (detects 4-space and 2-space consistently). Identical functions in different styles now compare as similar.

### BR2: Fix contract mismatch in `filter_files_by_size`
**Commit**: `18a15dd` | **Priority**: P1
Function returned `([], [])` silently when `max_size_mb is None` despite docstring claiming "None = unlimited". Fixed to walk and return all files when unlimited. Callers with guards unaffected.

### BR3: Fix `meta_vars` type annotation mismatch
**Commit**: `77e4b2d` | **Priority**: P1
`RuleViolation.meta_vars` declared as `Optional[Dict[str, str]]` but stored `List[str]` for `$$$` multi-captures, causing `TypeError` in fixer. Widened type to `Dict[str, str | list[str]]` with guarded replacements.

### BR4: Fix column 0-indexing inconsistency in RuleViolation
**Commit**: `81cf372` | **Priority**: P1
Columns left at 0-indexed value from ast-grep while lines applied `+1` offset. Added `+1` to column assignments to match 1-indexed docstring contract. `security_scanner` already correct; enforcer now aligned.

### BR5: Fix file handle leak in `configure_logging`
**Commit**: `682a5f5` | **Priority**: P1
Each call opened new file descriptor with no close, leaking in long-running processes. Fixed by holding module-level reference outside function. Test suites no longer leak file descriptors.

### BR6: Fix `CACHE_TTL` semantic mismatch with `CLEANUP_INTERVAL_SECONDS`
**Commit**: `955772c` | **Priority**: P2
`CACHE_TTL` initialized from `CLEANUP_INTERVAL_SECONDS` (300s background sweep) despite semantic difference. Introduced dedicated `DEFAULT_CACHE_TTL` (3600s); callers now get correct expiry.

### BR7: Fix double `os.environ.get` call in config path resolution
**Commit**: `abc9e0d` | **Priority**: P2
`_resolve_and_validate_config_path` read `AST_GREP_CONFIG` env var twice on same condition with dead code between. Simplified to single read with walrus operator.

### BR8: Add timeout to `kill()` + `wait()` in process cleanup
**Commit**: `99dec84` | **Priority**: P1
Bare `process.wait()` after `kill()` could block indefinitely on unkillable processes. Both `_terminate_process` and `_cleanup_process` fixed with 5s timeout.

## Additional Fixes

### CR1: Commit 565aaea Parser Fixes
**Commit**: `6473709` | **Priority**: P1
Fixed three critical parser issues in `sync_checker.py` identified in code review:
- High: `_split_params` depth counter guard (goes negative on `>` in `=>` defaults)
- High: `rstrip("?")` strips all trailing `?` chars (now uses `p.name[:-1] if p.name.endswith("?")`)
- Medium: JSDoc nested brace regex only handles 2 levels (pre-existing limitation noted)

### M1: Handle JS/TS brace counter edge cases
**Commit**: `10f757c` | **Priority**: P2
Improved brace counter for JavaScript/TypeScript to skip braces inside template strings and regex patterns. Surface extraction now ignores structural braces from escaped content.

### SE1: Replace `assert isinstance()` with explicit type checks
**Priority**: P2 | **Implementation session**: 2026-03-06
Removed 4 `assert isinstance()` calls in production code (asserts stripped under `-O` flag):
- `benchmark.py:82`: Removed redundant assert (value provably float)
- `applicator.py:673,680,689`: Replaced with `if not isinstance: raise TypeError`

## Duplication Consolidation (D1-D4)

### D1: Consolidate `_is_python_import` / `_is_javascript_import` in renamer
**Priority**: P2 | **Implementation session**: 2026-03-06
Merged two identical import-checking methods (`_is_python_import` and `_is_javascript_import`) into a single `_is_import(context)` method in `renamer.py`. Updated both call sites (lines 204, 258) to use the unified method. ~10 lines saved; 37 related tests pass.

### D2: Parameterize severity-suggestion helpers in search service
**Priority**: P2 | **Implementation session**: 2026-03-06
Replaced three identical severity-filtering helpers (`_add_error_suggestions`, `_add_warning_suggestions`, `_add_info_suggestions`) in `search/service.py` with a single parameterized `_add_suggestions_by_severity(severity, prefix, issues, suggestions)` function. Updated all call sites in `_generate_suggestions`. ~10 lines saved; 35 debug/pattern tests pass.

### D3: Console logger error/warning methods
**Priority**: P3 | **Implementation session**: 2026-03-06
Extracted shared `_log_to_stderr(prefix, message)` helper in `console_logger.py` to consolidate identical prefix/message logging logic. `error()` and `warning()` now delegate to the shared helper. ~8 lines saved; 5 related tests pass.

### D4: Smell detector `__init__` duplication
**Priority**: P3 | **Implementation session**: 2026-03-06
Added `__init__(self, threshold, logger_name)` to the `SmellDetector` ABC base class and refactored 5 detector subclasses (`LongFunctionDetector`, `ParameterBloatDetector`, `DeepNestingDetector`, `LargeClassDetector`, `MagicNumberDetector`) to call `super().__init__()` instead of duplicating threshold/logger initialization. ~20 lines saved; all 1,615 tests pass.

## Post-Refactoring Lint & Type Fixes

- Resolved 59 ruff errors introduced by complexity refactoring (96632cf)
- Resolved 38 mypy errors introduced by complexity refactoring (5a3f682)
- Wrapped `yaml.dump` return with `str()` to resolve `no-any-return` (f1b587d)
- Extracted 90 magic numbers into shared constants across 37 files (afdf71a)

## Summary

- **Items migrated**: 24 (C1-C10, BR1-BR8, CR1, M1, SE1, D1-D4)
- **Files affected**: 24 modules across core, features, utils, scripts
- **Total cyclomatic reduction**: ~280 complexity points across refactored functions
- **Duplication consolidated**: ~48 lines across search, refactoring, quality, utils modules
- **Quality gates**: All items pass ruff, mypy, pytest
