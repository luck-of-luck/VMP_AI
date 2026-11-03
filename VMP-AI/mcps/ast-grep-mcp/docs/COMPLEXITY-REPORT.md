# Complexity Analysis Report

**Date:** 2026-03-09
**Tool:** ast-grep-mcp `analyze_complexity` + `detect_code_smells`
**Scope:** Full repository (227 Python files, 3,919 functions)

## Executive Summary

| Metric | Value |
|---|---|
| Total functions | 3,919 |
| Total files | 227 |
| Functions exceeding thresholds | 201 (5.1%) |
| Avg cyclomatic complexity | 3.42 |
| Avg cognitive complexity | 3.46 |
| Max cyclomatic complexity | 41 |
| Max cognitive complexity | 97 |
| Max nesting depth | 10 |
| Code smells detected | 11 (all low severity) |

**Thresholds:** cyclomatic > 10, cognitive > 15, nesting > 4, length > 50 lines

## Threshold Violations by Category

| Category | Count | % of Total |
|---|---|---|
| Nesting depth | 140 | 69.7% |
| Cognitive complexity | 99 | 49.3% |
| Cyclomatic complexity | 75 | 37.3% |
| Function length | 46 | 22.9% |

Nesting depth is the most common violation, affecting nearly 70% of offending functions.

## Source Code Analysis (src/ only)

53 functions in `src/` exceed thresholds. Breakdown by feature:

| Feature | Offending Functions |
|---|---|
| deduplication | 23 |
| quality | 12 |
| documentation | 9 |
| refactoring | 7 |
| core/other | 1 |
| cross_language | 1 |

### Top 15 src/ Offenders (by cognitive complexity)

| Function | File | Lines | Cyc | Cog | Nest | Len |
|---|---|---|---|---|---|---|
| unknown | quality/fixer.py | 559-594 | 14 | 27 | 4 | 26 |
| unknown | deduplication/coverage.py | 346-383 | 13 | 25 | 6 | 28 |
| unknown | quality/fixer.py | 149-244 | 13 | 24 | 4 | 85 |
| unknown | deduplication/applicator.py | 603-626 | 13 | 24 | 4 | 23 |
| unknown | deduplication/coverage.py | 306-344 | 12 | 24 | 4 | 29 |
| unknown | refactoring/renamer.py | 475-501 | 7 | 24 | 6 | 18 |
| unknown | deduplication/detector.py | 490-513 | 16 | 23 | 4 | 19 |
| unknown | refactoring/renamer.py | 38-122 | 12 | 20 | 6 | 75 |
| unknown | refactoring/renamer.py | 503-539 | 11 | 20 | 5 | 27 |
| unknown | quality/fixer.py | 269-349 | 10 | 19 | 4 | 71 |
| unknown | quality/tools.py | 110-186 | 13 | 18 | 4 | 47 |
| unknown | refactoring/extractor.py | 352-380 | 10 | 18 | 5 | 21 |
| unknown | refactoring/renamer.py | 336-395 | 10 | 18 | 6 | 52 |
| unknown | documentation/changelog_generator.py | 516-551 | 9 | 18 | 4 | 27 |
| unknown | quality/tools.py | 189-252 | 15 | 17 | 5 | 44 |

File paths relative to `src/ast_grep_mcp/features/`.

### Hotspot Files in src/

| Offenders | File |
|---|---|
| 7 | features/quality/tools.py |
| 6 | features/deduplication/applicator.py |
| 5 | features/deduplication/coverage.py |
| 5 | features/refactoring/renamer.py |
| 5 | features/documentation/changelog_generator.py |
| 4 | features/quality/fixer.py |
| 4 | features/deduplication/applicator_post_validator.py |

## Full Repository File Hotspots

| Offenders | File |
|---|---|
| 10 | tests/unit/test_schema_enhancement.py |
| 8 | analyze_codebase.py |
| 7 | scripts/schema-graph-builder.py |
| 7 | tests/scripts/score_test_file.py |
| 7 | tests/unit/test_applicator_backup.py |
| 7 | tests/scripts/detect_fixture_patterns.py |
| 7 | src/ast_grep_mcp/features/quality/tools.py |
| 6 | scripts/migrate_print_to_logger.py |
| 6 | src/ast_grep_mcp/features/deduplication/applicator.py |
| 5 | tests/unit/test_complexity.py |
| 5 | tests/conftest.py |
| 5 | src/ast_grep_mcp/features/deduplication/coverage.py |
| 5 | src/ast_grep_mcp/features/refactoring/renamer.py |
| 5 | src/ast_grep_mcp/features/documentation/changelog_generator.py |
| 5 | tests/unit/test_coverage_detector.py |

## Top 10 Most Complex Functions (full repo)

| File | Lines | Cyc | Cog | Nest | Len | Exceeds |
|---|---|---|---|---|---|---|
| scripts/schema-graph-builder.py | 164-231 | 41 | 97 | 8 | 58 | cyc, cog, nest, len |
| scripts/backfill-skill-spans.py | 66-133 | 27 | 62 | 6 | 63 | cyc, cog, nest, len |
| tests/scripts/track_fixture_metrics.py | 91-117 | 19 | 50 | 8 | 26 | cyc, cog, nest |
| scripts/schema-graph-builder.py | 313-366 | 19 | 49 | 7 | 45 | cyc, cog, nest |
| tests/scripts/score_test_file.py | 189-203 | 10 | 44 | 9 | 14 | cog, nest |
| tests/quality/test_complexity_regression.py | 553-596 | 14 | 43 | 9 | 43 | cyc, cog, nest |
| tests/quality/test_complexity_regression.py | 391-451 | 13 | 40 | 5 | 49 | cyc, cog, nest |
| tests/unit/test_applicator_backup.py | 921-954 | 11 | 40 | 5 | 33 | cyc, cog, nest |
| scripts/schema-graph-builder.py | 233-263 | 11 | 40 | 7 | 22 | cyc, cog, nest |
| tests/unit/test_complexity.py | 608-656 | 20 | 39 | 6 | 40 | cyc, cog, nest |

## Code Smells

11 code smells detected, all **low severity**, all `magic_number` type:

| File | Line | Value | Suggestion |
|---|---|---|---|
| scripts/run_all_analysis.py | 108 | 3 | Extract to named constant |
| scripts/backfill-skill-spans.py | 42 | 8 | Extract to named constant |
| scripts/backfill-skill-spans.py | 105 | 4 | Extract to named constant |
| scripts/backfill-skill-spans.py | 108 | 5 | Extract to named constant |
| scripts/backfill-skill-spans.py | 109 | 4 | Extract to named constant |
| scripts/backfill-skill-spans.py | 119 | 3 | Extract to named constant |
| scripts/backfill-skill-spans.py | 121 | 3 | Extract to named constant |
| scripts/analyze-duplicates.py | 47 | 15 | Extract to named constant |
| scripts/analyze-duplicates.py | 50 | 4 | Extract to named constant |
| scripts/analyze-duplicates.py | 54 | 4 | Extract to named constant |

No high or medium severity smells were detected. Zero instances of: long functions, excessive parameters, deep nesting (class-level), large classes, or excessive methods.

## Recommendations

### Priority 1: Deduplication Feature (23 offenders)
- `applicator.py` (6 offenders): Extract nested conditional logic into helper functions
- `coverage.py` (5 offenders): Reduce nesting in coverage calculation methods (nesting depth 6)
- `applicator_post_validator.py` (4 offenders): 4 functions with nesting > 5

### Priority 2: Quality Feature (12 offenders)
- `tools.py` (7 offenders): Multiple high-cyclomatic tool functions; split into smaller handlers
- `fixer.py` (4 offenders): Lines 149-244 is 85 lines with cyc=13, cog=24; decompose into stages

### Priority 3: Refactoring Feature (7 offenders)
- `renamer.py` (5 offenders): Lines 38-122 (75 lines, nest=6, cog=20); extract rename logic phases
- `extractor.py`: Lines 37-115 (68 lines, nest=5); break up extraction pipeline

### Priority 4: Scripts (not production code)
- `schema-graph-builder.py` has the repo's worst function (cyc=41, cog=97) - consider refactoring if actively maintained

### General Patterns
- **Nesting** is the dominant issue (140/201 violations) - use early returns, guard clauses, and extract-method refactoring
- **Cognitive complexity** correlates with nesting - fixing nesting will reduce cognitive scores
- The `src/` codebase is in reasonable shape overall (53/3919 = 1.4% of functions exceed thresholds)
