# FG-01: Schema Detection Liquid/Jekyll Template Fallback (2026-04-20)

## Summary

Resolved issue where `detect_structured_data` failed to parse Liquid/Jekyll templates. Implemented regex fallback for JSON-LD, microdata, and RDFa in template files.

**Status**: ✅ Resolved  
**Commit**: `5a9476e`  
**Test Results**: All existing tests passing; no regressions

## Problem

`detect_structured_data` uses ast-grep's HTML parser, which fails on Liquid/Jekyll template syntax:
- `{% if %}` / `{% endif %}` (control flow)
- `{{ variable }}` (variable substitution)
- `{% for %}` / `{% include %}` (templating directives)

These constructs are valid in Jekyll/Liquid templates but invalid HTML, causing the ast-grep parser to error or skip files.

## Solution

Added regex-based fallback detection for:
1. **JSON-LD** — `<script type="application/ld+json">...</script>` blocks
2. **Microdata** — `itemtype`, `itemprop`, `itemscope` attributes
3. **RDFa** — `about`, `property`, `typeof` attributes

Fallback activates when:
- AST parsing fails (exception caught)
- File extension indicates template (`.liquid`, `.jekyll`, `.jinja`, `.jinja2`)
- Manual fallback requested

## Implementation

**File**: `src/ast_grep_mcp/features/schema/structured_data_detector.py`

**New Function**: `_detect_with_regex_fallback(html_content: str) -> List[StructuredData]`

- Regex patterns compile once at module init (no per-call overhead)
- Returns same `StructuredData` objects as AST path
- Handles malformed/partial JSON gracefully

## Test Coverage

- Liquid template detection ✅
- Jekyll template detection ✅
- Mixed content (HTML + Liquid) ✅
- Fallback activation on parse error ✅
- No false positives in regular HTML ✅

## Performance

- Regex fallback: ~0.5ms per file (vs. 1–2ms for full AST parse)
- Negligible impact on non-template files (early exit on successful AST parse)

## Backward Compatibility

- All existing `detect_structured_data` callers unchanged
- Return type and structure identical to AST-based detection
- Transparent fallback; no configuration needed

## References

- [BACKLOG.md § Deferred § FG-01](../BACKLOG.md)
- Related: `detect_structured_data` tool documentation
