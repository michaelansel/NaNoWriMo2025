#!/usr/bin/env python3
"""
Test categorization for PR #65 (Day 19) with REAL passage content

This uses the actual text from Start.twee before and after PR #65.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'formats' / 'allpaths'))

from generator import (
    calculate_path_hash,
    calculate_content_fingerprint,
    calculate_raw_content_fingerprint,
    calculate_route_hash,
    categorize_paths,
    strip_links_from_text,
)

# Real Start passage content BEFORE PR #65
start_before = """What is weighing on your mind today?

[[A rumor]]

[[The laundry->mansel-20251112]]"""

# Real Start passage content AFTER PR #65
start_after = """What is weighing on your mind today?

[[A rumor]]

[[The laundry->mansel-20251112]]

[[Sleep->Day 19 KEB]]"""

# Simulate passages BEFORE PR #65
passages_before = {
    'Start': {'text': start_before, 'pid': '1'},
    'A rumor': {'text': 'There were rumors...', 'pid': '2'},
    'mansel-20251112': {'text': 'Laundry content...', 'pid': '3'},
}

# Simulate passages AFTER PR #65
passages_after = {
    'Start': {'text': start_after, 'pid': '1'},
    'A rumor': {'text': 'There were rumors...', 'pid': '2'},
    'mansel-20251112': {'text': 'Laundry content...', 'pid': '3'},
    'Day 19 KEB': {'text': 'Sleep was calling to Javlyn...', 'pid': '4'},
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
    raw_content_fingerprint = calculate_raw_content_fingerprint(old_path, passages_before)
    route_hash = calculate_route_hash(old_path)

    validation_cache[path_hash] = {
        'route': ' → '.join(old_path),
        'route_hash': route_hash,
        'content_fingerprint': content_fingerprint,
        'raw_content_fingerprint': raw_content_fingerprint,
        'validated': True,
    }

print("=== PR #65 REAL CONTENT Test ===\n")
print("Start passage BEFORE:")
print(f"  Raw: {repr(start_before[:50])}...")
print(f"  Stripped: {repr(strip_links_from_text(start_before)[:50])}...")
print()

print("Start passage AFTER:")
print(f"  Raw: {repr(start_after[:50])}...")
print(f"  Stripped: {repr(strip_links_from_text(start_after)[:50])}...")
print()

print("Are stripped versions equal?", strip_links_from_text(start_before) == strip_links_from_text(start_after))
print()

print("BEFORE PR #65:")
for old_path in old_paths:
    print(f"  Path: {' → '.join(old_path)}")
    print(f"    content_fingerprint: {calculate_content_fingerprint(old_path, passages_before)}")
    print(f"    route_hash: {calculate_route_hash(old_path)}")
print()

# New paths after PR #65
new_paths = [
    ['Start', 'mansel-20251112'],  # Same route, Start has link added
    ['Start', 'A rumor'],           # Same route, Start has link added
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
        print(f"    Fingerprints match: {old_fingerprint == new_fingerprint}")
    else:
        print(f"    New fingerprint: {new_fingerprint}")
        print(f"    (no previous version)")
print()

print("EXPECTED RESULTS:")
print("  ✓ Start → mansel-20251112: MODIFIED (same prose, link added)")
print("  ✓ Start → A rumor: MODIFIED (same prose, link added)")
print("  ✓ Start → Day 19 KEB: NEW (new prose content)")
