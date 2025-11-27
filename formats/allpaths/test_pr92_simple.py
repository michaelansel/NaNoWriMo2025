#!/usr/bin/env python3
"""
Simple test for PR #92: Check file-level categorization without full build.

This tests the core categorization logic by checking a sample of reformatted files.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from generator import (
    analyze_file_changes,
    get_file_content_from_git,
    verify_base_ref_accessible,
)


def main():
    print("=" * 80)
    print("Testing File-Level Categorization for PR #92")
    print("=" * 80)
    print()

    repo_root = Path(__file__).parent.parent.parent
    base_ref = '1b917dd'

    print(f"Repository: {repo_root}")
    print(f"Base ref: {base_ref}")
    print()

    # Verify base ref
    if not verify_base_ref_accessible(repo_root, base_ref):
        print("ERROR: Base ref not accessible!")
        sys.exit(1)
    print()

    # Sample files that were reformatted in PR #92
    sample_files = [
        'src/KEB-251101.twee',
        'src/KEB-251102.twee',
        'src/KEB-251112.twee',
        'src/Start.twee',
        'src/mansel-20251112.twee',
    ]

    print("Testing file categorization for sample files:")
    print("-" * 80)
    print()

    results = {
        'is_new': 0,
        'has_prose_changes': 0,
        'has_any_changes': 0,
        'unchanged': 0,
    }

    for file_rel in sample_files:
        file_path = repo_root / file_rel

        print(f"File: {file_rel}")

        # Get git content from base ref
        git_content = get_file_content_from_git(file_path, repo_root, base_ref)

        # Analyze changes
        analysis = analyze_file_changes(file_path, repo_root, git_content)

        print(f"  Result: {analysis['reason']}")

        # Track results
        if analysis['is_new']:
            results['is_new'] += 1
            print(f"  ✗ Categorized as NEW (unexpected for PR #92)")
        elif analysis['has_prose_changes']:
            results['has_prose_changes'] += 1
            print(f"  ✗ Has PROSE changes (unexpected for linter reformats)")
        elif analysis['has_any_changes']:
            results['has_any_changes'] += 1
            print(f"  ✓ Has LINK/STRUCTURE changes only (expected for linter)")
        else:
            results['unchanged'] += 1
            print(f"  ✓ UNCHANGED (possible if not touched by linter)")

        print()

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    print(f"Files checked: {len(sample_files)}")
    print(f"  - NEW (file not in git): {results['is_new']}")
    print(f"  - PROSE changes: {results['has_prose_changes']}")
    print(f"  - LINK/STRUCTURE changes only: {results['has_any_changes']}")
    print(f"  - UNCHANGED: {results['unchanged']}")
    print()

    print("EXPECTATION CHECK:")
    print("-" * 80)
    print("For PR #92 (linter reformats):")
    print("  - All files should have LINK/STRUCTURE changes only (not prose changes)")
    print("  - No files should be NEW")
    print("  - Some files might be UNCHANGED if not touched by linter")
    print()

    # Determine pass/fail
    failed = False

    if results['is_new'] > 0:
        print(f"✗ FAIL: {results['is_new']} files categorized as NEW")
        failed = True

    if results['has_prose_changes'] > 0:
        print(f"✗ FAIL: {results['has_prose_changes']} files have PROSE changes")
        failed = True

    if results['has_any_changes'] > 0:
        print(f"✓ PASS: {results['has_any_changes']} files have LINK/STRUCTURE changes (expected)")

    print()

    # Path categorization implications
    print("PATH CATEGORIZATION IMPLICATIONS:")
    print("-" * 80)
    print("Since files have LINK/STRUCTURE changes only (not prose):")
    print("  → Paths through these files should be categorized as MODIFIED")
    print("  → NO paths should be categorized as NEW")
    print()

    if failed:
        print("TEST FAILED")
        sys.exit(1)
    else:
        print("TEST PASSED")
        sys.exit(0)


if __name__ == '__main__':
    main()
