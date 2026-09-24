#!/bin/bash
# Build AllPaths format output
# Enumerates every story path from the core artifacts (story_graph.json) and
# writes the text files, browser page and JSON indexes under dist/.
#
# Categorization env contract (set by the workflow on pull requests):
#   GITHUB_MERGE_BASE  ref to categorize against; required when GITHUB_BASE_REF is set
#   Neither set        local build, categorized against HEAD

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_DIR/dist"

echo "=== Building AllPaths Format ==="
echo "Project: $PROJECT_DIR"
echo "Output: $DIST_DIR"
echo ""

nanoif build allpaths \
  --repo "$PROJECT_DIR" \
  --src "$PROJECT_DIR/src" \
  --story-graph "$PROJECT_DIR/lib/artifacts/story_graph.json" \
  --out "$DIST_DIR"

echo ""
echo "=== Build Complete ==="
echo "Output files:"
echo "  - $DIST_DIR/allpaths.html (browse all paths)"
echo "  - $DIST_DIR/allpaths-clean/*.txt (clean prose for public)"
echo "  - $DIST_DIR/allpaths-metadata/*.txt (with metadata for AI)"
echo "  - $DIST_DIR/allpaths-raw/*.txt (Twee markup intact, for choice checks)"
echo "  - $DIST_DIR/allpaths-index.json (paths, categories, files, dates)"
echo "  - $DIST_DIR/changes.json (passages new or changed vs. the base)"
