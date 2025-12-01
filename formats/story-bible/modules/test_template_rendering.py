#!/usr/bin/env python3
"""
Integration test for HTML template rendering with entity-based data.

Tests that the template correctly renders passages and mentions fields.
"""

import sys
from pathlib import Path

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent))

from html_generator import generate_html_output
import tempfile


def test_template_renders_with_entity_data():
    """Test that template renders entity-based character data without errors."""

    # Sample data with entity-first format (passages and mentions)
    categorized_facts = {
        'metadata': {
            'view_type': 'entity_first',
            'generation_mode': 'ai',
            'total_constants': 0,
            'total_variables': 0,
            'total_characters': 2
        },
        'constants': {
            'world_rules': [],
            'setting': [],
            'timeline': []
        },
        'characters': {
            'Marcie': {
                'identity': [
                    {
                        'fact': 'Former member of group',
                        'evidence': [
                            {'passage': 'KEB-251101', 'quote': 'when Marcie was with us'}
                        ]
                    }
                ],
                'zero_action_state': [],
                'variables': [],
                'passages': ['KEB-251101', 'mansel-20251114'],
                'mentions': [
                    {
                        'quote': 'when Marcie was with us',
                        'context': 'dialogue',
                        'passage': 'KEB-251101'
                    },
                    {
                        'quote': 'since we lost Marcie',
                        'context': 'dialogue',
                        'passage': 'mansel-20251114'
                    }
                ]
            },
            'Terence': {
                'identity': [
                    {
                        'fact': 'Group leader',
                        'evidence': [
                            {'passage': 'passage1', 'quote': 'Terence leads the group'}
                        ]
                    }
                ],
                'zero_action_state': [],
                'variables': [],
                'passages': ['passage1'],
                'mentions': [
                    {
                        'quote': 'Terence said we should move on',
                        'context': 'dialogue',
                        'passage': 'passage1'
                    }
                ]
            }
        },
        'variables': {
            'events': [],
            'outcomes': []
        },
        'conflicts': [],
        'per_passage': {}
    }

    # Create temporary output file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        output_path = Path(f.name)

    try:
        # Generate HTML - this should not raise any errors
        generate_html_output(categorized_facts, output_path)

        # Verify file was created
        assert output_path.exists(), "HTML file was not created"

        # Read and verify content
        html_content = output_path.read_text()

        # Check that entity-specific content is rendered
        assert 'Marcie' in html_content, "Character name not found in HTML"
        assert 'Terence' in html_content, "Character name not found in HTML"

        # Check for passage count badges
        assert 'Mentioned in 2 passage' in html_content, "Passage count not found for Marcie"
        assert 'Mentioned in 1 passage' in html_content, "Passage count not found for Terence"

        # Check for passage tags
        assert 'KEB-251101' in html_content, "Passage name not found"
        assert 'mansel-20251114' in html_content, "Passage name not found"

        # Check for mentions section
        assert 'Mentions' in html_content, "Mentions section not found"
        assert 'when Marcie was with us' in html_content, "Mention quote not found"
        assert 'dialogue' in html_content or 'DIALOGUE' in html_content, "Context not found"

        print("✓ Template renders entity-based data correctly")
        print(f"✓ Generated HTML file: {output_path}")
        print(f"✓ File size: {len(html_content)} bytes")

        return True

    finally:
        # Clean up
        if output_path.exists():
            output_path.unlink()


def test_template_backward_compatibility():
    """Test that template still works with old format (no passages/mentions)."""

    # Sample data in old format (no passages or mentions fields)
    categorized_facts = {
        'metadata': {
            'view_type': 'summarized',
            'generation_mode': 'ai',
            'total_constants': 0,
            'total_variables': 0,
            'total_characters': 1
        },
        'constants': {
            'world_rules': [],
            'setting': [],
            'timeline': []
        },
        'characters': {
            'Javlyn': {
                'identity': [
                    {
                        'fact': 'Student at magic academy',
                        'evidence': [
                            {'passage': 'Start', 'quote': 'Javlyn studied magic'}
                        ]
                    }
                ],
                'zero_action_state': [],
                'variables': []
                # No passages or mentions fields
            }
        },
        'variables': {
            'events': [],
            'outcomes': []
        },
        'conflicts': [],
        'per_passage': {}
    }

    # Create temporary output file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
        output_path = Path(f.name)

    try:
        # Generate HTML - should work without passages/mentions
        generate_html_output(categorized_facts, output_path)

        # Verify file was created
        assert output_path.exists(), "HTML file was not created"

        # Read and verify content
        html_content = output_path.read_text()

        # Check that basic content is rendered
        assert 'Javlyn' in html_content, "Character name not found in HTML"
        assert 'Student at magic academy' in html_content, "Identity fact not found"

        # Verify no errors due to missing passages/mentions
        print("✓ Template works with old format (backward compatible)")
        print(f"✓ Generated HTML file: {output_path}")

        return True

    finally:
        # Clean up
        if output_path.exists():
            output_path.unlink()


if __name__ == '__main__':
    try:
        test_template_renders_with_entity_data()
        test_template_backward_compatibility()
        print("\n✓ All integration tests passed!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
