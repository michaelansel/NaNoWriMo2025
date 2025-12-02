#!/usr/bin/env python3
"""
Integration test for passage-based extraction.

Tests the complete flow using core library artifacts.
"""

import unittest
import json
import tempfile
from pathlib import Path
import sys

# Add services/lib to path
sys.path.insert(0, str(Path(__file__).parent))


class TestCoreLibraryIntegration(unittest.TestCase):
    """Integration tests for core library artifact loading."""

    def setUp(self):
        """Set up test environment with temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.metadata_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_core_library_takes_precedence_over_allpaths(self):
        """Test that core library artifacts are used when both are available."""
        # Create both core library and AllPaths files
        core_artifacts = {
            "passages": [
                {
                    "name": "CorePassage",
                    "content": "From core library",
                    "content_hash": "core123"
                }
            ]
        }

        with open(self.metadata_dir / "passages_deduplicated.json", 'w') as f:
            json.dump(core_artifacts, f)

        # Also create AllPaths files
        with open(self.metadata_dir / "allpaths.txt", 'w') as f:
            f.write("[PASSAGE: 616c6c70617468]\n:: AllPathsPassage\nFrom AllPaths")

        with open(self.metadata_dir / "allpaths-passage-mapping.json", 'w') as f:
            json.dump({"616c6c70617468": "AllPathsPassage"}, f)

        # Import function
        from story_bible_extractor import get_passages_to_extract_v2

        # Get passages (should use core library)
        cache = {}
        passages = get_passages_to_extract_v2(cache, self.metadata_dir, mode='full')

        # Should have core library passage, not AllPaths
        self.assertEqual(len(passages), 1)
        passage_id, _, content, content_hash = passages[0]
        self.assertEqual(passage_id, "CorePassage")
        self.assertIn("From core library", content)

    def test_incremental_mode_with_core_library(self):
        """Test incremental extraction with core library artifacts."""
        # Create core library artifacts
        core_artifacts = {
            "passages": [
                {"name": "Cached", "content": "Cached passage", "content_hash": "cached123"},
                {"name": "New", "content": "New passage", "content_hash": "new456"}
            ]
        }

        with open(self.metadata_dir / "passages_deduplicated.json", 'w') as f:
            json.dump(core_artifacts, f)

        # Cache one passage
        cache = {
            'passage_extractions': {
                'Cached': {
                    'content_hash': 'cached123',  # Same hash = no re-extraction
                    'entities': {'characters': []}
                }
            }
        }

        from story_bible_extractor import get_passages_to_extract_v2

        passages = get_passages_to_extract_v2(cache, self.metadata_dir, mode='incremental')

        # Should only extract the new passage
        self.assertEqual(len(passages), 1)
        passage_id, _, _, content_hash = passages[0]
        self.assertEqual(passage_id, "New")

    def test_changed_passage_detected_by_hash(self):
        """Test that changed passages are detected via content_hash."""
        # Create core library artifacts
        core_artifacts = {
            "passages": [
                {"name": "Modified", "content": "Updated content", "content_hash": "new_hash"}
            ]
        }

        with open(self.metadata_dir / "passages_deduplicated.json", 'w') as f:
            json.dump(core_artifacts, f)

        # Cache with old hash
        cache = {
            'passage_extractions': {
                'Modified': {
                    'content_hash': 'old_hash',  # Different hash = re-extract
                    'entities': {'characters': []}
                }
            }
        }

        from story_bible_extractor import get_passages_to_extract_v2

        passages = get_passages_to_extract_v2(cache, self.metadata_dir, mode='incremental')

        # Should extract the modified passage
        self.assertEqual(len(passages), 1)
        passage_id, _, content, content_hash = passages[0]
        self.assertEqual(passage_id, "Modified")
        self.assertIn("Updated content", content)


if __name__ == '__main__':
    unittest.main()
