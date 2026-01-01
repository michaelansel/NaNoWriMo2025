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

// Get passage history from footer element
function getHistory() {
    // Look in the rendered passage for the history span
    var passage = document.querySelector('tw-story tw-passage');
    if (!passage) return null;

    var historyEl = passage.querySelector('#harlowe-history-data');
    if (historyEl) {
        var text = historyEl.textContent.trim();
        // Filter out the macro text if not evaluated
        if (text && !text.includes('(history:)')) {
            var parts = text.split(', ').filter(function(s) { return s && s.length > 0; });
            console.log('[PathID] History from footer:', parts);
            return parts;
        }
    }
    console.log('[PathID] Could not read history from footer element');
    return null;
}

// Display path ID at endings
(function() {
    function checkAndDisplayPathId() {
        var passage = document.querySelector('tw-story tw-passage');
        if (!passage) {
            console.log('[PathID] No passage found');
            return;
        }

        // Check if this is an ending - look for any clickable links
        // Harlowe uses tw-link for rendered links
        var links = passage.querySelectorAll('tw-link');
        console.log('[PathID] Found', links.length, 'links in passage');
        if (links.length > 0) return; // Has links, not an ending

        // Also check for tw-expression with link macros (covers edge cases)
        var expressions = passage.querySelectorAll('tw-expression[name="link"], tw-expression[name="link-goto"]');
        console.log('[PathID] Found', expressions.length, 'link expressions');
        if (expressions.length > 0) return;

        console.log('[PathID] This appears to be an ending');

        // Get history
        var history = getHistory();
        if (!history || history.length === 0) {
            console.log('[PathID] No history available');
            return;
        }

        // Look up path ID
        var route = history.join('→');
        console.log('[PathID] Looking up route:', route);
        var pathId = window.getPathId(history);
        if (!pathId) {
            console.log('[PathID] No path ID found for route');
            // Show available keys for debugging
            var keys = Object.keys(window.pathIdLookup || {});
            console.log('[PathID] Available routes (first 5):', keys.slice(0, 5));
            return;
        }

        console.log('[PathID] Found path ID:', pathId);

        // Check if already displayed
        var container = passage.querySelector('.path-id-display');
        if (container) return;

        // Create and append display
        var div = document.createElement('div');
        div.className = 'path-id-display';
        div.style.cssText = 'margin-top: 2em; padding-top: 1em; border-top: 1px solid #666; font-size: 0.9em; color: #888;';
        div.innerHTML = '<p style="font-family: monospace; margin: 0;">Path ID: ' + pathId + '</p>';
        passage.appendChild(div);
        console.log('[PathID] Displayed path ID successfully');
    }

    // Run after each passage change with a delay for Harlowe to finish rendering
    var observer = new MutationObserver(function() {
        setTimeout(checkAndDisplayPathId, 200);
    });

    function init() {
        var story = document.querySelector('tw-story');
        if (story) {
            console.log('[PathID] Initialized, observing tw-story');
            observer.observe(story, { childList: true, subtree: true });
            setTimeout(checkAndDisplayPathId, 200);
        } else {
            console.log('[PathID] tw-story not found at init');
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
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
