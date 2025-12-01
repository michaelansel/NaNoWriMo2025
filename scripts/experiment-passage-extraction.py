#!/usr/bin/env python3
"""
Experimental: Extract story bible facts from individual Twee passages.

This bypasses the AllPaths full-path approach and extracts directly from
individual passages in the source .twee files.

Usage:
    python scripts/experiment-passage-extraction.py src/
    python scripts/experiment-passage-extraction.py src/ --output experiment-results.json
"""

import json
import sys
import re
import hashlib
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import requests

# Ollama config (same as story-bible)
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 60

# Passages to skip (metadata, not story content)
SKIP_PASSAGES = {'StoryTitle', 'StoryData', 'StoryStyles', 'Start'}

# Extraction prompt (same as ai_extractor.py)
EXTRACTION_PROMPT = """=== SECTION 1: ROLE & CONTEXT ===

You are extracting FACTS about an interactive fiction story world.

Your task: Extract CONSTANTS (always true) and VARIABLES (depend on player choices).

CRITICAL UNDERSTANDING:
- Focus on WORLD FACTS, not plot events
- Constants: True in all story paths regardless of player action
- Variables: Change based on player choices
- Zero Action State: What happens if player does nothing

=== SECTION 2: WHAT TO EXTRACT ===

Extract these fact types:

1. **World Rules**: Magic systems, technology level, physical laws
2. **Setting**: Geography, landmarks, historical events before story
3. **Character Identities**: Names, backgrounds, core traits (not fates)
4. **Timeline**: Events before story starts, chronological constants

For each character, identify:
- Identity (constants): Who they are, background
- Zero Action State: Default trajectory if player doesn't intervene
- Variables: Outcomes that depend on player choices

=== SECTION 3: OUTPUT FORMAT ===

Respond with JSON ONLY (no other text):

{{
  "facts": [
    {{
      "fact": "The city is on the coast",
      "type": "setting|world_rule|character_identity|timeline",
      "confidence": "high|medium|low",
      "evidence": [{{"passage": "PassageName", "quote": "Quote from passage demonstrating this fact"}}],
      "category": "constant|variable|zero_action_state"
    }}
  ]
}}

If no facts can be extracted, return:
{{"facts": []}}

=== SECTION 4: PASSAGE TEXT ===

Passage: {passage_name}

{passage_text}

=== SECTION 5: EXECUTION INSTRUCTIONS ===

Extract facts from the passage above. Output JSON only.

BEGIN EXTRACTION:
"""


def parse_twee_file(filepath: Path) -> Dict[str, str]:
    """
    Parse a .twee file into individual passages.

    Returns:
        Dict mapping passage name -> passage text
    """
    passages = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split by passage markers (:: PassageName)
    # Pattern: line starting with :: followed by passage name
    passage_pattern = r'^:: (.+?)$'

    # Find all passage starts
    parts = re.split(r'^(:: .+?)$', content, flags=re.MULTILINE)

    current_name = None
    for part in parts:
        if part.startswith(':: '):
            # This is a passage header
            current_name = part[3:].strip()
            # Remove any tags like [tag1 tag2]
            if '[' in current_name:
                current_name = current_name[:current_name.index('[')].strip()
        elif current_name:
            # This is passage content
            passages[current_name] = part.strip()
            current_name = None

    return passages


def call_ollama(prompt: str) -> str:
    """Call Ollama API and return response."""
    try:
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
            print(f"  Error: HTTP {response.status_code}", file=sys.stderr)
            return ""

        result = response.json()
        return result.get('response', '')
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return ""


def parse_json_response(response: str) -> Dict:
    """Extract JSON from Ollama response."""
    if not response:
        return {"facts": []}

    try:
        start = response.find('{')
        end = response.rfind('}') + 1

        if start >= 0 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
        return {"facts": []}
    except json.JSONDecodeError:
        return {"facts": []}


def calculate_hash(text: str) -> str:
    """Calculate content hash for caching."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Extract facts from individual Twee passages')
    parser.add_argument('src_dir', type=Path, help='Path to src/ directory with .twee files')
    parser.add_argument('--output', type=Path, default=Path('experiment-passage-results.json'),
                        help='Output JSON file')
    parser.add_argument('--cache', type=Path, default=Path('experiment-passage-cache.json'),
                        help='Cache file for incremental extraction')
    parser.add_argument('--limit', type=int, help='Limit number of passages to process')

    args = parser.parse_args()

    # Check Ollama availability
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code != 200:
            print("Error: Ollama not available", file=sys.stderr)
            sys.exit(1)
    except:
        print("Error: Ollama not available", file=sys.stderr)
        sys.exit(1)

    print(f"Ollama available, using model: {OLLAMA_MODEL}", file=sys.stderr)

    # Load cache
    cache = {}
    if args.cache.exists():
        with open(args.cache, 'r', encoding='utf-8') as f:
            cache = json.load(f)
        print(f"Loaded cache with {len(cache)} entries", file=sys.stderr)

    # Find and parse all .twee files
    twee_files = sorted(args.src_dir.glob('*.twee'))
    print(f"Found {len(twee_files)} .twee files", file=sys.stderr)

    all_passages = {}
    for twee_file in twee_files:
        passages = parse_twee_file(twee_file)
        for name, text in passages.items():
            if name not in SKIP_PASSAGES and text.strip():
                all_passages[name] = {
                    'text': text,
                    'source_file': twee_file.name
                }

    print(f"Found {len(all_passages)} story passages (excluding metadata)", file=sys.stderr)

    # Apply limit if specified
    passage_names = list(all_passages.keys())
    if args.limit:
        passage_names = passage_names[:args.limit]
        print(f"Limited to {args.limit} passages", file=sys.stderr)

    # Extract facts from each passage
    results = {
        'extractions': [],
        'metadata': {
            'total_passages': len(passage_names),
            'started_at': datetime.now().isoformat(),
            'model': OLLAMA_MODEL
        }
    }

    total_facts = 0
    cached_count = 0

    for i, passage_name in enumerate(passage_names, 1):
        passage_data = all_passages[passage_name]
        passage_text = passage_data['text']
        content_hash = calculate_hash(passage_text)

        print(f"\n[{i}/{len(passage_names)}] {passage_name}", file=sys.stderr)
        print(f"  Source: {passage_data['source_file']}", file=sys.stderr)
        print(f"  Length: {len(passage_text)} chars", file=sys.stderr)

        # Check cache
        if content_hash in cache:
            print(f"  Using cached extraction", file=sys.stderr)
            facts = cache[content_hash]['facts']
            cached_count += 1
        else:
            # Call Ollama
            print(f"  Calling Ollama...", file=sys.stderr)
            start_time = time.time()

            prompt = EXTRACTION_PROMPT.format(
                passage_name=passage_name,
                passage_text=passage_text
            )

            response = call_ollama(prompt)
            elapsed = time.time() - start_time
            print(f"  Response in {elapsed:.1f}s", file=sys.stderr)

            parsed = parse_json_response(response)
            facts = parsed.get('facts', [])

            # Update cache
            cache[content_hash] = {
                'passage_name': passage_name,
                'facts': facts,
                'extracted_at': datetime.now().isoformat()
            }

        print(f"  Extracted {len(facts)} facts", file=sys.stderr)
        total_facts += len(facts)

        results['extractions'].append({
            'passage_name': passage_name,
            'source_file': passage_data['source_file'],
            'content_hash': content_hash,
            'facts': facts,
            'cached': content_hash in cache
        })

        # Save cache periodically
        if i % 5 == 0:
            with open(args.cache, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2)

    # Final cache save
    with open(args.cache, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2)

    # Update metadata
    results['metadata']['completed_at'] = datetime.now().isoformat()
    results['metadata']['total_facts'] = total_facts
    results['metadata']['cached_extractions'] = cached_count

    # Save results
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    # Print summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"EXTRACTION COMPLETE", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Passages processed: {len(passage_names)}", file=sys.stderr)
    print(f"From cache: {cached_count}", file=sys.stderr)
    print(f"Total facts extracted: {total_facts}", file=sys.stderr)
    print(f"Average facts/passage: {total_facts/len(passage_names):.1f}", file=sys.stderr)
    print(f"Results saved to: {args.output}", file=sys.stderr)
    print(f"Cache saved to: {args.cache}", file=sys.stderr)

    # Print fact type breakdown
    fact_types = {}
    for ext in results['extractions']:
        for fact in ext['facts']:
            ft = fact.get('type', 'unknown')
            fact_types[ft] = fact_types.get(ft, 0) + 1

    print(f"\nFact types:", file=sys.stderr)
    for ft, count in sorted(fact_types.items(), key=lambda x: -x[1]):
        print(f"  {ft}: {count}", file=sys.stderr)


if __name__ == '__main__':
    main()
