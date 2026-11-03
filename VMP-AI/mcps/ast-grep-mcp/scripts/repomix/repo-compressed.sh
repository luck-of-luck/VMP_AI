#!/usr/bin/env bash
# Runs repomix --compress and writes docs/repomix/repo-compressed.xml
set -euo pipefail

ROOT="${1:?Usage: $0 <root_dir> <output_file>}"
OUTPUT_FILE="${2:?Usage: $0 <root_dir> <output_file>}"

CONFIG="$(cd "$(dirname "$0")" && pwd)/repomix.config.json"

FORCE_COLOR=0 NO_COLOR=1 timeout 120 \
npx repomix "$ROOT" -c "$CONFIG" --compress -o "$OUTPUT_FILE" >/dev/null 2>&1
