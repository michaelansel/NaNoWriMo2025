#!/usr/bin/env python3
"""
Tests for continuity-webhook.py

Focus on testing webhook handlers and ensuring both continuity checking
and Story Bible extraction run automatically after successful builds.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import json
import sys
from pathlib import Path

# Import the webhook module
sys.path.insert(0, str(Path(__file__).parent))
import importlib.util
spec = importlib.util.spec_from_file_location("continuity_webhook", Path(__file__).parent / "continuity-webhook.py")
webhook_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(webhook_module)


class TestWorkflowWebhook(unittest.TestCase):
    """Test automatic triggering of continuity checking and Story Bible extraction."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_workflow_payload = {
            "action": "completed",
            "workflow_run": {
                "id": 12345,
                "event": "pull_request",
                "conclusion": "success",
                "artifacts_url": "https://api.github.com/repos/owner/repo/actions/runs/12345/artifacts"
            }
        }

    @patch('continuity_webhook.get_pr_number_from_workflow')
    @patch('continuity_webhook.threading.Thread')
    @patch('continuity_webhook.metrics_lock')
    @patch('continuity_webhook.processed_workflow_runs', {})
    @patch('continuity_webhook.active_jobs', {})
    @patch('continuity_webhook.pr_active_jobs', {})
    def test_successful_workflow_triggers_both_continuity_and_extraction(
        self, mock_metrics_lock, mock_thread, mock_get_pr
    ):
        """Test that successful PR build triggers BOTH continuity check AND Story Bible extraction."""
        # Arrange
        mock_get_pr.return_value = 42

        # Mock the Thread class to capture what gets spawned
        thread_instances = []
        def create_mock_thread(*args, **kwargs):
            mock_thread_obj = MagicMock()
            thread_instances.append({
                'target': kwargs.get('target'),
                'args': kwargs.get('args'),
                'kwargs': kwargs
            })
            return mock_thread_obj

        mock_thread.side_effect = create_mock_thread

        # Act
        with patch.object(webhook_module.app, 'logger'):
            result = webhook_module.handle_workflow_webhook(self.sample_workflow_payload)

        # Assert
        # Should return 202 Accepted
        self.assertEqual(result[1], 202)

        # Should have spawned TWO threads
        self.assertEqual(len(thread_instances), 2,
            f"Expected 2 threads (continuity + extraction), got {len(thread_instances)}")

        # First thread: continuity checking
        continuity_thread = thread_instances[0]
        self.assertEqual(continuity_thread['target'].__name__, 'process_webhook_async')
        self.assertEqual(continuity_thread['args'][0], 12345)  # workflow_id
        self.assertEqual(continuity_thread['args'][1], 42)     # pr_number
        self.assertEqual(continuity_thread['args'][3], 'new-only')  # mode for continuity

        # Second thread: Story Bible extraction
        extraction_thread = thread_instances[1]
        self.assertEqual(extraction_thread['target'].__name__, 'process_story_bible_extraction_async')
        self.assertEqual(extraction_thread['args'][1], 42)     # pr_number
        # Should use incremental mode for automatic extraction
        self.assertEqual(extraction_thread['args'][4], 'incremental')

    @patch('continuity_webhook.get_pr_number_from_workflow')
    @patch('continuity_webhook.threading.Thread')
    @patch('continuity_webhook.metrics_lock')
    @patch('continuity_webhook.processed_workflow_runs', {})
    @patch('continuity_webhook.active_jobs', {})
    @patch('continuity_webhook.pr_active_jobs', {})
    def test_failed_workflow_does_not_trigger_extraction(
        self, mock_metrics_lock, mock_thread, mock_get_pr
    ):
        """Test that failed workflows don't trigger extraction (only successful builds should)."""
        # Arrange
        failed_payload = {
            "action": "completed",
            "workflow_run": {
                "id": 12345,
                "event": "pull_request",
                "conclusion": "failure",  # Failed build
                "artifacts_url": "https://api.github.com/repos/owner/repo/actions/runs/12345/artifacts"
            }
        }

        # Act
        with patch.object(webhook_module.app, 'logger'):
            result = webhook_module.handle_workflow_webhook(failed_payload)

        # Assert
        # Should return 200 with "not successful" message
        self.assertEqual(result[1], 200)

        # Should NOT have spawned any threads
        mock_thread.assert_not_called()


if __name__ == '__main__':
    unittest.main()
