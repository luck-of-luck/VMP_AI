# Schema.org HTML & Markdown Enhancement

Implementation plan for detecting, validating, and enhancing Schema.org structured data in HTML and markdown files using ast-grep patterns.

## Scope

- Detect JSON-LD `<script>` tags in HTML
- Match microdata attributes (`itemscope`, `itemtype`, `itemprop`)
- Match RDFa properties (`property`, `typeof`, `resource`)
- Extract Schema.org metadata from markdown frontmatter
- Integrate with existing `features/schema/` tools

## HTML Node Kinds

ast-grep's HTML parser exposes these tree-sitter node kinds:

| Kind | Description | Example |
|------|-------------|---------|
| `element` | Full HTML element including children | `<script type="application/ld+json">...</script>` |
| `tag_name` | Element tag name | `script`, `div`, `span` |
| `attribute_name` | Attribute key | `type`, `itemscope`, `itemprop` |
| `attribute_value` | Attribute value (quoted content) | `"application/ld+json"` |
| `text` | Text content inside elements | JSON-LD body, visible text |

## YAML Rules

### 1. Detect JSON-LD Script Tags

```yaml
id: find-json-ld-scripts
language: html
rule:
  kind: element
  has:
    stopBy: { kind: tag_name }
    kind: tag_name
    pattern: script
  has:
    kind: attribute_value
    regex: application/ld\+json
```

Matches `<script type="application/ld+json">...</script>` elements. The `stopBy` on `tag_name` prevents matching nested elements.

### 2. Extract JSON-LD Content

```yaml
id: extract-json-ld-content
language: html
rule:
  kind: text
  pattern: $JSON_CONTENT
  inside:
    kind: element
    has:
      stopBy: { kind: tag_name }
      kind: tag_name
      pattern: script
    has:
      kind: attribute_value
      regex: application/ld\+json
```

Captures the raw JSON-LD text inside matched script tags via `$JSON_CONTENT`.

### 3. Detect Microdata Attributes

```yaml
id: find-microdata-attributes
language: html
rule:
  kind: attribute_name
  regex: ^(itemscope|itemtype|itemprop|itemid|itemref)$
```

Finds all Schema.org microdata attributes across HTML files.

### 4. Detect Microdata Elements with Type

```yaml
id: find-microdata-elements
language: html
rule:
  kind: element
  has:
    kind: attribute_name
    regex: ^itemscope$
  has:
    kind: attribute_value
    pattern: $SCHEMA_TYPE
constraints:
  SCHEMA_TYPE:
    regex: schema\.org
```

Matches elements with `itemscope` whose `itemtype` references schema.org.

### 5. Detect RDFa Properties

```yaml
id: find-rdfa-properties
language: html
utils:
  in-element:
    inside:
      kind: element
      stopBy: { kind: element }
rule:
  kind: attribute_name
  regex: ^(property|typeof|resource|about|prefix|vocab)$
  matches: in-element
```

Finds RDFa attributes within their nearest parent element context.

### 6. Find Elements Missing Required Schema.org Properties

```yaml
id: microdata-missing-itemprop
language: html
rule:
  kind: element
  has:
    kind: attribute_name
    regex: ^itemscope$
  not:
    has:
      kind: attribute_name
      regex: ^itemtype$
```

Detects `itemscope` elements that lack the required `itemtype` attribute.

## Markdown Frontmatter

ast-grep does not have first-class markdown support. Two approaches:

### Option A: Regex-Based Extraction (Recommended)

Parse markdown files with Python regex to extract YAML frontmatter, then validate Schema.org fields with the existing schema tools.

```python
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---", re.DOTALL)

def extract_frontmatter(content: str) -> dict[str, Any] | None:
    match = FRONTMATTER_RE.match(content)
    if match:
        return yaml.safe_load(match.group(1))
    return None
```

Target fields: `@type`, `@context`, `schema`, `structured_data`, or CMS-specific keys like `seo.schema`.

### Option B: Custom Language Registration

Register markdown as a custom language in `sgconfig.yml` via `languageGlobs`:

```yaml
languageGlobs:
  html: ["**/*.md"]
```

This parses `.md` files as HTML, which works for embedded HTML blocks but loses frontmatter context.

**Recommendation**: Use Option A for frontmatter and Option B only when scanning for inline HTML structured data within markdown content.

## Implementation Plan

### Phase 1: HTML Detection Tools

Add to `features/schema/html_service.py`:

| Function | Purpose |
|----------|---------|
| `detect_jsonld_in_html(project_folder, file_globs)` | Find JSON-LD script tags, extract and parse content |
| `detect_microdata_in_html(project_folder, file_globs)` | Find microdata attributes, map to Schema.org types |
| `detect_rdfa_in_html(project_folder, file_globs)` | Find RDFa properties |
| `validate_html_structured_data(project_folder, file_globs)` | Run all detections, cross-reference with schema.org vocabulary |

Each function uses `find_code_by_rule_impl` with the YAML rules above, then post-processes matches.

### Phase 2: Markdown Frontmatter Tools

Add to `features/schema/markdown_service.py`:

| Function | Purpose |
|----------|---------|
| `extract_schema_from_frontmatter(project_folder, file_globs)` | Parse YAML frontmatter, extract Schema.org fields |
| `validate_frontmatter_schema(project_folder, file_globs)` | Validate extracted types against schema.org vocabulary |
| `suggest_frontmatter_enhancements(project_folder, file_globs)` | Suggest missing Schema.org properties based on content type |

### Phase 3: MCP Tool Registration

Register combined tools in `features/schema/tools.py`:

```python
@mcp.tool()
def detect_structured_data(
    project_folder: str,
    file_globs: list[str] | None = None,
    formats: list[str] | None = None,
) -> dict[str, Any]:
    """Detect Schema.org structured data in HTML and markdown files.

    Args:
        project_folder: Project root path
        file_globs: File patterns to scan (default: **/*.html, **/*.md)
        formats: Formats to detect: json-ld, microdata, rdfa, frontmatter (default: all)
    """
```

```python
@mcp.tool()
def validate_structured_data(
    project_folder: str,
    file_globs: list[str] | None = None,
) -> dict[str, Any]:
    """Validate Schema.org structured data in HTML/markdown against schema.org vocabulary.

    Returns validation errors, warnings, and enhancement suggestions.
    """
```

### Phase 4: Integration with Existing Enhancement Tools

Wire into `enhancement_service.py`:

- `analyze_entity_graph` reads JSON-LD from HTML files as input
- `_suggest_missing_entities` considers entities found in HTML when suggesting additions
- `build_entity_graph` can output JSON-LD wrapped in `<script>` tags for HTML embedding

## File Structure

```
src/ast_grep_mcp/features/schema/
  html_service.py      # NEW - HTML structured data detection
  markdown_service.py  # NEW - Markdown frontmatter extraction
  client.py            # EXISTING - add JSON-LD output helpers
  enhancement_service.py # EXISTING - wire in HTML/MD sources
  tools.py             # EXISTING - register new MCP tools
```

## Test Plan

```
tests/unit/
  test_schema_html.py       # HTML detection rules, JSON-LD parsing
  test_schema_markdown.py   # Frontmatter extraction, validation
  test_schema.py            # Existing - add integration cases
```

Test cases:
- JSON-LD detection in single and multiple script tags
- Malformed JSON-LD content handling
- Microdata attribute extraction across nested elements
- RDFa property detection
- Frontmatter with and without Schema.org fields
- Mixed format detection (HTML with both JSON-LD and microdata)
- Empty/missing frontmatter edge cases

## Dependencies

- `ast-grep` CLI with HTML language support (already available)
- `pyyaml` for frontmatter parsing (already in deps via `uv`)
- No new external dependencies required
