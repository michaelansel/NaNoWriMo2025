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
        // Create clickable link to clean path file
        var pathLink = '<a href="allpaths-clean/path-' + pathId + '.txt" target="_blank" rel="noopener" style="color: #88f; text-decoration: none;">' + pathId + '</a>';
        div.innerHTML = '<p style="font-family: monospace; margin: 0;">Path ID: ' + pathLink + '</p>' +
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
