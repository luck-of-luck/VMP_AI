# Refactoring Patterns - Proven Complexity Reduction Techniques

**Effectiveness:** 80-100% complexity reduction with zero behavioral regressions
**Last Updated:** 2025-11-28

## Pattern Selection Guide

Use this quick reference to choose the right pattern:

| Violation Type | Threshold | Best Pattern | Expected Reduction |
|---------------|-----------|--------------|-------------------|
| Cognitive >40 | Critical | Extract Method | 80-97% |
| Cyclomatic >30 | Critical | Configuration-Driven | 90-95% |
| Nesting >6 | Critical | Extract + Early Returns | 50-75% |
| Lines >150 | Critical | Service Layer Separation | 50-70% |
| Duplicate Code | Any | DRY Principle | Varies |

## Pattern 1: Extract Method

### When to Use
- **Best For:** High cognitive complexity (>40)
- **Indicators:** Long functions, multiple responsibilities, nested logic
- **Effectiveness:** 80-97% complexity reduction

### How It Works
Break monolithic functions into focused, single-responsibility helper functions. Each helper should do ONE thing well.

### Template
```python
# BEFORE: Monolithic function
def complex_function(data):
    # 100+ lines of mixed concerns
    # Validation logic
    # Business logic
    # Error handling
    # Response formatting
    return result

# AFTER: Orchestration with helpers
def complex_function(data):
    validated = _validate_input(data)
    processed = _process_data(validated)
    result = _format_response(processed)
    return result

def _validate_input(data):
    # 15-20 lines, single responsibility
    pass

def _process_data(data):
    # 20-30 lines, single responsibility
    pass

def _format_response(data):
    # 10-15 lines, single responsibility
    pass
```

### Real Examples

#### Example 1: _parallel_enrich (97% reduction)
**Before:** Cyclomatic=30, Cognitive=74, Nesting=7, Lines=117
**After:** Cyclomatic=3, Cognitive=2, Nesting=1, Lines=72

**Helpers Created:**
1. `_handle_enrichment_error` - Consolidated 3x duplicate error handling
2. `_process_completed_future` - Individual future processing
3. `_process_parallel_enrichment` - ThreadPoolExecutor logic
4. `_process_sequential_enrichment` - Non-parallel case

**Key Insight:** Consolidating duplicate error handling (appeared 3 times) drastically reduced cognitive load.

#### Example 2: _assess_breaking_change_risk (100% cognitive reduction)
**Before:** Cyclomatic=38, Cognitive=44
**After:** Cyclomatic=1, Cognitive=0

**Helpers Created:**
1. `_calculate_signature_change_risk` - Function signature changes
2. `_calculate_dependency_risk` - Dependency analysis
3. `_calculate_test_coverage_risk` - Test coverage assessment
4. `_calculate_usage_scope_risk` - Usage scope evaluation
5. `_calculate_import_change_risk` - Import pattern changes
6. `_determine_risk_level` - Risk level calculation

**Key Insight:** Extract one helper per risk factor. Each helper is simple and testable.

#### Example 3: _extract_classes (94% reduction)
**Before:** Cognitive=35, Nesting=7
**After:** Cognitive=2, Nesting=2

**Helpers Created:**
1. `_get_class_pattern(language)` - Pattern lookup
2. `_run_ast_grep_for_classes(...)` - Subprocess execution with early returns
3. `_process_class_matches(...)` - Match iteration
4. `_extract_class_info(...)` - Info extraction orchestration
5. `_extract_class_name(...)` - Name extraction
6. `_extract_line_range(...)` - Line numbers
7. `_count_methods_in_class(...)` - Method counting

**Key Insight:** Extract subprocess execution first (removes 3 nesting levels), then extract match processing.

### Guidelines

**Helper Function Characteristics:**
- ✅ Single responsibility (do ONE thing)
- ✅ 15-50 lines (sweet spot: 20-30)
- ✅ Descriptive names (`_validate_input` not `_helper1`)
- ✅ Maximum 2-3 levels of nesting
- ✅ Low complexity (cyclomatic <10)
- ✅ Easily testable in isolation

**Common Extraction Targets:**
1. **Validation logic** → `_validate_*` helpers
2. **Processing loops** → `_process_*` helpers
3. **Error handling** → `_handle_*` helpers
4. **Formatting/output** → `_format_*` helpers
5. **Calculation/logic** → `_calculate_*` helpers

**Avoid:**
- ❌ Single-line helpers (over-extraction)
- ❌ Helpers with >50 lines (insufficient extraction)
- ❌ Vague names (`_process`, `_helper`)
- ❌ Helpers that do multiple things
- ❌ Passing 5+ parameters (consider data classes)

## Pattern 2: Configuration-Driven Design

### When to Use
- **Best For:** High cyclomatic complexity (>30) from if-elif chains
- **Indicators:** Long if-elif-else chains, repetitive conditionals, hardcoded logic
- **Effectiveness:** 90-95% cyclomatic reduction

### How It Works
Replace imperative if-elif chains with declarative configuration dictionaries or dispatch tables.

### Template
```python
# BEFORE: Imperative if-elif chain
def generate_strategy(dup_type, language):
    if dup_type == "exact":
        if language == "python":
            return create_python_exact()
        elif language == "java":
            return create_java_exact()
        # ... 20 more elif blocks
    elif dup_type == "similar":
        # ... 15 more elif blocks
    # Cyclomatic: 37

# AFTER: Configuration-driven
STRATEGY_CONFIG = {
    ("exact", "python"): create_python_exact,
    ("exact", "java"): create_java_exact,
    ("similar", "python"): create_python_similar,
    # ... configuration entries
}

def generate_strategy(dup_type, language):
    key = (dup_type, language)
    generator = STRATEGY_CONFIG.get(key)
    if not generator:
        return default_strategy()
    return generator()
    # Cyclomatic: 2 (95% reduction!)
```

### Real Examples

#### Example 1: _generate_dedup_refactoring_strategies (95% reduction)
**Before:** Cyclomatic=37 (85% over limit)
**After:** Cyclomatic=2 (90% under limit)

**Configuration Created:**
```python
STRATEGY_CONFIG = {
    ("exact_duplicate", 5, "python"): ("extract_function", 9),
    ("exact_duplicate", 5, "java"): ("extract_method", 9),
    # ... 30+ entries
}

def _generate_dedup_refactoring_strategies(...):
    key = (duplication_type, min_lines, language)
    result = STRATEGY_CONFIG.get(key, DEFAULT)
    return _build_strategy_dict(result, ...)
```

**Key Insight:** Multi-dimensional configuration (type, lines, language) replaces massive nested if blocks.

#### Example 2: TYPE_INFERENCE_CONFIG (71-96% reduction in 3 functions)
**Before:** 3 functions with cyclomatic 22-24
**After:** All functions cyclomatic <8

**Configuration Created:**
```python
TYPE_INFERENCE_CONFIG = {
    ("python", "import"): _infer_python_import_type,
    ("python", "function_call"): _infer_python_function_call_type,
    ("javascript", "import"): _infer_javascript_import_type,
    # ... type inference handlers
}

def _infer_parameter_type(language, context, ...):
    key = (language, context)
    inferrer = TYPE_INFERENCE_CONFIG.get(key, _infer_generic_type)
    return inferrer(...)
```

**Key Insight:** Dispatch table pattern makes adding new languages/contexts trivial (add entry, not code).

### Guidelines

**Configuration Structure Options:**
1. **Simple Dict:** For single-dimension lookups
   ```python
   HANDLERS = {"python": handle_python, "java": handle_java}
   ```

2. **Tuple Keys:** For multi-dimension lookups
   ```python
   CONFIG = {("python", "exact"): handler1, ("java", "similar"): handler2}
   ```

3. **Nested Dicts:** For hierarchical lookups
   ```python
   CONFIG = {"python": {"exact": handler1, "similar": handler2}}
   ```

4. **Dataclasses/NamedTuples:** For complex configurations
   ```python
   @dataclass
   class StrategyConfig:
       pattern: str
       handler: Callable
       priority: int
   ```

**When to Use:**
- ✅ Repetitive if-elif chains (>5 branches)
- ✅ Logic varies by parameters (type, language, mode)
- ✅ Need to add new cases frequently
- ✅ Branches are independent
- ✅ Can express as lookup/dispatch

**When NOT to Use:**
- ❌ Complex conditional logic (use Extract Method)
- ❌ Interdependent conditions
- ❌ Stateful decision trees
- ❌ Only 2-3 simple conditions

**Benefits:**
- Extensibility: Add new cases via data, not code
- Testability: Test configuration separately
- Readability: Intent clear from structure
- Maintainability: Single location for all cases

## Pattern 3: Service Layer Separation

### When to Use
- **Best For:** MCP tool wrappers, API endpoints, long functions (>150 lines)
- **Indicators:** Mixed concerns (validation + logic + formatting), hard to test
- **Effectiveness:** 50-70% LOC reduction per function

### How It Works
Separate thin interface layer (MCP tool, API endpoint) from business logic implementation.

### Template
```python
# BEFORE: Mixed concerns (150+ lines)
def mcp_tool(args):
    # Argument validation (20 lines)
    # Business logic (80 lines)
    # Error handling (30 lines)
    # Response formatting (20 lines)
    return result

# AFTER: Service layer separation
def mcp_tool(args):
    """Thin MCP wrapper - validation and formatting only."""
    validated = _validate_args(args)
    result = service_impl(validated)  # Business logic in service
    return _format_response(result)

def service_impl(params):
    """Pure business logic - easy to test."""
    # Core logic (60 lines, no MCP coupling)
    return result

def _validate_args(args):
    # Validation logic (15 lines)
    pass

def _format_response(result):
    # Formatting logic (12 lines)
    pass
```

### Real Examples

#### Example 1: Tool Wrappers (5 functions refactored)
**Functions:**
1. `enforce_standards_tool` → Extracted `_validate_enforcement_inputs()`
2. `detect_code_smells_tool` → Extracted `_prepare_smell_detection_params()`, `_process_smell_detection_result()`
3. `extract_function_tool` → Extracted `_format_extract_function_response()`
4. `register_search_tools` → Split into 4 registration functions (158→8 lines main)

**Pattern Applied:**
```python
# Tool wrapper (thin)
def tool_name(args):
    validated = _validate_tool_args(args)
    result = service_function(validated)
    return _format_tool_response(result)

# Service layer (business logic)
def service_function(params):
    # Pure logic, no MCP coupling
    return business_result
```

**Key Insight:** Tool wrappers should be <50 lines. Extract validation, processing, and formatting to helpers.

### Guidelines

**Layer Responsibilities:**

**Interface Layer (MCP Tool/API Endpoint):**
- ✅ Argument validation
- ✅ Response formatting
- ✅ Error translation (service errors → API errors)
- ✅ Logging/monitoring hooks
- ❌ NO business logic
- ❌ NO complex processing

**Service Layer (Business Logic):**
- ✅ Core business logic
- ✅ Data processing
- ✅ Orchestration
- ✅ Domain rules
- ❌ NO MCP/API coupling
- ❌ NO response formatting

**Benefits:**
- Testability: Service layer has no MCP dependencies
- Reusability: Service functions can be used by multiple interfaces
- Maintainability: Clear separation of concerns
- Performance: Service layer can be optimized independently

## Pattern 4: Early Returns / Guard Clauses

### When to Use
- **Best For:** Deep nesting (>6), complex conditionals
- **Indicators:** Nested if blocks, "arrow code" pattern
- **Effectiveness:** 37-75% nesting reduction

### How It Works
Invert conditionals to fail fast, reducing nesting depth.

### Template
```python
# BEFORE: Nested conditionals (nesting=8)
def process(data):
    if data:
        if data.valid:
            if data.items:
                for item in data.items:
                    if item.active:
                        if item.ready:
                            # Process
                            pass

# AFTER: Early returns (nesting=3)
def process(data):
    if not data or not data.valid or not data.items:
        return []

    return [
        _process_item(item)
        for item in data.items
        if _should_process(item)
    ]

def _should_process(item):
    return item.active and item.ready
```

### Real Examples

#### Example 1: scan_for_secrets_regex (75% nesting reduction)
**Before:** Nesting=8, Cognitive=36
**After:** Nesting=2, Cognitive=2

**Pattern Applied:**
```python
# Before
def scan(...):
    if directory:
        for file in files:
            if not skip_file(file):
                if open_file:
                    for line in file:
                        if pattern.match(line):
                            # Deep nesting

# After
def scan(...):
    if not directory:
        return []

    files_to_scan = _get_scannable_files(directory)
    return _scan_files_for_secrets(files_to_scan, patterns)

def _scan_files_for_secrets(files, patterns):
    # Flat structure with early continues
    for file in files:
        results.extend(_scan_single_file(file, patterns))
```

### Guidelines

**When to Apply:**
1. **Validation at start** → Fail fast
2. **Loop filtering** → Skip items early with `continue`
3. **Optional processing** → Return None/default early
4. **Error cases** → Handle errors first, happy path last

**Pattern:**
```python
# Guard clauses first
if not precondition1:
    return default

if not precondition2:
    return default

# Happy path last (not nested)
return main_logic()
```

**Benefits:**
- Reduced cognitive load (flat structure)
- Faster failure (don't compute if invalid)
- Clearer intent (validations grouped)
- Easier testing (each path independent)

## Pattern 5: DRY Principle (Don't Repeat Yourself)

### When to Use
- **Best For:** Duplicate code blocks, copy-pasted functions
- **Indicators:** Nearly identical functions, repeated logic patterns
- **Effectiveness:** Varies (118 lines eliminated in one case)

### How It Works
Extract common logic to shared utility functions or modules. Create single source of truth.

### Template
```python
# BEFORE: Duplicate functions
# File 1
def process_a(data):
    # 60 lines of logic
    # 40 lines identical to process_b
    pass

# File 2
def process_b(data):
    # 60 lines of logic
    # 40 lines identical to process_a
    pass

# AFTER: Shared utility
# utils/shared.py
def process_common(data, mode):
    # 40 lines of common logic
    pass

# File 1
def process_a(data):
    result = process_common(data, mode="a")
    # 20 lines of A-specific logic
    return result

# File 2
def process_b(data):
    result = process_common(data, mode="b")
    # 20 lines of B-specific logic
    return result
```

### Real Example

#### _suggest_syntax_fix DRY Violation (118 lines eliminated)
**Before:**
- `applicator_validator.py:_suggest_syntax_fix` (cyclomatic=23)
- `applicator_post_validator.py:_suggest_syntax_fix` (cyclomatic=24)
- Nearly identical logic, 118 lines of duplication

**After:**
```python
# utils/syntax_validation.py (NEW)
ERROR_SUGGESTIONS = {
    ("python", "IndentationError"): [
        "Check indentation (4 spaces)",
        "Verify tab vs spaces consistency"
    ],
    ("javascript", "SyntaxError"): [
        "Check missing semicolons",
        "Verify bracket matching"
    ],
    # ... configuration for all languages/errors
}

def suggest_syntax_fix(language, error_type, error_msg):
    """Single source of truth for syntax fix suggestions."""
    key = (language, error_type)
    suggestions = ERROR_SUGGESTIONS.get(key, _get_generic_suggestions(error_msg))
    return _format_suggestions(suggestions)

# applicator_validator.py
def _suggest_syntax_fix(result):
    return suggest_syntax_fix(result.language, result.error_type, result.error_msg)

# applicator_post_validator.py
def _suggest_syntax_fix(result):
    return suggest_syntax_fix(result.language, result.error_type, result.error_msg)
```

**Impact:**
- Removed 118 lines of duplicate code
- Single source of truth for syntax validation
- Both original functions eliminated from violations
- Easier to add new languages/error types

### Guidelines

**DRY Assessment:**
1. **Identify duplication:** Look for copy-pasted code
2. **Extract commonality:** What's truly shared?
3. **Preserve differences:** What's unique to each case?
4. **Create abstraction:** Shared utility + mode/config parameter

**When to Extract:**
- ✅ >20 lines of duplicate logic
- ✅ Logic will evolve together
- ✅ Clear abstraction exists
- ✅ Reduces overall complexity

**When NOT to Extract:**
- ❌ Accidental similarity (will diverge)
- ❌ Creates complex abstraction (worse than duplication)
- ❌ <10 lines of simple code
- ❌ Coupling unrelated modules

**Benefits:**
- Single source of truth (one place to fix bugs)
- Reduced LOC (less code to maintain)
- Consistency (all usages behave identically)
- Easier updates (change once, applies everywhere)

## Pattern Combination Strategies

### Strategy 1: High Cognitive + High Cyclomatic
**Example:** _parallel_enrich (cognitive=74, cyclomatic=30)

**Approach:**
1. **Extract Method first** → Reduce cognitive by breaking into helpers
2. **Configuration-Driven** → Replace any if-elif chains in helpers
3. **Early Returns** → Flatten any remaining nesting

**Result:** 97% cognitive reduction, 90% cyclomatic reduction

### Strategy 2: Duplicate Complex Functions
**Example:** Two _extract_classes functions (cognitive=35 each)

**Approach:**
1. **Refactor one first** → Establish pattern
2. **Apply same pattern to second** → Ensure consistency
3. **Consider shared utility** → Extract true commonality

**Result:** Consistent 94% reduction in both, potential for shared helpers

### Strategy 3: Tool Wrappers with Deep Logic
**Example:** MCP tool wrappers (lines=150+, cyclomatic=22)

**Approach:**
1. **Service Layer Separation** → Extract business logic
2. **Extract Method** → Break down validation/formatting
3. **Configuration-Driven** → Replace hardcoded logic

**Result:** 60-70% LOC reduction, <20 cyclomatic in all functions

## Testing Strategy

### Test After Each Refactoring
```bash
# Module-specific tests
uv run pytest tests/unit/test_<module>*.py -v

# Complexity regression
uv run pytest tests/quality/test_complexity_regression.py -v

# Full suite (if time permits)
uv run pytest tests/ -q --tb=no
```

### Verification Checklist
- [ ] All module tests passing
- [ ] Complexity regression test passing
- [ ] Function no longer in violations list
- [ ] No behavioral changes (outputs identical)
- [ ] Type checking passes (mypy)
- [ ] Linting passes (ruff)

## Common Pitfalls & Solutions

### Pitfall 1: Over-Extraction
**Problem:** Creating too many tiny helpers (1-5 lines each)
**Solution:** Aim for 20-30 line helpers. Group related logic.

### Pitfall 2: Vague Names
**Problem:** Helpers named `_helper1`, `_process`, `_do_thing`
**Solution:** Use descriptive action-oriented names: `_validate_input`, `_calculate_risk_score`

### Pitfall 3: Configuration Complexity
**Problem:** Configuration becomes more complex than original if-elif
**Solution:** Only use config-driven for truly repetitive logic (>5 similar branches)

### Pitfall 4: Breaking Behavior
**Problem:** Subtle changes during refactoring
**Solution:** Run tests IMMEDIATELY after each change. Don't batch test runs.

### Pitfall 5: Missing Edge Cases
**Problem:** Edge cases handled in original but lost in refactoring
**Solution:** Read ALL code carefully. Preserve ALL logic, even ugly edge case handling.

## Tools for Refactoring

### Code-Refactor-Agent
- **Best For:** Complex refactorings (cognitive >40)
- **Model:** Use Opus for highest quality
- **Benefits:** Autonomous, comprehensive testing, detailed documentation
- **Usage:**
  ```python
  Task(
      subagent_type='code-refactor-agent',
      description='Refactor function_name',
      model='opus',
      prompt='Detailed refactoring instructions...'
  )
  ```

### Manual Refactoring
- **Best For:** Simple refactorings (minimal violations)
- **Tools:** Read, Edit, Write
- **When:** Cyclomatic <25, clear pattern, quick fix

### Hybrid Approach
- **Best For:** Batches of similar functions
- **Strategy:** Use agent for first, apply pattern manually to rest
- **Example:** Refactored _extract_classes with agent, applied same pattern to _extract_classes_from_file manually

## Success Metrics

### Quantitative Targets
- Cyclomatic ≤ 20
- Cognitive ≤ 30
- Nesting ≤ 6
- Lines ≤ 150

### Quality Indicators
- All tests passing
- No behavioral regressions
- Improved maintainability
- Better testability
- Enhanced readability

## Quick Reference

| Symptom | Pattern | Key Technique | Expected Result |
|---------|---------|---------------|-----------------|
| Cognitive >40 | Extract Method | 4-6 focused helpers | 80-97% ↓ |
| Cyclomatic >30 | Config-Driven | Lookup dict/dispatch | 90-95% ↓ |
| Nesting >6 | Early Returns | Guard clauses | 50-75% ↓ |
| Lines >150 | Service Layer | Business logic extraction | 50-70% ↓ |
| Duplicate Code | DRY Principle | Shared utility | Varies |
| Tool Wrapper | Service Separation | Thin wrapper + service | 60-70% ↓ |

## Conclusion

These patterns, proven through 48 successful refactorings, provide a systematic approach to complexity reduction. Key principles:

1. **Choose the right pattern** based on violation type
2. **Test immediately** after each change
3. **Combine patterns** for complex cases
4. **Use automation** (code-refactor-agent) for difficult refactorings
5. **Maintain zero regressions** through comprehensive testing

With these patterns, achieving 80-100% complexity reduction while preserving all functionality is not just possible—it's repeatable and systematic.

---

**Pattern Effectiveness:** 80-100% complexity reduction
**Success Rate:** 48/48 functions (100%)
**Behavioral Regressions:** 0 (zero)
**Test Coverage:** 15/15 regression tests, 278 module tests (100% pass)
**Last Updated:** 2025-11-28
