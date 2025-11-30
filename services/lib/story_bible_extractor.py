#!/usr/bin/env python3
"""
Story Bible fact extraction using Ollama.

Extracts world constants, variables, and character information from passages.
Includes AI summarization/deduplication (Stage 2.5).
"""

import requests
import json
import hashlib
import logging
import time
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# Ollama configuration
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 120  # 2 minutes per passage

# AI prompt for fact extraction
EXTRACTION_PROMPT = """Reasoning: high

=== SECTION 1: ROLE & CONTEXT ===

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

Respond with ONLY valid JSON (no markdown, no code blocks):

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

=== SECTION 4: PASSAGE TEXT ===

{passage_text}

BEGIN EXTRACTION (JSON only):
"""


def extract_facts_from_passage(passage_text: str, passage_id: str) -> List[Dict]:
    """
    Extract facts from a single passage using Ollama.

    Args:
        passage_text: The passage content
        passage_id: Unique identifier for passage

    Returns:
        List of extracted facts

    Raises:
        Exception: If Ollama API fails or times out
    """
    # Format prompt
    prompt = EXTRACTION_PROMPT.format(passage_text=passage_text)

    # Call Ollama API
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Lower temperature for more consistent extraction
                    "num_predict": 16000  # Max tokens for response (thinking can use 8k+, need room for actual response)
                }
            },
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()
        result = response.json()

        # Parse response
        raw_response = result.get('response', '')

        # DEBUG: Log full Ollama result
        import logging
        logging.warning(f"[DEBUG] Passage {passage_id}: done_reason={result.get('done_reason')}, response len={len(raw_response)}, thinking len={len(result.get('thinking', ''))}")

        # Extract JSON from response (may have preamble text)
        facts_data = parse_json_from_response(raw_response)

        if not facts_data or 'facts' not in facts_data:
            raise Exception(f"Invalid AI response for passage {passage_id}: missing 'facts' field")

        return facts_data['facts']

    except requests.Timeout:
        raise Exception(f"Ollama API timeout for passage {passage_id}")
    except requests.RequestException as e:
        raise Exception(f"Ollama API error: {e}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse Ollama response as JSON: {e}")


def parse_json_from_response(text: str) -> Dict:
    """
    Extract JSON object from AI response that may contain extra text.

    Looks for { } pattern and attempts to parse.

    Args:
        text: Raw AI response text

    Returns:
        Parsed JSON object

    Raises:
        json.JSONDecodeError: If no valid JSON found
    """
    # Try parsing entire response first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON object boundaries
    start = text.find('{')
    end = text.rfind('}')

    if start == -1 or end == -1:
        raise json.JSONDecodeError("No JSON object found in response", text, 0)

    json_text = text[start:end+1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in response: {e}", text, 0)


def run_summarization(per_passage_extractions: Dict) -> Tuple[Optional[Dict], str, float]:
    """
    Run AI summarization/deduplication on per-passage extractions.

    This is Stage 2.5: Deduplicate and merge related facts while preserving
    complete evidence trail.

    Args:
        per_passage_extractions: Dict of passage_id -> extraction data

    Returns:
        Tuple of (summarized_facts, status, duration_seconds) where:
        - summarized_facts: Unified facts dict (or None if failed)
        - status: "success" or "failed"
        - duration_seconds: Time taken for summarization
    """
    try:
        # Import summarizer (local import to avoid circular dependency)
        import sys
        from pathlib import Path

        # Add formats/story-bible/modules to path
        story_bible_modules = Path(__file__).parent.parent.parent / 'formats' / 'story-bible' / 'modules'
        if str(story_bible_modules) not in sys.path:
            sys.path.insert(0, str(story_bible_modules))

        from ai_summarizer import summarize_facts

        start_time = time.time()
        summarized_facts, status = summarize_facts(per_passage_extractions)
        duration = time.time() - start_time

        return (summarized_facts, status, duration)

    except Exception as e:
        logging.error(f"Failed to run summarization: {e}")
        return (None, "failed", 0.0)


def categorize_all_facts(passage_extractions: Dict, summarized_facts: Optional[Dict] = None) -> Dict:
    """
    Cross-reference facts across all passages to categorize as constants/variables.

    Can accept either summarized facts (from Stage 2.5) or raw per-passage extractions.

    Args:
        passage_extractions: Dict of passage_id -> extraction data (fallback)
        summarized_facts: Optional pre-summarized facts from Stage 2.5

    Returns:
        Categorized facts structure:
        {
            "constants": {"world_rules": [], "setting": [], "timeline": []},
            "variables": {"events": [], "outcomes": []},
            "characters": {
                "CharacterName": {
                    "identity": [],
                    "zero_action_state": [],
                    "variables": []
                }
            }
        }
    """
    # If we have summarized facts, they're already categorized!
    if summarized_facts:
        logging.info("Using summarized facts (already categorized)")
        return summarized_facts

    # Otherwise, fall back to basic categorization from per-passage extractions
    logging.info("Using per-passage extractions (no summarization)")

    # Collect all facts
    all_facts = []
    for passage_id, extraction in passage_extractions.items():
        for fact in extraction.get('facts', []):
            all_facts.append({
                'passage_id': passage_id,
                **fact
            })

    # Group by fact type
    constants = {'world_rules': [], 'setting': [], 'timeline': []}
    variables = {'events': [], 'outcomes': []}
    characters = {}

    for fact in all_facts:
        fact_type = fact.get('type', 'unknown')
        category = fact.get('category', 'unknown')

        if category == 'constant':
            if fact_type in constants:
                constants[fact_type].append(fact)
        elif category == 'variable':
            if fact_type in ['event', 'outcome']:
                variables['events' if fact_type == 'event' else 'outcomes'].append(fact)
        elif category == 'character_identity' or fact_type == 'character_identity':
            # Extract character name from fact (simple heuristic)
            character_name = extract_character_name(fact['fact'])
            if character_name not in characters:
                characters[character_name] = {
                    'identity': [],
                    'zero_action_state': [],
                    'variables': []
                }

            if category == 'zero_action_state':
                characters[character_name]['zero_action_state'].append(fact)
            elif category == 'variable':
                characters[character_name]['variables'].append(fact)
            else:
                characters[character_name]['identity'].append(fact)

    return {
        'constants': constants,
        'variables': variables,
        'characters': characters
    }


def extract_character_name(fact_text: str) -> str:
    """
    Simple heuristic to extract character name from fact text.

    Examples:
        "Javlyn is a student" -> "Javlyn"
        "The character Sarah studies magic" -> "Sarah"

    Args:
        fact_text: The fact description

    Returns:
        Extracted character name or "Unknown"
    """
    # Look for capitalized words at start (simple approach)
    words = fact_text.split()
    for word in words:
        # Skip common article words
        if word in ['The', 'A', 'An', 'This', 'That']:
            continue
        # Look for capitalized words
        if len(word) > 0 and word[0].isupper() and word.isalpha():
            return word

    return "Unknown"


def get_passages_to_extract(cache: Dict, metadata_dir: Path, mode: str = 'incremental') -> List[tuple]:
    """
    Identify which passages need fact extraction based on cache and mode.

    Args:
        cache: Story Bible cache dict
        metadata_dir: Directory containing allpaths-metadata/*.txt files
        mode: 'incremental' (only new/changed) or 'full' (all passages)

    Returns:
        List of (passage_id, passage_file_path, passage_content) tuples to process
    """
    passages_to_process = []

    for passage_file in metadata_dir.glob("*.txt"):
        # Get passage identifier from filename
        passage_id = passage_file.stem  # filename without extension

        # Read passage content
        passage_content = passage_file.read_text()
        content_hash = hashlib.md5(passage_content.encode()).hexdigest()

        # Check cache for this passage
        cached_extraction = cache.get('passage_extractions', {}).get(passage_id)

        if mode == 'full':
            # Force re-extraction regardless of cache
            passages_to_process.append((passage_id, passage_file, passage_content))
        elif mode == 'incremental':
            # Only extract if new or changed
            if not cached_extraction or cached_extraction.get('content_hash') != content_hash:
                passages_to_process.append((passage_id, passage_file, passage_content))

    return passages_to_process
