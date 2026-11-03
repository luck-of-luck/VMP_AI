# 2025-12-02 through 2025-12-04: Dedup Phase 5 & Modular Migration

## Added (2025-12-02)

- Implemented MinHash + LSH for O(n) similarity detection (f62b036)
- Implemented hybrid two-stage similarity pipeline (a8f51d0)
- Added SequenceMatcher fallback for small code blocks (fbc7b71)
- Implemented Phase 5 CodeBERT semantic similarity (58a13cd)
- Added regression and hybrid similarity tests (a6c55a6)
- Added fallback and performance tests (8784da3)

## Changed (2025-12-03)

- Registered `detect_orphans` tool and reduced complexity (0a3045b)
- Resolved all ruff and mypy errors across 14 files (010052b)
- Resolved Protocol and Union type mismatches in dedup generator (0e370ed)
- Added Callable type annotations to lambda dictionaries in dedup analyzer (41dcb51)
- Fixed ruff violations for SIM115 and B007 (f920615)

## Changed (2025-12-04)

- Migrated deduplication functions to modular architecture (9284084)
- Migrated integration tests to modular imports (e22d244)
- Migrated unit tests from main.py stubs to modular imports (fd0c16f)
- Updated cache fixtures to use modular imports (c1158f1)
- Updated test fixtures to use modular imports (2166889)
