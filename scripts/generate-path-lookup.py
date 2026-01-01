#!/usr/bin/env python3
"""
Generate Path ID Lookup for Harlowe Runtime

Reads story_graph.json from core artifacts, generates all paths,
and creates a JavaScript lookup table for runtime path ID display.

Output: src/PathIdLookup.twee with embedded JavaScript
"""

import sys
import json
from pathlib import Path

# Add formats/allpaths/modules to path for imports
script_dir = Path(__file__).parent
project_dir = script_dir.parent
modules_dir = project_dir / 'formats' / 'allpaths' / 'modules'
sys.path.insert(0, str(modules_dir))

from path_generator import generate_all_paths_dfs, calculate_path_hash
from parser import build_graph
from path_id_lookup import generate_path_id_lookup, generate_javascript_lookup


def main():
    """Generate path ID lookup and write to Twee file."""
    # Determine project directory (current working directory when script runs)
    current_project_dir = Path.cwd()

    # Load story_graph.json from core artifacts
    story_graph_path = current_project_dir / 'lib' / 'artifacts' / 'story_graph.json'

    if not story_graph_path.exists():
        print(f"Error: Core artifact not found: {story_graph_path}", file=sys.stderr)
        print(f"Run 'npm run build:core' first to generate core artifacts", file=sys.stderr)
        sys.exit(1)

    with open(story_graph_path, 'r', encoding='utf-8') as f:
        story_graph = json.load(f)

    # Extract data from story_graph
    start_passage = story_graph['start_passage']

    # Convert story_graph passages to format expected by path_generator
    passages = {}
    for name, passage_data in story_graph['passages'].items():
        passages[name] = {
            'text': passage_data['content']
        }

    # Build graph representation
    graph = build_graph(passages)

    # Generate all paths using DFS
    all_paths = generate_all_paths_dfs(graph, start_passage)
    print(f"Generated {len(all_paths)} paths", file=sys.stderr)

    # Generate lookup table
    lookup = generate_path_id_lookup(all_paths, passages)
    print(f"Created lookup table with {len(lookup)} entries", file=sys.stderr)

    # Generate JavaScript code
    js_code = generate_javascript_lookup(lookup)

    # JavaScript for path ID display
    helper_js = """
// Get path ID for current history
window.getPathId = function(history) {
    var route = history.join('→');
    return window.pathIdLookup[route] || null;
};

// Display path ID at endings (passages with no outgoing links)
(function() {
    function checkAndDisplayPathId() {
        // Check if this is an ending (no tw-link elements = no outgoing links)
        var links = document.querySelectorAll('tw-story tw-passage tw-link');
        if (links.length > 0) {
            return; // Has links, not an ending
        }

        // Get history from footer element
        var historyEl = document.getElementById('harlowe-history-data');
        if (!historyEl) return;

        var historyText = historyEl.textContent.trim();
        if (!historyText) return;

        var history = historyText.split(', ').filter(function(s) { return s; });
        if (history.length === 0) return;

        // Look up path ID
        var pathId = window.getPathId(history);
        if (!pathId) return;

        // Display in container
        var container = document.querySelector('.path-id-container');
        if (!container || container.hasChildNodes()) return;

        var div = document.createElement('div');
        div.style.cssText = 'margin-top: 2em; padding-top: 1em; border-top: 1px solid #666; font-size: 0.9em; color: #888;';
        div.innerHTML = '<p style="font-family: monospace;">Path ID: ' + pathId + '</p>';
        container.appendChild(div);
    }

    // Run after each passage renders
    var observer = new MutationObserver(function(mutations) {
        mutations.forEach(function(mutation) {
            if (mutation.addedNodes.length > 0) {
                setTimeout(checkAndDisplayPathId, 50);
            }
        });
    });

    // Start observing when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            var story = document.querySelector('tw-story');
            if (story) observer.observe(story, { childList: true, subtree: true });
            checkAndDisplayPathId();
        });
    } else {
        var story = document.querySelector('tw-story');
        if (story) observer.observe(story, { childList: true, subtree: true });
        checkAndDisplayPathId();
    }
})();
"""

    full_js = js_code + "\n" + helper_js

    # Write to Twee file
    output_path = current_project_dir / 'src' / 'PathIdLookup.twee'

    twee_content = f""":: PathIdLookup [script]
{full_js}
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(twee_content)

    print(f"✓ Generated {output_path}", file=sys.stderr)
    print(f"  - {len(lookup)} path ID mappings", file=sys.stderr)
    print(f"  - window.pathIdLookup available at runtime", file=sys.stderr)
    print(f"  - window.getPathId() helper function available", file=sys.stderr)


if __name__ == '__main__':
    main()
