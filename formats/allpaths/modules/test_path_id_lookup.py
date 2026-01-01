#!/usr/bin/env python3
"""
Tests for Path ID Lookup Generator

Tests the generation of path-to-ID mappings for runtime lookup in Harlowe.
"""

import pytest
from path_id_lookup import generate_path_id_lookup, generate_javascript_lookup


def test_generate_path_id_lookup_empty():
    """Empty paths should produce empty lookup."""
    paths = []
    passages = {}

    lookup = generate_path_id_lookup(paths, passages)

    assert lookup == {}


def test_generate_path_id_lookup_single_path():
    """Single path should create one lookup entry."""
    paths = [['Start', 'Ending']]
    passages = {
        'Start': {'text': 'Beginning'},
        'Ending': {'text': 'The End'}
    }

    lookup = generate_path_id_lookup(paths, passages)

    # Should have exactly one entry
    assert len(lookup) == 1

    # Key should be the passage sequence joined by →
    assert 'Start→Ending' in lookup

    # Value should be an 8-character hex hash
    path_id = lookup['Start→Ending']
    assert len(path_id) == 8
    assert all(c in '0123456789abcdef' for c in path_id)


def test_generate_path_id_lookup_multiple_paths():
    """Multiple paths should create multiple lookup entries."""
    paths = [
        ['Start', 'Left', 'End1'],
        ['Start', 'Right', 'End2']
    ]
    passages = {
        'Start': {'text': 'Beginning'},
        'Left': {'text': 'Go left'},
        'Right': {'text': 'Go right'},
        'End1': {'text': 'Left ending'},
        'End2': {'text': 'Right ending'}
    }

    lookup = generate_path_id_lookup(paths, passages)

    # Should have two entries
    assert len(lookup) == 2

    # Both paths should be present
    assert 'Start→Left→End1' in lookup
    assert 'Start→Right→End2' in lookup

    # IDs should be different
    assert lookup['Start→Left→End1'] != lookup['Start→Right→End2']


def test_generate_path_id_lookup_consistent_hashing():
    """Same path should always produce same ID."""
    from path_generator import calculate_path_hash

    path = ['Start', 'Middle', 'End']
    passages = {
        'Start': {'text': 'Begin'},
        'Middle': {'text': 'Middle'},
        'End': {'text': 'Finish'}
    }

    # Generate lookup twice
    lookup1 = generate_path_id_lookup([path], passages)
    lookup2 = generate_path_id_lookup([path], passages)

    # Should be identical
    assert lookup1 == lookup2

    # Should match the hash from calculate_path_hash
    expected_id = calculate_path_hash(path, passages)
    assert lookup1['Start→Middle→End'] == expected_id


def test_generate_javascript_lookup_empty():
    """Empty lookup should generate valid empty JavaScript object."""
    lookup = {}

    js = generate_javascript_lookup(lookup)

    # Should contain window.pathIdLookup assignment
    assert 'window.pathIdLookup' in js

    # Should be valid JavaScript (basic check)
    assert js.strip().endswith(';')

    # Should contain empty object
    assert '{}' in js


def test_generate_javascript_lookup_single_entry():
    """Single lookup entry should generate valid JavaScript."""
    lookup = {'Start→End': 'abc12345'}

    js = generate_javascript_lookup(lookup)

    # Should contain the path and ID
    assert 'Start→End' in js
    assert 'abc12345' in js

    # Should be valid JavaScript assignment
    assert 'window.pathIdLookup' in js
    assert js.strip().endswith(';')


def test_generate_javascript_lookup_escapes_special_chars():
    """JavaScript should escape special characters in passage names."""
    # Passage names with quotes and backslashes
    lookup = {"Start→It's here→End": 'abc12345'}

    js = generate_javascript_lookup(lookup)

    # Should not contain unescaped quotes
    # (either escaped or the string is in different quote style)
    assert "It\\'s here" in js or "It's here" in js.split('"')[1]


def test_generate_javascript_lookup_multiple_entries():
    """Multiple lookup entries should all be in generated JavaScript."""
    lookup = {
        'Start→Left→End1': 'aaa11111',
        'Start→Right→End2': 'bbb22222',
        'Start→Middle→End3': 'ccc33333'
    }

    js = generate_javascript_lookup(lookup)

    # All paths should be present
    assert 'Start→Left→End1' in js
    assert 'Start→Right→End2' in js
    assert 'Start→Middle→End3' in js

    # All IDs should be present
    assert 'aaa11111' in js
    assert 'bbb22222' in js
    assert 'ccc33333' in js
