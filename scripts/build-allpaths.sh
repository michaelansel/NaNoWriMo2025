#!/bin/bash
# Build the AllPaths outputs under dist/ from lib/artifacts/story_graph.json.
#
# Categorization env contract (set by the workflow on pull requests):
#   GITHUB_MERGE_BASE  ref to categorize against; required when GITHUB_BASE_REF is set
#   Neither set        local build, categorized against HEAD

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Building AllPaths Format ==="
nanoif build allpaths --repo "$PROJECT_DIR"
echo "=== Build Complete ==="
