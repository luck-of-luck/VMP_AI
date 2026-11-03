# Directory Structure

```
src/
  ast_grep_mcp/
    core/
      __init__.py (17 lines)
      cache.py (103 lines)
      config.py (137 lines)
      exceptions.py (48 lines)
      executor.py (292 lines)
      logging.py (31 lines)
      sentry.py (36 lines)
      usage_tracking.py (412 lines)
    features/
      complexity/
        __init__.py (21 lines)
        tools.py (350 lines)
      condense/
        __init__.py (24 lines)
        tools.py (101 lines)
      cross_language/
        __init__.py (11 lines)
        tools.py (362 lines)
      deduplication/
        __init__.py (28 lines)
        tools.py (143 lines)
      documentation/
        __init__.py (11 lines)
        tools.py (349 lines)
      quality/
        __init__.py (26 lines)
        tools.py (518 lines)
      refactoring/
        __init__.py (11 lines)
        tools.py (177 lines)
      rewrite/
        __init__.py (9 lines)
        tools.py (64 lines)
      schema/
        __init__.py (7 lines)
        tools.py (250 lines)
      search/
        __init__.py (7 lines)
        tools.py (492 lines)
      __init__.py (0 lines)
    models/
      __init__.py (21 lines)
      base.py (4 lines)
      complexity.py (46 lines)
      condense.py (32 lines)
      config.py (38 lines)
      cross_language.py (384 lines)
      deduplication.py (380 lines)
      documentation.py (405 lines)
      orphan.py (195 lines)
      pattern_debug.py (136 lines)
      pattern_develop.py (107 lines)
      refactoring.py (186 lines)
      schema_enhancement.py (117 lines)
      standards.py (310 lines)
    server/
      __init__.py (3 lines)
      registry.py (24 lines)
      runner.py (18 lines)
    utils/
      __init__.py (35 lines)
    __init__.py (0 lines)
    constants.py (726 lines)
CLAUDE.md (72 lines)
main.py (5 lines)
pyproject.toml (122 lines)
```