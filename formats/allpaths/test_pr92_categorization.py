#!/usr/bin/env python3
"""
Test path categorization for PR #92 (passage formatting linter).

PR #92 reformats 30+ twee files with:
- Smart quotes → ASCII quotes
- Trailing whitespace removal
- Blank line cleanup between link blocks

According to the spec, all paths through reformatted files should be MODIFIED (not NEW).
"""

import sys
import subprocess
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from generator import (
    parse_story_html,
    build_graph,
    generate_all_paths_dfs,
    calculate_path_hash,
    build_passage_to_file_mapping,
    categorize_paths,
    verify_base_ref_accessible,
)


def main():
    print("=" * 80)
    print("Testing Path Categorization for PR #92 (Passage Formatting Linter)")
    print("=" * 80)
    print()

    # Get repository root
    repo_root = Path(__file__).parent.parent.parent
    print(f"Repository root: {repo_root}")

    # Verify we're on pr-92 branch
    result = subprocess.run(
        ['git', 'branch', '--show-current'],
        cwd=repo_root,
        capture_output=True,
        text=True
    )
    current_branch = result.stdout.strip()
    print(f"Current branch: {current_branch}")

    if current_branch != 'pr-92':
        print(f"ERROR: Expected to be on pr-92 branch, but on {current_branch}")
        sys.exit(1)

    # Base commit for comparison (parent of PR)
    base_ref = '1b917dd'
    print(f"Base ref: {base_ref}")
    print()

    # Verify base ref is accessible
    print("Verifying base ref accessibility...")
    if not verify_base_ref_accessible(repo_root, base_ref):
        print("ERROR: Base ref not accessible!")
        sys.exit(1)
    print()

    # Build the story HTML from current state (pr-92 branch)
    print("Building story from current state (pr-92 branch)...")
    dist_dir = repo_root / 'dist'
    story_html = dist_dir / 'story.html'

    # Check if story.html exists, if not we need to build it
    if not story_html.exists():
        print("story.html not found, building...")
        result = subprocess.run(
            ['make', 'build'],
            cwd=repo_root,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print("ERROR: Failed to build story")
            print(result.stderr)
            sys.exit(1)

    # Parse the story
    with open(story_html, 'r', encoding='utf-8') as f:
        html_content = f.read()

    story_data, passages = parse_story_html(html_content)
    print(f"Parsed story: {story_data['name']}")
    print(f"Total passages: {len(passages)}")

    # Build graph and generate paths
    graph = build_graph(passages)

    # Find start passage
    start_passage = None
    for name, passage in passages.items():
        if passage['pid'] == story_data['start']:
            start_passage = name
            break

    if not start_passage:
        start_passage = 'Start'

    print(f"Start passage: {start_passage}")

    # Generate all paths
    print("Generating all paths...")
    all_paths = generate_all_paths_dfs(graph, start_passage)
    print(f"Total paths: {len(all_paths)}")
    print()

    # Build passage-to-file mapping
    source_dir = repo_root / 'src'
    passage_to_file = build_passage_to_file_mapping(source_dir)
    print(f"Passage-to-file mapping: {len(passage_to_file)} passages")
    print()

    # Categorize paths using git-based detection
    print("Categorizing paths with base_ref='1b917dd'...")
    print("-" * 80)

    # Empty validation cache (we don't care about previous validations)
    validation_cache = {}

    # Run categorization
    categories = categorize_paths(
        all_paths,
        passages,
        validation_cache,
        passage_to_file,
        repo_root,
        base_ref
    )

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    # Count categories
    new_count = sum(1 for c in categories.values() if c == 'new')
    modified_count = sum(1 for c in categories.values() if c == 'modified')
    unchanged_count = sum(1 for c in categories.values() if c == 'unchanged')

    print(f"NEW paths:       {new_count}")
    print(f"MODIFIED paths:  {modified_count}")
    print(f"UNCHANGED paths: {unchanged_count}")
    print(f"TOTAL:           {len(categories)}")
    print()

    # Expectation check
    print("EXPECTATION CHECK:")
    print("-" * 80)
    print("According to the continuity spec:")
    print("  - Linter reformats (smart quotes, spacing) should produce MODIFIED paths")
    print("  - NO paths should be categorized as NEW (no new prose content)")
    print()

    if new_count == 0:
        print("✓ PASS: No paths categorized as NEW (expected)")
    else:
        print(f"✗ FAIL: {new_count} paths categorized as NEW (unexpected)")
        print()
        print("Sample of incorrectly categorized NEW paths:")
        for i, (path_hash, category) in enumerate(categories.items()):
            if category == 'new' and i < 5:
                # Find the path
                for path in all_paths:
                    if calculate_path_hash(path, passages) == path_hash:
                        print(f"  - {' → '.join(path[:3])}{'...' if len(path) > 3 else ''}")
                        break

    if modified_count > 0:
        print(f"✓ PASS: {modified_count} paths categorized as MODIFIED (expected)")
    else:
        print("✗ FAIL: No paths categorized as MODIFIED (unexpected)")

    print()

    # Show sample paths by category
    print("SAMPLE PATHS BY CATEGORY:")
    print("-" * 80)

    for category_name in ['new', 'modified', 'unchanged']:
        sample_count = 0
        print(f"\n{category_name.upper()}:")
        for path in all_paths:
            path_hash = calculate_path_hash(path, passages)
            if categories.get(path_hash) == category_name:
                if sample_count < 3:
                    route = ' → '.join(path[:3]) + ('...' if len(path) > 3 else '')
                    print(f"  - {route}")
                    sample_count += 1
        if sample_count == 0:
            print("  (none)")

    print()
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

    # Exit with error if expectations not met
    if new_count > 0 or modified_count == 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
