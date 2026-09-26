#!/bin/bash
# Build the Story Bible pages (dist/story-bible.html, dist/story-bible.json)
# from ai/story-bible-cache.json. A missing cache renders the placeholder page
# (success); an invalid cache or a missing core artifact fails the build.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Building Story Bible ==="
nanoif build story-bible --repo "$PROJECT_DIR"
echo "=== Story Bible Build Complete ==="
