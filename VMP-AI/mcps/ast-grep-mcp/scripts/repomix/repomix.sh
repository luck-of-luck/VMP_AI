#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:?Usage: $0 <root_dir> <output_file>}"
OUTPUT_FILE="${2:?Usage: $0 <root_dir> <output_file>}"

CONFIG="$(cd "$(dirname "$0")" && pwd)/repomix-lossless.config.json"

FORCE_COLOR=0 NO_COLOR=1 timeout 120 \
npx repomix "$ROOT" -c "$CONFIG" -o "$OUTPUT_FILE" >/dev/null 2>&1