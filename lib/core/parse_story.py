#!/usr/bin/env python3
"""
Parse Story Module

Converts Tweego-compiled HTML into story_graph.json format.

This is the first stage of the core library pipeline:
Input: Tweego-compiled HTML file
Output: story_graph.json (passages, links, metadata)

Usage:
    python3 lib/core/parse_story.py input.html output.json
"""

import re
import sys
import json
import argparse
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Tuple


# =============================================================================
# HTML PARSING
# =============================================================================

class TweeStoryParser(HTMLParser):
    """Parse Tweego-compiled HTML to extract story data"""

    def __init__(self) -> None:
        super().__init__()
        self.story_data = {}
        self.passages = {}
        self.current_passage = None
        self.current_data = []
        self.in_passage = False

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        attrs_dict = dict(attrs)

        if tag == 'tw-storydata':
            self.story_data = {
                'name': attrs_dict.get('name', 'Untitled'),
                'ifid': attrs_dict.get('ifid', ''),
                'start': attrs_dict.get('startnode', '1'),
                'format': attrs_dict.get('format', 'Unknown'),
                'format_version': attrs_dict.get('format-version', 'Unknown'),
            }
        elif tag == 'tw-passagedata':
            self.in_passage = True
            self.current_passage = {
                'pid': attrs_dict.get('pid', ''),
                'name': attrs_dict.get('name', ''),
                'tags': attrs_dict.get('tags', '').split() if attrs_dict.get('tags') else [],
                'text': '',
            }
            self.current_data = []

    def handle_endtag(self, tag: str) -> None:
        if tag == 'tw-passagedata' and self.in_passage:
            self.current_passage['text'] = ''.join(self.current_data).strip()
            self.passages[self.current_passage['name']] = self.current_passage
            self.in_passage = False
            self.current_passage = None
            self.current_data = []

    def handle_data(self, data: str) -> None:
        if self.in_passage:
            self.current_data.append(data)


def parse_story_html(html_content: str) -> Tuple[Dict, Dict]:
    """Parse Tweego-compiled HTML and extract story data and passages.

    Args:
        html_content: Tweego-compiled HTML content as a string

    Returns:
        Tuple of (story_data, passages) where:
        - story_data: Dict with name, ifid, start, format, format_version
        - passages: Dict mapping passage name to passage data
    """
    parser = TweeStoryParser()
    parser.feed(html_content)
    return parser.story_data, parser.passages


# =============================================================================
# LINK PARSING
# =============================================================================

def parse_link(link_text: str) -> str:
    """Parse a Twee link and extract the target passage name.

    Supports three Twee link formats:
    - [[target]]
    - [[display->target]]
    - [[target<-display]]

    Args:
        link_text: The link text to parse (without surrounding [[ ]])

    Returns:
        The target passage name
    """
    # [[display->target]]
    if '->' in link_text:
        return link_text.split('->')[1].strip()
    # [[target<-display]]
    elif '<-' in link_text:
        return link_text.split('<-')[0].strip()
    # [[target]]
    else:
        return link_text.strip()


def extract_links(passage_text: str) -> List[str]:
    """Extract all link targets from passage text.

    Args:
        passage_text: Raw passage text containing Twee links

    Returns:
        List of unique link targets in order of appearance
    """
    links = re.findall(r'\[\[([^\]]+)\]\]', passage_text)
    targets = [parse_link(link) for link in links]

    # Remove duplicates while preserving order
    seen = set()
    unique_targets = []
    for t in targets:
        if t not in seen:
            seen.add(t)
            unique_targets.append(t)

    return unique_targets


# =============================================================================
# STORY GRAPH CONSTRUCTION
# =============================================================================

def parse_story(html_content: str) -> Dict:
    """Parse Tweego-compiled HTML and return story_graph data structure.

    This is the main entry point for the parse_story module.

    Args:
        html_content: Tweego-compiled HTML content as a string

    Returns:
        Dict with structure:
        {
            "passages": {
                "PassageName": {
                    "content": "passage text...",
                    "links": ["Link1", "Link2"]
                }
            },
            "start_passage": "Start",
            "metadata": {
                "story_title": "...",
                "ifid": "...",
                "format": "...",
                "format_version": "..."
            }
        }
    """
    # Parse HTML to extract raw story data and passages
    story_data, passages = parse_story_html(html_content)

    # Build the story_graph structure
    story_graph = {
        "passages": {},
        "start_passage": "",
        "metadata": {
            "story_title": story_data.get('name', 'Untitled'),
            "ifid": story_data.get('ifid', ''),
            "format": story_data.get('format', 'Unknown'),
            "format_version": story_data.get('format_version', 'Unknown'),
        }
    }

    # Find start passage by matching PID
    start_pid = story_data.get('start', '1')
    start_passage_name = None
    for name, passage in passages.items():
        if passage['pid'] == start_pid:
            start_passage_name = name
            break

    # Fallback to 'Start' if not found by PID
    if not start_passage_name:
        start_passage_name = 'Start' if 'Start' in passages else list(passages.keys())[0] if passages else 'Start'

    story_graph['start_passage'] = start_passage_name

    # Convert passages to story_graph format
    # Filter out special passages (StoryTitle, StoryData)
    for name, passage in passages.items():
        if name in ['StoryTitle', 'StoryData']:
            continue

        story_graph['passages'][name] = {
            'content': passage['text'],
            'links': extract_links(passage['text'])
        }

    return story_graph


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Parse Tweego HTML into story_graph.json format'
    )
    parser.add_argument('input_html', type=Path, help='Path to Tweego-compiled HTML file')
    parser.add_argument('output_json', type=Path, help='Path to output story_graph.json file')

    args = parser.parse_args()

    # Read input HTML
    if not args.input_html.exists():
        print(f"Error: Input file not found: {args.input_html}", file=sys.stderr)
        sys.exit(1)

    with open(args.input_html, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Parse story
    story_graph = parse_story(html_content)

    # Write output JSON
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump(story_graph, f, indent=2)

    print(f"✓ Parsed {len(story_graph['passages'])} passages", file=sys.stderr)
    print(f"✓ Start passage: {story_graph['start_passage']}", file=sys.stderr)
    print(f"✓ Output: {args.output_json}", file=sys.stderr)


if __name__ == '__main__':
    main()
