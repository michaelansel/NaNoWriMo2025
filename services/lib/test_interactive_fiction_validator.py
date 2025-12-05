#!/usr/bin/env python3
"""
Tests for interactive_fiction_validator.py with configurable story styles.

Tests validate that the validator can check for:
- Different perspectives (first/second/third person)
- Different protagonist handling (named vs unnamed)
- Different tenses (past/present)
"""

import unittest
from unittest.mock import patch, MagicMock
from interactive_fiction_validator import validate_interactive_fiction_style


class TestInteractiveFictionValidator(unittest.TestCase):
    """Test suite for Interactive Fiction validator with configurable story styles."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_second_person = """
You walk through the forest. The trees tower above you.
You hear a noise behind you and turn around.
What do you do?
"""

        self.sample_third_person = """
Javlyn walks through the forest. The trees tower above her.
She hears a noise behind her and turns around.
What does she do?
"""

        self.sample_first_person = """
I walk through the forest. The trees tower above me.
I hear a noise behind me and turn around.
What do I do?
"""

    @patch('interactive_fiction_validator.requests.post')
    def test_default_second_person_validation(self, mock_post):
        """Test that default behavior validates for second person present tense."""
        # Mock Ollama response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'response': '{"has_issues": false, "severity": "none", "issues": [], "summary": "No issues"}'
        }
        mock_post.return_value = mock_response

        # Call without story_style (should default to second person)
        result = validate_interactive_fiction_style(
            passage_text=self.sample_second_person,
            passage_id="test-1"
        )

        # Check that prompt contains second person guidance
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']
        self.assertIn("second person", prompt.lower())
        self.assertIn("you", prompt.lower())

    @patch('interactive_fiction_validator.requests.post')
    def test_third_person_with_protagonist(self, mock_post):
        """Test validation for third person with named protagonist."""
        # Mock Ollama response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'response': '{"has_issues": false, "severity": "none", "issues": [], "summary": "No issues"}'
        }
        mock_post.return_value = mock_response

        # Call with third person story style
        story_style = {
            "perspective": "third-person",
            "protagonist": "Javlyn",
            "tense": "past"
        }

        result = validate_interactive_fiction_style(
            passage_text=self.sample_third_person,
            passage_id="test-2",
            story_style=story_style
        )

        # Check that prompt contains third person guidance
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']
        self.assertIn("third person", prompt.lower())
        self.assertIn("Javlyn", prompt)
        self.assertIn("past tense", prompt.lower())

    @patch('interactive_fiction_validator.requests.post')
    def test_first_person_validation(self, mock_post):
        """Test validation for first person."""
        # Mock Ollama response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'response': '{"has_issues": false, "severity": "none", "issues": [], "summary": "No issues"}'
        }
        mock_post.return_value = mock_response

        # Call with first person story style
        story_style = {
            "perspective": "first-person",
            "protagonist": None,
            "tense": "present"
        }

        result = validate_interactive_fiction_style(
            passage_text=self.sample_first_person,
            passage_id="test-3",
            story_style=story_style
        )

        # Check that prompt contains first person guidance
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']
        self.assertIn("first person", prompt.lower())
        self.assertIn("present tense", prompt.lower())

    @patch('interactive_fiction_validator.requests.post')
    def test_backwards_compatibility_no_config(self, mock_post):
        """Test that validator works without story_style parameter (backwards compatible)."""
        # Mock Ollama response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'response': '{"has_issues": false, "severity": "none", "issues": [], "summary": "No issues"}'
        }
        mock_post.return_value = mock_response

        # Call without story_style parameter
        result = validate_interactive_fiction_style(
            passage_text=self.sample_second_person,
            passage_id="test-4"
        )

        # Should not raise error and should default to second person
        self.assertIsNotNone(result)
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']
        self.assertIn("second person", prompt.lower())

    @patch('interactive_fiction_validator.requests.post')
    def test_protagonist_consistency_issue_type_in_prompt(self, mock_post):
        """Test that prompt uses 'protagonist_consistency' as issue type, not 'protagonist_immersion'."""
        # Mock Ollama response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'response': '{"has_issues": false, "severity": "none", "issues": [], "summary": "No issues"}'
        }
        mock_post.return_value = mock_response

        # Call with default second-person config (triggers protagonist validation)
        result = validate_interactive_fiction_style(
            passage_text=self.sample_second_person,
            passage_id="test-protagonist-terminology"
        )

        # Check that prompt contains 'protagonist_consistency' as issue type
        call_args = mock_post.call_args
        prompt = call_args[1]['json']['prompt']
        self.assertIn("protagonist_consistency", prompt)
        self.assertNotIn("protagonist_immersion", prompt)


class TestInteractiveFictionValidatorErrorPaths(unittest.TestCase):
    """Test suite for error handling in Interactive Fiction validator."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_passage = "You walk through the forest."

    @patch('interactive_fiction_validator.requests.post')
    def test_timeout_returns_empty_issues(self, mock_post):
        """Test that timeout returns empty issues list, not crash."""
        # Mock timeout exception
        mock_post.side_effect = __import__('requests').Timeout("Connection timed out")

        # Call validator
        result = validate_interactive_fiction_style(
            passage_text=self.sample_passage,
            passage_id="test-timeout"
        )

        # Verify graceful degradation
        self.assertIsNotNone(result)
        self.assertEqual(result['has_issues'], False)
        self.assertEqual(result['severity'], 'none')
        self.assertEqual(result['issues'], [])
        self.assertIn("timed out", result['summary'].lower())

    @patch('interactive_fiction_validator.requests.post')
    def test_json_decode_error_returns_empty_issues(self, mock_post):
        """Test that JSONDecodeError returns empty issues list, not crash."""
        # Mock response with invalid JSON
        mock_response = MagicMock()
        mock_response.json.side_effect = __import__('json').JSONDecodeError("Invalid JSON", "", 0)
        mock_post.return_value = mock_response

        # Call validator
        result = validate_interactive_fiction_style(
            passage_text=self.sample_passage,
            passage_id="test-json-error"
        )

        # Verify graceful degradation
        self.assertIsNotNone(result)
        self.assertEqual(result['has_issues'], False)
        self.assertEqual(result['severity'], 'none')
        self.assertEqual(result['issues'], [])
        self.assertIn("error", result['summary'].lower())

    @patch('interactive_fiction_validator.requests.post')
    def test_malformed_ai_response_returns_empty_issues(self, mock_post):
        """Test that malformed AI response (missing expected fields) returns empty issues."""
        # Mock response with malformed structure (no 'response' field)
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'unexpected_field': 'some value'
        }
        mock_post.return_value = mock_response

        # Call validator
        result = validate_interactive_fiction_style(
            passage_text=self.sample_passage,
            passage_id="test-malformed-response"
        )

        # Verify graceful degradation
        # The parse_json_from_response should handle this gracefully
        self.assertIsNotNone(result)
        self.assertEqual(result['has_issues'], False)
        self.assertEqual(result['severity'], 'none')
        self.assertEqual(result['issues'], [])

    @patch('interactive_fiction_validator.requests.post')
    def test_http_error_returns_empty_issues(self, mock_post):
        """Test that HTTP errors return empty issues list, not crash."""
        # Mock HTTP error
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = __import__('requests').HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        # Call validator
        result = validate_interactive_fiction_style(
            passage_text=self.sample_passage,
            passage_id="test-http-error"
        )

        # Verify graceful degradation
        self.assertIsNotNone(result)
        self.assertEqual(result['has_issues'], False)
        self.assertEqual(result['severity'], 'none')
        self.assertEqual(result['issues'], [])
        self.assertIn("error", result['summary'].lower())

    @patch('interactive_fiction_validator.requests.post')
    def test_connection_error_returns_empty_issues(self, mock_post):
        """Test that connection errors return empty issues list, not crash."""
        # Mock connection error
        mock_post.side_effect = __import__('requests').ConnectionError("Failed to connect")

        # Call validator
        result = validate_interactive_fiction_style(
            passage_text=self.sample_passage,
            passage_id="test-connection-error"
        )

        # Verify graceful degradation
        self.assertIsNotNone(result)
        self.assertEqual(result['has_issues'], False)
        self.assertEqual(result['severity'], 'none')
        self.assertEqual(result['issues'], [])
        self.assertIn("error", result['summary'].lower())


if __name__ == '__main__':
    unittest.main()
