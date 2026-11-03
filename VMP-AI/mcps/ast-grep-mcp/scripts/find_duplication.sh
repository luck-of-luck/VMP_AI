#!/bin/bash
#
# Bash wrapper for the find_duplication tool
#
# Usage:
#   ./scripts/find_duplication.sh /path/to/project python
#   ./scripts/find_duplication.sh /path/to/project javascript class_definition 0.9
#   ./scripts/find_duplication.sh /path/to/project python function_definition 0.8 10 2000
#

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check if project folder is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <project_folder> <language> [construct_type] [min_similarity] [min_lines] [max_constructs]"
    echo ""
    echo "Examples:"
    echo "  $0 /path/to/project python"
    echo "  $0 /path/to/project javascript class_definition"
    echo "  $0 /path/to/project python function_definition 0.9"
    echo "  $0 /path/to/project python function_definition 0.8 10"
    echo "  $0 /path/to/project python function_definition 0.8 5 2000"
    exit 1
fi

# Get arguments
PROJECT_FOLDER="$1"
LANGUAGE="${2:-python}"
CONSTRUCT_TYPE="${3:-function_definition}"
MIN_SIMILARITY="${4:-0.8}"
MIN_LINES="${5:-5}"
MAX_CONSTRUCTS="${6:-1000}"

# Check if project folder exists
if [ ! -d "$PROJECT_FOLDER" ]; then
    echo "Error: Project folder does not exist: $PROJECT_FOLDER"
    exit 1
fi

# Run the Python script using uv
cd "$PROJECT_ROOT"
uv run python scripts/find_duplication.py "$PROJECT_FOLDER" \
    --language "$LANGUAGE" \
    --construct-type "$CONSTRUCT_TYPE" \
    --min-similarity "$MIN_SIMILARITY" \
    --min-lines "$MIN_LINES" \
    --max-constructs "$MAX_CONSTRUCTS"
