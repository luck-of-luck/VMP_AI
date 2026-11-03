# Deduplication Precision Filters (2026-03-08)

**Commit:** `6a27e23` feat(dedup): add precision filters to eliminate false-positive duplicate groups
**Follow-up:** `c412c78` fix(dedup): resolve high/medium reviewer findings in precision filters

## Summary

Implemented precision filters in `DuplicationDetector` to eliminate false-positive duplicate detection results. An investigation of 5 groups reported by `find_duplication` (sim >= 0.82) revealed they were all false positives or low-value for refactoring:
- Trivial constructors (`__init__` assigning a single parameter)
- Intentionally parallel language-specific formatters (e.g., `to_python()` vs `to_typescript()`)
- Thin semantic wrappers delegating to a shared helper (e.g., `error()` and `warning()` both calling `_log()`)
- Strategy pattern implementations with shared boilerplate
- Below-threshold line savings (<20 lines)

## Implemented Filters

### New Methods in `DuplicationDetector`

1. **`_apply_precision_filters`** — Orchestrates all filters, logs removal count
2. **`_is_trivial_constructor_group`** — Flags groups where all members are short constructors (<=10 lines)
   - Constant: `DetectorDefaults.TRIVIAL_INIT_MAX_LINES = 10`
3. **`_is_delegation_wrapper_group`** — Identifies thin wrappers delegating to `self._xxx()` / `super().xxx()`
   - Constant: `DetectorDefaults.DELEGATION_MAX_BODY_STATEMENTS = 2` (max statements in wrapper body)
4. **`_is_parallel_formatter_group`** — Detects parallel formatters with different prefixes (to_/from_/as_/into_)
   - Constant: `DetectorDefaults.PARALLEL_FORMATTER_PREFIXES = ("to_", "from_", "as_", "into_")`
5. **`_meets_min_savings`** — Enforces minimum line savings threshold
   - Constant: `DetectorDefaults.MIN_LINE_SAVINGS = 20`
6. **`_code_line_count`** — Helper to consolidate duplicated `len(code.split("\n"))` pattern (DRY refactor)

### New Constants in `DetectorDefaults`

```python
CONSTRUCTOR_NAMES = frozenset({"__init__", "constructor", "__new__", "init"})
TRIVIAL_INIT_MAX_LINES = 10
DELEGATION_MAX_BODY_STATEMENTS = 2
MIN_LINE_SAVINGS = 20
PARALLEL_FORMATTER_PREFIXES = ("to_", "from_", "as_", "into_")
```

### Compiled Regex Patterns (class-level, reused)

```python
_RE_FUNC_NAME = re.compile(r"^\s*(?:async\s+)?(?:def|function)\s+(\w+)")
_RE_JS_VAR_NAME = re.compile(r"^\s*(?:const|let|var)\s+(\w+)\s*=")
_RE_CALL_EXPR = re.compile(r"^(self\.\w+(?:\.\w+)*|super\(\)\.\w+(?:\.\w+)*|\w+)\(")
```

### Prefix/Token Constants (class-level tuples)

```python
_SIGNATURE_PREFIXES = ("def ", "async def ", "function ", "return ")
_CLOSING_TOKENS = ("}", "pass")
_NON_BODY_PREFIXES = ("class ", "@", "#", "//", "/*")
```

## Integration

Filters are applied in `_run_detection` between `group_duplicates` and `generate_refactoring_suggestions`:

```python
raw_groups = self.group_duplicates(all_matches, min_similarity, min_lines)
duplication_groups = self._apply_precision_filters(raw_groups)  # NEW
suggestions = self.generate_refactoring_suggestions(duplication_groups, construct_type)
```

## Test Coverage

Added 32 comprehensive tests across 5 test classes:
- `TestTrivialConstructorFilter` — 5 tests covering short init detection and edge cases
- `TestDelegationWrapperFilter` — 3 tests for thin wrapper heuristics
- `TestParallelFormatterFilter` — 3 tests for parallel formatter variants
- `TestMinSavingsFilter` — 4 tests for line savings thresholds
- `TestApplyPrecisionFilters` — 2 integration tests verifying all 5 false-positive patterns are eliminated while legitimate duplicates are preserved

All 90 tests pass (58 existing + 32 new).

## Result

All 5 false-positive groups from the investigation are now filtered out. The detector becomes more precise and requires less manual review of results.

## Deferred

**Strategy pattern filter** — Low-priority per investigation notes. Only candidate (Group 5 from investigation) would save ~18 lines with minor signature mismatch; deemed over-engineering for marginal benefit.
