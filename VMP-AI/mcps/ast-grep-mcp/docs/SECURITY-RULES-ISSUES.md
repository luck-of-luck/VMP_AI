# Python Security Rules: False Positive Analysis & Fixes

**Status:** 3 of 7 root causes fixed (E1-E3). 4 remaining (E4-E7).

---

## Fixed Issues

### E1: Metavar names are cosmetic
**Status:** ✅ FIXED in commit 3849633

**Problem:** In ast-grep, `$PASSWORD` has zero semantic meaning — it's structurally identical to `$X`. Patterns like `print($PASSWORD)` matched any single-arg call including `print(x)`, `print("hello")`.

**Solution:** Added `constraints` with `regex` to credential-named metavariables:
```yaml
pattern: print($VAR)
constraints:
  - kind: identifier
    regex: "(?i).*(password|secret|api_key|token|credential|auth|key).*"
```

**Affected Rules:** 1 (hardcoded-auth-secret), 9 (secret-variable-used-after-assignment), 12 (secrets-in-logging)

---

### E2: Python comments are stripped from AST
**Status:** ✅ FIXED in commit 3849633

**Problem:** Python comments (`# ...`) have no AST node representation in tree-sitter. `not: inside: pattern: "# Example"` clauses were dead code, silently matching nothing.

**Solution:** Removed all dead comment pattern clauses. Rely on functional exclusions like `not: inside: def test_`.

**Affected Rules:** 1, 2, 4, 9, 12 (removed 5 dead patterns total)

---

### E3: Metavar scope isolation in relational rules
**Status:** ✅ FIXED in commit 3849633

**Problem:** In relational clauses (`follows`, `precedes`, `inside`), each is evaluated independently. `$VAR` in `precedes: open($VAR, ...)` is a new independent match, not the same `$VAR` from top-level `pattern: $VAR = mktemp()`.

**Solution:**
- **Rule 5 (flask-debug-mode):** Moved `if __name__ == '__main__'` from match targets to exclusions. Fixed syntax errors (trailing quotes).
- **Rule 6 (insecure-temp-file):** Removed broken `precedes` clause. Simplified to `inside: $VAR = mktemp()` which captures the actual risk.
- **Rule 9 (secret-variable-used-after-assignment):** Removed `precedes` with independent scope. Expanded patterns to directly show credential contexts.

---

## Remaining Issues

### E4: No `usedforsecurity` exclusion for hashlib
**Status:** ✅ FIXED in commit ef902aa

**Problem:** Python 3.9+ added `hashlib.md5(data, usedforsecurity=False)` for legitimate non-security uses (checksums, content deduplication, git-style addressing). The `insecure-cryptography` rule flags all `hashlib.md5()` and `hashlib.sha1()` calls, including safe ones.

**Rule:** insecure-cryptography (Rule 4)

**Fix Strategy:**
```yaml
- not:
    any:
      - pattern: hashlib.md5($$$ARGS, usedforsecurity=False)
      - pattern: hashlib.sha1($$$ARGS, usedforsecurity=False)
```

**Impact:** All content-dedup, cache-key, and checksum code using `md5()`/`sha1()` is currently flagged.

---

### E5: Syntax error in flask-debug-mode
**Status:** ✅ FIXED (line 240-241: removed trailing `"`)

**Note:** Was `pattern: app.run()"` with trailing quote — invalid syntax. Fixed in E3 solution.

---

### E6: `inside: if __name__ == '__main__'` is match target, not exclusion
**Status:** ✅ FIXED (moved to `not: inside:` in E3 solution)

**Note:** Rule 5 listed Flask debug mode in main block as "acceptable" but flagged it anyway. Fixed by moving to exclusions.

---

### E7: No semantic filtering via `constraints`
**Status:** ⚠️ PARTIALLY FIXED

**Problem:** No rules used `constraints` to restrict metavariable matches by `kind` or `regex`. Generic patterns like `$VAR = os.getenv("KEY")` matched any variable, and `$SECRET` in concatenation matched unrelated strings.

**Current Status:**
- ✅ E1 fixes added constraints to credentials in Rules 1, 9, 12
- ❌ Rules 2, 3, 7, 8, 10, 11 still lack semantic filtering
- ❌ Rules 2 & 3 (database credentials) need constraints on `$PASSWORD`, `$USER`, `$KEY`
- ❌ Rule 7 (search engines) needs constraints on `$USER`, `$PASSWORD`, `$KEY`
- ❌ Rule 8 (HTTP credentials) needs constraints on URL structure validation
- ❌ Rule 10 (unencrypted connections) needs schema validation for connection strings
- ❌ Rule 11 (string concatenation) needs constraints on variable names

**Fix Strategy:** Systematic addition of `constraints` blocks across remaining rules:
```yaml
constraints:
  - kind: identifier
    regex: "(?i).*(password|user|credential|api_key|secret|token|auth|key).*"
```

---

## Implementation Roadmap

| Issue | Status | Priority | Effort | Impact |
|-------|--------|----------|--------|--------|
| E1 - Metavar constraints | ✅ Fixed | P0 | 30m | High (credential-specific matching) |
| E2 - Dead comment patterns | ✅ Fixed | P0 | 20m | High (5 rules affected) |
| E3 - Relational scope | ✅ Fixed | P1 | 45m | Medium (3 rules, subtle behavior) |
| E4 - hashlib usedforsecurity | ✅ Fixed | P1 | 10m | Medium (content-dedup false positives) |
| E7 - Full semantic filtering | ❌ TODO | P2 | 60m | High (8 rules, broad false positive reduction) |

---

## Testing Recommendations

1. **Constraint validation:** Create Python test files with credential variables (`password`, `api_key`) and non-credential variables (`color`, `result`). Verify rules only flag credential contexts.

2. **hashlib edge cases:** Test `md5()` with and without `usedforsecurity=False`. Verify only unsafe calls are flagged.

3. **Scope isolation:** Test multi-statement files where `mktemp()` appears in one function and `open()` in another. Verify no cross-function false positives.

4. **Integration:** Run full suite on real codebases (Django, Flask, FastAPI) to measure false positive reduction.

---

## Files Modified

- `rules/python-security-high-priority.yaml`
  - Commit 3849633: E1-E3 fixes
    - E1: Added constraints to Rules 1, 9, 12
    - E2: Removed dead comment patterns from 5 rules
    - E3: Fixed Rules 5, 6, 9 relational logic
  - Commit ef902aa: E4 fix
    - E4: Added `usedforsecurity=False` exclusions to Rule 4

---

## References

- **ast-grep constraints:** https://ast-grep.github.io/guide/rule-config.html#constraints
- **Python `hashlib.md5` usedforsecurity:** https://docs.python.org/3/library/hashlib.html#hashlib.md5
- **Tree-sitter Python grammar:** Comments are not AST nodes, only part of trivia
