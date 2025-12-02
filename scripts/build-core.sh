#!/bin/bash
# Build Core Artifacts
# Generates core library artifacts from Tweego HTML

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Building Core Artifacts ==="
echo

# Generate paperthin HTML for parsing
echo "Step 1/4: Generating paperthin HTML..."
tweego "$PROJECT_DIR/src" -o "$PROJECT_DIR/dist/story-paperthin.html" --format=paperthin-1.0.0
echo "✓ Generated: dist/story-paperthin.html"
echo

# Parse story structure
echo "Step 2/4: Parsing story structure..."
python3 "$PROJECT_DIR/lib/core/parse_story.py" \
  "$PROJECT_DIR/dist/story-paperthin.html" \
  "$PROJECT_DIR/lib/artifacts/story_graph.json"
echo

# Extract passages
echo "Step 3/4: Extracting passages..."
python3 "$PROJECT_DIR/lib/core/extract_passages.py" \
  "$PROJECT_DIR/lib/artifacts/story_graph.json" \
  "$PROJECT_DIR/lib/artifacts/passages_deduplicated.json"
echo

# Build mappings
echo "Step 4/4: Building passage mappings..."
python3 "$PROJECT_DIR/lib/core/build_mappings.py" \
  "$PROJECT_DIR/lib/artifacts/story_graph.json" \
  "$PROJECT_DIR/lib/artifacts/passage_mapping.json" \
  --src "$PROJECT_DIR/src"
echo

echo "=== Core Artifacts Complete ==="
echo "Generated:"
echo "  - lib/artifacts/story_graph.json"
echo "  - lib/artifacts/passages_deduplicated.json"
echo "  - lib/artifacts/passage_mapping.json"
echo
