# Technology Stack

## Languages

- **Rust** — Core implementation (pattern matching, rule engine, CLI, language crates)
- **TypeScript/JavaScript** — Node.js bindings via napi-rs (see `.github/workflows/napi.yml`)
- **Python** — Python bindings via PyO3 (see `.github/workflows/pyo3.yml`)
- **WebAssembly** — Browser/wasm target (see `.github/workflows/wasm.yml`)

## Core Dependencies

### Pattern Matching & Tree-Sitter
- **tree-sitter** — Incremental parsing framework; ast-grep depends on tree-sitter grammars for each language (C++, Go, JavaScript, Python, Rust, etc.)

### Language Bindings
- **napi-rs** — Node.js N-API bindings (Rust ↔ JavaScript/TypeScript FFI)
- **pyo3** — Python bindings (Rust ↔ Python FFI)
- **wasm-pack** — WebAssembly build and packaging

### Serialization & Configuration
- **serde** — Deserialization of YAML rule files and JSON schemas
- **serde_yaml** — YAML parsing for rule configuration

### CLI & Argument Parsing
- **clap** — Command-line argument parsing (see `crates/cli/src/utils/args.rs`)

### Testing & Development
- Various Rust test utilities (see `crates/*/tests/` directories)
- YAML-based test case definitions for rule verification

## Build System

### Workflows (`.github/workflows/`)
- **napi.yml** (162 lines) — Builds and publishes Node.js package (native binaries for macOS, Linux, Windows)
- **pyo3.yml** (167 lines) — Builds and publishes Python wheel (native wheels for multiple Python versions)
- **pypi.yml** (196 lines) — Python package publication to PyPI
- **wasm.yml** (112 lines) — WebAssembly build for browser environments
- **release.yml** (123 lines) — Release orchestration
- **coverage.yaml** (63 lines) — Code coverage reporting

### Build Configuration
- **Cargo.toml** — Rust package manifest (workspace root)
- **Cargo.toml** per crate (cli, config, core, language, napi, pyo3, wasm, etc.)
- **pyproject.toml** — Python project configuration (for PyO3 builds)

## Crate Structure

| Crate | Purpose | Dependencies |
|-------|---------|--------------|
| **cli** | Command-line interface and subcommands | core, config, language |
| **config** | Rule engine and YAML deserialization | core, serde, serde_yaml |
| **core** | Tree-sitter integration and pattern matching | tree-sitter, regex |
| **language** | Per-language implementations (bash, cpp, css, go, java, js, lua, python, rust, tsx, typescript, yaml) | core, tree-sitter |
| **dynamic** | Dynamic language loading via native libraries | — |
| **napi** | Node.js FFI wrapper | napi-rs, napi-derive |
| **pyo3** | Python FFI wrapper | pyo3 |
| **wasm** | WebAssembly target | wasm-bindgen |

## Schema Files (Large Reference Data)

- **schemas/languages.json** (3,606 lines) — Language definitions and tree-sitter grammar metadata
- **schemas/*_rule.json** — JSON schema validation for per-language rule constraints
  - bash_rule.json (1,300+ lines)
  - cpp_rule.json (1,300+ lines)
  - Similar patterns for other languages

*Note: These files are reference/validation data, not active logic. Query sparingly.*

## Key File Organization

### Core Logic (Load-Bearing Files)
- `crates/core/src/meta_var.rs` — Metavariable extraction and matching
- `crates/core/src/ops.rs` — Operator implementations (EQ, MATCHES, CONTAINS, etc.)
- `crates/core/src/cursor.rs` — AST node traversal and iteration
- `crates/config/src/rule_config.rs` (899 lines) — YAML rule deserialization entry point
- `crates/config/src/rule/relational_rule.rs` (728 lines) — Relational operator semantics (`inside`, `before`, `after`)

### CLI & Workflows
- `crates/cli/src/scan.rs` (536 lines) — Scan command implementation
- `crates/cli/src/run.rs` (466 lines) — Run command implementation
- `crates/cli/src/verify.rs` (365 lines) — Test/verify command implementation
- `crates/cli/src/utils/args.rs` (372 lines) — Argument parsing and CLI options

### Language Bindings
- `crates/napi/` — Node.js native bindings
- `crates/pyo3/` — Python bindings
- `crates/wasm/` — WebAssembly bindings
