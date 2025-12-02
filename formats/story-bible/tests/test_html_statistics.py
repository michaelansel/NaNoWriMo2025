#!/usr/bin/env python3
"""
Test HTML statistics calculation.

Ensures that metadata.total_constants, total_variables, and total_characters
are correctly calculated from the actual data.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.html_generator import generate_html_output


def test_statistics_calculation():
    """Test that statistics are calculated correctly from cache data."""

    # Create test data matching cache structure
    test_data = {
        'constants': {
            'world_rules': [
                {'fact': 'Rule 1', 'evidence': []}
            ] * 8,
            'setting': [
                {'fact': 'Setting 1', 'evidence': []}
            ] * 599,
            'timeline': [
                {'fact': 'Event 1', 'evidence': []}
            ] * 158
        },
        'characters': {
            f'Character{i}': {
                'identity': [],
                'zero_action_state': [],
                'variables': []
            } for i in range(36)
        },
        'variables': {
            'events': [
                {'fact': 'Event 1', 'evidence': []}
            ] * 5,
            'outcomes': [
                {'fact': 'Outcome 1', 'evidence': []}
            ] * 3
        },
        'conflicts': [],
        'metadata': {}  # Empty metadata
    }

    # Generate HTML to temporary file
    output_path = Path('/tmp/test-story-bible.html')
    generate_html_output(test_data, output_path)

    # Read generated HTML
    html_content = output_path.read_text()

    # Check statistics are displayed correctly
    # Total constants = world_rules + setting + timeline = 8 + 599 + 158 = 765
    expected_constants = 765
    # Total variables = events + outcomes = 5 + 3 = 8
    expected_variables = 8
    # Total characters = 36
    expected_characters = 36

    # Check statistics using regex (handles whitespace variations)
    import re
    stats_match = re.search(r'(\d+)\s+constants,\s*(\d+)\s+variables,\s*(\d+)\s+characters', html_content)

    if not stats_match:
        print(f"FAILED: No statistics found in HTML")
        return False

    actual_constants = int(stats_match.group(1))
    actual_variables = int(stats_match.group(2))
    actual_characters = int(stats_match.group(3))

    if (actual_constants != expected_constants or
        actual_variables != expected_variables or
        actual_characters != expected_characters):
        print(f"FAILED: Statistics don't match expected values")
        print(f"  Constants: {actual_constants} (expected {expected_constants})")
        print(f"  Variables: {actual_variables} (expected {expected_variables})")
        print(f"  Characters: {actual_characters} (expected {expected_characters})")
        return False

    print("PASSED: Statistics calculated correctly")
    print(f"  Constants: {expected_constants}")
    print(f"  Variables: {expected_variables}")
    print(f"  Characters: {expected_characters}")
    return True


if __name__ == '__main__':
    success = test_statistics_calculation()
    sys.exit(0 if success else 1)
