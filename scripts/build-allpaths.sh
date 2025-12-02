#!/bin/bash
# Build AllPaths format output
# Generates all possible story paths for AI-based continuity checking
# Now reads from core library artifacts (story_graph.json)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
FORMAT_DIR="$PROJECT_DIR/formats/allpaths"

# Create dist directory if it doesn't exist
mkdir -p "$DIST_DIR"

echo "=== Building AllPaths Format ==="
echo "Project: $PROJECT_DIR"
echo "Output: $DIST_DIR"
echo ""

# Generate all paths from core library artifacts
echo "Generating all paths from core artifacts..."

if command -v python3 &> /dev/null; then
    python3 "$FORMAT_DIR/generator.py" "$DIST_DIR"
    echo "✓ Paths generated"
else
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

echo ""
echo "=== Build Complete ==="
echo "Output files:"
echo "  - $DIST_DIR/allpaths.html (browse all paths)"
echo "  - $DIST_DIR/allpaths-clean/*.txt (clean prose for public)"
echo "  - $DIST_DIR/allpaths-metadata/*.txt (with metadata for AI)"
echo "  - $PROJECT_DIR/allpaths-validation-status.json (validation tracking)"
echo ""
echo "Next steps:"
echo "  1. Open allpaths.html in a browser to review all paths"
echo "  2. Feed text files to AI model for continuity checking"
echo "  3. Mark validated paths in the cache file"
