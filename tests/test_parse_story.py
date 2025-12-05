#!/usr/bin/env python3
"""
Tests for lib/core/parse_story.py

Tests the core story parsing functionality that converts Tweego HTML
into story_graph.json format.
"""

import sys
import json
from pathlib import Path

# Add lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.core.parse_story import parse_story


def test_parse_story_basic():
    """Test parsing basic Tweego HTML."""
    html = """
    <tw-storydata name="Test Story" startnode="1" ifid="ABC-123" format="Harlowe" format-version="3.3.9">
        <tw-passagedata pid="1" name="Start">Welcome to the story.</tw-passagedata>
        <tw-passagedata pid="2" name="Continue">The story continues. [[Next]]</tw-passagedata>
        <tw-passagedata pid="3" name="Next">The end.</tw-passagedata>
    </tw-storydata>
    """

    result = parse_story(html)

    # Verify structure
    assert 'passages' in result
    assert 'start_passage' in result
    assert 'metadata' in result

    # Verify start passage
    assert result['start_passage'] == 'Start'

    # Verify passages
    assert 'Start' in result['passages']
    assert result['passages']['Start']['content'] == 'Welcome to the story.'
    assert result['passages']['Start']['links'] == []

    assert 'Continue' in result['passages']
    assert result['passages']['Continue']['content'] == 'The story continues. [[Next]]'
    assert result['passages']['Continue']['links'] == ['Next']

    # Verify metadata
    assert result['metadata']['story_title'] == 'Test Story'
    assert result['metadata']['ifid'] == 'ABC-123'
    assert result['metadata']['format'] == 'Harlowe'
    assert result['metadata']['format_version'] == '3.3.9'


def test_parse_story_filters_special_passages():
    """Test that special passages like StoryData and StoryTitle are excluded."""
    html = """
    <tw-storydata name="Test" startnode="1">
        <tw-passagedata pid="1" name="Start">Story starts here.</tw-passagedata>
        <tw-passagedata pid="2" name="StoryTitle">My Story</tw-passagedata>
        <tw-passagedata pid="3" name="StoryData">{"ifid": "..."}</tw-passagedata>
    </tw-storydata>
    """

    result = parse_story(html)

    # Special passages should be excluded
    assert 'Start' in result['passages']
    assert 'StoryTitle' not in result['passages']
    assert 'StoryData' not in result['passages']


def test_parse_story_multiple_links():
    """Test parsing passage with multiple links."""
    html = """
    <tw-storydata name="Test" startnode="1">
        <tw-passagedata pid="1" name="Start">Choose: [[Option A]] or [[Option B]]</tw-passagedata>
        <tw-passagedata pid="2" name="Option A">You chose A</tw-passagedata>
        <tw-passagedata pid="3" name="Option B">You chose B</tw-passagedata>
    </tw-storydata>
    """

    result = parse_story(html)

    # Verify multiple links extracted
    assert set(result['passages']['Start']['links']) == {'Option A', 'Option B'}


def test_parse_story_link_formats():
    """Test parsing different Twee link formats."""
    html = """
    <tw-storydata name="Test" startnode="1">
        <tw-passagedata pid="1" name="Start">
            Simple: [[Target1]]
            Display: [[Click here->Target2]]
            Reverse: [[Target3<-Different text]]
        </tw-passagedata>
    </tw-storydata>
    """

    result = parse_story(html)

    # All link formats should extract the target
    links = set(result['passages']['Start']['links'])
    assert 'Target1' in links
    assert 'Target2' in links
    assert 'Target3' in links


def test_parse_story_empty():
    """Test parsing empty story."""
    html = """
    <tw-storydata name="Empty" startnode="1">
        <tw-passagedata pid="1" name="Start"></tw-passagedata>
    </tw-storydata>
    """

    result = parse_story(html)

    assert result['passages']['Start']['content'] == ''
    assert result['passages']['Start']['links'] == []


def test_parse_story_start_passage_by_pid():
    """Test that start passage is identified by PID, not name."""
    html = """
    <tw-storydata name="Test" startnode="5">
        <tw-passagedata pid="1" name="Start">Not the start!</tw-passagedata>
        <tw-passagedata pid="5" name="Beginning">This is the start.</tw-passagedata>
    </tw-storydata>
    """

    result = parse_story(html)

    # Start passage should be "Beginning" (pid 5), not "Start" (pid 1)
    assert result['start_passage'] == 'Beginning'


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
