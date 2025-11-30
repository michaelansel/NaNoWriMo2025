#!/usr/bin/env python3
"""
Tests for Story Bible validation module.

Tests the validation of story content against established world constants.
"""

import unittest
import json
from pathlib import Path
from unittest.mock import patch, Mock
import sys

# Add services/lib to path
sys.path.insert(0, str(Path(__file__).parent))

from story_bible_validator import (
    format_constants_for_validation,
    parse_json_from_response,
    merge_validation_results,
    validate_against_story_bible
)


class TestFormatConstantsForValidation(unittest.TestCase):
    """Test formatting of Story Bible constants for validation prompts."""

    def test_empty_cache(self):
        """Should return placeholder text for empty cache."""
        cache = {}
        result = format_constants_for_validation(cache)
        self.assertEqual(result, "(No world constants established yet)")

    def test_cache_with_no_constants(self):
        """Should return placeholder for cache with no categorized facts."""
        cache = {
            'categorized_facts': {
                'constants': {}
            }
        }
        result = format_constants_for_validation(cache)
        self.assertEqual(result, "(No world constants established yet)")

    def test_world_rules_formatting(self):
        """Should format world rules with evidence."""
        cache = {
            'categorized_facts': {
                'constants': {
                    'world_rules': [
                        {
                            'fact': 'Magic requires verbal incantations',
                            'evidence': 'She spoke the spell aloud'
                        }
                    ]
                }
            }
        }
        result = format_constants_for_validation(cache)
        self.assertIn('**World Rules:**', result)
        self.assertIn('Magic requires verbal incantations', result)
        self.assertIn('Evidence: "She spoke the spell aloud"', result)

    def test_setting_formatting(self):
        """Should format setting facts."""
        cache = {
            'categorized_facts': {
                'constants': {
                    'setting': [
                        {
                            'fact': 'The city is on the coast',
                            'evidence': 'Waves crashed against the shore'
                        }
                    ]
                }
            }
        }
        result = format_constants_for_validation(cache)
        self.assertIn('**Setting:**', result)
        self.assertIn('The city is on the coast', result)

    def test_timeline_formatting(self):
        """Should format timeline facts."""
        cache = {
            'categorized_facts': {
                'constants': {
                    'timeline': [
                        {
                            'fact': 'The war ended 10 years ago',
                            'evidence': 'A decade had passed since the ceasefire'
                        }
                    ]
                }
            }
        }
        result = format_constants_for_validation(cache)
        self.assertIn('**Timeline:**', result)
        self.assertIn('The war ended 10 years ago', result)

    def test_multiple_categories(self):
        """Should format multiple fact categories."""
        cache = {
            'categorized_facts': {
                'constants': {
                    'world_rules': [{'fact': 'Magic exists', 'evidence': 'spell cast'}],
                    'setting': [{'fact': 'City on coast', 'evidence': 'waves'}],
                    'timeline': [{'fact': 'War 10 years ago', 'evidence': 'decade passed'}]
                }
            }
        }
        result = format_constants_for_validation(cache)
        self.assertIn('**World Rules:**', result)
        self.assertIn('**Setting:**', result)
        self.assertIn('**Timeline:**', result)


class TestParseJsonFromResponse(unittest.TestCase):
    """Test parsing JSON from AI responses."""

    def test_valid_json_response(self):
        """Should parse valid JSON response."""
        response = '{"has_violations": false, "severity": "none", "violations": [], "summary": "No issues"}'
        result = parse_json_from_response(response)
        self.assertEqual(result['has_violations'], False)
        self.assertEqual(result['severity'], 'none')
        self.assertEqual(result['summary'], 'No issues')

    def test_json_with_preamble(self):
        """Should extract JSON from response with extra text."""
        response = 'Here is my analysis:\n{"has_violations": true, "severity": "major", "violations": [], "summary": "Issues found"}\nThat is all.'
        result = parse_json_from_response(response)
        self.assertEqual(result['has_violations'], True)
        self.assertEqual(result['severity'], 'major')

    def test_invalid_json(self):
        """Should return safe default for invalid JSON."""
        response = 'This is not JSON at all'
        result = parse_json_from_response(response)
        self.assertEqual(result['has_violations'], False)
        self.assertEqual(result['severity'], 'none')
        self.assertIn('Could not parse', result['summary'])

    def test_empty_response(self):
        """Should handle empty response."""
        response = ''
        result = parse_json_from_response(response)
        self.assertEqual(result['has_violations'], False)
        self.assertEqual(result['severity'], 'none')


class TestMergeValidationResults(unittest.TestCase):
    """Test merging of path and world validation results."""

    def test_no_world_validation(self):
        """Should return path result unchanged when no world validation."""
        path_result = {
            'has_issues': False,
            'severity': 'none',
            'issues': [],
            'summary': 'Path OK'
        }
        result = merge_validation_results(path_result, None)
        self.assertEqual(result['has_issues'], False)
        self.assertEqual(result['severity'], 'none')
        self.assertIsNone(result['world_validation'])

    def test_both_clean(self):
        """Should combine two clean results."""
        path_result = {
            'has_issues': False,
            'severity': 'none',
            'issues': [],
            'summary': 'Path OK'
        }
        world_result = {
            'has_violations': False,
            'severity': 'none',
            'violations': [],
            'summary': 'World OK'
        }
        result = merge_validation_results(path_result, world_result)
        self.assertEqual(result['has_issues'], False)
        self.assertEqual(result['severity'], 'none')
        self.assertIsNotNone(result['world_validation'])

    def test_path_issues_only(self):
        """Should preserve path issues when world is clean."""
        path_result = {
            'has_issues': True,
            'severity': 'major',
            'issues': [{'type': 'plot', 'severity': 'major'}],
            'summary': 'Path has issues'
        }
        world_result = {
            'has_violations': False,
            'severity': 'none',
            'violations': [],
            'summary': 'World OK'
        }
        result = merge_validation_results(path_result, world_result)
        self.assertEqual(result['has_issues'], True)
        self.assertEqual(result['severity'], 'major')

    def test_world_issues_only(self):
        """Should flag issues when world has violations but path is clean."""
        path_result = {
            'has_issues': False,
            'severity': 'none',
            'issues': [],
            'summary': 'Path OK'
        }
        world_result = {
            'has_violations': True,
            'severity': 'critical',
            'violations': [{'type': 'world_rule', 'severity': 'critical'}],
            'summary': 'World violations'
        }
        result = merge_validation_results(path_result, world_result)
        self.assertEqual(result['has_issues'], True)
        self.assertEqual(result['severity'], 'critical')

    def test_both_have_issues_max_severity(self):
        """Should take maximum severity when both have issues."""
        path_result = {
            'has_issues': True,
            'severity': 'minor',
            'issues': [{'type': 'character', 'severity': 'minor'}],
            'summary': 'Path minor issues'
        }
        world_result = {
            'has_violations': True,
            'severity': 'critical',
            'violations': [{'type': 'world_rule', 'severity': 'critical'}],
            'summary': 'World critical issues'
        }
        result = merge_validation_results(path_result, world_result)
        self.assertEqual(result['has_issues'], True)
        self.assertEqual(result['severity'], 'critical')


class TestValidateAgainstStoryBible(unittest.TestCase):
    """Test main validation function."""

    def test_empty_cache(self):
        """Should skip validation for empty cache."""
        cache = {}
        result = validate_against_story_bible("Test passage", cache, "passage123")
        self.assertEqual(result['has_violations'], False)
        self.assertIn('No Story Bible constants', result['summary'])

    def test_no_constants(self):
        """Should skip validation when cache has no constants."""
        cache = {
            'categorized_facts': {
                'constants': {}
            }
        }
        result = validate_against_story_bible("Test passage", cache, "passage123")
        self.assertEqual(result['has_violations'], False)

    @patch('story_bible_validator.requests.post')
    def test_ollama_timeout(self, mock_post):
        """Should handle Ollama timeout gracefully."""
        import requests
        mock_post.side_effect = requests.Timeout()

        cache = {
            'categorized_facts': {
                'constants': {
                    'world_rules': [{'fact': 'Magic exists', 'evidence': 'test'}]
                }
            }
        }

        result = validate_against_story_bible("Test passage", cache, "passage123")
        self.assertEqual(result['has_violations'], False)
        self.assertIn('timed out', result['summary'])

    @patch('story_bible_validator.requests.post')
    def test_ollama_error(self, mock_post):
        """Should handle Ollama API errors gracefully."""
        mock_post.side_effect = Exception("API error")

        cache = {
            'categorized_facts': {
                'constants': {
                    'world_rules': [{'fact': 'Magic exists', 'evidence': 'test'}]
                }
            }
        }

        result = validate_against_story_bible("Test passage", cache, "passage123")
        self.assertEqual(result['has_violations'], False)
        self.assertIn('error', result['summary'])

    @patch('story_bible_validator.requests.post')
    def test_successful_validation_no_violations(self, mock_post):
        """Should parse successful validation with no violations."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'response': '{"has_violations": false, "severity": "none", "violations": [], "summary": "No issues"}'
        }
        mock_post.return_value = mock_response

        cache = {
            'categorized_facts': {
                'constants': {
                    'world_rules': [{'fact': 'Magic exists', 'evidence': 'test'}]
                }
            }
        }

        result = validate_against_story_bible("Test passage", cache, "passage123")
        self.assertEqual(result['has_violations'], False)
        self.assertEqual(result['severity'], 'none')

    @patch('story_bible_validator.requests.post')
    def test_successful_validation_with_violations(self, mock_post):
        """Should parse successful validation with violations."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'response': json.dumps({
                'has_violations': True,
                'severity': 'major',
                'violations': [
                    {
                        'type': 'world_rule',
                        'severity': 'major',
                        'description': 'Magic contradiction',
                        'constant_fact': 'Magic requires words',
                        'passage_statement': 'Silent spell cast'
                    }
                ],
                'summary': 'Found contradiction'
            })
        }
        mock_post.return_value = mock_response

        cache = {
            'categorized_facts': {
                'constants': {
                    'world_rules': [{'fact': 'Magic requires words', 'evidence': 'test'}]
                }
            }
        }

        result = validate_against_story_bible("Silent spell cast", cache, "passage123")
        self.assertEqual(result['has_violations'], True)
        self.assertEqual(result['severity'], 'major')
        self.assertEqual(len(result['violations']), 1)


if __name__ == '__main__':
    unittest.main()
