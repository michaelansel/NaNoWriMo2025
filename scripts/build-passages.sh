#!/bin/bash
# Build the passage index page (dist/passages.html) from lib/artifacts/story_graph.json.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Building Passage Index ==="
nanoif build passages --repo "$PROJECT_DIR"
echo "=== Build Complete ==="
