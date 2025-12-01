#!/usr/bin/env python3
"""
Stage 2.5: AI Summarizer Module

Deduplicates and merges related facts from per-passage extractions using AI.

Input:
    - per_passage_extractions (Dict of passage_id -> extraction data)

Output:
    - summarized_facts (Dict with constants, characters, variables, conflicts)
    - summarization_status ("success" | "failed")

Responsibilities:
    - Call Ollama to deduplicate and merge related facts
    - Preserve complete evidence trail for all merged facts
    - Conservative deduplication (when uncertain, keep separate)
    - Surface contradictions as CONFLICT (don't auto-resolve)
    - Handle timeout/error gracefully (return status="failed")
"""

import requests
import json
import logging
from typing import Dict, List, Tuple, Optional

# Ollama configuration
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 300  # 5 minutes for summarization

# Category labels for prompts
CATEGORY_LABELS = {
    'world_rule': 'world rule',
    'setting': 'setting',
    'timeline': 'timeline',
    'character_identity': 'character identity',
    'variables': 'variable outcome'
}

# AI prompt for category-specific summarization
CATEGORY_SUMMARIZATION_PROMPT = """=== SECTION 1: ROLE & CONTEXT ===

You are deduplicating {category_label} facts extracted from multiple passages in an interactive fiction story.

Your task: Create a unified list by intelligently merging related facts while preserving complete evidence.

CRITICAL UNDERSTANDING:
- Input: {category_label} facts extracted from individual passages (may contain duplicates)
- Output: Unified facts with complete evidence citations
- Goal: Reduce redundancy while preserving all information
- Principle: Conservative deduplication (when uncertain, keep separate)

=== SECTION 2: MERGE RULES ===

**MERGE when facts are identical:**
1. Same meaning, different wording
   - Example: "Javlyn is a student" + "Javlyn attends as a student" → MERGE
   - Action: Combine into single fact, cite ALL source passages

2. Same fact with additive details
   - Example: "City is coastal" + "City is on eastern coast" → MERGE
   - Action: Combine details into richer fact, cite ALL sources

3. Repeated world rules
   - Example: Multiple passages mention "Magic requires training" → MERGE
   - Action: Single entry with complete evidence list

**KEEP SEPARATE when:**
1. Facts contradict each other
   - Example: "War ended 10 years ago" vs "War ended 2 years ago" → SEPARATE + FLAG CONFLICT
   - Action: Keep both, flag as "CONFLICT", mark severity

2. Path-specific variations (variables)
   - Example: "Javlyn masters magic" vs "Javlyn gives up on magic" → SEPARATE
   - Action: Keep as separate variable outcomes

3. Different aspects of same subject
   - Example: "Javlyn is a student" vs "Javlyn struggles with magic" → SEPARATE
   - Action: Different facts about same character (identity vs state)

4. Uncertain whether same fact
   - Example: "City has grand library" vs "Academy library contains texts" → SEPARATE
   - Action: Conservative deduplication (unclear if same building)

5. Different scope or context
   - Example: "Magic system exists" (world rule) vs "Javlyn studies magic" (character action) → SEPARATE
   - Action: Different fact types

**CONSERVATIVE PRINCIPLE:**
- When uncertain → Keep separate
- Better to have slight redundancy than lose meaningful distinctions
- Authors can verify merged facts are correct

=== SECTION 3: OUTPUT FORMAT ===

Respond with ONLY valid JSON (no markdown, no code blocks):

{{
  "facts": [
    {{
      "fact": "Combined or single fact statement",
      "evidence": [
        {{
          "passage": "passage name",
          "quote": "exact quote from passage"
        }}
      ],
      "confidence": "high|medium|low",
      "merged_from": ["original fact 1", "original fact 2"]
    }}
  ],
  "conflicts": [
    {{
      "description": "Brief description of conflict",
      "facts": [
        {{"fact": "...", "evidence": [...]}},
        {{"fact": "...", "evidence": [...]}}
      ],
      "severity": "critical|major|minor"
    }}
  ]
}}

CRITICAL: Evidence format MUST be array of objects with passage, quote.
CRITICAL: ALL evidence must be preserved. Never drop source passages.
CRITICAL: If facts conflict, keep both and add to conflicts array.
CRITICAL: Include merged_from field ONLY when facts were actually merged.

=== SECTION 4: INPUT FACTS ===

{facts_json}

BEGIN SUMMARIZATION (JSON only):
"""


def build_summarization_input(per_passage_extractions: Dict) -> List[Dict]:
    """
    Build input data for AI summarization from per-passage extractions.

    Args:
        per_passage_extractions: Dict of passage_id -> extraction data

    Returns:
        List of all facts with passage context
    """
    all_facts = []

    for passage_id, extraction in per_passage_extractions.items():
        passage_name = extraction.get('passage_name', 'Unknown')
        facts = extraction.get('facts', [])

        for fact in facts:
            all_facts.append({
                'fact': fact.get('fact', ''),
                'type': fact.get('type', 'unknown'),
                'confidence': fact.get('confidence', 'medium'),
                'category': fact.get('category', 'constant'),
                'evidence': fact.get('evidence', []),
                'passage_id': passage_id,
                'passage_name': passage_name
            })

    return all_facts


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


def validate_summarized_structure(summarized: Dict) -> bool:
    """
    Validate summarized facts have required structure.

    Args:
        summarized: Summarized facts dict

    Returns:
        True if valid, False otherwise
    """
    required_keys = ['constants', 'characters', 'variables']
    return all(key in summarized for key in required_keys)


def extract_character_from_fact(fact_text: str) -> str:
    """
    Extract primary character name from a character identity fact.

    Uses simple heuristic: looks for first capitalized word.

    Args:
        fact_text: The fact statement

    Returns:
        Character name or "Unknown" if not found
    """
    names = extract_all_characters_from_fact(fact_text)
    return names[0] if names else "Unknown"


def extract_all_characters_from_fact(fact_text: str) -> List[str]:
    """
    Extract ALL character names from a fact.

    Looks for capitalized words that appear to be proper nouns (names).
    Handles comma-separated lists like "Danita, Kian, and Terence".

    Args:
        fact_text: The fact statement

    Returns:
        List of character names found (may be empty)
    """
    words = fact_text.split()
    if not words:
        return []

    # Words to skip (articles, conjunctions, common words)
    skip_words = {
        'The', 'A', 'An', 'If', 'When', 'While', 'After', 'Before',
        'This', 'That', 'These', 'Those', 'There', 'Here',
        'During', 'Throughout', 'Whether', 'Although',
        'Three', 'Two', 'One', 'Four', 'Five',  # Numbers
        'Player', 'Unknown',  # Meta terms
    }

    names = []
    for word in words:
        # Strip trailing punctuation
        clean_word = word.rstrip(',.;:!?\'\"')

        # Check if it's a potential name
        if (clean_word and
            clean_word[0].isupper() and
            clean_word.isalpha() and
            clean_word not in skip_words and
            len(clean_word) > 1):
            names.append(clean_word)

    return names


def aggregate_entities_from_extractions(per_passage_extractions: Dict) -> Dict:
    """
    Aggregate entities from entity-first extractions.

    This function handles the new entity-first extraction format where each
    passage extraction contains an 'entities' dict with characters, locations,
    items, organizations, and concepts.

    Args:
        per_passage_extractions: Dict of passage_id -> extraction data

    Returns:
        Dict with aggregated entities:
        {
            'characters': {name: {identity: [...], mentions: [...], passages: [...]}},
            'locations': {name: {facts: [...], mentions: [...], passages: [...]}},
            'items': {name: {facts: [...], mentions: [...], passages: [...]}}
        }
    """
    # Initialize aggregated structure
    characters = {}  # name -> {identity: [], mentions: [], passages: []}
    locations = {}   # name -> {facts: [], mentions: [], passages: []}
    items = {}       # name -> {facts: [], mentions: [], passages: []}

    for passage_id, extraction in per_passage_extractions.items():
        entities = extraction.get('entities', {})

        # Process characters
        for char in entities.get('characters', []):
            name = char.get('name', '').strip()
            if not name:
                continue

            # Normalize name (strip possessives, preserve titles)
            normalized = normalize_name(name)

            if normalized not in characters:
                characters[normalized] = {
                    'identity': [],
                    'mentions': [],
                    'passages': []
                }

            # Add passage to list
            if passage_id not in characters[normalized]['passages']:
                characters[normalized]['passages'].append(passage_id)

            # Add facts as identity
            for fact in char.get('facts', []):
                fact_text = fact.strip() if isinstance(fact, str) else str(fact)
                if fact_text and fact_text not in characters[normalized]['identity']:
                    characters[normalized]['identity'].append(fact_text)

            # Add mentions
            for mention in char.get('mentions', []):
                quote = mention.get('quote', '')
                if quote and quote not in [m.get('quote') for m in characters[normalized]['mentions']]:
                    characters[normalized]['mentions'].append({
                        'quote': quote,
                        'context': mention.get('context', 'narrative'),
                        'passage': passage_id
                    })

        # Process locations
        for loc in entities.get('locations', []):
            name = loc.get('name', '').strip()
            if not name:
                continue

            normalized = normalize_name(name)

            if normalized not in locations:
                locations[normalized] = {
                    'facts': [],
                    'mentions': [],
                    'passages': []
                }

            if passage_id not in locations[normalized]['passages']:
                locations[normalized]['passages'].append(passage_id)

            for fact in loc.get('facts', []):
                fact_text = fact.strip() if isinstance(fact, str) else str(fact)
                if fact_text and fact_text not in locations[normalized]['facts']:
                    locations[normalized]['facts'].append(fact_text)

            for mention in loc.get('mentions', []):
                quote = mention.get('quote', '')
                if quote and quote not in [m.get('quote') for m in locations[normalized]['mentions']]:
                    locations[normalized]['mentions'].append({
                        'quote': quote,
                        'context': mention.get('context', 'narrative'),
                        'passage': passage_id
                    })

        # Process items
        for item in entities.get('items', []):
            name = item.get('name', '').strip()
            if not name:
                continue

            normalized = normalize_name(name)

            if normalized not in items:
                items[normalized] = {
                    'facts': [],
                    'mentions': [],
                    'passages': []
                }

            if passage_id not in items[normalized]['passages']:
                items[normalized]['passages'].append(passage_id)

            for fact in item.get('facts', []):
                fact_text = fact.strip() if isinstance(fact, str) else str(fact)
                if fact_text and fact_text not in items[normalized]['facts']:
                    items[normalized]['facts'].append(fact_text)

            for mention in item.get('mentions', []):
                quote = mention.get('quote', '')
                if quote and quote not in [m.get('quote') for m in items[normalized]['mentions']]:
                    items[normalized]['mentions'].append({
                        'quote': quote,
                        'context': mention.get('context', 'narrative'),
                        'passage': passage_id
                    })

    return {
        'characters': characters,
        'locations': locations,
        'items': items
    }


def normalize_name(name: str) -> str:
    """
    Normalize an entity name for deduplication.

    - Strip possessives ('s, ')
    - Preserve titles (Miss, Mr, etc.)
    - Title case
    """
    # Strip possessives
    if name.endswith("'s"):
        name = name[:-2]
    elif name.endswith("'"):
        name = name[:-1]

    # Title case
    name = name.strip().title()

    return name


def aggregate_facts_deterministically(per_passage_extractions: Dict) -> Dict[str, List[Dict]]:
    """
    Aggregate facts from per-passage extractions deterministically.

    This function collects ALL unique facts without lossy AI filtering.
    Only exact duplicates (same fact text) are merged by combining evidence.

    Args:
        per_passage_extractions: Dict of passage_id -> extraction data

    Returns:
        Dict mapping fact type to list of facts:
        {
            'world_rule': [...],
            'setting': [...],
            'timeline': [...],
            'character_identity': [...],
            'variables': [...]
        }
    """
    # First pass: collect all facts with deduplication by exact text match
    fact_map = {}  # fact_text -> fact dict with combined evidence

    for passage_id, extraction in per_passage_extractions.items():
        facts = extraction.get('facts', [])

        for fact in facts:
            fact_text = fact.get('fact', '').strip()
            fact_type = fact.get('type', 'unknown')
            category = fact.get('category', 'constant')

            if not fact_text:
                continue

            # Create unique key from fact text
            key = fact_text

            if key in fact_map:
                # Exact duplicate - merge evidence
                existing_fact = fact_map[key]
                existing_evidence = existing_fact.get('evidence', [])
                new_evidence = fact.get('evidence', [])

                # Normalize evidence to lists (may be string or list)
                if isinstance(existing_evidence, str):
                    existing_evidence = [{'quote': existing_evidence}]
                if isinstance(new_evidence, str):
                    new_evidence = [{'quote': new_evidence}]
                if not isinstance(existing_evidence, list):
                    existing_evidence = []
                if not isinstance(new_evidence, list):
                    new_evidence = []

                # Combine evidence lists
                combined_evidence = existing_evidence + new_evidence
                existing_fact['evidence'] = combined_evidence
            else:
                # New unique fact - store it
                evidence = fact.get('evidence', [])
                # Normalize evidence to list
                if isinstance(evidence, str):
                    evidence = [{'quote': evidence}]
                if not isinstance(evidence, list):
                    evidence = []

                fact_map[key] = {
                    'fact': fact_text,
                    'type': fact_type,
                    'category': category,
                    'confidence': fact.get('confidence', 'medium'),
                    'evidence': evidence
                }

    # Second pass: group by fact type
    grouped = {}

    for fact in fact_map.values():
        fact_type = fact.get('type', 'unknown')
        category = fact.get('category', 'constant')

        # Variables go into their own group regardless of type
        if category == 'variable':
            if 'variables' not in grouped:
                grouped['variables'] = []
            grouped['variables'].append(fact)
        else:
            # Constants group by type
            if fact_type not in grouped:
                grouped[fact_type] = []
            grouped[fact_type].append(fact)

    return grouped


# AI prompt for name normalization
NAME_NORMALIZATION_PROMPT = """=== ROLE ===

You are identifying name variants that refer to the same entity.

=== TASK ===

Given a list of character names extracted from facts, identify which names are variants of the same entity.

Focus ONLY on:
- Punctuation artifacts: "Danita," vs "Danita"
- Possessive forms: "Javlyn's" vs "Javlyn"
- Capitalization variants: "kian" vs "Kian"
- Common spelling variants

Do NOT merge:
- Different names that happen to be similar
- Names that could be different people

=== OUTPUT FORMAT ===

Respond with ONLY valid JSON (no markdown, no code blocks):

{{
  "name_mappings": [
    {{
      "variants": ["Danita,", "Danita"],
      "canonical": "Danita"
    }},
    {{
      "variants": ["Javlyn's", "Javlyn"],
      "canonical": "Javlyn"
    }}
  ]
}}

If no variants found, return: {{"name_mappings": []}}

=== INPUT NAMES ===

{names_json}

BEGIN NORMALIZATION (JSON only):
"""


def normalize_entity_names(facts: List[Dict]) -> Dict[str, str]:
    """
    Use AI to identify name variants that should be unified.

    This function asks AI to identify punctuation artifacts and possessive forms,
    NOT to decide what facts to keep/drop.

    Args:
        facts: List of facts (typically character_identity facts)

    Returns:
        Dict mapping variant name -> canonical name
        Example: {'Danita,': 'Danita', "Javlyn's": 'Javlyn'}
    """
    # Extract all character names from facts
    names = set()
    for fact in facts:
        fact_text = fact.get('fact', '')
        # Simple extraction: capitalized words
        words = fact_text.split()
        for word in words:
            if word and word[0].isupper():
                cleaned = word.rstrip(',.;:!?\'\"')
                if cleaned:
                    names.add(cleaned)

    if not names:
        return {}

    try:
        # Format names as JSON for prompt
        names_json = json.dumps(list(names), indent=2)

        # Build AI prompt
        prompt = NAME_NORMALIZATION_PROMPT.format(names_json=names_json)

        # Call Ollama API
        logging.info(f"Normalizing {len(names)} entity names...")

        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistency
                    "num_predict": 2000
                },
                "think": "low"
            },
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()
        result = response.json()

        # Parse response
        raw_response = result.get('response', '')
        parsed = parse_json_from_response(raw_response)

        # Build mapping
        name_mapping = {}
        mappings = parsed.get('name_mappings', [])

        for mapping in mappings:
            variants = mapping.get('variants', [])
            canonical = mapping.get('canonical', '')

            if not canonical or not variants:
                continue

            # Map each variant to canonical
            for variant in variants:
                if variant != canonical:
                    name_mapping[variant] = canonical

        logging.info(f"  → Found {len(name_mapping)} name variants")
        return name_mapping

    except Exception as e:
        logging.warning(f"Name normalization failed: {e}")
        return {}


def group_facts_by_character(facts: List[Dict], name_mapping: Dict[str, str]) -> Dict[str, Dict]:
    """
    Group character facts by character name, applying name normalization.

    Each fact is added to ALL characters mentioned in it, not just the first.
    This ensures facts like "Danita, Kian, and Terence are travelers" appear
    under all three characters.

    Args:
        facts: List of character_identity facts
        name_mapping: Dict mapping variant names to canonical names

    Returns:
        Dict mapping character name to facts organized by category:
        {
            'Kian': {
                'identity': [...],
                'zero_action_state': [...],
                'variables': [...]
            }
        }
    """
    characters = {}

    for fact in facts:
        # Extract ALL character names from this fact
        fact_text = fact.get('fact', '')
        char_names = extract_all_characters_from_fact(fact_text)

        # If no names found, use "Unknown"
        if not char_names:
            char_names = ["Unknown"]

        # Apply name normalization and add fact to each character
        for char_name in char_names:
            # Apply name normalization
            canonical_name = name_mapping.get(char_name, char_name)

            # Initialize character entry if needed
            if canonical_name not in characters:
                characters[canonical_name] = {
                    'identity': [],
                    'zero_action_state': [],
                    'variables': []
                }

            # Route to appropriate sub-category
            category = fact.get('category', 'constant')

            if category == 'variable':
                characters[canonical_name]['variables'].append(fact)
            elif category == 'zero_action_state':
                characters[canonical_name]['zero_action_state'].append(fact)
            else:
                characters[canonical_name]['identity'].append(fact)

    return characters


def group_facts_by_category(all_facts: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group facts by category type for chunked summarization.

    Groups facts into categories to send smaller batches to Ollama:
    - world_rule: World rules and magic systems
    - setting: Geography, landmarks, locations
    - timeline: Historical events and chronology
    - character_identity: Character identities and zero-action states
    - variables: Variable outcomes, events, and player-dependent facts

    Args:
        all_facts: List of all facts from per-passage extractions

    Returns:
        Dict mapping category name to list of facts in that category
    """
    groups = {}

    for fact in all_facts:
        fact_type = fact.get('type', 'unknown')
        category = fact.get('category', 'constant')

        # Variables go into their own group regardless of type
        if category == 'variable':
            if 'variables' not in groups:
                groups['variables'] = []
            groups['variables'].append(fact)
        # Character identity facts (including zero_action_state)
        elif fact_type == 'character_identity':
            if 'character_identity' not in groups:
                groups['character_identity'] = []
            groups['character_identity'].append(fact)
        # Constants group by type
        elif fact_type == 'world_rule':
            if 'world_rule' not in groups:
                groups['world_rule'] = []
            groups['world_rule'].append(fact)
        elif fact_type == 'setting':
            if 'setting' not in groups:
                groups['setting'] = []
            groups['setting'].append(fact)
        elif fact_type == 'timeline':
            if 'timeline' not in groups:
                groups['timeline'] = []
            groups['timeline'].append(fact)
        else:
            # Unknown types go to variables as fallback
            if 'variables' not in groups:
                groups['variables'] = []
            groups['variables'].append(fact)

    return groups


def merge_chunk_facts(per_passage_extractions: Dict) -> Dict:
    """
    Merge facts from chunks of the same passage before main deduplication.

    For passages that were chunked (chunks_processed > 1), merge duplicate facts
    from different chunks of the same passage.

    Args:
        per_passage_extractions: Dict of passage_id -> extraction data

    Returns:
        Modified per_passage_extractions with chunk facts merged
    """
    merged = {}

    for passage_id, extraction in per_passage_extractions.items():
        chunks_processed = extraction.get('chunks_processed', 1)

        if chunks_processed == 1:
            # No merging needed - single chunk
            merged[passage_id] = extraction
        else:
            # Multiple chunks - merge duplicate facts
            facts = extraction.get('facts', [])

            # Group facts by similarity (simple: same fact text)
            fact_groups = {}
            for fact in facts:
                fact_text = fact.get('fact', '').strip()
                if fact_text not in fact_groups:
                    fact_groups[fact_text] = []
                fact_groups[fact_text].append(fact)

            # Merge facts in each group
            merged_facts = []
            for fact_text, group in fact_groups.items():
                if len(group) == 1:
                    # Unique fact - keep as is (but strip chunk metadata)
                    fact = dict(group[0])
                    fact.pop('_chunk_number', None)
                    fact.pop('_chunk_total', None)
                    merged_facts.append(fact)
                else:
                    # Duplicate fact across chunks - merge evidence
                    base_fact = dict(group[0])
                    base_fact.pop('_chunk_number', None)
                    base_fact.pop('_chunk_total', None)

                    # Combine evidence from all chunks
                    all_evidence = []
                    for fact in group:
                        evidence = fact.get('evidence', [])
                        if evidence:
                            all_evidence.extend(evidence)

                    base_fact['evidence'] = all_evidence
                    merged_facts.append(base_fact)

            # Update extraction with merged facts
            merged[passage_id] = {
                **extraction,
                'facts': merged_facts
            }

    return merged


def summarize_category(facts: List[Dict], category_name: str) -> Tuple[Optional[Dict], List[Dict]]:
    """
    Summarize facts for a single category using AI.

    Args:
        facts: List of facts in this category
        category_name: Name of category (for logging and prompt)

    Returns:
        Tuple of (summarized_facts_list, conflicts_list)
        Returns (None, []) if summarization fails
    """
    if not facts:
        return ([], [])

    label = CATEGORY_LABELS.get(category_name, category_name)

    try:
        # Format facts as JSON for prompt
        facts_json = json.dumps(facts, indent=2)

        # Build AI prompt
        prompt = CATEGORY_SUMMARIZATION_PROMPT.format(
            category_label=label,
            facts_json=facts_json
        )

        # Call Ollama API
        logging.info(f"Summarizing {category_name}: {len(facts)} facts...")

        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 16000  # Smaller limit per category
                },
                "think": "low"
            },
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()
        result = response.json()

        # Parse response
        raw_response = result.get('response', '')
        summarized = parse_json_from_response(raw_response)

        # Extract facts and conflicts
        summarized_facts = summarized.get('facts', [])
        conflicts = summarized.get('conflicts', [])

        logging.info(f"  → {len(summarized_facts)} summarized facts, {len(conflicts)} conflicts")
        return (summarized_facts, conflicts)

    except Exception as e:
        logging.error(f"Error summarizing {category_name}: {e}")
        return (None, [])


def summarize_facts(per_passage_extractions: Dict) -> Tuple[Optional[Dict], str]:
    """
    Aggregate and deduplicate facts from per-passage extractions.

    Supports two extraction formats:
    1. Entity-first format (new): extractions have 'entities' dict with characters, locations, items
    2. Fact-based format (legacy): extractions have 'facts' list with typed fact objects

    Args:
        per_passage_extractions: Dict of passage_id -> extraction data

    Returns:
        Tuple of (summarized_facts, status) where:
        - summarized_facts: Dict with unified facts (or None if failed)
        - status: "success" or "failed"
    """
    try:
        # Pre-process: Merge facts from chunks of same passage
        merged_extractions = merge_chunk_facts(per_passage_extractions)

        if not merged_extractions:
            logging.warning("No extractions to summarize")
            return (None, "failed")

        # Detect extraction format by checking first extraction
        first_extraction = next(iter(merged_extractions.values()), {})
        has_entities = 'entities' in first_extraction and first_extraction.get('entities')
        has_facts = 'facts' in first_extraction and first_extraction.get('facts')

        if has_entities:
            # NEW ENTITY-FIRST FORMAT
            logging.info("Detected entity-first extraction format")
            return summarize_from_entities(merged_extractions)
        elif has_facts:
            # LEGACY FACT-BASED FORMAT
            logging.info("Detected legacy fact-based extraction format")
            return summarize_from_facts(merged_extractions)
        else:
            logging.warning("No entities or facts found in extractions")
            return (None, "failed")

    except Exception as e:
        logging.error(f"Unexpected error during aggregation: {e}")
        import traceback
        traceback.print_exc()
        return (None, "failed")


def summarize_from_entities(merged_extractions: Dict) -> Tuple[Optional[Dict], str]:
    """
    Aggregate from entity-first extraction format.

    This is the new lossless aggregation that directly processes entities
    (characters, locations, items) without AI filtering.
    """
    logging.info("Aggregating entities deterministically (lossless)...")

    # Aggregate all entities across passages
    aggregated = aggregate_entities_from_extractions(merged_extractions)

    char_count = len(aggregated.get('characters', {}))
    loc_count = len(aggregated.get('locations', {}))
    item_count = len(aggregated.get('items', {}))

    logging.info(f"  → {char_count} characters, {loc_count} locations, {item_count} items")

    # Build final structure
    # Convert characters dict to expected format
    characters = {}
    for name, data in aggregated.get('characters', {}).items():
        characters[name] = {
            'identity': data.get('identity', []),
            'zero_action_state': [],  # Not extracted in entity format
            'variables': [],  # Not extracted in entity format
            'passages': data.get('passages', []),
            'mentions': data.get('mentions', [])
        }

    # Convert locations to setting facts
    setting_facts = []
    for name, data in aggregated.get('locations', {}).items():
        for fact in data.get('facts', []):
            setting_facts.append({
                'fact': f"{name}: {fact}",
                'type': 'setting',
                'evidence': data.get('mentions', [])[:3],  # Limit evidence
                'passages': data.get('passages', [])
            })
        # Also add a basic "exists" fact if no facts
        if not data.get('facts'):
            setting_facts.append({
                'fact': f"Location: {name}",
                'type': 'setting',
                'evidence': data.get('mentions', [])[:3],
                'passages': data.get('passages', [])
            })

    # Convert items to setting facts (or separate category)
    for name, data in aggregated.get('items', {}).items():
        for fact in data.get('facts', []):
            setting_facts.append({
                'fact': f"{name}: {fact}",
                'type': 'setting',
                'evidence': data.get('mentions', [])[:3],
                'passages': data.get('passages', [])
            })
        if not data.get('facts'):
            setting_facts.append({
                'fact': f"Item: {name}",
                'type': 'setting',
                'evidence': data.get('mentions', [])[:3],
                'passages': data.get('passages', [])
            })

    result = {
        'constants': {
            'world_rules': [],
            'setting': setting_facts,
            'timeline': []
        },
        'characters': characters,
        'variables': {
            'events': [],
            'outcomes': []
        },
        'conflicts': []
    }

    logging.info("Entity aggregation successful (lossless)")
    logging.info(f"  Characters: {len(characters)}")
    logging.info(f"  Setting facts: {len(setting_facts)}")

    return (result, "success")


def summarize_from_facts(merged_extractions: Dict) -> Tuple[Optional[Dict], str]:
    """
    Aggregate from legacy fact-based extraction format.

    This is the original lossless aggregation that processes typed facts.
    """
    logging.info("Aggregating facts deterministically (lossless)...")

    # Aggregate facts deterministically
    aggregated = aggregate_facts_deterministically(merged_extractions)

    total_facts = sum(len(facts) for facts in aggregated.values())
    logging.info(f"  → {total_facts} unique facts after deduplication")

    # Extract character facts for name normalization
    character_facts = aggregated.get('character_identity', [])

    # Use AI to normalize entity names (punctuation/possessive only)
    name_mapping = {}
    if character_facts:
        logging.info(f"Normalizing character names ({len(character_facts)} character facts)...")
        name_mapping = normalize_entity_names(character_facts)
        if name_mapping:
            logging.info(f"  → Normalized {len(name_mapping)} name variants")

    # Group character facts by character (with normalization)
    characters = group_facts_by_character(character_facts, name_mapping)

    # Build final structure
    result = {
        'constants': {
            'world_rules': aggregated.get('world_rule', []),
            'setting': aggregated.get('setting', []),
            'timeline': aggregated.get('timeline', [])
        },
        'characters': characters,
        'variables': {
            'events': [],
            'outcomes': aggregated.get('variables', [])
        },
        'conflicts': []
    }

    logging.info("Fact aggregation successful (lossless)")
    logging.info(f"  World rules: {len(result['constants']['world_rules'])}")
    logging.info(f"  Setting: {len(result['constants']['setting'])}")
    logging.info(f"  Timeline: {len(result['constants']['timeline'])}")
    logging.info(f"  Characters: {len(characters)}")
    logging.info(f"  Variables: {len(result['variables']['outcomes'])}")

    return (result, "success")


def main():
    """Test AI summarizer functionality."""
    import argparse
    from pathlib import Path

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description='Test AI summarizer module')
    parser.add_argument('cache_file', type=Path, help='Path to story-bible-cache.json')
    parser.add_argument('--output', type=Path, help='Output JSON file (optional)')

    args = parser.parse_args()

    # Load cache
    with open(args.cache_file, 'r', encoding='utf-8') as f:
        cache = json.load(f)

    per_passage = cache.get('per_passage_extractions', {})

    if not per_passage:
        print("Error: No per_passage_extractions found in cache")
        return 1

    # Summarize facts
    summarized, status = summarize_facts(per_passage)

    if status == "success" and summarized:
        print(f"\nSummarization successful!")
        print(f"  Constants: {len(summarized.get('constants', {}))}")
        print(f"  Characters: {len(summarized.get('characters', {}))}")
        print(f"  Variables: {len(summarized.get('variables', {}))}")
        print(f"  Conflicts: {len(summarized.get('conflicts', []))}")

        # Save if requested
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(summarized, f, indent=2)
            print(f"\nSaved to {args.output}")
    else:
        print(f"\nSummarization failed: {status}")
        return 1

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
