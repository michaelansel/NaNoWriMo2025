#!/usr/bin/env python3
"""
Tests for Phase 2: Aggregation Evidence Attachment

Verifies that aggregation attaches evidence properly to facts.
"""

import unittest
import json
from pathlib import Path
import sys

# Add modules directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_summarizer import (
    aggregate_entities_from_extractions,
    summarize_from_entities
)


class TestAggregationEvidenceAttachment(unittest.TestCase):
    """Test that aggregation attaches passage names as evidence to facts."""

    def test_character_facts_have_evidence_with_passage_names(self):
        """Character facts should have evidence array with passage names."""
        per_passage_extractions = {
            'Start': {
                'entities': {
                    'characters': [
                        {
                            'name': 'Javlyn',
                            'facts': ['is a student at the Academy'],
                            'mentions': [
                                {'quote': 'Javlyn entered the Academy', 'context': 'narrative'}
                            ]
                        }
                    ],
                    'locations': [],
                    'items': []
                }
            }
        }

        result = aggregate_entities_from_extractions(per_passage_extractions)

        # Character should exist
        self.assertIn('characters', result)
        self.assertIn('Javlyn', result['characters'])

        # Identity facts should exist
        javlyn = result['characters']['Javlyn']
        self.assertIn('identity', javlyn)
        self.assertGreater(len(javlyn['identity']), 0)

        # CRITICAL: Facts should have evidence structure
        # Currently facts are strings, should be objects with evidence
        fact = javlyn['identity'][0]

        # This test will FAIL until we implement evidence attachment
        if isinstance(fact, str):
            self.fail("Facts should be objects with 'fact' and 'evidence' fields, not strings")

        self.assertIn('fact', fact, "Fact should have 'fact' field")
        self.assertIn('evidence', fact, "Fact should have 'evidence' field")
        self.assertIsInstance(fact['evidence'], list, "Evidence should be array")
        self.assertGreater(len(fact['evidence']), 0, "Evidence should be populated")

        # Evidence should have passage name
        evidence_item = fact['evidence'][0]
        self.assertIn('passage', evidence_item, "Evidence should have 'passage' field")
        self.assertEqual(evidence_item['passage'], 'Start', "Evidence should cite passage name")
        self.assertIn('quote', evidence_item, "Evidence should have 'quote' field")

    def test_location_facts_have_evidence_with_passage_names(self):
        """Location facts should have evidence array with passage names."""
        per_passage_extractions = {
            'Academy Entrance': {
                'entities': {
                    'characters': [],
                    'locations': [
                        {
                            'name': 'cave',
                            'facts': ['dark interior', 'near the village'],
                            'mentions': [
                                {'quote': 'The cave loomed before them', 'context': 'narrative'}
                            ]
                        }
                    ],
                    'items': []
                }
            }
        }

        result = aggregate_entities_from_extractions(per_passage_extractions)

        # Location should exist (normalized to title case)
        self.assertIn('locations', result)
        self.assertIn('Cave', result['locations'])

        cave = result['locations']['Cave']
        self.assertIn('facts', cave)
        self.assertGreater(len(cave['facts']), 0)

        # Facts should have evidence
        fact = cave['facts'][0]

        if isinstance(fact, str):
            self.fail("Location facts should be objects with evidence, not strings")

        self.assertIn('evidence', fact)
        self.assertGreater(len(fact['evidence']), 0)
        self.assertEqual(fact['evidence'][0]['passage'], 'Academy Entrance')

    def test_merges_evidence_from_multiple_passages(self):
        """Should merge evidence when same fact appears in multiple passages."""
        per_passage_extractions = {
            'Start': {
                'entities': {
                    'characters': [
                        {
                            'name': 'Javlyn',
                            'facts': ['is a student at the Academy'],
                            'mentions': [
                                {'quote': 'Javlyn, a student', 'context': 'narrative'}
                            ]
                        }
                    ],
                    'locations': [],
                    'items': []
                }
            },
            'Day 1': {
                'entities': {
                    'characters': [
                        {
                            'name': 'Javlyn',
                            'facts': ['is a student at the Academy'],  # Same fact
                            'mentions': [
                                {'quote': 'student Javlyn', 'context': 'narrative'}
                            ]
                        }
                    ],
                    'locations': [],
                    'items': []
                }
            }
        }

        result = aggregate_entities_from_extractions(per_passage_extractions)

        javlyn = result['characters']['Javlyn']

        # Should have 1 deduplicated fact (not 2)
        self.assertEqual(len(javlyn['identity']), 1)

        fact = javlyn['identity'][0]

        # Should have evidence from BOTH passages
        self.assertIn('evidence', fact)
        self.assertEqual(len(fact['evidence']), 2, "Should combine evidence from both passages")

        passages_cited = [e['passage'] for e in fact['evidence']]
        self.assertIn('Start', passages_cited)
        self.assertIn('Day 1', passages_cited)


class TestSummarizeFromEntitiesEvidence(unittest.TestCase):
    """Test that summarize_from_entities preserves evidence in final output."""

    def test_final_output_has_evidence_in_character_identity(self):
        """Final summarized output should have evidence arrays in character facts."""
        merged_extractions = {
            'Start': {
                'entities': {
                    'characters': [
                        {
                            'name': 'Javlyn',
                            'facts': ['is a student'],
                            'mentions': [
                                {'quote': 'Javlyn the student', 'context': 'narrative'}
                            ]
                        }
                    ],
                    'locations': [],
                    'items': []
                }
            }
        }

        result, status = summarize_from_entities(merged_extractions)

        self.assertEqual(status, 'success')
        self.assertIn('characters', result)
        self.assertIn('Javlyn', result['characters'])

        javlyn = result['characters']['Javlyn']
        self.assertIn('identity', javlyn)
        self.assertGreater(len(javlyn['identity']), 0)

        # Identity facts should have evidence
        fact = javlyn['identity'][0]

        if isinstance(fact, str):
            self.fail("Final output facts should be objects with evidence")

        self.assertIn('fact', fact)
        self.assertIn('evidence', fact)
        self.assertGreater(len(fact['evidence']), 0)

    def test_final_output_has_evidence_in_setting_facts(self):
        """Final setting facts should have evidence arrays."""
        merged_extractions = {
            'Start': {
                'entities': {
                    'characters': [],
                    'locations': [
                        {
                            'name': 'Mushroom Cave',
                            'facts': ['dark interior'],
                            'mentions': [
                                {'quote': 'The cave was dark', 'context': 'narrative'}
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
        self.assertIn('setting', result['constants'])

        setting_facts = result['constants']['setting']
        self.assertGreater(len(setting_facts), 0)

        # Setting facts should have evidence
        fact = setting_facts[0]
        self.assertIn('evidence', fact)
        self.assertIsInstance(fact['evidence'], list)


if __name__ == '__main__':
    unittest.main()
