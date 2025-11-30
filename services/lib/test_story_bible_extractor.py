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
    extract_character_name
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

    def test_no_json_raises_error(self):
        """Should raise JSONDecodeError when no JSON found."""
        text = 'No JSON here at all'
        with self.assertRaises(json.JSONDecodeError):
            parse_json_from_response(text)


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
