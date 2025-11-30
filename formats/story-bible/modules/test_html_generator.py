#!/usr/bin/env python3
"""
Tests for Story Bible HTML generator module.

Tests the evidence normalization and fact processing functions.
"""

import unittest
import json
from pathlib import Path
import sys

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent))

from html_generator import (
    normalize_evidence,
    normalize_facts,
    normalize_constants,
    normalize_variables,
    normalize_characters,
    normalize_conflicts
)


class TestNormalizeEvidence(unittest.TestCase):
    """Test evidence normalization to array-of-objects format."""

    def test_none_returns_empty_list(self):
        """Should return empty list for None evidence."""
        result = normalize_evidence(None)
        self.assertEqual(result, [])

    def test_string_to_object(self):
        """Should convert string evidence to object format."""
        evidence = "She cast a powerful spell"
        result = normalize_evidence(evidence)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['passage'], 'Source')
        self.assertEqual(result[0]['quote'], 'She cast a powerful spell')

    def test_array_of_strings(self):
        """Should convert array of strings to objects."""
        evidence = ["quote one", "quote two"]
        result = normalize_evidence(evidence)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['quote'], 'quote one')
        self.assertEqual(result[1]['quote'], 'quote two')
        self.assertEqual(result[0]['passage'], 'Source')

    def test_array_of_objects_preserved(self):
        """Should preserve array of objects format."""
        evidence = [
            {'passage': 'Start', 'quote': 'test quote'}
        ]
        result = normalize_evidence(evidence)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['passage'], 'Start')
        self.assertEqual(result[0]['quote'], 'test quote')

    def test_mixed_array(self):
        """Should handle mixed array of strings and objects."""
        evidence = [
            "string quote",
            {'passage': 'Middle', 'quote': 'object quote'}
        ]
        result = normalize_evidence(evidence)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['quote'], 'string quote')
        self.assertEqual(result[1]['passage'], 'Middle')
        self.assertEqual(result[1]['quote'], 'object quote')

    def test_object_missing_passage_gets_default(self):
        """Should add default passage when missing from object."""
        evidence = [{'quote': 'just a quote'}]
        result = normalize_evidence(evidence)

        self.assertEqual(result[0]['passage'], 'Source')
        self.assertEqual(result[0]['quote'], 'just a quote')

    def test_object_missing_quote_stringifies(self):
        """Should stringify object when quote is missing."""
        evidence = [{'passage': 'Start', 'other': 'data'}]
        result = normalize_evidence(evidence)

        self.assertEqual(result[0]['passage'], 'Start')
        # Quote should be stringified version of the dict
        self.assertIn('other', result[0]['quote'])


class TestNormalizeFacts(unittest.TestCase):
    """Test fact list normalization."""

    def test_empty_list(self):
        """Should return empty list for empty input."""
        result = normalize_facts([])
        self.assertEqual(result, [])

    def test_none_returns_empty(self):
        """Should return empty list for None input."""
        result = normalize_facts(None)
        self.assertEqual(result, [])

    def test_normalizes_evidence_in_facts(self):
        """Should normalize evidence within each fact."""
        facts = [
            {'fact': 'Magic exists', 'evidence': 'Some quote'}
        ]
        result = normalize_facts(facts)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['fact'], 'Magic exists')
        self.assertEqual(len(result[0]['evidence']), 1)
        self.assertEqual(result[0]['evidence'][0]['quote'], 'Some quote')

    def test_preserves_other_fields(self):
        """Should preserve non-evidence fields in facts."""
        facts = [
            {
                'fact': 'Magic exists',
                'type': 'world_rule',
                'confidence': 'high',
                'evidence': []
            }
        ]
        result = normalize_facts(facts)

        self.assertEqual(result[0]['type'], 'world_rule')
        self.assertEqual(result[0]['confidence'], 'high')


class TestNormalizeConstants(unittest.TestCase):
    """Test constants normalization."""

    def test_empty_constants(self):
        """Should return empty dict for empty input."""
        result = normalize_constants({})
        self.assertEqual(result, {})

    def test_none_returns_empty(self):
        """Should return empty dict for None input."""
        result = normalize_constants(None)
        self.assertEqual(result, {})

    def test_normalizes_all_categories(self):
        """Should normalize world_rules, setting, and timeline."""
        constants = {
            'world_rules': [{'fact': 'Magic', 'evidence': 'quote'}],
            'setting': [{'fact': 'Coastal city', 'evidence': 'quote'}],
            'timeline': [{'fact': 'War ended', 'evidence': 'quote'}]
        }
        result = normalize_constants(constants)

        self.assertIn('world_rules', result)
        self.assertIn('setting', result)
        self.assertIn('timeline', result)
        # Check evidence was normalized
        self.assertIsInstance(result['world_rules'][0]['evidence'], list)


class TestNormalizeVariables(unittest.TestCase):
    """Test variables normalization."""

    def test_empty_variables(self):
        """Should return empty dict for empty input."""
        result = normalize_variables({})
        self.assertEqual(result, {})

    def test_normalizes_events_and_outcomes(self):
        """Should normalize events and outcomes lists."""
        variables = {
            'events': [{'fact': 'Player chooses', 'evidence': 'quote'}],
            'outcomes': [{'fact': 'Story ends', 'evidence': 'quote'}]
        }
        result = normalize_variables(variables)

        self.assertIn('events', result)
        self.assertIn('outcomes', result)


class TestNormalizeCharacters(unittest.TestCase):
    """Test characters normalization."""

    def test_empty_characters(self):
        """Should return empty dict for empty input."""
        result = normalize_characters({})
        self.assertEqual(result, {})

    def test_normalizes_character_sections(self):
        """Should normalize identity, zero_action_state, and variables."""
        characters = {
            'Javlyn': {
                'identity': [{'fact': 'Is a student', 'evidence': 'quote'}],
                'zero_action_state': [{'fact': 'Studies magic', 'evidence': 'quote'}],
                'variables': [{'fact': 'Can master magic', 'evidence': 'quote'}]
            }
        }
        result = normalize_characters(characters)

        self.assertIn('Javlyn', result)
        self.assertIn('identity', result['Javlyn'])
        self.assertIn('zero_action_state', result['Javlyn'])
        self.assertIn('variables', result['Javlyn'])


class TestNormalizeConflicts(unittest.TestCase):
    """Test conflicts normalization."""

    def test_empty_conflicts(self):
        """Should return empty list for empty input."""
        result = normalize_conflicts([])
        self.assertEqual(result, [])

    def test_none_returns_empty(self):
        """Should return empty list for None input."""
        result = normalize_conflicts(None)
        self.assertEqual(result, [])

    def test_normalizes_facts_in_conflicts(self):
        """Should normalize facts within each conflict."""
        conflicts = [
            {
                'description': 'Timeline conflict',
                'facts': [
                    {'fact': 'War ended 10 years ago', 'evidence': 'quote1'},
                    {'fact': 'War ended 2 years ago', 'evidence': 'quote2'}
                ]
            }
        ]
        result = normalize_conflicts(conflicts)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['description'], 'Timeline conflict')
        self.assertEqual(len(result[0]['facts']), 2)
        # Check evidence was normalized
        self.assertIsInstance(result[0]['facts'][0]['evidence'], list)


if __name__ == '__main__':
    unittest.main()
