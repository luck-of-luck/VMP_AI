# core

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareSourceCode",
  "name": "core",
  "description": "Directory containing 7 code files with 17 classes and 51 functions",
  "programmingLanguage": [
    {
      "@type": "ComputerLanguage",
      "name": "Python"
    }
  ],
  "featureList": [
    "17 class definitions",
    "51 function definitions"
  ]
}
</script>

## Overview

This directory contains 7 code file(s) with extracted schemas.

## Files and Schemas

### `cache.py` (python)

**Classes:**
- `QueryCache` - Line 11
  - LRU cache with TTL for ast-grep query results using cachetools.
  - Methods: __init__, _make_key, get, put, clear (+1 more)

**Functions:**
- `get_query_cache() -> Optional[...]` - Line 108
- `init_query_cache(max_size, ttl_seconds) -> <ast.Constant object at 0x107ca9850>` - Line 115

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.config`, `cachetools`, `hashlib`, `typing`

### `config.py` (python)

**Classes:**
- `ServerSettings` (extends: BaseSettings) - Line 18
  - Server configuration using pydantic-settings for automatic env var loading.
  - Methods: handle_cache_disabled_flag

**Functions:**
- `_load_yaml_config(config_path) -> dict[...]` - Line 74
- `validate_config_file(config_path) -> AstGrepConfig` - Line 93
- `_add_cache_arguments(parser) -> <ast.Constant object at 0x1056929a0>` - Line 112
- `_create_argument_parser() -> argparse.ArgumentParser` - Line 132
- `_try_validate_config(config_path) -> <ast.Constant object at 0x1056a3190>` - Line 177
- `parse_args_and_get_config() -> <ast.Constant object at 0x105693730>` - Line 185

**Key Imports:** `argparse`, `ast_grep_mcp.constants`, `ast_grep_mcp.core.exceptions`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.models.config` (+6 more)

### `exceptions.py` (python)

**Classes:**
- `AstGrepError` (extends: Exception) - Line 8
  - Base exception for all ast-grep MCP server errors.
- `AstGrepNotFoundError` (extends: AstGrepError) - Line 14
  - Raised when ast-grep binary is not found in PATH.
  - Methods: __init__
- `InvalidYAMLError` (extends: AstGrepError) - Line 28
  - Raised when YAML rule is invalid or malformed.
  - Methods: __init__
- `ConfigurationError` (extends: AstGrepError) - Line 47
  - Raised when configuration file is invalid.
  - Methods: __init__
- `AstGrepExecutionError` (extends: AstGrepError) - Line 56
  - Raised when ast-grep command execution fails.
  - Methods: __init__
- `NoMatchesError` (extends: AstGrepError) - Line 72
  - Raised when no matches are found (for test_match_code_rule only).
  - Methods: __init__

**Key Imports:** `ast_grep_mcp.constants`, `typing`

### `executor.py` (python)

**Functions:**
- `_load_custom_languages() -> List[...]` - Line 27
- `get_supported_languages() -> List[...]` - Line 46
- `_execute_subprocess(args, input_text, allow_nonzero) -> subprocess.CompletedProcess[...]` - Line 80
- `run_command(args, input_text) -> subprocess.CompletedProcess[...]` - Line 113
- `_get_language_extensions(language) -> Optional[...]` - Line 153
- `_should_skip_directory(dirname) -> bool` - Line 179
- `_process_file(file, root, lang_extensions, max_size_bytes, logger) -> Tuple[...]` - Line 193
- `_walk_and_classify(directory, lang_extensions, max_size_bytes, logger) -> Tuple[...]` - Line 237
- `filter_files_by_size(directory, max_size_mb, language) -> Tuple[...]` - Line 261
- `_write_language_globs_config(language_globs, tmpdir) -> str` - Line 299
- ... and 8 more functions

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.config`, `ast_grep_mcp.core.exceptions`, `ast_grep_mcp.core.logging`, `ast_grep_mcp.utils.tool_context` (+12 more)

### `logging.py` (python)

**Functions:**
- `configure_logging(log_level, log_file) -> <ast.Constant object at 0x108054730>` - Line 12
- `get_logger(name) -> Any` - Line 54

**Key Imports:** `logging`, `structlog`, `sys`, `typing`

### `sentry.py` (python)

**Functions:**
- `_make_tag_event(service_name) -> Any` - Line 15
- `_sentry_init(dsn, service_name, sentry_env) -> <ast.Constant object at 0x10802f430>` - Line 28
- `init_sentry(service_name) -> <ast.Constant object at 0x107f51f10>` - Line 45

**Key Imports:** `ast_grep_mcp.constants`, `ast_grep_mcp.core.logging`, `os`, `sentry_sdk`, `sentry_sdk.integrations.anthropic` (+1 more)

### `usage_tracking.py` (python)

**Classes:**
- `OperationType` (extends: str, Enum) - Line 42
  - Types of operations tracked for cost estimation.
- `OperationPricing` - Line 73
  - Cost estimation for an operation type.
- `UsageLogEntry` (extends: BaseModel) - Line 186
  - A single usage log entry.
- `UsageStats` (extends: BaseModel) - Line 207
  - Aggregated usage statistics.
- `UsageAlert` (extends: BaseModel) - Line 225
  - A usage alert/warning.
- `AlertThresholds` (extends: BaseModel) - Line 236
  - Configurable alert thresholds.
- `UsageDatabase` - Line 385
  - SQLite-based usage tracking database.
  - Methods: __init__, _get_connection, _init_schema, log_usage, get_stats (+2 more)
- `_TrackedWrapper` - Line 656
  - Callable wrapper that tracks usage metrics for a function.
  - Methods: __init__, __call__
- `_OperationTracker` - Line 744
  - Helper class for track_operation context manager.
  - Methods: _finalize

**Functions:**
- `calculate_operation_cost(operation, files_processed, lines_analyzed, matches_found) -> float` - Line 154
- `_entry_to_params(entry) -> tuple[...]` - Line 270
- `_row_to_log_entry(row) -> UsageLogEntry` - Line 287
- `_parse_stats_row(row, start_time, end_time) -> dict[...]` - Line 318
- `_db_calls_by_tool(conn, start_iso, end_iso) -> Dict[...]` - Line 336
- `_db_calls_by_operation(conn, start_iso, end_iso) -> Dict[...]` - Line 344
- `_db_cost_by_tool(conn, start_iso, end_iso) -> Dict[...]` - Line 352
- `_make_alert(level, metric, value, threshold, fmt) -> UsageAlert` - Line 360
- `_threshold_alert(alerts, metric, value, warning, critical, fmt) -> <ast.Constant object at 0x108062880>` - Line 371
- `get_usage_database() -> UsageDatabase` - Line 592
- ... and 10 more functions

**Key Imports:** `ast_grep_mcp.constants`, `contextlib`, `dataclasses`, `datetime`, `enum` (+11 more)

---
*Generated by Enhanced Schema Generator with schema.org markup*