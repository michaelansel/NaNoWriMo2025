#!/usr/bin/env python3
"""
Tests for GitService class.
"""

import sys
import tempfile
import subprocess
from pathlib import Path

# Import GitService (will fail until we create it)
from lib.git_service import GitService


def test_get_file_commit_date():
    """Test getting the most recent commit date for a file."""
    # Use the current repo for testing
    repo_root = Path(__file__).parent.parent.parent
    test_file = repo_root / 'README.md'

    if not test_file.exists():
        print("✗ test_get_file_commit_date - README.md not found")
        return False

    service = GitService(repo_root)
    commit_date = service.get_file_commit_date(test_file)

    # Should return a valid ISO date string
    if commit_date and len(commit_date) >= 10:
        print("✓ test_get_file_commit_date - retrieved date")
        return True
    else:
        print("✗ test_get_file_commit_date - no date returned")
        return False


def test_get_file_creation_date():
    """Test getting the first commit date for a file."""
    repo_root = Path(__file__).parent.parent.parent
    test_file = repo_root / 'README.md'

    if not test_file.exists():
        print("✗ test_get_file_creation_date - README.md not found")
        return False

    service = GitService(repo_root)
    creation_date = service.get_file_creation_date(test_file)

    # Should return a valid ISO date string
    if creation_date and len(creation_date) >= 10:
        print("✓ test_get_file_creation_date - retrieved date")
        return True
    else:
        print("✗ test_get_file_creation_date - no date returned")
        return False


def test_verify_ref_accessible():
    """Test verifying a git ref is accessible."""
    repo_root = Path(__file__).parent.parent.parent
    service = GitService(repo_root)

    # HEAD should always be accessible in a git repo
    is_accessible = service.verify_ref_accessible('HEAD')

    if is_accessible:
        print("✓ test_verify_ref_accessible - HEAD is accessible")
        return True
    else:
        print("✗ test_verify_ref_accessible - HEAD not accessible")
        return False


def test_verify_ref_inaccessible():
    """Test that invalid refs are detected."""
    repo_root = Path(__file__).parent.parent.parent
    service = GitService(repo_root)

    # This ref should not exist
    is_accessible = service.verify_ref_accessible('nonexistent-ref-12345')

    if not is_accessible:
        print("✓ test_verify_ref_inaccessible - correctly detected invalid ref")
        return True
    else:
        print("✗ test_verify_ref_inaccessible - should have detected invalid ref")
        return False


def test_get_file_content_at_ref():
    """Test getting file content at a specific ref."""
    repo_root = Path(__file__).parent.parent.parent
    test_file = repo_root / 'README.md'

    if not test_file.exists():
        print("✗ test_get_file_content_at_ref - README.md not found")
        return False

    service = GitService(repo_root)
    content = service.get_file_content_at_ref(test_file, 'HEAD')

    # Should return some content
    if content and len(content) > 0:
        print("✓ test_get_file_content_at_ref - retrieved content from HEAD")
        return True
    else:
        print("✗ test_get_file_content_at_ref - no content returned")
        return False


def test_file_has_changes():
    """Test checking if a file has changes vs a base ref."""
    repo_root = Path(__file__).parent.parent.parent
    test_file = repo_root / 'README.md'

    if not test_file.exists():
        print("✗ test_file_has_changes - README.md not found")
        return False

    service = GitService(repo_root)

    # File should have no changes vs HEAD (assuming no uncommitted changes to README)
    has_changes = service.file_has_changes(test_file, 'HEAD')

    # This test is informational - either result is valid depending on repo state
    print(f"✓ test_file_has_changes - executed (has_changes={has_changes})")
    return True


def test_nonexistent_file():
    """Test that nonexistent files are handled gracefully."""
    repo_root = Path(__file__).parent.parent.parent
    test_file = repo_root / 'nonexistent-file-12345.txt'

    service = GitService(repo_root)
    commit_date = service.get_file_commit_date(test_file)

    # Should return None for nonexistent file
    if commit_date is None:
        print("✓ test_nonexistent_file - correctly handled nonexistent file")
        return True
    else:
        print("✗ test_nonexistent_file - should return None for nonexistent file")
        return False


def main():
    """Run all tests."""
    print("="*80)
    print("GITSERVICE TEST SUITE")
    print("="*80)
    print()

    tests = [
        test_get_file_commit_date,
        test_get_file_creation_date,
        test_verify_ref_accessible,
        test_verify_ref_inaccessible,
        test_get_file_content_at_ref,
        test_file_has_changes,
        test_nonexistent_file,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} - exception: {e}")
            failed += 1

    print()
    print("="*80)
    print(f"Tests Passed: {passed}")
    print(f"Tests Failed: {failed}")
    print(f"Total Tests:  {passed + failed}")
    print("="*80)

    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
