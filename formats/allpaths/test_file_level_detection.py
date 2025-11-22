#!/usr/bin/env python3
"""
Test file-level git diff detection for passage splits.

Creates actual test files and uses git to verify the implementation works.
"""

import sys
import tempfile
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from generator import (
    get_file_content_from_git,
    file_has_prose_changes,
    normalize_prose_for_comparison,
    strip_links_from_text,
)
import subprocess


def setup_test_repo():
    """Create a temporary git repo with test files."""
    test_dir = Path(tempfile.mkdtemp())

    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=test_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=test_dir, check=True, capture_output=True)
    subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=test_dir, check=True, capture_output=True)
    # Disable commit signing for test repos
    subprocess.run(['git', 'config', 'commit.gpgsign', 'false'], cwd=test_dir, check=True, capture_output=True)

    return test_dir


def test_git_file_retrieval():
    """Test that we can retrieve file content from git."""
    print("Test 1: Git File Retrieval")
    print("-" * 70)

    test_dir = setup_test_repo()

    try:
        # Create and commit a file
        test_file = test_dir / 'test.twee'
        test_file.write_text(':: Passage\nSome prose here.')

        subprocess.run(['git', 'add', 'test.twee'], cwd=test_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial'], cwd=test_dir, check=True, capture_output=True)

        # Retrieve from git
        content = get_file_content_from_git(test_file, test_dir)

        print(f"Original content: {repr(test_file.read_text())}")
        print(f"Git content: {repr(content)}")
        print(f"Match: {content == test_file.read_text()}")

        assert content == test_file.read_text(), "Git content should match file"
        print("✓ PASSED\n")

    finally:
        shutil.rmtree(test_dir)


def test_split_detection_no_prose_change():
    """Test that splitting a passage (same prose) is detected as no prose change."""
    print("Test 2: Split Detection - No Prose Change")
    print("-" * 70)

    test_dir = setup_test_repo()

    try:
        test_file = test_dir / 'mansel.twee'

        # Create initial file (before split)
        before_content = ''':: mansel-20251112

The laundry story.

"Okay, just hang tight and I'll bring something back", she said gently.

As she collected an armful of various snacks, Javlyn pondered what to do.'''

        test_file.write_text(before_content)
        subprocess.run(['git', 'add', 'mansel.twee'], cwd=test_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Before split'], cwd=test_dir, check=True, capture_output=True)

        # Modify file (after split - add links and passage marker)
        after_content = ''':: mansel-20251112

The laundry story.

"Okay, just hang tight and I'll bring something back", she said gently.

[[Collect snacks]]
[[Empty kitchen->Day 21 KEB]]

::Collect snacks

As she collected an armful of various snacks, Javlyn pondered what to do.'''

        test_file.write_text(after_content)

        # Check for prose changes
        has_changes = file_has_prose_changes(test_file, test_dir)

        # Verify prose is the same
        old_content = get_file_content_from_git(test_file, test_dir)
        old_prose = normalize_prose_for_comparison(strip_links_from_text(old_content))
        new_prose = normalize_prose_for_comparison(strip_links_from_text(after_content))

        print(f"Old prose: {old_prose[:80]}...")
        print(f"New prose: {new_prose[:80]}...")
        print(f"Prose match: {old_prose == new_prose}")
        print(f"Has prose changes: {has_changes}")
        print(f"Expected: False (no genuine prose changes)")

        assert old_prose == new_prose, "Prose should be identical after normalization"
        assert not has_changes, "Should detect no prose changes (only split/links)"
        print("✓ PASSED\n")

    finally:
        shutil.rmtree(test_dir)


def test_genuine_prose_addition():
    """Test that adding genuinely new prose is detected."""
    print("Test 3: Genuine Prose Addition")
    print("-" * 70)

    test_dir = setup_test_repo()

    try:
        test_file = test_dir / 'story.twee'

        # Create initial file
        before_content = ''':: Start
Some initial prose.'''

        test_file.write_text(before_content)
        subprocess.run(['git', 'add', 'story.twee'], cwd=test_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial'], cwd=test_dir, check=True, capture_output=True)

        # Add genuinely new prose
        after_content = ''':: Start
Some initial prose.

This is completely new prose that didn't exist before.'''

        test_file.write_text(after_content)

        # Check for prose changes
        has_changes = file_has_prose_changes(test_file, test_dir)

        old_content = get_file_content_from_git(test_file, test_dir)
        old_prose = normalize_prose_for_comparison(strip_links_from_text(old_content))
        new_prose = normalize_prose_for_comparison(strip_links_from_text(after_content))

        print(f"Old prose: {repr(old_prose)}")
        print(f"New prose: {repr(new_prose)}")
        print(f"Prose match: {old_prose == new_prose}")
        print(f"Has prose changes: {has_changes}")
        print(f"Expected: True (genuinely new prose)")

        assert old_prose != new_prose, "Prose should be different"
        assert has_changes, "Should detect prose changes"
        print("✓ PASSED\n")

    finally:
        shutil.rmtree(test_dir)


def test_link_only_changes():
    """Test that adding only links (no prose change) is detected correctly."""
    print("Test 4: Link-Only Changes")
    print("-" * 70)

    test_dir = setup_test_repo()

    try:
        test_file = test_dir / 'story.twee'

        # Create initial file
        before_content = ''':: Start
Some prose here.'''

        test_file.write_text(before_content)
        subprocess.run(['git', 'add', 'story.twee'], cwd=test_dir, check=True, capture_output=True)
        subprocess.run(['git', 'commit', '-m', 'Initial'], cwd=test_dir, check=True, capture_output=True)

        # Add only links
        after_content = ''':: Start
Some prose here.

[[Link to somewhere]]
[[Another link->Elsewhere]]'''

        test_file.write_text(after_content)

        # Check for prose changes
        has_changes = file_has_prose_changes(test_file, test_dir)

        old_content = get_file_content_from_git(test_file, test_dir)
        old_prose = normalize_prose_for_comparison(strip_links_from_text(old_content))
        new_prose = normalize_prose_for_comparison(strip_links_from_text(after_content))

        print(f"Old prose: {repr(old_prose)}")
        print(f"New prose: {repr(new_prose)}")
        print(f"Prose match: {old_prose == new_prose}")
        print(f"Has prose changes: {has_changes}")
        print(f"Expected: False (only links added)")

        assert old_prose == new_prose, "Prose should be identical"
        assert not has_changes, "Should detect no prose changes (only links)"
        print("✓ PASSED\n")

    finally:
        shutil.rmtree(test_dir)


def test_new_file_detection():
    """Test that new files (not in git) are detected as having changes."""
    print("Test 5: New File Detection")
    print("-" * 70)

    test_dir = setup_test_repo()

    try:
        # Create a file but don't commit it
        test_file = test_dir / 'new.twee'
        test_file.write_text(':: New Passage\nNew prose.')

        # Check for prose changes
        has_changes = file_has_prose_changes(test_file, test_dir)

        print(f"File in git: False")
        print(f"Has prose changes: {has_changes}")
        print(f"Expected: True (new file)")

        assert has_changes, "New files should be detected as having changes"
        print("✓ PASSED\n")

    finally:
        shutil.rmtree(test_dir)


def run_all_tests():
    """Run all file-level detection tests."""
    print("=" * 70)
    print("FILE-LEVEL GIT DIFF DETECTION TEST SUITE")
    print("=" * 70)
    print()

    tests = [
        test_git_file_retrieval,
        test_split_detection_no_prose_change,
        test_genuine_prose_addition,
        test_link_only_changes,
        test_new_file_detection,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"✗ ERROR: {e}\n")
            import traceback
            traceback.print_exc()
            failed += 1

    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    print()
    print("These tests verify that file-level git diff correctly detects:")
    print("  ✓ Passage splits (same prose) → no prose changes")
    print("  ✓ Genuine new prose → prose changes detected")
    print("  ✓ Link-only additions → no prose changes")
    print("  ✓ New files → detected as changed")

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
