#!/usr/bin/env python3
"""
Integration test for Story Bible validation in continuity checking.

Tests the end-to-end flow of Story Bible validation without requiring Ollama.
"""

import sys
from pathlib import Path

# Add services/lib to path
sys.path.insert(0, str(Path(__file__).parent))

from story_bible_validator import (
    format_constants_for_validation,
    merge_validation_results
)


def test_integration_flow():
    """Test the complete flow of Story Bible validation integration."""

    print("Testing Story Bible Phase 3 Integration")
    print("=" * 60)

    # Simulate Story Bible cache with constants
    story_bible_cache = {
        'categorized_facts': {
            'constants': {
                'world_rules': [
                    {
                        'fact': 'Magic requires verbal incantations',
                        'evidence': 'She spoke the spell aloud'
                    }
                ],
                'setting': [
                    {
                        'fact': 'The academy is located on a mountain',
                        'evidence': 'Looking down from the academy grounds'
                    }
                ],
                'timeline': [
                    {
                        'fact': 'The war ended 10 years ago',
                        'evidence': 'A decade had passed since the ceasefire'
                    }
                ]
            }
        }
    }

    print("\n1. Formatting constants for validation prompt...")
    formatted = format_constants_for_validation(story_bible_cache)
    print(formatted)
    assert '**World Rules:**' in formatted
    assert 'Magic requires verbal incantations' in formatted
    assert '**Setting:**' in formatted
    assert '**Timeline:**' in formatted
    print("✓ Constants formatted correctly")

    print("\n2. Testing result merging...")

    # Test case: Path has issues, world has violations
    path_result = {
        'has_issues': True,
        'severity': 'minor',
        'issues': [
            {
                'type': 'character',
                'severity': 'minor',
                'description': 'Name spelling inconsistency'
            }
        ],
        'summary': 'Minor character consistency issue'
    }

    world_result = {
        'has_violations': True,
        'severity': 'critical',
        'violations': [
            {
                'type': 'world_rule',
                'severity': 'critical',
                'description': 'Magic system contradiction',
                'constant_fact': 'Magic requires verbal incantations',
                'passage_statement': 'She cast the spell silently'
            }
        ],
        'summary': 'Critical world contradiction detected'
    }

    merged = merge_validation_results(path_result, world_result)

    assert merged['has_issues'] == True
    assert merged['severity'] == 'critical'  # Max of minor and critical
    assert merged['world_validation'] is not None
    assert merged['world_validation']['has_violations'] == True
    print("✓ Results merged correctly (combined severity: critical)")

    # Test case: Both clean
    print("\n3. Testing clean results merge...")
    clean_path = {
        'has_issues': False,
        'severity': 'none',
        'issues': [],
        'summary': 'No issues'
    }
    clean_world = {
        'has_violations': False,
        'severity': 'none',
        'violations': [],
        'summary': 'No violations'
    }

    clean_merged = merge_validation_results(clean_path, clean_world)
    assert clean_merged['has_issues'] == False
    assert clean_merged['severity'] == 'none'
    print("✓ Clean results merged correctly")

    # Test case: No world validation
    print("\n4. Testing without world validation...")
    no_world = merge_validation_results(path_result, None)
    assert no_world['world_validation'] is None
    assert no_world['severity'] == 'minor'  # Unchanged from path
    print("✓ Handles missing world validation correctly")

    print("\n" + "=" * 60)
    print("✅ All integration tests passed!")
    print("\nPhase 3 Story Bible validation is ready for deployment.")
    print("\nNext steps:")
    print("  1. Deploy webhook service with Phase 3 integration")
    print("  2. Test with real Story Bible cache on PR branch")
    print("  3. Verify combined PR comments include world validation")


if __name__ == '__main__':
    test_integration_flow()
