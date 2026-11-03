#!/usr/bin/env python3
"""Generate AST-grep rules for eslint-plugin-zod patterns."""

from ast_grep_mcp.features.search.service import build_rule_impl

SEPARATOR_WIDTH = 60
SEPARATOR = "=" * SEPARATOR_WIDTH


def print_header(title: str, leading_newline: bool = False) -> None:
    prefix = "\n" if leading_newline else ""
    print(f"{prefix}{SEPARATOR}")
    print(title)
    print(SEPARATOR)


# Rule 1: no-any-schema - Disallow z.any()
print_header("RULE 1: no-any-schema")
rule1 = build_rule_impl(
    pattern="z.any()",
    language="typescript",
    rule_id="no-any-schema",
    message="Disallow z.any() - use z.unknown().catch({}) instead",
    severity="error"
)
print(rule1)

# Rule 2: require-schema-suffix - Require Schema suffix
print_header("RULE 2: require-schema-suffix", leading_newline=True)
rule2 = build_rule_impl(
    pattern="const $NAME = z.object($$ARGS)",
    language="typescript",
    rule_id="require-schema-suffix",
    message="Schema variables must end with 'Schema' suffix",
    severity="warning"
)
print(rule2)

# Rule 3: require-error-message - Refine must have error message
print_header("RULE 3: require-error-message", leading_newline=True)
rule3 = build_rule_impl(
    pattern="$SCHEMA.refine($$ARGS)",
    language="typescript",
    rule_id="require-error-message",
    message="refine() must include error message in second argument",
    severity="error"
)
print(rule3)

# Rule 4: prefer-enum-over-literal-union - Use enum for literal unions
print_header("RULE 4: prefer-enum-over-literal-union", leading_newline=True)
rule4 = build_rule_impl(
    pattern="z.union([z.literal($LIT1), z.literal($LIT2)])",
    language="typescript",
    rule_id="prefer-enum-over-literal-union",
    message="Use z.enum() instead of union of literals",
    severity="warning"
)
print(rule4)

# Rule 5: no-optional-and-default-together
print_header("RULE 5: no-optional-and-default-together", leading_newline=True)
rule5 = build_rule_impl(
    pattern="$SCHEMA.optional().default($VAL)",
    language="typescript",
    rule_id="no-optional-and-default-together",
    message="Don't use both .optional() and .default() - just use .default()",
    severity="error"
)
print(rule5)

print_header("All rules generated successfully!", leading_newline=True)
