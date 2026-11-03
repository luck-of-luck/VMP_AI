# Developer Onboarding: Testing with Fixtures

**Quick Start Guide** for new developers working on ast-grep-mcp

## Welcome!

This guide will get you up to speed with our testing approach using pytest fixtures. After reading this, you'll know how to write tests that are clean, reusable, and maintainable.

## Prerequisites

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run specific file
uv run pytest tests/unit/test_cache.py -v
```

## 5-Minute Quick Start

### 1. Your First Test with Fixtures

```python
def test_file_operations(temp_dir):
    """temp_dir is a fixture - it's automatically provided."""
    # temp_dir is a real directory you can use
    file_path = os.path.join(temp_dir, "test.txt")

    # Write a file
    with open(file_path, "w") as f:
        f.write("Hello, World!")

    # Verify it exists
    assert os.path.exists(file_path)

    # No cleanup needed - fixture handles it!
```

### 2. Using Multiple Fixtures

```python
def test_search_with_cache(temp_project_with_files, initialized_cache, mcp_tools):
    """Combine multiple fixtures for complex scenarios."""
    # Get project directory
    project = temp_project_with_files["project"]

    # Get an MCP tool
    find_code = mcp_tools("find_code")

    # Cache is already initialized and ready
    # Run your test
    result = find_code(pattern="def", project_folder=project)
    assert len(result) > 0
```

### 3. What Are Fixtures?

Think of fixtures as **test ingredients** that pytest provides to your test functions:

```python
# Without fixtures (old way):
class TestExample:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()  # Setup
        # ... more setup ...

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)  # Cleanup

    def test_something(self):
        file = os.path.join(self.temp_dir, "test.txt")  # Use setup

# With fixtures (new way):
def test_something(temp_dir):
    file = os.path.join(temp_dir, "test.txt")
    # Setup and cleanup automatic!
```

## Fixtures You Should Know

### Essential Fixtures (Use These Daily)

#### `temp_dir` - Temporary Directory
```python
def test_file_creation(temp_dir):
    """temp_dir is a clean directory, deleted after test."""
    file_path = os.path.join(temp_dir, "data.json")
    with open(file_path, "w") as f:
        json.dump({"key": "value"}, f)
    assert os.path.exists(file_path)
```

#### `temp_project_with_files` - Test Project with Sample Files
```python
def test_code_modification(temp_project_with_files):
    """Provides a project with Python files."""
    project = temp_project_with_files["project"]  # Project directory
    sample_py = temp_project_with_files["sample_py"]  # sample.py file
    complex_py = temp_project_with_files["complex_py"]  # complex.py file

    # Files already exist and contain sample code
    with open(sample_py) as f:
        content = f.read()
    assert "def hello" in content
```

#### `mcp_tools` - Get MCP Tools
```python
def test_search(mcp_tools, temp_dir):
    """mcp_tools is a factory to get tool functions."""
    find_code = mcp_tools("find_code")

    # Use the tool
    result = find_code(pattern="test", project_folder=temp_dir)
    assert result is not None
```

#### `initialized_cache` - Pre-configured Cache
```python
def test_caching(initialized_cache):
    """Cache is already set up and ready."""
    initialized_cache.set("key", "value")
    assert initialized_cache.get("key") == "value"
```

### Mock Fixtures (For Unit Tests)

#### `mock_popen` - Mock Streaming Commands
```python
def test_streaming(mock_popen):
    """Mock subprocess.Popen for streaming output."""
    mock_popen.return_value.stdout = iter(['line1', 'line2', 'line3'])
    mock_popen.return_value.poll.return_value = None

    # Your code that uses Popen
    # The mock will return the lines above
```

#### `mock_subprocess_run` - Mock Non-Streaming Commands
```python
def test_command(mock_subprocess_run):
    """Mock subprocess.run for simple commands."""
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stdout = "success"

    # Your code that uses subprocess.run
    # The mock will return the values above
```

### Sample Data Fixtures

#### `sample_search_result` - Realistic Search Result
```python
def test_result_processing(sample_search_result):
    """Use realistic test data."""
    # sample_search_result has structure like actual ast-grep output
    assert "text" in sample_search_result
    assert "file" in sample_search_result
```

## Common Patterns

### Pattern 1: File System Testing

```python
def test_create_and_read(temp_dir):
    """Create files, read them back."""
    # Create
    file_path = os.path.join(temp_dir, "data.txt")
    Path(file_path).write_text("test data")

    # Read
    content = Path(file_path).read_text()
    assert content == "test data"
```

### Pattern 2: Testing MCP Tools

```python
def test_mcp_tool(mcp_tools, temp_project_with_files):
    """Test an MCP tool end-to-end."""
    # Get the tool
    find_code = mcp_tools("find_code")

    # Get test project
    project = temp_project_with_files["project"]

    # Use the tool
    results = find_code(
        pattern="def",
        project_folder=project,
        language="python"
    )

    # Verify
    assert len(results) > 0
    assert all("def" in r["text"] for r in results)
```

### Pattern 3: Testing with Mocks

```python
def test_with_mock(mock_subprocess_run, temp_dir):
    """Test code that calls external commands."""
    # Configure mock
    mock_subprocess_run.return_value.returncode = 0
    mock_subprocess_run.return_value.stdout = "mocked output"

    # Your code that uses subprocess
    from src.ast_grep_mcp.features.search.service import find_code_impl
    result = find_code_impl(...)

    # Verify mock was called
    assert mock_subprocess_run.called
```

## DON'Ts - Common Mistakes

### ❌ DON'T: Use `setup_method` in New Tests

```python
# DON'T DO THIS (will be blocked by pre-commit hook):
class TestExample:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def test_something(self):
        # ...
```

```python
# DO THIS INSTEAD:
def test_something(temp_dir):
    # Use fixture
    pass
```

### ❌ DON'T: Manual Cleanup

```python
# DON'T:
def test_something(temp_dir):
    # ...
    shutil.rmtree(temp_dir)  # Unnecessary! Fixture does this
```

```python
# DO:
def test_something(temp_dir):
    # ... test code ...
    # Cleanup happens automatically
```

### ❌ DON'T: Recreate Existing Fixtures

```python
# DON'T:
def test_something():
    temp_dir = tempfile.mkdtemp()
    try:
        # ... test ...
    finally:
        shutil.rmtree(temp_dir)
```

```python
# DO:
def test_something(temp_dir):
    # Use existing fixture
    pass
```

## How to Find Fixtures

### Method 1: Search conftest.py

```bash
grep "@pytest.fixture" tests/conftest.py
```

### Method 2: Use Quick Reference

Open [FIXTURE_QUICK_REFERENCE.md](FIXTURE_QUICK_REFERENCE.md) for complete list.

### Method 3: IDE Autocomplete

Most IDEs show available fixtures when you type parameters:

```python
def test_example(|  # Type here, IDE suggests fixtures
```

## Writing Your First Test

### Step 1: Identify What You Need

Ask yourself:
- Do I need files? → `temp_dir` or `temp_project_with_files`
- Do I need to test an MCP tool? → `mcp_tools`
- Do I need to mock commands? → `mock_popen` or `mock_subprocess_run`
- Do I need caching? → `initialized_cache` or `cache_disabled`

### Step 2: Write Test Function

```python
def test_my_feature(temp_dir, mcp_tools):
    """Test my new feature."""
    # 1. Setup (using fixtures)
    project = temp_dir
    find_code = mcp_tools("find_code")

    # 2. Execute
    result = find_code(pattern="test", project_folder=project)

    # 3. Assert
    assert result is not None
```

### Step 3: Run and Iterate

```bash
# Run your test
uv run pytest tests/unit/test_my_feature.py::test_my_feature -v

# Debug if needed
uv run pytest tests/unit/test_my_feature.py::test_my_feature -v --pdb
```

## Running Tests

```bash
# All tests
uv run pytest

# Specific file
uv run pytest tests/unit/test_cache.py

# Specific test
uv run pytest tests/unit/test_cache.py::test_cache_basic

# With output
uv run pytest -v -s

# Stop on first failure
uv run pytest -x

# Show fixture setup
uv run pytest --setup-show
```

## Debugging Tips

### Tip 1: Print Fixture Values

```python
def test_debug(temp_dir):
    print(f"temp_dir = {temp_dir}")  # See what fixture provides
    # Run with: pytest -s
```

### Tip 2: Use --setup-show

```bash
# See fixture setup/teardown
pytest tests/unit/test_cache.py::test_cache_basic --setup-show
```

### Tip 3: Use Debugger

```python
def test_debug(temp_dir):
    import pdb; pdb.set_trace()  # Breakpoint
    # ... test code ...
```

```bash
pytest tests/unit/test_cache.py::test_debug --pdb
```

## Next Steps

### Learn More

1. **Read the cookbook** - [FIXTURE_COOKBOOK.md](FIXTURE_COOKBOOK.md)
   - Real-world examples
   - Common patterns
   - Before/after comparisons

2. **Understand migration** - [FIXTURE_MIGRATION_GUIDE.md](FIXTURE_MIGRATION_GUIDE.md)
   - How to convert old tests
   - Step-by-step process

3. **Propose fixtures** - [FIXTURE_GOVERNANCE.md](FIXTURE_GOVERNANCE.md)
   - When to create new fixtures
   - Proposal process

### Practice Tasks

1. **Write a simple test**
   ```python
   def test_practice(temp_dir):
       """Practice using temp_dir fixture."""
       # Create a file
       # Read it back
       # Assert contents
   ```

2. **Test an MCP tool**
   ```python
   def test_mcp_practice(mcp_tools, temp_dir):
       """Practice using mcp_tools fixture."""
       # Get a tool
       # Use it
       # Verify results
   ```

3. **Combine fixtures**
   ```python
   def test_combination(temp_project_with_files, mcp_tools, initialized_cache):
       """Practice combining multiple fixtures."""
       # Use all three fixtures together
   ```

## Getting Help

### Documentation

- **Quick lookup**: [FIXTURE_QUICK_REFERENCE.md](FIXTURE_QUICK_REFERENCE.md)
- **Recipes**: [FIXTURE_COOKBOOK.md](FIXTURE_COOKBOOK.md)
- **Migration**: [FIXTURE_MIGRATION_GUIDE.md](FIXTURE_MIGRATION_GUIDE.md)
- **Governance**: [FIXTURE_GOVERNANCE.md](FIXTURE_GOVERNANCE.md)

### Commands

```bash
# List all fixtures
pytest --fixtures

# List fixtures with descriptions
pytest --fixtures -v

# Score test files (see which need refactoring)
python tests/scripts/score_test_file.py --all
```

### Examples

Look at existing tests:
- `tests/unit/test_conftest_fixtures.py` - Fixture usage examples
- `tests/unit/test_linting_rules.py` - Simple fixture usage
- `tests/unit/test_rewrite.py` - Complex fixture usage (being migrated)

## Quick Reference Card

```python
# File System
def test_fs(temp_dir):                          # Empty temp directory
def test_fs(temp_project_with_files):           # Project with Python files

# MCP Tools
def test_tool(mcp_tools):                       # Get MCP tools
    find_code = mcp_tools("find_code")

# Caching
def test_cache(initialized_cache):              # Cache ready to use
def test_no_cache(cache_disabled):              # Cache explicitly disabled

# Mocking
def test_mock(mock_popen):                      # Mock streaming commands
def test_mock(mock_subprocess_run):             # Mock simple commands
def test_mock(mock_ast_grep_success):           # Mock successful ast-grep
def test_mock(mock_ast_grep_failure):           # Mock failed ast-grep

# Sample Data
def test_data(sample_search_result):            # Realistic search result
def test_data(sample_rewrite_result):           # Realistic rewrite result
def test_data(sample_duplication_data):         # Realistic duplication data

# Configuration
def test_config(test_config):                   # Test configuration
```

## Welcome to the Team!

You now know enough to write effective tests using fixtures. Remember:

1. **Use fixtures** - They're there to help you
2. **Don't use setup_method** - Pre-commit hook will block it
3. **Check documentation** - Quick reference has all fixtures
4. **Ask questions** - We're here to help!

Happy testing! 🎉
