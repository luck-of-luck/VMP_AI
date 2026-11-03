#!/usr/bin/env python3
"""Generate AST-grep rules for eslint-plugin-import-zod patterns."""

from ast_grep_mcp.features.search.service import build_rule_impl

SEPARATOR_WIDTH = 60
SEPARATOR = "=" * SEPARATOR_WIDTH


def print_header(title: str, leading_newline: bool = False) -> None:
    prefix = "\n" if leading_newline else ""
    print(f"{prefix}{SEPARATOR}")
    print(title)
    print(SEPARATOR)


# Rule 1: Named imports of z
print_header("RULE 1: import-zod-named-to-namespace")
rule1 = build_rule_impl(
    pattern='import { z } from "zod"',
    language="typescript",
    rule_id="import-zod-named-to-namespace",
    message='Use namespace import: import * as z from "zod"',
    severity="warning",
    fix='import * as z from "zod"'
)
print(rule1)

# Rule 2: Default imports of z
print_header("RULE 2: import-zod-default-to-namespace", leading_newline=True)
rule2 = build_rule_impl(
    pattern='import z from "zod"',
    language="typescript",
    rule_id="import-zod-default-to-namespace",
    message='Use namespace import: import * as z from "zod"',
    severity="warning",
    fix='import * as z from "zod"'
)
print(rule2)

# Rule 3: Default imports with different names
print_header("RULE 3: import-zod-default-renamed-to-namespace", leading_newline=True)
rule3 = build_rule_impl(
    pattern='import $NAME from "zod"',
    language="typescript",
    rule_id="import-zod-default-renamed-to-namespace",
    message='Use namespace import instead of default import for zod',
    severity="warning"
)
print(rule3)

# Rule 4: Type default imports
print_header("RULE 4: import-zod-type-default-to-namespace", leading_newline=True)
rule4 = build_rule_impl(
    pattern='import type z from "zod"',
    language="typescript",
    rule_id="import-zod-type-default-to-namespace",
    message='Use namespace type import: import type * as z from "zod"',
    severity="warning",
    fix='import type * as z from "zod"'
)
print(rule4)

# Rule 5: Mixed default and named imports
print_header("RULE 5: import-zod-mixed-to-namespace", leading_newline=True)
rule5 = build_rule_impl(
    pattern='import z, { $$EXPORTS } from "zod"',
    language="typescript",
    rule_id="import-zod-mixed-to-namespace",
    message='Use namespace import for z and separate import for other exports',
    severity="warning"
)
print(rule5)

# Rule 6: Subpath imports with z
print_header("RULE 6: import-zod-subpath-to-namespace", leading_newline=True)
rule6 = build_rule_impl(
    pattern='import { z } from "zod/$$SUBPATH"',
    language="typescript",
    rule_id="import-zod-subpath-to-namespace",
    message='Use namespace import for zod subpath: import * as z from "zod/..."',
    severity="warning"
)
print(rule6)

# Rule 7: Type-only mixed imports
print_header("RULE 7: import-zod-type-mixed-to-namespace", leading_newline=True)
rule7 = build_rule_impl(
    pattern='import type { $$TYPES, z } from "zod"',
    language="typescript",
    rule_id="import-zod-type-mixed-to-namespace",
    message='Use namespace import for z: import type * as z from "zod"',
    severity="warning"
)
print(rule7)

print_header("All import-zod rules generated successfully!", leading_newline=True)
