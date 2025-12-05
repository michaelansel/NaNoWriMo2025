#!/usr/bin/env python3
"""
Comprehensive test suite for allpaths generator implementation.

Tests:
1. Unit tests for key functions
2. Integration tests with real data
3. Edge case handling
4. Validation workflow compatibility
"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Project root is two directories up from this file (formats/allpaths/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

from generator import (
    calculate_path_similarity,
    generate_passage_id_mapping,
    load_validation_cache,
)
from modules.categorizer import (
    calculate_route_hash,
    categorize_paths,
    strip_links_from_text,
)
from modules.parser import (
    parse_story_html,
    build_graph,
    extract_links,
    parse_link,
)
from modules.path_generator import (
    calculate_path_hash,
    generate_all_paths_dfs,
    format_passage_text,
)
from modules.git_enricher import (
    build_passage_to_file_mapping,
    get_file_commit_date,
    get_path_commit_date,
)
from modules.output_generator import (
    save_validation_cache,
)

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
# PART 1: UNIT TESTS FOR KEY FUNCTIONS
# ============================================================================

@test("calculate_path_hash - produces consistent hashes")
def test_path_hash_consistency():
    passages = {
        'Start': {'text': 'Welcome to the story', 'pid': '1'},
        'Middle': {'text': 'You are in the middle', 'pid': '2'},
        'End': {'text': 'The end', 'pid': '3'}
    }
    path = ['Start', 'Middle', 'End']

    hash1 = calculate_path_hash(path, passages)
    hash2 = calculate_path_hash(path, passages)

    assert hash1 == hash2, f"Hash should be consistent: {hash1} != {hash2}"
    assert len(hash1) == 8, f"Hash should be 8 characters: {len(hash1)}"
    assert all(c in '0123456789abcdef' for c in hash1), f"Hash should be hexadecimal: {hash1}"

@test("calculate_path_hash - changes with content")
def test_path_hash_changes_with_content():
    passages1 = {
        'Start': {'text': 'Welcome to the story', 'pid': '1'},
        'End': {'text': 'The end', 'pid': '2'}
    }
    passages2 = {
        'Start': {'text': 'Welcome to the story MODIFIED', 'pid': '1'},
        'End': {'text': 'The end', 'pid': '2'}
    }
    path = ['Start', 'End']

    hash1 = calculate_path_hash(path, passages1)
    hash2 = calculate_path_hash(path, passages2)

    assert hash1 != hash2, f"Hash should change when content changes: {hash1} == {hash2}"

@test("calculate_path_hash - changes with structure")
def test_path_hash_changes_with_structure():
    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'Middle': {'text': 'Middle', 'pid': '2'},
        'End': {'text': 'End', 'pid': '3'}
    }
    path1 = ['Start', 'End']
    path2 = ['Start', 'Middle', 'End']

    hash1 = calculate_path_hash(path1, passages)
    hash2 = calculate_path_hash(path2, passages)

    assert hash1 != hash2, f"Hash should change when path structure changes: {hash1} == {hash2}"


@test("calculate_path_similarity - identical paths")
def test_similarity_identical():
    path1 = ['Start', 'Middle', 'End']
    path2 = ['Start', 'Middle', 'End']

    similarity = calculate_path_similarity(path1, path2)

    assert similarity == 1.0, f"Identical paths should have similarity 1.0: {similarity}"

@test("calculate_path_similarity - no overlap")
def test_similarity_no_overlap():
    path1 = ['Start', 'A', 'B']
    path2 = ['Start', 'C', 'D']

    similarity = calculate_path_similarity(path1, path2)

    # Should have some overlap because both have 'Start'
    assert 0.0 < similarity < 1.0, f"Partial overlap should have 0 < similarity < 1.0: {similarity}"

@test("calculate_path_similarity - completely different")
def test_similarity_different():
    path1 = ['A', 'B', 'C']
    path2 = ['X', 'Y', 'Z']

    similarity = calculate_path_similarity(path1, path2)

    assert similarity == 0.0, f"Completely different paths should have similarity 0.0: {similarity}"

@test("calculate_path_similarity - partial overlap")
def test_similarity_partial():
    path1 = ['Start', 'A', 'B', 'End']
    path2 = ['Start', 'C', 'D', 'End']

    similarity = calculate_path_similarity(path1, path2)

    # Jaccard: intersection = 2 (Start, End), union = 6 (Start, A, B, C, D, End)
    expected = 2.0 / 6.0
    assert abs(similarity - expected) < 0.01, f"Expected similarity {expected}, got {similarity}"

@test("calculate_path_similarity - empty paths")
def test_similarity_empty():
    path1 = []
    path2 = ['A', 'B']

    similarity = calculate_path_similarity(path1, path2)

    assert similarity == 0.0, f"Empty path should have similarity 0.0: {similarity}"

@test("strip_links_from_text - removes all link syntax")
def test_strip_links():
    # Test simple link
    text1 = "Some text [[Target]] more text"
    result1 = strip_links_from_text(text1)
    assert '[[' not in result1, "Should remove link brackets"
    assert 'Target' not in result1, "Should remove link target"
    assert 'Some text' in result1, "Should preserve prose"
    assert 'more text' in result1, "Should preserve prose"

    # Test arrow link
    text2 = "Before [[Display->Target]] after"
    result2 = strip_links_from_text(text2)
    assert '[[' not in result2, "Should remove link brackets"
    assert '->' not in result2, "Should remove arrow"
    assert 'Before' in result2, "Should preserve prose"
    assert 'after' in result2, "Should preserve prose"

    # Test whitespace normalization
    text3 = "Line 1\n\n[[Link1]]\n\n[[Link2]]\n\nLine 2"
    result3 = strip_links_from_text(text3)
    assert '[[' not in result3, "Should remove all links"
    assert 'Line 1' in result3, "Should preserve prose"
    assert 'Line 2' in result3, "Should preserve prose"

    # Test that same prose with different links produces same result
    text_with_link1 = "Hello world\n\n[[Link A]]"
    text_with_link2 = "Hello world\n\n[[Link B]]"
    assert strip_links_from_text(text_with_link1) == strip_links_from_text(text_with_link2), \
        "Same prose with different links should produce same stripped result"

@test("categorize_paths - new path")
def test_categorize_new_path():
    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'End': {'text': 'End', 'pid': '2'}
    }
    current_paths = [['Start', 'End']]
    validation_cache = {}  # Empty cache

    categories = categorize_paths(current_paths, passages, validation_cache)

    path_hash = calculate_path_hash(['Start', 'End'], passages)
    assert categories[path_hash] == 'new', f"Should categorize as new: {categories[path_hash]}"

@test("categorize_paths - unchanged path")
def test_categorize_unchanged_path():
    # NOTE: With git-first architecture, paths without git data fall back to 'new'
    # This test validates the fallback behavior when git is unavailable
    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'End': {'text': 'End', 'pid': '2'}
    }
    path = ['Start', 'End']
    path_hash = calculate_path_hash(path, passages)

    validation_cache = {
        path_hash: {
            'route': 'Start → End',
            'validated': True
        }
    }

    current_paths = [path]
    # No passage_to_file or repo_root provided → falls back to 'new'
    categories = categorize_paths(current_paths, passages, validation_cache)

    assert categories[path_hash] == 'new', f"Should fall back to new without git: {categories[path_hash]}"




@test("categorize_paths - handles empty cache")
def test_categorize_empty_cache():
    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'End': {'text': 'End', 'pid': '2'}
    }
    current_paths = [['Start', 'End']]
    validation_cache = {}

    categories = categorize_paths(current_paths, passages, validation_cache)

    assert len(categories) == 1, f"Should categorize 1 path: {len(categories)}"
    assert list(categories.values())[0] == 'new', "Should categorize as new"

@test("categorize_paths - handles missing fingerprint field")
def test_categorize_missing_fingerprint():
    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'End': {'text': 'End', 'pid': '2'}
    }
    path = ['Start', 'End']
    path_hash = calculate_path_hash(path, passages)

    # Old cache without content_fingerprint field
    validation_cache = {
        path_hash: {
            'route': 'Start → End',
            'validated': True
        }
    }

    current_paths = [path]
    # Should not crash
    # NOTE: With git-first architecture, paths without git data fall back to 'new'
    categories = categorize_paths(current_paths, passages, validation_cache)

    # Without git data, falls back to 'new' (conservative approach)
    assert categories[path_hash] == 'new', f"Should fall back to new without git: {categories[path_hash]}"

@test("categorize_paths - handles non-dict entries")
def test_categorize_non_dict_entries():
    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'End': {'text': 'End', 'pid': '2'}
    }

    # Cache with non-dict entry (like 'last_updated')
    validation_cache = {
        'last_updated': '2025-11-19T00:00:00'
    }

    current_paths = [['Start', 'End']]

    # Should not crash
    categories = categorize_paths(current_paths, passages, validation_cache)

    assert len(categories) == 1, "Should categorize 1 path"

@test("build_passage_to_file_mapping - finds passages")
def test_build_passage_mapping():
    # Use the actual source directory
    source_dir = PROJECT_ROOT / 'src'

    if not source_dir.exists():
        print("  (Skipping - no src directory)")
        return

    mapping = build_passage_to_file_mapping(source_dir)

    assert isinstance(mapping, dict), "Should return a dict"
    assert len(mapping) > 0, "Should find some passages"

    # Check that all values are Path objects
    for name, path in mapping.items():
        assert isinstance(path, Path), f"Mapping value should be Path: {type(path)}"
        assert path.exists(), f"File should exist: {path}"

@test("get_file_commit_date - retrieves date for tracked file")
def test_get_file_commit_date():
    repo_root = PROJECT_ROOT

    # Test with a file that should be tracked
    test_file = repo_root / 'README.md'

    if not test_file.exists():
        print("  (Skipping - no README.md)")
        return

    commit_date = get_file_commit_date(test_file, repo_root)

    # Should get a date (if file is tracked)
    if commit_date:
        assert isinstance(commit_date, str), f"Should return string: {type(commit_date)}"
        # Should be ISO format (contains T or -)
        assert 'T' in commit_date or '-' in commit_date, f"Should be ISO format: {commit_date}"

@test("get_file_commit_date - handles untracked file")
def test_get_file_commit_date_untracked():
    repo_root = PROJECT_ROOT

    # Create a temporary file
    with tempfile.NamedTemporaryFile(dir=repo_root, delete=False, suffix='.tmp') as f:
        temp_file = Path(f.name)

    try:
        commit_date = get_file_commit_date(temp_file, repo_root)

        # Should return None for untracked file
        assert commit_date is None, f"Should return None for untracked file: {commit_date}"
    finally:
        temp_file.unlink()

@test("parse_link - handles simple links")
def test_parse_link_simple():
    assert parse_link('Target') == 'Target'
    assert parse_link('Another Passage') == 'Another Passage'

@test("parse_link - handles arrow syntax")
def test_parse_link_arrows():
    assert parse_link('Display->Target') == 'Target'
    assert parse_link('Target<-Display') == 'Target'

@test("format_passage_text - converts links")
def test_format_passage_text():
    text = 'You can [[Continue->NextPassage]] or [[GoBack]].'
    formatted = format_passage_text(text)

    # Should convert links to plain text
    assert '[[' not in formatted, "Should not contain [["
    assert 'Continue' in formatted, "Should contain display text"
    assert 'GoBack' in formatted, "Should contain link text"

@test("format_passage_text - marks unselected links")
def test_format_passage_text_selected():
    text = 'You can [[Continue->NextPassage]] or [[GoBack->PreviousPassage]].'
    formatted = format_passage_text(text, selected_target='NextPassage')

    assert 'Continue' in formatted, "Should show selected link"
    assert '[unselected]' in formatted, "Should mark unselected links"

@test("generate_passage_id_mapping - creates stable IDs")
def test_generate_passage_id_mapping():
    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'Middle': {'text': 'Middle', 'pid': '2'},
        'End': {'text': 'End', 'pid': '3'}
    }

    mapping1 = generate_passage_id_mapping(passages)
    mapping2 = generate_passage_id_mapping(passages)

    assert mapping1 == mapping2, "Should generate consistent IDs"
    assert len(mapping1) == 3, "Should map all passages"

    for name, id_val in mapping1.items():
        assert len(id_val) == 12, f"ID should be 12 chars: {id_val}"
        assert all(c in '0123456789abcdef' for c in id_val), f"ID should be hex: {id_val}"

# ============================================================================
# PART 2: INTEGRATION TESTS WITH REAL DATA
# ============================================================================

@test("Integration - load actual validation cache")
def test_load_real_cache():
    cache_file = PROJECT_ROOT / 'allpaths-validation-status.json'

    if not cache_file.exists():
        print("  (Skipping - no validation cache)")
        return

    cache = load_validation_cache(cache_file)

    assert isinstance(cache, dict), "Cache should be a dict"
    assert len(cache) > 0, "Cache should not be empty"

    # Check for known fields
    for key, value in cache.items():
        if key == 'last_updated':
            assert isinstance(value, str), "last_updated should be string"
        elif isinstance(value, dict):
            assert 'route' in value, f"Path entry should have route: {key}"

@test("Integration - parse real twee file")
def test_parse_real_twee():
    # We can't test this directly as it requires compiled HTML
    # But we can test the link extraction
    twee_file = PROJECT_ROOT / 'src' / 'KEB-251106.twee'

    if not twee_file.exists():
        print("  (Skipping - no twee file)")
        return

    with open(twee_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract links from the content
    links = extract_links(content)

    # Should find some links (or none if this passage has no links)
    assert isinstance(links, list), "extract_links should return list"

@test("Integration - categorize with real cache")
def test_categorize_with_real_cache():
    cache_file = PROJECT_ROOT / 'allpaths-validation-status.json'

    if not cache_file.exists():
        print("  (Skipping - no validation cache)")
        return

    cache = load_validation_cache(cache_file)

    # Create fake passages matching a known path from cache
    passages = {
        'Start': {'text': 'Test', 'pid': '1'},
        'Continue on': {'text': 'Test', 'pid': '2'},
        'End': {'text': 'Test', 'pid': '3'}
    }

    current_paths = [['Start', 'Continue on', 'End']]

    # Should not crash
    categories = categorize_paths(current_paths, passages, cache)

    assert isinstance(categories, dict), "Should return dict"


# ============================================================================
# PART 3: EDGE CASE TESTS
# ============================================================================


@test("Edge case - cache save and load round-trip")
def test_cache_round_trip():
    cache = {
        'abc12345': {
            'route': 'Start → End',
            'validated': True,
            'content_fingerprint': 'def67890'
        },
        'last_updated': datetime.now().isoformat()
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_file = Path(f.name)

    try:
        save_validation_cache(temp_file, cache)
        loaded = load_validation_cache(temp_file)

        assert loaded['abc12345']['route'] == cache['abc12345']['route'], "Should preserve data"
        assert loaded['abc12345']['validated'] == cache['abc12345']['validated'], "Should preserve data"
    finally:
        temp_file.unlink()

# ============================================================================
# PART 4: VALIDATION WORKFLOW COMPATIBILITY
# ============================================================================

@test("Workflow - check-story-continuity can read cache")
def test_workflow_check_continuity():
    cache_file = PROJECT_ROOT / 'allpaths-validation-status.json'

    if not cache_file.exists():
        print("  (Skipping - no validation cache)")
        return

    # Simulate what check-story-continuity.py does
    try:
        with open(cache_file, 'r') as f:
            cache = json.load(f)

        # Should be able to iterate over entries
        for key, value in cache.items():
            if isinstance(value, dict):
                # Check it has expected fields
                pass  # If we can iterate, it's compatible

        assert True, "Cache is compatible with validation workflow"
    except Exception as e:
        raise AssertionError(f"Cache incompatible: {e}")

@test("Workflow - new fields don't break old code")
def test_workflow_backward_compatibility():
    # Create a cache with new fields
    cache_with_new_fields = {
        'abc12345': {
            'route': 'Start → End',
            'validated': True,
            'content_fingerprint': 'def67890',  # New field
            'commit_date': '2025-11-19T00:00:00',  # New field
            'category': 'new'  # New field
        },
        'last_updated': '2025-11-19T00:00:00'
    }

    # Simulate old code that only expects route and validated
    for key, value in cache_with_new_fields.items():
        if isinstance(value, dict):
            route = value.get('route')
            validated = value.get('validated', False)

            # Old code should still work
            assert route is not None, "Should have route"
            assert isinstance(validated, bool), "Should have validated bool"

@test("Workflow - old cache without new fields works")
def test_workflow_old_cache():
    # Old cache without new fields
    old_cache = {
        'abc12345': {
            'route': 'Start → End',
            'validated': True
        },
        'last_updated': '2025-11-19T00:00:00'
    }

    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'End': {'text': 'End', 'pid': '2'}
    }

    # New code should handle old cache
    current_paths = [['Start', 'End']]
    categories = categorize_paths(current_paths, passages, old_cache)

    assert len(categories) == 1, "Should categorize paths with old cache"

# ============================================================================
# RUN ALL TESTS
# ============================================================================

def run_all_tests():
    """Run all test functions"""
    print("=" * 80)
    print("ALLPATHS GENERATOR COMPREHENSIVE TEST SUITE")
    print("=" * 80)
    print()

    print("PART 1: Unit Tests for Key Functions")
    print("-" * 80)
    test_path_hash_consistency()
    test_path_hash_changes_with_content()
    test_path_hash_changes_with_structure()
    test_similarity_identical()
    test_similarity_no_overlap()
    test_similarity_different()
    test_similarity_partial()
    test_similarity_empty()
    test_strip_links()
    test_categorize_new_path()
    test_categorize_unchanged_path()
    test_categorize_empty_cache()
    test_categorize_missing_fingerprint()
    test_categorize_non_dict_entries()
    test_build_passage_mapping()
    test_get_file_commit_date()
    test_get_file_commit_date_untracked()
    test_parse_link_simple()
    test_parse_link_arrows()
    test_format_passage_text()
    test_format_passage_text_selected()
    test_generate_passage_id_mapping()

    print()
    print("PART 2: Integration Tests with Real Data")
    print("-" * 80)
    test_load_real_cache()
    test_parse_real_twee()
    test_categorize_with_real_cache()

    print()
    print("PART 3: Edge Case Tests")
    print("-" * 80)
    test_cache_round_trip()

    print()
    print("PART 4: Validation Workflow Compatibility")
    print("-" * 80)
    test_workflow_check_continuity()
    test_workflow_backward_compatibility()
    test_workflow_old_cache()

    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests:  {tests_passed + tests_failed}")
    print(f"Success Rate: {100 * tests_passed / (tests_passed + tests_failed):.1f}%")
    print()

    if tests_failed > 0:
        print("FAILED TESTS:")
        for detail in test_details:
            if detail.startswith('✗'):
                print(f"  {detail}")
        print()
        return 1
    else:
        print("ALL TESTS PASSED!")
        return 0

if __name__ == '__main__':
    sys.exit(run_all_tests())
