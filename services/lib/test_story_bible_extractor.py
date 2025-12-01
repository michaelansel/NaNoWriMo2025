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

# Add formats/story-bible/modules to path for ai_summarizer tests
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'formats' / 'story-bible' / 'modules'))

try:
    from ai_summarizer import group_facts_by_category
except ImportError:
    group_facts_by_category = None


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


@unittest.skipIf(group_facts_by_category is None, "ai_summarizer module not available")
class TestGroupFactsByCategory(unittest.TestCase):
    """Test grouping facts by category for chunked summarization."""

    def test_groups_by_type_for_constants(self):
        """Should group world_rule, setting, timeline facts separately."""
        all_facts = [
            {'fact': 'Magic exists', 'type': 'world_rule', 'category': 'constant'},
            {'fact': 'City is coastal', 'type': 'setting', 'category': 'constant'},
            {'fact': 'War ended 10 years ago', 'type': 'timeline', 'category': 'constant'},
            {'fact': 'Magic requires training', 'type': 'world_rule', 'category': 'constant'},
        ]

        result = group_facts_by_category(all_facts)

        # Should have separate groups
        self.assertIn('world_rule', result)
        self.assertIn('setting', result)
        self.assertIn('timeline', result)

        # Check counts
        self.assertEqual(len(result['world_rule']), 2)
        self.assertEqual(len(result['setting']), 1)
        self.assertEqual(len(result['timeline']), 1)

    def test_groups_character_identity_separately(self):
        """Should group character_identity facts by character."""
        all_facts = [
            {'fact': 'Javlyn is a student', 'type': 'character_identity', 'category': 'constant'},
            {'fact': 'Eldon is a teacher', 'type': 'character_identity', 'category': 'constant'},
            {'fact': 'Javlyn studies magic', 'type': 'character_identity', 'category': 'zero_action_state'},
        ]

        result = group_facts_by_category(all_facts)

        # Should have character group
        self.assertIn('character_identity', result)
        self.assertEqual(len(result['character_identity']), 3)

    def test_groups_variables_together(self):
        """Should group variable/event/outcome facts together."""
        all_facts = [
            {'fact': 'Javlyn masters magic', 'type': 'character_identity', 'category': 'variable'},
            {'fact': 'War breaks out', 'type': 'event', 'category': 'variable'},
            {'fact': 'City is destroyed', 'type': 'outcome', 'category': 'variable'},
        ]

        result = group_facts_by_category(all_facts)

        # Should have variables group
        self.assertIn('variables', result)
        self.assertEqual(len(result['variables']), 3)

    def test_handles_empty_facts(self):
        """Should handle empty fact list."""
        result = group_facts_by_category([])
        self.assertEqual(len(result), 0)

    def test_handles_mixed_categories(self):
        """Should correctly separate constants from variables."""
        all_facts = [
            {'fact': 'Magic exists', 'type': 'world_rule', 'category': 'constant'},
            {'fact': 'Javlyn masters magic', 'type': 'character_identity', 'category': 'variable'},
            {'fact': 'City is coastal', 'type': 'setting', 'category': 'constant'},
        ]

        result = group_facts_by_category(all_facts)

        # Constants and variables should be separate
        self.assertIn('world_rule', result)
        self.assertIn('setting', result)
        self.assertIn('variables', result)

        self.assertEqual(len(result['world_rule']), 1)
        self.assertEqual(len(result['setting']), 1)
        self.assertEqual(len(result['variables']), 1)


# Import new functions for testing deterministic aggregation
try:
    from ai_summarizer import (
        aggregate_facts_deterministically,
        normalize_entity_names,
        group_facts_by_character
    )
except ImportError:
    aggregate_facts_deterministically = None
    normalize_entity_names = None
    group_facts_by_character = None


@unittest.skipIf(aggregate_facts_deterministically is None, "New aggregation functions not available")
class TestAggregatFactsDeterministically(unittest.TestCase):
    """Test deterministic fact aggregation without lossy AI filtering."""

    def test_preserves_all_unique_facts(self):
        """Should preserve all facts with unique text."""
        per_passage = {
            'p1': {
                'facts': [
                    {'fact': 'Kian is a warrior', 'type': 'character_identity', 'evidence': [{'passage': 'p1', 'quote': 'quote1'}]},
                    {'fact': 'Terence is a mage', 'type': 'character_identity', 'evidence': [{'passage': 'p1', 'quote': 'quote2'}]}
                ]
            },
            'p2': {
                'facts': [
                    {'fact': 'Kian carries a sword', 'type': 'character_identity', 'evidence': [{'passage': 'p2', 'quote': 'quote3'}]},
                    {'fact': 'Magic requires training', 'type': 'world_rule', 'evidence': [{'passage': 'p2', 'quote': 'quote4'}]}
                ]
            }
        }

        result = aggregate_facts_deterministically(per_passage)

        # Should have all 4 unique facts
        all_facts = []
        for category_facts in result.values():
            all_facts.extend(category_facts)

        self.assertEqual(len(all_facts), 4)
        fact_texts = [f['fact'] for f in all_facts]
        self.assertIn('Kian is a warrior', fact_texts)
        self.assertIn('Terence is a mage', fact_texts)
        self.assertIn('Kian carries a sword', fact_texts)
        self.assertIn('Magic requires training', fact_texts)

    def test_merges_exact_duplicate_facts(self):
        """Should merge facts with identical text and combine evidence."""
        per_passage = {
            'p1': {
                'facts': [
                    {'fact': 'Magic exists', 'type': 'world_rule', 'evidence': [{'passage': 'p1', 'quote': 'quote1'}]}
                ]
            },
            'p2': {
                'facts': [
                    {'fact': 'Magic exists', 'type': 'world_rule', 'evidence': [{'passage': 'p2', 'quote': 'quote2'}]}
                ]
            }
        }

        result = aggregate_facts_deterministically(per_passage)

        # Should have 1 fact with combined evidence
        world_rules = result.get('world_rule', [])
        self.assertEqual(len(world_rules), 1)
        self.assertEqual(world_rules[0]['fact'], 'Magic exists')
        self.assertEqual(len(world_rules[0]['evidence']), 2)

    def test_keeps_similar_but_different_facts(self):
        """Should NOT merge similar facts that aren't identical."""
        per_passage = {
            'p1': {
                'facts': [
                    {'fact': 'Kian is a warrior', 'type': 'character_identity', 'evidence': [{'passage': 'p1', 'quote': 'quote1'}]},
                    {'fact': 'Kian is a skilled warrior', 'type': 'character_identity', 'evidence': [{'passage': 'p1', 'quote': 'quote2'}]}
                ]
            }
        }

        result = aggregate_facts_deterministically(per_passage)

        # Should keep both - they're different facts
        char_facts = result.get('character_identity', [])
        self.assertEqual(len(char_facts), 2)

    def test_groups_by_fact_type(self):
        """Should group aggregated facts by type."""
        per_passage = {
            'p1': {
                'facts': [
                    {'fact': 'Magic exists', 'type': 'world_rule', 'evidence': [{'passage': 'p1', 'quote': 'q1'}]},
                    {'fact': 'City is coastal', 'type': 'setting', 'evidence': [{'passage': 'p1', 'quote': 'q2'}]},
                    {'fact': 'Kian is a warrior', 'type': 'character_identity', 'evidence': [{'passage': 'p1', 'quote': 'q3'}]}
                ]
            }
        }

        result = aggregate_facts_deterministically(per_passage)

        # Should have separate groups
        self.assertIn('world_rule', result)
        self.assertIn('setting', result)
        self.assertIn('character_identity', result)
        self.assertEqual(len(result['world_rule']), 1)
        self.assertEqual(len(result['setting']), 1)
        self.assertEqual(len(result['character_identity']), 1)


@unittest.skipIf(normalize_entity_names is None, "Name normalization function not available")
class TestNormalizeEntityNames(unittest.TestCase):
    """Test AI-based entity name normalization (punctuation/variant cleanup only)."""

    @patch('ai_summarizer.requests.post')
    def test_normalizes_punctuation_artifacts(self, mock_post):
        """Should normalize 'Danita,' to 'Danita' via AI."""
        # Mock AI response
        mock_post.return_value.json.return_value = {
            'response': json.dumps({
                'name_mappings': [
                    {'variants': ['Danita,', 'Danita'], 'canonical': 'Danita'}
                ]
            })
        }

        facts = [
            {'fact': 'Danita, is a student', 'type': 'character_identity'},
            {'fact': 'Danita studies magic', 'type': 'character_identity'}
        ]

        result = normalize_entity_names(facts)

        # Should map 'Danita,' -> 'Danita'
        self.assertIn('Danita,', result)
        self.assertEqual(result['Danita,'], 'Danita')

    @patch('ai_summarizer.requests.post')
    def test_normalizes_possessive_forms(self, mock_post):
        """Should normalize "Javlyn's" to "Javlyn" via AI."""
        mock_post.return_value.json.return_value = {
            'response': json.dumps({
                'name_mappings': [
                    {'variants': ["Javlyn's", 'Javlyn'], 'canonical': 'Javlyn'}
                ]
            })
        }

        facts = [
            {'fact': "Javlyn's magic is strong", 'type': 'character_identity'},
            {'fact': 'Javlyn is a student', 'type': 'character_identity'}
        ]

        result = normalize_entity_names(facts)

        self.assertIn("Javlyn's", result)
        self.assertEqual(result["Javlyn's"], 'Javlyn')

    @patch('ai_summarizer.requests.post')
    def test_returns_empty_for_no_variants(self, mock_post):
        """Should return empty mapping when no variants found."""
        mock_post.return_value.json.return_value = {
            'response': json.dumps({'name_mappings': []})
        }

        facts = [
            {'fact': 'Kian is a warrior', 'type': 'character_identity'}
        ]

        result = normalize_entity_names(facts)
        self.assertEqual(len(result), 0)


@unittest.skipIf(group_facts_by_character is None, "Character grouping function not available")
class TestGroupFactsByCharacter(unittest.TestCase):
    """Test grouping character facts by character name with name normalization."""

    def test_groups_facts_by_character_name(self):
        """Should group character facts by extracted name."""
        facts = [
            {'fact': 'Kian is a warrior', 'type': 'character_identity', 'category': 'constant'},
            {'fact': 'Kian carries a sword', 'type': 'character_identity', 'category': 'constant'},
            {'fact': 'Terence is a mage', 'type': 'character_identity', 'category': 'constant'}
        ]

        result = group_facts_by_character(facts, name_mapping={})

        self.assertIn('Kian', result)
        self.assertIn('Terence', result)
        self.assertEqual(len(result['Kian']['identity']), 2)
        self.assertEqual(len(result['Terence']['identity']), 1)

    def test_applies_name_normalization(self):
        """Should use name mapping to unify variants."""
        facts = [
            {'fact': 'Danita, is a student', 'type': 'character_identity', 'category': 'constant'},
            {'fact': 'Danita studies magic', 'type': 'character_identity', 'category': 'constant'}
        ]

        name_mapping = {'Danita,': 'Danita'}

        result = group_facts_by_character(facts, name_mapping)

        # Should have single 'Danita' entry with both facts
        self.assertIn('Danita', result)
        self.assertEqual(len(result['Danita']['identity']), 2)
        # Should NOT have 'Danita,' as a separate character
        self.assertNotIn('Danita,', result)

    def test_separates_by_category(self):
        """Should separate identity, zero_action_state, and variables."""
        facts = [
            {'fact': 'Kian is a warrior', 'type': 'character_identity', 'category': 'constant'},
            {'fact': 'Kian trains daily', 'type': 'character_identity', 'category': 'zero_action_state'},
            {'fact': 'Kian masters swordplay', 'type': 'character_identity', 'category': 'variable'}
        ]

        result = group_facts_by_character(facts, name_mapping={})

        self.assertEqual(len(result['Kian']['identity']), 1)
        self.assertEqual(len(result['Kian']['zero_action_state']), 1)
        self.assertEqual(len(result['Kian']['variables']), 1)


@unittest.skipIf(aggregate_facts_deterministically is None, "Summarizer module not available")
class TestIntegrationLosslessAggregation(unittest.TestCase):
    """Integration test: verify all character facts are preserved through the full pipeline."""

    def test_preserves_kian_and_terence_facts(self):
        """
        Regression test: Ensure characters mentioned in many passages (like Kian, Terence)
        are NOT dropped during aggregation.
        """
        # Simulate per-passage extractions with Kian and Terence mentioned across passages
        per_passage = {
            'p1': {
                'facts': [
                    {'fact': 'Kian is a warrior', 'type': 'character_identity', 'category': 'constant',
                     'evidence': [{'passage': 'p1', 'quote': 'Kian stood ready'}]},
                    {'fact': 'Terence is a mage', 'type': 'character_identity', 'category': 'constant',
                     'evidence': [{'passage': 'p1', 'quote': 'Terence studied magic'}]}
                ]
            },
            'p2': {
                'facts': [
                    {'fact': 'Kian carries a sword', 'type': 'character_identity', 'category': 'constant',
                     'evidence': [{'passage': 'p2', 'quote': 'His sword gleamed'}]},
                    {'fact': 'Terence knows ancient spells', 'type': 'character_identity', 'category': 'constant',
                     'evidence': [{'passage': 'p2', 'quote': 'Ancient knowledge'}]}
                ]
            },
            'p3': {
                'facts': [
                    {'fact': 'Kian trained for years', 'type': 'character_identity', 'category': 'zero_action_state',
                     'evidence': [{'passage': 'p3', 'quote': 'Years of training'}]},
                ]
            }
        }

        # Run through aggregation pipeline
        from ai_summarizer import summarize_facts

        result, status = summarize_facts(per_passage)

        self.assertEqual(status, "success")
        self.assertIsNotNone(result)

        # Verify Kian appears in characters
        characters = result.get('characters', {})
        self.assertIn('Kian', characters)

        # Verify Terence appears in characters
        self.assertIn('Terence', characters)

        # Verify Kian has all 3 facts (2 identity + 1 zero_action_state)
        kian_facts = characters['Kian']
        self.assertEqual(len(kian_facts['identity']), 2)
        self.assertEqual(len(kian_facts['zero_action_state']), 1)

        # Verify Terence has both facts
        terence_facts = characters['Terence']
        self.assertEqual(len(terence_facts['identity']), 2)

        # Verify fact texts are preserved
        kian_identity_texts = [f['fact'] for f in kian_facts['identity']]
        self.assertIn('Kian is a warrior', kian_identity_texts)
        self.assertIn('Kian carries a sword', kian_identity_texts)

        terence_identity_texts = [f['fact'] for f in terence_facts['identity']]
        self.assertIn('Terence is a mage', terence_identity_texts)
        self.assertIn('Terence knows ancient spells', terence_identity_texts)

    def test_deduplicates_exact_duplicates_only(self):
        """Should merge exact duplicates but preserve unique facts."""
        per_passage = {
            'p1': {
                'facts': [
                    {'fact': 'Magic exists', 'type': 'world_rule', 'category': 'constant',
                     'evidence': [{'passage': 'p1', 'quote': 'quote1'}]}
                ]
            },
            'p2': {
                'facts': [
                    {'fact': 'Magic exists', 'type': 'world_rule', 'category': 'constant',
                     'evidence': [{'passage': 'p2', 'quote': 'quote2'}]},
                    {'fact': 'Magic requires training', 'type': 'world_rule', 'category': 'constant',
                     'evidence': [{'passage': 'p2', 'quote': 'quote3'}]}
                ]
            }
        }

        from ai_summarizer import summarize_facts

        result, status = summarize_facts(per_passage)

        self.assertEqual(status, "success")

        # Should have 2 unique world rules
        world_rules = result['constants']['world_rules']
        self.assertEqual(len(world_rules), 2)

        # 'Magic exists' should have combined evidence from both passages
        magic_exists = [f for f in world_rules if f['fact'] == 'Magic exists'][0]
        self.assertEqual(len(magic_exists['evidence']), 2)


if __name__ == '__main__':
    unittest.main()
