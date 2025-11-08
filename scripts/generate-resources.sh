#!/bin/bash
# Automatically generate Resource-Passage Names file
# Extracts all passage definitions and links from .twee files

output="Resource-Passage Names"
temp_output="${output}.tmp"

# Clear temp file
> "$temp_output"

# Process each .twee file in src/, sorted alphabetically by basename
for file in src/*.twee; do
    [ -f "$file" ] || continue
    basename=$(basename "$file")

    # Print filename
    echo "$basename" >> "$temp_output"

    # Extract passage definitions (lines starting with ::)
    grep "^::" "$file" | sed 's/^/  /' >> "$temp_output" 2>/dev/null || true

    # Extract lines containing links (lines with [[)
    grep "\[\[" "$file" | grep -v "^::" | sed 's/^/  /' >> "$temp_output" 2>/dev/null || true

    # Add blank line between files
    echo "" >> "$temp_output"
done

# Move temp file to final location
mv "$temp_output" "$output"

echo "Generated $output successfully"
