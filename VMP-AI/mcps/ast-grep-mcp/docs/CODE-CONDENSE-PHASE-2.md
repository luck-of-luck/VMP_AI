# Code Condense Phase 2: Additional Insights from Whitepaper Research

> Supplementary findings from the [code-condense-whitepaper](./code-condense-whitepaper/) collection that extend the Phase 1 plan (see [Appendix A](#appendix-a-phase-1-reference-excerpts)) with dictionary training, complexity-guided extraction, per-file-type routing, and archival pipeline options.

### Provenance Guide

This document contains two types of content, marked throughout:

- **Sourced claims** cite specific sections of the whitepaper collection. All benchmark numbers, compression ratios, and tool capabilities are traceable to cited sources.
- **Design inferences** (marked with `> Design inference:` callouts) are proposed specifications derived from sourced principles but with specific thresholds or parameters chosen by the author. These should be validated during implementation.

---

## 1. Dictionary Training Integration

**Source:** [zstd-condense-report.md](./code-condense-whitepaper/zstd-condense-report.md) Section "Small Data Compression", [pipeline doc](./code-condense-whitepaper/repomix_to_condense_with_additional_integrations.md) Section 3d

Repos with consistent coding style (naming conventions, indentation, import patterns) benefit from zstd dictionary training — 10-30% better compression on small-to-medium files (<100KB) vs. standard zstd.

### Proposed Tool

| Tool | Purpose | Input | Output |
|---|---|---|---|
| `condense_train_dictionary` | Generate zstd dictionary from codebase samples | `path`, `language`, `sample_count` | Dictionary bytes + training stats |

### Implementation

```python
# In features/condense/dictionary.py
import subprocess

async def train_dictionary_impl(
    path: str,
    language: str | None = None,
    sample_count: int = 200,
) -> DictionaryResult:
    """Train a zstd dictionary on representative code samples."""
    # 1. Collect sample files (filtered by language if specified)
    # 2. Run: zstd --train <samples> -o <dict_path>
    # 3. Return dict path + stats (dict size, sample count, est. improvement)
```

### Constants Addition

> **Design inference:** `SAMPLE_COUNT` and `MAX_SAMPLE_SIZE_BYTES` are proposed defaults. `DICT_SIZE_BYTES` (110 KB) matches the zstd CLI default. Tune `SAMPLE_COUNT` based on repo size during implementation.

```python
class CondenseDictionaryDefaults:
    """Defaults for zstd dictionary training."""
    SAMPLE_COUNT = 200
    MAX_SAMPLE_SIZE_BYTES = 102_400  # 100 KB per sample
    DICT_SIZE_BYTES = 112_640  # 110 KB (zstd default)
    DICT_OUTPUT_DIR = ".condense/dictionaries"
```

### Best Fit

- Monorepos with many similarly-structured small files
- Microservices repos with shared patterns
- Configuration file collections (.json, .yaml)

---

## 2. Complexity-Guided Extraction Depth

**Source:** [pipeline doc](./code-condense-whitepaper/repomix_to_condense_with_additional_integrations.md) Section 3b, Appendix A.1 (complexity-guided extraction)

Appendix A.1 (complexity-guided extraction) states:
- "High complexity functions: Keep full body (complex = important)"
- "Low complexity functions: Signature + docstring only"
- "Trivial functions (≤3 lines): Inline the body"

This section formalizes those rules with specific thresholds.

### Extraction Depth Rules

> **Design inference:** The specific cyclomatic/cognitive cutoffs below are proposed thresholds, not sourced from the whitepaper. They are derived from the project's existing `ComplexityDefaults` (cyclomatic ≤20, cognitive ≤30) and Appendix A.1 (complexity-guided extraction) guidance. Tune during implementation based on measured reduction vs. information loss.

| Cyclomatic Complexity | Cognitive Complexity | Extraction Behavior | Source |
|---|---|---|---|
| ≤5 and ≤3 lines | Any | **Inline**: keep full body (trivial, costs little) | Appendix A.1: "Trivial functions (≤3 lines): Inline the body" |
| ≤10 | ≤15 | **Signature + docstring**: low complexity, strip body | Appendix A.1: "Low complexity functions: Signature + docstring only" |
| >10 | >15 | **Full body**: high complexity = important logic, keep it | Appendix A.1: "High complexity functions: Keep full body" |
| Any | Any (test files) | **Signature only**: test names matter, bodies don't | Appendix A.2: test files strategy |

### Parameter Addition to `condense_extract_surface`

```python
async def extract_surface_impl(
    path: str,
    language: str,
    include_docstrings: bool = True,
    complexity_guided: bool = False,  # NEW: use complexity to decide depth
    complexity_threshold: int = 10,   # NEW: cyclomatic threshold for full-body keep
) -> str:
```

### Reuse

- `features/complexity/complexity_analyzer.py` provides per-function cyclomatic and cognitive scores
- Threshold constants already exist in `CondenseDefaults.MAX_FUNCTION_BODY_LINES` (3 lines) and `ComplexityDefaults`

---

## 3. Per-File-Type Routing in `condense_pack`

**Source:** [pipeline doc](./code-condense-whitepaper/repomix_to_condense_with_additional_integrations.md) Section 3c (Makefile strategies)

Appendix A.2 (polyglot pipeline strategy) describes polyglot strategy selection but the `condense_pack` tool definition does not expose file-type routing. This section formalizes it.

### File-Type Strategy Map

| File Type | Detection | Strategy | Reason |
|---|---|---|---|
| Code (.ts, .py, .rs, .go, .java) | Extension + Tree-sitter parseable | `ai_chat` or `ai_analysis` | AST extraction is the high-value step |
| Config (.json, .yaml, .toml, .xml) | Extension | **Pass-through** (no AST extraction) | Structure must be preserved verbatim |
| Text (.md, .txt, .rst) | Extension | Strip empty lines only | Natural language; minimal safe reduction |
| Test files (`**/test*`, `**/spec*`) | Path pattern | Extract signatures only | Test names matter, bodies are regenerable |
| Generated files (`dist/`, `build/`, `*.gen.*`) | Path pattern + markers | **Exclude entirely** | Regenerable from source |
| SVG (.svg) | Extension | Pass-through + flag as high-compressibility | XML text; compresses 3-4x under zstd |
| Images (.png, .jpg, .gif) | Extension | **Exclude** | Binary; already compressed |
| Lock files (`*.lock`, `package-lock.json`) | Filename | **Exclude** | Regenerable, large, low information density |

### Parameter Addition to `condense_pack`

```python
async def condense_pack_impl(
    path: str,
    language: str | None = None,
    strategy: str = "ai_analysis",
    file_type_routing: bool = True,  # NEW: auto-select strategy per file type
    exclude_patterns: list[str] | None = None,  # NEW: additional exclusions
) -> CondenseResult:
```

### Constants Addition

> **Design inference:** Extension sets and glob patterns below are proposed defaults derived from the whitepaper's per-file-type strategy table (Section 3c) and standard conventions. The whitepaper specifies categories (code, config, text, images) and strategies; the specific extensions are implementation choices.

```python
class CondenseFileRouting:
    """File-type routing for polyglot condensation."""
    CODE_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".java", ".rb", ".php", ".swift", ".kt", ".cs", ".cpp", ".c", ".h"}
    CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".xml", ".ini", ".env.example"}
    TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".adoc"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp"}
    EXCLUDE_PATTERNS = ["dist/**", "build/**", "*.lock", "package-lock.json", "yarn.lock", "*.gen.*", "*.min.js", "*.min.css"]
    TEST_PATTERNS = ["**/test_*", "**/test/**", "**/*_test.*", "**/*.spec.*", "**/*.test.*"]
```

---

## 4. Archival Pipeline Options (Downstream)

**Source:** [pipeline doc](./code-condense-whitepaper/repomix_to_condense_with_additional_integrations.md) Section 3a, [PPM doc](./code-condense-whitepaper/prediction-by-partial-matching.md)

These are downstream of ast-grep-mcp's semantic extraction but relevant for users building full pipelines.

### PPMd vs. zstd for Code Archives

From the [Large Text Compression Benchmark](https://mattmahoney.net/dc/text.html) (enwik9, 1 GB Wikipedia XML), as cited in the pipeline doc Section 3a:

| Metric | zstd --ultra -22 | PPMd (7zip, order 10) | Source |
|---|---|---|---|
| Compression ratio (text) | 4.6x | 5.6x | Pipeline doc Section 3a table |
| Compress time (enwik9) | 701s | 503s | Pipeline doc Section 3a table |
| Decompress speed | ~1500 MB/s | 5-10x slower than zstd | Pipeline doc Section 3a narrative |
| Memory | 792 MB | 1630 MB | Pipeline doc Section 3a table |

> **Note on PPMd decompress speed:** The pipeline doc states "5-10x slower decompression" relative to zstd. Other docs in the collection report PPMd decompress at 5-20 MB/s depending on workload (OTEL doc: "300x slower than zstd"; SQL/KV doc: "20 MB/s"). The actual speed varies significantly by data type and implementation. Do not assume a specific number — benchmark on representative code samples.

**Recommendation:** Use zstd for active/hot data (fast decompress for AI tools). Use PPMd for cold archival (compress once, read rarely). PPMd's 15-25% better ratio on text matters at scale but the significantly slower decompress rules it out for interactive use.

### Full Pipeline with ast-grep-mcp

From pipeline doc Section 4 summary table:

```
Active use:   ast-grep-mcp condense → repomix pack → zstd -9      (91-93% reduction)
Cold archive: ast-grep-mcp condense → repomix pack → PPMd via 7z  (93-95% reduction)
```

### Documentation Note

Add to `condense_pack` tool description:

> The condensed output is optimized for downstream compression. For active AI consumption, pipe through `zstd -9`. For archival, use `7z a -m0=PPMd -mx=9`. See the [code-condense-whitepaper](./code-condense-whitepaper/) for pipeline benchmarks.

---

## 5. ast-grep-mcp's Differentiator vs. Repomix

**Source:** [repomix cheat sheet](./code-condense-whitepaper/repomix-command-line-cheat-sheet.md) Section "Is --compress Lossless?"

Repomix `--compress` is all-or-nothing:
- No per-function granularity
- No complexity-aware depth selection
- No selective pattern extraction
- No normalization pre-pass
- Single boolean toggle, no configuration

ast-grep-mcp's `condense` feature provides:
- **Pattern-based extraction** — keep specific exports, types, or API surfaces
- **Complexity-guided depth** — keep bodies of complex functions, strip simple ones
- **Normalization pre-pass** — canonical forms increase downstream compression
- **Dead code elimination** — remove unused imports, debug stmts before packing
- **Deduplication integration** — collapse clones before extraction
- **Per-file-type routing** — different strategies for code, config, text, tests
- **Estimation without modification** — dry-run mode for planning

This surgical precision is the core value proposition. Repomix treats all code uniformly; ast-grep-mcp treats each function, file, and language according to its role.

---

## 6. Updated Implementation Order

Extends the Phase 1 implementation order (Appendix A.3) with Phase 2 additions:

| Phase | Work | New in Phase 2 |
|---|---|---|
| **P1** | Constants + models + estimator | `CondenseDictionaryDefaults`, `CondenseFileRouting` |
| **P2** | Surface extraction | `complexity_guided` parameter |
| **P3** | Normalizer | — |
| **P4** | Strip | — |
| **P5** | Pack pipeline | `file_type_routing` parameter, per-type strategy map |
| **P6** | Tool registration | — |
| **P7** | Tests | Dictionary training tests, file routing tests |
| **P8** | Polyglot strategy | — |
| **P9** | Dictionary training tool | `condense_train_dictionary` (new) |

---

## References

- [Appendix A](#appendix-a-phase-1-reference-excerpts) — Phase 1 reference excerpts (folded in from retired `CODE-CONDENSE-PREP.md`)
- [Repomix-to-Condense Pipeline](./code-condense-whitepaper/repomix_to_condense_with_additional_integrations.md) — Core whitepaper
- [Repomix CLI Cheat Sheet](./code-condense-whitepaper/repomix-command-line-cheat-sheet.md) — Repomix limitations
- [Zstandard Condense Report](./code-condense-whitepaper/zstd-condense-report.md) — Dictionary training, benchmarks
- [Prediction by Partial Matching](./code-condense-whitepaper/prediction-by-partial-matching.md) — PPMd archival option

---

## Appendix A: Phase 1 Reference Excerpts

> Folded in from the retired `CODE-CONDENSE-PREP.md` (deleted in commit `8dca38e`). Only the sections referenced elsewhere in this document are preserved; the remainder of the Phase 1 plan is obsolete.

### A.1 Complexity-Guided Extraction (formerly PREP Section 6b)

Use `features/complexity/complexity_analyzer.py` to decide extraction depth:

- **High complexity functions:** Keep full body (complex = important)
- **Low complexity functions:** Signature + docstring only
- **Trivial functions (≤3 lines):** Inline the body

### A.2 Polyglot Pipeline Strategy (formerly PREP Section 7)

Per-file-type strategy selection (see also Section 3 above for the expanded Phase 2 routing table):

| File Type | Strategy | Reason |
|---|---|---|
| Code (.ts, .py, .rs, .go) | `condense_pack` with `ai_chat` | AST extraction removes 70%+ |
| Config (.json, .yaml, .toml) | Pass-through (no AST extraction) | Structure must be preserved |
| Text (.md, .txt) | Strip empty lines only | Natural language, minimal reduction |
| Test files | `condense_extract_surface` | Keep test names/structure, strip bodies |
| Generated files | Exclude entirely | Regenerable from source |

Implementation: `strategies.py` selects per-file strategy based on language and path patterns.

### A.3 Phase 1 Implementation Order (formerly PREP Section 10)

| Phase | Work | Dependencies | Est. Files |
|---|---|---|---|
| **P1** | Constants + models + estimator | None | 3 |
| **P2** | Surface extraction (per-language patterns) | P1 | 2 |
| **P3** | Normalizer (rewrite transforms) | P1 | 1 |
| **P4** | Strip (dead code removal) | P1 | 1 |
| **P5** | Pack pipeline (orchestration) | P2, P3, P4 | 1 |
| **P6** | Tool registration + MCP integration | P5 | 2 |
| **P7** | Tests (unit + integration) | P6 | 8 |
| **P8** | Polyglot strategy refinement | P7 | 1 |

Total new files: ~19 (6 source + 1 model + 1 constants update + ~8 test files + 3 supporting).
