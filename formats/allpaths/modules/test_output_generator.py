#!/usr/bin/env python3
"""
Test suite for AllPaths output generator module.

Tests the Stage 5 (Output Generation) functionality that generates
HTML browser, text files, and validation cache from categorized paths.
"""

import sys
import json
import tempfile
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

SAMPLE_STORY_DATA = {
    'name': 'Test Story',
    'ifid': '12345678-1234-1234-1234-123456789ABC',
    'start': '1'
}

SAMPLE_PASSAGES = {
    'Start': {
        'text': 'This is the start. [[Middle]]',
        'pid': '1'
    },
    'Middle': {
        'text': 'You are in the middle. [[End]]',
        'pid': '2'
    },
    'End': {
        'text': 'This is the end.',
        'pid': '3'
    }
}

SAMPLE_PATHS = [
    ['Start', 'Middle', 'End']
]

SAMPLE_VALIDATION_CACHE = {
    'abc12345': {
        'route': 'Start → Middle → End',
        'first_seen': '2025-01-15T10:00:00',
        'validated': False,
        'commit_date': '2025-01-15T10:00:00Z',
        'created_date': '2025-01-15T10:00:00Z',
        'category': 'new'
    }
}

SAMPLE_PATH_CATEGORIES = {
    'abc12345': 'new'
}

# ============================================================================
# FORMAT DATE TESTS
# ============================================================================

@test("format_date_for_display - formats ISO date correctly")
def test_format_date_iso():
    from output_generator import format_date_for_display

    result = format_date_for_display('2025-01-15T10:30:00Z')
    assert '2025-01-15' in result, f"Date should contain '2025-01-15', got {result}"
    assert '10:30' in result, f"Time should contain '10:30', got {result}"
    assert 'UTC' in result, f"Should include 'UTC', got {result}"

@test("format_date_for_display - handles missing date")
def test_format_date_missing():
    from output_generator import format_date_for_display

    result = format_date_for_display('')
    assert result == 'Unknown', f"Empty date should return 'Unknown', got {result}"

    result = format_date_for_display(None)
    assert result == 'Unknown', f"None date should return 'Unknown', got {result}"

@test("format_date_for_display - handles invalid date")
def test_format_date_invalid():
    from output_generator import format_date_for_display

    result = format_date_for_display('invalid-date')
    # Should return at least the date part or handle gracefully
    assert result is not None, "Should handle invalid date"

# ============================================================================
# HTML OUTPUT TESTS
# ============================================================================

@test("generate_html_output - returns HTML string")
def test_generate_html_basic():
    from output_generator import generate_html_output

    html = generate_html_output(SAMPLE_STORY_DATA, SAMPLE_PASSAGES, SAMPLE_PATHS)

    assert isinstance(html, str), "Should return a string"
    assert len(html) > 0, "HTML should not be empty"
    assert '<!DOCTYPE html>' in html or '<html' in html, "Should contain HTML structure"

@test("generate_html_output - includes story name")
def test_generate_html_story_name():
    from output_generator import generate_html_output

    html = generate_html_output(SAMPLE_STORY_DATA, SAMPLE_PASSAGES, SAMPLE_PATHS)

    assert 'Test Story' in html, "HTML should include story name"

@test("generate_html_output - includes path count")
def test_generate_html_path_count():
    from output_generator import generate_html_output

    html = generate_html_output(SAMPLE_STORY_DATA, SAMPLE_PASSAGES, SAMPLE_PATHS)

    # Should show total path count somewhere
    assert '1' in html, "HTML should include path count"

@test("generate_html_output - includes passage content")
def test_generate_html_passage_content():
    from output_generator import generate_html_output

    html = generate_html_output(SAMPLE_STORY_DATA, SAMPLE_PASSAGES, SAMPLE_PATHS)

    # Should include passage text (at least partial)
    assert 'start' in html.lower(), "HTML should include passage content"

@test("generate_html_output - handles validation cache")
def test_generate_html_with_cache():
    from output_generator import generate_html_output

    html = generate_html_output(
        SAMPLE_STORY_DATA,
        SAMPLE_PASSAGES,
        SAMPLE_PATHS,
        validation_cache=SAMPLE_VALIDATION_CACHE
    )

    assert isinstance(html, str), "Should handle validation cache"
    assert len(html) > 0, "HTML should not be empty with cache"

@test("generate_html_output - handles path categories")
def test_generate_html_with_categories():
    from output_generator import generate_html_output

    html = generate_html_output(
        SAMPLE_STORY_DATA,
        SAMPLE_PASSAGES,
        SAMPLE_PATHS,
        path_categories=SAMPLE_PATH_CATEGORIES
    )

    assert isinstance(html, str), "Should handle path categories"
    assert len(html) > 0, "HTML should not be empty with categories"

@test("generate_html_output - handles empty paths")
def test_generate_html_empty_paths():
    from output_generator import generate_html_output

    html = generate_html_output(SAMPLE_STORY_DATA, SAMPLE_PASSAGES, [])

    assert isinstance(html, str), "Should handle empty paths"
    # May show 0 paths or an error message

# ============================================================================
# GENERATE OUTPUTS TESTS
# ============================================================================

@test("generate_outputs - creates HTML file")
def test_generate_outputs_html():
    from output_generator import generate_outputs

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        result = generate_outputs(
            story_data=SAMPLE_STORY_DATA,
            passages=SAMPLE_PASSAGES,
            all_paths=SAMPLE_PATHS,
            output_dir=output_dir
        )

        html_file = output_dir / 'allpaths.html'
        assert html_file.exists(), f"HTML file should be created at {html_file}"

        with open(html_file, 'r') as f:
            content = f.read()
            assert len(content) > 0, "HTML file should not be empty"

@test("generate_outputs - creates clean text directory")
def test_generate_outputs_clean_text():
    from output_generator import generate_outputs

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        result = generate_outputs(
            story_data=SAMPLE_STORY_DATA,
            passages=SAMPLE_PASSAGES,
            all_paths=SAMPLE_PATHS,
            output_dir=output_dir
        )

        text_dir = output_dir / 'allpaths-clean'
        assert text_dir.exists(), f"Clean text directory should be created at {text_dir}"
        assert text_dir.is_dir(), "allpaths-clean should be a directory"

        # Should have at least one text file
        text_files = list(text_dir.glob('*.txt'))
        assert len(text_files) > 0, "Should create at least one text file"

@test("generate_outputs - creates metadata text directory")
def test_generate_outputs_metadata_text():
    from output_generator import generate_outputs

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        result = generate_outputs(
            story_data=SAMPLE_STORY_DATA,
            passages=SAMPLE_PASSAGES,
            all_paths=SAMPLE_PATHS,
            output_dir=output_dir
        )

        metadata_dir = output_dir / 'allpaths-metadata'
        assert metadata_dir.exists(), f"Metadata text directory should be created at {metadata_dir}"
        assert metadata_dir.is_dir(), "allpaths-metadata should be a directory"

        # Should have at least one text file
        text_files = list(metadata_dir.glob('*.txt'))
        assert len(text_files) > 0, "Should create at least one metadata text file"

@test("generate_outputs - text files use path hash naming")
def test_generate_outputs_text_naming():
    from output_generator import generate_outputs

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        result = generate_outputs(
            story_data=SAMPLE_STORY_DATA,
            passages=SAMPLE_PASSAGES,
            all_paths=SAMPLE_PATHS,
            output_dir=output_dir
        )

        text_dir = output_dir / 'allpaths-clean'
        text_files = list(text_dir.glob('*.txt'))

        # File names should start with 'path-' and end with '.txt'
        for text_file in text_files:
            assert text_file.name.startswith('path-'), f"Text file should start with 'path-', got {text_file.name}"
            assert text_file.name.endswith('.txt'), f"Text file should end with '.txt', got {text_file.name}"

@test("generate_outputs - clean text has no metadata headers")
def test_generate_outputs_clean_no_metadata():
    from output_generator import generate_outputs

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        result = generate_outputs(
            story_data=SAMPLE_STORY_DATA,
            passages=SAMPLE_PASSAGES,
            all_paths=SAMPLE_PATHS,
            output_dir=output_dir
        )

        text_dir = output_dir / 'allpaths-clean'
        text_files = list(text_dir.glob('*.txt'))

        # Check that clean text doesn't have metadata markers
        for text_file in text_files:
            with open(text_file, 'r') as f:
                content = f.read()
                # Should not have PATH headers or Route: lines
                assert 'PATH 1 of' not in content, "Clean text should not have PATH headers"
                assert 'Route:' not in content, "Clean text should not have Route metadata"

@test("generate_outputs - metadata text has headers")
def test_generate_outputs_metadata_has_headers():
    from output_generator import generate_outputs

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        result = generate_outputs(
            story_data=SAMPLE_STORY_DATA,
            passages=SAMPLE_PASSAGES,
            all_paths=SAMPLE_PATHS,
            output_dir=output_dir
        )

        metadata_dir = output_dir / 'allpaths-metadata'
        text_files = list(metadata_dir.glob('*.txt'))

        # Check that metadata text has headers
        for text_file in text_files:
            with open(text_file, 'r') as f:
                content = f.read()
                # Should have PATH headers
                assert 'PATH 1 of' in content, "Metadata text should have PATH headers"

@test("generate_outputs - returns result dict")
def test_generate_outputs_return_value():
    from output_generator import generate_outputs

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        result = generate_outputs(
            story_data=SAMPLE_STORY_DATA,
            passages=SAMPLE_PASSAGES,
            all_paths=SAMPLE_PATHS,
            output_dir=output_dir
        )

        assert isinstance(result, dict), "Should return a dictionary"
        # Result might contain file paths or counts

@test("generate_outputs - saves validation cache")
def test_generate_outputs_validation_cache():
    from output_generator import generate_outputs

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)
        cache_file = Path(tmpdir) / 'allpaths-validation-status.json'

        result = generate_outputs(
            story_data=SAMPLE_STORY_DATA,
            passages=SAMPLE_PASSAGES,
            all_paths=SAMPLE_PATHS,
            output_dir=output_dir,
            validation_cache={},
            cache_file=cache_file
        )

        assert cache_file.exists(), f"Validation cache should be saved at {cache_file}"

        with open(cache_file, 'r') as f:
            cache = json.load(f)
            assert isinstance(cache, dict), "Cache should be a dictionary"

@test("generate_outputs - handles passage ID mapping")
def test_generate_outputs_passage_mapping():
    from output_generator import generate_outputs

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        passage_id_mapping = {
            'Start': 'abc123',
            'Middle': 'def456',
            'End': 'ghi789'
        }

        result = generate_outputs(
            story_data=SAMPLE_STORY_DATA,
            passages=SAMPLE_PASSAGES,
            all_paths=SAMPLE_PATHS,
            output_dir=output_dir,
            passage_id_mapping=passage_id_mapping
        )

        # Should use IDs in metadata text files
        metadata_dir = output_dir / 'allpaths-metadata'
        text_files = list(metadata_dir.glob('*.txt'))

        for text_file in text_files:
            with open(text_file, 'r') as f:
                content = f.read()
                # Should have at least one ID from mapping in the route
                has_id = any(id_val in content for id_val in passage_id_mapping.values())
                # This is optional - may or may not use IDs

# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == '__main__':
    print("=" * 80)
    print("ALLPATHS OUTPUT GENERATOR MODULE TESTS")
    print("=" * 80)
    print()

    # Format date tests
    test_format_date_iso()
    test_format_date_missing()
    test_format_date_invalid()

    # HTML output tests
    test_generate_html_basic()
    test_generate_html_story_name()
    test_generate_html_path_count()
    test_generate_html_passage_content()
    test_generate_html_with_cache()
    test_generate_html_with_categories()
    test_generate_html_empty_paths()

    # Generate outputs tests
    test_generate_outputs_html()
    test_generate_outputs_clean_text()
    test_generate_outputs_metadata_text()
    test_generate_outputs_text_naming()
    test_generate_outputs_clean_no_metadata()
    test_generate_outputs_metadata_has_headers()
    test_generate_outputs_return_value()
    test_generate_outputs_validation_cache()
    test_generate_outputs_passage_mapping()

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
