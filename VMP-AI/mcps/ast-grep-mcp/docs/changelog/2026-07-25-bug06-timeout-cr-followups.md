# BUG-06 Timeout Fix Code-Review Follow-ups (2026-07-25)

## Summary

Closed 12 of the 29 BUG-06 code-review findings from the `_process_parallel_enrichment`
timeout fix session (2026-07-24). Work focused on correctness of the `CancelledBeforeStartError`
distinction, adopting the shared `map_with_per_item_timeout` helper in the last remaining
site (ranker), type widening to enable sub-second test timeouts, and cleanup of the
`error_message` string-smuggling pattern.

**Status**: ✅ Complete  
**Date**: 2026-07-25  
**Commits**: `2f6cf36`, `b366844`, `77f187f`, `2adc6c0`, `df5dcdf`  
**Test Results**: 1,754 passed, 0 failed (no regressions)

## Fixed Issues

### Never-started enrichment disambiguation (CR-07 / CR-28)

| Item | Change | Files |
|---|---|---|
| CR-07 | Added `CancelledBeforeStartError(WaitTimeoutError)` to `utils/futures.py`; `_wait_for_item` uses `future.cancel()` return to distinguish PENDING ("starved") from RUNNING ("timed out") futures | `utils/futures.py` |
| CR-07 | `_handle_enrichment_error` branches on `CancelledBeforeStartError` → logs `{op}_never_started` (warning) and sets field to "Cancelled before start"; `WaitTimeoutError` keeps `{op}_timeout` (error) | `analysis_orchestrator.py` |
| CR-28 | `test_all_hung_candidates_each_marked_timed_out` no longer pins exact label for never-started candidates; asserts `"error" in c` instead | `test_orchestrator_optimizations.py` |

Regression tests: `TestCancelledBeforeStartDisambiguation` (2 tests) in `test_futures.py`.

### Ranker parallel scoring adoption (CR-10)

| Item | Change | Files |
|---|---|---|
| CR-10 | `DuplicationRanker._score_candidates_parallel` rewritten to use `map_with_per_item_timeout`. Removes the last `ThreadPoolExecutor + as_completed` (no timeout) idiom in the pipeline. On timeout/error, candidate receives fallback score `0.0` (lowest priority) with a warning log. | `ranker.py` |

Regression test: `TestParallelScoringTimeout` (monkeypatches to 0.2s timeout for fast test completion).

### Float timeout and zero guard (CR-11 / CR-18)

| Item | Change | Files |
|---|---|---|
| CR-18 | `timeout_per_candidate` widened from `Optional[int]` to `Optional[float]` across `AnalysisConfig`, all `analysis_orchestrator.py` method signatures, `coverage.py`, and `tools.py`. Enables sub-second timeouts in tests. | `config.py`, `analysis_orchestrator.py`, `coverage.py`, `tools.py` |
| CR-11 | `_resolve_timeout` now guards `timeout_per_candidate <= 0` — treats as `None` (returns default 30s). Prevents `future.result(timeout=0)` from instantly failing running futures. | `analysis_orchestrator.py` |

### Error message cleanup (CR-14)

| Item | Change | Files |
|---|---|---|
| CR-14 | `_handle_enrichment_error` signature changed from `error_message: Optional[str]` to `timeout_seconds: Optional[float]`. The `on_error` callback passes the numeric timeout directly; the log field is now a number, not a string. Format uses `:g` to strip trailing zeros (`1.0` → `"1s"`, `0.2` → `"0.2s"`). | `analysis_orchestrator.py` |

### Docstring accuracy (CR-27)

| Item | Change | Files |
|---|---|---|
| CR-27 | `_parallel_enrich` docstring for `timeout_per_candidate` updated to accurately describe wait-based semantics: wait clock starts when the loop reaches each future (not when the candidate started executing); users directed to `total_timeout_seconds` for a hard wall-clock cap. | `analysis_orchestrator.py` |

### Test cleanup (CR-19 deferred / CR-20 / CR-21 / CR-22 / CR-23 / CR-29)

| Item | Change | Files |
|---|---|---|
| CR-20 | Hoisted `import threading` and `import time` to module level in `test_orchestrator_optimizations.py`; removed 6 inline local imports | `test_orchestrator_optimizations.py` |
| CR-21 | `EXPECTED_TIMEOUT_ERROR = f"Operation timed out after {TIMEOUT_SECONDS}s"` class constant in `TestPerCandidateTimeoutEnforcement` and `TestSequentialPathTimeoutEnforcement` | `test_orchestrator_optimizations.py` |
| CR-22 | Named `HUNG_WORKER_SAFETY_NET_SECONDS = 30` and `ELAPSED_BOUND_SECONDS = 10` constants in both classes; all literals replaced | `test_orchestrator_optimizations.py` |
| CR-23 | `ELAPSED_BOUND_SECONDS = 10` with comment explaining the bound relative to the 300s global deadline | `test_orchestrator_optimizations.py` |
| CR-18 + CR-29 | `TIMEOUT_SECONDS` reduced 1 → 0.2 in `TestPerCandidateTimeoutEnforcement` and `TestSequentialPathTimeoutEnforcement`, cutting ~4s from the unit run and reducing CI flake window from ~2s to ~0.4s | `test_orchestrator_optimizations.py` |

CR-19 (extract `_run` helper in test class) remains open — deferred as low-value cosmetic refactor.

## Remaining Open BUG-06-CR Items

| ID | Priority | Description |
|---|---|---|
| CR-17 | P4 | Fresh ThreadPoolExecutor per stage per call — "no action" documented (per-call pools are the defensible choice under the abandonment strategy) |
| CR-19 | P4 | Two timeout tests duplicate scaffolding — deferred (cosmetic, low value) |
