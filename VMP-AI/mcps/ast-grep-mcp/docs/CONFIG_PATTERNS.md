# Config File Search Patterns

Config files use declarations and objects rather than executable code, so standard
function/class patterns return no matches. This guide documents ast-grep patterns
that work against common config file formats.

## Language Mapping

Non-standard extensions must be mapped to a language — either via `--config sgconfig.yml`
(see CF-01 in BACKLOG.md) or by passing `language_globs` to `find_code_impl`.

| Extension | Language | Notes |
|-----------|----------|-------|
| `.cjs` | `javascript` | CommonJS config modules |
| `.mjs` | `javascript` | ES module config files |
| `.json` | `json` | Standard JSON data |
| `.schema.json` | `json` | JSON Schema files |
| `.eslintrc` | `json` | ESLint config (no extension) |
| `.babelrc` | `json` | Babel config (no extension) |
| `.yml`, `.yaml` | `yaml` | YAML config files |

Example `language_globs`:
```python
language_globs = {
    "javascript": ["**/*.cjs", "**/*.mjs"],
    # ".eslintrc" is an exact filename pattern supported by ast-grep's languageGlobs.
    # This only takes effect with the `scan` subcommand (--config sgconfig.yml).
    # Use "**/.eslintrc" if your tool path uses glob expansion before passing to ast-grep.
    "json": [".eslintrc", ".babelrc", "*.schema.json"],
    "yaml": ["*.config.yml"],
}
```

---

## CommonJS Config (`.cjs`, `.js`)

Language: `javascript`

**Note:** These are JavaScript object expression patterns, not YAML key patterns.
Object properties must be matched inside their containing object literal context.

```
# Module exports (any value — broadest match)
module.exports = $VALUE

# Module exports object with any properties (single or multi-property)
module.exports = {$$$PROPS}

# Property assignment
$OBJ.$PROP = $VALUE

# Require call
require($MODULE)
```

### PM2 Ecosystem (`ecosystem.config.cjs`)

PM2 apps are entries in the `apps` array. Use `{$$$PROPS}` (no trailing comma)
to match objects with any number of properties including single-property objects:

```
# All exports with apps array (matches single-property and multi-property objects)
module.exports = {$$$PROPS}

# Function call (e.g. process.env access)
process.env.$VAR

# Arrow function in config
$KEY: ($$$ARGS) => $BODY
```

For PM2-specific field extraction, use `find_code_by_rule_impl` with a rule that
matches string literals or property assignments within the `apps` array context.

---

## JSON Data (`.json`)

Language: `json`

```
# Any key-value pair
"$KEY": $VALUE

# Nested object
"$KEY": { $$$PROPS }

# Array value
"$KEY": [$$$ITEMS]

# String value
"$KEY": "$STR"
```

### JSON Schema (`.schema.json`)

```
# Property definitions
"properties": { $$$DEFS }

# Required fields list
"required": [$$$FIELDS]

# $ref reference
"$ref": "$PATH"

# Type constraint
"type": "$TYPE"

# Enum constraint
"enum": [$$$VALUES]
```

### package.json

```
# Script definition
"$NAME": "$CMD"

# Dependency entry
"$PKG": "$VER"

# Main entry point
"main": "$PATH"
```

---

## YAML Config (`.yml`, `.yaml`)

Language: `yaml`

```
# Any key: value
$KEY: $VALUE

# List item
- $ITEM

# Nested mapping
$KEY:
  $$$PROPS
```

---

## Zod Schemas (TypeScript)

Language: `typescript`

```
# Object schema
z.object({ $$$FIELDS })

# String validator
z.string()

# Number validator
z.number()

# Array schema
z.array($INNER)

# Optional field
z.optional($SCHEMA)

# Enum schema
z.enum([$$$VALUES])

# Union type
z.union([$$$SCHEMAS])

# Inferred type
z.infer<typeof $SCHEMA>
```

---

## JSON-LD / Schema.org

Language: `json`

```
# @type declaration
"@type": $TYPE

# @context declaration
"@context": $CTX

# @id reference
"@id": $ID

# @graph container
"@graph": [$$$ENTITIES]

# Property with @value
"$PROP": { "@value": $VAL }
```

---

## OpenAPI / Swagger

Language: `json` or `yaml`

### JSON
```
# Path operation
"$METHOD": { $$$OP }

# Parameter definition
"$NAME": { "in": "$LOC", $$$PROPS }

# Schema reference
"$ref": "#/components/schemas/$NAME"

# Response definition
"$CODE": { "description": "$DESC", $$$PROPS }
```

### YAML
```
# Path entry
$PATH:
  $METHOD:
    $$$OPERATION

# Response code
$CODE:
  description: $DESC
```

---

## ESLint Config (`.eslintrc`, `.eslintrc.json`)

Language: `json`

```
# Rule configuration
"$RULE": $SEVERITY

# Rule with options
"$RULE": [$SEVERITY, $$$OPTS]

# Extends list item
"$BASE"

# Plugin name
"$PLUGIN"
```

---

## Notes

- **Zero matches** on config dirs with default patterns (`function $NAME(...)`) is expected — switch to the patterns above.
- **`run_all_tools.py`** auto-detects config-only directories and warns when function-oriented patterns are used (CF-03).
- **`find_code_impl`** accepts `language_globs` since CF-01 to map non-standard extensions at the tool call level.
