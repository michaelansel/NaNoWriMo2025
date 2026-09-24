#!/bin/bash
# Build Core Artifacts: compile the story once (paperthin) and parse it into
# lib/artifacts/ (story_graph.json, passages_deduplicated.json) plus the
# generated src/PathIdLookup.twee.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Story formats live in the repository root (the workflow unpacks them there).
export TWEEGO_PATH="${TWEEGO_PATH:-$PROJECT_DIR/storyformats}"

echo "=== Building Core Artifacts ==="
mkdir -p "$PROJECT_DIR/dist"
# PathIdLookup.twee is generated from the graph; a stale copy must not be compiled into it.
rm -f "$PROJECT_DIR/src/PathIdLookup.twee"

echo "Step 1/2: Compiling paperthin HTML..."
tweego "$PROJECT_DIR/src" -o "$PROJECT_DIR/dist/story-paperthin.html" --format=paperthin-1

echo "Step 2/2: Parsing story structure and generating path ID lookup..."
nanoif build core --repo "$PROJECT_DIR"
echo "=== Core Artifacts Complete ==="
