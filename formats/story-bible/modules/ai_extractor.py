#!/usr/bin/env python3
"""
Stage 2: AI Extractor Module

Uses Ollama AI to extract facts from story passages.

Input:
    - loaded_paths.json (from Stage 1)

Output:
    - extracted_facts.json (intermediate artifact)

Responsibilities:
    - Call Ollama AI to extract constants/variables from passages
    - Parse JSON responses
    - Cache extraction results for performance
    - Handle errors and timeouts gracefully
"""

import json
import sys
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# Import Ollama client
import os
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))
from ollama_client import call_ollama, check_ollama_available


# AI Extraction Prompt Template
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
      "evidence": "Quote from passage demonstrating this fact",
      "category": "constant|variable|zero_action_state"
    }}
  ]
}}

If no facts can be extracted, return:
{{"facts": []}}

=== SECTION 4: PASSAGE TEXT ===

{passage_text}

=== SECTION 5: EXECUTION INSTRUCTIONS ===

Extract facts from the passage above. Output JSON only.

BEGIN EXTRACTION:
"""


def calculate_content_hash(text: str) -> str:
    """Calculate MD5 hash of passage content for caching."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def load_extraction_cache(cache_file: Path) -> Dict:
    """
    Load extraction cache from file.

    Cache structure:
    {
        "content_hash": {
            "extracted_facts": [...],
            "extracted_at": "timestamp"
        }
    }
    """
    if not cache_file.exists():
        return {}

    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load extraction cache: {e}", file=sys.stderr)
        return {}


def save_extraction_cache(cache_file: Path, cache: Dict):
    """Save extraction cache to file."""
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save extraction cache: {e}", file=sys.stderr)


def parse_ollama_response(response: str) -> Dict:
    """
    Parse Ollama's JSON response.

    Args:
        response: Raw response from Ollama

    Returns:
        Parsed JSON dict, or empty facts list if parsing fails
    """
    if not response:
        return {"facts": []}

    try:
        # Try to find JSON in the response
        start = response.find('{')
        end = response.rfind('}') + 1

        if start >= 0 and end > start:
            json_str = response[start:end]
            return json.loads(json_str)
        else:
            return {"facts": []}

    except json.JSONDecodeError as e:
        print(f"  Warning: Could not parse AI response as JSON: {e}", file=sys.stderr)
        return {"facts": []}


def extract_facts_from_passage(passage_name: str, passage_text: str, cache: Dict) -> Dict:
    """
    Extract facts from a single passage using AI.

    Args:
        passage_name: Name of the passage
        passage_text: Text content of the passage
        cache: Extraction cache (for checking if already processed)

    Returns:
        Dict with extracted facts:
        {
            "passage_name": "...",
            "facts": [...],
            "extracted_at": "timestamp",
            "cached": true/false
        }
    """
    # Calculate content hash for caching
    content_hash = calculate_content_hash(passage_text)

    # Check if already in cache
    if content_hash in cache:
        cached_result = cache[content_hash]
        print(f"  Using cached extraction for '{passage_name}'", file=sys.stderr)
        return {
            "passage_name": passage_name,
            "facts": cached_result['extracted_facts'],
            "extracted_at": cached_result['extracted_at'],
            "cached": True
        }

    # Call AI to extract facts
    prompt = EXTRACTION_PROMPT.format(passage_text=passage_text)

    try:
        response = call_ollama(prompt)
        result = parse_ollama_response(response)

        facts = result.get('facts', [])

        # Update cache
        cache[content_hash] = {
            'extracted_facts': facts,
            'extracted_at': datetime.now().isoformat()
        }

        return {
            "passage_name": passage_name,
            "facts": facts,
            "extracted_at": datetime.now().isoformat(),
            "cached": False
        }

    except Exception as e:
        print(f"  Error extracting facts from '{passage_name}': {e}", file=sys.stderr)
        return {
            "passage_name": passage_name,
            "facts": [],
            "extracted_at": datetime.now().isoformat(),
            "error": str(e),
            "cached": False
        }


def extract_facts_with_ai(loaded_data: Dict, cache_file: Optional[Path] = None) -> Dict:
    """
    Extract facts from all passages using AI.

    Args:
        loaded_data: Output from Stage 1 (loader)
        cache_file: Path to extraction cache file (optional)

    Returns:
        Dict with structure:
        {
            "extractions": [
                {
                    "passage_name": "...",
                    "facts": [...],
                    "extracted_at": "timestamp"
                }
            ],
            "cache": {
                "content_hash": {...}
            }
        }

    Raises:
        RuntimeError: If Ollama service is not available
    """
    # Check if Ollama is available
    if not check_ollama_available():
        raise RuntimeError(
            "Ollama service is not available. "
            "Please start Ollama service before running Story Bible generation."
        )

    # Load extraction cache
    if cache_file is None:
        cache_file = Path.cwd() / 'story-bible-extraction-cache.json'

    cache = load_extraction_cache(cache_file)
    print(f"Loaded extraction cache with {len(cache)} entries", file=sys.stderr)

    # Get passages from loaded data
    passages = loaded_data.get('passages', {})

    print(f"Extracting facts from {len(passages)} passages...", file=sys.stderr)

    # Extract facts from each passage
    extractions = []
    failed_count = 0

    # Process passages (sequential for now, can parallelize later)
    for i, (passage_name, passage_data) in enumerate(passages.items(), 1):
        print(f"\n[{i}/{len(passages)}] Processing '{passage_name}'...", file=sys.stderr)

        passage_text = passage_data.get('text', '')

        # Skip empty passages
        if not passage_text.strip():
            print(f"  Skipping empty passage", file=sys.stderr)
            continue

        # Extract facts
        extraction = extract_facts_from_passage(passage_name, passage_text, cache)

        if 'error' in extraction:
            failed_count += 1

        extractions.append(extraction)

        # Check failure rate
        if failed_count > len(passages) * 0.5:
            raise RuntimeError(
                f"Too many extraction failures ({failed_count}/{len(passages)}). "
                f"Aborting Story Bible generation."
            )

    # Save updated cache
    save_extraction_cache(cache_file, cache)
    print(f"\nSaved extraction cache to {cache_file}", file=sys.stderr)

    # Return result
    result = {
        "extractions": extractions,
        "cache": cache
    }

    print(f"\nExtraction complete: {len(extractions)} passages processed", file=sys.stderr)
    print(f"  Failures: {failed_count}", file=sys.stderr)
    print(f"  Cached: {sum(1 for e in extractions if e.get('cached', False))}", file=sys.stderr)

    return result


def main():
    """Test AI extraction functionality."""
    import argparse

    parser = argparse.ArgumentParser(description='Test AI extractor module')
    parser.add_argument('loaded_data', type=Path, help='Path to loaded_paths.json from Stage 1')
    parser.add_argument('--cache', type=Path, help='Path to extraction cache file')
    parser.add_argument('--output', type=Path, help='Output JSON file (optional)')

    args = parser.parse_args()

    # Load input data
    with open(args.loaded_data, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)

    # Extract facts
    result = extract_facts_with_ai(loaded_data, cache_file=args.cache)

    # Print summary
    print(f"\nExtraction summary:")
    print(f"  Total extractions: {len(result['extractions'])}")
    total_facts = sum(len(e.get('facts', [])) for e in result['extractions'])
    print(f"  Total facts extracted: {total_facts}")

    # Save to file if requested
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved to {args.output}")


if __name__ == '__main__':
    main()
