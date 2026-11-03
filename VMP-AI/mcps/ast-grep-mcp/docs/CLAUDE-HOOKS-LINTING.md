# Linting Strategy for Claude Hooks

Based on session findings from 2026-04-20 regarding `prefer-const` handling.

## Problem

- 703 `prefer-const` violations in `~/.claude`
- Blanket AST-grep rewrites created 79 TypeScript errors
- Pattern-based fixes cannot detect semantic reassignment

## Solution: ESLint + Type Safety

### Quick Setup (5 minutes)

```bash
cd ~/.claude/hooks

# 1. Install ESLint with TypeScript support
npm install --save-dev eslint @typescript-eslint/eslint-plugin @typescript-eslint/parser

# 2. Copy config from ast-grep-mcp template
cp /path/to/ast-grep-mcp/templates/eslintrc-typescript.json .eslintrc.json

# 3. Add lint commands to package.json
npm set-script lint "eslint src --ext .ts"
npm set-script lint:fix "eslint src --ext .ts --fix"

# 4. Run linter
npm run lint
npm run lint:fix  # Auto-fixes safe violations
```

### What ESLint's `prefer-const` Does Better

| Scenario | ast-grep Pattern | ESLint prefer-const |
|----------|------------------|---------------------|
| Loop counter `let i = 0; i++` | ❌ Flags incorrectly | ✅ Ignores (knows it's reassigned) |
| Conditional reassign `let x = 'A'; if(...) x='B'` | ❌ Flags incorrectly | ✅ Detects scope, rejects |
| Accumulator `let sum = 0; sum += val` | ❌ Flags incorrectly | ✅ Detects `+=`, rejects |
| Safe const `let config = {...}` | ✅ Flags correctly | ✅ Flags and auto-fixes |

### Autofix Workflow

1. **Run locally first (with review):**
   ```bash
   npm run lint:fix
   git diff  # Review changes
   git add . && git commit
   ```

2. **Add to pre-commit hook:**
   ```bash
   # .git/hooks/pre-commit
   npm run lint:fix || exit 1
   ```

3. **CI integration:**
   ```yaml
   # .github/workflows/lint.yml
   - name: Lint
     run: npm run lint
   ```

### Common ESLint Errors & Fixes

| Error | Meaning | Fix |
|-------|---------|-----|
| `prefer-const` | Can use `const` | Run `npm run lint:fix` |
| `no-explicit-any` | Avoid `any` type | Add explicit type or suppress with `// @ts-ignore` |
| `no-unused-vars` | Dead code | Remove or rename with `_` prefix |

### Key Config Options

In `.eslintrc.json`:

```json
{
  "rules": {
    "prefer-const": [
      "warn",
      {
        "destructuring": "any",          // Allow destructuring
        "ignoreReadBeforeAssign": true,  // Skip read-before-assign
        "ignoreLoopCondition": true      // Ignore loop conditions
      }
    ]
  }
}
```

---

## Alternative: Strict TypeScript

If ESLint feels like overkill, use TypeScript's strict mode:

```json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitReturns": true,
    "noImplicitOverride": true,
    "noUncheckedIndexedAccess": true
  }
}
```

Then rely on IDE hints (`Ctrl+.` in VS Code) for refactoring.

---

## Why NOT Blanket Rewrites

Lessons learned:

1. **Pattern matching != semantic analysis**
   - AST-grep sees `let $VAR = $INIT` but not scope/reassignment
   - ESLint's scope analysis prevents false positives

2. **Autofix without validation breaks code**
   - 79 TypeScript errors from one rewrite attempt
   - Always validate after auto-fixes

3. **Selective fixes are safer**
   - Run `eslint --fix` locally with review
   - Commit incrementally
   - Catch errors before pushing

---

## Summary

✅ **Do:** Use ESLint for intelligent `prefer-const` detection  
❌ **Don't:** Use pattern-based rewrites for semantic rules  
✅ **Do:** Review auto-fixes before committing  
❌ **Don't:** Rely on blanket transforms without validation
