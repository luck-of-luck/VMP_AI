#!/usr/bin/env bash
# Runs repomix --token-count-tree and writes the "📈 Top 5..." section onward to OUTPUT_FILE
set -euo pipefail

ROOT="${1:?Usage: $0 <root_dir> <output_file>}"
OUTPUT_FILE="${2:?Usage: $0 <root_dir> <output_file>}"

CONFIG="$(cd "$(dirname "$0")" && pwd)/repomix.config.json"

FORCE_COLOR=0 NO_COLOR=1 npx repomix "$ROOT" -c "$CONFIG" --token-count-tree --no-files --no-file-summary 2>&1 \
  | tr -d '\r' \
  | sed -E 's/\x1B\[[0-9;]*[A-Za-z]//g' \
  | awk 'BEGIN{keep=0} /^🔢 Token Count Tree:/{keep=1} /^🔎 Security Check:/{keep=0} keep' \
  > "$OUTPUT_FILE"
