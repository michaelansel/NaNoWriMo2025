#!/bin/bash
# Build AllPaths format output
# Generates all possible story paths for AI-based continuity checking

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

# Step 1: Compile story with Paperthin format (just to get the story data)
echo "[1/2] Compiling story with Tweego..."
TEMP_FILE="$DIST_DIR/allpaths-temp.html"

if command -v tweego &> /dev/null; then
    # Use paperthin format as it's simple and just outputs the story data
    tweego src -o "$TEMP_FILE" -f paperthin-1
    echo "✓ Story compiled"
else
    echo "Error: tweego not found. Please install tweego first."
    exit 1
fi

# Step 2: Generate all paths with Python
echo ""
echo "[2/2] Generating all paths..."

if command -v python3 &> /dev/null; then
    python3 "$FORMAT_DIR/generator.py" "$TEMP_FILE" "$DIST_DIR"
    echo "✓ Paths generated"
else
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

# Clean up temp file
rm -f "$TEMP_FILE"

echo ""
echo "=== Build Complete ==="
echo "Output files:"
echo "  - $DIST_DIR/allpaths.html (browse all paths)"
echo "  - $DIST_DIR/allpaths-text/*.txt (individual paths for AI)"
echo "  - $PROJECT_DIR/allpaths-validation-cache.json (validation tracking)"
echo ""
echo "Next steps:"
echo "  1. Open allpaths.html in a browser to review all paths"
echo "  2. Feed text files to AI model for continuity checking"
echo "  3. Mark validated paths in the cache file"
