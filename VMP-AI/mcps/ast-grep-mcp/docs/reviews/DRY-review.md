# DRY Review — Shared Utility Adoption Gaps (2026-03-08)

Audit of recently extracted shared utilities against the full codebase. Identifies duplicate patterns that should adopt the shared implementations.

**Shared utilities audited:**
- `utils/backup.py` — `get_file_hash`, `resolve_backup_dir`, `copy_file_to_backup`, `restore_file_from_backup`
- `utils/tool_context.py` — `tool_context`, `async_tool_context`
- `utils/text.py` — `indent_lines`, `read_file_lines`, `write_file_lines`
- `constants.py` — `FilePatterns.normalize_excludes()`

---

## 1. `cross_language/tools.py:_run_tool()` reimplements `tool_context`

**Priority: High** | **Impact: ~20 lines removed, pattern alignment with all other tool modules**

`cross_language/tools.py:40-57` defines `_run_tool()` — a manual try/except wrapper that duplicates `tool_context` exactly: timing via `time.time()`, structured error logging, and `sentry_sdk.capture_exception(e)`. All 5 cross-language tools use it via lambda wrappers (lines 177-335).

```python
# Current (lines 40-57)
def _run_tool(tool_name: str, fn: Callable[[], Dict[str, Any]], start_time: float, log_kwargs: Dict[str, Any]) -> Dict[str, Any]:
    logger = get_logger(f"tool.{tool_name}")
    logger.info("tool_invoked", tool=tool_name, **log_kwargs)
    try:
        result = fn()
        elapsed = round(time.time() - start_time, FormattingDefaults.ROUNDING_PRECISION)
        logger.info("tool_completed", tool=tool_name, execution_time_seconds=elapsed)
        return result
    except Exception as e:
        elapsed = round(time.time() - start_time, FormattingDefaults.ROUNDING_PRECISION)
        logger.error("tool_failed", tool=tool_name, execution_time_seconds=elapsed,
                      error=str(e)[: DisplayDefaults.ERROR_OUTPUT_PREVIEW_LENGTH])
        sentry_sdk.capture_exception(e)
        raise
```

### Fix

Replace `_run_tool()` and all 5 lambda call sites with `tool_context`:

```python
from ast_grep_mcp.utils.tool_context import tool_context

def search_multi_language_tool(...) -> Dict[str, Any]:
    with tool_context("search_multi_language", language=language, pattern=pattern):
        return _search_multi_language_impl(...)
```

Remove: `_run_tool`, `time` import, `sentry_sdk` import, `DisplayDefaults` import, all `start_time = time.time()` lines at each call site.

---

## 2. Hardcoded exclude lists — 8 files should use `FilePatterns`

**Priority: High** | **Impact: Single source of truth for exclude patterns across 8+ files**

`constants.py:FilePatterns.DEFAULT_EXCLUDE` and `FilePatterns.normalize_excludes()` exist but 8 files still hardcode their own exclude lists.

### 2a. `deduplication/detector.py`

**Lines 38, 78-84:**
```python
_MANDATORY_ENV_EXCLUDE_PATTERNS = ["site-packages", ".venv", "venv", "virtualenv"]

def _build_exclude_patterns(self, exclude_patterns):
    result = ["site-packages", "node_modules", ".venv", "venv", "vendor"] if exclude_patterns is None else list(exclude_patterns)
```

**Fix:** Replace with `FilePatterns.normalize_excludes(exclude_patterns)`. Remove `_MANDATORY_ENV_EXCLUDE_PATTERNS`. The `_build_exclude_patterns` method body becomes a one-liner delegating to the shared method. Note: detector uses substring-match strings (not globs), so verify `normalize_excludes` output format is compatible or convert at the call boundary.

### 2b. `documentation/sync_checker.py`

**Lines 259-267, 330:**
```python
_DEFAULT_EXCLUDE_PATTERNS = [
    "**/node_modules/**", "**/__pycache__/**", "**/venv/**",
    "**/.venv/**", "**/dist/**", "**/build/**", "**/.git/**",
]
# ...
exclude_dirs = ["node_modules", ".git", "venv", ".venv"]
```

**Fix:** Replace `_DEFAULT_EXCLUDE_PATTERNS` with `FilePatterns.DEFAULT_EXCLUDE`. Replace inline `exclude_dirs` with names derived from `FilePatterns`. The `_find_source_files` method already calls `FilePatterns.normalize_excludes()` at line 330 — remove the redundant `_DEFAULT_EXCLUDE_PATTERNS` constant.

### 2c. `documentation/readme_generator.py`

**Line 122:**
```python
_SKIP_DIRS = {"node_modules", ".git", "venv", "__pycache__", "dist", "build"}
```

**Fix:** Derive from `FilePatterns.DEFAULT_EXCLUDE`:
```python
_SKIP_DIRS = FilePatterns.skip_dir_names()  # or inline extraction
```
If `skip_dir_names()` doesn't exist, add a classmethod that extracts bare directory names from the glob patterns (strip `**/` and `/**`), or define `FilePatterns.SKIP_DIRS` as a frozenset constant.

### 2d. `documentation/api_docs_generator.py`

**Line 514:**
```python
_SKIP_DIRS = {"node_modules", ".git", "venv", "__pycache__", "dist", "build"}
```

**Fix:** Same as 2c — identical set. Both should reference a shared constant.

### 2e. `quality/security_scanner.py`

**Line 381:**
```python
skip_dirs = ["node_modules", "__pycache__", "venv", ".venv", "dist", "build"]
```

**Fix:** Replace with shared constant (same pattern as 2c/2d).

### 2f. `condense/estimator.py`

**Line 127:**
```python
skip_dirs = {"dist", "build", "node_modules", "__pycache__", ".git", ".venv", "venv"}
```

**Fix:** Replace with shared constant.

### 2g. `core/executor.py`

**Line 165:**
```python
return dirname in ["node_modules", "venv", ".venv", "build", "dist"]
```

**Fix:** Replace inline list with shared constant in `_should_skip_directory()`.

### 2h. `models/orphan.py`

**Lines 188-198:**
```python
exclude_patterns: List[str] = field(
    default_factory=lambda: [
        "**/node_modules/**", "**/__pycache__/**", "**/.git/**",
        "**/dist/**", "**/build/**", "**/.venv/**", "**/venv/**",
    ]
)
```

**Fix:** Replace default factory with `default_factory=lambda: list(FilePatterns.DEFAULT_EXCLUDE)`.

### Implementation strategy

Add a `FilePatterns.SKIP_DIR_NAMES` frozenset to `constants.py` for the bare-name use cases (2c-2g):

```python
class FilePatterns:
    DEFAULT_EXCLUDE = [...]  # existing glob patterns

    SKIP_DIR_NAMES: frozenset[str] = frozenset(
        p.strip("*").strip("/")
        for p in DEFAULT_EXCLUDE
        if p.startswith("**/") and p.endswith("/**")
    )
```

Then each hardcoded set/list becomes `FilePatterns.SKIP_DIR_NAMES`.

---

## 3. Manual `read_file_lines` / `write_file_lines` — 3 files

**Priority: Medium** | **Impact: Consistent error handling and encoding across file I/O**

### 3a. `cross_language/polyglot_refactoring.py:129-130`

```python
with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
    lines = f.readlines()
```

**Note:** This file already imports `read_file_lines` (line 22) but doesn't use it at line 129. Fix: `lines = read_file_lines(file_path)`. Caveat: the current code uses `errors="ignore"` — verify `read_file_lines` handles encoding errors equivalently or add an `errors` parameter.

### 3b. `refactoring/renamer.py:321-323`

```python
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()
    lines = content.split("\n")
```

**Fix:** `lines = read_file_lines(file_path)`. Add import.

### 3c. `quality/fixer.py:163-166`

```python
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()
lines = content.splitlines(keepends=True)
```

**Fix:** `lines = read_file_lines(file_path)`. Note: fixer uses `splitlines(keepends=True)` which preserves line endings — verify `read_file_lines` (which uses `readlines()`) preserves endings equivalently. Both do, so this is a safe replacement.

### 3d. `documentation/sync_checker.py:236-237`

```python
with open(file_path, "r", encoding="utf-8") as f:
    lines = f.read().split("\n")
```

**Fix:** `lines = read_file_lines(file_path)`. Add import.

---

## 4. Redundant re-timing inside `tool_context`

**Priority: Low** | **Impact: Cleaner tool functions, ~2 lines per tool**

Multiple tool modules use `tool_context` correctly but then manually recalculate elapsed time inside the context block. The context manager already computes timing — these tools should either use the yielded `start_time` or drop the redundant calculation.

### Affected files

| File | Tool count | Pattern |
|------|-----------|---------|
| `condense/tools.py` | 6 tools (lines 68-218) | `start = time.time()` before context, `elapsed = time.time() - start` inside |
| `documentation/tools.py` | 5 tools (lines 153-347) | Same pattern |
| `schema/tools.py` | 9 tools (lines 32-287) | Same pattern (async) |
| `quality/tools.py` | Multiple tools | Same pattern |

### Fix

Option A — Remove manual timing entirely (recommended if timing is only for the log line that `tool_context` already emits):

```python
# Before
start = time.time()
with tool_context("tool_name"):
    result = do_work()
    elapsed = time.time() - start
    logger.info("done", elapsed=elapsed)
    return result

# After
with tool_context("tool_name"):
    return do_work()
```

Option B — If the tool needs `elapsed` for its return dict, use the yielded start time:

```python
with tool_context("tool_name") as ctx:
    result = do_work()
    result["elapsed"] = round(time.time() - ctx, 3)
    return result
```

Verify `tool_context` yields `start_time` (check `utils/tool_context.py` API).

---

## 5. Backup timestamp formatting — repeated 3x

**Priority: Low** | **Impact: 3 lines consolidated into 1 helper**

The pattern `datetime.now().strftime("%Y%m%d-%H%M%S-%f")[: -FormattingDefaults.TIMESTAMP_MS_TRIM]` appears in:

| File | Line(s) |
|------|---------|
| `rewrite/backup.py` | 21, 50 |
| `deduplication/applicator_backup.py` | 170 |

### Fix

Add to `utils/backup.py`:

```python
def generate_backup_timestamp() -> str:
    """Generate a formatted timestamp for backup IDs."""
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f")[: -FormattingDefaults.TIMESTAMP_MS_TRIM]
```

Then each call site becomes:
```python
from ast_grep_mcp.utils.backup import generate_backup_timestamp, resolve_backup_dir

timestamp = generate_backup_timestamp()
backup_id, backup_dir = resolve_backup_dir("backup", timestamp, backup_base_dir)
```

---

## Summary

| # | Area | Priority | Files | Est. lines saved |
|---|------|----------|-------|-----------------|
| 1 | `_run_tool` → `tool_context` | High | 1 | ~20 |
| 2 | Hardcoded excludes → `FilePatterns` | High | 8 | ~40 |
| 3 | Manual file I/O → `read_file_lines` | Medium | 4 | ~12 |
| 4 | Redundant re-timing in `tool_context` | Low | 4 | ~30 (2/tool × 20 tools) |
| 5 | Timestamp formatting helper | Low | 3 | ~6 |

**Total estimated:** ~108 lines removed/consolidated across 16 files.
