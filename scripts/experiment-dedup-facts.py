#!/usr/bin/env python3
"""
Deduplicate and summarize facts from chunked extraction.

Takes the raw chunked results and consolidates them into a clean story bible.

Usage:
    python scripts/experiment-dedup-facts.py experiment-chunked-results.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime
import requests
import time

OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 120

# Dedup prompt for each category
DEDUP_PROMPT = """You are consolidating story facts into a clean story bible.

Below are {count} facts about "{category}" extracted from an interactive fiction story.
Many facts are duplicates or variations of the same information.

Your task:
1. Merge duplicate/similar facts into single authoritative facts
2. Keep the most specific and accurate version
3. Preserve important details, discard redundancy
4. Output clean, deduplicated facts

Input facts:
{facts}

Output JSON only - a deduplicated list:

{{
  "facts": [
    {{
      "fact": "Clean, authoritative statement",
      "confidence": "high|medium|low",
      "category": "constant|variable"
    }}
  ]
}}

Deduplicate now:"""

CHARACTER_PROMPT = """You are building character profiles for a story bible.

Below are facts mentioning various characters from an interactive fiction story.
Consolidate these into clean character profiles.

Input facts:
{facts}

For each unique character, create a profile with:
- identity: Who they are (background, role, appearance)
- relationships: Connections to other characters
- key_facts: Important details about them

Output JSON only:

{{
  "characters": {{
    "CharacterName": {{
      "identity": "Single sentence description",
      "relationships": ["relationship to other character", ...],
      "key_facts": ["fact 1", "fact 2", ...]
    }}
  }}
}}

Build character profiles now:"""


def call_ollama(prompt: str) -> str:
    """Call Ollama API."""
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={'model': OLLAMA_MODEL, 'prompt': prompt, 'stream': False},
            timeout=OLLAMA_TIMEOUT
        )
        if response.status_code != 200:
            return ""
        return response.json().get('response', '')
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return ""


def parse_json_response(response: str) -> dict:
    """Extract JSON from response."""
    if not response:
        return {}
    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
        return {}
    except json.JSONDecodeError:
        return {}


def dedup_category(facts: list, category: str) -> list:
    """Deduplicate facts in a category using AI."""
    if not facts:
        return []

    # Format facts for prompt
    facts_text = "\n".join(f"- {f['fact']}" for f in facts)

    prompt = DEDUP_PROMPT.format(
        count=len(facts),
        category=category,
        facts=facts_text
    )

    print(f"  Deduplicating {len(facts)} {category} facts...", file=sys.stderr)
    start = time.time()
    response = call_ollama(prompt)
    elapsed = time.time() - start
    print(f"  Response in {elapsed:.1f}s", file=sys.stderr)

    parsed = parse_json_response(response)
    result = parsed.get('facts', [])
    print(f"  {len(facts)} -> {len(result)} facts", file=sys.stderr)

    return result


def build_character_profiles(facts: list) -> dict:
    """Build character profiles from character_identity facts."""
    if not facts:
        return {}

    facts_text = "\n".join(f"- {f['fact']}" for f in facts)

    prompt = CHARACTER_PROMPT.format(facts=facts_text)

    print(f"  Building profiles from {len(facts)} character facts...", file=sys.stderr)
    start = time.time()
    response = call_ollama(prompt)
    elapsed = time.time() - start
    print(f"  Response in {elapsed:.1f}s", file=sys.stderr)

    parsed = parse_json_response(response)
    characters = parsed.get('characters', {})
    print(f"  Found {len(characters)} characters", file=sys.stderr)

    return characters


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Deduplicate chunked facts')
    parser.add_argument('input', type=Path, help='Chunked results JSON')
    parser.add_argument('--output', type=Path, default=Path('experiment-deduped-results.json'))

    args = parser.parse_args()

    # Load chunked results
    with open(args.input) as f:
        data = json.load(f)

    facts = data['facts']
    print(f"Loaded {len(facts)} raw facts", file=sys.stderr)

    # Group by type
    by_type = {}
    for f in facts:
        t = f.get('type', 'unknown')
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(f)

    print(f"\nFacts by type:", file=sys.stderr)
    for t, fs in sorted(by_type.items()):
        print(f"  {t}: {len(fs)}", file=sys.stderr)

    # Deduplicate each category
    print(f"\n=== DEDUPLICATION ===", file=sys.stderr)

    results = {
        'method': 'chunked+dedup',
        'metadata': {
            'source': str(args.input),
            'raw_facts': len(facts),
            'processed_at': datetime.now().isoformat(),
            'model': OLLAMA_MODEL
        },
        'characters': {},
        'constants': {
            'world_rules': [],
            'setting': [],
            'timeline': []
        },
        'variables': []
    }

    # Process characters first
    print(f"\n[Characters]", file=sys.stderr)
    char_facts = by_type.get('character_identity', [])
    results['characters'] = build_character_profiles(char_facts)

    # Process world rules
    print(f"\n[World Rules]", file=sys.stderr)
    world_facts = by_type.get('world_rule', [])
    results['constants']['world_rules'] = dedup_category(world_facts, 'world rules')

    # Process setting
    print(f"\n[Setting]", file=sys.stderr)
    setting_facts = by_type.get('setting', [])
    results['constants']['setting'] = dedup_category(setting_facts, 'setting')

    # Process timeline
    print(f"\n[Timeline]", file=sys.stderr)
    timeline_facts = by_type.get('timeline', [])
    results['constants']['timeline'] = dedup_category(timeline_facts, 'timeline')

    # Collect variables
    for f in facts:
        if f.get('category') == 'variable':
            results['variables'].append({
                'fact': f['fact'],
                'type': f.get('type', 'unknown')
            })

    # Count final facts
    final_count = (
        len(results['characters']) +
        len(results['constants']['world_rules']) +
        len(results['constants']['setting']) +
        len(results['constants']['timeline']) +
        len(results['variables'])
    )
    results['metadata']['final_facts'] = final_count

    # Save
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)

    # Summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"DEDUPLICATION COMPLETE", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Raw facts: {len(facts)}", file=sys.stderr)
    print(f"Characters: {len(results['characters'])}", file=sys.stderr)
    print(f"World rules: {len(results['constants']['world_rules'])}", file=sys.stderr)
    print(f"Setting: {len(results['constants']['setting'])}", file=sys.stderr)
    print(f"Timeline: {len(results['constants']['timeline'])}", file=sys.stderr)
    print(f"Variables: {len(results['variables'])}", file=sys.stderr)
    print(f"Output: {args.output}", file=sys.stderr)


if __name__ == '__main__':
    main()
