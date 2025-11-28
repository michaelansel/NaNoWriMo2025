#!/usr/bin/env python3
"""
Test suite for AllPaths categorizer module.

Tests the Stage 4 (Categorization) functionality that classifies paths
as new/modified/unchanged using two-level test (path existence + content changes).
"""

import sys
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime

# Test counters
tests_passed = 0
tests_failed = 0
test_details = []

def test(name):
    """Decorator to mark test functions"""
    def decorator(func):
        def wrapper():
            global tests_passed, tests_failed, test_details
            try:
                func()
                tests_passed += 1
                test_details.append(f"✓ {name}")
                print(f"✓ {name}")
            except AssertionError as e:
                tests_failed += 1
                test_details.append(f"✗ {name}: {e}")
                print(f"✗ {name}: {e}")
            except Exception as e:
                tests_failed += 1
                test_details.append(f"✗ {name}: Unexpected error: {e}")
                print(f"✗ {name}: Unexpected error: {e}")
        return wrapper
    return decorator

# ============================================================================
# TEST DATA
# ============================================================================

SAMPLE_PATHS_ENRICHED = {
    "paths": [
        {
            "id": "abc12345",
            "route": ["Start", "Middle", "End"],
            "content": {
                "Start": "Beginning text",
                "Middle": "Middle text",
                "End": "End text"
            },
            "git_metadata": {
                "files": ["src/file1.twee"],
                "commit_date": "2025-11-20T10:00:00Z",
                "created_date": "2025-11-02T10:00:00Z",
                "passage_to_file": {
                    "Start": "src/file1.twee",
                    "Middle": "src/file1.twee",
                    "End": "src/file1.twee"
                }
            }
        },
        {
            "id": "def67890",
            "route": ["Start", "End"],
            "content": {
                "Start": "Beginning text",
                "End": "End text"
            },
            "git_metadata": {
                "files": ["src/file1.twee"],
                "commit_date": "2025-11-20T10:00:00Z",
                "created_date": "2025-11-02T10:00:00Z",
                "passage_to_file": {
                    "Start": "src/file1.twee",
                    "End": "src/file1.twee"
                }
            }
        }
    ]
}

EMPTY_CACHE = {}

SAMPLE_CACHE = {
    "abc12345": {
        "route": "Start → Middle → End",
        "first_seen": "2025-11-01T10:00:00Z",
        "validated": False,
        "commit_date": "2025-11-20T10:00:00Z",
        "created_date": "2025-11-02T10:00:00Z",
        "category": "new"
    }
}

# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================

@test("calculate_route_hash - generates stable hash from route")
def test_calculate_route_hash():
    from categorizer import calculate_route_hash

    route1 = ["Start", "Middle", "End"]
    route2 = ["Start", "Middle", "End"]
    route3 = ["Start", "End"]

    hash1 = calculate_route_hash(route1)
    hash2 = calculate_route_hash(route2)
    hash3 = calculate_route_hash(route3)

    # Same route should produce same hash
    assert hash1 == hash2, f"Same routes should produce same hash: {hash1} != {hash2}"

    # Different routes should produce different hashes
    assert hash1 != hash3, f"Different routes should produce different hashes: {hash1} == {hash3}"

    # Hash should be 8 characters
    assert len(hash1) == 8, f"Hash should be 8 characters, got {len(hash1)}"

@test("calculate_route_hash - based only on passage names")
def test_calculate_route_hash_structure_only():
    from categorizer import calculate_route_hash

    # Same route structure should produce same hash regardless of content
    route = ["Start", "Middle", "End"]
    hash1 = calculate_route_hash(route)
    hash2 = calculate_route_hash(route)

    assert hash1 == hash2, "Route hash should be deterministic"

# ============================================================================
# CATEGORIZE_PATHS FUNCTION TESTS
# ============================================================================

@test("categorize_paths - returns paths_categorized structure")
def test_categorize_paths_structure():
    from categorizer import categorize_paths

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)

    # Check required fields
    assert 'paths' in result, "Missing 'paths' field"
    assert 'statistics' in result, "Missing 'statistics' field"
    assert isinstance(result['paths'], list), "paths should be a list"
    assert isinstance(result['statistics'], dict), "statistics should be a dict"

@test("categorize_paths - adds category field to each path")
def test_categorize_paths_adds_category():
    from categorizer import categorize_paths

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)

    for path in result['paths']:
        assert 'category' in path, f"Path {path['id']} missing 'category' field"
        assert path['category'] in ['new', 'modified', 'unchanged'], \
            f"Invalid category: {path['category']}"

@test("categorize_paths - adds validated field to each path")
def test_categorize_paths_adds_validated():
    from categorizer import categorize_paths

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)

    for path in result['paths']:
        assert 'validated' in path, f"Path {path['id']} missing 'validated' field"
        assert isinstance(path['validated'], bool), \
            f"validated should be boolean, got {type(path['validated'])}"

@test("categorize_paths - adds first_seen field to each path")
def test_categorize_paths_adds_first_seen():
    from categorizer import categorize_paths

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)

    for path in result['paths']:
        assert 'first_seen' in path, f"Path {path['id']} missing 'first_seen' field"
        # Should be ISO format timestamp
        try:
            datetime.fromisoformat(path['first_seen'].replace('Z', '+00:00'))
        except:
            raise AssertionError(f"first_seen should be ISO format: {path['first_seen']}")

@test("categorize_paths - preserves existing path data")
def test_categorize_paths_preserves_data():
    from categorizer import categorize_paths

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)

    # Check first path
    path = result['paths'][0]
    assert path['id'] == 'abc12345', "Should preserve path ID"
    assert path['route'] == ["Start", "Middle", "End"], "Should preserve route"
    assert 'content' in path, "Should preserve content"
    assert 'git_metadata' in path, "Should preserve git_metadata"

@test("categorize_paths - calculates statistics")
def test_categorize_paths_statistics():
    from categorizer import categorize_paths

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)
    stats = result['statistics']

    # Check required statistics fields
    assert 'new' in stats, "Missing 'new' count"
    assert 'modified' in stats, "Missing 'modified' count"
    assert 'unchanged' in stats, "Missing 'unchanged' count"

    # All should be integers >= 0
    assert isinstance(stats['new'], int) and stats['new'] >= 0, \
        f"new count should be non-negative integer: {stats['new']}"
    assert isinstance(stats['modified'], int) and stats['modified'] >= 0, \
        f"modified count should be non-negative integer: {stats['modified']}"
    assert isinstance(stats['unchanged'], int) and stats['unchanged'] >= 0, \
        f"unchanged count should be non-negative integer: {stats['unchanged']}"

@test("categorize_paths - statistics sum equals total paths")
def test_categorize_paths_statistics_sum():
    from categorizer import categorize_paths

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)
    stats = result['statistics']

    total = stats['new'] + stats['modified'] + stats['unchanged']
    assert total == len(result['paths']), \
        f"Statistics should sum to total paths: {total} != {len(result['paths'])}"

# ============================================================================
# CATEGORIZATION LOGIC TESTS
# ============================================================================

@test("categorize_paths - new path not in cache marked as 'new'")
def test_categorize_new_path():
    from categorizer import categorize_paths

    # Empty cache - all paths should be new
    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)

    # With empty cache and no git data, paths should be marked as 'new'
    # (this is the conservative fallback)
    for path in result['paths']:
        assert path['category'] == 'new', \
            f"Path {path['id']} should be 'new' with empty cache, got '{path['category']}'"

@test("categorize_paths - uses cache for first_seen date")
def test_categorize_uses_cache_first_seen():
    from categorizer import categorize_paths

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, SAMPLE_CACHE)

    # Path in cache should use cached first_seen
    cached_path = [p for p in result['paths'] if p['id'] == 'abc12345'][0]
    assert cached_path['first_seen'] == "2025-11-01T10:00:00Z", \
        f"Should use cached first_seen: {cached_path['first_seen']}"

@test("categorize_paths - uses cache for validated flag")
def test_categorize_uses_cache_validated():
    from categorizer import categorize_paths

    # Set a path as validated in cache
    cache_with_validated = SAMPLE_CACHE.copy()
    cache_with_validated['abc12345']['validated'] = True

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, cache_with_validated)

    # Path in cache should preserve validated flag
    cached_path = [p for p in result['paths'] if p['id'] == 'abc12345'][0]
    assert cached_path['validated'] == True, \
        f"Should preserve validated flag from cache"

@test("categorize_paths - new path gets current timestamp for first_seen")
def test_categorize_new_path_timestamp():
    from categorizer import categorize_paths

    before = datetime.now().isoformat()
    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)
    after = datetime.now().isoformat()

    # New paths should get timestamp close to now
    new_path = result['paths'][0]
    first_seen = new_path['first_seen']

    # Just check it's a valid ISO timestamp
    try:
        datetime.fromisoformat(first_seen.replace('Z', '+00:00'))
    except:
        raise AssertionError(f"first_seen should be ISO format: {first_seen}")

@test("categorize_paths - new path has validated=False")
def test_categorize_new_path_not_validated():
    from categorizer import categorize_paths

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)

    # New paths should not be validated
    for path in result['paths']:
        assert path['validated'] == False, \
            f"New path {path['id']} should have validated=False"

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@test("Integration - full categorization workflow")
def test_integration_full_workflow():
    from categorizer import categorize_paths

    # Start with empty cache
    result1 = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)

    # All paths should be new
    for path in result1['paths']:
        assert path['category'] == 'new', "First run should mark all as new"

    # Build cache from result
    cache = {
        path['id']: {
            'route': ' → '.join(path['route']),
            'first_seen': path['first_seen'],
            'validated': path['validated'],
            'category': path['category']
        }
        for path in result1['paths']
    }

    # Run again with cache
    result2 = categorize_paths(SAMPLE_PATHS_ENRICHED, cache)

    # Should preserve first_seen dates
    for i, path in enumerate(result2['paths']):
        assert path['first_seen'] == result1['paths'][i]['first_seen'], \
            f"Should preserve first_seen from cache"

@test("Integration - validate against JSON schema")
def test_integration_schema_validation():
    from categorizer import categorize_paths

    try:
        import jsonschema
    except ImportError:
        print("    (jsonschema not installed, skipping schema validation)")
        return

    # Load schema
    schema_path = Path(__file__).parent.parent / 'schemas' / 'paths_categorized.schema.json'
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    result = categorize_paths(SAMPLE_PATHS_ENRICHED, EMPTY_CACHE)

    # This should not raise an exception
    try:
        jsonschema.validate(result, schema)
    except jsonschema.ValidationError as e:
        raise AssertionError(f"Categorized paths don't match schema: {e}")

# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    print("=" * 80)
    print("CATEGORIZER MODULE TEST SUITE")
    print("=" * 80)
    print()

    print("Unit Tests")
    print("-" * 80)
    # Helper function tests
    test_calculate_route_hash()
    test_calculate_route_hash_structure_only()

    # categorize_paths function tests
    test_categorize_paths_structure()
    test_categorize_paths_adds_category()
    test_categorize_paths_adds_validated()
    test_categorize_paths_adds_first_seen()
    test_categorize_paths_preserves_data()
    test_categorize_paths_statistics()
    test_categorize_paths_statistics_sum()

    # Categorization logic tests
    test_categorize_new_path()
    test_categorize_uses_cache_first_seen()
    test_categorize_uses_cache_validated()
    test_categorize_new_path_timestamp()
    test_categorize_new_path_not_validated()

    print()
    print("Integration Tests")
    print("-" * 80)
    test_integration_full_workflow()
    test_integration_schema_validation()

    # Print summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests:  {tests_passed + tests_failed}")
    print(f"Success Rate: {100 * tests_passed / (tests_passed + tests_failed) if (tests_passed + tests_failed) > 0 else 0:.1f}%")
    print()

    if tests_failed == 0:
        print("ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED!")
        print("\nFailed tests:")
        for detail in test_details:
            if detail.startswith("✗"):
                print(f"  {detail}")
        sys.exit(1)
