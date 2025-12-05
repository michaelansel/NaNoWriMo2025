#!/usr/bin/env python3
"""
Stage 2.5: Entity Aggregation Module

Aggregates entities from per-passage extractions into unified structure.

Input:
    - per_passage_extractions (Dict of passage_id -> extraction data)
    - Must be in entity-first format with 'entities' dict containing
      characters, locations, items, organizations, and concepts

Output:
    - aggregated_facts (Dict with constants, characters, variables, conflicts)
    - status ("success" | "failed")

Responsibilities:
    - Aggregate entities across passages deterministically (lossless)
    - Normalize entity names (strip possessives, title case)
    - Preserve complete evidence trail for all entities
    - Merge entities from chunked passages
"""

import json
import logging
from typing import Dict, List, Tuple, Optional

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

            # Add facts as identity with evidence
            for fact in char.get('facts', []):
                # Handle both old format (string) and new format (object with evidence)
                if isinstance(fact, dict):
                    # New format: fact is already an object with 'fact' and 'evidence' fields
                    fact_text = fact.get('fact', '').strip()
                    evidence_quote = fact.get('evidence', '')
                elif isinstance(fact, str):
                    # Old format: fact is a string, use first mention as evidence
                    fact_text = fact.strip()
                    # Find supporting quote from mentions
                    evidence_quote = ""
                    mentions_list = char.get('mentions', [])
                    if mentions_list and len(mentions_list) > 0:
                        evidence_quote = mentions_list[0].get('quote', '')
                else:
                    # Unknown format, skip
                    continue

                if not fact_text:
                    continue

                # Create fact object with evidence
                fact_obj = {
                    'fact': fact_text,
                    'evidence': [
                        {
                            'passage': passage_id,
                            'quote': evidence_quote
                        }
                    ]
                }

                # Check if fact already exists (merge evidence)
                existing_fact = None
                for existing in characters[normalized]['identity']:
                    if isinstance(existing, dict) and existing.get('fact') == fact_text:
                        existing_fact = existing
                        break

                if existing_fact:
                    # Merge evidence (add this passage's evidence)
                    existing_fact['evidence'].append({
                        'passage': passage_id,
                        'quote': evidence_quote
                    })
                else:
                    # New fact - add it
                    characters[normalized]['identity'].append(fact_obj)

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

            # Add facts with evidence
            for fact in loc.get('facts', []):
                # Handle both old format (string) and new format (object with evidence)
                if isinstance(fact, dict):
                    # New format: fact is already an object with 'fact' and 'evidence' fields
                    fact_text = fact.get('fact', '').strip()
                    evidence_quote = fact.get('evidence', '')
                elif isinstance(fact, str):
                    # Old format: fact is a string, use first mention as evidence
                    fact_text = fact.strip()
                    # Find supporting quote from mentions
                    evidence_quote = ""
                    mentions_list = loc.get('mentions', [])
                    if mentions_list and len(mentions_list) > 0:
                        evidence_quote = mentions_list[0].get('quote', '')
                else:
                    # Unknown format, skip
                    continue

                if not fact_text:
                    continue

                # Create fact object with evidence
                fact_obj = {
                    'fact': fact_text,
                    'evidence': [
                        {
                            'passage': passage_id,
                            'quote': evidence_quote
                        }
                    ]
                }

                # Check if fact already exists (merge evidence)
                existing_fact = None
                for existing in locations[normalized]['facts']:
                    if isinstance(existing, dict) and existing.get('fact') == fact_text:
                        existing_fact = existing
                        break

                if existing_fact:
                    # Merge evidence
                    existing_fact['evidence'].append({
                        'passage': passage_id,
                        'quote': evidence_quote
                    })
                else:
                    # New fact
                    locations[normalized]['facts'].append(fact_obj)

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

            # Add facts with evidence
            for fact in item.get('facts', []):
                # Handle both old format (string) and new format (object with evidence)
                if isinstance(fact, dict):
                    # New format: fact is already an object with 'fact' and 'evidence' fields
                    fact_text = fact.get('fact', '').strip()
                    evidence_quote = fact.get('evidence', '')
                elif isinstance(fact, str):
                    # Old format: fact is a string, use first mention as evidence
                    fact_text = fact.strip()
                    # Find supporting quote from mentions
                    evidence_quote = ""
                    mentions_list = item.get('mentions', [])
                    if mentions_list and len(mentions_list) > 0:
                        evidence_quote = mentions_list[0].get('quote', '')
                else:
                    # Unknown format, skip
                    continue

                if not fact_text:
                    continue

                # Create fact object with evidence
                fact_obj = {
                    'fact': fact_text,
                    'evidence': [
                        {
                            'passage': passage_id,
                            'quote': evidence_quote
                        }
                    ]
                }

                # Check if fact already exists (merge evidence)
                existing_fact = None
                for existing in items[normalized]['facts']:
                    if isinstance(existing, dict) and existing.get('fact') == fact_text:
                        existing_fact = existing
                        break

                if existing_fact:
                    # Merge evidence
                    existing_fact['evidence'].append({
                        'passage': passage_id,
                        'quote': evidence_quote
                    })
                else:
                    # New fact
                    items[normalized]['facts'].append(fact_obj)

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


def summarize_facts(per_passage_extractions: Dict) -> Tuple[Optional[Dict], str]:
    """
    Aggregate and deduplicate facts from per-passage extractions.

    Requires entity-first extraction format where extractions have 'entities' dict
    with characters, locations, and items.

    Args:
        per_passage_extractions: Dict of passage_id -> extraction data

    Returns:
        Tuple of (summarized_facts, status) where:
        - summarized_facts: Dict with unified facts (or None if failed)
        - status: "success" or "failed"

    Raises:
        ValueError: If extractions are not in entity-first format
    """
    try:
        # Pre-process: Merge entities from chunks of same passage
        merged_extractions = merge_chunk_facts(per_passage_extractions)

        if not merged_extractions:
            logging.warning("No extractions to summarize")
            return (None, "failed")

        # Verify entity-first format
        first_extraction = next(iter(merged_extractions.values()), {})
        has_entities = 'entities' in first_extraction and first_extraction.get('entities')

        if not has_entities:
            raise ValueError(
                "Extractions must be in entity-first format (have 'entities' dict). "
                "Legacy fact-based format is no longer supported. "
                "Re-run extraction with current extractor version."
            )

        logging.info("Processing entity-first extraction format")
        return summarize_from_entities(merged_extractions)

    except ValueError:
        raise  # Re-raise ValueError for fail-fast behavior
    except Exception as e:
        logging.error(f"Unexpected error during aggregation: {e}")
        import traceback
        traceback.print_exc()
        return (None, "failed")


def is_world_rule(fact_text: str) -> bool:
    """
    Heuristic to determine if a fact is a world rule.

    World rules are facts about how the world works (magic system, technology, physics).
    """
    fact_lower = fact_text.lower()

    # Keywords indicating world rules
    world_rule_keywords = [
        'magic', 'technology', 'always', 'never', 'requires',
        'system', 'law', 'rule', 'physics', 'power', 'ability',
        'electricity', 'industrial', 'medieval', 'modern',
        'can', 'cannot', 'must', 'forbidden', 'allowed'
    ]

    return any(keyword in fact_lower for keyword in world_rule_keywords)


def is_timeline_event(fact_text: str) -> bool:
    """
    Heuristic to determine if a fact is a historical/timeline event.

    Timeline events are things that happened before the story starts.
    """
    fact_lower = fact_text.lower()

    # Keywords indicating past events
    timeline_keywords = [
        'ago', 'years', 'decades', 'centuries',
        'before', 'ancient', 'old', 'historical',
        'was', 'were', 'had', 'ended', 'began',
        'witnessed', 'remembered', 'past', 'former',
        'destroyed', 'built', 'founded', 'established',
        'war', 'battle', 'conflict', 'calamity'
    ]

    return any(keyword in fact_lower for keyword in timeline_keywords)


def categorize_fact(fact_obj: Dict, entity_name: str) -> str:
    """
    Categorize a fact as 'world_rule', 'timeline', or 'setting'.

    Args:
        fact_obj: Fact object with 'fact' and 'evidence' fields
        entity_name: Name of the entity this fact belongs to

    Returns:
        Category string: 'world_rule', 'timeline', or 'setting'
    """
    fact_text = fact_obj.get('fact', '')

    if is_world_rule(fact_text):
        return 'world_rule'
    elif is_timeline_event(fact_text):
        return 'timeline'
    else:
        return 'setting'


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
    timeline_facts = []

    for name, data in aggregated.get('characters', {}).items():
        identity = []

        # Categorize character facts
        for fact_obj in data.get('identity', []):
            category = categorize_fact(fact_obj, name)

            if category == 'timeline':
                # Move to timeline instead of character identity
                timeline_facts.append({
                    'fact': f"{name}: {fact_obj['fact']}",
                    'type': 'timeline',
                    'evidence': fact_obj.get('evidence', []),
                    'source_entity': name
                })
            else:
                # Keep in character identity
                identity.append(fact_obj)

        characters[name] = {
            'identity': identity,
            'zero_action_state': [],  # Not extracted in entity format
            'variables': [],  # Not extracted in entity format
            'passages': data.get('passages', []),
            'mentions': data.get('mentions', [])
        }

    # Categorize location and item facts
    world_rules = []
    setting_facts = []

    for name, data in aggregated.get('locations', {}).items():
        facts_list = data.get('facts', [])

        if facts_list:
            for fact_obj in facts_list:
                category = categorize_fact(fact_obj, name)

                if category == 'world_rule':
                    world_rules.append({
                        'fact': f"{name}: {fact_obj['fact']}",
                        'type': 'world_rule',
                        'evidence': fact_obj.get('evidence', []),
                        'source_entity': name
                    })
                elif category == 'timeline':
                    timeline_facts.append({
                        'fact': f"{name}: {fact_obj['fact']}",
                        'type': 'timeline',
                        'evidence': fact_obj.get('evidence', []),
                        'source_entity': name
                    })
                else:
                    setting_facts.append({
                        'fact': f"{name}: {fact_obj['fact']}",
                        'type': 'setting',
                        'evidence': fact_obj.get('evidence', []),
                        'source_entity': name
                    })
        else:
            # No facts - add basic existence fact
            setting_facts.append({
                'fact': f"Location: {name}",
                'type': 'setting',
                'evidence': data.get('mentions', [])[:3],
                'passages': data.get('passages', [])
            })

    # Convert items to categorized facts
    for name, data in aggregated.get('items', {}).items():
        facts_list = data.get('facts', [])

        if facts_list:
            for fact_obj in facts_list:
                category = categorize_fact(fact_obj, name)

                if category == 'world_rule':
                    world_rules.append({
                        'fact': f"{name}: {fact_obj['fact']}",
                        'type': 'world_rule',
                        'evidence': fact_obj.get('evidence', []),
                        'source_entity': name
                    })
                elif category == 'timeline':
                    timeline_facts.append({
                        'fact': f"{name}: {fact_obj['fact']}",
                        'type': 'timeline',
                        'evidence': fact_obj.get('evidence', []),
                        'source_entity': name
                    })
                else:
                    setting_facts.append({
                        'fact': f"{name}: {fact_obj['fact']}",
                        'type': 'setting',
                        'evidence': fact_obj.get('evidence', []),
                        'source_entity': name
                    })
        else:
            # No facts - add basic existence fact
            setting_facts.append({
                'fact': f"Item: {name}",
                'type': 'setting',
                'evidence': data.get('mentions', [])[:3],
                'passages': data.get('passages', [])
            })

    result = {
        'constants': {
            'world_rules': world_rules,
            'setting': setting_facts,
            'timeline': timeline_facts
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
    logging.info(f"  World rules: {len(world_rules)}")
    logging.info(f"  Timeline: {len(timeline_facts)}")
    logging.info(f"  Setting facts: {len(setting_facts)}")

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
