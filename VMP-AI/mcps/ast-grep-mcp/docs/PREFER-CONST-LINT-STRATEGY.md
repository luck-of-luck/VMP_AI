# Prefer-Const Lint Rule: Session Findings & Strategy

## Session Summary (2026-04-20)

**Objective:** Fix 703 `prefer-const` violations in `~/.claude` using ast-grep rewrite tool.

**Result:** ❌ Failed — created 79 TypeScript compilation errors.

---

## Root Cause Analysis

### What Went Wrong

The blanket rewrite pattern `let $VAR = $INIT; -> const $VAR = $INIT;` was too aggressive and flagged variables that ARE reassigned:

**Examples of False Positives:**

| Variable | Init | Reassignment | Error |
|----------|------|--------------|-------|
| `bytes` | `const bytes = key.length + KEY_OVERHEAD_BYTES;` | `bytes += ...` (3 times) | TS2588 |
| `i` | `const i = 0;` | `i++` (loop increment) | TS2588 |
| `color` | `const color = 'OK';` | `color = 'ERROR'` (conditional) | TS2588 |
| `output` | `const output = '';` | `output += ...` (13 times) | TS2588 |
| `input` | `const input = '';` | `input = userInput` | TS2588 |

### Why Pattern-Based Rewrites Fail

1. **Loop Counters:** Variables initialized with `let i = 0` always get reassigned (`i++`/`i--`). Excluding `let $VAR = 0` reduces false positives from 698 → 247 but still misses cases like `let count = length`.

2. **Accumulator Variables:** Code like `let sum = 0; sum += val;` appears as single initialization but is immediately mutated.

3. **Conditional Reassignment:** Variables conditionally reassigned later (e.g., `let x = 'A'; if (...) x = 'B';`) are flagged but shouldn't be `const`.

4. **Function Scope:** Variables reassigned in nested scopes (callbacks, loops inside function bodies) are harder to detect with simple patterns.

---

## Better Approach: Semantic-Aware Linting

### Core Principle

**Only flag `let` → `const` when the variable is provably never reassigned.**

This requires AST-based analysis, not pattern matching.

### Implementation Options

#### Option 1: ESLint Rule (Recommended for Development)

Use `eslint-plugin-prefer-const` with proper configuration:

```json
{
  "plugins": ["prefer-const"],
  "rules": {
    "prefer-const": [
      "warn",
      {
        "destructuring": "any",
        "ignoreReadBeforeAssign": true,
        "ignoreLoopCondition": true
      }
    ]
  }
}
```

**Advantages:**
- Industry-standard, well-tested rule
- Real AST analysis (not pattern-based)
- IDE integration (auto-fix on save)
- Respects edge cases (loop conditions, destructuring)

**Setup for `~/.claude/hooks`:**
```bash
npm install --save-dev eslint @typescript-eslint/eslint-plugin eslint-plugin-prefer-const
```

#### Option 2: TypeScript Strict Compiler Option

Enable `noImplicitReassignment` (when available in future TS versions) or use strict analysis mode:

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "noImplicitThis": true,
    "strictNullChecks": true,
    "strictFunctionTypes": true,
    "strictBindCallApply": true,
    "strictPropertyInitialization": true,
    "noImplicitReturns": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true
  }
}
```

#### Option 3: Custom ast-grep Rule with Reassignment Detection

Create an ast-grep rule that detects reassignment in scope:

```yaml
id: prefer-const-safe-v2
language: typescript
rule:
  pattern: let $VAR = $INIT;
  inside:
    pattern: |
      {
        let $VAR = $INIT;
        $BEFORE
        $VAR = $NEW;
        $AFTER
      }
  not: true  # Only match if NOT inside reassignment pattern

fix: const $VAR = $INIT;
```

**Limitations:** Can't detect all reassignment patterns (nested scopes, callbacks).

---

## Recommended Strategy

### For `~/.claude/hooks`

1. **Do NOT use blanket rewrites** — they break code.

2. **Enable ESLint** with `prefer-const` rule:
   ```bash
   npm install --save-dev eslint @typescript-eslint/eslint-plugin
   # Create .eslintrc.json
   ```

3. **Use IDE auto-fix** (`Ctrl+.` in VS Code) to fix one-by-one with human review.

4. **Automate in CI** with `npm run lint -- --fix` before merge.

### For ast-grep Tool

Update `enforce_standards` rule to flag `prefer-const` violations but **DO NOT** provide automatic fix:

```yaml
id: prefer-const-recommend
language: typescript
severity: info
message: |
  Variable '{{ $VAR }}' is declared with 'let' but never reassigned.
  Consider using 'const' for immutability. Review manually before changing.
rule:
  pattern: let $VAR = $INIT;
# Intentionally omit 'fix' field to require manual review
```

---

## Session Deliverables

### Files Modified

- ✅ Reverted breaking commit (`f9a7756b`)
- ❌ Removed auto-committed broken changes
- ✅ Fixed 79 TypeScript errors

### Measurements

| Metric | Before | After | Status |
|--------|--------|-------|--------|
| prefer-const violations | 703 | 703 (unchanged) | ⚠️ Still exist |
| TypeScript errors | 0 | 0 ✅ | Fixed |
| Files modified | 104 | 0 (reverted) | Safe |
| Commits | 1 breaking | 1 revert | Clean |

---

## Takeaways

1. **Pattern-based rewrites are unsafe** for semantic rules like `prefer-const`.
2. **Blanket changes need compiler/linter validation** before commit.
3. **Semantic analysis (ESLint/TypeScript) > Pattern matching (ast-grep)** for this rule.
4. **Manual review is essential** for code transformations that affect semantics.

---

## Next Steps

If fixing `prefer-const` is a priority:

1. Set up ESLint in `~/.claude/hooks` with `prefer-const` rule
2. Run `eslint --fix` selectively with human review
3. Add linting to pre-commit hooks
4. Document findings in project CLAUDE.md

**Not recommended:** Using ast-grep or find-replace tools for semantic transformations without post-validation.
