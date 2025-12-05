#!/usr/bin/env python3
"""
Tests for lib/core/build_mappings.py

Tests the passage mapping functionality that builds name/ID/file mappings.
"""

import sys
import tempfile
from pathlib import Path

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.core.build_mappings import build_mappings


def test_build_mappings_basic():
    """Test building basic passage mappings."""
    story_graph = {
        'passages': {
            'Start': {'content': 'Welcome', 'links': []},
            'Continue': {'content': 'Next', 'links': []},
            'End': {'content': 'The end', 'links': []}
        },
        'start_passage': 'Start',
        'metadata': {}
    }

    # Create temporary source directory with Twee files
    with tempfile.TemporaryDirectory() as tmpdir:
        src_dir = Path(tmpdir) / 'src'
        src_dir.mkdir()

        # Create Start.twee
        (src_dir / 'Start.twee').write_text(""":: Start
Welcome""")

        # Create Story.twee with Continue and End
        (src_dir / 'Story.twee').write_text(""":: Continue
Next

:: End
The end""")

        result = build_mappings(story_graph, src_dir)

        # Verify structure
        assert 'by_name' in result
        assert 'by_id' in result
        assert 'by_file' in result

        # Verify by_name mapping
        assert 'Start' in result['by_name']
        assert result['by_name']['Start']['file'] == 'src/Start.twee'
        assert result['by_name']['Start']['line'] == 1

        assert 'Continue' in result['by_name']
        assert result['by_name']['Continue']['file'] == 'src/Story.twee'

        # Verify by_file mapping
        assert 'src/Start.twee' in result['by_file']
        assert any(p['name'] == 'Start' for p in result['by_file']['src/Start.twee'])


def test_build_mappings_no_source_files():
    """Test building mappings when source files don't exist."""
    story_graph = {
        'passages': {
            'Start': {'content': 'Welcome', 'links': []}
        },
        'start_passage': 'Start',
        'metadata': {}
    }

    # Use non-existent source directory
    result = build_mappings(story_graph, Path('/nonexistent'))

    # Should still return valid structure, but with no file mappings
    assert 'by_name' in result
    assert 'by_id' in result
    assert 'by_file' in result

    # Passage should exist but without file info
    assert 'Start' in result['by_name']
    # File info may be None or missing


def test_build_mappings_empty_story():
    """Test building mappings for empty story."""
    story_graph = {
        'passages': {},
        'start_passage': 'Start',
        'metadata': {}
    }

    result = build_mappings(story_graph)

    assert result['by_name'] == {}
    assert result['by_id'] == {}
    assert result['by_file'] == {}


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
