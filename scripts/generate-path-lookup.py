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
// Get path ID for current history (including current passage)
window.getPathId = function(fullPath) {
    var route = fullPath.join('→');
    return window.pathIdLookup[route] || null;
};

// Get current passage name from footer element
function getCurrentPassage() {
    var el = document.getElementById('harlowe-current-passage');
    if (el) {
        var text = el.textContent.trim();
        // Filter out unevaluated macro text
        if (text && !text.includes('(') && !text.includes(':')) {
            return text;
        }
    }
    return null;
}

// Get full path: history (past passages) + current passage
function getFullPath() {
    // Get current passage from footer
    var currentPassage = getCurrentPassage();
    if (!currentPassage) {
        console.log('[PathID] Could not get current passage name');
        return null;
    }
    console.log('[PathID] Current passage:', currentPassage);

    // Get history from footer element (past passages only)
    // History is delimited by ||| since Harlowe doesn't have a join macro
    var historyEl = document.getElementById('harlowe-history-data');
    var pastPassages = [];
    if (historyEl) {
        var text = historyEl.textContent.trim();
        // Filter out unevaluated macro text
        if (text && !text.includes('(history:)') && !text.includes('(for:')) {
            // Split by ||| delimiter, filter empty strings
            pastPassages = text.split('|||').filter(function(s) { return s && s.length > 0; });
        }
    }
    console.log('[PathID] Past passages:', pastPassages);

    // Combine: history + current passage = full path
    var fullPath = pastPassages.concat([currentPassage]);
    console.log('[PathID] Full path:', fullPath);
    return fullPath;
}

// Display path ID at endings
(function() {
    var lastDisplayedPassage = '';

    function checkAndDisplayPathId() {
        var passage = document.querySelector('tw-story tw-passage');
        if (!passage) {
            console.log('[PathID] No passage found');
            return;
        }

        // Get current passage from footer element
        var currentPassage = getCurrentPassage();
        console.log('[PathID] Checking passage:', currentPassage);
        if (!currentPassage) {
            console.log('[PathID] Current passage not available yet');
            return;
        }

        // Skip if already processed this passage
        if (currentPassage === lastDisplayedPassage) return;

        // Check if this is an ending - look for any clickable links
        var links = passage.querySelectorAll('tw-link');
        console.log('[PathID] Found', links.length, 'links in passage');
        if (links.length > 0) return; // Has links, not an ending

        console.log('[PathID] This appears to be an ending');

        // Get full path (history + current passage)
        var fullPath = getFullPath();
        if (!fullPath || fullPath.length === 0) {
            console.log('[PathID] No path available');
            return;
        }

        // Look up path ID
        var route = fullPath.join('→');
        console.log('[PathID] Looking up route:', route);
        var pathId = window.getPathId(fullPath);
        if (!pathId) {
            console.log('[PathID] No path ID found for route');
            var keys = Object.keys(window.pathIdLookup || {});
            console.log('[PathID] Available routes (first 5):', keys.slice(0, 5));
            return;
        }

        console.log('[PathID] Found path ID:', pathId);
        lastDisplayedPassage = currentPassage;

        // Check if already displayed
        if (passage.querySelector('.path-id-display')) return;

        // Create and append display with path ID and route
        var div = document.createElement('div');
        div.className = 'path-id-display';
        div.style.cssText = 'margin-top: 2em; padding-top: 1em; border-top: 1px solid #666; font-size: 0.9em; color: #888;';
        // Format route with arrows for display
        var routeDisplay = fullPath.join(' → ');
        div.innerHTML = '<p style="font-family: monospace; margin: 0;">Path ID: ' + pathId + '</p>' +
                        '<p style="font-size: 0.85em; margin: 0.5em 0 0 0; opacity: 0.8;">(' + routeDisplay + ')</p>';
        passage.appendChild(div);
        console.log('[PathID] Displayed path ID successfully');
    }

    // Run after each passage change with a delay for Harlowe to finish rendering
    var observer = new MutationObserver(function() {
        setTimeout(checkAndDisplayPathId, 300);
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
