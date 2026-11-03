#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

TEST_TARGETS=(
  "sidequest/pipeline-core"
  "sidequest/pipeline-runners/test_collect_git_activity.py"
)

resolve_python() {
  local candidate="$1"
  if [[ -z "$candidate" ]]; then
    return 1
  fi

  if [[ "$candidate" == */* ]]; then
    [[ -x "$candidate" ]] || return 1
    printf '%s\n' "$candidate"
    return 0
  fi

  command -v "$candidate" 2>/dev/null || return 1
}

can_run_tests() {
  local python_bin="$1"
  "$python_bin" -c "import pytest, pydantic" >/dev/null 2>&1
}

declare -a CANDIDATES=()
if [[ -n "${PYTEST_PYTHON:-}" ]]; then
  CANDIDATES+=("$PYTEST_PYTHON")
fi

CANDIDATES+=(
  "$ROOT/venv/bin/python"
  "python3"
  "python"
  "$HOME/.pyenv/versions/3.13.7/bin/python"
  "/Users/alyshialedlie/code-env/python/pyenv/versions/3.13.7/bin/python"
)

declare -a UNIQUE_BINS=()
for candidate in "${CANDIDATES[@]}"; do
  python_bin="$(resolve_python "$candidate" || true)"
  [[ -n "${python_bin:-}" ]] || continue
  already_seen=false
  for seen_bin in "${UNIQUE_BINS[@]-}"; do
    if [[ "$seen_bin" == "$python_bin" ]]; then
      already_seen=true
      break
    fi
  done
  if [[ "$already_seen" == true ]]; then
    continue
  fi
  UNIQUE_BINS+=("$python_bin")

  if can_run_tests "$python_bin"; then
    echo "Using Python test runner: $python_bin"
    cd "$ROOT"
    PYTHONNOUSERSITE=1 "$python_bin" -m pytest -q "${TEST_TARGETS[@]}" "$@"
    exit 0
  fi
done

echo "No Python interpreter with both pytest and pydantic was found." >&2
echo "Set PYTEST_PYTHON=/path/to/python and retry." >&2
exit 1
