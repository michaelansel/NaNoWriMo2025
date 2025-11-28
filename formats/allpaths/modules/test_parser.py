#!/usr/bin/env python3
"""
Test suite for AllPaths parser module.

Tests the Stage 1 (Parse & Extract) functionality that converts
Tweego-compiled HTML into a clean story_graph data structure.
"""

import sys
import json
from pathlib import Path

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
# TEST DATA
# ============================================================================

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Story</title>
</head>
<body>
    <tw-storydata name="Test Story"
                   ifid="12345678-1234-1234-1234-123456789ABC"
                   startnode="1"
                   format="Harlowe"
                   format-version="3.2.0">
        <tw-passagedata pid="1" name="Start" tags="">
            This is the start passage.
            [[Middle]]
            [[Skip to End->End]]
        </tw-passagedata>
        <tw-passagedata pid="2" name="Middle" tags="">
            You are in the middle.
            [[Continue to End->End]]
        </tw-passagedata>
        <tw-passagedata pid="3" name="End" tags="">
            This is the end.
        </tw-passagedata>
        <tw-passagedata pid="4" name="StoryTitle" tags="">
            Test Story
        </tw-passagedata>
    </tw-storydata>
</body>
</html>
"""

# ============================================================================
# PARSER FUNCTION TESTS
# ============================================================================

@test("parse_story - returns story_graph with required fields")
def test_parse_story_structure():
    from parser import parse_story

    result = parse_story(SAMPLE_HTML)

    # Check required top-level fields
    assert 'passages' in result, "Missing 'passages' field"
    assert 'start_passage' in result, "Missing 'start_passage' field"
    assert 'metadata' in result, "Missing 'metadata' field"

    # Check metadata fields
    assert 'story_title' in result['metadata'], "Missing 'story_title' in metadata"
    assert 'ifid' in result['metadata'], "Missing 'ifid' in metadata"
    assert 'format' in result['metadata'], "Missing 'format' in metadata"
    assert 'format_version' in result['metadata'], "Missing 'format_version' in metadata"

@test("parse_story - extracts correct metadata")
def test_parse_story_metadata():
    from parser import parse_story

    result = parse_story(SAMPLE_HTML)
    metadata = result['metadata']

    assert metadata['story_title'] == "Test Story", f"Wrong story title: {metadata['story_title']}"
    assert metadata['ifid'] == "12345678-1234-1234-1234-123456789ABC", f"Wrong IFID: {metadata['ifid']}"
    assert metadata['format'] == "Harlowe", f"Wrong format: {metadata['format']}"
    assert metadata['format_version'] == "3.2.0", f"Wrong format version: {metadata['format_version']}"

@test("parse_story - extracts passages correctly")
def test_parse_story_passages():
    from parser import parse_story

    result = parse_story(SAMPLE_HTML)
    passages = result['passages']

    # Should have 3 non-special passages (Start, Middle, End)
    # StoryTitle is a special passage and should be excluded
    assert 'Start' in passages, "Missing 'Start' passage"
    assert 'Middle' in passages, "Missing 'Middle' passage"
    assert 'End' in passages, "Missing 'End' passage"
    assert 'StoryTitle' not in passages, "StoryTitle should be filtered out"

@test("parse_story - passage has content and links fields")
def test_parse_story_passage_structure():
    from parser import parse_story

    result = parse_story(SAMPLE_HTML)
    start_passage = result['passages']['Start']

    assert 'content' in start_passage, "Missing 'content' field in passage"
    assert 'links' in start_passage, "Missing 'links' field in passage"
    assert isinstance(start_passage['content'], str), "Content should be a string"
    assert isinstance(start_passage['links'], list), "Links should be a list"

@test("parse_story - extracts links correctly")
def test_parse_story_links():
    from parser import parse_story

    result = parse_story(SAMPLE_HTML)

    # Start passage has two links
    start_links = result['passages']['Start']['links']
    assert len(start_links) == 2, f"Start should have 2 links, got {len(start_links)}"
    assert 'Middle' in start_links, f"Start should link to Middle, got {start_links}"
    assert 'End' in start_links, f"Start should link to End, got {start_links}"

    # Middle passage has one link
    middle_links = result['passages']['Middle']['links']
    assert len(middle_links) == 1, f"Middle should have 1 link, got {len(middle_links)}"
    assert 'End' in middle_links, f"Middle should link to End, got {middle_links}"

    # End passage has no links
    end_links = result['passages']['End']['links']
    assert len(end_links) == 0, f"End should have 0 links, got {len(end_links)}"

@test("parse_story - sets correct start passage")
def test_parse_story_start_passage():
    from parser import parse_story

    result = parse_story(SAMPLE_HTML)

    assert result['start_passage'] == 'Start', f"Wrong start passage: {result['start_passage']}"

@test("parse_story - preserves passage content")
def test_parse_story_content():
    from parser import parse_story

    result = parse_story(SAMPLE_HTML)
    start_content = result['passages']['Start']['content']

    # Content should include the prose
    assert 'This is the start passage' in start_content, "Missing prose content"
    # Content should include links
    assert '[[Middle]]' in start_content, "Missing link in content"

# ============================================================================
# LINK EXTRACTION TESTS
# ============================================================================

@test("extract_links - simple link format")
def test_extract_links_simple():
    from parser import extract_links

    text = "Some text [[Target]] more text"
    links = extract_links(text)

    assert links == ['Target'], f"Expected ['Target'], got {links}"

@test("extract_links - display->target format")
def test_extract_links_display_target():
    from parser import extract_links

    text = "Click [[here->Target]] to continue"
    links = extract_links(text)

    assert links == ['Target'], f"Expected ['Target'], got {links}"

@test("extract_links - target<-display format")
def test_extract_links_target_display():
    from parser import extract_links

    text = "Click [[Target<-here]] to continue"
    links = extract_links(text)

    assert links == ['Target'], f"Expected ['Target'], got {links}"

@test("extract_links - multiple links")
def test_extract_links_multiple():
    from parser import extract_links

    text = "Go [[North]] or [[South]] or [[East->Eastern Path]]"
    links = extract_links(text)

    assert len(links) == 3, f"Expected 3 links, got {len(links)}"
    assert 'North' in links, f"Missing 'North' in {links}"
    assert 'South' in links, f"Missing 'South' in {links}"
    assert 'Eastern Path' in links, f"Missing 'Eastern Path' in {links}"

@test("extract_links - deduplicates links")
def test_extract_links_deduplication():
    from parser import extract_links

    text = "Go [[Target]] or [[Target]] again"
    links = extract_links(text)

    assert links == ['Target'], f"Links should be deduplicated, got {links}"

# ============================================================================
# GRAPH CONSTRUCTION TESTS
# ============================================================================

@test("build_graph - creates adjacency list")
def test_build_graph_structure():
    from parser import build_graph

    passages = {
        'Start': {'text': 'Go [[Middle]]', 'pid': '1'},
        'Middle': {'text': 'Go [[End]]', 'pid': '2'},
        'End': {'text': 'The end.', 'pid': '3'}
    }

    graph = build_graph(passages)

    assert 'Start' in graph, "Missing 'Start' in graph"
    assert 'Middle' in graph, "Missing 'Middle' in graph"
    assert 'End' in graph, "Missing 'End' in graph"

@test("build_graph - filters special passages")
def test_build_graph_filters_special():
    from parser import build_graph

    passages = {
        'Start': {'text': 'Go [[Middle]]', 'pid': '1'},
        'StoryTitle': {'text': 'My Story', 'pid': '2'},
        'StoryData': {'text': '{}', 'pid': '3'},
        'Middle': {'text': 'The end.', 'pid': '4'}
    }

    graph = build_graph(passages)

    assert 'StoryTitle' not in graph, "StoryTitle should be filtered"
    assert 'StoryData' not in graph, "StoryData should be filtered"
    assert 'Start' in graph, "Start should be included"
    assert 'Middle' in graph, "Middle should be included"

# ============================================================================
# EDGE CASES
# ============================================================================

@test("parse_story - handles empty passages")
def test_parse_story_empty_passage():
    html = """
    <tw-storydata name="Test" ifid="12345678-1234-1234-1234-123456789ABC" startnode="1" format="Harlowe" format-version="3.2.0">
        <tw-passagedata pid="1" name="Empty" tags="">
        </tw-passagedata>
    </tw-storydata>
    """

    from parser import parse_story
    result = parse_story(html)

    assert 'Empty' in result['passages'], "Should handle empty passages"
    assert result['passages']['Empty']['content'] == '', "Empty passage should have empty content"
    assert result['passages']['Empty']['links'] == [], "Empty passage should have no links"

@test("parse_story - handles passages with no links")
def test_parse_story_no_links():
    html = """
    <tw-storydata name="Test" ifid="12345678-1234-1234-1234-123456789ABC" startnode="1" format="Harlowe" format-version="3.2.0">
        <tw-passagedata pid="1" name="NoLinks" tags="">
            This passage has no links.
        </tw-passagedata>
    </tw-storydata>
    """

    from parser import parse_story
    result = parse_story(html)

    assert result['passages']['NoLinks']['links'] == [], "Should have empty links array"

@test("extract_links - handles no links")
def test_extract_links_none():
    from parser import extract_links

    text = "This has no links at all"
    links = extract_links(text)

    assert links == [], f"Expected empty list, got {links}"

# ============================================================================
# SCHEMA VALIDATION (bonus test)
# ============================================================================

@test("parse_story - output validates against schema")
def test_parse_story_schema_validation():
    from parser import parse_story

    try:
        import jsonschema
    except ImportError:
        print("    (jsonschema not installed, skipping schema validation)")
        return

    # Load schema
    schema_path = Path(__file__).parent.parent / 'schemas' / 'story_graph.schema.json'
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    result = parse_story(SAMPLE_HTML)

    # This should not raise an exception
    try:
        jsonschema.validate(result, schema)
    except jsonschema.ValidationError as e:
        raise AssertionError(f"Story graph doesn't match schema: {e}")

# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    print("=" * 80)
    print("ALLPATHS PARSER MODULE TESTS")
    print("=" * 80)
    print()

    # Run all tests
    test_parse_story_structure()
    test_parse_story_metadata()
    test_parse_story_passages()
    test_parse_story_passage_structure()
    test_parse_story_links()
    test_parse_story_start_passage()
    test_parse_story_content()

    test_extract_links_simple()
    test_extract_links_display_target()
    test_extract_links_target_display()
    test_extract_links_multiple()
    test_extract_links_deduplication()

    test_build_graph_structure()
    test_build_graph_filters_special()

    test_parse_story_empty_passage()
    test_parse_story_no_links()
    test_extract_links_none()

    test_parse_story_schema_validation()

    # Print summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests:  {tests_passed + tests_failed}")
    print(f"Success Rate: {100 * tests_passed / (tests_passed + tests_failed) if (tests_passed + tests_failed) > 0 else 0:.1f}%")
    print()

    if tests_failed == 0:
        print("ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("SOME TESTS FAILED!")
        print("\nFailed tests:")
        for detail in test_details:
            if detail.startswith("✗"):
                print(f"  {detail}")
        sys.exit(1)
