# Performance Benchmarking Guide

This document describes the performance benchmarking suite for the ast-grep MCP server.

## Overview

The benchmarking suite provides:
- **Standard query patterns** to measure performance consistently
- **Baseline tracking** to detect performance regressions
- **Memory profiling** to catch memory leaks
- **CI integration** for automated regression detection
- **Detailed reports** showing performance trends

## Quick Start

```bash
# Run benchmarks
uv run python scripts/run_benchmarks.py

# Update baseline (after performance improvements)
uv run python scripts/run_benchmarks.py --save-baseline

# Check for regressions (for CI)
uv run python scripts/run_benchmarks.py --check-regression
```

## Benchmark Suite

### Standard Benchmarks

The suite includes these standard benchmarks:

| Benchmark | Description | Measures |
|-----------|-------------|----------|
| **simple_pattern_search** | Simple pattern with `find_code` | Basic search performance |
| **yaml_rule_search** | YAML rule with `find_code_by_rule` | Rule-based search |
| **early_termination_max_10** | Search with `max_results=10` | Early termination efficiency |
| **file_size_filtering_10mb** | Search with `max_file_size_mb=10` | File filtering overhead |
| **cache_miss** | First search (not in cache) | Uncached performance |
| **cache_hit** | Repeat search (cached) | Cache hit performance |

### Metrics Tracked

For each benchmark, we track:
- **Execution Time** (seconds) - How long the query takes
- **Memory Usage** (MB) - Peak memory during execution
- **Result Count** - Number of matches found
- **Cache Status** - Whether result was cached

## Performance Targets

### Expected Performance Ranges

Based on codebase size:

| Codebase Size | Files | Simple Search | Complex Rule | With Cache |
|---------------|-------|---------------|--------------|------------|
| **Small** | <100 | <0.5s | <1.0s | <0.01s |
| **Medium** | 100-1K | <2.0s | <4.0s | <0.05s |
| **Large** | 1K-10K | <10s | <20s | <0.1s |
| **XLarge** | >10K | <60s | <120s | <0.5s |

### Memory Usage Targets

- **Simple patterns:** <50MB
- **Complex rules:** <100MB
- **Large result sets:** <200MB (with streaming)
- **Cache overhead:** <10MB per 100 cached queries

## Regression Detection

### What Triggers a Regression?

A regression is detected when:
- Execution time increases by >10% compared to baseline
- Memory usage increases by >20% compared to baseline
- Cache hit rate drops below 95%

### How It Works

1. **Baseline Storage:** First run saves metrics to `tests/benchmark_baseline.json`
2. **Comparison:** Subsequent runs compare against baseline
3. **Threshold Check:** Fails if any metric exceeds threshold
4. **CI Failure:** Returns exit code 1 to fail CI build

### Updating Baseline

Update the baseline after:
- Implementing performance improvements
- Major refactoring that changes performance characteristics
- Upgrading ast-grep version

```bash
# Run benchmarks and save as new baseline
uv run python scripts/run_benchmarks.py --save-baseline
```

## Running Benchmarks

### Local Development

```bash
# Run all benchmarks
uv run python -m pytest tests/integration/test_benchmark.py -v

# Run specific benchmark
uv run python -m pytest tests/integration/test_benchmark.py::TestPerformanceBenchmarks::test_benchmark_simple_pattern_search -v

# Run with verbose output
uv run python -m pytest tests/integration/test_benchmark.py -v -s
```

### CI Integration

Add to your `.github/workflows/ci.yml`:

```yaml
- name: Run performance benchmarks
  run: |
    uv run uv run python scripts/run_benchmarks.py --check-regression
  env:
    CI: true
```

The benchmarks will:
- Run the standard benchmark suite
- Compare results to baseline
- Fail the build if >10% regression detected

### Custom Benchmarks

Add custom benchmarks to `tests/integration/test_benchmark.py`:

```python
def test_benchmark_custom_query(
    self,
    benchmark_runner: BenchmarkRunner,
    benchmark_fixtures: Path
) -> None:
    """Benchmark custom query pattern."""
    tool = mcp.tools["find_code"]

    result = benchmark_runner.run_benchmark(
        "custom_query_name",
        tool,
        project_folder=str(benchmark_fixtures),
        pattern="your $PATTERN",
        language="python",
        output_format="json"
    )

    assert result.execution_time < 5.0, "Query too slow"
    assert result.memory_mb < 50.0, "Query uses too much memory"
```

## Benchmark Reports

### Report Format

Reports include:
- Execution summary (date, benchmark count)
- Results table with all metrics
- Comparison to baseline (% change)
- Regression warnings (if any)

### Example Report

```markdown
# Performance Benchmark Report

**Date:** 2025-11-16 14:30:00
**Benchmarks Run:** 6

## Benchmark Results

| Benchmark | Time (s) | Memory (MB) | Results | vs Baseline |
|-----------|----------|-------------|---------|-------------|
| simple_pattern_search | 0.234 | 12.45 | 42 | -5.2% 🟢 |
| yaml_rule_search | 0.456 | 15.67 | 38 | +2.1% |
| early_termination_max_10 | 0.123 | 8.90 | 10 | -12.3% 🟢 |
| cache_hit | 0.008 | 2.34 | 42 | ~same |

## ✅ No Performance Regressions
```

## Interpreting Results

### Good Performance Indicators

✅ Execution time stays within expected ranges
✅ Memory usage remains bounded (<200MB)
✅ Cache hit performance is >10x faster than miss
✅ Early termination works (result_count = max_results)

### Warning Signs

⚠️ Execution time increases over time
⚠️ Memory usage grows without bound
⚠️ Cache hit performance degrading
⚠️ Regressions >10% without code changes

## Troubleshooting

### Benchmarks Are Slow

Possible causes:
- **Large test fixtures** - Reduce fixture size or add max_results
- **Cold caches** - Warming may help but defeats benchmarking purpose
- **Background processes** - Close other applications during benchmarks
- **Debug mode** - Ensure running in production mode

### Memory Usage Too High

Possible causes:
- **Not using streaming** - Check that streaming is enabled
- **Large result sets** - Use max_results to limit results
- **Memory leaks** - Profile with tracemalloc to find leaks
- **Cache unbounded** - Check cache size limits

### Regressions Without Code Changes

Possible causes:
- **System differences** - Different hardware/OS than baseline
- **ast-grep version** - Different ast-grep version
- **Test fixtures changed** - Fixtures modified since baseline
- **Background load** - System under load during benchmarks

**Solution:** Re-run baseline on current system/environment

## Advanced Usage

### Memory Profiling

```python
import tracemalloc

tracemalloc.start()
# Run your code
current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024:.2f} MB")
print(f"Peak: {peak / 1024 / 1024:.2f} MB")
tracemalloc.stop()
```

### Performance Comparison

Compare performance across branches:

```bash
# On main branch
git checkout main
uv run python scripts/run_benchmarks.py --save-baseline
mv tests/benchmark_baseline.json tests/baseline_main.json

# On feature branch
git checkout feature-branch
uv run python scripts/run_benchmarks.py --save-baseline
mv tests/benchmark_baseline.json tests/baseline_feature.json

# Compare
diff tests/baseline_main.json tests/baseline_feature.json
```

### Custom Regression Thresholds

Modify threshold in `tests/integration/test_benchmark.py`:

```python
# Default: 10% regression threshold
has_regression, errors = benchmark_runner.check_regression(threshold=0.10)

# Stricter: 5% regression threshold
has_regression, errors = benchmark_runner.check_regression(threshold=0.05)
```

## Best Practices

### Running Benchmarks

1. **Close other applications** - Minimize background noise
2. **Use consistent hardware** - Run on same machine as baseline
3. **Warm up if needed** - But be aware this affects cold-start measurements
4. **Run multiple times** - Average results for more accuracy

### Maintaining Baselines

1. **Update after improvements** - Capture performance gains
2. **Document changes** - Note what changed in baseline commit
3. **Keep old baselines** - Archive for historical comparison
4. **Review regressions** - Investigate all regressions before updating baseline

### CI Integration

1. **Use fixed hardware** - Consistent CI runners
2. **Fail on regression** - Don't merge performance regressions
3. **Track trends** - Monitor performance over time
4. **Alert on degradation** - Set up alerts for performance drops

## Future Enhancements

Potential improvements to the benchmark suite:

- **Historical tracking** - Store all benchmark runs for trend analysis
- **Visualization** - Generate charts showing performance over time
- **Parallel benchmarks** - Run benchmarks in parallel for faster results
- **More metrics** - CPU usage, I/O metrics, network calls
- **Automated tuning** - Suggest optimizations based on results
- **Benchmark fixtures** - Generate realistic benchmark codebases

## References

- [pytest benchmarking](https://docs.pytest.org/en/stable/how-to/benchmarks.html)
- [Python memory profiling](https://docs.python.org/3/library/tracemalloc.html)
- [Performance testing best practices](https://martinfowler.com/articles/nonDeterminism.html)

---

**Last Updated:** 2025-11-16
**Maintained by:** AST-Grep MCP Development Team
