#!/bin/bash
# Build the writing metrics page (dist/metrics.html) from lib/artifacts/story_graph.json.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Building Writing Metrics ==="
nanoif build metrics --repo "$PROJECT_DIR" --top 10
echo "=== Build Complete ==="
