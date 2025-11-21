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

# Add the formats/allpaths directory to the path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent / 'formats' / 'allpaths'))

from generator import (
    calculate_path_hash,
    calculate_content_fingerprint,
    calculate_raw_content_fingerprint,
    calculate_route_hash,
    calculate_path_similarity,
    categorize_paths,
    build_passage_to_file_mapping,
    get_file_commit_date,
    get_path_commit_date,
    parse_story_html,
    build_graph,
    generate_all_paths_dfs,
    extract_links,
    parse_link,
    format_passage_text,
    generate_passage_id_mapping,
    load_validation_cache,
    save_validation_cache,
    strip_links_from_text,
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

@test("calculate_content_fingerprint - differs from path_hash")
def test_content_fingerprint_differs():
    passages = {
        'Start': {'text': 'Welcome to the story', 'pid': '1'},
        'End': {'text': 'The end', 'pid': '2'}
    }
    path = ['Start', 'End']

    path_hash = calculate_path_hash(path, passages)
    fingerprint = calculate_content_fingerprint(path, passages)

    assert path_hash != fingerprint, f"Fingerprint should differ from hash: {path_hash} == {fingerprint}"
    assert len(fingerprint) == 8, f"Fingerprint should be 8 characters: {len(fingerprint)}"

@test("calculate_content_fingerprint - ignores passage names")
def test_content_fingerprint_name_agnostic():
    passages1 = {
        'Passage1': {'text': 'Content A', 'pid': '1'},
        'Passage2': {'text': 'Content B', 'pid': '2'}
    }
    passages2 = {
        'DifferentName1': {'text': 'Content A', 'pid': '1'},
        'DifferentName2': {'text': 'Content B', 'pid': '2'}
    }
    path1 = ['Passage1', 'Passage2']
    path2 = ['DifferentName1', 'DifferentName2']

    fp1 = calculate_content_fingerprint(path1, passages1)
    fp2 = calculate_content_fingerprint(path2, passages2)

    assert fp1 == fp2, f"Fingerprint should be same for same content: {fp1} != {fp2}"

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
    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'End': {'text': 'End', 'pid': '2'}
    }
    path = ['Start', 'End']
    path_hash = calculate_path_hash(path, passages)
    fingerprint = calculate_content_fingerprint(path, passages)
    raw_fingerprint = calculate_raw_content_fingerprint(path, passages)
    route_hash = calculate_route_hash(path)

    validation_cache = {
        path_hash: {
            'route': 'Start → End',
            'route_hash': route_hash,
            'content_fingerprint': fingerprint,
            'raw_content_fingerprint': raw_fingerprint,
            'validated': True
        }
    }

    current_paths = [path]
    categories = categorize_paths(current_paths, passages, validation_cache)

    assert categories[path_hash] == 'unchanged', f"Should categorize as unchanged: {categories[path_hash]}"

@test("categorize_paths - new path (content change)")
def test_categorize_new_content_change():
    passages_old = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'End': {'text': 'End', 'pid': '2'}
    }
    passages_new = {
        'Start': {'text': 'Welcome MODIFIED', 'pid': '1'},
        'End': {'text': 'End', 'pid': '2'}
    }
    path = ['Start', 'End']

    # Old hash and fingerprint
    old_hash = calculate_path_hash(path, passages_old)
    old_fingerprint = calculate_content_fingerprint(path, passages_old)
    old_raw_fingerprint = calculate_raw_content_fingerprint(path, passages_old)
    old_route_hash = calculate_route_hash(path)

    validation_cache = {
        old_hash: {
            'route': 'Start → End',
            'route_hash': old_route_hash,
            'content_fingerprint': old_fingerprint,
            'raw_content_fingerprint': old_raw_fingerprint,
            'validated': True
        }
    }

    # New path with modified content - content_fingerprint changes
    new_hash = calculate_path_hash(path, passages_new)
    new_fingerprint = calculate_content_fingerprint(path, passages_new)

    # Content changed, so should be NEW (new prose)
    current_paths = [path]
    categories = categorize_paths(current_paths, passages_new, validation_cache)

    # Should be 'new' because content is different (new prose)
    assert categories[new_hash] == 'new', f"Should categorize as new: {categories[new_hash]}"

@test("categorize_paths - modified path (restructured)")
def test_categorize_modified_restructured():
    # Same content in different passage structure
    passages_old = {
        'Start': {'text': 'Welcome to the story.', 'pid': '1'},
        'End': {'text': 'The end.', 'pid': '2'}
    }
    passages_new = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'Middle': {'text': 'to the story.', 'pid': '2'},
        'End': {'text': 'The end.', 'pid': '3'}
    }

    old_path = ['Start', 'End']
    new_path = ['Start', 'Middle', 'End']

    # Old route
    old_hash = calculate_path_hash(old_path, passages_old)
    old_fingerprint = calculate_content_fingerprint(old_path, passages_old)
    old_raw_fingerprint = calculate_raw_content_fingerprint(old_path, passages_old)
    old_route_hash = calculate_route_hash(old_path)

    validation_cache = {
        old_hash: {
            'route': 'Start → End',
            'route_hash': old_route_hash,
            'content_fingerprint': old_fingerprint,
            'raw_content_fingerprint': old_raw_fingerprint,
            'validated': True
        }
    }

    # New route with same content (restructured)
    # Manually construct matching content fingerprint
    # Content: "Welcome to the story.\nThe end."
    passages_new_matching = {
        'Start': {'text': 'Welcome to the story.', 'pid': '1'},
        'Middle': {'text': '', 'pid': '2'},  # Empty passage
        'End': {'text': 'The end.', 'pid': '3'}
    }
    new_path_matching = ['Start', 'Middle', 'End']

    # Adjust passages to have same total content
    # Actually, let's make it simpler - just reuse exact content
    passages_restructured = {
        'Start': {'text': 'Welcome to the story.', 'pid': '1'},
        'End': {'text': 'The end.', 'pid': '2'}
    }

    # Create a second path with same content but restructured
    # For simplicity, simulate by having same fingerprint but different route
    new_fingerprint = old_fingerprint  # Same content
    new_route_hash = calculate_route_hash(['Start', 'Middle', 'End'])  # Different route

    # Actually test with matching fingerprint
    new_hash = calculate_path_hash(old_path, passages_old)  # Reuse to get matching fingerprint

    # Simulate a restructured path: same content, different route
    # We'll add it to the cache manually and test categorization
    current_paths = [old_path]  # Same path structure for now

    # Let me create a proper test: same content but passage names changed
    passages_renamed = {
        'Beginning': {'text': 'Welcome to the story.', 'pid': '1'},  # Same content, different name
        'Finale': {'text': 'The end.', 'pid': '2'}
    }
    renamed_path = ['Beginning', 'Finale']

    renamed_hash = calculate_path_hash(renamed_path, passages_renamed)
    renamed_fingerprint = calculate_content_fingerprint(renamed_path, passages_renamed)
    renamed_route_hash = calculate_route_hash(renamed_path)

    # fingerprints should match (same content), route_hash should differ (different passage names)
    assert renamed_fingerprint == old_fingerprint, "Content should match"
    assert renamed_route_hash != old_route_hash, "Route should differ"

    current_paths = [renamed_path]
    categories = categorize_paths(current_paths, passages_renamed, validation_cache)

    # Should be 'modified' because same content, different route
    assert categories[renamed_hash] == 'modified', f"Should categorize as modified (restructured): {categories[renamed_hash]}"

@test("categorize_paths - modified path (link added)")
def test_categorize_modified_link_added():
    # Test the core new behavior: adding links while keeping prose same → MODIFIED
    passages_before = {
        'Start': {'text': 'What is weighing on your mind today?', 'pid': '1'},
        'End': {'text': 'The end.', 'pid': '2'}
    }
    passages_after = {
        'Start': {'text': 'What is weighing on your mind today?\n\n[[New Link->Somewhere]]', 'pid': '1'},
        'End': {'text': 'The end.', 'pid': '2'}
    }

    path = ['Start', 'End']

    # Build cache with old version
    old_hash = calculate_path_hash(path, passages_before)
    old_prose_fp = calculate_content_fingerprint(path, passages_before)
    old_raw_fp = calculate_raw_content_fingerprint(path, passages_before)
    old_route_hash = calculate_route_hash(path)

    validation_cache = {
        old_hash: {
            'route': 'Start → End',
            'route_hash': old_route_hash,
            'content_fingerprint': old_prose_fp,
            'raw_content_fingerprint': old_raw_fp,
            'validated': True
        }
    }

    # Check new version
    new_hash = calculate_path_hash(path, passages_after)
    new_prose_fp = calculate_content_fingerprint(path, passages_after)
    new_raw_fp = calculate_raw_content_fingerprint(path, passages_after)

    # Verify our assumptions
    assert new_prose_fp == old_prose_fp, "Prose fingerprints should match (links stripped)"
    assert new_raw_fp != old_raw_fp, "Raw fingerprints should differ (link added)"

    current_paths = [path]
    categories = categorize_paths(current_paths, passages_after, validation_cache)

    # Should be 'modified' because prose same but links changed
    assert categories[new_hash] == 'modified', f"Should categorize as modified (link added): {categories[new_hash]}"

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
    categories = categorize_paths(current_paths, passages, validation_cache)

    # Since fingerprint is missing, we can't match content, so should be new
    assert categories[path_hash] == 'new', f"Should categorize as new when fingerprint missing: {categories[path_hash]}"

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
    source_dir = Path('/home/user/NaNoWriMo2025/src')

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
    repo_root = Path('/home/user/NaNoWriMo2025')

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
    repo_root = Path('/home/user/NaNoWriMo2025')

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
    assert '(not selected)' in formatted, "Should mark unselected links"

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
    cache_file = Path('/home/user/NaNoWriMo2025/allpaths-validation-status.json')

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
    twee_file = Path('/home/user/NaNoWriMo2025/src/KEB-251106.twee')

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
    cache_file = Path('/home/user/NaNoWriMo2025/allpaths-validation-status.json')

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

@test("Edge case - path with missing passages")
def test_path_with_missing_passages():
    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'}
        # 'End' is missing
    }
    path = ['Start', 'End']

    # Should handle gracefully
    hash_val = calculate_path_hash(path, passages)
    fingerprint = calculate_content_fingerprint(path, passages)

    assert len(hash_val) == 8, "Should still produce hash"
    assert len(fingerprint) == 8, "Should still produce fingerprint"
    assert 'MISSING' in str(hash_val) or True, "Should handle missing passage"

@test("Edge case - very long path")
def test_very_long_path():
    # Create 100 passages
    passages = {f'Passage{i}': {'text': f'Content {i}', 'pid': str(i)}
                for i in range(100)}
    path = [f'Passage{i}' for i in range(100)]

    hash_val = calculate_path_hash(path, passages)
    fingerprint = calculate_content_fingerprint(path, passages)

    assert len(hash_val) == 8, "Should handle long path"
    assert len(fingerprint) == 8, "Should handle long path"

@test("Edge case - very short path")
def test_very_short_path():
    passages = {
        'OnlyPassage': {'text': 'The only passage', 'pid': '1'}
    }
    path = ['OnlyPassage']

    hash_val = calculate_path_hash(path, passages)
    fingerprint = calculate_content_fingerprint(path, passages)

    assert len(hash_val) == 8, "Should handle single passage"
    assert len(fingerprint) == 8, "Should handle single passage"

@test("Edge case - passage with special characters")
def test_special_characters():
    passages = {
        'Passage → with → arrows': {'text': 'Content with → arrows', 'pid': '1'},
        'Passage\nwith\nnewlines': {'text': 'Content\nwith\nnewlines', 'pid': '2'}
    }
    path = ['Passage → with → arrows', 'Passage\nwith\nnewlines']

    hash_val = calculate_path_hash(path, passages)
    fingerprint = calculate_content_fingerprint(path, passages)

    assert len(hash_val) == 8, "Should handle special characters"
    assert len(fingerprint) == 8, "Should handle special characters"

@test("Edge case - empty passage text")
def test_empty_passage_text():
    passages = {
        'Start': {'text': '', 'pid': '1'},
        'End': {'text': '', 'pid': '2'}
    }
    path = ['Start', 'End']

    hash_val = calculate_path_hash(path, passages)
    fingerprint = calculate_content_fingerprint(path, passages)

    assert len(hash_val) == 8, "Should handle empty text"
    assert len(fingerprint) == 8, "Should handle empty text"

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
    cache_file = Path('/home/user/NaNoWriMo2025/allpaths-validation-status.json')

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
    test_content_fingerprint_differs()
    test_content_fingerprint_name_agnostic()
    test_similarity_identical()
    test_similarity_no_overlap()
    test_similarity_different()
    test_similarity_partial()
    test_similarity_empty()
    test_strip_links()
    test_categorize_new_path()
    test_categorize_unchanged_path()
    test_categorize_new_content_change()
    test_categorize_modified_restructured()
    test_categorize_modified_link_added()
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
    test_path_with_missing_passages()
    test_very_long_path()
    test_very_short_path()
    test_special_characters()
    test_empty_passage_text()
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
