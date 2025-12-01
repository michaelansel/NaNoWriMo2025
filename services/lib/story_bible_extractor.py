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

# AI prompt for entity-first extraction
EXTRACTION_PROMPT = """=== SECTION 1: ROLE & CONTEXT ===

You are extracting ALL named ENTITIES from an interactive fiction story passage.

Your task: Extract entities FIRST (characters, locations, items), then associate facts with those entities.

CRITICAL UNDERSTANDING:
- STEP 1: Extract EVERY named entity (100% detection is the goal)
- STEP 2: Associate facts with those entities
- Dialogue mentions count: "when Marcie was with us" → Extract "Marcie"
- Possessive mentions count: "Miss Rosie's beef stew" → Extract "Miss Rosie" AND "beef stew"
- Indirect mentions count: "Josie fell out of a tree" → Extract "Josie"
- When in doubt, EXTRACT IT (better to over-extract than miss entities)

=== SECTION 2: ENTITY TYPES TO EXTRACT ===

STEP 1: ENTITY EXTRACTION (CRITICAL - Do this first)

Scan the passage for ALL named entities. Extract EVERY proper noun, named item, location, and character.

Types of entities to extract:

1. **CHARACTERS** (people, beings):
   - Proper names: Javlyn, Terence, Marcie, Miss Rosie, Josie
   - Titles + names: "Miss Rosie" (extract as single entity with title)
   - Mentioned in dialogue: "when Marcie was with us"
   - Possessive form: "Rosie's beef stew" → Extract "Miss Rosie"
   - Indirect mention: "Josie fell out of a tree" → Extract "Josie"
   - Pronouns with clear antecedents: Track back to named character

2. **LOCATIONS** (places):
   - Named places: Academy, village, city, cave, passageway
   - Geographic features: mountain, coast, forest
   - Buildings: inn, temple, entrance
   - Extract even if mentioned once

3. **ITEMS/OBJECTS** (things):
   - Named items: lantern, jerkin, belt, beef stew, artifact
   - Unique objects: "the lantern" (if it's THE specific one)
   - Food: "Miss Rosie's famous beef stew" → Extract "beef stew"
   - Tools, weapons, magical items

4. **ORGANIZATIONS/GROUPS**:
   - Named groups: "the village", "our group"
   - Collective pronouns: "we", "us" → Resolve to group if possible
   - Institutions: "the Academy" (when referring to organization)

5. **CONCEPTS/ABILITIES** (if named):
   - Named abilities: "workings", "luck working", "light working"
   - Magic terms specific to this story

NORMALIZATION RULES:
- Strip possessives: "Rosie's" → "Rosie"
- Preserve titles: "Miss Rosie" (NOT just "Rosie")
- Case-insensitive: "Marcie" = "marcie"
- Resolve pronouns: "she" → Track to named entity if clear

STEP 2: FACT ASSOCIATION (After entities extracted)

For each entity extracted in Step 1, extract:
- Identity facts (if available): "Javlyn is a student"
- Mentions: ALL passages where entity appears
- Context: How entity is mentioned (dialogue, narrative, possessive, etc.)
- Relationships: Entity X associated with entity Y
- Minimal info acceptable: Even if only "Marcie was mentioned"

=== SECTION 3: OUTPUT FORMAT ===

Respond with ONLY valid JSON (no markdown, no code blocks):

{{
  "entities": {{
    "characters": [
      {{
        "name": "Marcie",
        "title": null,
        "mentions": [
          {{
            "context": "dialogue|narrative|possessive|internal_thought",
            "quote": "when Marcie was with us"
          }}
        ],
        "facts": [
          "Was previously with the group",
          "Left or lost (implied by 'was with us')"
        ]
      }}
    ],
    "locations": [
      {{
        "name": "cave",
        "mentions": [
          {{
            "context": "narrative",
            "quote": "the cave entrance"
          }}
        ],
        "facts": ["Has an entrance"]
      }}
    ],
    "items": [
      {{
        "name": "beef stew",
        "mentions": [
          {{
            "context": "possessive",
            "quote": "Miss Rosie's famous beef stew"
          }}
        ],
        "facts": ["Associated with Miss Rosie", "Described as famous"]
      }}
    ],
    "organizations": [],
    "concepts": []
  }}
}}

CRITICAL RULES:
- Extract EVERY named entity, even if only mentioned once
- Dialogue mentions count (don't skip "when Marcie was with us")
- Possessive mentions count (don't skip "Miss Rosie's beef stew")
- Indirect mentions count (don't skip "Josie fell out of a tree")
- When in doubt, EXTRACT IT (better to over-extract than miss entities)

Your goal: 100% entity detection. Nothing named in the story should be missed.

=== SECTION 4: PASSAGE TEXT ===

{passage_text}

BEGIN EXTRACTION (JSON only):
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

    Looks for { } pattern and attempts to parse. Returns empty facts
    if parsing fails (resilient to malformed LLM output).

    Args:
        text: Raw AI response text

    Returns:
        Parsed JSON object, or {"facts": []} if parsing fails
    """
    if not text:
        return {"facts": []}

    # Try parsing entire response first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON object boundaries
    start = text.find('{')
    end = text.rfind('}')

    if start == -1 or end == -1:
        return {"facts": []}

    json_text = text[start:end+1]

    # Try direct parse
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        pass

    # Try fixing common JSON errors from LLMs
    # 1. Remove trailing commas before } or ]
    import re
    fixed = re.sub(r',(\s*[}\]])', r'\1', json_text)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # 2. Try fixing unescaped quotes in strings (common LLM error)
    # This is a heuristic - replace \" with escaped version
    try:
        # More aggressive cleanup
        fixed = json_text.replace('\n', ' ').replace('\r', '')
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    # Give up - return empty facts rather than crashing
    return {"facts": []}


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
