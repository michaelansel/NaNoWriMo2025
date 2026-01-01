#!/usr/bin/env python3
"""
Tests for generate-path-lookup.py script
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
import sys
import subprocess


def create_test_story_graph(temp_dir: Path):
    """Create a minimal story_graph.json for testing."""
    story_graph = {
        'start_passage': 'Start',
        'passages': {
            'Start': {
                'content': 'Beginning.\n\n[[Go left->Left]]\n[[Go right->Right]]'
            },
            'Left': {
                'content': 'You went left.\n\n[[End1]]'
            },
            'Right': {
                'content': 'You went right.\n\n[[End2]]'
            },
            'End1': {
                'content': 'Left ending (no links).'
            },
            'End2': {
                'content': 'Right ending (no links).'
            }
        },
        'metadata': {
            'story_title': 'Test Story',
            'ifid': 'test-123',
            'format': 'Harlowe',
            'format_version': '3.3.9'
        }
    }

    # Create lib/artifacts directory structure
    artifacts_dir = temp_dir / 'lib' / 'artifacts'
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Write story_graph.json
    story_graph_path = artifacts_dir / 'story_graph.json'
    with open(story_graph_path, 'w', encoding='utf-8') as f:
        json.dump(story_graph, f, indent=2)

    return story_graph_path


def test_generate_path_lookup_integration(tmp_path):
    """Integration test: run the script and verify output."""
    # Setup: Create test directory structure
    test_project_dir = tmp_path / 'test_project'
    test_project_dir.mkdir()

    # Create story_graph.json
    create_test_story_graph(test_project_dir)

    # Create src directory
    src_dir = test_project_dir / 'src'
    src_dir.mkdir()

    # Run the script (simulating from project root)
    script_path = Path(__file__).parent / 'generate-path-lookup.py'

    # Temporarily change to test directory
    import os
    old_cwd = os.getcwd()
    try:
        os.chdir(test_project_dir)

        # Run script
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True
        )

        # Verify script succeeded
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Verify output file exists
        output_path = src_dir / 'PathIdLookup.twee'
        assert output_path.exists(), "PathIdLookup.twee was not created"

        # Read and verify content
        with open(output_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Should contain Twee passage header
        assert ':: PathIdLookup [script]' in content

        # Should contain script tag
        assert '<script>' in content
        assert '</script>' in content

        # Should contain window.pathIdLookup
        assert 'window.pathIdLookup' in content

        # Should contain window.getPathId helper
        assert 'window.getPathId' in content

        # Should contain both paths
        assert 'Start→Left→End1' in content
        assert 'Start→Right→End2' in content

        # Verify it's valid JavaScript (basic check)
        assert content.count('<script>') == content.count('</script>')

    finally:
        os.chdir(old_cwd)


def test_generate_path_lookup_error_no_story_graph():
    """Script should error gracefully if story_graph.json doesn't exist."""
    # Create temp directory without story_graph.json
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create empty lib/artifacts
        artifacts_dir = test_dir / 'lib' / 'artifacts'
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        script_path = Path(__file__).parent / 'generate-path-lookup.py'

        # Run script from empty directory
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(test_dir)

            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True
            )

            # Should exit with error
            assert result.returncode != 0

            # Error message should mention missing artifact
            assert 'not found' in result.stderr or 'Error' in result.stderr

        finally:
            os.chdir(old_cwd)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
