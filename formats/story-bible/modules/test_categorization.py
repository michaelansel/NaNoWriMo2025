#!/usr/bin/env python3
"""
Tests for Phase 3: Categorization (World Rules and Timeline)

Verifies that summarization categorizes facts into world_rules and timeline
based on content heuristics.
"""

import unittest
import json
from pathlib import Path
import sys

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_summarizer import summarize_from_entities


class TestWorldRulesCategorization(unittest.TestCase):
    """Test that world rules are extracted and categorized."""

    def test_magic_system_facts_categorized_as_world_rules(self):
        """Facts about magic system should be categorized as world_rules."""
        merged_extractions = {
            'Start': {
                'entities': {
                    'characters': [],
                    'locations': [
                        {
                            'name': 'Academy',
                            'facts': ['teaches magic', 'magic requires formal training'],
                            'mentions': [
                                {'quote': 'At the Academy, magic requires training', 'context': 'narrative'}
                            ]
                        }
                    ],
                    'items': []
                }
            }
        }

        result, status = summarize_from_entities(merged_extractions)

        self.assertEqual(status, 'success')
        self.assertIn('constants', result)
        self.assertIn('world_rules', result['constants'])

        # Should extract facts about magic as world rules
        world_rules = result['constants']['world_rules']
        # This will FAIL until we implement categorization
        self.assertGreater(len(world_rules), 0, "World rules should be populated")

        # Should contain magic-related fact
        rule_texts = [r.get('fact', '') for r in world_rules]
        has_magic_rule = any('magic' in text.lower() and 'training' in text.lower() for text in rule_texts)
        self.assertTrue(has_magic_rule, "Should categorize magic system facts as world rules")

    def test_technology_level_categorized_as_world_rules(self):
        """Facts about technology level should be categorized as world_rules."""
        merged_extractions = {
            'Start': {
                'entities': {
                    'characters': [],
                    'locations': [
                        {
                            'name': 'Village',
                            'facts': ['pre-industrial technology', 'no electricity'],
                            'mentions': [
                                {'quote': 'The village used candles for light', 'context': 'narrative'}
                            ]
                        }
                    ],
                    'items': []
                }
            }
        }

        result, status = summarize_from_entities(merged_extractions)

        world_rules = result['constants']['world_rules']
        self.assertGreater(len(world_rules), 0)

        rule_texts = [r.get('fact', '') for r in world_rules]
        has_tech_rule = any('technology' in text.lower() or 'electricity' in text.lower() for text in rule_texts)
        self.assertTrue(has_tech_rule, "Should categorize technology facts as world rules")


class TestTimelineCategorization(unittest.TestCase):
    """Test that timeline facts are extracted and categorized."""

    def test_historical_events_categorized_as_timeline(self):
        """Facts about past events should be categorized as timeline."""
        merged_extractions = {
            'Start': {
                'entities': {
                    'characters': [],
                    'locations': [
                        {
                            'name': 'Capital',
                            'facts': ['war ended 10 years ago', 'was destroyed before the story'],
                            'mentions': [
                                {'quote': 'The war ended a decade past', 'context': 'narrative'}
                            ]
                        }
                    ],
                    'items': []
                }
            }
        }

        result, status = summarize_from_entities(merged_extractions)

        self.assertEqual(status, 'success')
        self.assertIn('constants', result)
        self.assertIn('timeline', result['constants'])

        # Should extract historical facts as timeline
        timeline = result['constants']['timeline']
        # This will FAIL until we implement categorization
        self.assertGreater(len(timeline), 0, "Timeline should be populated")

        # Should contain historical fact
        timeline_texts = [t.get('fact', '') for t in timeline]
        has_historical = any('years ago' in text.lower() or 'before' in text.lower() for text in timeline_texts)
        self.assertTrue(has_historical, "Should categorize historical facts as timeline")

    def test_backstory_events_categorized_as_timeline(self):
        """Facts about events before story start should be timeline."""
        merged_extractions = {
            'Start': {
                'entities': {
                    'characters': [
                        {
                            'name': 'Elder',
                            'facts': ['witnessed the ancient war', 'lived before the calamity'],
                            'mentions': [
                                {'quote': 'The Elder remembered the ancient war', 'context': 'narrative'}
                            ]
                        }
                    ],
                    'locations': [],
                    'items': []
                }
            }
        }

        result, status = summarize_from_entities(merged_extractions)

        timeline = result['constants']['timeline']
        self.assertGreater(len(timeline), 0)

        timeline_texts = [t.get('fact', '') for t in timeline]
        has_backstory = any('ancient' in text.lower() or 'before' in text.lower() for text in timeline_texts)
        self.assertTrue(has_backstory, "Should categorize backstory as timeline")


class TestCategorizationPreservesEvidence(unittest.TestCase):
    """Test that categorization preserves evidence when moving facts."""

    def test_world_rules_have_evidence_from_source(self):
        """World rules should preserve evidence from original extraction."""
        merged_extractions = {
            'Start': {
                'entities': {
                    'characters': [],
                    'locations': [
                        {
                            'name': 'Academy',
                            'facts': ['magic requires training'],
                            'mentions': [
                                {'quote': 'Magic must be learned', 'context': 'narrative'}
                            ]
                        }
                    ],
                    'items': []
                }
            }
        }

        result, status = summarize_from_entities(merged_extractions)

        world_rules = result['constants']['world_rules']
        if len(world_rules) > 0:
            rule = world_rules[0]
            self.assertIn('evidence', rule, "World rule should have evidence")
            self.assertIsInstance(rule['evidence'], list)
            # Evidence should have passage reference
            if len(rule['evidence']) > 0:
                self.assertIn('passage', rule['evidence'][0])


if __name__ == '__main__':
    unittest.main()
