#!/usr/bin/env python3
"""
Build Mappings Module

Builds passage name/ID/file mappings from story_graph and source files.

This is the third stage of the core library pipeline:
Input: story_graph.json (from parse_story) + src/ directory
Output: passage_mapping.json (name ↔ ID ↔ file mappings)

Usage:
    python3 lib/core/build_mappings.py story_graph.json passage_mapping.json --src src/
"""

import sys
import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Optional


def parse_twee_file_for_passages(twee_path: Path) -> List[Dict]:
    """Parse a Twee file and extract passage names with line numbers.

    Args:
        twee_path: Path to .twee file

    Returns:
        List of dicts with 'name' and 'line' for each passage
    """
    try:
        with open(twee_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except (IOError, UnicodeDecodeError):
        return []

    passages = []
    # Pattern: :: PassageName [optional tags]
    passage_pattern = re.compile(r'^::\s+([^\[\n]+?)(?:\s+\[.*?\])?\s*$', re.MULTILINE)

    for match in passage_pattern.finditer(content):
        passage_name = match.group(1).strip()
        # Calculate line number (count newlines before match)
        line_num = content[:match.start()].count('\n') + 1

        passages.append({
            'name': passage_name,
            'line': line_num
        })

    return passages


def build_passage_to_file_mapping(src_dir: Path) -> Dict[str, Dict]:
    """Build mapping from passage names to their source files.

    Args:
        src_dir: Path to source directory containing .twee files

    Returns:
        Dict mapping passage name to {'file': path, 'line': line_num}
    """
    if not src_dir.exists():
        return {}

    mapping = {}

    # Find all .twee files
    for twee_file in sorted(src_dir.glob('*.twee')):
        passages = parse_twee_file_for_passages(twee_file)

        for passage_info in passages:
            # Use relative path from project root
            relative_path = str(twee_file.relative_to(src_dir.parent))

            mapping[passage_info['name']] = {
                'file': relative_path,
                'line': passage_info['line']
            }

    return mapping


def build_mappings(story_graph: Dict, src_dir: Optional[Path] = None) -> Dict:
    """Build passage name/ID/file mappings from story graph.

    Args:
        story_graph: Dict from parse_story() with passages, start_passage, metadata
        src_dir: Optional path to source directory (default: src/)

    Returns:
        Dict conforming to passage_mapping.schema.json:
        {
            "by_name": {
                "PassageName": {
                    "file": "src/file.twee",
                    "line": 1
                }
            },
            "by_id": {
                "passage_id": {
                    "name": "PassageName",
                    "file": "src/file.twee",
                    "line": 1
                }
            },
            "by_file": {
                "src/file.twee": [
                    {"name": "PassageName", "line": 1}
                ]
            }
        }
    """
    # Default to src/ directory
    if src_dir is None:
        src_dir = Path('src')

    # Build passage-to-file mapping from source files
    passage_to_file = build_passage_to_file_mapping(src_dir)

    # Initialize mapping structures
    by_name = {}
    by_id = {}
    by_file = {}

    # Build mappings for each passage in story graph
    for passage_name in sorted(story_graph.get('passages', {}).keys()):
        # Get file info if available
        file_info = passage_to_file.get(passage_name, {})

        # Build by_name entry
        by_name[passage_name] = {
            'file': file_info.get('file'),
            'line': file_info.get('line')
        }

        # Build by_file entry
        if file_info.get('file'):
            file_path = file_info['file']
            if file_path not in by_file:
                by_file[file_path] = []

            by_file[file_path].append({
                'name': passage_name,
                'line': file_info.get('line')
            })

    return {
        'by_name': by_name,
        'by_id': by_id,  # Kept for future use (would need ID generation)
        'by_file': by_file
    }


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description='Build passage mappings from story_graph.json and source files'
    )
    parser.add_argument('input_json', type=Path, help='Path to story_graph.json file')
    parser.add_argument('output_json', type=Path, help='Path to output passage_mapping.json file')
    parser.add_argument('--src', type=Path, default=Path('src'),
                       help='Source directory containing .twee files (default: src/)')

    args = parser.parse_args()

    # Read input JSON
    if not args.input_json.exists():
        print(f"Error: Input file not found: {args.input_json}", file=sys.stderr)
        sys.exit(1)

    with open(args.input_json, 'r', encoding='utf-8') as f:
        story_graph = json.load(f)

    # Build mappings
    mappings = build_mappings(story_graph, args.src)

    # Write output JSON
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output_json, 'w', encoding='utf-8') as f:
        json.dump(mappings, f, indent=2)

    passage_count = len(mappings['by_name'])
    file_count = len(mappings['by_file'])

    print(f"✓ Mapped {passage_count} passages across {file_count} files", file=sys.stderr)
    print(f"✓ Output: {args.output_json}", file=sys.stderr)


if __name__ == '__main__':
    main()
