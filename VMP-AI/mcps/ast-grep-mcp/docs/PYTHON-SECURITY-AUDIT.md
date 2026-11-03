# Python Security Rules Audit & Implementation Status

**Date:** 2026-04-20  
**Scope:** Audit of Python security rules against ast-grep-essentials GitHub repo  
**Status:** 12/60 rules implemented (20% coverage)

---

## Completed Work ✅

### Rules Implemented (12/48 high-priority)
1. ✅ `hardcoded-auth-secret` — JWT, OpenAI, Requests
2. ✅ `database-hardcoded-credential` — PostgreSQL, MySQL, MongoDB, Redis, CouchBase
3. ✅ `database-empty-credential` — Empty password detection
4. ✅ `insecure-cryptography` — RC4, DES, MD5, SHA1
5. ✅ `flask-debug-mode` — Flask debug=True detection
6. ✅ `insecure-temp-file` — mktemp() race conditions
7. ✅ `search-engine-hardcoded-credentials` — Elasticsearch, OpenSearch
8. ✅ `http-embedded-credentials` — Credentials in URLs
9. ✅ `secret-variable-used-after-assignment` — Variable tracking (precedes)
10. ✅ `unencrypted-db-connection` — http:// in connection strings
11. ✅ `credentials-string-concatenation` — String concat detection
12. ✅ `secrets-in-logging` — Secrets in log calls

### Pattern Examples (30+ added to JSON)
- ✅ Hardcoded credentials (6 patterns)
- ✅ Empty passwords (4 patterns)
- ✅ Weak cryptography (3 patterns)
- ✅ Flask debug mode (2 patterns)
- ✅ Insecure temp files (2 patterns)
- ✅ Search engines (2 patterns)
- ✅ HTTP credentials (1 pattern)
- ✅ Variable assignment (1 pattern)
- ✅ String concatenation (1 pattern)
- ✅ Logging leaks (1 pattern)

### Relational Pattern Coverage
- ✅ `follows` — 10 rules with import verification
- ✅ `precedes` — 1 rule with variable usage tracking
- ✅ `inside` — 12 rules with context detection
- ✅ `not` — 12 rules with false positive exclusion
- ✅ `all` composition — 12 rules
- ✅ `any` composition — 12 rules

---

## Un-Addressed Issues

### Priority 1: Testing & Validation

#### SR-01: Unit Tests for Security Detector
**Status:** ❌ Not started  
**Effort:** 2-4 hours  
**Impact:** High — no verification that detection logic works  
**Required for:** Production readiness

**Scope:**
- Add `tests/unit/test_security_detection.py`
- Test each of 12 rules on vulnerable code samples
- Verify false positives/negatives
- Test edge cases (commented imports, test functions, safe patterns)

**Files needed:**
```
tests/unit/test_security_detection.py
tests/fixtures/vulnerable_auth.py
tests/fixtures/vulnerable_db.py
tests/fixtures/vulnerable_crypto.py
```

---

#### SR-02: Integration Tests for YAML Rules
**Status:** ❌ Not started  
**Effort:** 3-5 hours  
**Impact:** High — rules never tested against real AST

**Scope:**
- Validate `rules/python-security-high-priority.yaml` via `find_code_by_rule_impl()`
- Test against vulnerable code samples
- Verify relational patterns work (follows, precedes, inside)
- Test anti-patterns (excluded patterns don't match)

**Test coverage:**
- Hardcoded credentials (5 databases + 3 auth methods)
- Empty passwords (4 databases)
- Weak crypto (4 algorithm types)
- Flask debug (2 variants)
- mktemp() (2 import styles)
- Elasticsearch (2 auth methods)
- HTTP credentials (2 protocols)
- Variable tracking (precedes pattern)
- String concatenation (3 types)
- Logging leaks (5 logger methods)

---

### Priority 2: Documentation

#### SR-03: Python Security Rules Guide
**Status:** ❌ Not started  
**Effort:** 1-2 hours  
**Impact:** Medium — operators need to understand rules

**Required sections:**
1. Rule overview (12 rules × CWE mapping)
2. Coverage analysis (what each rule detects)
3. Known limitations
   - False positive scenarios
   - Edge cases not covered
   - Why certain patterns were excluded
4. Example vulnerable code per rule
5. Remediation guidance
6. Performance implications
7. Integration with quality gates

**Output:** `docs/PYTHON-SECURITY-RULES.md`

---

#### SR-04: Relational Pattern Documentation
**Status:** ❌ Not started  
**Effort:** 1 hour  
**Impact:** Low — reference material

**Scope:**
- How `follows` validates imports
- How `precedes` tracks variable usage
- How `inside` provides context
- How `not` excludes false positives
- Pattern composition best practices

**Output:** Section in `docs/PATTERNS.md`

---

### Priority 3: Rule Expansion

#### SR-05: Medium-Priority Rules (36 additional)
**Status:** ❌ Not started  
**Effort:** 8-12 hours  
**Impact:** Medium — extends coverage

**Rules to implement:**
- Hash/LDAP empty passwords (2 rules)
- LDAP hardcoded secrets (1 rule)
- Cassandra hardcoded secrets (1 rule)
- Cassandra empty password (1 rule)
- CouchDB hardcoded secrets (1 rule)
- CouchDB empty password (1 rule)
- WebreREPL empty password (1 rule)
- JWT + pyjwt hardcoded (1 rule)
- Django/Flask HashIDs secret leaks (2 rules)
- App.run() with bad host (1 rule)
- (27 more from GitHub essentials repo)

**Effort breakdown:**
- Database variants: 6-8 hours (consolidate into 2-3 rules)
- API/Auth variants: 2-3 hours
- Framework-specific: 1-2 hours

---

#### SR-06: Constraint-Based Filtering
**Status:** ❌ Not started  
**Effort:** 3-4 hours  
**Impact:** High — reduces false positives

**Catalog feature not yet used:** Constraints on metavariables

**Example enhancement:**
```yaml
# Current: detects any password= with string
pattern: psycopg2.connect(..., password="$PASSWORD", ...)

# Enhanced: only flags if $PASSWORD looks like hardcoded string
constraints:
  PASSWORD:
    kind: string_literal
    not:
      - pattern: "[0-9a-f]{32}"  # looks like hash
      - pattern: "****"          # placeholder
```

**Rules to enhance:** All 12 (especially hardcoded credentials)

---

### Priority 4: Additional Coverage

#### SR-07: Additional CWE Coverage
**Status:** ❌ Not started  
**Effort:** 4-6 hours  
**Impact:** Medium — extends scope

**CWEs not yet covered:**
- CWE-611: XML External Entity (XXE) injection
- CWE-330: Use of Insufficiently Random Values
- CWE-434: Unrestricted Upload of File with Dangerous Type
- CWE-502: Deserialization of Untrusted Data
- CWE-295: Improper Certificate Validation (partial)
- CWE-347: Improper Verification of Cryptographic Signature

**New rules needed:** 6-8

---

#### SR-08: Pattern Examples Expansion
**Status:** ❌ Not started  
**Effort:** 1-2 hours  
**Impact:** Low — reference material

**Current:** 30 patterns  
**Target:** 50+ patterns (including SR-07 CWEs)

**Output:** Expanded `pattern_examples.json[python][security]`

---

### Priority 5: Integration & Deployment

#### SR-09: Register Rules with MCP Server
**Status:** ❌ Not started  
**Effort:** 1 hour  
**Impact:** High — rules not accessible via MCP

**Scope:**
- Add `python-security-high-priority` to tool registry
- Update `quality/tools.py` to reference YAML rules
- Add to `docs/BACKLOG.md` as implemented
- Update tool list in README

**Files to modify:**
- `src/ast_grep_mcp/features/quality/tools.py`
- `src/ast_grep_mcp/server/registry.py`
- `README.md`
- `docs/CONFIGURATION.md`

---

#### SR-10: Rule Performance Benchmarking
**Status:** ❌ Not started  
**Effort:** 2 hours  
**Impact:** Medium — understand performance impact

**Scope:**
- Benchmark 12 rules on codebase (1K+ Python files)
- Identify slow patterns
- Optimize if needed
- Document performance characteristics

---

### Priority 6: Future Enhancements

#### SR-11: Auto-Fix Generation
**Status:** ❌ Not started  
**Effort:** 4-8 hours  
**Impact:** Low — currently detection-only

**Scope:**
- Add `fix` fields to YAML rules
- Example: `fix: openai.api_key = os.getenv("OPENAI_API_KEY")`
- Implement via `rewrite_code_impl()`

**Effort:** Significant for 12 rules

---

#### SR-12: Configuration Options
**Status:** ❌ Not started  
**Effort:** 1-2 hours  
**Impact:** Low — operators control strictness

**Options:**
- `--ignore-test-files` (default: true)
- `--ignore-commented-imports` (default: true)
- `--ignore-development-code` (default: false)
- `--severity-threshold` (warning/error)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Rules not tested before release | High | High | Implement SR-01, SR-02 |
| False positives in production | Medium | High | Add constraint filtering (SR-06) |
| Operators misunderstand rules | Medium | Medium | Add documentation (SR-03) |
| Missing coverage for 75% of patterns | High | Low | Phase 2: implement SR-05 |
| Performance degradation | Low | Medium | Benchmark (SR-10) |

---

## Recommended Implementation Order

**Phase 1 (This week) — Production Readiness:**
1. SR-01: Unit tests
2. SR-02: Integration tests  
3. SR-03: Documentation
4. SR-09: Register with MCP

**Phase 2 (Next week) — Extended Coverage:**
1. SR-05: Medium-priority rules (36 additional)
2. SR-06: Constraint-based filtering
3. SR-04: Pattern documentation

**Phase 3 (Sprint) — Polish & Optimize:**
1. SR-10: Performance benchmarking
2. SR-07: Additional CWE coverage
3. SR-11: Auto-fix generation

---

## Files Status

| File | Status | Changes Needed |
|------|--------|-----------------|
| `rules/python-security-high-priority.yaml` | ✅ Complete | None (production-ready) |
| `src/ast_grep_mcp/features/search/pattern_examples.json` | ✅ Updated | Expand for SR-07 |
| `tests/unit/test_security_detection.py` | ❌ Missing | Create (SR-01) |
| `tests/integration/test_python_security_rules.py` | ❌ Missing | Create (SR-02) |
| `docs/PYTHON-SECURITY-RULES.md` | ❌ Missing | Create (SR-03) |
| `src/ast_grep_mcp/features/quality/tools.py` | 🟡 Partial | Register rules (SR-09) |

---

## Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Rules implemented | 12 | 48 (high-priority) |
| Coverage %| 25% | 100% (high-priority) |
| Relational patterns/rule | 9.6 | 5+ (achieved) |
| Test coverage | 0% | 80%+ |
| Documentation coverage | 0% | 100% |
| False positive rate | Unknown | <5% |

---

**Last Updated:** 2026-04-20  
**Next Review:** After SR-01, SR-02 completion
