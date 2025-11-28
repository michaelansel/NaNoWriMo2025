#!/usr/bin/env python3
"""
Test suite for path_generator module (Stage 2 of AllPaths pipeline).

Tests path enumeration, route extraction, content mapping, and statistics calculation.
"""

import sys
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.path_generator import (
    generate_paths,
    calculate_path_hash,
    format_passage_text,
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
# UNIT TESTS FOR PATH GENERATOR
# ============================================================================

@test("generate_paths - simple linear story (1 path)")
def test_generate_paths_linear():
    """Test with a simple linear story: Start -> Middle -> End"""
    story_graph = {
        'passages': {
            'Start': {
                'text': 'Welcome to the story',
                'pid': '1',
                'links': ['Middle']
            },
            'Middle': {
                'text': 'You are in the middle',
                'pid': '2',
                'links': ['End']
            },
            'End': {
                'text': 'The end',
                'pid': '3',
                'links': []
            }
        },
        'start_passage': 'Start',
        'metadata': {
            'story_title': 'Test Story',
            'ifid': 'test-123',
            'format': 'Twine',
            'format_version': '2.0'
        }
    }

    result = generate_paths(story_graph)

    # Should have required fields
    assert 'paths' in result, "Result should have 'paths' field"
    assert 'statistics' in result, "Result should have 'statistics' field"

    # Should have exactly 1 path
    assert len(result['paths']) == 1, f"Should have 1 path, got {len(result['paths'])}"

    # Check path structure
    path = result['paths'][0]
    assert 'id' in path, "Path should have 'id' field"
    assert 'route' in path, "Path should have 'route' field"
    assert 'content' in path, "Path should have 'content' field"

    # Check route
    assert path['route'] == ['Start', 'Middle', 'End'], f"Route should be Start->Middle->End, got {path['route']}"

    # Check content mapping
    assert 'Start' in path['content'], "Content should include Start"
    assert 'Middle' in path['content'], "Content should include Middle"
    assert 'End' in path['content'], "Content should include End"
    assert path['content']['Start'] == 'Welcome to the story'

    # Check statistics
    stats = result['statistics']
    assert stats['total_paths'] == 1
    assert stats['total_passages'] == 3
    assert stats['avg_path_length'] == 3.0

@test("generate_paths - branching story (multiple paths)")
def test_generate_paths_branching():
    """Test with a branching story: Start -> A/B -> End"""
    story_graph = {
        'passages': {
            'Start': {
                'text': 'Choose your path',
                'pid': '1',
                'links': ['ChoiceA', 'ChoiceB']
            },
            'ChoiceA': {
                'text': 'You chose A',
                'pid': '2',
                'links': ['End']
            },
            'ChoiceB': {
                'text': 'You chose B',
                'pid': '3',
                'links': ['End']
            },
            'End': {
                'text': 'The end',
                'pid': '4',
                'links': []
            }
        },
        'start_passage': 'Start',
        'metadata': {
            'story_title': 'Branching Story',
            'ifid': 'test-456',
            'format': 'Twine',
            'format_version': '2.0'
        }
    }

    result = generate_paths(story_graph)

    # Should have 2 paths
    assert len(result['paths']) == 2, f"Should have 2 paths, got {len(result['paths'])}"

    # Check routes
    routes = [path['route'] for path in result['paths']]
    assert ['Start', 'ChoiceA', 'End'] in routes, "Should have Start->A->End path"
    assert ['Start', 'ChoiceB', 'End'] in routes, "Should have Start->B->End path"

    # Check statistics
    stats = result['statistics']
    assert stats['total_paths'] == 2
    assert stats['total_passages'] == 4
    assert stats['avg_path_length'] == 3.0  # Both paths have 3 passages

@test("generate_paths - path IDs are unique")
def test_generate_paths_unique_ids():
    """Test that different paths get different IDs"""
    story_graph = {
        'passages': {
            'Start': {
                'text': 'Start',
                'pid': '1',
                'links': ['A', 'B']
            },
            'A': {
                'text': 'Path A',
                'pid': '2',
                'links': []
            },
            'B': {
                'text': 'Path B (different content)',
                'pid': '3',
                'links': []
            }
        },
        'start_passage': 'Start',
        'metadata': {
            'story_title': 'ID Test',
            'ifid': 'test-789',
            'format': 'Twine',
            'format_version': '2.0'
        }
    }

    result = generate_paths(story_graph)

    # Get all path IDs
    path_ids = [path['id'] for path in result['paths']]

    # Should have 2 unique IDs
    assert len(path_ids) == 2, "Should have 2 paths"
    assert len(set(path_ids)) == 2, "Path IDs should be unique"

    # IDs should be 8-character hex strings
    for path_id in path_ids:
        assert len(path_id) == 8, f"Path ID should be 8 chars: {path_id}"
        assert all(c in '0123456789abcdef' for c in path_id), f"Path ID should be hex: {path_id}"

@test("generate_paths - path ID is stable")
def test_generate_paths_stable_ids():
    """Test that same path generates same ID across calls"""
    story_graph = {
        'passages': {
            'Start': {
                'text': 'Start',
                'pid': '1',
                'links': ['End']
            },
            'End': {
                'text': 'End',
                'pid': '2',
                'links': []
            }
        },
        'start_passage': 'Start',
        'metadata': {
            'story_title': 'Stable ID Test',
            'ifid': 'test-stable',
            'format': 'Twine',
            'format_version': '2.0'
        }
    }

    result1 = generate_paths(story_graph)
    result2 = generate_paths(story_graph)

    id1 = result1['paths'][0]['id']
    id2 = result2['paths'][0]['id']

    assert id1 == id2, f"Path ID should be stable: {id1} != {id2}"

@test("generate_paths - detects cycles/loops")
def test_generate_paths_cycles():
    """Test that DFS handles cycles by limiting repetition"""
    story_graph = {
        'passages': {
            'Start': {
                'text': 'Start',
                'pid': '1',
                'links': ['Loop']
            },
            'Loop': {
                'text': 'Loop back',
                'pid': '2',
                'links': ['Start', 'End']  # Loop back to Start
            },
            'End': {
                'text': 'End',
                'pid': '3',
                'links': []
            }
        },
        'start_passage': 'Start',
        'metadata': {
            'story_title': 'Cycle Test',
            'ifid': 'test-cycle',
            'format': 'Twine',
            'format_version': '2.0'
        }
    }

    result = generate_paths(story_graph)

    # Should terminate and not infinite loop
    assert len(result['paths']) > 0, "Should generate at least one path"
    assert len(result['paths']) < 100, "Should not generate excessive paths from cycles"

    # Check that at least one path reaches End
    routes = [path['route'] for path in result['paths']]
    end_paths = [r for r in routes if r[-1] == 'End']
    assert len(end_paths) > 0, "Should have at least one path that reaches End"

@test("generate_paths - empty story")
def test_generate_paths_empty():
    """Test handling of empty story graph"""
    story_graph = {
        'passages': {},
        'start_passage': 'Start',
        'metadata': {
            'story_title': 'Empty Story',
            'ifid': 'test-empty',
            'format': 'Twine',
            'format_version': '2.0'
        }
    }

    result = generate_paths(story_graph)

    # Should handle gracefully
    assert 'paths' in result
    assert 'statistics' in result
    assert result['statistics']['total_paths'] == 0
    assert result['statistics']['total_passages'] == 0

@test("generate_paths - single passage story")
def test_generate_paths_single_passage():
    """Test story with only one passage (no links)"""
    story_graph = {
        'passages': {
            'OnlyPassage': {
                'text': 'The only content',
                'pid': '1',
                'links': []
            }
        },
        'start_passage': 'OnlyPassage',
        'metadata': {
            'story_title': 'Single Passage',
            'ifid': 'test-single',
            'format': 'Twine',
            'format_version': '2.0'
        }
    }

    result = generate_paths(story_graph)

    # Should have exactly 1 path with 1 passage
    assert len(result['paths']) == 1
    assert result['paths'][0]['route'] == ['OnlyPassage']
    assert result['statistics']['total_paths'] == 1
    assert result['statistics']['total_passages'] == 1
    assert result['statistics']['avg_path_length'] == 1.0

@test("calculate_path_hash - consistent hashing")
def test_calculate_path_hash_consistent():
    """Test that path hash function produces consistent results"""
    path = ['Start', 'Middle', 'End']
    passages = {
        'Start': {'text': 'Welcome'},
        'Middle': {'text': 'Middle'},
        'End': {'text': 'End'}
    }

    hash1 = calculate_path_hash(path, passages)
    hash2 = calculate_path_hash(path, passages)

    assert hash1 == hash2, "Hash should be consistent"
    assert len(hash1) == 8, "Hash should be 8 characters"

@test("calculate_path_hash - changes with content")
def test_calculate_path_hash_content_change():
    """Test that hash changes when content changes"""
    path = ['Start', 'End']
    passages1 = {
        'Start': {'text': 'Original'},
        'End': {'text': 'End'}
    }
    passages2 = {
        'Start': {'text': 'Modified'},
        'End': {'text': 'End'}
    }

    hash1 = calculate_path_hash(path, passages1)
    hash2 = calculate_path_hash(path, passages2)

    assert hash1 != hash2, "Hash should change when content changes"

@test("format_passage_text - preserves prose")
def test_format_passage_text_preserves_prose():
    """Test that format_passage_text preserves readable prose"""
    text = 'You can [[Continue->NextPassage]] or [[GoBack]].'
    formatted = format_passage_text(text)

    # Should remove [[ and ]]
    assert '[[' not in formatted
    assert ']]' not in formatted

    # Should preserve readable parts
    assert 'You can' in formatted
    assert 'or' in formatted

# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@test("Integration - validate against JSON schema")
def test_validate_against_schema():
    """Test that generated output matches JSON schema"""
    import jsonschema

    # Load schema
    schema_path = Path(__file__).parent.parent / 'schemas' / 'paths.schema.json'
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    # Generate paths
    story_graph = {
        'passages': {
            'Start': {'text': 'Start', 'pid': '1', 'links': ['End']},
            'End': {'text': 'End', 'pid': '2', 'links': []}
        },
        'start_passage': 'Start',
        'metadata': {
            'story_title': 'Schema Test',
            'ifid': 'test-schema',
            'format': 'Twine',
            'format_version': '2.0'
        }
    }

    result = generate_paths(story_graph)

    # Validate against schema
    try:
        jsonschema.validate(instance=result, schema=schema)
    except jsonschema.ValidationError as e:
        raise AssertionError(f"Generated output doesn't match schema: {e}")

# ============================================================================
# RUN ALL TESTS
# ============================================================================

def run_all_tests():
    """Run all test functions"""
    print("=" * 80)
    print("PATH GENERATOR MODULE TEST SUITE")
    print("=" * 80)
    print()

    # Unit tests
    print("Unit Tests")
    print("-" * 80)
    test_generate_paths_linear()
    test_generate_paths_branching()
    test_generate_paths_unique_ids()
    test_generate_paths_stable_ids()
    test_generate_paths_cycles()
    test_generate_paths_empty()
    test_generate_paths_single_passage()
    test_calculate_path_hash_consistent()
    test_calculate_path_hash_content_change()
    test_format_passage_text_preserves_prose()

    # Integration tests
    print()
    print("Integration Tests")
    print("-" * 80)
    test_validate_against_schema()

    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests:  {tests_passed + tests_failed}")
    if tests_passed + tests_failed > 0:
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
