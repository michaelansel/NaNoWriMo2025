#!/usr/bin/env python3
"""
Stage 4: HTML Generator Module

Generates human-readable HTML Story Bible.

Input:
    - categorized_facts.json (from Stage 3)

Output:
    - dist/story-bible.html

Responsibilities:
    - Load Jinja2 template
    - Render facts with evidence
    - Generate navigation structure
    - Add git metadata (commit hash, timestamp)
"""

import json
import sys
import subprocess
from pathlib import Path
from typing import Dict
from datetime import datetime
from jinja2 import Environment, FileSystemLoader


def get_current_commit_hash() -> str:
    """
    Get current git commit hash.

    Returns:
        Short commit hash (8 chars) or 'unknown' if not in git repo
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short=8', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except:
        return 'unknown'


def format_date_for_display(iso_timestamp: str) -> str:
    """
    Format ISO timestamp for human-readable display.

    Args:
        iso_timestamp: ISO 8601 timestamp string

    Returns:
        Formatted date string
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except:
        return iso_timestamp


def generate_html_output(categorized_facts: Dict, output_path: Path) -> None:
    """
    Generate HTML Story Bible output.

    Args:
        categorized_facts: Output from Stage 3 (categorizer)
        output_path: Path to write story-bible.html

    Raises:
        FileNotFoundError: If template not found
        RuntimeError: If rendering fails
    """
    print("\nGenerating HTML output...", file=sys.stderr)

    # Get git metadata
    commit_hash = get_current_commit_hash()
    generated_at = datetime.now().isoformat()

    # Get template directory
    template_dir = Path(__file__).parent.parent / 'templates'

    if not template_dir.exists():
        raise FileNotFoundError(f"Template directory not found: {template_dir}")

    # Load Jinja2 environment
    env = Environment(loader=FileSystemLoader(str(template_dir)))

    # Get template
    try:
        template = env.get_template('story-bible.html.jinja2')
    except Exception as e:
        raise FileNotFoundError(f"Template not found: {e}")

    # Prepare template data
    template_data = {
        'story_title': 'NaNoWriMo2025',  # Could be extracted from story data
        'generated_at': format_date_for_display(generated_at),
        'commit_hash': commit_hash,
        'constants': categorized_facts.get('constants', {}),
        'characters': categorized_facts.get('characters', {}),
        'variables': categorized_facts.get('variables', {}),
        'conflicts': categorized_facts.get('conflicts', []),
        'metadata': categorized_facts.get('metadata', {})
    }

    # Render template
    try:
        html = template.render(**template_data)
    except Exception as e:
        raise RuntimeError(f"Failed to render template: {e}")

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"Generated HTML: {output_path}", file=sys.stderr)


def main():
    """Test HTML generator functionality."""
    import argparse

    parser = argparse.ArgumentParser(description='Test HTML generator module')
    parser.add_argument('categorized_facts', type=Path, help='Path to categorized_facts.json from Stage 3')
    parser.add_argument('output', type=Path, help='Output HTML file path')

    args = parser.parse_args()

    # Load input data
    with open(args.categorized_facts, 'r', encoding='utf-8') as f:
        categorized_facts = json.load(f)

    # Generate HTML
    generate_html_output(categorized_facts, args.output)

    print(f"\nHTML generation complete: {args.output}")


if __name__ == '__main__':
    main()
