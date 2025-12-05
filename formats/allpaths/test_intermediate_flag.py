#!/usr/bin/env python3
"""
Test script for --write-intermediate flag functionality
"""

import sys
import json
import tempfile
import shutil
import subprocess
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(Path(__file__).parent))

def create_test_html():
    """Create a minimal Twine HTML file for testing"""
    return '''
<tw-storydata name="Test Story" startnode="1" ifid="12345678-1234-1234-1234-123456789012" format="Paperthin" format-version="1.0.0">
  <tw-passagedata pid="1" name="Start">Welcome to the story. [[Continue]]</tw-passagedata>
  <tw-passagedata pid="2" name="Continue">You continued. [[End]]</tw-passagedata>
  <tw-passagedata pid="3" name="End">The end.</tw-passagedata>
</tw-storydata>
'''

def test_without_flag():
    """Test that intermediate artifacts are NOT written without the flag"""
    print("Test 1: Running without --write-intermediate flag...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test HTML file
        html_file = tmpdir / 'test.html'
        html_file.write_text(create_test_html())

        # Create output directory
        output_dir = tmpdir / 'dist'
        output_dir.mkdir()

        # Run generator WITHOUT --write-intermediate flag
        result = subprocess.run(
            ['python3', 'generator.py', str(html_file), str(output_dir)],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Check that intermediate directory was NOT created
        intermediate_dir = output_dir / 'allpaths-intermediate'
        if intermediate_dir.exists():
            print("✗ FAILED: Intermediate directory should NOT exist without flag")
            return False
        else:
            print("✓ PASSED: Intermediate directory not created (as expected)")
            return True

def test_with_flag():
    """Test that intermediate artifacts ARE written with the flag"""
    print("\nTest 2: Running WITH --write-intermediate flag...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create test HTML file
        html_file = tmpdir / 'test.html'
        html_file.write_text(create_test_html())

        # Create output directory
        output_dir = tmpdir / 'dist'
        output_dir.mkdir()

        # Run generator WITH --write-intermediate flag
        result = subprocess.run(
            ['python3', 'generator.py', str(html_file), str(output_dir), '--write-intermediate'],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Check that intermediate directory was created
        intermediate_dir = output_dir / 'allpaths-intermediate'

        if not intermediate_dir.exists():
            print("✗ FAILED: Intermediate directory should exist with flag")
            print(f"STDERR: {result.stderr}")
            return False

        # Define all 4 expected intermediate artifacts
        expected_artifacts = {
            'story_graph.json': {
                'description': 'Stage 1: Story structure from HTML',
                'required_fields': ['passages', 'start_passage', 'metadata']
            },
            'paths.json': {
                'description': 'Stage 2: All enumerated paths',
                'required_fields': ['paths', 'statistics']
            },
            'paths_enriched.json': {
                'description': 'Stage 3: Paths with git metadata',
                'required_fields': ['paths', 'statistics']
            },
            'paths_categorized.json': {
                'description': 'Stage 4: Paths with categorization',
                'required_fields': ['paths', 'statistics']
            }
        }

        # Check that all 4 artifacts exist
        all_passed = True
        for filename, spec in expected_artifacts.items():
            artifact_file = intermediate_dir / filename

            if not artifact_file.exists():
                print(f"✗ FAILED: {filename} should exist")
                print(f"  Description: {spec['description']}")
                print(f"  Files in intermediate dir: {list(intermediate_dir.iterdir())}")
                all_passed = False
                continue

            # Validate JSON structure
            try:
                with open(artifact_file, 'r') as f:
                    data = json.load(f)

                # Check required fields
                for field in spec['required_fields']:
                    if field not in data:
                        print(f"✗ FAILED: {filename} missing required field: {field}")
                        all_passed = False
                        break
                else:
                    print(f"✓ {filename} created with correct structure")
                    print(f"  Description: {spec['description']}")

            except json.JSONDecodeError as e:
                print(f"✗ FAILED: {filename} is not valid JSON: {e}")
                all_passed = False
            except Exception as e:
                print(f"✗ FAILED: Error reading {filename}: {e}")
                all_passed = False

        # Additional validation for story_graph.json content
        if all_passed:
            story_graph_file = intermediate_dir / 'story_graph.json'
            with open(story_graph_file, 'r') as f:
                story_graph = json.load(f)

            # Check passages
            if len(story_graph['passages']) != 3:
                print(f"✗ FAILED: Expected 3 passages, got {len(story_graph['passages'])}")
                all_passed = False

            # Check metadata
            metadata = story_graph['metadata']
            if metadata['story_title'] != 'Test Story':
                print(f"✗ FAILED: Expected story title 'Test Story', got '{metadata['story_title']}'")
                all_passed = False

        if all_passed:
            print("\n✓ PASSED: All 4 intermediate artifacts created with correct structure")
            return True
        else:
            return False

def test_help_flag():
    """Test that --help flag works"""
    print("\nTest 3: Testing --help flag...")

    result = subprocess.run(
        ['python3', 'generator.py', '--help'],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode != 0:
        print("✗ FAILED: --help should return exit code 0")
        return False

    if '--write-intermediate' not in result.stdout:
        print("✗ FAILED: --write-intermediate should appear in help text")
        print(f"Help output: {result.stdout}")
        return False

    print("✓ PASSED: --help works and mentions --write-intermediate")
    return True

def main():
    """Run all tests"""
    print("="*80)
    print("Testing --write-intermediate flag functionality")
    print("="*80)

    tests = [
        test_without_flag,
        test_with_flag,
        test_help_flag,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"✗ Test raised exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    passed = sum(results)
    total = len(results)
    print(f"Tests Passed: {passed}/{total}")

    if passed == total:
        print("\nALL TESTS PASSED!")
        return 0
    else:
        print(f"\n{total - passed} TEST(S) FAILED")
        return 1

if __name__ == '__main__':
    sys.exit(main())
