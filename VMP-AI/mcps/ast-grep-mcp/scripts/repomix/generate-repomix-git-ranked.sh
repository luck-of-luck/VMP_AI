#!/usr/bin/env bash
# Generate a repomix bundle ranked by file change frequency using git metadata.
# Output is restricted to files that appear in the selected commit window.
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
ROOT="${1:?Usage: $SCRIPT_NAME <root_dir> <output_file> [include_logs_count]}"
OUTPUT_FILE="${2:?Usage: $SCRIPT_NAME <root_dir> <output_file> [include_logs_count]}"
INCLUDE_LOGS_COUNT="${3:-200}"

# Preflight: required commands.
for cmd in jq npx git; do
  command -v "$cmd" >/dev/null 2>&1 \
    || { echo "$SCRIPT_NAME: required command not found: $cmd" >&2; exit 1; }
done

# Canonicalize ROOT and verify it is a git repository.
ROOT="$(cd "$ROOT" 2>/dev/null && pwd)" \
  || { echo "ROOT does not exist or is not accessible: ${1}" >&2; exit 1; }
if ! git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  echo "ROOT is not a git repository: $ROOT" >&2
  exit 1
fi

# Canonicalize OUTPUT_FILE to absolute path (M3).
OUTPUT_FILE="$(cd "$(dirname "$OUTPUT_FILE")" 2>/dev/null && pwd)/$(basename "$OUTPUT_FILE")" \
  || { echo "Cannot resolve output file path: ${2}" >&2; exit 1; }

# Validate output directory exists.
OUTPUT_DIR="$(dirname "$OUTPUT_FILE")"
if [[ ! -d "$OUTPUT_DIR" ]]; then
  echo "Output directory does not exist: $OUTPUT_DIR" >&2
  exit 1
fi

# Optional overrides via environment variables.
INCLUDE_DIFFS="${REPOMIX_INCLUDE_DIFFS:-true}"
INCLUDE_LOGS="${REPOMIX_INCLUDE_LOGS:-true}"
INCLUDE_FILES="${REPOMIX_INCLUDE_FILES:-false}"
SORT_BY_CHANGES_MAX_COMMITS="${REPOMIX_SORT_BY_CHANGES_MAX_COMMITS:-1000}"
TIMEOUT_SECONDS="${REPOMIX_TIMEOUT_SECONDS:-120}"
REPOMIX_LOG_TAIL_LINES="${REPOMIX_LOG_TAIL_LINES:-20}"

if ! [[ "$INCLUDE_LOGS_COUNT" =~ ^[0-9]+$ ]] || [[ "$INCLUDE_LOGS_COUNT" -lt 0 ]]; then
  echo "include_logs_count must be a non-negative integer: $INCLUDE_LOGS_COUNT" >&2
  exit 1
fi

if ! [[ "$SORT_BY_CHANGES_MAX_COMMITS" =~ ^[0-9]+$ ]] || [[ "$SORT_BY_CHANGES_MAX_COMMITS" -lt 1 ]]; then
  echo "REPOMIX_SORT_BY_CHANGES_MAX_COMMITS must be a positive integer: $SORT_BY_CHANGES_MAX_COMMITS" >&2
  exit 1
fi

if [[ "$INCLUDE_DIFFS" != "true" && "$INCLUDE_DIFFS" != "false" ]]; then
  echo "REPOMIX_INCLUDE_DIFFS must be true|false: $INCLUDE_DIFFS" >&2
  exit 1
fi

if [[ "$INCLUDE_LOGS" != "true" && "$INCLUDE_LOGS" != "false" ]]; then
  echo "REPOMIX_INCLUDE_LOGS must be true|false: $INCLUDE_LOGS" >&2
  exit 1
fi

if [[ "$INCLUDE_FILES" != "true" && "$INCLUDE_FILES" != "false" ]]; then
  echo "REPOMIX_INCLUDE_FILES must be true|false: $INCLUDE_FILES" >&2
  exit 1
fi

# Cross-field warning after boolean validation (M2).
if [[ "$INCLUDE_LOGS_COUNT" -eq 0 && "$INCLUDE_LOGS" == "true" ]]; then
  echo "Warning: INCLUDE_LOGS=true but include_logs_count=0; no logs will be included" >&2
fi

# Create all temp files together so the trap covers them all (H2).
TMP_CONFIG="$(mktemp "${TMPDIR:-/tmp}/repomix-git-ranked.XXXXXX.json")"
TMP_FILES="$(mktemp "${TMPDIR:-/tmp}/repomix-git-ranked-files.XXXXXX")"
TMP_LOG="$(mktemp "${TMPDIR:-/tmp}/repomix-run.XXXXXX.log")"
trap 'rm -f "$TMP_CONFIG" "$TMP_FILES" "$TMP_LOG"' EXIT INT TERM

# Ignore patterns sourced from base repomix config (full set: generated
# bundles, docs, tests, results, media, secrets, etc.).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLE_IGNORE_PATTERNS_FILE="$SCRIPT_DIR/repomix.config.json"
if [[ -f "$BUNDLE_IGNORE_PATTERNS_FILE" ]]; then
  BUNDLE_IGNORE_PATTERNS_JSON="$(
    jq -c '[.ignore.customPatterns[]?] | unique' "$BUNDLE_IGNORE_PATTERNS_FILE" 2>/dev/null
  )" || {
    echo "Warning: $BUNDLE_IGNORE_PATTERNS_FILE exists but is not valid JSON; using empty ignore patterns" >&2
    BUNDLE_IGNORE_PATTERNS_JSON='[]'
  }
else
  BUNDLE_IGNORE_PATTERNS_JSON='[]'
fi

# Generated artifacts that should never be re-ingested into ranked bundles.
# Override via REPOMIX_EXCLUDE_ARTIFACTS (newline-separated glob patterns).
# Patterns are intentionally interpreted as globs by case.
# Do not pass untrusted input in REPOMIX_EXCLUDE_ARTIFACTS.
EXCLUDE_ARTIFACTS="${REPOMIX_EXCLUDE_ARTIFACTS:-docs/repomix/*
sidequest/docs/gitlog-sidequest.txt}"

is_generated_bundle_artifact() {
  local rel_path="$1"
  local pattern
  while IFS= read -r pattern; do
    [[ -z "$pattern" ]] && continue
    # shellcheck disable=SC2254
    case "$rel_path" in
      $pattern) return 0 ;;
    esac
  done <<< "$EXCLUDE_ARTIFACTS"
  return 1
}

# Build include list from files touched in the selected commit window.
# Use sort -u for deduplication (compatible with bash 3.x on macOS).
git -C "$ROOT" -c core.quotePath=false log --name-only --pretty=format: -n "$SORT_BY_CHANGES_MAX_COMMITS" \
  | grep -v '^$' \
  | sort -u \
  | while IFS= read -r rel_path; do
      if is_generated_bundle_artifact "$rel_path"; then
        continue
      fi
      if [[ -f "$ROOT/$rel_path" ]]; then
        printf '%s\n' "$rel_path"
      fi
    done > "$TMP_FILES"

if [[ ! -s "$TMP_FILES" ]]; then
  echo "No existing files found in the selected commit window." >&2
  exit 1
fi

include_files_json="$(jq -R -s 'split("\n") | map(select(length > 0))' "$TMP_FILES")"

jq -n \
  --argjson includeFiles "$include_files_json" \
  --argjson bundleIgnorePatterns "$BUNDLE_IGNORE_PATTERNS_JSON" \
  --argjson includeLogsCount "$INCLUDE_LOGS_COUNT" \
  --argjson sortByChangesMaxCommits "$SORT_BY_CHANGES_MAX_COMMITS" \
  --arg includeDiffs "$INCLUDE_DIFFS" \
  --arg includeLogs "$INCLUDE_LOGS" \
  --arg includeFiles "$INCLUDE_FILES" '
{
  "$schema": "https://repomix.com/schemas/latest/schema.json",
  "output": {
    "style": "xml",
    "parsableStyle": true,
    "removeComments": true,
    "removeEmptyLines": true,
    "fileSummary": false,
    "directoryStructure": false,
    "files": ($includeFiles == "true"),
    "includeEmptyDirectories": false,
    "git": {
      "sortByChanges": true,
      "sortByChangesMaxCommits": $sortByChangesMaxCommits,
      "includeDiffs": ($includeDiffs == "true"),
      "includeLogs": ($includeLogs == "true"),
      "includeLogsCount": $includeLogsCount
    }
  },
  "ignore": {
    "useGitignore": true,
    "useDotIgnore": true,
    "useDefaultPatterns": true,
    "customPatterns": $bundleIgnorePatterns
  },
  "include": $includeFiles
}' > "$TMP_CONFIG"

# Capture exit code explicitly; $? is unreliable inside `if !` (H1).
REPOMIX_EXIT=0
FORCE_COLOR=0 NO_COLOR=1 timeout "$TIMEOUT_SECONDS" \
  npx repomix "$ROOT" -c "$TMP_CONFIG" -o "$OUTPUT_FILE" >"$TMP_LOG" 2>&1 \
  || REPOMIX_EXIT=$?
if [[ $REPOMIX_EXIT -ne 0 ]]; then
  echo "repomix failed (exit $REPOMIX_EXIT). Last output:" >&2
  tail -"$REPOMIX_LOG_TAIL_LINES" "$TMP_LOG" >&2
  exit 1
fi
