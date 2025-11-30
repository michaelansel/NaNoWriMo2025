#!/usr/bin/env python3
"""
Experimental: Extract story bible facts from ALL passages concatenated together.

One-shot approach: shove all passage text together and let the model extract facts.

Usage:
    python scripts/experiment-oneshot-extraction.py src/
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
import requests

# Ollama config
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 300  # 5 minutes for the big extraction

# Passages to skip (metadata, not story content)
SKIP_PASSAGES = {'StoryTitle', 'StoryData', 'StoryStyles', 'Start'}

# One-shot extraction prompt
ONESHOT_PROMPT = """=== ROLE ===

You are extracting a comprehensive STORY BIBLE from an interactive fiction story.

=== TASK ===

Extract ALL facts about this story world. Focus on:

1. **World Rules**: Magic systems, technology, physical laws
2. **Setting**: Geography, landmarks, locations, environment
3. **Characters**: Names, roles, relationships, backgrounds
4. **Timeline**: Historical events, chronology, time-related facts

Categorize each fact as:
- **constant**: Always true regardless of player choices
- **variable**: Changes based on player decisions
- **zero_action_state**: Default outcome if player does nothing

=== OUTPUT FORMAT ===

Respond with JSON ONLY:

{{
  "facts": [
    {{
      "fact": "Description of the fact",
      "type": "setting|world_rule|character_identity|timeline",
      "confidence": "high|medium|low",
      "evidence": "Quote or passage reference",
      "category": "constant|variable|zero_action_state"
    }}
  ]
}}

=== STORY TEXT (ALL PASSAGES) ===

{all_passages}

=== INSTRUCTIONS ===

Extract ALL facts from the story above. Be thorough - this is the entire story content.
Deduplicate similar facts. Output JSON only.

BEGIN EXTRACTION:
"""


def parse_twee_file(filepath: Path) -> dict:
    """Parse a .twee file into individual passages."""
    passages = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    parts = re.split(r'^(:: .+?)$', content, flags=re.MULTILINE)

    current_name = None
    for part in parts:
        if part.startswith(':: '):
            current_name = part[3:].strip()
            if '[' in current_name:
                current_name = current_name[:current_name.index('[')].strip()
        elif current_name:
            passages[current_name] = part.strip()
            current_name = None

    return passages


def call_ollama(prompt: str) -> str:
    """Call Ollama API."""
    try:
        print(f"Calling Ollama (this may take a few minutes)...", file=sys.stderr)
        response = requests.post(
            OLLAMA_API_URL,
            json={
                'model': OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False
            },
            timeout=OLLAMA_TIMEOUT
        )

        if response.status_code != 200:
            print(f"Error: HTTP {response.status_code}", file=sys.stderr)
            return ""

        return response.json().get('response', '')
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return ""


def parse_json_response(response: str) -> dict:
    """Extract JSON from response."""
    if not response:
        return {"facts": []}

    try:
        start = response.find('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(response[start:end])
        return {"facts": []}
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}", file=sys.stderr)
        return {"facts": []}


def main():
    import argparse

    parser = argparse.ArgumentParser(description='One-shot fact extraction from all passages')
    parser.add_argument('src_dir', type=Path, help='Path to src/ directory')
    parser.add_argument('--output', type=Path, default=Path('experiment-oneshot-results.json'))

    args = parser.parse_args()

    # Check Ollama
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code != 200:
            print("Error: Ollama not available", file=sys.stderr)
            sys.exit(1)
    except:
        print("Error: Ollama not available", file=sys.stderr)
        sys.exit(1)

    print(f"Ollama available, using model: {OLLAMA_MODEL}", file=sys.stderr)

    # Parse all twee files
    twee_files = sorted(args.src_dir.glob('*.twee'))
    print(f"Found {len(twee_files)} .twee files", file=sys.stderr)

    all_passages = {}
    for twee_file in twee_files:
        passages = parse_twee_file(twee_file)
        for name, text in passages.items():
            if name not in SKIP_PASSAGES and text.strip():
                all_passages[name] = text

    print(f"Found {len(all_passages)} story passages", file=sys.stderr)

    # Concatenate all passages
    concatenated = ""
    for name, text in sorted(all_passages.items()):
        concatenated += f"\n=== PASSAGE: {name} ===\n{text}\n"

    print(f"Total concatenated length: {len(concatenated)} chars", file=sys.stderr)

    # Build prompt
    prompt = ONESHOT_PROMPT.format(all_passages=concatenated)
    print(f"Total prompt length: {len(prompt)} chars", file=sys.stderr)

    # Call Ollama
    import time
    start_time = time.time()
    response = call_ollama(prompt)
    elapsed = time.time() - start_time
    print(f"Response received in {elapsed:.1f}s", file=sys.stderr)
    print(f"Response length: {len(response)} chars", file=sys.stderr)

    # Parse response
    parsed = parse_json_response(response)
    facts = parsed.get('facts', [])

    print(f"\nExtracted {len(facts)} facts", file=sys.stderr)

    # Build results
    results = {
        'method': 'oneshot',
        'metadata': {
            'total_passages': len(all_passages),
            'concatenated_length': len(concatenated),
            'prompt_length': len(prompt),
            'response_length': len(response),
            'extraction_time_seconds': elapsed,
            'extracted_at': datetime.now().isoformat(),
            'model': OLLAMA_MODEL
        },
        'facts': facts,
        'raw_response': response
    }

    # Save
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    # Summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"ONE-SHOT EXTRACTION COMPLETE", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Passages processed: {len(all_passages)}", file=sys.stderr)
    print(f"Total facts: {len(facts)}", file=sys.stderr)
    print(f"Time: {elapsed:.1f}s", file=sys.stderr)
    print(f"Results: {args.output}", file=sys.stderr)

    # Fact breakdown
    fact_types = {}
    categories = {}
    for fact in facts:
        ft = fact.get('type', 'unknown')
        cat = fact.get('category', 'unknown')
        fact_types[ft] = fact_types.get(ft, 0) + 1
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\nFact types:", file=sys.stderr)
    for ft, count in sorted(fact_types.items(), key=lambda x: -x[1]):
        print(f"  {ft}: {count}", file=sys.stderr)

    print(f"\nCategories:", file=sys.stderr)
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}", file=sys.stderr)


if __name__ == '__main__':
    main()
