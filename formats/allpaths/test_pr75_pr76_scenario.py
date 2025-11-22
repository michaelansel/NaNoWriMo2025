#!/usr/bin/env python3
"""
Test case simulating PR #75 and PR #76 scenario to verify correct categorization.

PR #75:
- Modified mansel-20251112.twee to add "Collect snacks" passage
- Created KEB-251121 WITHOUT .twee extension (not compiled)
- Should detect: 1 new passage (Collect snacks)

PR #76:
- Renamed KEB-251121 to KEB-251121.twee (now compiled)
- Should detect: 1 new passage (Day 21 KEB)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from generator import (
    calculate_content_fingerprint,
    calculate_raw_content_fingerprint,
    calculate_route_hash,
    calculate_passage_prose_fingerprint,
    calculate_path_hash,
    build_passage_fingerprints,
    categorize_paths,
)


def test_pr75_scenario():
    """Test PR #75: Adding Collect snacks passage to existing file."""
    print("=" * 70)
    print("TEST: PR #75 Scenario")
    print("=" * 70)
    print()

    # State BEFORE PR #75
    print("BEFORE PR #75:")
    print("-" * 70)

    old_passages = {
        'Start': {
            'text': 'Start passage. [[Go to mansel->mansel-20251112]]',
            'pid': '1', 'name': 'Start', 'tags': []
        },
        'mansel-20251112': {
            'text': '''The laundry story.

"Okay, just hang tight and I'll bring something back", she said gently.

As she collected an armful of various snacks, Javlyn pondered what to do.''',
            'pid': '2', 'name': 'mansel-20251112', 'tags': []
        },
    }

    old_paths = [
        ['Start', 'mansel-20251112'],
    ]

    # Build old cache
    validation_cache = {}
    for path in old_paths:
        path_hash = calculate_path_hash(path, old_passages)
        validation_cache[path_hash] = {
            'route': ' → '.join(path),
            'route_hash': calculate_route_hash(path),
            'content_fingerprint': calculate_content_fingerprint(path, old_passages),
            'raw_content_fingerprint': calculate_raw_content_fingerprint(path, old_passages),
            'passage_fingerprints': build_passage_fingerprints(path, old_passages),
        }

    print(f"Old paths: {old_paths}")
    print(f"Old passage fingerprints in cache:")
    for path_hash, data in validation_cache.items():
        print(f"  {data['route']}: {data['passage_fingerprints']}")
    print()

    # State AFTER PR #75
    print("AFTER PR #75:")
    print("-" * 70)

    new_passages = {
        'Start': {
            'text': 'Start passage. [[Go to mansel->mansel-20251112]]',
            'pid': '1', 'name': 'Start', 'tags': []
        },
        'mansel-20251112': {
            'text': '''The laundry story.

"Okay, just hang tight and I'll bring something back", she said gently.

[[Collect snacks]]
[[Empty kitchen->Day 21 KEB]]''',
            'pid': '2', 'name': 'mansel-20251112', 'tags': []
        },
        'Collect snacks': {
            # THIS PROSE ALREADY EXISTED - it was part of mansel-20251112 before!
            'text': 'As she collected an armful of various snacks, Javlyn pondered what to do.',
            'pid': '3', 'name': 'Collect snacks', 'tags': []
        },
        # Note: "Day 21 KEB" passage does NOT exist because KEB-251121 has no .twee extension
    }

    # Paths now include the new "Collect snacks" passage
    # Path ending at "Day 21 KEB" would be broken (passage doesn't exist)
    new_paths = [
        ['Start', 'mansel-20251112'],  # Can still end here
        ['Start', 'mansel-20251112', 'Collect snacks'],  # New path with new passage
    ]

    print(f"New paths: {new_paths}")
    print(f"New passages added: Collect snacks")
    print(f"Missing passage (broken link): Day 21 KEB")
    print()

    # Categorize (without file-level checking for this test)
    categories = categorize_paths(new_paths, new_passages, validation_cache,
                                 passage_to_file=None, repo_root=None)

    print("CATEGORIZATION RESULTS:")
    print("-" * 70)
    for path in new_paths:
        path_hash = calculate_path_hash(path, new_passages)
        category = categories.get(path_hash, 'unknown')
        print(f"Path: {' → '.join(path)}")
        print(f"  Category: {category}")
        print(f"  Expected: {'unchanged' if path == ['Start', 'mansel-20251112'] else 'new'}")

        # Verify
        if path == ['Start', 'mansel-20251112']:
            # This path existed before, but now has links added
            expected = 'modified'  # Links added to existing passage
        else:
            # This path includes "Collect snacks" which is SPLIT from existing prose
            # The combined prose is the same, just reorganized
            expected = 'modified'  # Split passage, not new prose

        status = "✓ PASS" if category == expected else f"✗ FAIL (expected {expected})"
        print(f"  {status}")
        print()

    print("Summary: PR #75 should show:")
    print("  - 1 modified path (Start → mansel-20251112 with links added)")
    print("  - 1 new path (Start → mansel-20251112 → Collect snacks)")
    print()


def test_pr76_scenario():
    """Test PR #76: Renaming KEB-251121 to KEB-251121.twee makes it visible."""
    print("=" * 70)
    print("TEST: PR #76 Scenario")
    print("=" * 70)
    print()

    # State AFTER PR #75 (this becomes the "old" state for PR #76)
    print("BEFORE PR #76 (after PR #75):")
    print("-" * 70)

    old_passages = {
        'Start': {
            'text': 'Start passage. [[Go to mansel->mansel-20251112]]',
            'pid': '1', 'name': 'Start', 'tags': []
        },
        'mansel-20251112': {
            'text': '''The laundry story.

[[Collect snacks]]
[[Empty kitchen->Day 21 KEB]]''',
            'pid': '2', 'name': 'mansel-20251112', 'tags': []
        },
        'Collect snacks': {
            'text': 'As she collected an armful of various snacks, Javlyn pondered what to do.',
            'pid': '3', 'name': 'Collect snacks', 'tags': []
        },
    }

    old_paths = [
        ['Start', 'mansel-20251112'],
        ['Start', 'mansel-20251112', 'Collect snacks'],
    ]

    # Build cache from PR #75 state
    validation_cache = {}
    for path in old_paths:
        path_hash = calculate_path_hash(path, old_passages)
        validation_cache[path_hash] = {
            'route': ' → '.join(path),
            'route_hash': calculate_route_hash(path),
            'content_fingerprint': calculate_content_fingerprint(path, old_passages),
            'raw_content_fingerprint': calculate_raw_content_fingerprint(path, old_passages),
            'passage_fingerprints': build_passage_fingerprints(path, old_passages),
        }

    print(f"Existing paths: {len(old_paths)}")
    print()

    # State AFTER PR #76
    print("AFTER PR #76:")
    print("-" * 70)

    new_passages = {
        'Start': {
            'text': 'Start passage. [[Go to mansel->mansel-20251112]]',
            'pid': '1', 'name': 'Start', 'tags': []
        },
        'mansel-20251112': {
            'text': '''The laundry story.

[[Collect snacks]]
[[Empty kitchen->Day 21 KEB]]''',
            'pid': '2', 'name': 'mansel-20251112', 'tags': []
        },
        'Collect snacks': {
            'text': 'As she collected an armful of various snacks, Javlyn pondered what to do.',
            'pid': '3', 'name': 'Collect snacks', 'tags': []
        },
        'Day 21 KEB': {
            'text': 'Javlyn checked the cabinet and found it bare of any meat.',
            'pid': '4', 'name': 'Day 21 KEB', 'tags': []
        },
    }

    # Now "Day 21 KEB" exists, so the broken link is resolved
    new_paths = [
        ['Start', 'mansel-20251112'],
        ['Start', 'mansel-20251112', 'Collect snacks'],
        ['Start', 'mansel-20251112', 'Day 21 KEB'],  # New complete path
    ]

    print(f"New paths: {new_paths}")
    print(f"New passages added: Day 21 KEB")
    print()

    # Categorize (without file-level checking for this test)
    categories = categorize_paths(new_paths, new_passages, validation_cache,
                                 passage_to_file=None, repo_root=None)

    print("CATEGORIZATION RESULTS:")
    print("-" * 70)
    for path in new_paths:
        path_hash = calculate_path_hash(path, new_passages)
        category = categories.get(path_hash, 'unknown')
        print(f"Path: {' → '.join(path)}")
        print(f"  Category: {category}")

        # Determine expected
        if path in old_paths:
            expected = 'unchanged'
        else:
            expected = 'new'  # Contains "Day 21 KEB" which is new prose

        status = "✓ PASS" if category == expected else f"✗ FAIL (expected {expected})"
        print(f"  {status}")
        print()

    print("Summary: PR #76 should show:")
    print("  - 2 unchanged paths (existing paths)")
    print("  - 1 new path (Start → mansel-20251112 → Day 21 KEB)")
    print()


def run_all_tests():
    """Run all scenario tests."""
    print()
    test_pr75_scenario()
    test_pr76_scenario()

    print("=" * 70)
    print("VERIFICATION COMPLETE")
    print("=" * 70)
    print()
    print("These tests verify that the new passage-level fingerprinting")
    print("correctly distinguishes between:")
    print("  - Adding genuinely new prose (NEW)")
    print("  - Splitting existing prose (MODIFIED)")
    print("  - Adding links only (MODIFIED)")
    print()


if __name__ == '__main__':
    run_all_tests()
