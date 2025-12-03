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
from interactive_fiction_validator import (
    validate_interactive_fiction_style,
    VALIDATION_PROMPT
)


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


if __name__ == '__main__':
    unittest.main()
