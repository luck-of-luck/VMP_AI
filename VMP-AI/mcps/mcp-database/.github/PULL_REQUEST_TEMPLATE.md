## What

<!-- What does this PR change and why? -->

## Checklist

- [ ] `make lint` passes clean
- [ ] `make test` passes (or `make test-unit` if the change has no adapter surface)
- [ ] New behavior covered with happy, sad and absurd cases
- [ ] New/changed tools: added to `VALID_ARGS` in `tests/e2e/test_tools_contract.py`, prefix semantics and MCP annotations declared, `docs/tools.md` updated
- [ ] Security invariants untouched (read tools never write, fail-closed validation, password redaction)
- [ ] No project version bump (releases go through the "Prepare release" workflow)
