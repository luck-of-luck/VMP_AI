# Deduplication Guide

This guide covers the enhanced code deduplication system in ast-grep-mcp, which provides intelligent detection, analysis, and automated refactoring of duplicate code.

**Last Updated:** 2026-04-22
**Architecture:** Modular (v2.0)
**Code Quality:** ✅ ZERO complexity violations (all deduplication modules refactored)

> **Note:** This guide uses MCP tool names. For direct module imports in custom scripts, see the [Module Architecture](#module-architecture) section.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Tools Reference](#tools-reference)
4. [Refactoring Strategies](#refactoring-strategies)
5. [CLI Usage](#cli-usage)
6. [Workflow Examples](#workflow-examples)
7. [API Reference](#api-reference)
8. [Module Architecture](#module-architecture)
9. [Similarity Algorithm Selection](#similarity-algorithm-selection)
10. [Troubleshooting](#troubleshooting)

---

## Overview

The enhanced deduplication system extends beyond simple duplicate detection to provide:

- **Intelligent Pattern Analysis** - Extracts parameters and identifies variations between duplicates
- **Automated Code Generation** - Creates refactored functions/classes with proper signatures
- **Ranked Prioritization** - Scores candidates by potential savings, complexity, and risk
- **Safe Application** - Preview-first workflow with automatic backups and rollback
- **Multi-file Orchestration** - Atomic changes across multiple files

### Key Components

1. **`find_duplication`** - Detects duplicate functions, classes, and methods
2. **`analyze_deduplication_candidates`** - Ranks duplicates by refactoring value
3. **`apply_deduplication`** - Applies refactoring with validation and backup
4. **`benchmark_deduplication`** - Benchmarks candidate scoring pipelines
5. **`calculate_ast_similarity`** - Structural AST similarity between two code snippets
6. **`calculate_semantic_similarity`** - CodeBERT-based semantic similarity between two code snippets

**Parallel scoring (PA-06):** `DuplicationRanker` accepts `max_workers=N` to score candidates in parallel via `ThreadPoolExecutor`; `max_workers=0` disables parallelism, `None` uses the default pool.

### Supported Languages

Python, TypeScript, JavaScript, Java, Go, Rust, C, C++, Ruby, PHP, and 20+ more via ast-grep.

---

## Quick Start

### Basic Duplication Detection

```python
# Find duplicate functions in a Python project
result = find_duplication(
    project_folder="/path/to/project",
    language="python"
)

# View summary
print(f"Found {result['summary']['duplicate_groups']} duplicate groups")
print(f"Potential savings: {result['summary']['potential_line_savings']} lines")

# Review suggestions
for suggestion in result['refactoring_suggestions']:
    print(f"Group {suggestion['group_id']}: {suggestion['type']}")
    print(f"  {suggestion['suggestion']}")
```

### Ranked Analysis

```python
# Get prioritized candidates
candidates = analyze_deduplication_candidates(
    project_path="/path/to/project",
    language="python",
    min_similarity=0.85
)

# Top candidate
top = candidates['candidates'][0]
print(f"Rank #{top['rank']}: {top['potential_savings']} lines saved")
print(f"Priority: {top['priority_score']:.1%}")
```

### Apply Refactoring

```python
# Preview changes (dry run)
preview = apply_deduplication(
    project_folder="/path/to/project",
    group_id=1,
    refactoring_plan=refactoring_plan,
    dry_run=True
)

# Review the diff
for change in preview['changes_preview']:
    print(f"\n{change['file']}:")
    print(change['diff'])

# Apply for real
result = apply_deduplication(
    project_folder="/path/to/project",
    group_id=1,
    refactoring_plan=refactoring_plan,
    dry_run=False
)

# Save backup_id for potential rollback
backup_id = result['backup_id']
```

---

## Tools Reference

### find_duplication

Detects duplicate code constructs across a project.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_folder` | str | required | Absolute path to project |
| `language` | str | required | Programming language |
| `construct_type` | str | `"function_definition"` | Type to analyze: `function_definition`, `class_definition`, `method_definition` |
| `min_similarity` | float | `0.8` | Minimum similarity threshold (0.0-1.0) |
| `min_lines` | int | `5` | Minimum lines to consider |
| `max_constructs` | int | `1000` | Performance limit (0=unlimited) |
| `exclude_patterns` | list | `["site-packages", "node_modules", ...]` | Paths to exclude |

**Returns:**

```python
{
    "summary": {
        "total_constructs": 150,
        "duplicate_groups": 5,
        "total_duplicated_lines": 120,
        "potential_line_savings": 80,
        "analysis_time_seconds": 1.23
    },
    "duplication_groups": [
        {
            "group_id": 1,
            "similarity_score": 0.92,
            "instances": [
                {
                    "file": "/path/to/file1.py",
                    "lines": "10-25",
                    "code_preview": "def process_data(...)..."
                },
                ...
            ]
        },
        ...
    ],
    "refactoring_suggestions": [
        {
            "group_id": 1,
            "type": "Extract Function",
            "description": "Similar logic detected",
            "duplicate_count": 3,
            "lines_per_duplicate": 15,
            "total_duplicated_lines": 45,
            "locations": [...],
            "suggestion": "Extract common logic..."
        },
        ...
    ]
}
```

---

### analyze_deduplication_candidates

Analyzes duplicates and returns ranked candidates by refactoring value.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_path` | str | required | Absolute path to project |
| `language` | str | required | Programming language |
| `min_similarity` | float | `0.8` | Minimum similarity threshold |
| `include_test_coverage` | bool | `True` | Check test coverage for prioritization |
| `min_lines` | int | `5` | Minimum lines to consider |
| `max_candidates` | int | `100` | Maximum candidates to return |
| `exclude_patterns` | list | default patterns | Paths to exclude |

**Returns:**

```python
{
    "candidates": [
        {
            "rank": 1,
            "group_id": 3,
            "priority_score": 0.85,
            "similarity_score": 0.95,
            "instance_count": 4,
            "potential_savings": 60,
            "avg_lines_per_instance": 20,
            "files_affected": ["/path/to/file1.py", ...],
            "instances": [...],
            "recommendation": "High-value refactoring opportunity..."
        },
        ...
    ],
    "total_groups": 8,
    "total_savings_potential": 200,
    "analysis_metadata": {
        "project_path": "/path/to/project",
        "language": "python",
        "total_constructs_analyzed": 150,
        "analysis_time_seconds": 2.34
    }
}
```

**Ranking Algorithm:**

Priority score is calculated from:
- **Potential line savings** (40% weight)
- **Refactoring ease** based on complexity (30% weight)
- **Risk level** based on test coverage (30% weight)

---

### apply_deduplication

Applies automated refactoring with comprehensive validation.

**Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `project_folder` | str | required | Absolute path to project |
| `group_id` | int | required | Duplication group ID |
| `refactoring_plan` | dict | required | Plan with generated_code, files_affected, strategy, language |
| `dry_run` | bool | `True` | Preview without applying |
| `backup` | bool | `True` | Create backup before changes |
| `extract_to_file` | str | `None` | Target file for extracted code (auto-detect if None) |

**Refactoring Plan Structure:**

```python
refactoring_plan = {
    "language": "python",
    "strategy": "extract_function",
    "generated_code": {
        "extracted_function": "def common_logic(param1, param2):\n    ...",
        "helper_code": ""
    },
    "files_affected": [
        {
            "file": "/path/to/file1.py",
            "changes": [
                {
                    "type": "replace",
                    "start_line": 10,
                    "end_line": 25,
                    "old_code": "...",
                    "new_code": "result = common_logic(x, y)"
                }
            ]
        }
    ]
}
```

**Returns:**

```python
{
    "status": "success",  # or "preview", "failed", "rolled_back"
    "backup_id": "backup-20231115-143022-123",
    "files_modified": ["/path/to/file1.py", "/path/to/file2.py"],
    "changes_preview": [
        {
            "file": "/path/to/file1.py",
            "diff": "--- before\n+++ after\n@@ -10,15 +10,1 @@\n..."
        }
    ],
    "validation": {
        "pre_validation": {"passed": True, "errors": []},
        "post_validation": {"passed": True, "errors": []}
    }
}
```

**Validation Pipeline:**

1. **Pre-validation** - Validates generated code before applying
2. **Application** - Creates backup and applies changes
3. **Post-validation** - Validates modified files
4. **Auto-rollback** - Restores from backup if validation fails

---

## Refactoring Strategies

### extract_function

Extracts common code into a shared function.

**Best for:**
- Similar functions with minor parameter differences
- Repeated logic blocks within functions
- Utility operations used across files

**Example:**

Before:
```python
# file1.py
def process_user(user):
    if not user.email:
        raise ValueError("Email required")
    user.email = user.email.lower()
    user.created_at = datetime.now()
    return user

# file2.py
def process_admin(admin):
    if not admin.email:
        raise ValueError("Email required")
    admin.email = admin.email.lower()
    admin.created_at = datetime.now()
    admin.is_admin = True
    return admin
```

After:
```python
# utils.py
def normalize_entity(entity):
    if not entity.email:
        raise ValueError("Email required")
    entity.email = entity.email.lower()
    entity.created_at = datetime.now()
    return entity

# file1.py
def process_user(user):
    return normalize_entity(user)

# file2.py
def process_admin(admin):
    admin = normalize_entity(admin)
    admin.is_admin = True
    return admin
```

---

### extract_class

Extracts common code into a base class.

**Best for:**
- Similar classes with shared methods
- Classes with identical initialization patterns
- Polymorphic behavior with common base

**Example:**

Before:
```python
class FileExporter:
    def __init__(self, path):
        self.path = path
        self.logger = logging.getLogger(__name__)

    def validate(self):
        if not os.path.exists(os.path.dirname(self.path)):
            raise ValueError("Invalid path")

class DatabaseExporter:
    def __init__(self, path):
        self.path = path
        self.logger = logging.getLogger(__name__)

    def validate(self):
        if not os.path.exists(os.path.dirname(self.path)):
            raise ValueError("Invalid path")
```

After:
```python
class BaseExporter:
    def __init__(self, path):
        self.path = path
        self.logger = logging.getLogger(__name__)

    def validate(self):
        if not os.path.exists(os.path.dirname(self.path)):
            raise ValueError("Invalid path")

class FileExporter(BaseExporter):
    pass

class DatabaseExporter(BaseExporter):
    pass
```

---

### inline

Inlines duplicated code into a single location (for small snippets).

**Best for:**
- Very small code snippets (2-3 lines)
- Code that's clearer when visible at call site
- One-time deduplication where extraction adds complexity

**Note:** This strategy is rarely recommended. The system typically suggests `extract_function` or `extract_class` for most cases.

---

## CLI Usage

> **Note:** The standalone CLI script (`scripts/find_duplication.py`) is not currently shipped in this repo; only the bash wrapper `scripts/find_duplication.sh` exists and it invokes the missing `.py`. The flag reference below documents the intended CLI surface. For working usage today, call the MCP tool `find_duplication` directly (see the Python examples elsewhere in this guide).

### Basic Usage

```bash
# Analyze Python functions
python scripts/find_duplication.py /path/to/project --language python

# Analyze JavaScript classes
python scripts/find_duplication.py /path/to/project --language javascript \
    --construct-type class_definition

# Strict similarity matching
python scripts/find_duplication.py /path/to/project --language python \
    --min-similarity 0.9 --min-lines 10
```

### All Flags

```bash
python scripts/find_duplication.py [project_folder] [options]

Required:
  project_folder          Absolute path to the project folder
  --language, -l          Programming language (python, javascript, etc.)

Detection Options:
  --construct-type, -c    Type to analyze: function_definition (default),
                          class_definition, method_definition
  --min-similarity, -s    Minimum similarity 0.0-1.0 (default: 0.8)
  --min-lines, -m         Minimum lines to consider (default: 5)
  --max-constructs, -x    Max constructs to analyze, 0=unlimited (default: 1000)
  --exclude-patterns, -e  Patterns to exclude (default: site-packages
                          node_modules .venv venv vendor)

Analysis Options:
  --analyze, -a           Use ranked analysis with recommendations
  --max-candidates        Max candidates with --analyze (default: 100)
  --include-test-coverage Check test coverage (default: True)

Output Options:
  --json, -j              Output as JSON
  --detailed, -d          Show diff previews between duplicates
  --no-color              Disable colored output
```

### Examples

```bash
# Basic analysis
python scripts/find_duplication.py /home/user/myproject --language python

# Ranked analysis with recommendations
python scripts/find_duplication.py /home/user/myproject --language python --analyze

# Detailed output with diff previews
python scripts/find_duplication.py /home/user/myproject --language python --detailed

# Combined: ranked + detailed
python scripts/find_duplication.py /home/user/myproject --language python --analyze --detailed

# JSON output for programmatic use
python scripts/find_duplication.py /home/user/myproject --language python --json > report.json

# Strict matching for critical code
python scripts/find_duplication.py /home/user/myproject --language python \
    --min-similarity 0.95 --min-lines 15

# Exclude custom patterns
python scripts/find_duplication.py /home/user/myproject --language python \
    --exclude-patterns migrations fixtures test_data

# Pipe to file without colors
python scripts/find_duplication.py /home/user/myproject --language python \
    --no-color > duplication-report.txt
```

### Output Format

**Standard Output:**
```
Analyzing: /path/to/project
Language: python
Construct type: function_definition
Min similarity: 80.0%
Min lines: 5
Max constructs: 1000

Searching for duplicates...

================================================================================
DUPLICATION ANALYSIS SUMMARY
================================================================================
Total constructs analyzed:    45
Duplicate groups found:       3
Total duplicated lines:       89
Potential line savings:       58
Analysis time:                0.234s
================================================================================

--------------------------------------------------------------------------------
DUPLICATION GROUPS
--------------------------------------------------------------------------------

Group 1 (Similarity: 92.0%)
   Found 3 duplicate instances:
   - /path/to/file1.py:10-25
   - /path/to/file2.py:45-60
   - /path/to/file3.py:100-115

--------------------------------------------------------------------------------
REFACTORING SUGGESTIONS
--------------------------------------------------------------------------------

Suggestion #1: Extract Function
   Similar function logic detected across multiple files
   Duplicates: 3 instances
   Lines per instance: 15
   Total duplicated: 45 lines

   Locations:
   - /path/to/file1.py:10-25
   - /path/to/file2.py:45-60
   - /path/to/file3.py:100-115

   Recommendation:
   Extract the common logic into a shared function...
```

**JSON Output:**
```json
{
  "summary": {
    "total_constructs": 45,
    "duplicate_groups": 3,
    "total_duplicated_lines": 89,
    "potential_line_savings": 58,
    "analysis_time_seconds": 0.234
  },
  "duplication_groups": [...],
  "refactoring_suggestions": [...]
}
```

---

## Workflow Examples

### Workflow 1: Quick Scan

Find duplicates and review manually.

```bash
# 1. Run detection
python scripts/find_duplication.py /path/to/project --language python

# 2. Review output and manually implement suggestions
```

### Workflow 2: Prioritized Refactoring

Focus on highest-value opportunities first.

```python
# 1. Get ranked candidates
candidates = analyze_deduplication_candidates(
    project_path="/path/to/project",
    language="python",
    min_similarity=0.85,
    max_candidates=10
)

# 2. Review top candidates
for candidate in candidates['candidates'][:5]:
    print(f"Rank #{candidate['rank']}: {candidate['potential_savings']} lines")
    print(f"  Priority: {candidate['priority_score']:.1%}")
    print(f"  Files: {len(candidate['files_affected'])}")
    print(f"  Recommendation: {candidate['recommendation']}")
    print()

# 3. Apply top candidate after review
# ... (prepare refactoring_plan based on candidate)
```

### Workflow 3: Safe Automated Refactoring

Apply changes with full safety net.

```python
# 1. Detect duplicates
duplicates = find_duplication(
    project_folder="/path/to/project",
    language="python"
)

# 2. Select a group to refactor
group_id = 1
suggestion = duplicates['refactoring_suggestions'][0]

# 3. Build refactoring plan (simplified example)
refactoring_plan = {
    "language": "python",
    "strategy": "extract_function",
    "generated_code": {
        "extracted_function": """def common_logic(param1, param2):
    # Common implementation
    result = param1 + param2
    return result"""
    },
    "files_affected": [
        {"file": f, "changes": [...]}
        for f in suggestion['locations']
    ]
}

# 4. Preview changes
preview = apply_deduplication(
    project_folder="/path/to/project",
    group_id=group_id,
    refactoring_plan=refactoring_plan,
    dry_run=True
)

# 5. Review diff
for change in preview['changes_preview']:
    print(f"\n=== {change['file']} ===")
    print(change['diff'])

# 6. Apply if satisfied
if input("Apply changes? (y/n): ").lower() == 'y':
    result = apply_deduplication(
        project_folder="/path/to/project",
        group_id=group_id,
        refactoring_plan=refactoring_plan,
        dry_run=False
    )

    print(f"Success! Backup ID: {result['backup_id']}")
    print(f"Modified: {result['files_modified']}")

    # 7. Run tests
    # If tests fail, rollback:
    # rollback_rewrite(project_folder="/path/to/project", backup_id=result['backup_id'])
```

### Workflow 4: CI Integration

Add duplication detection to CI pipeline.

```yaml
# .github/workflows/code-quality.yml
jobs:
  duplication-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Check for duplicates
        run: |
          python scripts/find_duplication.py ${{ github.workspace }} \
            --language python \
            --min-similarity 0.9 \
            --json > duplication-report.json

          # Fail if too many duplicates
          GROUPS=$(jq '.summary.duplicate_groups' duplication-report.json)
          if [ "$GROUPS" -gt 10 ]; then
            echo "Too many duplicate groups: $GROUPS"
            exit 1
          fi
```

---

## API Reference

### Key Functions

#### Pattern Analysis

```python
def extract_parameters(instances: List[Dict]) -> List[Dict]:
    """
    Extract varying parameters from duplicate instances.

    Returns:
        List of parameter definitions with name, type hint, and values.
    """
```

```python
def calculate_complexity_score(group: Dict) -> float:
    """
    Calculate refactoring complexity score (0.0-1.0).

    Factors:
    - Number of parameters
    - Import changes required
    - Conditional logic variations
    - Nested call depth
    - Total line count
    """
```

#### Code Generation

```python
def generate_extracted_function(
    group: Dict,
    language: str,
    function_name: str
) -> str:
    """
    Generate extracted function code from duplicate group.

    Returns:
        Complete function code with signature, docstring, and body.
    """
```

```python
def generate_replacement_call(
    instance: Dict,
    function_name: str,
    parameters: List[Dict]
) -> str:
    """
    Generate replacement call for a duplicate instance.

    Returns:
        Call expression with proper arguments.
    """
```

#### Validation

```python
def validate_syntax(code: str, language: str) -> Dict:
    """
    Validate code syntax for given language.

    Returns:
        {"valid": bool, "errors": List[str]}
    """
```

---

## Module Architecture

The deduplication feature is implemented as a modular system under `src/ast_grep_mcp/features/deduplication/`:

### Module Structure

```
features/deduplication/
├── __init__.py          # Public API exports
├── detector.py          # DuplicationDetector class
├── analyzer.py          # PatternAnalyzer, variation analysis
├── generator.py         # CodeGenerator for refactoring
├── ranker.py            # DuplicationRanker scoring
├── applicator.py        # Multi-file orchestration
├── coverage.py          # Test coverage detection
├── impact.py            # Impact analysis (refactored 2025-11-28)
├── recommendations.py   # Recommendation engine
├── reporting.py         # Enhanced reporting with diffs
├── benchmark.py         # Performance benchmarking
└── tools.py             # MCP tool definitions
```

**Recent Refactoring (2025-11-28/29):**
- `impact.py`: `_assess_breaking_change_risk` reduced from 44→0 cognitive complexity (100%)
- `impact.py`: `_parallel_enrich` reduced from 74→2 cognitive complexity (97%)
- `impact.py`: `_find_import_references` reduced from 31→5 cognitive complexity (84%)
- Shared utilities extracted to `utils/syntax_validation.py` (DRY principle)
- See [PATTERNS.md](./PATTERNS.md) for refactoring techniques used

### Direct Module Imports

For custom scripts (not using MCP tools), import from modules directly:

**Detector:**
```python
from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

detector = DuplicationDetector(
    project_folder="/path/to/project",
    language="python"
)
duplicates = detector.find_duplicates()
```

**Analyzer:**
```python
from ast_grep_mcp.features.deduplication.analyzer import PatternAnalyzer

analyzer = PatternAnalyzer()
variations = analyzer.analyze_variations(duplicate_group)
```

**Ranker:**
```python
from ast_grep_mcp.features.deduplication.ranker import DuplicationRanker

ranker = DuplicationRanker()
candidates = ranker.rank_candidates(duplicate_groups)
```

**Applicator:**
```python
from ast_grep_mcp.features.deduplication.applicator import DeduplicationApplicator

applicator = DeduplicationApplicator(project_folder="/path")
result = applicator.apply_refactoring(plan, dry_run=True)
```

**Coverage Detection:**
```python
from ast_grep_mcp.features.deduplication.coverage import has_test_coverage

covered = has_test_coverage(
    file_path="/path/to/module.py",
    project_folder="/path/to/project",
    language="python"
)
```

**Impact Analysis:**
```python
from ast_grep_mcp.features.deduplication.impact import analyze_deduplication_impact

impact = analyze_deduplication_impact(
    duplicate_group=group,
    project_folder="/path",
    language="python"
)
```

### Data Models

Import deduplication models from `models/deduplication.py`:

```python
from ast_grep_mcp.models.deduplication import (
    DuplicateInstance,
    DuplicateGroup,
    DeduplicationCandidate,
    RefactoringPlan,
    ParameterMapping
)
```

### Import Locations

All deduplication functionality is available from the modular architecture:

```python
from ast_grep_mcp.features.deduplication.detector import DuplicationDetector
from ast_grep_mcp.features.deduplication.analyzer import PatternAnalyzer
```

---

## Similarity Algorithm Selection

The deduplication system automatically selects the optimal similarity algorithm based on code size to balance accuracy and performance.

### Small Code (< 15 tokens)
- **Algorithm:** `difflib.SequenceMatcher`
- **Complexity:** O(n^2)
- **Accuracy:** 100% (exact)
- **Use Case:** Functions, small methods, code snippets

MinHash accuracy depends on shingle count. Small code produces too few shingles, causing inaccurate similarity estimation. SequenceMatcher provides exact results for these cases.

### Large Code (>= 15 tokens)
- **Algorithm:** MinHash with LSH
- **Complexity:** O(n) for MinHash, O(1) amortized for LSH queries
- **Accuracy:** ~95% (approximate)
- **Use Case:** Classes, modules, large functions

MinHash with Locality Sensitive Hashing enables scalable duplicate detection across large codebases.

### Configuration

```python
from ast_grep_mcp.features.deduplication.similarity import SimilarityConfig, MinHashSimilarity

config = SimilarityConfig(
    small_code_threshold=15,        # Tokens below this use SequenceMatcher
    use_small_code_fallback=True,   # Enable fallback (recommended)
    num_permutations=128,           # MinHash permutations (higher = more accurate)
    shingle_size=3,                 # Token shingle size (3 is optimal for code)
)

similarity = MinHashSimilarity(config)
score = similarity.estimate_similarity(code1, code2)
```

### Disabling the Fallback

In rare cases where you want consistent MinHash-only behavior:

```python
config = SimilarityConfig(use_small_code_fallback=False)
similarity = MinHashSimilarity(config)
```

Note: This may produce less accurate results for small code snippets.

### Performance Characteristics

| Code Size | Algorithm | Time (per comparison) | Accuracy |
|-----------|-----------|----------------------|----------|
| < 15 tokens | SequenceMatcher | ~0.1ms | 100% |
| 15-100 tokens | MinHash | ~0.05ms | ~95% |
| > 100 tokens | MinHash + LSH | ~0.01ms | ~95% |

### Hybrid Mode (Default)

The default `hybrid` similarity mode in `DuplicationDetector` combines:
1. **Stage 1:** Fast MinHash filter (O(n)) - eliminates dissimilar pairs
2. **Stage 2:** Precise structural verification for candidates

This provides both speed and accuracy for production use:

```python
from ast_grep_mcp.features.deduplication.detector import DuplicationDetector

# Uses hybrid mode by default
detector = DuplicationDetector()

# Or explicitly:
detector = DuplicationDetector(similarity_mode="hybrid")
```

---

## Troubleshooting

### Common Issues

#### "No duplicates found"

**Possible causes:**
1. Similarity threshold too high
2. Min lines too high
3. Code is excluded by patterns

**Solutions:**
```bash
# Lower thresholds
python scripts/find_duplication.py /path --language python \
    --min-similarity 0.7 --min-lines 3

# Check exclude patterns
python scripts/find_duplication.py /path --language python \
    --exclude-patterns ""  # No exclusions
```

#### "Too many false positives"

**Possible causes:**
1. Similarity threshold too low
2. Including library code

**Solutions:**
```bash
# Raise thresholds
python scripts/find_duplication.py /path --language python \
    --min-similarity 0.9 --min-lines 10

# Add exclusions
python scripts/find_duplication.py /path --language python \
    --exclude-patterns "migrations" "fixtures" "generated"
```

#### "apply_deduplication validation failed"

**Possible causes:**
1. Generated code has syntax errors
2. Missing imports
3. Incorrect indentation

**Check:**
```python
result = apply_deduplication(..., dry_run=True)
print(result['validation']['pre_validation']['errors'])
```

**Solutions:**
1. Review and fix the refactoring_plan
2. Ensure all required imports are included
3. Check indentation matches target file style

#### "Rollback failed"

**Possible causes:**
1. Invalid backup_id
2. Backup files were deleted/moved

**Check:**
```bash
# List available backups
ls -la /path/to/project/.ast-grep-backups/
```

**Prevention:**
- Always save the backup_id returned from apply_deduplication
- Don't delete .ast-grep-backups/ directory until verified

#### "Performance is slow"

**Possible causes:**
1. Too many constructs to analyze
2. No exclusion patterns

**Solutions:**
```bash
# Limit constructs
python scripts/find_duplication.py /path --language python \
    --max-constructs 500

# Add exclusions
python scripts/find_duplication.py /path --language python \
    --exclude-patterns "node_modules" "dist" "build" "__pycache__"
```

### Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `min_similarity must be between 0.0 and 1.0` | Invalid threshold | Use value in 0.0-1.0 range |
| `Project folder does not exist` | Invalid path | Check path is absolute and exists |
| `Language not supported` | Unknown language | Use supported language from list |
| `refactoring_plan is required` | Missing plan | Provide complete refactoring_plan dict |
| `No valid files found` | Files don't exist | Verify files_affected paths |

### Getting Help

1. Check tool documentation in CLAUDE.md
2. Review test files in `tests/` for usage examples
3. Run with `--json` for detailed structured output
4. Check logs for error details

---

## Additional Resources

- [CLAUDE.md](../CLAUDE.md) - Project overview and tool documentation
- [README.md](../README.md) - Quick start and installation
- [CONFIGURATION.md](./CONFIGURATION.md) - Configuration options
- [BENCHMARKING.md](./BENCHMARKING.md) - Performance benchmarks

---

**End of Deduplication Guide**
