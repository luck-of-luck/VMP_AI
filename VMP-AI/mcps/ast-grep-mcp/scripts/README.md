# Scripts

Utility scripts for analysis, migration, benchmarking, code generation, and repomix management.

## Analysis

| Script | Description |
|--------|-------------|
| `run_all_analysis.py` | Runs complete analysis suite (complexity, smells, security, standards, orphans, duplication, benchmarks) and prints summary. |
| `analyze_violations.py` | Scans Python codebase for functions exceeding complexity thresholds (cyclomatic, cognitive, nesting, length). |
| `analyze_analyticsbot.py` | Runs complexity, smell, and security analysis on the AnalyticsBot project. |
| `analyze-duplicates.py` | Parses scan reports to identify exact duplicate code blocks with file locations. |
| `list_complexity_violations.py` | Lists all Python functions exceeding critical complexity thresholds with detailed metrics. |
| `analysis_output_helpers.py` | Formatting utilities (section headers, count breakdowns) used by other analysis scripts. |
| `schema-graph-builder.py` | Extracts Schema.org entities from HTML/JSON, builds a knowledge graph, and validates entity IDs. |
| `find_duplication.sh` | Wrapper for Python duplication detector with configurable language, construct type, and similarity threshold. |
| `find_large_classes.sh` | Finds TypeScript classes by size and method count. |

## Benchmarking

| Script | Description |
|--------|-------------|
| `run_benchmarks.py` | Orchestrates benchmark tests with baseline saving and regression detection (>10% threshold). |
| `benchmark_batch_coverage.py` | Benchmarks dedup coverage detection on candidate batches of varying sizes (10-100). |
| `benchmark_parallel_enrichment.py` | Benchmarks sequential vs parallel enrichment on dedup candidates. |

## Migration & Fixes

| Script | Description |
|--------|-------------|
| `migrate_print_to_logger.py` | Migrates `print()` to console logger calls with dry-run support and change tracking. |
| `migrate_prints_smart.py` | Smart migration of remaining `print()` calls, avoiding nested calls and preserving intent. |
| `migration_common.py` | Common utilities for migration scripts (file paths, read/write, line range removal). |
| `fix_import_orphans.py` | Fixes orphaned closing parentheses and import statements from migration errors. |
| `fix_imports.py` | Adds missing `console_logger` imports to Python files that use it. |
| `fix_migration_errors.py` | Fixes syntax errors in test files from migration (orphaned imports, broken multi-line imports). |
| `import_helpers.py` | Helper functions for managing imports (scan state, insert positions, ensuring presence). |
| `replace-magic.sh` | Preview-first find-and-replace for magic values with constants. Supports literal and regex modes. |
| `fix-types.ts` | Installs `@types/node` if missing and runs `npm run typecheck`. |

## Code Generation

| Script | Description |
|--------|-------------|
| `generate-http-status-constants.ts` | Generates HTTP status constants from YAML definition to TypeScript and Python. |
| `categorize-magic-numbers.ts` | Categorizes magic number literals from ESLint output and generates semantic grouping reports. |

## Repomix

| Script | Description |
|--------|-------------|
| `repomix-regen.sh` | Master regeneration: rebuilds all repomix outputs (compressed, lossless, docs, git-ranked, token tree, gitlog). |
| `generate-repomix.sh` | Generates lossless repomix output of the full repository. |
| `generate-repo-compressed.sh` | Generates lossy-compressed repomix output. |
| `generate-repomix-docs.sh` | Generates docs-only repomix output with doc-specific exclusion patterns. |
| `generate-repomix-git-ranked.sh` | Generates git-ranked repomix output prioritizing recently modified files. |
| `generate-token-tree.sh` | Generates token count tree view showing distribution across files. |
| `generate-sidequest-gitlog.sh` | Generates formatted git log for sidequest module with configurable commit count. |
| `generate-diff-summary.sh` | Generates git log with top N largest tracked files and recent commit history. |
| `repo-compressed.sh` | Alias for `generate-repo-compressed.sh`. |
| `repomix.config.json` | Main repomix config: output style, file includes/excludes, security checks, token budgets. |
| `repomix-docs.config.json` | Config for documentation-only repomix output. |

## DevOps & Verification

| Script | Description |
|--------|-------------|
| `deploy-traditional-server.sh` | OS-aware deployment (setup, update, rollback) with macOS/Linux handling. |
| `verify-bugfixes.sh` | Comprehensive pre/post-deployment, health, and smoke tests with color-coded output. |
| `verify-setup.ts` | Setup verification checks (Node, npm, uv, ast-grep, Python, Doppler) with pass/fail reporting. |
| `validate-permissions.ts` | Validates executable permissions on critical scripts; `--fix` to apply corrections. |
| `run-python-tests.sh` | Resolves Python interpreter and runs pytest with proper environment isolation. |
| `warm-doppler-cache.sh` | Manages Doppler CLI secrets cache with backup creation and validation. |
| `cleanup-error-logs.ts` | Error log cleanup with configurable retention (7d active, 30d archive) and gzip compression. |
