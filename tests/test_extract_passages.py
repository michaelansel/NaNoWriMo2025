#!/usr/bin/env python3
"""
Tests for lib/core/extract_passages.py

Tests the passage extraction functionality that converts story_graph
into passages_deduplicated.json format.
"""

import sys
from pathlib import Path

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.core.extract_passages import extract_passages


def test_extract_passages_basic():
    """Test extracting flat passage list from story graph."""
    story_graph = {
        'passages': {
            'Start': {'content': 'Welcome to the story.', 'links': ['Next']},
            'Next': {'content': 'The end.', 'links': []}
        },
        'start_passage': 'Start',
        'metadata': {'story_title': 'Test Story'}
    }

    result = extract_passages(story_graph)

    # Verify structure
    assert 'passages' in result

    # Verify passage count
    assert len(result['passages']) == 2

    # Verify passage data
    start_passage = next(p for p in result['passages'] if p['name'] == 'Start')
    assert start_passage['content'] == 'Welcome to the story.'
    assert 'content_hash' in start_passage
    assert len(start_passage['content_hash']) > 0

    next_passage = next(p for p in result['passages'] if p['name'] == 'Next')
    assert next_passage['content'] == 'The end.'
    assert 'content_hash' in next_passage


def test_extract_passages_content_hash_stable():
    """Test that content hash is stable for same content."""
    story_graph = {
        'passages': {
            'Passage1': {'content': 'Same content', 'links': []},
            'Passage2': {'content': 'Same content', 'links': []}
        },
        'start_passage': 'Passage1',
        'metadata': {}
    }

    result = extract_passages(story_graph)

    # Same content should produce same hash
    passage1 = next(p for p in result['passages'] if p['name'] == 'Passage1')
    passage2 = next(p for p in result['passages'] if p['name'] == 'Passage2')
    assert passage1['content_hash'] == passage2['content_hash']


def test_extract_passages_content_hash_different():
    """Test that different content produces different hashes."""
    story_graph = {
        'passages': {
            'Passage1': {'content': 'Different content 1', 'links': []},
            'Passage2': {'content': 'Different content 2', 'links': []}
        },
        'start_passage': 'Passage1',
        'metadata': {}
    }

    result = extract_passages(story_graph)

    # Different content should produce different hashes
    passage1 = next(p for p in result['passages'] if p['name'] == 'Passage1')
    passage2 = next(p for p in result['passages'] if p['name'] == 'Passage2')
    assert passage1['content_hash'] != passage2['content_hash']


def test_extract_passages_empty_story():
    """Test extracting from empty story."""
    story_graph = {
        'passages': {},
        'start_passage': 'Start',
        'metadata': {}
    }

    result = extract_passages(story_graph)

    assert result['passages'] == []


def test_extract_passages_preserves_order():
    """Test that passage order is preserved (sorted by name)."""
    story_graph = {
        'passages': {
            'Zebra': {'content': 'Z', 'links': []},
            'Apple': {'content': 'A', 'links': []},
            'Middle': {'content': 'M', 'links': []}
        },
        'start_passage': 'Apple',
        'metadata': {}
    }

    result = extract_passages(story_graph)

    # Should be sorted by name
    names = [p['name'] for p in result['passages']]
    assert names == ['Apple', 'Middle', 'Zebra']


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
