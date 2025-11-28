#!/usr/bin/env python3
"""
AllPaths Categorizer Module (Stage 4)

Classifies paths as new/modified/unchanged based on validation cache.

This module implements the simplified categorization that uses the validation
cache to determine which paths have been seen before and their status.
The complex git-based categorization logic remains in generator.py until
the full refactoring is complete.
"""

import hashlib
from datetime import datetime
from typing import Dict, List, Optional


def calculate_route_hash(route: List[str]) -> str:
    """Calculate hash based ONLY on passage names (route structure), not content.

    This identifies the path structure independent of content changes.
    Two paths with the same sequence of passages will have the same route_hash
    even if the content in those passages has been edited.

    Used in categorization logic to determine if a path existed in the base branch
    by comparing route hashes.

    Args:
        route: List of passage names in order

    Returns:
        8-character hex hash based on route structure only
    """
    route_string = ' → '.join(route)
    return hashlib.md5(route_string.encode()).hexdigest()[:8]


def categorize_paths(paths_enriched: Dict, validation_cache: Dict) -> Dict:
    """Categorize paths as new/modified/unchanged based on validation cache.

    This is a simplified categorization that uses the validation cache to determine
    path status. For now, this implements basic cache-based categorization.

    The full two-level categorization logic (path existence test + content test)
    remains in generator.py and will be migrated in a future refactoring step.

    Args:
        paths_enriched: Dict with paths array (from git_enricher module)
        validation_cache: Dict mapping path_id -> validation metadata

    Returns:
        Dict with:
            - paths: Array of paths with added categorization fields
            - statistics: Dict with counts of new/modified/unchanged paths

    Each path in the output includes:
        - category: "new", "modified", or "unchanged"
        - validated: Boolean from cache (False for new paths)
        - first_seen: ISO timestamp from cache (current time for new paths)
    """
    paths = paths_enriched.get('paths', [])
    categorized_paths = []

    # Statistics counters
    stats = {
        'new': 0,
        'modified': 0,
        'unchanged': 0
    }

    for path in paths:
        path_id = path['id']

        # Create a copy of the path with categorization fields
        categorized_path = path.copy()

        # Check if path exists in validation cache
        if path_id in validation_cache:
            cache_entry = validation_cache[path_id]

            # Use category from cache (this was computed by generator.py's full logic)
            category = cache_entry.get('category', 'new')
            validated = cache_entry.get('validated', False)
            first_seen = cache_entry.get('first_seen', datetime.now().isoformat())
        else:
            # New path - not in cache
            category = 'new'
            validated = False
            first_seen = datetime.now().isoformat()

        # Add categorization fields
        categorized_path['category'] = category
        categorized_path['validated'] = validated
        categorized_path['first_seen'] = first_seen

        # Update statistics
        stats[category] += 1

        categorized_paths.append(categorized_path)

    return {
        'paths': categorized_paths,
        'statistics': stats
    }
