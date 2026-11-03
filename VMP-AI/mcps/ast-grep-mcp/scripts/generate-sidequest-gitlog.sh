#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root (parent of scripts/)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMITS="${1:-200}"
DEFAULT_OUT="$REPO_ROOT/sidequest/docs/gitlog-sidequest.txt"
REPO_MIRROR_OUT="$REPO_ROOT/docs/repomix/gitlog-sidequest.txt"
OUT="${2:-"$DEFAULT_OUT"}"
MIRROR_OUT="${3:-"$REPO_MIRROR_OUT"}"
mkdir -p "$(dirname "$OUT")" "$(dirname "$MIRROR_OUT")"

TMP_OUT="$(mktemp)"
trap 'rm -f "$TMP_OUT"' EXIT

git -C "$REPO_ROOT" log -n "$COMMITS" \
  --date=short \
  --pretty='format:%h %ad %s' \
  --name-only \
  -- sidequest/ \
| awk '
    NF==0 { print ""; next }              # blank line between commits
    /^[0-9a-f]{7,40} / { print; next }    # commit header
    { print "  " $0 }                     # indent filenames
  ' > "$TMP_OUT"

cp "$TMP_OUT" "$OUT"

if [[ "$MIRROR_OUT" != "$OUT" ]]; then
  cp "$TMP_OUT" "$MIRROR_OUT"
  echo "Wrote: $OUT"
  echo "Wrote: $MIRROR_OUT"
else
  echo "Wrote: $OUT"
fi
