#!/usr/bin/env python3
"""
Experimental: Extract story bible facts from passages in chunks.

Chunks passages to stay within context window, then aggregates results.

Usage:
    python scripts/experiment-chunked-extraction.py src/
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime
import requests
import time

# Ollama config
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 180

# Max content size per chunk (chars) - leave room for prompt template
# Most models are 8k-32k tokens. ~4 chars/token, so 8k tokens = ~32k chars
# Being conservative: 20k chars content + ~2k prompt = safe
MAX_CHUNK_CHARS = 20000

# Passages to skip
SKIP_PASSAGES = {'StoryTitle', 'StoryData', 'StoryStyles', 'Start'}

# Extraction prompt - CONTENT GOES AT THE END so it doesn't get truncated
CHUNK_PROMPT = """You are extracting FACTS about an interactive fiction story world.

Extract these fact types:
1. **World Rules**: Magic systems, technology, physical laws
2. **Setting**: Geography, landmarks, locations
3. **Characters**: Names, roles, relationships, backgrounds
4. **Timeline**: Historical events, chronology

Categorize each fact as:
- **constant**: Always true regardless of player choices
- **variable**: Changes based on player decisions

Respond with JSON ONLY:

{{
  "facts": [
    {{
      "fact": "Description",
      "type": "setting|world_rule|character_identity|timeline",
      "confidence": "high|medium|low",
      "evidence": "Quote or passage name",
      "category": "constant|variable"
    }}
  ]
}}

=== STORY PASSAGES (chunk {chunk_num}/{total_chunks}) ===

{passages}

=== END PASSAGES ===

Extract ALL facts from the passages above. Output JSON only:"""


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
        response = requests.post(
            OLLAMA_API_URL,
            json={'model': OLLAMA_MODEL, 'prompt': prompt, 'stream': False},
            timeout=OLLAMA_TIMEOUT
        )
        if response.status_code != 200:
            print(f"  Error: HTTP {response.status_code}", file=sys.stderr)
            return ""
        return response.json().get('response', '')
    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
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
    except json.JSONDecodeError:
        return {"facts": []}


def chunk_passages(passages: dict, max_chars: int) -> list:
    """
    Split passages into chunks that fit within max_chars.

    Returns list of [(passage_name, text), ...] chunks.
    """
    chunks = []
    current_chunk = []
    current_size = 0

    for name, text in sorted(passages.items()):
        passage_block = f"\n=== {name} ===\n{text}\n"
        block_size = len(passage_block)

        if current_size + block_size > max_chars and current_chunk:
            # Save current chunk, start new one
            chunks.append(current_chunk)
            current_chunk = []
            current_size = 0

        current_chunk.append((name, passage_block))
        current_size += block_size

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Chunked fact extraction')
    parser.add_argument('src_dir', type=Path, help='Path to src/ directory')
    parser.add_argument('--output', type=Path, default=Path('experiment-chunked-results.json'))
    parser.add_argument('--chunk-size', type=int, default=MAX_CHUNK_CHARS,
                        help=f'Max chars per chunk (default: {MAX_CHUNK_CHARS})')

    args = parser.parse_args()

    # Check Ollama
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code != 200:
            raise Exception("not available")
    except:
        print("Error: Ollama not available", file=sys.stderr)
        sys.exit(1)

    print(f"Ollama available, model: {OLLAMA_MODEL}", file=sys.stderr)
    print(f"Chunk size: {args.chunk_size} chars", file=sys.stderr)

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

    # Chunk passages
    chunks = chunk_passages(all_passages, args.chunk_size)
    print(f"Split into {len(chunks)} chunks", file=sys.stderr)

    # Process each chunk
    all_facts = []
    chunk_results = []
    total_time = 0

    for i, chunk in enumerate(chunks, 1):
        passage_names = [name for name, _ in chunk]
        passages_text = "".join(block for _, block in chunk)

        print(f"\n[Chunk {i}/{len(chunks)}] {len(chunk)} passages, {len(passages_text)} chars", file=sys.stderr)
        print(f"  Passages: {', '.join(passage_names[:3])}{'...' if len(passage_names) > 3 else ''}", file=sys.stderr)

        prompt = CHUNK_PROMPT.format(
            chunk_num=i,
            total_chunks=len(chunks),
            passages=passages_text
        )
        print(f"  Prompt size: {len(prompt)} chars", file=sys.stderr)

        start_time = time.time()
        response = call_ollama(prompt)
        elapsed = time.time() - start_time
        total_time += elapsed
        print(f"  Response in {elapsed:.1f}s, {len(response)} chars", file=sys.stderr)

        parsed = parse_json_response(response)
        facts = parsed.get('facts', [])
        print(f"  Extracted {len(facts)} facts", file=sys.stderr)

        # Tag facts with chunk info
        for fact in facts:
            fact['_chunk'] = i
            fact['_passages'] = passage_names

        all_facts.extend(facts)
        chunk_results.append({
            'chunk': i,
            'passages': passage_names,
            'facts_count': len(facts),
            'time_seconds': elapsed
        })

    # Build results
    results = {
        'method': 'chunked',
        'metadata': {
            'total_passages': len(all_passages),
            'num_chunks': len(chunks),
            'chunk_size_limit': args.chunk_size,
            'total_facts': len(all_facts),
            'total_time_seconds': total_time,
            'extracted_at': datetime.now().isoformat(),
            'model': OLLAMA_MODEL
        },
        'chunk_results': chunk_results,
        'facts': all_facts
    }

    # Save
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    # Summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"CHUNKED EXTRACTION COMPLETE", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)
    print(f"Passages: {len(all_passages)}", file=sys.stderr)
    print(f"Chunks: {len(chunks)}", file=sys.stderr)
    print(f"Total facts: {len(all_facts)}", file=sys.stderr)
    print(f"Total time: {total_time:.1f}s", file=sys.stderr)
    print(f"Results: {args.output}", file=sys.stderr)

    # Breakdown
    fact_types = {}
    for fact in all_facts:
        ft = fact.get('type', 'unknown')
        fact_types[ft] = fact_types.get(ft, 0) + 1

    print(f"\nFact types:", file=sys.stderr)
    for ft, count in sorted(fact_types.items(), key=lambda x: -x[1]):
        print(f"  {ft}: {count}", file=sys.stderr)


if __name__ == '__main__':
    main()
