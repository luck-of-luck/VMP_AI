#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
OUT="${2:-$ROOT/docs/repomix/gitlog-top20.txt}"

N=20
COMMITS=200

mkdir -p "$(dirname "$OUT")"

# Get Top-N tracked files by blob size (bytes), macOS-safe
TOP_FILES=()
while IFS= read -r f; do
  [[ -n "$f" ]] && TOP_FILES+=("$f")
done < <(
  git -C "$ROOT" ls-files -z \
  | while IFS= read -r -d '' f; do
      sz="$(git -C "$ROOT" cat-file -s ":$f" 2>/dev/null || echo 0)"
      printf '%s\t%s\n' "$sz" "$f"
    done \
  | sort -nr \
  | head -n "$N" \
  | cut -f2-
)

# Log: commit header + filenames (no statuses), only for those Top-N files
git -C "$ROOT" log -n "$COMMITS" \
  --date=short \
  --pretty='format:%h %ad %s' \
  --name-only \
  -- "${TOP_FILES[@]}" \
| awk '
    NF==0 { print ""; next }
    /^[0-9a-f]{7,40} / { print; next }
    { print "  " $0 }
  ' > "$OUT"

echo "Wrote: $OUT"
