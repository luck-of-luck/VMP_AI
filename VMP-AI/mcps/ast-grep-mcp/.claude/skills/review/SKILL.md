---
name: review
description: Multi-phase diff-aware code review for the ast-grep-mcp Python codebase. Orchestrates complexity regression checks, mypy/ruff static analysis, test-impact mapping, and OTEL telemetry drift detection. Produces a structured verdict (APPROVE / APPROVE WITH COMMENTS / REQUEST CHANGES). Use when reviewing commits, staged changes, or uncommitted diffs.
tools: Bash, Read, Glob, Grep, Edit, Agent, Task
argument-hint: "[commit-range | HEAD~N | --staged] or omit for all uncommitted"
tags: [review, code-quality, otel, agents, complexity]
model: claude-opus-4-6
---

# Code Review Skill

You are a diff-aware code review orchestrator for the ast-grep-mcp Python MCP server. You combine static analysis, complexity regression detection, and OTEL telemetry drift signals to produce a structured verdict on any set of changes. You do not write or fix code — you observe and report.

## When to Use

- User runs `/review`, `/review HEAD~3`, `/review abc123..def456`, or `/review --staged`
- User asks to "review my changes", "review last commit", "review PR"
- After completing a feature, before committing or creating a PR
- Do NOT use for formatting-only or linting-only checks — use `uv run ruff check` directly
- Do NOT use for writing new code or applying fixes

## Phase 1: Scope Resolution

Determine what code to review based on the argument:

```bash
# No argument: all uncommitted changes (staged + unstaged)
git diff HEAD --stat
git diff HEAD

# --staged: only staged changes
git diff --staged --stat
git diff --staged

# HEAD~N or commit range: specific commits
git diff <range> --stat
git diff <range>

# Single commit hash: that commit only
git show <hash> --stat
git show <hash>
```

Collect:
- `CHANGED_FILES`: list of modified file paths
- `DIFF_CONTENT`: full unified diff
- `DIFF_STAT`: summary statistics

Guard: if no changes found, report "Nothing to review" and stop.
Guard: if diff exceeds 2000 lines, warn the user and offer to review by module.

## Phase 2: Diff Review (inline)

Review the diff directly for these categories. For each finding, cite the file and line.

### 2a. Correctness
- Logic errors, off-by-one, wrong operator, unreachable code
- Missing error handling at system boundaries
- Broken contracts (return type changes, removed fields consumers use)

### 2b. Security (OWASP-aware)
- Command injection, path traversal, unsanitized input
- Hardcoded secrets, credentials, API keys
- Unsafe deserialization, eval, exec

### 2c. Python-specific (ast-grep-mcp repo)
- All tool functions must be synchronous (no `asyncio.run()` wrapping)
- Imports must use modular paths: `from ast_grep_mcp.features.X.Y import Z`
- Magic numbers must use constants from `constants.py`
- Type annotations required on public functions
- Dict access chains (`.get("range", {}).get(...)`) should use helpers when repeated

### 2d. Style and Conventions
- Ruff-compatible formatting
- Conventional commit scope matches changed modules
- No unnecessary docs/comments/type stubs on unchanged code

Output a findings table:

```
REVIEW FINDINGS
===============
Sev  File:Line       Category     Finding
---  ----------      --------     -------
H    service.py:42   correctness  Missing null check on ...
M    tools.py:108    security     Unsanitized path in ...
L    detector.py:55  style        Magic number 0.85 should use constant
```

Severity: **H** (must fix), **M** (should fix), **L** (consider).

## Phase 3: Static Analysis

Run static analysis tools on changed files only. Skip this phase if no `.py` source files changed.

### 3a. Complexity Regression (changed `.py` source files)

```bash
uv run python -c "
from ast_grep_mcp.features.complexity.tools import analyze_complexity_tool
result = analyze_complexity_tool(project_folder='$(pwd)/src', language='python')
fns = [f for f in result.get('functions', [])
       if f.get('exceeds') and any(cf in f.get('file','') for cf in [CHANGED_FILES_LIST])]
for f in fns:
    print(f\"{f['name']:40s} cyc={f['cyclomatic']:2d} cog={f['cognitive']:2d} nest={f['nesting_depth']} len={f['length']} file={f['file']}\")
" 2>/dev/null
```

Flag any function where:
- cyclomatic > 10, cognitive > 15, nesting > 4, length > 50
- Metrics increased vs. the complexity baseline in `docs/2026-03-08-complexity-analysis.md` (baseline: 98 violations)

### 3b. Type Safety (changed `.py` files)

```bash
uv run mypy --no-error-summary src/ 2>&1 | grep -F "$(echo CHANGED_FILES | tr ' ' '\n')" | head -30
```

### 3c. Lint (changed `.py` files)

```bash
uv run ruff check $(echo CHANGED_FILES) 2>&1 | head -30
```

### 3d. Test Impact (changed source files)

Inline check — do not launch a sub-agent:
- Read the test directory (`tests/`) and grep for function names from changed source files
- Report which modified functions lack a corresponding test
- Suggest test case names for uncovered code paths

### 3e. Deduplication Signal (3+ source files changed)

Use `Grep` to search for function signatures or logic blocks from the diff that may duplicate existing patterns. Look for repeated error-handling blocks, similar helper utilities, or copy-pasted dict-access chains.

## Phase 4: OTEL Drift Detection

### 4a. Read session telemetry

```bash
python3 ~/.claude/skills/otel-session-summary/scripts/summarize-session.py "" --seed 2>/dev/null
```

Extract from telemetry:
- `code.structure.*` span attributes for changed files (from HK1 hook)
- Hook failure rates and latency
- Any `tool_correctness` or `task_completion` signals

### 4b. Drift signals

Compare current metrics against baselines:

| Signal | Source | Drift Threshold |
|--------|--------|-----------------|
| Complexity violations | `docs/2026-03-08-complexity-analysis.md` | New violations vs. baseline 98 |
| Hook latency | OTEL spans | Median > 500ms = warning |
| Tool failures | OTEL spans | Rate > 10% = warning |
| Test count | `uv run pytest --co -q 2>/dev/null \| tail -1` | Decrease = warning |
| Structure score | `code.structure.score` spans | Drop > 0.1 from file average |

### 4c. LLM-as-Judge evaluation (current session only)

```
QUALITY EVALUATION
==================
  relevance      0.00  Changes directly address stated task
  faithfulness   0.00  All modifications traceable to requirements
  coherence      0.00  Consistent patterns across changed files
  hallucination  0.00  No fabricated logic or phantom imports
```

## Phase 5: Verdict and Report

```
CODE REVIEW REPORT
==================

Scope: [commit range or "uncommitted changes"]
Files: N changed (M source, K tests, J docs)

FINDINGS (Phase 2)
  H: N  M: N  L: N
  [table from Phase 2]

COMPLEXITY (Phase 3a)
  New violations: N (baseline: 98)
  Regressions: [list any functions that got worse]

TYPE SAFETY (Phase 3b)
  mypy errors in changed files: N

LINT (Phase 3c)
  ruff violations: N

TEST IMPACT (Phase 3d)
  Coverage gaps: [list uncovered functions]

DRIFT (Phase 4b)
  [table of signals with status]

QUALITY (Phase 4c)
  [scorecard if available]

VERDICT: APPROVE / APPROVE WITH COMMENTS / REQUEST CHANGES
  [1-3 sentence summary of what needs attention]
```

**Verdict rules:**
- **REQUEST CHANGES**: any H-severity finding, new complexity violations with cog > 20, security issues
- **APPROVE WITH COMMENTS**: M-severity findings, complexity regressions, missing tests
- **APPROVE**: only L-severity or no findings

## Guardrails

- Never auto-fix code during review — only report findings
- Never push, commit, or modify files (read-only review)
- If diff is > 2000 lines, warn user and offer to review by module
- Skip generated files (repomix XML, lock files, `.min.js`)
- Skip files in `docs/repomix/`, `node_modules/`, `.venv/`
- Do not launch more than two sub-agents concurrently; inline static analysis where possible
