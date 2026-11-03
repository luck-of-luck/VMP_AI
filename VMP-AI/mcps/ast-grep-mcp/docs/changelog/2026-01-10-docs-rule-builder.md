# 2026-01-10: Documentation & Rule Builder Tools + Warning System

Based on the [ast-grep Prompting Guide](https://ast-grep.github.io/advanced/prompting.html).

## Added

- `get_ast_grep_docs` — on-demand documentation retrieval (topics: pattern, rules, relational, metavariables, workflow, all)
- `build_rule` — YAML rule builder with automatic `stopBy: end` on relational rules
- `get_pattern_examples` — common patterns by language and category
- Automatic warning detection in `find_code_by_rule` for missing `stopBy` and lowercase metavariables
- Enhanced tool descriptions with pattern syntax quick reference
- 24+ new tests in `tests/unit/test_docs_and_rule_builder.py`
