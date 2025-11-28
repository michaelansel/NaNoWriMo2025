#!/bin/bash
# Build Writing Metrics & Statistics
# Generates metrics.html for GitHub Pages deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
METRICS_SCRIPT="$SCRIPT_DIR/calculate-metrics.py"
TEMPLATE_FILE="$PROJECT_DIR/formats/metrics/template.html.jinja2"
OUTPUT_FILE="$DIST_DIR/metrics.html"

# Create dist directory if it doesn't exist
mkdir -p "$DIST_DIR"

echo "=== Building Writing Metrics ==="
echo "Project: $PROJECT_DIR"
echo "Output: $OUTPUT_FILE"
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

# Step 1: Generate metrics JSON
echo "[1/2] Calculating metrics..."
METRICS_JSON=$(python3 "$METRICS_SCRIPT" --src "$PROJECT_DIR/src" --json --top 10)

if [ $? -ne 0 ]; then
    echo "Error: Failed to calculate metrics"
    exit 1
fi

echo "✓ Metrics calculated"

# Step 2: Render HTML template
echo ""
echo "[2/2] Generating HTML..."

python3 -c "
import json
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Load metrics JSON
metrics = json.loads('''$METRICS_JSON''')

# Add story name to metrics
metrics['story_name'] = 'NaNoWriMo 2025'

# Load and render template
env = Environment(loader=FileSystemLoader('$PROJECT_DIR/formats/metrics'))
template = env.get_template('template.html.jinja2')
html = template.render(metrics=metrics)

# Write output
with open('$OUTPUT_FILE', 'w') as f:
    f.write(html)
"

if [ $? -ne 0 ]; then
    echo "Error: Failed to generate HTML"
    exit 1
fi

echo "✓ HTML generated"

echo ""
echo "=== Build Complete ==="
echo "Output file: $OUTPUT_FILE"
echo ""
echo "Next steps:"
echo "  1. Open metrics.html in a browser to review statistics"
echo "  2. Deploy to GitHub Pages (npm run deploy)"
