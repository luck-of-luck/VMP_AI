# 2026-02-28: Analyzer CLI, Syntax Validation, and Quality Fixes

## Added

- Added `--filepath` and `--language` CLI arguments to `analyze_codebase.py` (8c488e4)
- Added `--fix` flag to analyzer for applying safe auto-fixes after enforcement (2fb6ea3)
- Added dedicated TypeScript validation via `tsc` with `--module esnext --target esnext --moduleResolution bundler`, eliminating false positives from `import.meta` and modern TS features (2fb6ea3)
- Switched JavaScript validation from `new Function()` to `node --check` with `.mjs` temp files for proper ESM support (2fb6ea3)
- Added per-rule file exclusions for quality false positives (9b66b52)
- Added `TSC_TIMEOUT_SECONDS` and `TSC_SYNTAX_ERROR_PATTERN` constants (2fb6ea3)

## Fixed

- Fixed `no-empty-catch` rule: replaced unparseable `catch ($E) {}` pattern with kind-based `catch_clause` + `has` field matching (06fe291)
- Fixed ast-grep exit code 1 handling: scan success with error-level diagnostics no longer treated as command failure (06fe291)
- Fixed API mismatches in `analyze_codebase.py` and reporter (80245c9)
- Passed language correctly to `DuplicationDetector` in tools and orchestrator (2fb6ea3)
- Fixed off-by-one in violation line numbers causing wrong-line removal (0e24a7c, 2026-03-01)

## Changed

- Extracted magic numbers to named constants across quality modules (484fdcf)
- Reduced complexity in applicator, schema client, and sentry tool (ed58e44)
- Extracted rule-specific code transforms and removal rules into declarative dicts in `fixer.py` (2fb6ea3)
- Broadened exclude patterns for `node_modules`, `dist`, `build` dirs in analyzer (2fb6ea3)
- Made `pattern` optional in `LintingRule.to_yaml_dict()` to support kind-only rules (06fe291)
