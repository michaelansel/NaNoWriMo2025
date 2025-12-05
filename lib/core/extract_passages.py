#!/usr/bin/env python3
"""
Extract Passages Module

Extracts flat passage list from story_graph into passages_deduplicated.json format.

This is the second stage of the core library pipeline:
Input: story_graph.json (from parse_story)
Output: passages_deduplicated.json (flat list of passages with hashes)

Usage:
    python3 lib/core/extract_passages.py story_graph.json passages_deduplicated.json
"""

import sys
import json
import hashlib
import argparse
from pathlib import Path
from typing import Dict, List


def calculate_content_hash(content: str) -> str:
    """Calculate a stable hash of passage content for deduplication.

    Args:
        content: Passage content text

    Returns:
        Hex digest of content hash (first 16 characters)
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]


def extract_passages(story_graph: Dict) -> Dict:
    """Extract flat list of deduplicated passages from story graph.

    Args:
        story_graph: Dict from parse_story() with passages, start_passage, metadata

    Returns:
        Dict conforming to passages_deduplicated.schema.json:
        {
            "passages": [
                {
                    "name": "PassageName",
                    "content": "passage text...",
                    "content_hash": "abc123..."
                }
            ]
        }
    """
    passages = []

    # Extract passages in sorted order (by name) for stability
    for name in sorted(story_graph.get('passages', {}).keys()):
        passage_data = story_graph['passages'][name]

        passage_obj = {
            'name': name,
            'content': passage_data['content'],
            'content_hash': calculate_content_hash(passage_data['content'])
        }

        passages.append(passage_obj)

    return {
        'passages': passages
    }


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Extract passages from story_graph.json into passages_deduplicated.json'
    )
    parser.add_argument('input_json', type=Path, help='Path to story_graph.json file')
    parser.add_argument('output_json', type=Path, help='Path to output passages_deduplicated.json file')

    args = parser.parse_args()

    # Read input JSON
    if not args.input_json.exists():
        print(f"Error: Input file not found: {args.input_json}", file=sys.stderr)
        sys.exit(1)

    with open(args.input_json, 'r', encoding='utf-8') as f:
        story_graph = json.load(f)

    # Extract passages
    passages_data = extract_passages(story_graph)

    # Write output JSON
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump(passages_data, f, indent=2)

    print(f"✓ Extracted {len(passages_data['passages'])} passages", file=sys.stderr)
    print(f"✓ Output: {args.output_json}", file=sys.stderr)


if __name__ == '__main__':
    main()
