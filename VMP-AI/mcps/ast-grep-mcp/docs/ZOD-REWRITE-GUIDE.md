# Zod Rewrite Guide

Complete guide to using ast-grep rewrite rules for enforcing Zod best practices.

## Quick Start

### Using Pre-built Rules Files

```bash
# Find all z.any() violations
uv run main.py find_code_by_rule \
  --project_folder . \
  --rule_path rules/zod-validation-rules.yaml \
  --rule_id no-any-schema

# Fix all import violations (dry-run preview)
uv run main.py rewrite_code \
  --project_folder . \
  --yaml_rule "$(cat rules/import-zod-rules.yaml | head -20)" \
  --dry_run true

# Apply fixes with backup
uv run main.py rewrite_code \
  --project_folder . \
  --yaml_rule "$(cat rules/zod-validation-rules.yaml | head -20)" \
  --dry_run false
```

### Using the MCP Tools

```
# List available Zod rules (category: 'schema', 'import', or 'all')
list_zod_rewrite_rules(category="all")

# Fetch a specific rule and apply it
rule = get_zod_rewrite_rule(rule_id="no-any-schema")
rewrite_code(project_folder="/path/to/project", yaml_rule=rule["yaml_rule"], dry_run=True)
```

### Using Templates from Code

```python
from ast_grep_mcp.features.rewrite.zod_templates import get_zod_rule, list_schema_rules
from ast_grep_mcp.features.rewrite.service import rewrite_code_impl

# Get a specific rule
rule = get_zod_rule('no-any-schema')

# Preview changes
result = rewrite_code_impl(
    project_folder='/path/to/project',
    yaml_rule=rule,
    dry_run=True  # Always preview first!
)

# View available rules
rules = list_schema_rules()
for rule_id, description in rules.items():
    print(f"{rule_id}: {description}")
```

## Zod Schema Validation Rules

### 1. no-any-schema

**Problem:** `z.any()` is unsafe and vague.

**Pattern:**
```typescript
// ❌ Bad
const userSchema = z.object({
  data: z.any()
});
```

**Fix:**
```typescript
// ✅ Good
const userSchema = z.object({
  data: z.unknown().catch({})
});
```

**YAML Rule:**
```yaml
id: no-any-schema
language: typescript
rule:
  pattern: z.any()
fix: z.unknown().catch({})
```

---

### 2. require-schema-suffix

**Problem:** Schema variables should end with "Schema" for clarity.

**Pattern:**
```typescript
// ❌ Bad
const user = z.object({ name: z.string() });

// ✅ Good
const userSchema = z.object({ name: z.string() });
```

**YAML Rule:**
```yaml
id: require-schema-suffix
language: typescript
rule:
  pattern: const $NAME = z.object($$ARGS)
fix: const $${NAME}Schema = z.object($$ARGS)
```

---

### 3. require-error-message

**Problem:** `refine()` callbacks should include error messages.

**Pattern:**
```typescript
// ❌ Bad
const schema = z.string().refine((val) => val.length > 5);

// ✅ Good
const schema = z.string().refine(
  (val) => val.length > 5,
  { message: "String must be longer than 5 characters" }
);
```

**YAML Rule:**
```yaml
id: require-error-message
language: typescript
rule:
  pattern: $SCHEMA.refine($CB)
fix: $SCHEMA.refine($CB, { message: "Validation failed" })
```

---

### 4. prefer-enum-over-literal-union

**Problem:** Union of literal strings should use `.enum()` instead.

**Pattern:**
```typescript
// ❌ Bad
const statusSchema = z.union([
  z.literal("active"),
  z.literal("inactive"),
  z.literal("pending")
]);

// ✅ Good
const statusSchema = z.enum(["active", "inactive", "pending"]);
```

**YAML Rule:**
```yaml
id: prefer-enum-over-literal-union
language: typescript
rule:
  pattern: z.union([z.literal($LIT1), z.literal($LIT2)])
fix: z.enum([$LIT1, $LIT2])
```

---

### 5. no-optional-and-default-together

**Problem:** Don't use both `.optional()` and `.default()` together.

**Pattern:**
```typescript
// ❌ Bad
const fieldSchema = z.string().optional().default("fallback");

// ✅ Good
const fieldSchema = z.string().default("fallback");
```

**YAML Rule:**
```yaml
id: no-optional-and-default-together
language: typescript
rule:
  pattern: $SCHEMA.optional().default($VAL)
fix: $SCHEMA.default($VAL)
```

---

## Zod Import Rules

### 1. import-zod-named-to-namespace

**Problem:** Named imports don't tree-shake well.

**Pattern:**
```typescript
// ❌ Bad
import { z } from 'zod';

// ✅ Good
import * as z from 'zod';
```

**YAML Rule:**
```yaml
id: import-zod-named-to-namespace
language: typescript
rule:
  pattern: import { z } from "zod"
fix: import * as z from "zod"
```

---

### 2. import-zod-default-to-namespace

**Problem:** Default imports should be namespace for consistency.

**Pattern:**
```typescript
// ❌ Bad
import z from 'zod';

// ✅ Good
import * as z from 'zod';
```

---

### 3. import-zod-mixed-to-namespace

**Problem:** Separate namespace and named imports.

**Pattern:**
```typescript
// ❌ Bad
import z, { toJSONSchema } from 'zod';

// ✅ Good
import * as z from 'zod';
import { toJSONSchema } from 'zod';
```

---

## Using rewrite_code() Tool

### Example 1: Fix z.any() violations

```python
yaml_rule = """
id: no-any-schema
language: typescript
rule:
  pattern: z.any()
fix: z.unknown().catch({})
message: "Use z.unknown().catch({}) instead"
"""

result = rewrite_code_impl(
    project_folder='/path/to/project',
    yaml_rule=yaml_rule,
    dry_run=True
)
print(result)  # Preview diffs before applying
```

### Example 2: Fix multiple import patterns

Create a combined rule file with multiple rules and apply:

```python
yaml_rules = """
---
id: import-zod-named
language: typescript
rule:
  pattern: import { z } from "zod"
fix: import * as z from "zod"
---
id: import-zod-default
language: typescript
rule:
  pattern: import z from "zod"
fix: import * as z from "zod"
"""

result = rewrite_code_impl(
    project_folder='/path/to/project',
    yaml_rule=yaml_rules,
    dry_run=False,  # Apply changes
    backup=True     # Create backup first
)
```

### Example 3: Undo changes with rollback_rewrite()

```python
# If something went wrong, rollback
from ast_grep_mcp.features.rewrite.service import rollback_rewrite_impl

# From the rewrite result, get backup_id
backup_id = result['backup_id']

# Rollback
rollback_result = rollback_rewrite_impl(
    backup_id=backup_id,
    project_folder='/path/to/project'
)
```

## Best Practices

1. **Always use dry_run=True first**
   - Preview changes before applying
   - Verify the fixes match your intentions

2. **Enable backups**
   - Default is backup=True
   - Allows easy rollback with rollback_rewrite()

3. **Test with find_code_by_rule first**
   - See how many matches your rule finds
   - Verify it's matching the right patterns

4. **Use context constraints**
   - Add `inside` and `has` to make rules more precise
   - Reduces false positives

5. **Combine related rules**
   - Create multi-rule YAML files for consistent fixes
   - Apply all related patterns in one operation

## Rule Files Location

- **Schema validation rules:** `rules/zod-validation-rules.yaml`
- **Import enforcement rules:** `rules/import-zod-rules.yaml`

## See Also

- [docs/DEDUPLICATION-GUIDE.md](DEDUPLICATION-GUIDE.md) - Deduplication workflows
- [docs/PATTERNS.md](PATTERNS.md) - General refactoring patterns
- ESLint Plugins:
  - [eslint-plugin-zod](https://github.com/marcalexiei/eslint-plugin-zod)
  - [eslint-plugin-import-zod](https://github.com/samchungy/eslint-plugin-import-zod)
