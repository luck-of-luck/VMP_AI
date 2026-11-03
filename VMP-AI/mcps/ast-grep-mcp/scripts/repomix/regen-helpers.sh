#!/usr/bin/env bash
# Shared helpers for repomix-regen.sh

# Set up repo root and project dir
export ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PROJECT_DIR="$(basename "$ROOT")"

run_step() {
  local description="$1"; local script="$2"; shift 2
  echo "$description"
  bash "$script" "$@"
  echo "Success!"
  echo
}

print_artifact() {
  local file_path="$1"
  local display_name="$2"

  if [[ -f "$file_path" ]]; then
    chars=$(wc -c < "$file_path" | tr -d ' ')
    tokens=$((chars / 4))
    echo " - $display_name (~$tokens tokens, $chars chars)"
  else
    echo " - $display_name (missing)"
  fi
}
