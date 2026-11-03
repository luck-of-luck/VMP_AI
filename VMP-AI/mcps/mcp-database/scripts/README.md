# scripts/

Standalone development and build scripts. Run from the repo root; never imported by `src/` or `tests/`.

| Script | What it does |
|--------|--------------|
| `bin_entry.py` | PyInstaller entrypoint for `make bin` |
| `build_binary.py` | Single source of truth for the PyInstaller flags (bundles every driver); called by `make bin` and the CI `binaries` job |
| `seed/` | Deterministic sample data for the playground databases (`make seed`; `docs/evals/` depends on it) |
| `run_evals.py` | Runs a `docs/evals/` question file through headless `claude -p` sessions (one per question, single stdio server) and writes a pass/fail report (`make evals`) |
