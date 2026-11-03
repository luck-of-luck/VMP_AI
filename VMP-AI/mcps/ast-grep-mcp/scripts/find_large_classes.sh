#!/bin/bash
# Find all classes in AnalyticsBot and estimate their sizes

cd /Users/alyshialedlie/code/ISPublicSites/AnalyticsBot

echo "=== Finding all TypeScript classes ==="
echo

find . -type f \( -name "*.ts" -o -name "*.tsx" \) \
  -not -path "*/node_modules/*" \
  -not -path "*/build/*" \
  -not -path "*/dist/*" \
  -exec grep -l "^class \|^export class " {} \; | while read file; do

  # Get class name and line number
  grep -n "^class \|^export class " "$file" | while IFS=: read linenum classdef; do
    # Extract class name
    classname=$(echo "$classdef" | sed -E 's/.*(class |export class )([A-Za-z0-9_]+).*/\2/')

    # Get total file lines
    total_lines=$(wc -l < "$file")

    # Estimate class size (simple heuristic: from class line to end of file)
    class_size=$((total_lines - linenum))

    # Count methods (functions inside the class)
    # This is a rough estimate
    method_count=$(sed -n "${linenum},\$p" "$file" | grep -c "^\s*\(async \)\?[a-zA-Z_][a-zA-Z0-9_]*\s*(")

    echo "$file:$linenum - $classname ($class_size lines, ~$method_count methods)"
  done
done | sort -t'(' -k2 -rn
