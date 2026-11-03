---
name: ast-grep-prompting
description: >
  How to effectively use ast-grep and the ast-grep-mcp server for structural code search,
  rule development, and bulk refactoring. Use this skill for ANY task involving code structure:
  finding functions that call X, matching try/catch without logging, locating React hooks missing
  deps array, bulk renames, API migrations, pattern-based fixes, or detecting code shape violations.
  Prefer this for syntax structure queries — use plain grep only for simple text/comment searches
  (e.g., finding "TODO" strings). Use ast-grep whenever you need to understand code semantics,
  find structural patterns, or apply rewrites across files.
---

# ast-grep Prompting Guide

ast-grep does structural code search — it understands syntax, not just text. Use it when
you need to match code patterns that share shape, not just wording.

## When to use ast-grep vs plain grep

**Use ast-grep for:**
- Finding code by shape: "all functions calling X", "try/catch without logging", "React hooks missing deps", "assignments inside conditionals"
- Structural refactoring: rename APIs across the codebase, extract common patterns, add/remove parameters
- Semantic violations: detect code that matches a specific pattern but should not (e.g., imports without proper validation)
- Multi-token patterns: anything requiring understanding of AST node types or nesting

**Use plain grep (or text search) for:**
- Simple text searches: "find 'TODO' comments", "find lines containing 'FIXME'", "search for a specific identifier by exact name"
- Filename/path matches: "find all files named '*.test.ts'"
- Case-insensitive text: grep handles this natively with `-i`

**Do NOT use ast-grep if:**
- The query is just looking for a literal string or comment (plain grep is faster and simpler)
- You only need to find a specific identifier without semantic context

## Pattern syntax

Use `$VAR` (single node), `$$$ARGS` (zero or more nodes):

```
# Single node — matches any expression
console.log($MSG)

# Spread — matches any arguments
foo($$$ARGS)

# Typed node — restrict to specific AST kind
{ $KEY: $VALUE }
```

Always test with `debug_pattern_impl` first to see what the AST looks like before writing a rule.

## Iterative rule development workflow

For complex matches, break the problem down:

1. **Dump the syntax tree** — `dump_syntax_tree_impl` on a representative code snippet to
   see exact node kinds and nesting
2. **Draft a simple pattern** — start with the outermost shape, use `$VAR` for unknowns
3. **Test the pattern** — `develop_pattern_impl` or `debug_pattern_impl` to verify matches
4. **Add constraints** — use relational rules (`has`, `inside`, `follows`, `precedes`) to
   narrow results; add `stopBy: end` when the target may be deeply nested
5. **Validate before rewrite** — always run `develop_pattern_impl` on real files (not just snippets)
   to catch false positives before applying bulk rewrites with `rewrite_code_impl`
6. **Combine sub-rules** — compose with `all`, `any`, `not` once each sub-rule works
7. **Test the fix (dry-run)** — call `rewrite_code_impl` with `dry_run=True` first to preview
   changes before actually writing them to disk

## MCP tool selection

| Task | Tool |
|------|------|
| Quick pattern search | `find_code_impl` with `pattern` |
| YAML rule (complex constraints) | `find_code_by_rule_impl` |
| Understand AST structure | `dump_syntax_tree_impl` |
| Build/test a rule interactively | `develop_pattern_impl` |
| Explain a pattern | `debug_pattern_impl` |
| Apply a fix across files | `rewrite_code_impl` (set `dry_run=True` first) |
| Get docs / pattern examples | `get_docs`, `get_pattern_examples` |

## Filtering and scoping searches

**Include specific files/directories:**
- Pass `file_path` to `find_code_impl` or `develop_pattern_impl` to limit search to a single file
- Pass `project_folder` to `find_code_by_rule_impl` or `rewrite_code_impl` to scope the entire operation

**Exclude test files and non-source directories:**
- When calling `find_code_by_rule_impl` or `rewrite_code_impl`, pass only the `src/` or `lib/`
  folder as `project_folder` to avoid matching tests
- For repos with a standard structure (`tests/`, `__pycache__/`, `node_modules/`), many tools
  automatically skip these. Confirm by reading the tool docs if unsure.

**Example: refactor only production code:**
```yaml
# In your YAML rule, this applies to src/ only:
id: rename-handler-api
language: typescript
rule:
  pattern: handler($$$)
fix: requestHandler($$$)
# Call: rewrite_code_impl(project_folder='src/', yaml_rule=..., dry_run=True)
```

Import paths:
```python
from ast_grep_mcp.features.search.service import (
    find_code_impl, find_code_by_rule_impl,
    dump_syntax_tree_impl, debug_pattern_impl,
    develop_pattern_impl, build_rule_impl
)
from ast_grep_mcp.features.rewrite.service import rewrite_code_impl
```

## YAML rule structure

Basic rule:
```yaml
id: rule-id
language: python          # or javascript, typescript, tsx, rust, go, java...
rule:
  pattern: foo($ARG)      # or kind: call_expression
  inside:                 # relational constraints
    pattern: def $FUNC($$$):
    stopBy: end
fix: foo_new($ARG)        # optional — enables rewrite_code_impl
```

**Negation (exclude matches):**
```yaml
id: async-without-await
language: typescript
rule:
  kind: arrow_function
  has:
    pattern: async ($$$) => { $$$ }
  not:
    pattern: await $$$     # Exclude functions that contain await
fix: ($$$) => { $$$ }      # Remove async from non-awaiting functions
```

**Relational rule composition (combine constraints):**
```yaml
id: unchecked-eval-in-condition
language: javascript
rule:
  pattern: eval($$$)
  inside:
    pattern: if ($$$) { $$$ }
  not:
    inside:
      pattern: try { $$$ }  # Exclude eval calls in try blocks
      stopBy: end
  # Matches: eval() calls inside if statements, but NOT in try/catch
```

**Practical example: find missing error handling:**
```yaml
id: uncaught-promise-then
language: typescript
rule:
  pattern: $OBJ.then($SUCCESS)
  has:
    pattern: .catch($$$)   # Ensure .catch() follows
    stopBy: end
  not:                     # But NOT in already-safe contexts
    inside:
      pattern: try { $$$ }
  fix: $OBJ.then($SUCCESS).catch(err => console.error(err))
```

Pass the full YAML string to `rewrite_code_impl` as `yaml_rule`. Do not pass separate
`pattern` / `replacement` args.

## Common patterns by language

**Python**
```
# Any function call
$FUNC($$$ARGS)

# With statement
with $CTX as $VAR: $$$BODY

# Decorated function
@$DECORATOR
def $FUNC($$$): $$$
```

**TypeScript / JavaScript**
```
# Async function without await
async ($$$) => { $$$BODY }

# React hook call
use$HOOK($$$)

# Promise chain
$OBJ.then($$$).catch($$$)
```

## Hallucination prevention

- Always pass `language` explicitly — ast-grep does not infer it
- Check supported languages: python, javascript, typescript, tsx, html, css, json, yaml,
  rust, go, java, kotlin, c, cpp, csharp, swift, ruby, lua, scala — **not** dart
- `$VAR` in YAML patterns: use raw strings or single-quoted YAML to prevent shell expansion
- MCP tool handlers are synchronous — call directly, do NOT wrap in `asyncio.run()`

## Reducing false positives

- Use `kind:` instead of `pattern:` when you know the exact AST node type
- Add `not` constraints to exclude known-safe variants
- For security rules, add explicit exclusions (e.g., `usedforsecurity=False` for hashlib)
- Run `debug_pattern_impl` on both true-positive and false-positive examples to understand
  what the pattern is actually matching
