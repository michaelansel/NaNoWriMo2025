#!/usr/bin/env python3
"""
Test categorization for PR #65 (Day 19)

PR #65 changes:
1. Added link in Start.twee: [[Sleep->Day 19 KEB]]
2. Created new file KEB-251119.twee with Day 19 prose
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'formats' / 'allpaths'))

from generator import (
    calculate_path_hash,
    calculate_content_fingerprint,
    calculate_route_hash,
    categorize_paths,
)

# Simulate the state BEFORE PR #65
passages_before = {
    'Start': {'text': 'What is weighing on your mind today?\n\n[[The laundry->mansel-20251112]]', 'pid': '1'},
    'A rumor': {'text': 'There were rumors...', 'pid': '2'},
    'mansel-20251112': {'text': 'Laundry content...', 'pid': '3'},
}

# Simulate the state AFTER PR #65
passages_after = {
    'Start': {'text': 'What is weighing on your mind today?\n\n[[The laundry->mansel-20251112]]\n\n[[Sleep->Day 19 KEB]]', 'pid': '1'},
    'A rumor': {'text': 'There were rumors...', 'pid': '2'},
    'mansel-20251112': {'text': 'Laundry content...', 'pid': '3'},
    'Day 19 KEB': {'text': 'NEW PROSE: Sleep was calling to Javlyn...', 'pid': '4'},
}

# Old paths before PR #65
old_paths = [
    ['Start', 'mansel-20251112'],
    ['Start', 'A rumor'],
]

# Build validation cache with old paths
validation_cache = {}
for old_path in old_paths:
    path_hash = calculate_path_hash(old_path, passages_before)
    content_fingerprint = calculate_content_fingerprint(old_path, passages_before)
    route_hash = calculate_route_hash(old_path)

    validation_cache[path_hash] = {
        'route': ' → '.join(old_path),
        'route_hash': route_hash,
        'content_fingerprint': content_fingerprint,
        'validated': True,
    }

print("=== PR #65 Categorization Test ===\n")
print("BEFORE PR #65:")
for old_path in old_paths:
    print(f"  Path: {' → '.join(old_path)}")
    print(f"    content_fingerprint: {calculate_content_fingerprint(old_path, passages_before)}")
    print(f"    route_hash: {calculate_route_hash(old_path)}")
print()

# New paths after PR #65
new_paths = [
    ['Start', 'mansel-20251112'],  # Same route, but Start content changed
    ['Start', 'A rumor'],           # Same route, but Start content changed
    ['Start', 'Day 19 KEB'],        # New route with new content
]

print("AFTER PR #65:")
for new_path in new_paths:
    print(f"  Path: {' → '.join(new_path)}")
    print(f"    content_fingerprint: {calculate_content_fingerprint(new_path, passages_after)}")
    print(f"    route_hash: {calculate_route_hash(new_path)}")
print()

# Run categorization
categories = categorize_paths(new_paths, passages_after, validation_cache)

print("CATEGORIZATION RESULTS:")
for new_path in new_paths:
    path_hash = calculate_path_hash(new_path, passages_after)
    category = categories.get(path_hash, 'unknown')
    route = ' → '.join(new_path)

    old_fingerprint = None
    new_fingerprint = calculate_content_fingerprint(new_path, passages_after)

    # Try to find old fingerprint
    for old_path in old_paths:
        if old_path == new_path:
            old_fingerprint = calculate_content_fingerprint(old_path, passages_before)
            break

    print(f"  {category.upper()}: {route}")
    if old_fingerprint:
        print(f"    Old fingerprint: {old_fingerprint}")
        print(f"    New fingerprint: {new_fingerprint}")
        print(f"    Content changed: {old_fingerprint != new_fingerprint}")
    else:
        print(f"    New fingerprint: {new_fingerprint}")
        print(f"    No previous version")
print()

print("ANALYSIS:")
print("  Expected: 1 NEW path (Day 19), existing paths should be MODIFIED or NEW")
print("  ")
print("  Issue: Start.twee content changed (link added), so content_fingerprint changes")
print("  for all paths going through Start. This makes them NEW, not MODIFIED.")
print("  ")
print("  The content-based logic detects ANY content change as new prose.")
print("  To get MODIFIED, we'd need the exact same prose in a different structure.")
