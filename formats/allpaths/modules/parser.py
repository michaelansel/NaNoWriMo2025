#!/usr/bin/env python3
"""
AllPaths Parser Module (Stage 1: Parse & Extract)

Converts Tweego-compiled HTML into a clean story_graph data structure.
This is the first stage of the AllPaths pipeline.

Input: Tweego-compiled HTML file
Output: story_graph dict with passages, links, and metadata
"""

import re
from html.parser import HTMLParser
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
    """Parse Tweego-compiled HTML and extract story data and passages"""
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
    # [[target]]
    # [[display->target]]
    # [[target<-display]]
    if '->' in link_text:
        return link_text.split('->')[1].strip()
    elif '<-' in link_text:
        return link_text.split('<-')[0].strip()
    else:
        return link_text.strip()


def extract_links(passage_text: str) -> List[str]:
    """Extract all link targets from passage text"""
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
# GRAPH CONSTRUCTION
# =============================================================================

def build_graph(passages: Dict) -> Dict[str, List[str]]:
    """Build a directed graph from passages"""
    graph = {}

    for name, passage in passages.items():
        # Skip special passages
        if name in ['StoryTitle', 'StoryData']:
            continue

        links = extract_links(passage['text'])
        graph[name] = links

    return graph


# =============================================================================
# MAIN PARSER FUNCTION
# =============================================================================

def parse_story(html_content: str) -> Dict:
    """Parse Tweego-compiled HTML and return story_graph data structure.

    This is the main entry point for Stage 1 (Parse & Extract) of the
    AllPaths pipeline.

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
        start_passage_name = 'Start' if 'Start' in passages else list(passages.keys())[0]

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
