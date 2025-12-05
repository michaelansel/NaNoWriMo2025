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
import re
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# Ollama configuration
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 120  # 2 minutes per passage

# AI prompt for entity-first extraction (simplified for reliability)
EXTRACTION_PROMPT = """Extract ALL named entities from this story passage with facts and mentions.

IMPORTANT - Extract EVERY:
- Character name (e.g., "Jerrick", "Miss Rosie", "Javlyn")
- Titles with names as ONE entity (e.g., "Miss Rosie" not just "Rosie")
- Possessive mentions (e.g., "Miss Rosie's beef stew" -> extract "Miss Rosie")
- Location name (e.g., "cave", "village", "Academy")
- Item name (e.g., "lantern", "beef stew", "hammer")

PRONOUN RESOLUTION:
- Resolve pronouns (he/she/they/him/her/his/their) to entity names when unambiguous
- Use the entity's full name in the extraction, not the pronoun
- Keep the original text (with pronoun) in quote fields
- When ambiguous, do not resolve (skip that mention or extract as separate entity)
- Example: "Javlyn entered. She picked up the book." -> Extract as "Javlyn" entity, not "She"

For EACH entity, provide:
- name: The entity name (resolved from pronouns if applicable)
- type: "character", "location", or "item"
- facts: Array of fact OBJECTS with evidence (see format below)
- mentions: Array of mentions with quote and context

FACT FORMAT (CRITICAL):
Each fact MUST be an object with:
- fact: A brief statement about the entity (e.g., "is a student", "has an entrance")
- evidence: A direct quote from the passage that PROVES this fact

The evidence MUST:
- Be a quote from the passage
- Actually prove or support the fact (not just mention the entity)
- Show WHY the fact is true

Example:
{{"fact": "is a student at the Academy", "evidence": "Javlyn was a student at the Academy"}}

NOT acceptable:
{{"fact": "has an entrance", "evidence": "in the cave long though"}}  <- doesn't prove the fact!

Context types:
- "narrative" for narrator descriptions
- "dialogue" for character speech
- "possessive" for possessive references like "Rosie's stew"

Respond with ONLY valid JSON (no markdown):
{{
  "entities": [
    {{
      "name": "EntityName",
      "type": "character|location|item",
      "facts": [
        {{"fact": "brief statement", "evidence": "quote from passage that proves it"}},
        {{"fact": "another statement", "evidence": "another supporting quote"}}
      ],
      "mentions": [
        {{"quote": "text from passage mentioning entity", "context": "narrative|dialogue|possessive"}}
      ]
    }}
  ]
}}

EXAMPLE:
Passage: "Javlyn was a student at the Academy. She struggled with magic but practiced daily."
Response:
{{
  "entities": [
    {{
      "name": "Javlyn",
      "type": "character",
      "facts": [
        {{"fact": "is a student at the Academy", "evidence": "Javlyn was a student at the Academy"}},
        {{"fact": "struggles with magic", "evidence": "She struggled with magic"}},
        {{"fact": "practices daily", "evidence": "practiced daily"}}
      ],
      "mentions": [
        {{"quote": "Javlyn was a student at the Academy", "context": "narrative"}},
        {{"quote": "She struggled with magic but practiced daily", "context": "narrative"}}
      ]
    }},
    {{
      "name": "Academy",
      "type": "location",
      "facts": [
        {{"fact": "is a school", "evidence": "Javlyn was a student at the Academy"}}
      ],
      "mentions": [
        {{"quote": "Javlyn was a student at the Academy", "context": "narrative"}}
      ]
    }}
  ]
}}

PASSAGE:
{passage_text}

JSON:
"""


def chunk_passage(
    passage_name: str,
    passage_text: str,
    max_chars: int = 20000,
    overlap_chars: int = 200
) -> List[Tuple[str, str, int]]:
    """
    Split passage into chunks that fit within max_chars.

    Args:
        passage_name: Name of the passage
        passage_text: Full passage text
        max_chars: Maximum characters per chunk
        overlap_chars: Characters to overlap between chunks

    Returns:
        List of (chunk_name, chunk_text, chunk_number) tuples

    Example:
        chunk_passage("Start", "...", 20000)
        -> [("Start", "...", 1)]  # Single chunk if fits
        -> [("Start_chunk_1", "...", 1), ("Start_chunk_2", "...", 2)]  # Multiple if large
    """
    # Fast path: passage fits in one chunk
    if len(passage_text) <= max_chars:
        return [(passage_name, passage_text, 1)]

    chunks = []
    chunk_num = 1

    # Split at paragraph boundaries (double newline preferred)
    paragraphs = passage_text.split('\n\n')

    current_chunk = ""

    for para in paragraphs:
        # If adding this paragraph exceeds limit
        if current_chunk and len(current_chunk) + len(para) + 2 > max_chars:
            # Save current chunk
            chunk_name = f"{passage_name}_chunk_{chunk_num}"
            chunks.append((chunk_name, current_chunk, chunk_num))
            chunk_num += 1

            # Start new chunk with overlap from previous chunk
            overlap = current_chunk[-overlap_chars:] if len(current_chunk) > overlap_chars else current_chunk
            current_chunk = overlap + '\n\n' + para

        elif not current_chunk:
            # First paragraph in chunk
            current_chunk = para

        else:
            # Add paragraph to current chunk
            current_chunk += '\n\n' + para

    # Save final chunk
    if current_chunk:
        chunk_name = f"{passage_name}_chunk_{chunk_num}"
        chunks.append((chunk_name, current_chunk, chunk_num))

    return chunks


def extract_facts_from_passage(passage_text: str, passage_id: str) -> Dict:
    """
    Extract entities and facts from a single passage using Ollama.

    Now uses entity-first extraction approach: extracts entities (characters,
    locations, items) FIRST, then associates facts with those entities.

    Args:
        passage_text: The passage content
        passage_id: Unique identifier for passage

    Returns:
        Dict with extraction data:
        {
            "entities": {
                "characters": [...],
                "locations": [...],
                "items": [...],
                "organizations": [...],
                "concepts": [...]
            },
            "facts": []  # Empty list for backward compatibility
        }

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
                    "num_predict": 8000  # Enough for thinking + response
                },
                "think": "low"  # Key fix: minimize thinking for gpt-oss
            },
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()
        result = response.json()

        # Parse response
        raw_response = result.get('response', '')

        # Extract JSON from response (may have preamble text)
        # parse_json_from_response returns {"facts": []} or {"entities": {...}} on success
        extraction_data = parse_json_from_response(raw_response)

        # Ensure entity-first structure
        if 'entities' not in extraction_data:
            # Fallback: create empty entity structure
            extraction_data = {
                'entities': {
                    'characters': [],
                    'locations': [],
                    'items': [],
                    'organizations': [],
                    'concepts': []
                },
                'facts': extraction_data.get('facts', [])  # Preserve old format if present
            }
        else:
            # Add empty facts list for backward compatibility
            if 'facts' not in extraction_data:
                extraction_data['facts'] = []

        return extraction_data

    except requests.Timeout:
        raise Exception(f"Ollama API timeout for passage {passage_id}")
    except requests.RequestException as e:
        raise Exception(f"Ollama API error: {e}")


def parse_json_from_response(text: str) -> Dict:
    """
    Extract JSON object from AI response that may contain extra text.

    Handles multiple LLM output formats:
    1. Clean JSON
    2. JSON wrapped in ```json...``` markdown code blocks
    3. Flat entity list format ({"entities": [{"name": "X", "type": "character"}]})
    4. Nested entity format ({"entities": {"characters": [...]}})

    Args:
        text: Raw AI response text

    Returns:
        Parsed JSON object in normalized entity format, or {"facts": []} if parsing fails
    """
    import re

    if not text:
        return {"facts": []}

    # Strip markdown code blocks if present
    if '```' in text:
        # Extract content between ```json and ``` (or just ``` and ```)
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1)

    # Try parsing entire response first
    parsed = None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        pass

    if not parsed:
        # Find JSON object boundaries
        start = text.find('{')
        end = text.rfind('}')

        if start == -1 or end == -1:
            return {"facts": []}

        json_text = text[start:end+1]

        # Try direct parse
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            pass

        if not parsed:
            # Try fixing common JSON errors from LLMs
            # 1. Remove trailing commas before } or ]
            fixed = re.sub(r',(\s*[}\]])', r'\1', json_text)
            try:
                parsed = json.loads(fixed)
            except json.JSONDecodeError:
                pass

        if not parsed:
            # 2. Try fixing unescaped quotes in strings (common LLM error)
            try:
                fixed = json_text.replace('\n', ' ').replace('\r', '')
                parsed = json.loads(fixed)
            except json.JSONDecodeError:
                pass

    if not parsed:
        # Give up - return empty facts rather than crashing
        return {"facts": []}

    # Normalize entity format: convert flat list to nested dict
    # LLM sometimes returns: {"entities": [{"name": "X", "type": "character"}, ...]}
    # We need: {"entities": {"characters": [...], "locations": [...], ...}}
    if 'entities' in parsed and isinstance(parsed['entities'], list):
        flat_entities = parsed['entities']
        nested_entities = {
            'characters': [],
            'locations': [],
            'items': [],
            'organizations': [],
            'concepts': []
        }

        # Type mapping (normalize various type names)
        type_map = {
            'character': 'characters',
            'person': 'characters',
            'people': 'characters',
            'location': 'locations',
            'place': 'locations',
            'item': 'items',
            'object': 'items',
            'thing': 'items',
            'weapon': 'items',
            'tool': 'items',
            'food': 'items',
            'organization': 'organizations',
            'group': 'organizations',
            'concept': 'concepts',
            'ability': 'concepts',
            'weather': 'concepts',  # Map weather to concepts
        }

        for entity in flat_entities:
            entity_type = entity.get('type', '').lower()
            target_key = type_map.get(entity_type)

            if target_key:
                # Convert to expected format with name, mentions, facts
                normalized_entity = {
                    'name': entity.get('name', ''),
                    'title': entity.get('title'),
                    'mentions': entity.get('mentions', []),
                    'facts': entity.get('facts', [])
                }
                nested_entities[target_key].append(normalized_entity)

        parsed['entities'] = nested_entities

    return parsed


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


def calculate_metrics(cache: Dict) -> Dict:
    """
    Calculate quality metrics for extraction validation.

    Args:
        cache: Story Bible cache dict

    Returns:
        Dict with extraction statistics
    """
    try:
        from story_bible_metrics import calculate_extraction_stats
        return calculate_extraction_stats(cache)
    except Exception as e:
        logging.error(f"Failed to calculate metrics: {e}")
        return {}


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
    # If we have summarized facts, use them but preserve per-passage breakdown
    if summarized_facts:
        logging.info("Using summarized facts with per-passage preservation")
        # Start with summarized facts structure
        result = dict(summarized_facts)
        # Add per-passage breakdown for reference (preserves all original facts)
        result['per_passage'] = {}
        for passage_id, extraction in passage_extractions.items():
            result['per_passage'][passage_id] = {
                'passage_name': extraction.get('passage_name', 'Unknown'),
                'facts': extraction.get('facts', [])
            }
        return result

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

    # Map singular type names to plural keys (AI returns singular)
    type_to_key = {
        'world_rule': 'world_rules',
        'setting': 'setting',
        'timeline': 'timeline'
    }

    for fact in all_facts:
        fact_type = fact.get('type', 'unknown')
        category = fact.get('category', 'unknown')

        if category == 'constant':
            # Map type to key, handling both singular and plural forms
            key = type_to_key.get(fact_type, fact_type)
            if key in constants:
                constants[key].append(fact)
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


def extract_facts_from_passage_with_chunking(
    passage_name: str,
    passage_text: str,
    max_chars: int = 20000
) -> Tuple[Dict, int]:
    """
    Extract entities and facts from a passage, chunking if necessary.

    Args:
        passage_name: Name/ID of the passage
        passage_text: Full passage text
        max_chars: Maximum characters per chunk

    Returns:
        Tuple of (extraction_data, chunks_processed) where:
        - extraction_data: Combined entity extraction from all chunks
        - chunks_processed: Number of chunks created (1 for most passages)
    """
    # Chunk the passage
    chunks = chunk_passage(passage_name, passage_text, max_chars)

    # Initialize combined extraction
    combined_extraction = {
        'entities': {
            'characters': [],
            'locations': [],
            'items': [],
            'organizations': [],
            'concepts': []
        },
        'facts': []
    }

    for chunk_name, chunk_text, chunk_num in chunks:
        # Extract from this chunk
        chunk_extraction = extract_facts_from_passage(chunk_text, chunk_name)

        # Merge entities from this chunk
        for entity_type in ['characters', 'locations', 'items', 'organizations', 'concepts']:
            chunk_entities = chunk_extraction.get('entities', {}).get(entity_type, [])
            # Tag entities with chunk metadata for debugging
            for entity in chunk_entities:
                entity['_chunk_number'] = chunk_num
                entity['_chunk_total'] = len(chunks)
            combined_extraction['entities'][entity_type].extend(chunk_entities)

        # Merge facts (for backward compatibility)
        chunk_facts = chunk_extraction.get('facts', [])
        for fact in chunk_facts:
            fact['_chunk_number'] = chunk_num
            fact['_chunk_total'] = len(chunks)
        combined_extraction['facts'].extend(chunk_facts)

    return (combined_extraction, len(chunks))




def load_passages_from_core_library(metadata_dir: Path) -> Optional[List[Dict]]:
    """
    Load passages from core library artifacts (passages_deduplicated.json).

    This is the PRIMARY passage loading method. Falls back to AllPaths format
    if core library artifacts are not available.

    Args:
        metadata_dir: Directory containing passages_deduplicated.json

    Returns:
        List of passages in format:
        [
          {
            "passage_id": "Start",
            "content": "Passage text...",
            "content_hash": "abc123..."
          }
        ]
        Returns None if core library artifacts not available (triggers fallback).

    Raises:
        No exceptions - returns None on any error to allow fallback
    """
    try:
        # Look for core library artifact in metadata_dir
        artifacts_file = metadata_dir / "passages_deduplicated.json"

        if not artifacts_file.exists():
            logging.info("Core library artifacts not found, will fall back to AllPaths format")
            return None

        logging.info(f"Found core library artifacts at {artifacts_file}")

        # Load and parse JSON
        with open(artifacts_file, 'r') as f:
            data = json.load(f)

        # Extract passages
        passages = []
        for passage in data.get('passages', []):
            passages.append({
                'passage_id': passage['name'],
                'content': passage['content'],
                'content_hash': passage['content_hash'],
                'source': 'core_library'
            })

        logging.info(f"Loaded {len(passages)} passages from core library")
        return passages

    except json.JSONDecodeError as e:
        logging.warning(f"Invalid JSON in core library artifacts: {e}, falling back to AllPaths")
        return None
    except Exception as e:
        logging.warning(f"Error loading core library artifacts: {e}, falling back to AllPaths")
        return None


def get_passages_to_extract_v2(cache: Dict, metadata_dir: Path, mode: str = 'incremental') -> List[tuple]:
    """
    Identify which passages need fact extraction based on cache and mode.

    Uses core library artifacts (passages_deduplicated.json). Fails if not available.

    Args:
        cache: Story Bible cache dict
        metadata_dir: Directory containing core library artifacts
        mode: 'incremental' (only new/changed) or 'full' (all passages)

    Returns:
        List of (passage_id, passage_file, passage_content, content_hash) tuples to process.
        The content_hash is included so webhook can cache it without recomputing.

    Raises:
        FileNotFoundError: If core library artifacts not found
    """
    passages_to_process = []

    # Load from core library artifacts (required)
    passages = load_passages_from_core_library(metadata_dir)

    if not passages:
        raise FileNotFoundError(
            f"Core library artifacts not found in {metadata_dir}\n"
            f"Run 'npm run build:core' first to generate core artifacts."
        )

    logging.info("Using core library passages for extraction")

    for passage in passages:
        passage_id = passage['passage_id']
        passage_content = passage['content']
        content_hash = passage['content_hash']

        # Check cache for this passage
        cached_extraction = cache.get('passage_extractions', {}).get(passage_id)

        if mode == 'full':
            # Force re-extraction regardless of cache
            passages_to_process.append((passage_id, passage_id, passage_content, content_hash))
        elif mode == 'incremental':
            # Only extract if new or changed
            if not cached_extraction or cached_extraction.get('content_hash') != content_hash:
                passages_to_process.append((passage_id, passage_id, passage_content, content_hash))

    logging.info(f"Selected {len(passages_to_process)} passages for extraction from core library (mode: {mode})")
    return passages_to_process
