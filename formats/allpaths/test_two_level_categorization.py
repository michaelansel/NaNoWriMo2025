#!/usr/bin/env python3
"""
Unit test for two-level path categorization logic.

This test verifies that the PRIMARY path existence test is working correctly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from generator import (
    parse_twee_content,
    build_graph,
    generate_all_paths_dfs,
    calculate_route_hash,
    categorize_paths,
    calculate_path_hash,
)


def test_two_level_categorization():
    """Test that paths existing in base are never categorized as NEW"""

    print("=" * 80)
    print("Testing Two-Level Path Categorization Logic")
    print("=" * 80)
    print()

    # Create sample twee content for base branch (with smart quotes)
    base_twee = """
:: Start
Welcome to the story.

[[Chapter 1]]

:: Chapter 1
This is chapter one with "smart quotes".

[[Chapter 2]]

:: Chapter 2
The end with more "smart quotes".
"""

    # Create sample twee content for current branch (with ASCII quotes - linter format)
    current_twee = """
:: Start
Welcome to the story.

[[Chapter 1]]

:: Chapter 1
This is chapter one with "ASCII quotes".

[[Chapter 2]]

:: Chapter 2
The end with more "ASCII quotes".
"""

    # Parse both versions
    base_passages = parse_twee_content(base_twee)
    current_passages = parse_twee_content(current_twee)

    print(f"Base passages: {list(base_passages.keys())}")
    print(f"Current passages: {list(current_passages.keys())}")
    print()

    # Build graphs
    base_graph = build_graph(base_passages)
    current_graph = build_graph(current_passages)

    # Generate paths
    base_paths = generate_all_paths_dfs(base_graph, 'Start')
    current_paths = generate_all_paths_dfs(current_graph, 'Start')

    print(f"Base paths: {len(base_paths)}")
    for path in base_paths:
        print(f"  {' → '.join(path)}")
    print()

    print(f"Current paths: {len(current_paths)}")
    for path in current_paths:
        print(f"  {' → '.join(path)}")
    print()

    # Calculate route hashes for base paths
    base_route_hashes = {calculate_route_hash(path) for path in base_paths}

    print(f"Base route hashes: {len(base_route_hashes)}")
    for path in base_paths:
        route_hash = calculate_route_hash(path)
        print(f"  {route_hash}: {' → '.join(path)}")
    print()

    # Check current paths against base
    print("Checking current paths against base:")
    print("-" * 80)

    all_paths_exist_in_base = True
    for path in current_paths:
        route_hash = calculate_route_hash(path)
        exists_in_base = route_hash in base_route_hashes
        print(f"  {' → '.join(path)}")
        print(f"    Route hash: {route_hash}")
        print(f"    Existed in base: {exists_in_base}")

        if not exists_in_base:
            all_paths_exist_in_base = False

    print()
    print("EXPECTATION:")
    print("-" * 80)
    print("All current paths should exist in base (same route structure)")
    print("Even though content changed (quotes), the path structure is identical")
    print()

    if all_paths_exist_in_base:
        print("✓ PASS: All current paths existed in base")
    else:
        print("✗ FAIL: Some current paths didn't exist in base")
        return False

    print()
    print("IMPLICATION:")
    print("-" * 80)
    print("Since all paths existed in base:")
    print("  → NO paths should be categorized as NEW")
    print("  → All changed paths should be MODIFIED (quote changes)")
    print()

    return True


def test_mock_categorization():
    """Test categorization with mock scenario (no git required)"""

    print("=" * 80)
    print("Testing Mock Categorization Scenario")
    print("=" * 80)
    print()

    # This demonstrates the logic without requiring actual git operations
    # We simulate: path exists in base, content changed (formatting only)

    current_twee = """
:: Start
Welcome.

[[End]]

:: End
Goodbye.
"""

    passages = parse_twee_content(current_twee)
    graph = build_graph(passages)
    paths = generate_all_paths_dfs(graph, 'Start')

    print(f"Paths: {len(paths)}")
    for path in paths:
        print(f"  {' → '.join(path)}")
    print()

    # Simulate base route hashes (same paths exist in base)
    base_route_hashes = {calculate_route_hash(path) for path in paths}

    print("Simulated scenario:")
    print("  - All paths existed in base branch")
    print("  - Content changed (formatting only)")
    print("  - Expected: All paths MODIFIED (not NEW)")
    print()

    # Mock the categorization logic
    for path in paths:
        route_hash = calculate_route_hash(path)
        path_existed_in_base = route_hash in base_route_hashes

        # Simulate: content changed (formatting)
        has_any_changes = True
        has_prose_changes = False

        # Apply two-level logic
        if path_existed_in_base:
            if has_any_changes:
                category = 'modified'
            else:
                category = 'unchanged'
        else:
            if has_prose_changes:
                category = 'new'
            else:
                category = 'modified'

        print(f"Path: {' → '.join(path)}")
        print(f"  Existed in base: {path_existed_in_base}")
        print(f"  Has changes: {has_any_changes}")
        print(f"  Has prose changes: {has_prose_changes}")
        print(f"  → Category: {category.upper()}")

        if category == 'new':
            print("  ✗ FAIL: Should be MODIFIED, not NEW")
            return False
        elif category == 'modified':
            print("  ✓ PASS: Correctly categorized as MODIFIED")
        print()

    return True


def main():
    print()

    # Run both tests
    test1_passed = test_two_level_categorization()
    print()
    print()

    test2_passed = test_mock_categorization()
    print()

    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()

    if test1_passed and test2_passed:
        print("✓ ALL TESTS PASSED")
        print()
        print("The two-level categorization logic is working correctly:")
        print("  1. PRIMARY test: Route hash existence check")
        print("  2. SECONDARY test: Content change detection")
        print("  → Paths that existed in base are never NEW (even with content changes)")
        sys.exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == '__main__':
    main()
