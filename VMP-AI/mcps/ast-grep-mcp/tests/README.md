# Test Suite Organization

This directory contains the complete test suite for the ast-grep MCP server, organized into unit and integration tests.

## Directory Structure

```
tests/
├── unit/               # Unit tests (fast, mocked dependencies)
│   ├── test_unit.py           # Core functionality tests (57 tests)
│   ├── test_cache.py          # Query caching tests (15 tests)
│   ├── test_duplication.py    # Duplication detection tests (24 tests)
│   └── test_phase2.py         # Phase 2 performance tests (21 tests)
├── integration/        # Integration tests (require ast-grep binary)
│   ├── test_integration.py    # End-to-end tests (5 tests)
│   └── test_benchmark.py      # Performance benchmarks (7 tests)
└── fixtures/           # Shared test fixtures and sample files
```

## Test Categories

### Unit Tests (122 tests)

**Fast, mocked, no external dependencies**

Run with: `uv run pytest tests/unit/`

- **test_unit.py** (57 tests)
  - Tool functions (dump_syntax_tree, find_code, find_code_by_rule, test_match_code_rule)
  - Output formatting (text vs JSON)
  - Command execution and error handling
  - Config validation and language support
  - YAML rule validation

- **test_cache.py** (15 tests)
  - QueryCache class functionality
  - LRU eviction and TTL expiration
  - Cache hit/miss tracking
  - Integration with find_code/find_code_by_rule

- **test_duplication.py** (24 tests)
  - Code normalization
  - Similarity calculation
  - Duplicate grouping
  - Refactoring suggestions

- **test_phase2.py** (21 tests)
  - Result streaming (7 tests)
  - Parallel execution (4 tests)
  - Large file handling (8 tests)
  - Feature integration (2 tests)

### Integration Tests (12 tests)

**Require ast-grep binary installed**

Run with: `uv run pytest tests/integration/`

- **test_integration.py** (5 tests)
  - End-to-end searches with real ast-grep subprocess
  - Text and JSON output formats
  - Result limiting with max_results
  - Error handling with real fixtures

- **test_benchmark.py** (7 tests)
  - Performance benchmarking suite
  - Baseline tracking and regression detection
  - Cache hit performance measurement
  - Memory profiling

## Running Tests

```bash
# Run all tests
uv run pytest

# Run only unit tests (fast)
uv run pytest tests/unit/

# Run only integration tests (requires ast-grep)
uv run pytest tests/integration/

# Run specific test file
uv run pytest tests/unit/test_cache.py

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=main --cov-report=term-missing

# Run and stop at first failure
uv run pytest -x
```

## Test Fixtures

The `fixtures/` directory contains:
- `example.py` - Sample Python code for testing searches
- `*.yaml` - Sample YAML configurations for testing config validation
- Other test data files

Fixtures are shared between unit and integration tests.

## Writing New Tests

### Unit Tests

Place in `tests/unit/` and mock subprocess calls:

```python
from unittest.mock import patch

@patch("main.stream_ast_grep_results")
def test_my_feature(mock_stream):
    mock_stream.return_value = iter([{"text": "match"}])
    # Test code here
```

### Integration Tests

Place in `tests/integration/` and use real ast-grep:

```python
def test_real_search(fixtures_dir):
    result = find_code(
        project_folder=str(fixtures_dir),
        pattern="def $NAME",
        language="python"
    )
    assert "def hello" in result
```

## Cache Isolation

When writing tests that call search tools, clear the cache in `setup_method()`:

```python
def setup_method(self):
    """Clear cache before each test"""
    if main._query_cache is not None:
        main._query_cache.cache.clear()
        main._query_cache.hits = 0
        main._query_cache.misses = 0
```

This prevents test interference from cached results.

## CI/CD

For continuous integration:

```bash
# Run unit tests (fast, no ast-grep needed)
uv run pytest tests/unit/

# Run integration tests (requires ast-grep)
uv run pytest tests/integration/

# Check for performance regressions
python scripts/run_benchmarks.py --check-regression
```
