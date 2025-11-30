#!/usr/bin/env python3
"""
Tests for Story Bible extraction module.

Tests the extraction and categorization of facts from story passages.
"""

import unittest
import json
from pathlib import Path
from unittest.mock import patch, Mock
import sys

# Add services/lib to path
sys.path.insert(0, str(Path(__file__).parent))

from story_bible_extractor import (
    parse_json_from_response,
    categorize_all_facts,
    extract_character_name,
    chunk_passage
)


class TestParseJsonFromResponse(unittest.TestCase):
    """Test JSON parsing from AI responses."""

    def test_clean_json(self):
        """Should parse clean JSON directly."""
        text = '{"facts": [{"fact": "Magic exists"}]}'
        result = parse_json_from_response(text)
        self.assertEqual(result['facts'][0]['fact'], "Magic exists")

    def test_json_with_preamble(self):
        """Should extract JSON from response with preamble text."""
        text = 'Here is the extraction:\n{"facts": [{"fact": "Magic exists"}]}'
        result = parse_json_from_response(text)
        self.assertEqual(result['facts'][0]['fact'], "Magic exists")

    def test_json_with_trailing_text(self):
        """Should extract JSON ignoring trailing text."""
        text = '{"facts": []}\n\nNote: No facts found.'
        result = parse_json_from_response(text)
        self.assertEqual(result['facts'], [])

    def test_no_json_returns_empty_facts(self):
        """Should return empty facts when no JSON found (resilient behavior)."""
        text = 'No JSON here at all'
        result = parse_json_from_response(text)
        self.assertEqual(result, {"facts": []})


class TestCategorizeAllFacts(unittest.TestCase):
    """Test fact categorization with per-passage preservation."""

    def test_preserves_per_passage_when_summarized_exists(self):
        """Should preserve per-passage data alongside summarized facts."""
        passage_extractions = {
            'passage1': {
                'passage_name': 'Start',
                'facts': [{'fact': 'Magic exists', 'type': 'world_rule'}]
            },
            'passage2': {
                'passage_name': 'Middle',
                'facts': [{'fact': 'City is coastal', 'type': 'setting'}]
            }
        }
        summarized_facts = {
            'constants': {'world_rules': [{'fact': 'Magic exists'}]},
            'characters': {},
            'variables': {}
        }

        result = categorize_all_facts(passage_extractions, summarized_facts)

        # Should have summarized facts
        self.assertIn('constants', result)
        self.assertEqual(result['constants']['world_rules'][0]['fact'], 'Magic exists')

        # Should ALSO have per-passage data
        self.assertIn('per_passage', result)
        self.assertIn('passage1', result['per_passage'])
        self.assertIn('passage2', result['per_passage'])
        self.assertEqual(result['per_passage']['passage1']['passage_name'], 'Start')
        self.assertEqual(len(result['per_passage']['passage1']['facts']), 1)

    def test_fallback_when_no_summarization(self):
        """Should use basic categorization when no summarized facts."""
        passage_extractions = {
            'passage1': {
                'passage_name': 'Start',
                'facts': [
                    {'fact': 'Magic exists', 'type': 'world_rule', 'category': 'constant'}
                ]
            }
        }

        result = categorize_all_facts(passage_extractions, summarized_facts=None)

        # Should have categorized structure
        self.assertIn('constants', result)
        self.assertIn('world_rules', result['constants'])
        # Per-passage not added in fallback mode (handled differently)
        self.assertNotIn('per_passage', result)

    def test_empty_passage_extractions(self):
        """Should handle empty passage extractions."""
        passage_extractions = {}
        summarized_facts = {
            'constants': {'world_rules': []},
            'characters': {},
            'variables': {}
        }

        result = categorize_all_facts(passage_extractions, summarized_facts)

        self.assertIn('per_passage', result)
        self.assertEqual(len(result['per_passage']), 0)

    def test_missing_passage_name_uses_default(self):
        """Should use 'Unknown' when passage_name is missing."""
        passage_extractions = {
            'passage1': {
                'facts': [{'fact': 'Test fact'}]
            }
        }
        summarized_facts = {
            'constants': {},
            'characters': {},
            'variables': {}
        }

        result = categorize_all_facts(passage_extractions, summarized_facts)

        self.assertEqual(result['per_passage']['passage1']['passage_name'], 'Unknown')


class TestExtractCharacterName(unittest.TestCase):
    """Test character name extraction heuristic."""

    def test_name_at_start(self):
        """Should extract capitalized name at start of fact."""
        result = extract_character_name("Javlyn is a student")
        self.assertEqual(result, "Javlyn")

    def test_skips_articles(self):
        """Should skip common articles like 'The'."""
        result = extract_character_name("The character Sarah studies magic")
        self.assertEqual(result, "Sarah")

    def test_no_name_returns_unknown(self):
        """Should return 'Unknown' when no name found."""
        result = extract_character_name("the city is on the coast")
        self.assertEqual(result, "Unknown")

    def test_skips_a_an(self):
        """Should skip 'A' and 'An' articles."""
        result = extract_character_name("A wizard named Merlin appears")
        self.assertEqual(result, "Merlin")


class TestChunkPassage(unittest.TestCase):
    """Test passage chunking functionality."""

    def test_small_passage_single_chunk(self):
        """Should return single chunk for passage within limit."""
        text = "This is a small passage.\n\nIt has two paragraphs."
        result = chunk_passage("TestPassage", text, max_chars=20000)

        self.assertEqual(len(result), 1)
        chunk_name, chunk_text, chunk_num = result[0]
        self.assertEqual(chunk_name, "TestPassage")
        self.assertEqual(chunk_text, text)
        self.assertEqual(chunk_num, 1)

    def test_large_passage_multiple_chunks(self):
        """Should split large passage into multiple chunks."""
        # Create passage > 100 chars (using low limit for test)
        para1 = "A" * 60
        para2 = "B" * 60
        text = f"{para1}\n\n{para2}"

        result = chunk_passage("TestPassage", text, max_chars=100)

        # Should create 2 chunks
        self.assertEqual(len(result), 2)

        # Check chunk names
        self.assertEqual(result[0][0], "TestPassage_chunk_1")
        self.assertEqual(result[1][0], "TestPassage_chunk_2")

        # Check chunk numbers
        self.assertEqual(result[0][2], 1)
        self.assertEqual(result[1][2], 2)

    def test_chunk_overlap(self):
        """Should include overlap between chunks."""
        para1 = "A" * 60
        para2 = "B" * 60
        text = f"{para1}\n\n{para2}"

        result = chunk_passage("TestPassage", text, max_chars=100, overlap_chars=20)

        # Second chunk should start with overlap from first
        self.assertIn("A", result[1][1])  # Contains some As from para1

    def test_empty_passage(self):
        """Should handle empty passage gracefully."""
        result = chunk_passage("Empty", "", max_chars=20000)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][1], "")

    def test_exactly_at_limit(self):
        """Should handle passage exactly at character limit."""
        text = "A" * 100
        result = chunk_passage("Exact", text, max_chars=100)

        # Should be single chunk (not over limit)
        self.assertEqual(len(result), 1)


class TestCategorizeAllFactsFallback(unittest.TestCase):
    """Test categorization fallback path (no summarization)."""

    def test_categorizes_world_rules(self):
        """Should categorize world_rule facts into constants."""
        passage_extractions = {
            'p1': {
                'facts': [
                    {'fact': 'Magic requires training', 'type': 'world_rule', 'category': 'constant'}
                ]
            }
        }

        result = categorize_all_facts(passage_extractions, summarized_facts=None)

        self.assertEqual(len(result['constants']['world_rules']), 1)
        self.assertEqual(result['constants']['world_rules'][0]['fact'], 'Magic requires training')

    def test_categorizes_setting_facts(self):
        """Should categorize setting facts into constants."""
        passage_extractions = {
            'p1': {
                'facts': [
                    {'fact': 'City is coastal', 'type': 'setting', 'category': 'constant'}
                ]
            }
        }

        result = categorize_all_facts(passage_extractions, summarized_facts=None)

        self.assertEqual(len(result['constants']['setting']), 1)

    def test_categorizes_timeline_facts(self):
        """Should categorize timeline facts into constants."""
        passage_extractions = {
            'p1': {
                'facts': [
                    {'fact': 'War ended 10 years ago', 'type': 'timeline', 'category': 'constant'}
                ]
            }
        }

        result = categorize_all_facts(passage_extractions, summarized_facts=None)

        self.assertEqual(len(result['constants']['timeline']), 1)


if __name__ == '__main__':
    unittest.main()
