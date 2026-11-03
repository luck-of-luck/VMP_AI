# Test Automation Scripts

Scripts for managing fixture migration and tracking test quality metrics.

## Available Scripts

### score_test_file.py

**Purpose:** Calculate refactoring priority scores for test files

**Usage:**
```bash
# Score a single file
python tests/scripts/score_test_file.py tests/unit/test_cache.py

# Score with detailed metrics
python tests/scripts/score_test_file.py tests/unit/test_cache.py --detailed

# Score all test files
python tests/scripts/score_test_file.py --all

# Output as JSON
python tests/scripts/score_test_file.py --all --json > scores.json
```

**Scoring System (0-100):**
- **Pain Points (40%)**: Maintenance burden, flakiness, duplication
- **Opportunity (35%)**: Lines saved, complexity reduction, reusability
- **Risk (15% inverse)**: Test count, self-attributes, dependencies
- **Alignment (10%)**: Feature work, team familiarity

**Score Ranges:**
- **≥70**: HIGH PRIORITY - Refactor soon
- **55-69**: MEDIUM PRIORITY - Refactor when touching file
- **40-54**: LOW PRIORITY - Refactor opportunistically
- **25-39**: DEFER - Keep using setup_method
- **<25**: SKIP - Not worth refactoring

### track_fixture_metrics.py

**Purpose:** Track fixture adoption rates and usage statistics

**Usage:**
```bash
# Current metrics
python tests/scripts/track_fixture_metrics.py

# Detailed breakdown
python tests/scripts/track_fixture_metrics.py --detailed

# View historical trend
python tests/scripts/track_fixture_metrics.py --history

# Save to history file
python tests/scripts/track_fixture_metrics.py --save

# JSON output
python tests/scripts/track_fixture_metrics.py --json
```

**Metrics Tracked:**
- Fixture adoption rate (% of tests using fixtures)
- Per-fixture usage counts
- Test file categories (fixture-based, setup_method, mixed, neither)
- Trend tracking over time

### detect_fixture_patterns.py

**Purpose:** Identify common patterns that could become fixtures

**Usage:**
```bash
# Detect patterns (default threshold: 3 occurrences)
python tests/scripts/detect_fixture_patterns.py

# Lower threshold
python tests/scripts/detect_fixture_patterns.py --threshold 2

# Detailed with suggested implementations
python tests/scripts/detect_fixture_patterns.py --detailed

# JSON output
python tests/scripts/detect_fixture_patterns.py --json
```

**Patterns Detected:**
- Repeated temporary directory creation
- Common file creation patterns
- Mock subprocess patterns
- Cache initialization patterns
- Repeated imports

**Output:**
- Pattern type and description
- Occurrence count and file count
- Fixture value score (0-10)
- Suggested fixture name and implementation

### validate_refactoring.py

**Purpose:** Validate that refactored tests work correctly

**Usage:**
```bash
# Basic validation
python tests/scripts/validate_refactoring.py tests/unit/test_cache.py

# Compare against baseline
python tests/scripts/validate_refactoring.py tests/unit/test_cache.py --baseline baseline.json

# Include performance check
python tests/scripts/validate_refactoring.py tests/unit/test_cache.py --performance

# Save new baseline
python tests/scripts/validate_refactoring.py tests/unit/test_cache.py --save-baseline baseline.json

# JSON output
python tests/scripts/validate_refactoring.py tests/unit/test_cache.py --json
```

**Validation Checks:**
- ✓ Tests collect successfully
- ✓ All tests pass
- ✓ Same number of tests as baseline
- ✓ Performance within 20% of baseline
- ✓ No increase in warnings

### benchmark_fixtures.py

**Purpose:** Measure fixture performance overhead

**Usage:**
```bash
# Benchmark all fixtures
python tests/scripts/benchmark_fixtures.py

# Benchmark specific fixture
python tests/scripts/benchmark_fixtures.py --fixture temp_dir

# Detailed breakdown
python tests/scripts/benchmark_fixtures.py --detailed

# More iterations for accuracy
python tests/scripts/benchmark_fixtures.py --iterations 5

# JSON output
python tests/scripts/benchmark_fixtures.py --json
```

**Measurements:**
- Setup time (ms)
- Teardown time (ms)
- Total overhead (ms)
- Pass/fail threshold (<100ms is good)

**Thresholds:**
- **Good**: <100ms overhead
- **Slow**: ≥100ms overhead (needs optimization)

## Quick Examples

### Scoring & Prioritization
```bash
# Find high-priority files to refactor
python tests/scripts/score_test_file.py --all | grep "HIGH PRIORITY"

# Get detailed analysis of top candidate
python tests/scripts/score_test_file.py tests/unit/test_rewrite.py --detailed

# Export all scores for tracking
python tests/scripts/score_test_file.py --all --json > baseline_scores.json
```

### Metrics Tracking
```bash
# Check current adoption rate
python tests/scripts/track_fixture_metrics.py

# Save metrics to history
python tests/scripts/track_fixture_metrics.py --save

# View trend over time
python tests/scripts/track_fixture_metrics.py --history
```

### Pattern Detection
```bash
# Find common patterns
python tests/scripts/detect_fixture_patterns.py --detailed

# Look for patterns with lower threshold
python tests/scripts/detect_fixture_patterns.py --threshold 2 --detailed
```

### Validation Workflow
```bash
# Before refactoring: save baseline
python tests/scripts/validate_refactoring.py tests/unit/test_cache.py --save-baseline before.json

# After refactoring: validate against baseline
python tests/scripts/validate_refactoring.py tests/unit/test_cache.py --baseline before.json --performance
```

### Performance Monitoring
```bash
# Benchmark all fixtures
python tests/scripts/benchmark_fixtures.py --detailed

# Check specific fixture
python tests/scripts/benchmark_fixtures.py --fixture temp_dir --iterations 10
```

## Baseline Scores

Baseline scores captured on 2025-11-25:

**High Priority (≥70):**
- test_rewrite.py: 92.2
- test_apply_deduplication.py: 74.6

**Medium Priority (55-69):**
- test_deduplication_rollback.py: 69.4
- test_batch.py: 65.1
- test_cli_duplication.py: 60.1
- test_schema.py: 58.9

See `tests/baseline_scores.json` for complete data.

## Integration with Git Hooks

The pre-commit hook (`.git/hooks/pre-commit`) enforces fixture usage for new test files.

**Bypass (not recommended):**
```bash
git commit --no-verify
```

## Documentation

- [FIXTURE_MIGRATION_GUIDE.md](../FIXTURE_MIGRATION_GUIDE.md) - How to refactor tests
- [FIXTURE_GOVERNANCE.md](../FIXTURE_GOVERNANCE.md) - Fixture lifecycle management
- [FIXTURE_COOKBOOK.md](../FIXTURE_COOKBOOK.md) - Common testing patterns
- [DEVELOPER_ONBOARDING.md](../DEVELOPER_ONBOARDING.md) - Quick start for new developers

## Contributing

When adding new scripts:

1. Follow naming convention: `{verb}_{noun}.py`
2. Include `--help` flag with usage
3. Support `--json` output when applicable
4. Update this README
5. Add tests in `tests/test_scripts/`
