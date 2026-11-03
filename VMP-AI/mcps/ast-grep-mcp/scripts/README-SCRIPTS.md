# Scripts Reference

Utility scripts for analysis, migration, benchmarking, code generation, repomix management, and DevOps verification. **41 files** (17 Python, 6 TypeScript, 11 Shell).

## Table of Contents

- [Dataflow Overview](#dataflow-overview)
- [Analysis](#analysis)
- [Benchmarking](#benchmarking)
- [Migration & Fixes](#migration--fixes)
- [Code Generation](#code-generation)
- [Repomix](#repomix)
- [DevOps & Verification](#devops--verification)
- [Shared Libraries](#shared-libraries)
- [Conventions](#conventions)

---

## Dataflow Overview

### Analysis Pipeline

```
                                  ast_grep_mcp.features.*
                                           |
                      +--------------------+--------------------+
                      |                    |                    |
               complexity.tools      quality.tools     deduplication.tools
               (analyze_complexity   (enforce_standards (find_duplication
                detect_code_smells)   detect_security    benchmark_dedup)
                                      detect_orphans)
                      |                    |                    |
                      +--------------------+--------------------+
                                           |
                                  run_all_analysis.py
                                   (orchestrator)
                                           |
                                     Console output
                                   (summary + details)

     Standalone analysis:
     scan_complexity_offenders.py ----> complexity.metrics
                                        complexity.analyzer
                                           |
                                     Markdown table
                                   (for BACKLOG.md)

     analyze_violations.py -----------> complexity.tools
     list_complexity_violations.py ---> complexity.tools
     analyze_analyticsbot.py ---------> complexity + quality + security tools
                                           |
                                  analysis_output_helpers.py
                                   (formatting utilities)
```

### Migration Pipeline

```
     Source .py files
           |
           v
     migrate_print_to_logger.py ----+----> migration_common.py
           |                        |        (read_lines, write_lines,
           v                        |         remove_line_ranges,
     migrate_prints_smart.py -------+         MIGRATION_ERROR_TEST_FILES)
           |                        |
           v                        +----> import_helpers.py
     fix_imports.py                          (scan_import_state,
     fix_import_orphans.py                    ensure_import_present,
     fix_migration_errors.py                  CONSOLE_IMPORT_STMT)
           |
           v
     Migrated .py files
     (print -> console_logger)
```

### Repomix Regeneration Chain

```
     repomix-regen.sh (master orchestrator)
           |
           | 1. Clean all existing artifacts
           |
           +---> token-tree.sh
           |       Output: docs/repomix/token-tree.txt
           |
           +---> repo-compressed.sh
           |       Output: docs/repomix/repo-compressed.xml
           |
           +---> repomix.sh (lossless)
           |       Output: docs/repomix/repomix.xml
           |
           +---> generate-repomix-docs.sh
           |       Output: docs/repomix/repomix-docs.xml
           |       Config: repomix.config.json + repomix-docs.config.json
           |
           +---> generate-repomix-git-ranked.sh
           |       Output: docs/repomix/repomix-git-ranked.xml
           |       Env:    REPOMIX_GIT_RANKED_INCLUDE_LOGS_COUNT (default 200)
           |
           +---> generate-diff-summary.sh
                   Output: docs/repomix/gitlog-top20.txt
```

### Magic Number Categorization Pipeline

```
     ESLint JSON report (--eslint-json) OR live ESLint run
           |
           v
     categorize-magic-numbers.ts
           |
           +---> gatherOccurrences()
           |       Parse no-magic-numbers violations
           |       Extract literal, numeric value, context lines
           |       Build token set per occurrence (Jaccard-ready)
           |
           +---> gatherConstants()
           |       Scan *constants*.ts, *constants*.py, etc. via rg
           |       Extract UPPER_CASE = <number> definitions
           |       Deduplicate by file:line:name:value
           |
           +---> summarizeGroups()
           |       Group occurrences by literal value
           |       Score each constant candidate:
           |         - Exact value match (numeric equality)
           |         - Semantic score (Jaccard similarity of tokens)
           |       Cluster peer occurrences (UnionFind + Jaccard)
           |
           v
     docs/magic-number-categories.json
       { summary, literals[]: { occurrences, exactConstantMatches,
         semanticConstantMatches, peerClusters } }
```

### Deployment & Verification Pipeline

```
     deploy-traditional-server.sh
           |
     +-----+-----+----------+
     |           |           |
   --setup    --update   --rollback
     |           |           |
     v           v           v
   Init       Deploy      Revert
   infra      code        backup
     |           |           |
     +-----------+-----------+
                 |
                 v
     verify-bugfixes.sh
           |
     +-----+-----+----------+----------+
     |           |           |          |
   --pre      --post     --smoke   --rollback
     |           |           |          |
     v           v           v          v
   Pre-deploy  Post-deploy  Smoke    Rollback
   checks      checks       tests    validation
```

---

## Analysis

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `run_all_analysis.py` | Master orchestrator for all quality analysis | `src/` (default) or custom path | Console: complexity, smells, security, standards, orphans, duplication summaries |
| `analyze_violations.py` | Functions exceeding complexity thresholds | Python source path | Console: threshold violations (cyclomatic, cognitive, nesting, length) |
| `list_complexity_violations.py` | Detailed complexity metrics per function | Python source path | Console: function-level metrics with threshold flags |
| `scan_complexity_offenders.py` | Markdown table of high-complexity functions | 7 hardcoded source modules | Markdown table for BACKLOG.md (`--all` for all functions) |
| `analyze_analyticsbot.py` | Analysis on sibling AnalyticsBot project | AnalyticsBot source | Console via `analysis_output_helpers` formatting |
| `analyze-duplicates.py` | Parse scan reports for exact duplicates | Scan report files | Console: duplicate blocks with file locations |
| `schema-graph-builder.py` | Schema.org entity extraction and knowledge graph | HTML/JSON source files | Knowledge graph; entity ID validation |
| `find_duplication.sh` | Shell wrapper for Python duplication detector | Language, construct type, similarity threshold | Console: duplication results |
| `find_large_classes.sh` | Find TypeScript classes by size/method count | TypeScript source path | Console: class metrics |

### Key Invocations

```bash
uv run python scripts/run_all_analysis.py [src_path]
uv run python scripts/scan_complexity_offenders.py --all
uv run python scripts/analyze_violations.py src/
```

---

## Benchmarking

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `run_benchmarks.py` | Orchestrate benchmarks with regression detection | `--save-baseline`, `--check-regression`, `--output` | `benchmark_report.md`, `tests/benchmark_baseline.json` |
| `benchmark_batch_coverage.py` | Dedup coverage on batch sizes 10-100 | CLI args via argparse | Console: coverage metrics per batch size |
| `benchmark_parallel_enrichment.py` | Sequential vs parallel enrichment comparison | Dedup candidates | Console: timing comparison |

**Regression threshold**: >10% slowdown from baseline triggers failure.

```bash
uv run python scripts/run_benchmarks.py --save-baseline
uv run python scripts/run_benchmarks.py --check-regression
```

---

## Migration & Fixes

Scripts for converting `print()` calls to structured `console_logger` and fixing resulting issues.

| Script | Purpose | Phase |
|--------|---------|-------|
| `migrate_print_to_logger.py` | Primary print-to-logger migrator | 1 - Initial migration |
| `migrate_prints_smart.py` | Second-pass smart migration (avoids nested calls) | 2 - Cleanup pass |
| `fix_imports.py` | Add missing `console_logger` imports | 3 - Import fix |
| `fix_import_orphans.py` | Remove orphaned closing parens from imports | 3 - Import fix |
| `fix_migration_errors.py` | Fix syntax errors in test files | 3 - Import fix |
| `replace-magic.sh` | Preview-first magic value replacement | Standalone |
| `fix-types.ts` | Install `@types/node`, run typecheck | Standalone |

### Shared Libraries

| Module | Exports | Used By |
|--------|---------|---------|
| `migration_common.py` | `MIGRATION_ERROR_TEST_FILES`, `read_lines()`, `write_lines()`, `remove_line_ranges()` | `fix_migration_errors`, `fix_import_orphans` |
| `import_helpers.py` | `CONSOLE_IMPORT_STMT`, `scan_import_state()`, `compute_import_insert_index()`, `ensure_import_present()` | `migrate_print_to_logger`, `migrate_prints_smart` |

### Execution Order

```bash
# Phase 1: Initial migration (dry-run first)
uv run python scripts/migrate_print_to_logger.py --dry-run src/
uv run python scripts/migrate_print_to_logger.py src/

# Phase 2: Smart cleanup
uv run python scripts/migrate_prints_smart.py src/

# Phase 3: Fix import errors
uv run python scripts/fix_imports.py
uv run python scripts/fix_import_orphans.py
uv run python scripts/fix_migration_errors.py
```

---

## Code Generation

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `generate-http-status-constants.ts` | HTTP status constants from YAML definitions | YAML definition file | TypeScript + Python constant files |
| `categorize-magic-numbers.ts` | Categorize magic numbers from ESLint output | ESLint JSON report (or live run) | `docs/magic-number-categories.json` |

### categorize-magic-numbers.ts

Parses ESLint `no-magic-numbers` violations, scans existing constant files (`*constants*.ts`, `*constants*.py`), and produces a categorized report matching magic numbers to potential constant replacements.

**Key algorithms**:
- **Token extraction**: Splits identifiers (camelCase, snake_case), filters stopwords, builds token sets from file paths + context lines
- **Jaccard similarity**: Measures semantic overlap between occurrence tokens and constant definition tokens
- **UnionFind clustering**: Groups peer occurrences by token similarity (configurable threshold)
- **Candidate scoring**: Ranks constants by exact value match + semantic score

**CLI options**:
```bash
node --strip-types scripts/categorize-magic-numbers.ts \
  --eslint-json <path>         # Existing ESLint JSON (omit to run live)
  --out <path>                 # Output path (default: docs/magic-number-categories.json)
  --context <n>                # Context lines per occurrence (default: 2)
  --max-candidates <n>         # Top matches per literal group (default: 5)
  --min-semantic-score <0..1>  # Minimum score to keep (default: 0.2)
  --peer-threshold <0..1>      # Clustering similarity threshold (default: 0.35)
```

---

## Repomix

### Configuration

| File | Purpose |
|------|---------|
| `repomix/repomix.config.json` | Base config: output style, file includes/excludes, security checks, token budgets |
| `repomix/repomix-docs.config.json` | Documentation-only extraction config |

### Scripts

| Script | Output | Purpose |
|--------|--------|---------|
| `repomix/repomix-regen.sh` | All artifacts | Master orchestrator (cleans + rebuilds all) |
| `repomix/repomix.sh` | `docs/repomix/repomix.xml` | Lossless full-repo pack |
| `repomix/repo-compressed.sh` | `docs/repomix/repo-compressed.xml` | Lossy-compressed pack (~70% smaller) |
| `repomix/generate-repomix-docs.sh` | `docs/repomix/repomix-docs.xml` | Docs-only extraction |
| `repomix/generate-repomix-git-ranked.sh` | `docs/repomix/repomix-git-ranked.xml` | Files ranked by git activity |
| `repomix/token-tree.sh` | `docs/repomix/token-tree.txt` | Token distribution tree |
| `repomix/generate-diff-summary.sh` | `docs/repomix/gitlog-top20.txt` | Top 20 changed files + recent commits |

### Invocation

```bash
# Regenerate all repomix artifacts
scripts/repomix/repomix-regen.sh

# Individual generation
scripts/repomix/token-tree.sh
scripts/repomix/repomix.sh
```

---

## DevOps & Verification

| Script | Purpose | Modes/Flags |
|--------|---------|-------------|
| `deploy-traditional-server.sh` | OS-aware deployment (macOS/Linux) | `--setup`, `--update`, `--rollback` |
| `verify-bugfixes.sh` | Pre/post-deployment test suite | `--pre`, `--post`, `--smoke`, `--rollback`, `all` |
| `verify-setup.ts` | Environment setup checks | Reports pass/fail for Node, npm, uv, ast-grep, Python, Doppler |
| `validate-permissions.ts` | Executable permission validation | `--fix` to auto-correct |
| `run-python-tests.sh` | pytest runner with interpreter resolution | Resolves Python, sets env isolation |
| `warm-doppler-cache.sh` | Doppler secrets cache management | Creates backup, validates cache |
| `cleanup-error-logs.ts` | Log rotation with retention policies | 7d active, 30d archive, gzip compression |
| `backfill-skill-spans.py` | OTEL telemetry span reconstruction | `--skill`, `--agent`, `--sessions`, `--write` (dry-run default) |

### backfill-skill-spans.py

Reconstructs missing OTEL plugin spans from agent-cache and trace-ctx data.

```bash
uv run python scripts/backfill-skill-spans.py \
  --skill review --agent code-reviewer --category review \
  --sessions abc123,def456 --write
```

**Data sources**: `~/.claude/agent-cache/`, `~/.claude/telemetry/trace-ctx/`
**Output**: `~/.claude/telemetry/traces-{DATE}.jsonl` (OTEL-compatible spans)
**Idempotent**: Checks `backfill.source` + `plugin.name` to skip duplicates.

---

## Shared Libraries

| Module | Purpose | Consumers |
|--------|---------|-----------|
| `analysis_output_helpers.py` | `print_section_header()`, `count_by_key()`, `log_count_breakdown()` | `analyze_analyticsbot.py` |
| `migration_common.py` | File I/O, line range removal, test file path list | `fix_migration_errors.py`, `fix_import_orphans.py` |
| `import_helpers.py` | Import detection, insertion, `CONSOLE_IMPORT_STMT` | `migrate_print_to_logger.py`, `migrate_prints_smart.py` |

---

## Conventions

- **Python scripts**: `snake_case.py`, run via `uv run python scripts/<name>.py`
- **Shell scripts**: `kebab-case.sh`, all use `set -euo pipefail`
- **TypeScript scripts**: `kebab-case.ts`, run via `node --strip-types` or `npx tsx`
- **CLI args**: Python uses `argparse`; TypeScript uses manual `parseArgs`
- **Feature imports**: Analysis/benchmark scripts import directly from `ast_grep_mcp.features.*.tools`
- **Dual import pattern**: Migration shared libs use try/except for `scripts.` prefix vs direct import
- **Cross-project refs**: TypeScript scripts may import from `../sidequest/` and `../api/`
