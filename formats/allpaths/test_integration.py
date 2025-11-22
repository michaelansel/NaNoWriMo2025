#!/usr/bin/env python3
"""
Integration and stress tests for the allpaths generator.
Tests the full workflow with real story data.
"""

import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime

# Project root is two directories up from this file (formats/allpaths/)
PROJECT_ROOT = Path(__file__).parent.parent.parent

from generator import (
    parse_story_html,
    build_graph,
    generate_all_paths_dfs,
    calculate_path_hash,
    calculate_content_fingerprint,
    calculate_raw_content_fingerprint,
    calculate_route_hash,
    categorize_paths,
    build_passage_to_file_mapping,
    get_file_commit_date,
    get_path_commit_date,
    generate_html_output,
    generate_path_text,
    generate_passage_id_mapping,
    load_validation_cache,
    save_validation_cache,
)

def create_test_story_html():
    """Create a minimal test story in HTML format"""
    return '''<!DOCTYPE html>
<html>
<head>
    <title>Test Story</title>
</head>
<body>
    <tw-storydata name="Test Story" startnode="1" ifid="test-ifid">
        <tw-passagedata pid="1" name="Start" tags="">
You wake up in a mysterious forest.

[[Go north->North]]
[[Go south->South]]
        </tw-passagedata>
        <tw-passagedata pid="2" name="North" tags="">
You walk north and find a cottage.

[[Enter the cottage->Cottage]]
[[Go back->Start]]
        </tw-passagedata>
        <tw-passagedata pid="3" name="South" tags="">
You walk south and find a river.

[[Cross the river->River]]
[[Go back->Start]]
        </tw-passagedata>
        <tw-passagedata pid="4" name="Cottage" tags="">
Inside the cottage, you find treasure!

This is an ending.
        </tw-passagedata>
        <tw-passagedata pid="5" name="River" tags="">
You cross the river and continue your journey.

[[Continue->Forest]]
        </tw-passagedata>
        <tw-passagedata pid="6" name="Forest" tags="">
You are back in a forest, but this one feels different.

[[Explore->Discovery]]
[[Return->Start]]
        </tw-passagedata>
        <tw-passagedata pid="7" name="Discovery" tags="">
You discover an ancient ruin!

This is an ending.
        </tw-passagedata>
    </tw-storydata>
</body>
</html>'''

def test_full_workflow():
    """Test the complete workflow from HTML to output"""
    print("=" * 80)
    print("INTEGRATION TEST: Full Workflow")
    print("=" * 80)
    print()

    # Step 1: Parse story HTML
    print("Step 1: Parsing story HTML...")
    html_content = create_test_story_html()
    story_data, passages = parse_story_html(html_content)

    print(f"  Story name: {story_data['name']}")
    print(f"  Passages found: {len(passages)}")
    assert len(passages) == 7, f"Expected 7 passages, got {len(passages)}"
    print("  ✓ Story parsed successfully")
    print()

    # Step 2: Build graph
    print("Step 2: Building story graph...")
    graph = build_graph(passages)

    print(f"  Graph nodes: {len(graph)}")
    print(f"  Links from Start: {graph.get('Start', [])}")
    assert 'Start' in graph, "Start passage should be in graph"
    assert len(graph['Start']) == 2, "Start should have 2 choices"
    print("  ✓ Graph built successfully")
    print()

    # Step 3: Generate all paths
    print("Step 3: Generating all paths...")
    all_paths = generate_all_paths_dfs(graph, 'Start')

    print(f"  Total paths: {len(all_paths)}")
    print(f"  Path lengths: {min(len(p) for p in all_paths)}-{max(len(p) for p in all_paths)} passages")
    assert len(all_paths) > 0, "Should generate at least one path"

    # Print all paths
    for i, path in enumerate(all_paths, 1):
        print(f"    Path {i}: {' → '.join(path)}")

    print("  ✓ Paths generated successfully")
    print()

    # Step 4: Calculate hashes and fingerprints
    print("Step 4: Calculating path hashes and fingerprints...")
    path_hashes = {}
    path_fingerprints = {}

    for path in all_paths:
        path_hash = calculate_path_hash(path, passages)
        fingerprint = calculate_content_fingerprint(path, passages)
        path_hashes[tuple(path)] = path_hash
        path_fingerprints[tuple(path)] = fingerprint

    print(f"  Unique hashes: {len(set(path_hashes.values()))}")
    print(f"  Unique fingerprints: {len(set(path_fingerprints.values()))}")

    # All paths should have unique hashes
    assert len(set(path_hashes.values())) == len(all_paths), "All paths should have unique hashes"
    print("  ✓ Hashes calculated successfully")
    print()

    # Step 5: Test categorization (first run - all new)
    print("Step 5: Testing categorization (first run)...")
    empty_cache = {}
    categories = categorize_paths(all_paths, passages, empty_cache)

    new_count = sum(1 for c in categories.values() if c == 'new')
    print(f"  New paths: {new_count}")
    assert new_count == len(all_paths), "All paths should be new on first run"
    print("  ✓ Categorization correct for first run")
    print()

    # Step 6: Simulate a cache with existing paths
    print("Step 6: Testing categorization (with existing cache)...")
    simulated_cache = {}
    for path in all_paths[:2]:  # Mark first 2 paths as existing
        path_hash = calculate_path_hash(path, passages)
        fingerprint = calculate_content_fingerprint(path, passages)
        raw_fingerprint = calculate_raw_content_fingerprint(path, passages)
        route_hash = calculate_route_hash(path)
        simulated_cache[path_hash] = {
            'route': ' → '.join(path),
            'route_hash': route_hash,
            'content_fingerprint': fingerprint,
            'raw_content_fingerprint': raw_fingerprint,
            'validated': True
        }

    categories = categorize_paths(all_paths, passages, simulated_cache)

    unchanged_count = sum(1 for c in categories.values() if c == 'unchanged')
    new_count = sum(1 for c in categories.values() if c == 'new')

    print(f"  Unchanged paths: {unchanged_count}")
    print(f"  New paths: {new_count}")
    assert unchanged_count >= 2, f"Should have at least 2 unchanged paths, got {unchanged_count}"
    print("  ✓ Categorization correct with existing cache")
    print()

    # Step 7: Test passage ID mapping
    print("Step 7: Testing passage ID mapping...")
    id_mapping = generate_passage_id_mapping(passages)

    print(f"  Passages mapped: {len(id_mapping)}")
    print(f"  Sample mappings:")
    for name, id_val in list(id_mapping.items())[:3]:
        print(f"    {name} → {id_val}")

    assert len(id_mapping) == len(passages), "Should map all passages"
    print("  ✓ Passage ID mapping generated")
    print()

    # Step 8: Test text generation with IDs
    print("Step 8: Testing path text generation...")
    first_path = all_paths[0]
    text_with_ids = generate_path_text(first_path, passages, 1, len(all_paths),
                                      passage_id_mapping=id_mapping)

    # Check that passage names are replaced with IDs
    for passage_name in first_path:
        expected_id = id_mapping[passage_name]
        assert f"[PASSAGE: {expected_id}]" in text_with_ids, \
            f"Text should use ID {expected_id} instead of {passage_name}"

    print(f"  Text length: {len(text_with_ids)} characters")
    print("  Sample (first 200 chars):")
    print(f"    {text_with_ids[:200]}...")
    print("  ✓ Path text generated with IDs")
    print()

    # Step 9: Test HTML generation
    print("Step 9: Testing HTML output generation...")
    html_output = generate_html_output(story_data, passages, all_paths,
                                      simulated_cache, categories)

    print(f"  HTML length: {len(html_output)} characters")
    assert '<html' in html_output.lower(), "Should generate valid HTML"
    assert story_data['name'] in html_output, "Should include story name"
    print("  ✓ HTML output generated")
    print()

    # Step 10: Test cache save/load
    print("Step 10: Testing cache save and load...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        cache_file = Path(f.name)

    try:
        # Build a full cache
        full_cache = {}
        for path in all_paths:
            path_hash = calculate_path_hash(path, passages)
            fingerprint = calculate_content_fingerprint(path, passages)
            full_cache[path_hash] = {
                'route': ' → '.join(path),
                'first_seen': datetime.now().isoformat(),
                'validated': False,
                'content_fingerprint': fingerprint,
                'category': categories.get(path_hash, 'new')
            }

        save_validation_cache(cache_file, full_cache)
        loaded_cache = load_validation_cache(cache_file)

        print(f"  Saved {len(full_cache)} entries")
        print(f"  Loaded {len(loaded_cache)} entries")

        # Check that data matches (excluding last_updated)
        for key in full_cache:
            if key != 'last_updated':
                assert key in loaded_cache, f"Missing key {key} after load"
                assert loaded_cache[key]['route'] == full_cache[key]['route'], \
                    f"Route mismatch for {key}"

        print("  ✓ Cache save/load working correctly")
    finally:
        cache_file.unlink()

    print()

def test_stress_scenarios():
    """Test various stress scenarios"""
    print("=" * 80)
    print("STRESS TESTS")
    print("=" * 80)
    print()

    # Scenario 1: Story with cycles
    print("Scenario 1: Story with cycles...")
    html_with_cycle = '''<!DOCTYPE html>
<html><body>
<tw-storydata name="Cycle Test" startnode="1">
    <tw-passagedata pid="1" name="A" tags="">[[Go to B->B]]</tw-passagedata>
    <tw-passagedata pid="2" name="B" tags="">[[Go to C->C]]</tw-passagedata>
    <tw-passagedata pid="3" name="C" tags="">[[Back to A->A]] or [[End->End]]</tw-passagedata>
    <tw-passagedata pid="4" name="End" tags="">The end</tw-passagedata>
</tw-storydata>
</body></html>'''

    story_data, passages = parse_story_html(html_with_cycle)
    graph = build_graph(passages)
    paths = generate_all_paths_dfs(graph, 'A', max_cycles=1)

    print(f"  Paths generated: {len(paths)}")
    print(f"  Max path length: {max(len(p) for p in paths)}")

    # Should handle cycles without infinite loop
    assert len(paths) > 0, "Should generate paths even with cycles"
    assert len(paths) < 100, "Should terminate with max_cycles limit"
    print("  ✓ Cycles handled correctly")
    print()

    # Scenario 2: Content changes
    print("Scenario 2: Detecting content changes...")
    passages_v1 = {
        'Start': {'text': 'Original content', 'pid': '1'},
        'End': {'text': 'The end', 'pid': '2'}
    }
    passages_v2 = {
        'Start': {'text': 'Modified content', 'pid': '1'},
        'End': {'text': 'The end', 'pid': '2'}
    }
    path = ['Start', 'End']

    hash_v1 = calculate_path_hash(path, passages_v1)
    hash_v2 = calculate_path_hash(path, passages_v2)
    fp_v1 = calculate_content_fingerprint(path, passages_v1)
    fp_v2 = calculate_content_fingerprint(path, passages_v2)

    print(f"  Hash changed: {hash_v1 != hash_v2}")
    print(f"  Fingerprint changed: {fp_v1 != fp_v2}")

    assert hash_v1 != hash_v2, "Hash should change with content"
    assert fp_v1 != fp_v2, "Fingerprint should change with content"
    print("  ✓ Content changes detected")
    print()

    # Scenario 3: Passage rename (structure unchanged)
    print("Scenario 3: Passage rename detection...")
    passages_before = {
        'OldName1': {'text': 'Content A', 'pid': '1'},
        'OldName2': {'text': 'Content B', 'pid': '2'}
    }
    passages_after = {
        'NewName1': {'text': 'Content A', 'pid': '1'},
        'NewName2': {'text': 'Content B', 'pid': '2'}
    }
    path_before = ['OldName1', 'OldName2']
    path_after = ['NewName1', 'NewName2']

    hash_before = calculate_path_hash(path_before, passages_before)
    hash_after = calculate_path_hash(path_after, passages_after)
    fp_before = calculate_content_fingerprint(path_before, passages_before)
    fp_after = calculate_content_fingerprint(path_after, passages_after)

    print(f"  Hash changed: {hash_before != hash_after}")
    print(f"  Fingerprint same: {fp_before == fp_after}")

    assert hash_before != hash_after, "Hash should change with passage names"
    assert fp_before == fp_after, "Fingerprint should stay same (content unchanged)"
    print("  ✓ Passage renames detected correctly")
    print()

def test_backward_compatibility():
    """Test compatibility with old validation cache formats"""
    print("=" * 80)
    print("BACKWARD COMPATIBILITY TESTS")
    print("=" * 80)
    print()

    passages = {
        'Start': {'text': 'Welcome', 'pid': '1'},
        'End': {'text': 'End', 'pid': '2'}
    }
    path = ['Start', 'End']
    path_hash = calculate_path_hash(path, passages)

    # Test 1: Old cache (pre-fingerprint)
    print("Test 1: Old cache without fingerprint field...")
    old_cache = {
        path_hash: {
            'route': 'Start → End',
            'validated': True,
            'validated_at': '2025-11-01T00:00:00',
            'validated_by': 'user'
        }
    }

    categories = categorize_paths([path], passages, old_cache)
    print(f"  Category: {categories[path_hash]}")
    # Without fingerprint, should be marked as modified
    assert categories[path_hash] == 'modified', \
        f"Should categorize as modified without fingerprint, got {categories[path_hash]}"
    print("  ✓ Old cache handled correctly")
    print()

    # Test 2: Cache with last_updated as string (not dict)
    print("Test 2: Cache with non-dict entries...")
    mixed_cache = {
        path_hash: {
            'route': 'Start → End',
            'validated': True
        },
        'last_updated': '2025-11-01T00:00:00',
        'version': '1.0'
    }

    # Should not crash
    categories = categorize_paths([path], passages, mixed_cache)
    print(f"  Categories: {len(categories)}")
    assert len(categories) == 1, "Should process valid entries only"
    print("  ✓ Mixed cache handled correctly")
    print()

    # Test 3: Corrupted cache (empty)
    print("Test 3: Empty cache...")
    empty_cache = {}

    categories = categorize_paths([path], passages, empty_cache)
    print(f"  Category: {categories[path_hash]}")
    assert categories[path_hash] == 'new', "Should mark all as new"
    print("  ✓ Empty cache handled correctly")
    print()

def test_real_data():
    """Test with actual project data if available"""
    print("=" * 80)
    print("REAL DATA TESTS")
    print("=" * 80)
    print()

    cache_file = PROJECT_ROOT / 'allpaths-validation-status.json'
    src_dir = PROJECT_ROOT / 'src'
    repo_root = PROJECT_ROOT

    if cache_file.exists():
        print("Test 1: Loading real validation cache...")
        cache = load_validation_cache(cache_file)
        print(f"  Cache entries: {len(cache)}")

        validated_count = sum(1 for v in cache.values()
                            if isinstance(v, dict) and v.get('validated', False))
        print(f"  Validated paths: {validated_count}")

        # Check for new fields
        has_fingerprint = sum(1 for v in cache.values()
                             if isinstance(v, dict) and 'content_fingerprint' in v)
        has_commit_date = sum(1 for v in cache.values()
                             if isinstance(v, dict) and 'commit_date' in v)
        has_category = sum(1 for v in cache.values()
                          if isinstance(v, dict) and 'category' in v)

        print(f"  Entries with fingerprint: {has_fingerprint}")
        print(f"  Entries with commit_date: {has_commit_date}")
        print(f"  Entries with category: {has_category}")
        print("  ✓ Real cache loaded successfully")
        print()

    if src_dir.exists():
        print("Test 2: Building passage-to-file mapping...")
        mapping = build_passage_to_file_mapping(src_dir)
        print(f"  Passages mapped: {len(mapping)}")

        # Show some examples
        print("  Sample mappings:")
        for name, path in list(mapping.items())[:5]:
            print(f"    {name} → {path.name}")

        print("  ✓ Passage mapping built successfully")
        print()

        if len(mapping) > 0:
            print("Test 3: Testing git commit date retrieval...")
            # Test with first passage
            first_passage = list(mapping.keys())[0]
            first_file = mapping[first_passage]

            commit_date = get_file_commit_date(first_file, repo_root)
            print(f"  File: {first_file.name}")
            print(f"  Commit date: {commit_date}")

            if commit_date:
                print("  ✓ Git commit dates working")
            else:
                print("  ! No commit date (file may be untracked)")
            print()

def main():
    """Run all integration tests"""
    try:
        test_full_workflow()
        test_stress_scenarios()
        test_backward_compatibility()
        test_real_data()

        print()
        print("=" * 80)
        print("ALL INTEGRATION TESTS PASSED!")
        print("=" * 80)
        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
