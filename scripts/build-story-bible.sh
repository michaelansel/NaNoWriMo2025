#!/bin/bash
# Build Story Bible output
# Generates human and machine-readable story bible from AllPaths format

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
FORMAT_DIR="$PROJECT_DIR/formats/story-bible"

echo "=== Building Story Bible ==="

# Check prerequisites
if [ ! -d "$DIST_DIR/allpaths-metadata" ]; then
    echo "Error: AllPaths output not found. Run 'npm run build:allpaths' first."
    exit 1
fi

# Generate Story Bible
echo "Generating Story Bible..."

if command -v python3 &> /dev/null; then
    # Run generator with error handling
    if python3 "$FORMAT_DIR/generator.py" "$DIST_DIR"; then
        echo "✓ Story Bible generated successfully"
        echo "  - HTML: $DIST_DIR/story-bible.html"
        echo "  - JSON: $DIST_DIR/story-bible.json"
    else
        echo "⚠️  Story Bible generation failed (non-blocking)"
        echo "  Build will continue without Story Bible"
        exit 0  # Exit 0 to not block the build
    fi
else
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

echo "=== Story Bible Build Complete ==="
