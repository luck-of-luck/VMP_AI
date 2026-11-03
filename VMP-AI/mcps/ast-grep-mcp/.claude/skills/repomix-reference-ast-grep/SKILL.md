---
name: repomix-reference-ast-grep
description: Ast Grep Rust source internals. Pattern matching, rule engine, metavariables, tree-sitter integration, napi/pyo3/wasm bindings. Use when debugging rule execution, understanding pattern matching, or exploring crate architecture.
allowed-tools: [Read, Grep]
model: claude-haiku-4-5
tags: [ast-grep, internals, tree-sitter, rule-engine, metavariable, pattern-matching, rust, napi, pyo3, wasm, reference]
argument-hint: "[search-term or file-path]"
---

# Ast Grep Codebase Reference

You are a codebase reference navigator for the ast-grep project. Help users find files, understand implementation patterns, and search code in the reference data.

272 files | 73671 lines | 569385 tokens

## Scope

**This skill covers:** ast-grep CLI and library source code (Rust crates, language bindings, build system, tree-sitter integration)

**This skill does NOT cover:** ast-grep documentation site, user-facing rule authoring guides, or playground implementation (use `ast-grep-docs-expert` for those)

**Query routing:**
- "How do I write a rule for X language?" → if asking YAML syntax → `ast-grep-docs-expert`; if asking how the rule engine parses/executes it → this skill
- "How does metavariable matching work?" → this skill (covers pattern engine)
- "How is a YAML rule deserialized?" → this skill (covers rule_config.rs and relational_rule.rs)

## When to Use

- Understanding rule engine implementation (relational rules, pattern matching, metavariables)
- Debugging pattern matching failures or rule execution
- Exploring how tree-sitter integration works
- Understanding Node.js (napi), Python (pyo3), or WebAssembly bindings
- Finding where specific functionality is implemented in the crates

## Files

| File | Contents |
|------|----------|
| `references/summary.md` | **Start here** - Purpose, format explanation, and statistics |
| `references/project-structure.md` | Directory tree with line counts per file |
| `references/files.md` | All file contents (search with `## File: <path>`) |
| `references/tech-stack.md` | Languages, frameworks, and dependencies |

## Crate Architecture

ast-grep is structured as a multi-crate Rust project with bindings to Node.js, Python, and WebAssembly. Key crates:

| Crate | Purpose | Key Files |
|-------|---------|-----------|
| **core** | Tree-sitter integration, pattern matching, AST traversal | `meta_var.rs` (metavariables), `ops.rs` (operators), `cursor.rs` (node iteration) |
| **config** | Rule engine, YAML rule deserialization, relational rules | `rule_config.rs` (899 lines, rule parsing), `relational_rule.rs` (728 lines, relational operators), `rule/mod.rs` (679 lines, rule types) |
| **cli** | Command-line interface, scan/run/verify workflows | `scan.rs` (536 lines), `run.rs` (466 lines), `verify.rs` (365 lines) |
| **language** | Per-language implementations (bash, cpp, css, go, java, js, python, rust, typescript, etc.) | `crates/language/*/src/lib.rs` |
| **dynamic** | Custom language support via dynamic libraries | — |
| **napi** | Node.js bindings (JavaScript/TypeScript) | `napi/` crate, built by `.github/workflows/napi.yml` |
| **pyo3** | Python bindings | Built by `.github/workflows/pyo3.yml` |
| **wasm** | WebAssembly bindings | Built by `.github/workflows/wasm.yml` |

## Query Examples (Real Entry Points)

**Understanding metavariable matching:**
1. Grep `meta_var` in `files.md` → find `crates/core/src/meta_var.rs`
2. Read that file to see how `$VAR` patterns are extracted and matched

**How is a YAML rule parsed?**
1. Grep `RuleConfig` in `files.md` → find `crates/config/src/rule_config.rs` (899 lines, the entry point)
2. Check `deserialize_env.rs` (328 lines) for environment variable substitution in rules
3. Read `relational_rule.rs` (728 lines) for relational operator semantics (`inside`, `before`, `after`, etc.)

**How does the Node.js binding work?**
1. Read `.github/workflows/napi.yml` (162 lines) to understand the build system
2. Check `crates/napi/` for Rust FFI code
3. Grep `napi` in `files.md` to find binding implementations

**Debugging a pattern matching failure:**
1. Check `crates/core/src/ops.rs` for operator implementations (EQ, MATCHES, CONTAINS, etc.)
2. Search for the pattern operator in `files.md` (e.g., `MATCHES`, `INSIDE`)
3. Trace through the cursor/node traversal in `crates/core/src/cursor.rs`

**How does rule deserialization handle special cases?**
1. Start at `crates/config/src/rule_config.rs` — the main entry point
2. Check specific rule types in `crates/config/src/rule/` subdirectories
3. Grep the specific field name (e.g., `selector`, `pattern`, `regex`) in `files.md`

## Tips

- **Relational rules are complex:** Start with `relational_rule.rs` (728 lines) — this is the largest rule implementation and controls `inside`, `before`, `after`, `reaches` operators
- **Pattern matching entry point:** Search for `PatternMeta` or `MetaVariable` in `files.md` — both lead to core matching logic
- **Tree-sitter context:** Check `.github/workflows/napi.yml`, `pyo3.yml`, `wasm.yml` to understand language binding builds
- **Rule deserialization trace:** `rule_config.rs` (899 lines) → `deserialize_env.rs` (328 lines) → specific rule type files in `rule/` subdirectory
- **Language implementations:** Each language in `crates/language/*/src/lib.rs` maps tree-sitter grammar queries to ast-grep syntax

---

## Telemetry

Completion signal (always emit as final output line):
```
[SKILL_COMPLETE] skill=repomix-reference-ast-grep outcome=success|failure queries=N
```

| Span | Attributes | Source |
|------|-----------|--------|
| `skill-activation-prompt` | `skill_activation.matches` | user-prompt.ts |
| `plugin-post-tool` | `plugin.name=repomix-reference-ast-grep`, `plugin.output_size` | post-tool.ts |
| `builtin-post-tool` | `builtin.tool=Read\|Grep`, `builtin.result_count` | post-tool.ts |

---

This skill was generated by [Repomix](https://github.com/yamadashy/repomix) from [Ast Grep](ast-grep/ast-grep)
