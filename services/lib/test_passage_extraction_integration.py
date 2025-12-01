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

from story_bible_extractor import get_passages_to_extract


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


if __name__ == '__main__':
    unittest.main()
