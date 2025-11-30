#!/usr/bin/env python3
"""
Stage 5: JSON Generator Module

Generates machine-readable JSON Story Bible.

Input:
    - categorized_facts.json (from Stage 3)

Output:
    - dist/story-bible.json

Responsibilities:
    - Build JSON structure
    - Add metadata (timestamp, commit hash)
    - Validate against schema (optional)
    - Write JSON output
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import Dict
from datetime import datetime


def get_current_commit_hash() -> str:
    """
    Get current git commit hash.

    Returns:
        Full commit hash or 'unknown' if not in git repo
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except:
        return 'unknown'


def generate_json_output(categorized_facts: Dict, output_path: Path) -> None:
    """
    Generate JSON Story Bible output.

    Args:
        categorized_facts: Output from Stage 3 (categorizer)
        output_path: Path to write story-bible.json

    Raises:
        RuntimeError: If JSON generation fails
    """
    print("\nGenerating JSON output...", file=sys.stderr)

    # Build JSON structure
    story_bible = {
        "meta": {
            "generated": datetime.now().isoformat(),
            "commit": get_current_commit_hash(),
            "version": "1.0",
            "schema_version": "1.0.0"
        },
        "constants": categorized_facts.get('constants', {}),
        "characters": categorized_facts.get('characters', {}),
        "variables": categorized_facts.get('variables', {}),
        "conflicts": categorized_facts.get('conflicts', []),
        "metadata": categorized_facts.get('metadata', {})
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(story_bible, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise RuntimeError(f"Failed to write JSON output: {e}")

    print(f"Generated JSON: {output_path}", file=sys.stderr)


def main():
    """Test JSON generator functionality."""
    import argparse

    parser = argparse.ArgumentParser(description='Test JSON generator module')
    parser.add_argument('categorized_facts', type=Path, help='Path to categorized_facts.json from Stage 3')
    parser.add_argument('output', type=Path, help='Output JSON file path')

    args = parser.parse_args()

    # Load input data
    with open(args.categorized_facts, 'r', encoding='utf-8') as f:
        categorized_facts = json.load(f)

    # Generate JSON
    generate_json_output(categorized_facts, args.output)

    print(f"\nJSON generation complete: {args.output}")


if __name__ == '__main__':
    main()
