#!/usr/bin/env python3
"""
Test suite for git_enricher module (Stage 3 of AllPaths pipeline).

Tests git metadata enrichment: passage-to-file mapping, commit dates, creation dates.
"""

import sys
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.git_enricher import (
    build_passage_to_file_mapping,
    get_path_commit_date,
    get_path_creation_date,
    enrich_paths,
)

# Test counters
tests_passed = 0
tests_failed = 0
test_details = []

def test(name):
    """Decorator to mark test functions"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            global tests_passed, tests_failed, test_details
            try:
                func(*args, **kwargs)
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
# UNIT TESTS FOR GIT ENRICHER
# ============================================================================

@test("build_passage_to_file_mapping - simple mapping")
def test_build_passage_to_file_mapping_simple(tmp_path):
    """Test passage-to-file mapping with simple twee files"""
    # Create temporary twee files
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    file1 = src_dir / "story.twee"
    file1.write_text(""":: Start
Welcome to the story.

:: Middle
You are in the middle.
""")

    file2 = src_dir / "endings.twee"
    file2.write_text(""":: End
The end.
""")

    # Build mapping
    mapping = build_passage_to_file_mapping(src_dir)

    # Verify mapping
    assert 'Start' in mapping, "Should find Start passage"
    assert 'Middle' in mapping, "Should find Middle passage"
    assert 'End' in mapping, "Should find End passage"

    assert mapping['Start'] == file1, f"Start should map to {file1}"
    assert mapping['Middle'] == file1, f"Middle should map to {file1}"
    assert mapping['End'] == file2, f"End should map to {file2}"

@test("build_passage_to_file_mapping - handles tags")
def test_build_passage_to_file_mapping_tags(tmp_path):
    """Test that passage mapping handles Twee tags correctly"""
    src_dir = tmp_path / "src_tags"
    src_dir.mkdir()

    file1 = src_dir / "tagged.twee"
    file1.write_text(""":: Start [tag1 tag2]
Content with tags.

::Middle[tagged]
No space after colon.
""")

    mapping = build_passage_to_file_mapping(src_dir)

    assert 'Start' in mapping, "Should find Start passage (with tags)"
    assert 'Middle' in mapping, "Should find Middle passage (no space)"
    assert mapping['Start'] == file1
    assert mapping['Middle'] == file1

@test("build_passage_to_file_mapping - nested directories")
def test_build_passage_to_file_mapping_nested(tmp_path):
    """Test passage mapping with nested directory structure"""
    src_dir = tmp_path / "src"
    subdir = src_dir / "chapters"
    subdir.mkdir(parents=True)

    file1 = subdir / "chapter1.twee"
    file1.write_text(""":: ChapterOne
First chapter.
""")

    mapping = build_passage_to_file_mapping(src_dir)

    assert 'ChapterOne' in mapping, "Should find passage in nested directory"
    assert mapping['ChapterOne'] == file1

@test("get_path_commit_date - single file")
def test_get_path_commit_date_single_file():
    """Test getting commit date for path with single file"""
    # Mock GitService
    mock_git_service = Mock()
    mock_git_service.get_file_commit_date.return_value = "2025-11-20T10:00:00Z"

    path = ['Start', 'Middle', 'End']
    passage_to_file = {
        'Start': Path('/repo/src/story.twee'),
        'Middle': Path('/repo/src/story.twee'),
        'End': Path('/repo/src/story.twee'),
    }
    repo_root = Path('/repo')

    # Inject mock git_service for testing
    from modules import git_enricher
    original_git_service_class = git_enricher.GitService
    git_enricher.GitService = lambda x: mock_git_service

    try:
        commit_date = get_path_commit_date(path, passage_to_file, repo_root)

        assert commit_date == "2025-11-20T10:00:00Z", f"Should return commit date, got {commit_date}"
        # Should only call once for single file
        assert mock_git_service.get_file_commit_date.call_count >= 1
    finally:
        git_enricher.GitService = original_git_service_class

@test("get_path_commit_date - multiple files, most recent")
def test_get_path_commit_date_multiple_files():
    """Test getting commit date returns most recent across multiple files"""
    mock_git_service = Mock()

    def mock_get_commit_date(file_path):
        if 'file1' in str(file_path):
            return "2025-11-15T10:00:00Z"  # Older
        elif 'file2' in str(file_path):
            return "2025-11-20T10:00:00Z"  # More recent
        return None

    mock_git_service.get_file_commit_date.side_effect = mock_get_commit_date

    path = ['Start', 'Middle', 'End']
    passage_to_file = {
        'Start': Path('/repo/src/file1.twee'),
        'Middle': Path('/repo/src/file1.twee'),
        'End': Path('/repo/src/file2.twee'),
    }
    repo_root = Path('/repo')

    from modules import git_enricher
    original_git_service_class = git_enricher.GitService
    git_enricher.GitService = lambda x: mock_git_service

    try:
        commit_date = get_path_commit_date(path, passage_to_file, repo_root)

        assert commit_date == "2025-11-20T10:00:00Z", f"Should return most recent date, got {commit_date}"
    finally:
        git_enricher.GitService = original_git_service_class

@test("get_path_creation_date - returns most recent passage creation")
def test_get_path_creation_date():
    """Test getting path creation date (when path became complete)"""
    mock_git_service = Mock()

    def mock_get_creation_date(file_path):
        if 'file1' in str(file_path):
            return "2025-11-02T10:00:00Z"  # Older passage
        elif 'file2' in str(file_path):
            return "2025-11-10T10:00:00Z"  # Newer passage (path became complete)
        return None

    mock_git_service.get_file_creation_date.side_effect = mock_get_creation_date

    path = ['Start', 'End']
    passage_to_file = {
        'Start': Path('/repo/src/file1.twee'),
        'End': Path('/repo/src/file2.twee'),
    }
    repo_root = Path('/repo')

    from modules import git_enricher
    original_git_service_class = git_enricher.GitService
    git_enricher.GitService = lambda x: mock_git_service

    try:
        creation_date = get_path_creation_date(path, passage_to_file, repo_root)

        # Should return most recent creation date (when path became complete)
        assert creation_date == "2025-11-10T10:00:00Z", f"Should return most recent creation date, got {creation_date}"
    finally:
        git_enricher.GitService = original_git_service_class

@test("enrich_paths - adds git metadata to all paths")
def test_enrich_paths_basic():
    """Test that enrich_paths adds git metadata to all paths"""
    paths_data = {
        'paths': [
            {
                'id': 'abc12345',
                'route': ['Start', 'End'],
                'content': {
                    'Start': 'Welcome',
                    'End': 'The end'
                }
            }
        ],
        'statistics': {
            'total_paths': 1,
            'total_passages': 2,
            'avg_path_length': 2.0
        }
    }

    # Mock GitService
    mock_git_service = Mock()
    mock_git_service.get_file_commit_date.return_value = "2025-11-20T10:00:00Z"
    mock_git_service.get_file_creation_date.return_value = "2025-11-02T10:00:00Z"

    # Mock passage_to_file mapping
    passage_to_file = {
        'Start': Path('/repo/src/story.twee'),
        'End': Path('/repo/src/story.twee'),
    }

    from modules import git_enricher
    original_git_service_class = git_enricher.GitService
    original_build_mapping = git_enricher.build_passage_to_file_mapping

    git_enricher.GitService = lambda x: mock_git_service
    git_enricher.build_passage_to_file_mapping = lambda x: passage_to_file

    try:
        source_dir = Path('/repo/src')
        enriched = enrich_paths(paths_data, source_dir, Path('/repo'))

        # Verify structure
        assert 'paths' in enriched, "Should have paths array"
        assert len(enriched['paths']) == 1, "Should have 1 path"

        # Verify git metadata was added
        path = enriched['paths'][0]
        assert 'git_metadata' in path, "Path should have git_metadata"

        git_meta = path['git_metadata']
        assert 'files' in git_meta, "Should have files list"
        assert 'commit_date' in git_meta, "Should have commit_date"
        assert 'created_date' in git_meta, "Should have created_date"
        assert 'passage_to_file' in git_meta, "Should have passage_to_file mapping"

        # Verify values
        assert git_meta['commit_date'] == "2025-11-20T10:00:00Z"
        assert git_meta['created_date'] == "2025-11-02T10:00:00Z"
        assert 'Start' in git_meta['passage_to_file']
        assert 'End' in git_meta['passage_to_file']

    finally:
        git_enricher.GitService = original_git_service_class
        git_enricher.build_passage_to_file_mapping = original_build_mapping

@test("enrich_paths - handles missing git data gracefully")
def test_enrich_paths_missing_git_data():
    """Test that enrich_paths handles missing git data (returns None for dates)"""
    paths_data = {
        'paths': [
            {
                'id': 'xyz98765',
                'route': ['Start'],
                'content': {'Start': 'Content'}
            }
        ],
        'statistics': {
            'total_paths': 1,
            'total_passages': 1,
            'avg_path_length': 1.0
        }
    }

    # Mock GitService that returns None (file not in git)
    mock_git_service = Mock()
    mock_git_service.get_file_commit_date.return_value = None
    mock_git_service.get_file_creation_date.return_value = None

    passage_to_file = {
        'Start': Path('/repo/src/new_file.twee'),
    }

    from modules import git_enricher
    original_git_service_class = git_enricher.GitService
    original_build_mapping = git_enricher.build_passage_to_file_mapping

    git_enricher.GitService = lambda x: mock_git_service
    git_enricher.build_passage_to_file_mapping = lambda x: passage_to_file

    try:
        enriched = enrich_paths(paths_data, Path('/repo/src'), Path('/repo'))

        path = enriched['paths'][0]
        git_meta = path['git_metadata']

        # Should have None for missing dates
        assert git_meta['commit_date'] is None, "Should have None for missing commit date"
        assert git_meta['created_date'] is None, "Should have None for missing creation date"

        # Should still have files and passage mapping
        assert 'files' in git_meta
        assert 'passage_to_file' in git_meta

    finally:
        git_enricher.GitService = original_git_service_class
        git_enricher.build_passage_to_file_mapping = original_build_mapping

@test("enrich_paths - preserves original data")
def test_enrich_paths_preserves_data():
    """Test that enrich_paths preserves original path data (id, route, content)"""
    paths_data = {
        'paths': [
            {
                'id': 'original1',
                'route': ['A', 'B', 'C'],
                'content': {
                    'A': 'Content A',
                    'B': 'Content B',
                    'C': 'Content C'
                }
            }
        ],
        'statistics': {
            'total_paths': 1,
            'total_passages': 3,
            'avg_path_length': 3.0
        }
    }

    mock_git_service = Mock()
    mock_git_service.get_file_commit_date.return_value = "2025-11-20T10:00:00Z"
    mock_git_service.get_file_creation_date.return_value = "2025-11-02T10:00:00Z"

    passage_to_file = {
        'A': Path('/repo/src/story.twee'),
        'B': Path('/repo/src/story.twee'),
        'C': Path('/repo/src/story.twee'),
    }

    from modules import git_enricher
    original_git_service_class = git_enricher.GitService
    original_build_mapping = git_enricher.build_passage_to_file_mapping

    git_enricher.GitService = lambda x: mock_git_service
    git_enricher.build_passage_to_file_mapping = lambda x: passage_to_file

    try:
        enriched = enrich_paths(paths_data, Path('/repo/src'), Path('/repo'))

        path = enriched['paths'][0]

        # Original data should be preserved
        assert path['id'] == 'original1', "Should preserve original path ID"
        assert path['route'] == ['A', 'B', 'C'], "Should preserve original route"
        assert path['content'] == {'A': 'Content A', 'B': 'Content B', 'C': 'Content C'}, "Should preserve original content"

        # Statistics should be preserved
        assert enriched['statistics'] == paths_data['statistics'], "Should preserve statistics"

    finally:
        git_enricher.GitService = original_git_service_class
        git_enricher.build_passage_to_file_mapping = original_build_mapping

# ============================================================================
# RUN ALL TESTS
# ============================================================================

def run_all_tests():
    """Run all test functions"""
    print("=" * 80)
    print("GIT ENRICHER MODULE TEST SUITE")
    print("=" * 80)
    print()

    # Need to create tmp_path for file system tests
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        print("Unit Tests")
        print("-" * 80)
        test_build_passage_to_file_mapping_simple(tmp_path)
        test_build_passage_to_file_mapping_tags(tmp_path)
        test_build_passage_to_file_mapping_nested(tmp_path)
        test_get_path_commit_date_single_file()
        test_get_path_commit_date_multiple_files()
        test_get_path_creation_date()
        test_enrich_paths_basic()
        test_enrich_paths_missing_git_data()
        test_enrich_paths_preserves_data()

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
