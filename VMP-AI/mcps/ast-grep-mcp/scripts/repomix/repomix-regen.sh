#!/usr/bin/env bash
# Wrapper: generates token tree + compressed repomix output
set -euo pipefail

# shellcheck source=regen-helpers.sh
source "$(dirname "$0")/regen-helpers.sh"

# basenames (suffixed _BASE to avoid shadowing)
TREE_BASE="token-tree"
COMPRESSED_BASE="repo-compressed"
LOSSLESS_BASE="repomix"
DOCS_ONLY_BASE="repomix-docs"
GIT_RANKED_BASE="repomix-git-ranked"
GIT_TOP_20_BASE="gitlog-top20"

# input/output directories
INPUT_PATH="scripts/repomix"
OUTPUT_PATH="docs/repomix"

# output absolute filepaths
export OUT_DIR="$ROOT/$OUTPUT_PATH"
TOKEN_TREE_FILE="$OUT_DIR/$TREE_BASE.txt"
COMPRESSED_REPO_FILE="$OUT_DIR/$COMPRESSED_BASE.xml"
LOSSLESS_REPO_FILE="$OUT_DIR/$LOSSLESS_BASE.xml"
DOCS_ONLY_REPO_FILE="$OUT_DIR/$DOCS_ONLY_BASE.xml"
GIT_RANKED_REPO_FILE="$OUT_DIR/$GIT_RANKED_BASE.xml"
GITLOG_TOP_FILE="$OUT_DIR/$GIT_TOP_20_BASE.txt"

# input absolute filepaths
export INPUT_DIR="$ROOT/$INPUT_PATH"
TOKEN_TREE_SCRIPT="$INPUT_DIR/$TREE_BASE.sh"
COMPRESS_SCRIPT="$INPUT_DIR/$COMPRESSED_BASE.sh"
LOSSLESS_SCRIPT="$INPUT_DIR/$LOSSLESS_BASE.sh"
DOCS_ONLY_SCRIPT="$INPUT_DIR/generate-repomix-docs.sh"
GIT_RANKED_SCRIPT="$INPUT_DIR/generate-repomix-git-ranked.sh"
GITLOG_TOP_SCRIPT="$INPUT_DIR/generate-diff-summary.sh"
GIT_RANKED_INCLUDE_LOGS_COUNT="${REPOMIX_GIT_RANKED_INCLUDE_LOGS_COUNT:-200}"

# relative filepaths (for display)
TOKEN_TREE_REL="$OUTPUT_PATH/$TREE_BASE.txt"
COMPRESSED_REL="$OUTPUT_PATH/$COMPRESSED_BASE.xml"
LOSSLESS_REL="$OUTPUT_PATH/$LOSSLESS_BASE.xml"
DOCS_ONLY_REL="$OUTPUT_PATH/$DOCS_ONLY_BASE.xml"
GIT_RANKED_REL="$OUTPUT_PATH/$GIT_RANKED_BASE.xml"
GITLOG_TOP_REL="$OUTPUT_PATH/$GIT_TOP_20_BASE.txt"

# --- main ---

echo "Preparing output directory..."
mkdir -p "$OUT_DIR"

# delete only the artifacts this wrapper regenerates
rm -f \
  "$TOKEN_TREE_FILE" \
  "$COMPRESSED_REPO_FILE" \
  "$LOSSLESS_REPO_FILE" \
  "$DOCS_ONLY_REPO_FILE" \
  "$GIT_RANKED_REPO_FILE" \
  "$GITLOG_TOP_FILE"

run_step "Generating token count tree for $PROJECT_DIR at $TOKEN_TREE_REL" \
  "$TOKEN_TREE_SCRIPT" "$ROOT" "$TOKEN_TREE_FILE"

run_step "Generating compressed repomix file for $PROJECT_DIR at $COMPRESSED_REL" \
  "$COMPRESS_SCRIPT" "$ROOT" "$COMPRESSED_REPO_FILE"

run_step "Generating repomix file for $PROJECT_DIR at $LOSSLESS_REL" \
  "$LOSSLESS_SCRIPT" "$ROOT" "$LOSSLESS_REPO_FILE"

run_step "Generating docs-only repomix file for $PROJECT_DIR at $DOCS_ONLY_REL" \
  "$DOCS_ONLY_SCRIPT" "$ROOT" "$DOCS_ONLY_REPO_FILE"

run_step "Generating git-ranked repomix file for $PROJECT_DIR at $GIT_RANKED_REL" \
  "$GIT_RANKED_SCRIPT" "$ROOT" "$GIT_RANKED_REPO_FILE" "$GIT_RANKED_INCLUDE_LOGS_COUNT"

run_step "Generating top-file git history for $PROJECT_DIR at $GITLOG_TOP_REL" \
  "$GITLOG_TOP_SCRIPT" "$ROOT" "$GITLOG_TOP_FILE"

echo "Artifacts:"
print_artifact "$TOKEN_TREE_FILE" "$TOKEN_TREE_REL"
print_artifact "$COMPRESSED_REPO_FILE" "$COMPRESSED_REL"
print_artifact "$LOSSLESS_REPO_FILE" "$LOSSLESS_REL"
print_artifact "$DOCS_ONLY_REPO_FILE" "$DOCS_ONLY_REL"
print_artifact "$GIT_RANKED_REPO_FILE" "$GIT_RANKED_REL"
print_artifact "$GITLOG_TOP_FILE" "$GITLOG_TOP_REL"
