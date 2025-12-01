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


def normalize_evidence(evidence):
    """
    Normalize evidence to array of objects format.

    The cache may have evidence as:
    - A string: "Some quote text"
    - An array of strings: ["quote1", "quote2"]
    - An array of objects: [{"passage": "Start", "quote": "..."}]

    This function normalizes to array of objects format for the template.

    Args:
        evidence: Evidence in any format

    Returns:
        List of dicts with 'passage' and 'quote' keys
    """
    if evidence is None:
        return []

    if isinstance(evidence, str):
        # Single string - convert to single-item array
        return [{'passage': 'Source', 'quote': evidence}]

    if isinstance(evidence, list):
        result = []
        for item in evidence:
            if isinstance(item, str):
                # String in array - convert to object
                result.append({'passage': 'Source', 'quote': item})
            elif isinstance(item, dict):
                # Already an object - ensure it has required keys
                result.append({
                    'passage': item.get('passage', 'Source'),
                    'quote': item.get('quote', str(item))
                })
            else:
                # Unknown type - convert to string
                result.append({'passage': 'Source', 'quote': str(item)})
        return result

    # Unknown type - convert to string
    return [{'passage': 'Source', 'quote': str(evidence)}]


def normalize_facts(facts_list):
    """
    Normalize a list of facts, ensuring evidence is in correct format.

    Args:
        facts_list: List of fact dictionaries

    Returns:
        List of facts with normalized evidence
    """
    if not facts_list:
        return []

    result = []
    for fact in facts_list:
        normalized_fact = dict(fact)  # Copy
        normalized_fact['evidence'] = normalize_evidence(fact.get('evidence'))
        result.append(normalized_fact)
    return result


def normalize_constants(constants):
    """Normalize all fact lists in constants dict."""
    if not constants:
        return {}

    return {
        'world_rules': normalize_facts(constants.get('world_rules', [])),
        'setting': normalize_facts(constants.get('setting', [])),
        'timeline': normalize_facts(constants.get('timeline', []))
    }


def normalize_variables(variables):
    """Normalize all fact lists in variables dict."""
    if not variables:
        return {}

    return {
        'events': normalize_facts(variables.get('events', [])),
        'outcomes': normalize_facts(variables.get('outcomes', []))
    }


def normalize_characters(characters):
    """Normalize all fact lists in characters dict.

    Preserves passages and mentions fields from entity-first summarizer.
    """
    if not characters:
        return {}

    result = {}
    for char_name, char_data in characters.items():
        result[char_name] = {
            'identity': normalize_facts(char_data.get('identity', [])),
            'zero_action_state': normalize_facts(char_data.get('zero_action_state', [])),
            'variables': normalize_facts(char_data.get('variables', []))
        }

        # Preserve passages field if present (entity-first summarizer)
        if 'passages' in char_data:
            result[char_name]['passages'] = char_data['passages']

        # Preserve mentions field if present (entity-first summarizer)
        if 'mentions' in char_data:
            result[char_name]['mentions'] = char_data['mentions']

    return result


def normalize_conflicts(conflicts):
    """Normalize conflicts list."""
    if not conflicts:
        return []

    result = []
    for conflict in conflicts:
        normalized = dict(conflict)
        if 'facts' in conflict:
            normalized['facts'] = normalize_facts(conflict['facts'])
        result.append(normalized)
    return result


def generate_html_output(categorized_facts: Dict, output_path: Path) -> None:
    """
    Generate HTML Story Bible output.

    Args:
        categorized_facts: Output from Stage 3 (categorizer) or cache
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

    # Normalize data to ensure evidence is in correct format
    # (cache may have evidence as strings, template expects objects)
    constants = normalize_constants(categorized_facts.get('constants', {}))
    characters = normalize_characters(categorized_facts.get('characters', {}))
    variables = normalize_variables(categorized_facts.get('variables', {}))
    conflicts = normalize_conflicts(categorized_facts.get('conflicts', []))

    # Get metadata and view type
    metadata = categorized_facts.get('metadata', {})
    view_type = metadata.get('view_type', 'unknown')

    # Normalize per-passage facts if present
    per_passage_raw = categorized_facts.get('per_passage', {})
    per_passage = {}
    for passage_id, passage_data in per_passage_raw.items():
        per_passage[passage_id] = {
            'passage_name': passage_data.get('passage_name', 'Unknown'),
            'facts': normalize_facts(passage_data.get('facts', []))
        }

    # Prepare template data
    template_data = {
        'story_title': 'NaNoWriMo2025',  # Could be extracted from story data
        'generated_at': format_date_for_display(generated_at),
        'commit_hash': commit_hash,
        'constants': constants,
        'characters': characters,
        'variables': variables,
        'conflicts': conflicts,
        'per_passage': per_passage,
        'metadata': metadata,
        'view_type': view_type  # Pass view_type separately for easy access in template
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
