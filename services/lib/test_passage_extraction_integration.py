#!/usr/bin/env python3
"""
Integration test for passage-based extraction.

Tests the complete flow from allpaths.txt to extracted passages.
"""

import unittest
import json
import tempfile
from pathlib import Path
import sys

# Add services/lib to path
sys.path.insert(0, str(Path(__file__).parent))


class TestPassageExtractionIntegration(unittest.TestCase):
    """Integration tests for passage-based extraction flow."""

    def setUp(self):
        """Create temporary directory with test files."""
        self.tmpdir = tempfile.mkdtemp()
        self.metadata_dir = Path(self.tmpdir)

    def test_full_extraction_flow(self):
        """Test complete flow from allpaths.txt to passage extraction."""
        # Create test allpaths.txt
        allpaths_content = """
[PATH 1/2]

========================================
[PASSAGE: 68616c6c776179]
========================================

:: hallway
You are in a hallway.

[[Go north|room-a]]
[[Go south|room-b]]

========================================
[PASSAGE: 726f6f6d2d61]
========================================

:: room-a
You enter room A.

[PATH 2/2]

[PASSAGE: 68616c6c776179]
:: hallway
You are in a hallway.

[PASSAGE: 726f6f6d2d62]
:: room-b
You enter room B.
"""
        allpaths_file = self.metadata_dir / "allpaths.txt"
        allpaths_file.write_text(allpaths_content)

        # Create test mapping
        mapping = {
            "68616c6c776179": "hallway",
            "726f6f6d2d61": "room-a",
            "726f6f6d2d62": "room-b"
        }
        mapping_file = self.metadata_dir / "allpaths-passage-mapping.json"
        mapping_file.write_text(json.dumps(mapping))

        # Test with empty cache (all passages should be extracted)
        cache = {"passage_extractions": {}}
        passages = get_passages_to_extract(cache, self.metadata_dir, mode='incremental')

        # Should get 3 unique passages (deduplication works)
        self.assertEqual(len(passages), 3)

        # Extract passage IDs
        passage_ids = {p[0] for p in passages}
        self.assertEqual(passage_ids, {"hallway", "room-a", "room-b"})

        # Verify content is clean (no separators)
        for passage_id, _, content in passages:
            self.assertNotIn("====", content)
            self.assertIn("::", content)

    def test_incremental_extraction_with_cache(self):
        """Test incremental extraction skips cached passages."""
        # Create simple allpaths.txt
        allpaths_content = """
[PASSAGE: 74657374]
:: test
Test content.
"""
        allpaths_file = self.metadata_dir / "allpaths.txt"
        allpaths_file.write_text(allpaths_content)

        mapping = {"74657374": "test"}
        mapping_file = self.metadata_dir / "allpaths-passage-mapping.json"
        mapping_file.write_text(json.dumps(mapping))

        # Cache with correct hash for this passage
        import hashlib
        content = ":: test\nTest content."
        content_hash = hashlib.md5(content.encode()).hexdigest()

        cache = {
            "passage_extractions": {
                "test": {
                    "content_hash": content_hash,
                    "entities": {}
                }
            }
        }

        passages = get_passages_to_extract(cache, self.metadata_dir, mode='incremental')

        # Should not extract cached passage
        self.assertEqual(len(passages), 0)

    def test_full_mode_ignores_cache(self):
        """Test full mode extracts all passages regardless of cache."""
        allpaths_content = """
[PASSAGE: 74657374]
:: test
Test content.
"""
        allpaths_file = self.metadata_dir / "allpaths.txt"
        allpaths_file.write_text(allpaths_content)

        mapping = {"74657374": "test"}
        mapping_file = self.metadata_dir / "allpaths-passage-mapping.json"
        mapping_file.write_text(json.dumps(mapping))

        # Cache with passage already extracted
        cache = {
            "passage_extractions": {
                "test": {
                    "content_hash": "some_hash",
                    "entities": {}
                }
            }
        }

        passages = get_passages_to_extract(cache, self.metadata_dir, mode='full')

        # Should extract even though cached
        self.assertEqual(len(passages), 1)
        self.assertEqual(passages[0][0], "test")

    def test_handles_missing_allpaths_file(self):
        """Test graceful handling of missing allpaths.txt."""
        # Don't create allpaths.txt
        cache = {"passage_extractions": {}}
        passages = get_passages_to_extract(cache, self.metadata_dir, mode='incremental')

        # Should return empty list, not crash
        self.assertEqual(len(passages), 0)

    def test_handles_missing_mapping_file(self):
        """Test graceful handling of missing mapping file."""
        # Create allpaths.txt but not mapping
        allpaths_file = self.metadata_dir / "allpaths.txt"
        allpaths_file.write_text("[PASSAGE: 74657374]\n:: test\nContent.")

        cache = {"passage_extractions": {}}
        passages = get_passages_to_extract(cache, self.metadata_dir, mode='incremental')

        # Should return empty list, not crash
        self.assertEqual(len(passages), 0)


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

    def test_falls_back_to_allpaths_when_core_missing(self):
        """Test fallback to AllPaths when core library not available."""
        # Create only AllPaths files
        with open(self.metadata_dir / "allpaths.txt", 'w') as f:
            f.write("[PASSAGE: 616c6c70617468]\n:: AllPathsPassage\nFrom AllPaths")

        with open(self.metadata_dir / "allpaths-passage-mapping.json", 'w') as f:
            json.dump({"616c6c70617468": "AllPathsPassage"}, f)

        from story_bible_extractor import get_passages_to_extract_v2

        cache = {}
        passages = get_passages_to_extract_v2(cache, self.metadata_dir, mode='full')

        # Should have AllPaths passage
        self.assertEqual(len(passages), 1)
        passage_id, _, content, content_hash = passages[0]
        self.assertEqual(passage_id, "AllPathsPassage")
        self.assertIn("From AllPaths", content)

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
