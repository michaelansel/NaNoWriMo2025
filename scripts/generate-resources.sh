#!/bin/bash
# Automatically generate Resource-Passage Names file
# Extracts all passage definitions and links from .twee files
# Groups links under their respective passages

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

    # Process the file to group links under passages
    awk '
    /^::/ {
        # Found a new passage
        # Print any accumulated links from previous passage
        if (current_passage != "") {
            for (i = 1; i <= link_count; i++) {
                print links[i]
            }
        }
        # Print the new passage
        print "  " $0
        current_passage = $0
        link_count = 0
        next
    }
    /\[\[/ {
        # Found a line with links, save it
        link_count++
        links[link_count] = "  " $0
    }
    END {
        # Print any remaining links from last passage
        if (current_passage != "") {
            for (i = 1; i <= link_count; i++) {
                print links[i]
            }
        }
    }
    ' "$file" >> "$temp_output"

    # Add blank line between files
    echo "" >> "$temp_output"
done

# Move temp file to final location
mv "$temp_output" "$output"

echo "Generated $output successfully"
