#!/bin/bash
# Build Core Artifacts
# Compiles the story once (paperthin) and parses it into the JSON artifacts
# that the other formats consume, plus the PathIdLookup script passage.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Story formats live in the repository root (the workflow unpacks them there).
export TWEEGO_PATH="${TWEEGO_PATH:-$PROJECT_DIR/storyformats}"

echo "=== Building Core Artifacts ==="
echo

mkdir -p "$PROJECT_DIR/dist" "$PROJECT_DIR/lib/artifacts"

# PathIdLookup.twee is generated below; a stale copy must not be compiled
# into the graph it is generated from.
rm -f "$PROJECT_DIR/src/PathIdLookup.twee"

echo "Step 1/2: Compiling paperthin HTML..."
tweego "$PROJECT_DIR/src" -o "$PROJECT_DIR/dist/story-paperthin.html" --format=paperthin-1
echo "Generated: dist/story-paperthin.html"
echo

echo "Step 2/2: Parsing story structure and generating path ID lookup..."
nanoif build core \
  --html "$PROJECT_DIR/dist/story-paperthin.html" \
  --src "$PROJECT_DIR/src" \
  --out "$PROJECT_DIR/lib/artifacts" \
  --lookup "$PROJECT_DIR/src/PathIdLookup.twee"
echo

echo "=== Core Artifacts Complete ==="
echo "Generated:"
echo "  - lib/artifacts/story_graph.json"
echo "  - lib/artifacts/passages_deduplicated.json"
echo "  - src/PathIdLookup.twee (path ID runtime lookup)"
echo
