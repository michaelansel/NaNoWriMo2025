#!/usr/bin/env python3
"""
Test cases for passage split detection in AllPaths generator.

Tests verify that:
- Splitting passages (same prose) → MODIFIED
- Adding links only → MODIFIED
- Adding new prose → NEW
- No changes → UNCHANGED
"""

import sys
from pathlib import Path

# Add parent directory to path to import generator
sys.path.insert(0, str(Path(__file__).parent))

from generator import (
    strip_links_from_text,
    normalize_prose_for_comparison,
    calculate_content_fingerprint,
    calculate_passage_prose_fingerprint,
    categorize_paths,
)


def test_whitespace_normalization():
    """Test that whitespace normalization handles splits correctly."""
    print("Test 1: Whitespace Normalization")
    print("-" * 50)

    # Original passage
    original = "First part. Second part."

    # After split (with links)
    split_a = "First part. [[Continue]]"
    split_b = "Second part."

    # Strip links
    original_prose = strip_links_from_text(original)
    split_a_prose = strip_links_from_text(split_a)
    split_b_prose = strip_links_from_text(split_b)

    # Join and normalize
    original_normalized = normalize_prose_for_comparison(original_prose)
    split_combined = ' '.join([split_a_prose, split_b_prose])
    split_normalized = normalize_prose_for_comparison(split_combined)

    print(f"Original: {repr(original_prose)}")
    print(f"Original normalized: {repr(original_normalized)}")
    print(f"Split A: {repr(split_a_prose)}")
    print(f"Split B: {repr(split_b_prose)}")
    print(f"Split combined: {repr(split_combined)}")
    print(f"Split normalized: {repr(split_normalized)}")
    print(f"Match: {original_normalized == split_normalized}")

    assert original_normalized == split_normalized, "Normalized prose should match after split"
    print("✓ PASSED\n")


def test_path_fingerprint_split():
    """Test that path-level fingerprints match when passages are split."""
    print("Test 2: Path-Level Fingerprint After Split")
    print("-" * 50)

    # Original path
    passages_before = {
        'A': {'text': 'First part. Second part.', 'pid': '1', 'name': 'A', 'tags': []},
    }
    path_before = ['A']

    # After split
    passages_after = {
        'A': {'text': 'First part. [[Continue->B]]', 'pid': '1', 'name': 'A', 'tags': []},
        'B': {'text': 'Second part.', 'pid': '2', 'name': 'B', 'tags': []},
    }
    path_after = ['A', 'B']

    fp_before = calculate_content_fingerprint(path_before, passages_before)
    fp_after = calculate_content_fingerprint(path_after, passages_after)

    print(f"Path before: {path_before}")
    print(f"Fingerprint: {fp_before}")
    print(f"Path after: {path_after}")
    print(f"Fingerprint: {fp_after}")
    print(f"Match: {fp_before == fp_after}")

    assert fp_before == fp_after, "Path fingerprints should match after split (same prose)"
    print("✓ PASSED\n")


def test_passage_fingerprint_different():
    """Test that individual passage fingerprints differ after split."""
    print("Test 3: Passage-Level Fingerprints After Split")
    print("-" * 50)

    original_text = "First part. Second part."
    split_a_text = "First part. [[Continue]]"
    split_b_text = "Second part."

    fp_original = calculate_passage_prose_fingerprint(original_text)
    fp_split_a = calculate_passage_prose_fingerprint(split_a_text)
    fp_split_b = calculate_passage_prose_fingerprint(split_b_text)

    print(f"Original passage: {repr(original_text)}")
    print(f"  Fingerprint: {fp_original}")
    print(f"Split A: {repr(split_a_text)}")
    print(f"  Fingerprint: {fp_split_a}")
    print(f"Split B: {repr(split_b_text)}")
    print(f"  Fingerprint: {fp_split_b}")
    print(f"A matches original: {fp_split_a == fp_original}")
    print(f"B matches original: {fp_split_b == fp_original}")

    assert fp_split_a != fp_original, "Split passage A should have different fingerprint"
    assert fp_split_b != fp_original, "Split passage B should have different fingerprint"
    print("✓ PASSED (as expected - individual passages differ)\n")


def test_categorize_split_as_modified():
    """Test that splitting a passage is categorized as MODIFIED, not NEW."""
    print("Test 4: Categorize Split as MODIFIED")
    print("-" * 50)

    # Mock old cache with original passage
    old_passages = {
        'A': {'text': 'First part. Second part.', 'pid': '1', 'name': 'A', 'tags': []},
    }
    old_path = ['A']

    validation_cache = {
        'old_hash': {
            'route': 'A',
            'route_hash': 'abc123',
            'content_fingerprint': calculate_content_fingerprint(old_path, old_passages),
            'raw_content_fingerprint': 'xyz789',
            'passage_fingerprints': {
                'A': calculate_passage_prose_fingerprint('First part. Second part.')
            }
        }
    }

    # New passages after split
    new_passages = {
        'A': {'text': 'First part. [[Continue->B]]', 'pid': '1', 'name': 'A', 'tags': []},
        'B': {'text': 'Second part.', 'pid': '2', 'name': 'B', 'tags': []},
    }
    new_paths = [['A', 'B']]

    categories = categorize_paths(new_paths, new_passages, validation_cache)

    print(f"Old path: {old_path}")
    print(f"New path: {new_paths[0]}")
    print(f"Old passage prose FP: {validation_cache['old_hash']['passage_fingerprints']['A']}")
    print(f"Old path prose FP: {validation_cache['old_hash']['content_fingerprint']}")
    print(f"New path prose FP: {calculate_content_fingerprint(new_paths[0], new_passages)}")

    # Get the category for the new path
    from generator import calculate_path_hash
    new_path_hash = calculate_path_hash(new_paths[0], new_passages)
    category = categories.get(new_path_hash, 'unknown')

    print(f"Category: {category}")

    assert category == 'modified', f"Split passage should be MODIFIED, got {category}"
    print("✓ PASSED\n")


def test_categorize_new_prose_as_new():
    """Test that genuinely new prose is categorized as NEW."""
    print("Test 5: Categorize New Prose as NEW")
    print("-" * 50)

    # Mock old cache
    old_passages = {
        'A': {'text': 'Old content.', 'pid': '1', 'name': 'A', 'tags': []},
    }
    old_path = ['A']

    validation_cache = {
        'old_hash': {
            'route': 'A',
            'content_fingerprint': calculate_content_fingerprint(old_path, old_passages),
            'raw_content_fingerprint': 'xyz789',
            'passage_fingerprints': {
                'A': calculate_passage_prose_fingerprint('Old content.')
            }
        }
    }

    # New passage with genuinely new prose
    new_passages = {
        'A': {'text': 'Old content.', 'pid': '1', 'name': 'A', 'tags': []},
        'B': {'text': 'Completely new prose here.', 'pid': '2', 'name': 'B', 'tags': []},
    }
    new_paths = [['A', 'B']]

    categories = categorize_paths(new_paths, new_passages, validation_cache)

    from generator import calculate_path_hash
    new_path_hash = calculate_path_hash(new_paths[0], new_passages)
    category = categories.get(new_path_hash, 'unknown')

    print(f"Old path: {old_path}")
    print(f"New path: {new_paths[0]}")
    print(f"Category: {category}")

    assert category == 'new', f"New prose should be NEW, got {category}"
    print("✓ PASSED\n")


def test_categorize_link_only_as_modified():
    """Test that adding links only (no prose change) is categorized as MODIFIED."""
    print("Test 6: Categorize Link-Only Changes as MODIFIED")
    print("-" * 50)

    # Mock old cache
    old_passages = {
        'A': {'text': 'Some prose here.', 'pid': '1', 'name': 'A', 'tags': []},
    }
    old_path = ['A']

    validation_cache = {
        'old_hash': {
            'route': 'A',
            'route_hash': calculate_content_fingerprint(old_path, old_passages),
            'content_fingerprint': calculate_content_fingerprint(old_path, old_passages),
            'raw_content_fingerprint': 'raw123',
            'passage_fingerprints': {
                'A': calculate_passage_prose_fingerprint('Some prose here.')
            }
        }
    }

    # Same passage but with links added
    new_passages = {
        'A': {'text': 'Some prose here. [[Link->B]]', 'pid': '1', 'name': 'A', 'tags': []},
    }
    new_paths = [['A']]

    categories = categorize_paths(new_paths, new_passages, validation_cache)

    from generator import calculate_path_hash, calculate_raw_content_fingerprint
    new_path_hash = calculate_path_hash(new_paths[0], new_passages)
    category = categories.get(new_path_hash, 'unknown')

    print(f"Old text: {repr(old_passages['A']['text'])}")
    print(f"New text: {repr(new_passages['A']['text'])}")
    print(f"Old prose FP: {validation_cache['old_hash']['content_fingerprint']}")
    print(f"New prose FP: {calculate_content_fingerprint(new_paths[0], new_passages)}")
    print(f"Old raw FP: {validation_cache['old_hash']['raw_content_fingerprint']}")
    print(f"New raw FP: {calculate_raw_content_fingerprint(new_paths[0], new_passages)}")
    print(f"Category: {category}")

    assert category == 'modified', f"Link-only change should be MODIFIED, got {category}"
    print("✓ PASSED\n")


def run_all_tests():
    """Run all test cases."""
    print("=" * 60)
    print("PASSAGE SPLIT DETECTION TEST SUITE")
    print("=" * 60)
    print()

    tests = [
        test_whitespace_normalization,
        test_path_fingerprint_split,
        test_passage_fingerprint_different,
        test_categorize_split_as_modified,
        test_categorize_new_prose_as_new,
        test_categorize_link_only_as_modified,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}\n")
            failed += 1

    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
