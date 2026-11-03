"""ast-grep documentation content for LLM context.

This module provides condensed ast-grep documentation that can be
retrieved on-demand to provide context to LLMs, reducing hallucinations
and improving pattern/rule writing accuracy.

Based on: https://ast-grep.github.io/llms-full.txt
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from ast_grep_mcp.constants import FormattingDefaults

AST_GREP_DOCS: Dict[str, str] = {
    "pattern": """# ast-grep Pattern Syntax

## Overview
Patterns are code snippets that match against target code using AST (Abstract Syntax Tree)
structure. Unlike text-based regex, patterns understand code syntax.

## Key Principle
**Pattern code must be valid, parseable code** that tree-sitter can parse.

## Metavariables
Metavariables are placeholders that match AST nodes. They use `$` prefix.

### Single-Node Metavariables: `$NAME`
- Match exactly ONE AST node
- Must use UPPERCASE letters, underscores, or digits (1-9)
- Valid: `$NAME`, `$VAR1`, `$MY_VAR`, `$_`, `$_123`
- Invalid: `$name` (lowercase), `$123` (starts with digit), `$KEBAB-CASE` (hyphen)

Examples:
```
function $NAME() { }     # Matches: function foo() { }
$OBJ.$METHOD()           # Matches: console.log(), arr.push()
$A == $A                 # Matches: x == x (same var both sides)
```

### Multi-Node Metavariables: `$$$` or `$$$NAME`
- Match ZERO OR MORE AST nodes
- Essential for function arguments, array elements, statement blocks

Examples:
```
foo($$$ARGS)             # Matches: foo(), foo(a), foo(a, b, c)
function $F($$$PARAMS) { $$$BODY }   # Matches any function
[$$$ELEMENTS]            # Matches any array literal
```

### Non-Capturing: `$_` or `$_NAME`
- Match but don't capture (performance optimization)
- Use when you don't need the matched value

Example:
```
$_FUNC($_ARG)            # Matches any function call, doesn't capture
```

### Unnamed Node Capture: `$$VAR`
- Captures unnamed tree-sitter nodes (advanced usage)
- Rarely needed in typical patterns

## Pattern Matching Rules
1. Patterns match at the AST level, not text level
2. Whitespace and formatting differences are ignored
3. Same metavariable name enforces structural equality: `$A == $A` matches `x == x` but not `x == y`
4. Nested patterns match nested code

## Pattern Objects (context + selector)

⚠️ **This solves the #1 "my pattern doesn't match" issue!**

When your pattern is a code fragment that isn't valid standalone code, use a pattern object
with `context` and `selector` to provide parsing context.

### The Problem
```yaml
# ❌ FAILS: "key": "$VAL" isn't valid standalone JavaScript
rule:
  pattern: '"key": "$VAL"'
```

### The Solution
```yaml
# ✅ WORKS: Provide full context, select the part you want
rule:
  pattern:
    context: '{"key": "$VAL"}'
    selector: pair
```

### How It Works
1. `context`: Valid, parseable code containing your target pattern
2. `selector`: The AST node kind to actually match (use `dump_syntax_tree` to find it)

### Common Use Cases

**JSON key-value pairs:**
```yaml
pattern:
  context: '{"key": "$VAL"}'
  selector: pair
```

**Object properties in JavaScript:**
```yaml
pattern:
  context: '({foo: $VAL})'
  selector: pair
```

**Function parameters (not full function):**
```yaml
pattern:
  context: 'function f($PARAM: $TYPE) {}'
  selector: required_parameter
```

**Go function calls (need context for parsing):**
```yaml
pattern:
  context: 'package main; func f() { io.Copy($DST, $SRC) }'
  selector: call_expression
```

**C struct fields:**
```yaml
pattern:
  context: 'struct S { $TYPE $NAME; };'
  selector: field_declaration
```

### When to Use Pattern Objects
- Pattern doesn't match and you've verified metavariable syntax
- Your pattern is a sub-expression (not a complete statement)
- tree-sitter can't parse your pattern as standalone code
- You're matching language constructs that need surrounding context

### Finding the Right Selector
Use `dump_syntax_tree` to see the AST structure:
```
dump_syntax_tree(code='{"key": "value"}', language="json", format="named")
```
Look for the node kind that wraps exactly what you want to match.

## Common Patterns by Language

### JavaScript/TypeScript
```
console.log($$$ARGS)                    # Console logs
import $NAME from '$PATH'               # Named imports
const $NAME = ($$$PARAMS) => $BODY      # Arrow functions
async function $NAME($$$) { $$$BODY }   # Async functions
```

### Python
```
def $NAME($$$PARAMS): $$$BODY           # Function definitions
import $MODULE                          # Imports
class $NAME: $$$BODY                    # Class definitions
for $VAR in $ITER: $$$BODY              # For loops
```

### Go
```
func $NAME($$$PARAMS) $RET { $$$BODY }  # Functions
if err != nil { $$$BODY }               # Error handling
go $FUNC($$$ARGS)                       # Goroutines
```

## Best Practices
1. Start simple, add complexity gradually
2. Use `dump_syntax_tree` to understand code structure
3. Test patterns with `test_match_code_rule` before deployment
4. Use `debug_pattern` when patterns don't match as expected
5. Verify patterns in the ast-grep playground: https://ast-grep.github.io/playground.html

## Online Playground
Test patterns interactively at: **https://ast-grep.github.io/playground.html**

The playground lets you:
- Write and test patterns in real-time
- See the AST structure of your code
- Debug why patterns don't match
- Share patterns via URL
""",
    "rules": """# ast-grep YAML Rule Configuration

## Rule Structure
Every YAML rule must have these required fields:

```yaml
id: unique-rule-identifier    # Required: unique ID for the rule
language: python              # Required: target language
rule:                         # Required: the matching rule
  pattern: def $NAME($$$): $$$
```

## Optional Fields
```yaml
message: "Description of what was found"   # Human-readable message
severity: warning                          # error, warning, info, hint
fix: "replacement code"                    # Auto-fix template
```

## Rule Object
The `rule` field can contain:

### Atomic Rules (match specific nodes)
- `pattern`: Match code structure
- `kind`: Match node type (e.g., `function_declaration`)
- `regex`: Match node text with regex (Rust regex syntax)

### Relational Rules (match based on position)
- `inside`: Match nodes inside a parent
- `has`: Match nodes containing a child
- `follows`: Match nodes after another
- `precedes`: Match nodes before another

### Composite Rules (combine rules)
- `all`: ALL sub-rules must match (AND)
- `any`: ANY sub-rule must match (OR)
- `not`: Rule must NOT match (negation)
- `matches`: Reference a utility rule by ID (for reuse and recursion)

## The `matches` Rule (Reusable & Recursive Patterns)

The `matches` rule references another rule by its ID, enabling:
- **Rule reuse**: Define once, use in multiple places
- **Recursive patterns**: Match nested structures (e.g., nested function calls)
- **Modular rules**: Break complex rules into smaller, testable pieces

### Basic Usage

Define utility rules in `utils` section, reference with `matches`:

```yaml
id: find-dangerous-calls
language: javascript
utils:
  is-user-input:
    any:
      - pattern: req.body.$PROP
      - pattern: req.query.$PROP
      - pattern: req.params.$PROP
rule:
  pattern: eval($ARG)
  has:
    stopBy: end
    matches: is-user-input    # References the utility rule
```

### Recursive Matching

Match deeply nested structures by having a rule reference itself:

```yaml
id: find-nested-callbacks
language: javascript
utils:
  callback-pattern:
    any:
      - pattern: $FN($$$, function($$$) { $$$BODY })
      - pattern: $FN($$$, ($$$) => { $$$BODY })
      # Recursive: callback containing another callback
      - all:
          - pattern: $FN($$$, function($$$) { $$$BODY })
          - has:
              stopBy: end
              matches: callback-pattern
rule:
  matches: callback-pattern
```

### Multiple Utility Rules

Combine multiple utilities for complex matching:

```yaml
id: security-audit
language: javascript
utils:
  sql-sink:
    any:
      - pattern: $DB.query($$$)
      - pattern: $DB.execute($$$)
  user-input:
    any:
      - pattern: req.body
      - pattern: req.query
rule:
  matches: sql-sink
  has:
    stopBy: end
    matches: user-input
message: "Potential SQL injection: user input flows to SQL query"
```

### Key Points
- Utility rules are defined in the `utils` section at the top level
- `matches` takes a string: the ID of the utility rule
- Utility rules can reference other utility rules
- Be careful with infinite recursion in self-referencing rules

## The `stopBy` Parameter (CRITICAL!)

⚠️ **This is the #1 source of "why doesn't my rule match?" issues**

Relational rules have a `stopBy` parameter:
- `neighbor` (DEFAULT): Only checks IMMEDIATE parent/sibling
- `end`: Searches to tree boundaries (usually what you want!)
- Custom rule object: Stops when match is found

### WRONG (common mistake):
```yaml
rule:
  pattern: $CALL
  inside:
    kind: function_declaration   # Missing stopBy: end!
```

### CORRECT:
```yaml
rule:
  pattern: $CALL
  inside:
    stopBy: end                  # Searches entire tree!
    kind: function_declaration
```

## Rule Ordering

⚠️ **Rule objects are UNORDERED!**

YAML doesn't guarantee field order. If order matters, use `all`:

```yaml
rule:
  all:
    - pattern: $FIRST
    - follows:
        pattern: $SECOND
```

## Complete Example

```yaml
id: no-console-in-production
language: javascript
severity: warning
message: "Remove console.log before production"
rule:
  any:
    - pattern: console.log($$$)
    - pattern: console.warn($$$)
    - pattern: console.error($$$)
  inside:
    stopBy: end
    kind: function_declaration
fix: ""
```

## Strictness Modes
For pattern matching, you can adjust strictness:
- `cst` (strictest): Match exact concrete syntax
- `smart` (default): Ignore trivial differences
- `ast`: Match abstract syntax only
- `relaxed`: More lenient matching
- `signature`: Match function signatures only

```yaml
rule:
  pattern:
    context: "function $F($$$) { $$$BODY }"
    strictness: relaxed
```
""",
    "strictness": """# ast-grep Strictness Modes

Strictness controls which AST nodes are skipped during pattern matching.
The principle: **the less a pattern specifies, the more code it can match**.

## Quick Reference

| Mode | Skips in Pattern | Skips in Code | Use Case |
|------|------------------|---------------|----------|
| `cst` | Nothing | Nothing | Exact syntax matching |
| `smart` | Nothing | Unnamed nodes | **Default** - balanced matching |
| `ast` | Unnamed nodes | Unnamed nodes | Ignore syntax variations |
| `relaxed` | Unnamed + comments | Unnamed + comments | Ignore comments |
| `signature` | Text content | Text content | Structure-only matching |

## The Five Modes

### `cst` (Concrete Syntax Tree) - Strictest
- **Behavior:** All nodes must match exactly. No nodes are skipped.
- **When to use:** Need absolute precision, exact syntax match required
- **Note:** Rarely needed; may fail on trivial whitespace/formatting differences

### `smart` (Default) ⭐
- **Behavior:** All pattern nodes must match. Unnamed nodes in target code are skipped.
- **When to use:** Most use cases - balances specificity with flexibility
- **Example:**
  ```javascript
  // Pattern: function $NAME() { }
  // Matches: function foo() { }
  // Matches: async function bar() { }  (skips 'async' keyword in target)
  ```

### `ast` (Abstract Syntax Tree)
- **Behavior:** Only named nodes are matched. Unnamed nodes skipped on both sides.
- **When to use:** Ignore syntactic variations like quote styles
- **Example:**
  ```javascript
  // Pattern: import $NAME from 'lib'
  // Matches: import foo from 'lib'    (single quotes)
  // Matches: import bar from "lib"    (double quotes)
  ```

### `relaxed`
- **Behavior:** Named nodes matched. Comments and unnamed nodes skipped.
- **When to use:** Comments in code shouldn't affect matching
- **Example:**
  ```javascript
  // Pattern: foo($ARG)
  // Matches: foo(bar)
  // Matches: foo(/* comment */ bar)   (comment is ignored)
  ```

### `signature` - Most Relaxed
- **Behavior:** Only node kinds are matched. Text content is ignored.
- **When to use:** Match structural patterns regardless of identifiers/literals
- **Example:**
  ```javascript
  // Pattern: foo(bar)
  // Matches: foo(bar)
  // Matches: baz(qux)  (same structure: call with one argument)
  ```
- **Warning:** Very permissive - may match more than expected!

## How to Set Strictness

### In YAML Rules
```yaml
rule:
  pattern:
    context: $FUNC($$$ARGS)
    strictness: relaxed
```

### Using build_rule Tool
The `build_rule` tool doesn't yet support strictness, but you can manually add it
to the generated YAML.

## When to Change from Default (`smart`)

| Situation | Try This |
|-----------|----------|
| Pattern matches too little | `ast` or `relaxed` |
| Pattern matches too much | `cst` |
| Quote styles vary (' vs ") | `ast` |
| Inline comments interfere | `relaxed` |
| Need structure-only matching | `signature` |
| Default isn't working | Check metavariables first! |

## Common Mistakes

### 1. Using `signature` When You Want Exact Text
```yaml
# Wrong: Will match ANY function call with one arg
rule:
  pattern:
    context: dangerousFunction($ARG)
    strictness: signature
```

### 2. Using `cst` Unnecessarily
```yaml
# Usually overkill - smart handles most cases
rule:
  pattern:
    context: console.log($MSG)
    strictness: cst  # Rarely needed
```

### 3. Forgetting That Strictness Affects Both Directions (for some modes)
```yaml
# With 'ast', unnamed nodes in YOUR pattern are also skipped!
# Be explicit about what you want to match.
```

## Best Practices

1. **Start with `smart`** (the default) - it's designed for most use cases
2. **Use `ast`** when quote styles or minor syntax differences cause false negatives
3. **Use `relaxed`** when matching code with inline comments
4. **Use `signature`** only for structural refactoring tools
5. **Avoid `cst`** unless you have a specific need for exact matching
6. **Test your rules** with `test_match_code_rule` to verify behavior
""",
    "relational": """# ast-grep Relational Rules

Relational rules match nodes based on their position relative to other nodes.

## The Four Relational Rules

### `inside` - Match nodes WITHIN a parent
```yaml
rule:
  pattern: console.log($$$)
  inside:
    stopBy: end
    kind: function_declaration
```
Matches `console.log()` calls that are inside a function.

### `has` - Match nodes that CONTAIN a child
```yaml
rule:
  kind: function_declaration
  has:
    stopBy: end
    pattern: return $VALUE
```
Matches functions that have a return statement.

### `follows` - Match nodes that come AFTER another
```yaml
rule:
  pattern: $USAGE
  follows:
    pattern: const $NAME = $VALUE
```
Matches code that follows a const declaration.

### `precedes` - Match nodes that come BEFORE another
```yaml
rule:
  pattern: const $NAME = $VALUE
  precedes:
    pattern: $NAME($$$)
```
Matches const declarations before their usage.

## The `stopBy` Parameter

⚠️ **CRITICAL: Always specify stopBy for relational rules!**

| Value | Behavior | When to Use |
|-------|----------|-------------|
| `neighbor` | Only immediate parent/sibling (DEFAULT) | Rarely what you want |
| `end` | Search to tree boundary | Most common use case |
| `{rule}` | Stop when rule matches | Advanced filtering |

### Examples

**Find console.log anywhere inside a function:**
```yaml
rule:
  pattern: console.log($$$)
  inside:
    stopBy: end              # Search up the entire tree
    kind: function_declaration
```

**Find console.log only at top level of function (immediate child):**
```yaml
rule:
  pattern: console.log($$$)
  inside:
    stopBy: neighbor         # Only immediate parent
    kind: block              # Function body block
```

**Find variables declared inside try blocks, stopping at function boundary:**
```yaml
rule:
  pattern: let $NAME = $VALUE
  inside:
    stopBy:
      kind: function_declaration   # Stop at function boundary
    kind: try_statement
```

## The `field` Parameter

Specify which child field to match (for `inside` and `has`):

```yaml
rule:
  kind: if_statement
  has:
    field: condition         # Only match in the condition field
    pattern: $A == null
```

## Combining Relational Rules

Use `all` to combine multiple relational constraints:

```yaml
rule:
  all:
    - pattern: $VAR
    - inside:
        stopBy: end
        kind: function_declaration
    - follows:
        pattern: const $VAR = $$$
```

## Common Patterns

### Find function calls inside async functions:
```yaml
rule:
  pattern: await $PROMISE
  inside:
    stopBy: end
    pattern: async function $NAME($$$) { $$$BODY }
```

### Find unused variables (declared but not used):
```yaml
rule:
  pattern: const $NAME = $VALUE
  not:
    has:
      stopBy: end
      pattern: $NAME
```

### Find error handling patterns:
```yaml
rule:
  kind: catch_clause
  has:
    stopBy: end
    pattern: console.error($$$)
```
""",
    "metavariables": """# ast-grep Metavariable Reference

Metavariables are placeholders in patterns that match AST nodes.

## Quick Reference Table

| Syntax | Name | Matches | Example |
|--------|------|---------|---------|
| `$NAME` | Single | One AST node | `$FUNC()` |
| `$$$` | Multi (anonymous) | Zero or more nodes | `foo($$$)` |
| `$$$NAME` | Multi (named) | Zero or more nodes | `foo($$$ARGS)` |
| `$_` | Non-capturing | One node (not captured) | `$_($$$)` |
| `$_NAME` | Non-capturing named | One node (not captured) | `$_FUNC($_ARG)` |
| `$$VAR` | Unnamed | Unnamed tree-sitter nodes | Advanced |

## Valid Naming Rules

### VALID metavariable names:
- `$NAME` - uppercase letters
- `$MY_VAR` - uppercase with underscores
- `$VAR1` - uppercase with trailing digits
- `$_` - single underscore (non-capturing wildcard)
- `$_123` - underscore with digits

### INVALID metavariable names:
- `$name` - ❌ lowercase letters not allowed
- `$myVar` - ❌ mixed case not allowed
- `$123` - ❌ cannot start with digit
- `$KEBAB-CASE` - ❌ hyphens not allowed
- `$` - ❌ bare dollar sign

## Single-Node Metavariables: `$NAME`

Match exactly one AST node.

```javascript
// Pattern: $OBJ.$METHOD($$$ARGS)
// Matches:
console.log("hello")     // $OBJ=console, $METHOD=log
array.push(1, 2, 3)      // $OBJ=array, $METHOD=push
user.getName()           // $OBJ=user, $METHOD=getName
```

### Structural Equality
Same metavariable name must match identical structure:

```javascript
// Pattern: $A == $A
// Matches: x == x, foo.bar == foo.bar
// Does NOT match: x == y, a.b == a.c
```

## Multi-Node Metavariables: `$$$`

Match zero or more consecutive AST nodes.

### In Function Arguments
```javascript
// Pattern: foo($$$ARGS)
// Matches:
foo()              // $$$ARGS = (empty)
foo(a)             // $$$ARGS = a
foo(a, b, c)       // $$$ARGS = a, b, c
```

### In Function Parameters
```javascript
// Pattern: function $NAME($$$PARAMS) { $$$BODY }
// Matches any function with any number of parameters
```

### In Arrays
```javascript
// Pattern: [$$$ELEMENTS]
// Matches: [], [1], [1, 2, 3], ["a", "b"]
```

### In Statements
```javascript
// Pattern: { $$$STATEMENTS }
// Matches any block with any statements
```

### ⚠️ Multi-Metavariable Laziness (Important!)

**Multi-metavariables (`$$$`) are LAZY** - they stop matching as soon as the
next part of the pattern can match. This is subtle but critical behavior!

**How It Works:**
```javascript
// Pattern: foo($$$A, b, $$$C)
// Code:    foo(a, c, b, b, c)

// Result:
// $$$A = a, c     (stops at first 'b')
// $$$C = b, c     (captures the rest)
```

**Key Insight:** `$$$A` stops before the first `b` because `b` is the next
literal in the pattern. It doesn't greedily consume all nodes.

**Another Example:**
```javascript
// Pattern: [$$$FIRST, 0, $$$REST]
// Code:    [1, 2, 0, 3, 0, 4]

// Result:
// $$$FIRST = 1, 2    (stops at first 0)
// $$$REST = 3, 0, 4  (captures everything after first 0)
```

**Implications:**
1. Order matters in patterns with multiple `$$$` variables
2. Literal values between `$$$` act as "stop points"
3. The first `$$$` is NOT greedy - it yields to the next pattern element

**Common Pitfall:**
```javascript
// Pattern: foo($$$ARGS, callback)
// Code:    foo(a, b, callback, callback)

// You might expect $$$ARGS = a, b, callback
// But actually: $$$ARGS = a, b (stops at first 'callback')
```

**Workaround for Greedy Matching:**
If you need greedy behavior, restructure your pattern or use multiple rules
with `any` to handle different cases.

## Non-Capturing: `$_`

Use when you need to match but don't care about the value.
Performance optimization - doesn't store the match.

```javascript
// Pattern: $_FUNC($_ARG)
// Matches any single-argument function call
// Both $_FUNC and $_ARG can be different in the match
```

vs:

```javascript
// Pattern: $FUNC($ARG)
// Captures both the function name and argument
```

## Common Mistakes

### 1. Using lowercase metavariables
```
❌ $name, $myVar
✅ $NAME, $MY_VAR
```

### 2. Single metavariable for multiple arguments
```
❌ foo($ARG)      - Only matches foo(x), not foo(x, y)
✅ foo($$$ARGS)   - Matches foo(), foo(x), foo(x, y, z)
```

### 3. Forgetting $$$  in function definitions
```
❌ def $NAME($PARAM):     - Only matches single-param functions
✅ def $NAME($$$PARAMS):  - Matches any number of params
```

## Metavariables in Fixes

Metavariables captured in patterns can be used in fix templates:

```yaml
id: convert-to-template-literal
language: javascript
rule:
  pattern: $A + $B
fix: "`${$A}${$B}`"
```

Input: `name + greeting`
Output: `` `${name}${greeting}` ``
""",
    "workflow": """# ast-grep Development Workflow

## Recommended Iterative Approach

The ast-grep documentation recommends an iterative, trial-and-error workflow:

### 1. Start Simple
Begin with a basic pattern using `find_code`:
```
find_code(pattern="console.log($$$)", language="javascript")
```

### 2. Understand the Structure
Use `dump_syntax_tree` to see how code is parsed:
```
dump_syntax_tree(code="function foo() { console.log('hi'); }",
                 language="javascript",
                 format="cst")
```

### 3. Build Incrementally
Add complexity one step at a time:
1. Start with the core pattern
2. Add one relational rule
3. Test after each addition
4. Debug failures before adding more

### 4. Test Iterations
Use `test_match_code_rule` to validate against sample code:
```
test_match_code_rule(
    code="function foo() { console.log('test'); }",
    yaml_rule=your_rule
)
```

### 5. Debug Failures
Use `debug_pattern` when patterns don't match:
```
debug_pattern(
    pattern="console.log($message)",  # Wrong! lowercase
    code="console.log('hello')",
    language="javascript"
)
```

## Tool Selection Guide

| Task | Tool |
|------|------|
| Quick pattern search | `find_code` |
| Complex rules (relational, composite) | `find_code_by_rule` |
| Understand code structure | `dump_syntax_tree` |
| Validate rule against sample | `test_match_code_rule` |
| Debug pattern matching issues | `debug_pattern` |
| Build rule from components | `build_rule` |
| Get documentation help | `get_ast_grep_docs` |
| Interactive testing | [ast-grep Playground](https://ast-grep.github.io/playground.html) |

## Common Development Patterns

### Pattern 1: Find and Refine
```
1. find_code with broad pattern
2. Review results
3. Add constraints to narrow results
4. Repeat until precise
```

### Pattern 2: Debug First
```
1. Write expected pattern
2. dump_syntax_tree on target code
3. Compare structures
4. Adjust pattern to match structure
```

### Pattern 3: Build Up Rules
```
1. Start with pattern-only rule
2. Add 'inside' with stopBy: end
3. Add 'has' constraints
4. Add 'not' exclusions
5. Test each iteration
```

## Troubleshooting Checklist

1. ✅ Metavariables are UPPERCASE
2. ✅ Using `$$$` for multiple arguments/elements
3. ✅ `stopBy: end` on all relational rules
4. ✅ Pattern is valid, parseable code
5. ✅ Correct language specified
6. ✅ Pattern matches the actual AST structure (use dump_syntax_tree)
""",
}


def get_docs(topic: str) -> str:
    """Return ast-grep documentation for topic. Use 'all' to get every section."""
    if topic == "all":
        sections = []
        for name, content in AST_GREP_DOCS.items():
            sections.append(
                f"{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}\n{name.upper()}\n{'=' * FormattingDefaults.WIDE_SECTION_WIDTH}\n\n{content}"
            )
        return "\n\n".join(sections)

    if topic in AST_GREP_DOCS:
        return AST_GREP_DOCS[topic]

    available = ", ".join(sorted(AST_GREP_DOCS.keys()))
    return f"Unknown topic: '{topic}'. Available topics: {available}, all"


def _load_pattern_examples() -> Dict[str, Dict[str, List[Dict[str, str]]]]:
    """Load pattern examples from the bundled JSON file."""
    data_path = Path(__file__).parent / "pattern_examples.json"
    with data_path.open(encoding="utf-8") as f:
        result: Dict[str, Dict[str, List[Dict[str, str]]]] = json.load(f)
        return result


PATTERN_EXAMPLES: Dict[str, Dict[str, List[Dict[str, str]]]] = _load_pattern_examples()

PATTERN_CATEGORIES = [
    "function",
    "class",
    "import",
    "variable",
    "control_flow",
    "error_handling",
    "async",
]

PATTERN_LANGUAGES = list(PATTERN_EXAMPLES.keys())


_LANGUAGE_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "golang": "go",
    "c++": "cpp",
}


def _resolve_language(language: str) -> str:
    return _LANGUAGE_ALIASES.get(language, language)


def _resolve_categories(
    lang_patterns: Dict[str, List[Dict[str, str]]],
    category: Optional[str],
) -> str | List[str]:
    """Return list of categories or an error string."""
    if category is None or category == "all":
        return list(lang_patterns.keys())
    category = category.lower()
    if category not in lang_patterns:
        available = ", ".join(sorted(lang_patterns.keys()))
        return f"Unknown category: '{category}'. Available: {available}, all"
    return [category]


def _format_pattern_entry(p: Dict[str, str]) -> List[str]:
    lines = [f"### {p['description']}", "```", p["pattern"], "```"]
    if "notes" in p:
        lines.append(f"*{p['notes']}*")
    lines.append("")
    return lines


def _build_pattern_output(
    language: str,
    lang_patterns: Dict[str, List[Dict[str, str]]],
    categories: List[str],
) -> str:
    lines: List[str] = [f"# {language.title()} Pattern Examples", ""]
    for cat in categories:
        patterns = lang_patterns.get(cat, [])
        if not patterns:
            continue
        lines.append(f"## {cat.replace('_', ' ').title()}")
        lines.append("")
        for p in patterns:
            lines.extend(_format_pattern_entry(p))
    return "\n".join(lines)


def get_pattern_examples(
    language: str,
    category: Optional[str] = None,
) -> str:
    """Return formatted pattern examples for a language and optional category filter."""
    language = _resolve_language(language.lower())

    if language not in PATTERN_EXAMPLES:
        available = ", ".join(sorted(PATTERN_EXAMPLES.keys()))
        return f"Unknown language: '{language}'. Available: {available}"

    lang_patterns = PATTERN_EXAMPLES[language]
    categories = _resolve_categories(lang_patterns, category)
    if isinstance(categories, str):
        return categories

    return _build_pattern_output(language, lang_patterns, categories)
