#!/usr/bin/env python3
"""
Stage 3: Categorizer Module

Organizes extracted facts into constants, variables, and character states.

Input:
    - extracted_facts.json (from Stage 2)
    - loaded_paths.json (from Stage 1)

Output:
    - categorized_facts.json (intermediate artifact)

Responsibilities:
    - Cross-reference facts across all paths
    - Identify constants (appear in all paths)
    - Identify variables (differ by path)
    - Determine zero action state for characters
    - Merge duplicate facts
    - Detect conflicts/contradictions
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict
import difflib


def normalize_fact_text(fact_text: str) -> str:
    """
    Normalize fact text for comparison.

    Args:
        fact_text: Raw fact text

    Returns:
        Normalized fact text (lowercase, stripped)
    """
    return fact_text.lower().strip()


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate similarity between two texts using sequence matching.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score between 0.0 and 1.0
    """
    return difflib.SequenceMatcher(None, text1, text2).ratio()


def merge_duplicate_facts(facts: List[Dict]) -> List[Dict]:
    """
    Merge duplicate or very similar facts.

    Uses fuzzy matching (>90% similarity) to identify duplicates.

    Args:
        facts: List of fact dicts

    Returns:
        Deduplicated list of facts with combined evidence
    """
    if not facts:
        return []

    merged = []
    processed = set()

    for i, fact1 in enumerate(facts):
        if i in processed:
            continue

        # Start a new merged fact
        merged_fact = {
            'fact': fact1['fact'],
            'type': fact1['type'],
            'confidence': fact1.get('confidence', 'medium'),
            'evidence': [{'passage': fact1.get('passage', 'Unknown'),
                         'quote': fact1.get('evidence', '')}],
            'category': fact1.get('category', 'constant')
        }

        # Look for similar facts to merge
        for j, fact2 in enumerate(facts[i+1:], start=i+1):
            if j in processed:
                continue

            # Check similarity
            similarity = calculate_similarity(
                normalize_fact_text(fact1['fact']),
                normalize_fact_text(fact2['fact'])
            )

            if similarity > 0.9:  # 90% similarity threshold
                # Merge evidence
                merged_fact['evidence'].append({
                    'passage': fact2.get('passage', 'Unknown'),
                    'quote': fact2.get('evidence', '')
                })
                processed.add(j)

        processed.add(i)
        merged.append(merged_fact)

    return merged


def categorize_facts(extracted_facts: Dict, loaded_data: Dict) -> Dict:
    """
    Categorize facts into constants, variables, and character states.

    Args:
        extracted_facts: Output from Stage 2 (ai_extractor)
        loaded_data: Output from Stage 1 (loader)

    Returns:
        Dict with structure:
        {
            "constants": {
                "world_rules": [...],
                "setting": [...],
                "timeline": [...]
            },
            "characters": {
                "CharacterName": {
                    "identity": [...],
                    "zero_action_state": [...],
                    "variables": [...]
                }
            },
            "variables": {
                "events": [...],
                "outcomes": [...]
            },
            "conflicts": [...]
        }
    """
    print("\nCategorizing facts...", file=sys.stderr)

    # Get total number of paths for coverage calculation
    total_paths = loaded_data['metadata']['total_paths']
    passages = loaded_data['passages']

    # Data structures for categorization
    fact_occurrences = defaultdict(lambda: {
        'fact': '',
        'type': '',
        'evidence': [],
        'paths': set(),
        'category': 'constant',
        'confidence': 'medium'
    })

    # Process all extractions
    extractions = extracted_facts.get('extractions', [])

    for extraction in extractions:
        passage_name = extraction.get('passage_name', 'Unknown')
        facts = extraction.get('facts', [])

        # Get paths this passage appears in
        passage_data = passages.get(passage_name, {})
        passage_paths = set(passage_data.get('appears_in_paths', []))

        for fact in facts:
            # Create a key for this fact (normalized text + type)
            fact_key = (
                normalize_fact_text(fact.get('fact', '')),
                fact.get('type', 'unknown')
            )

            # Update fact occurrence tracking
            if not fact_occurrences[fact_key]['fact']:
                fact_occurrences[fact_key]['fact'] = fact.get('fact', '')
                fact_occurrences[fact_key]['type'] = fact.get('type', 'unknown')
                fact_occurrences[fact_key]['category'] = fact.get('category', 'constant')
                fact_occurrences[fact_key]['confidence'] = fact.get('confidence', 'medium')

            # Add evidence
            fact_occurrences[fact_key]['evidence'].append({
                'passage': passage_name,
                'quote': fact.get('evidence', '')
            })

            # Track paths
            fact_occurrences[fact_key]['paths'].update(passage_paths)

    # Categorize facts based on path coverage
    constants_by_type = defaultdict(list)
    variables_by_type = defaultdict(list)
    characters = defaultdict(lambda: {
        'identity': [],
        'zero_action_state': [],
        'variables': []
    })

    for fact_key, fact_data in fact_occurrences.items():
        fact_type = fact_data['type']
        path_coverage = len(fact_data['paths']) / total_paths if total_paths > 0 else 0
        category = fact_data['category']

        # Build fact object
        fact_obj = {
            'fact': fact_data['fact'],
            'evidence': fact_data['evidence'][:5],  # Limit to 5 pieces of evidence
            'confidence': fact_data['confidence'],
            'appears_in_paths': list(fact_data['paths'])[:10]  # Limit to 10 path IDs
        }

        # Categorize based on type and path coverage
        if fact_type == 'character_identity':
            # Extract character name (assume it's in the fact text)
            # This is a simplification - could be improved with NER
            char_name = extract_character_name(fact_data['fact'])

            if category == 'zero_action_state':
                characters[char_name]['zero_action_state'].append(fact_obj)
            elif path_coverage >= 0.8:  # Constant if in 80%+ of paths
                characters[char_name]['identity'].append(fact_obj)
            else:
                characters[char_name]['variables'].append(fact_obj)

        elif path_coverage >= 0.8:  # Constants: appear in 80%+ of paths
            if fact_type in ['world_rule', 'world_rules']:
                constants_by_type['world_rules'].append(fact_obj)
            elif fact_type == 'setting':
                constants_by_type['setting'].append(fact_obj)
            elif fact_type == 'timeline':
                constants_by_type['timeline'].append(fact_obj)
            else:
                # Unknown constant type
                constants_by_type['other'].append(fact_obj)

        else:  # Variables: appear in some but not all paths
            if category == 'variable' or path_coverage < 0.8:
                variables_by_type['events'].append(fact_obj)

    # Detect conflicts (contradictory facts)
    conflicts = detect_conflicts(fact_occurrences)

    # Build result
    result = {
        'constants': dict(constants_by_type),
        'characters': dict(characters),
        'variables': dict(variables_by_type),
        'conflicts': conflicts,
        'metadata': {
            'total_facts': len(fact_occurrences),
            'total_constants': sum(len(v) for v in constants_by_type.values()),
            'total_variables': sum(len(v) for v in variables_by_type.values()),
            'total_characters': len(characters)
        }
    }

    # Print summary
    print(f"\nCategorization summary:", file=sys.stderr)
    print(f"  Total facts processed: {len(fact_occurrences)}", file=sys.stderr)
    print(f"  Constants: {result['metadata']['total_constants']}", file=sys.stderr)
    print(f"  Variables: {result['metadata']['total_variables']}", file=sys.stderr)
    print(f"  Characters: {result['metadata']['total_characters']}", file=sys.stderr)
    print(f"  Conflicts detected: {len(conflicts)}", file=sys.stderr)

    return result


def extract_character_name(fact_text: str) -> str:
    """
    Extract character name from fact text.

    This is a simple heuristic - looks for capitalized words.

    Args:
        fact_text: Fact text (e.g., "Javlyn is a student")

    Returns:
        Character name or "Unknown"
    """
    words = fact_text.split()
    for word in words:
        # Look for capitalized word that's not at start and not common words
        if word[0].isupper() and word.lower() not in ['the', 'a', 'an', 'is', 'was', 'has', 'have']:
            return word
    return "Unknown"


def detect_conflicts(fact_occurrences: Dict) -> List[Dict]:
    """
    Detect contradictory facts.

    Looks for facts of the same type with high similarity but different content.

    Args:
        fact_occurrences: Dict of fact occurrences

    Returns:
        List of conflict dicts
    """
    conflicts = []

    # Group facts by type
    facts_by_type = defaultdict(list)
    for fact_key, fact_data in fact_occurrences.items():
        facts_by_type[fact_data['type']].append((fact_key, fact_data))

    # Look for conflicts within each type
    for fact_type, facts in facts_by_type.items():
        for i, (key1, fact1) in enumerate(facts):
            for key2, fact2 in facts[i+1:]:
                # Check if facts are similar enough to be about the same thing
                # but different enough to be contradictory
                similarity = calculate_similarity(
                    normalize_fact_text(fact1['fact']),
                    normalize_fact_text(fact2['fact'])
                )

                # Potential conflict: 50-90% similar (related but different)
                if 0.5 <= similarity <= 0.9:
                    conflicts.append({
                        'type': 'contradictory_constants',
                        'description': f"Potentially conflicting facts about {fact_type}",
                        'facts': [
                            {
                                'fact': fact1['fact'],
                                'evidence': fact1['evidence'][:2]
                            },
                            {
                                'fact': fact2['fact'],
                                'evidence': fact2['evidence'][:2]
                            }
                        ]
                    })

    return conflicts


def main():
    """Test categorizer functionality."""
    import argparse

    parser = argparse.ArgumentParser(description='Test categorizer module')
    parser.add_argument('extracted_facts', type=Path, help='Path to extracted_facts.json from Stage 2')
    parser.add_argument('loaded_data', type=Path, help='Path to loaded_paths.json from Stage 1')
    parser.add_argument('--output', type=Path, help='Output JSON file (optional)')

    args = parser.parse_args()

    # Load input data
    with open(args.extracted_facts, 'r', encoding='utf-8') as f:
        extracted_facts = json.load(f)

    with open(args.loaded_data, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)

    # Categorize facts
    result = categorize_facts(extracted_facts, loaded_data)

    # Print summary
    print(f"\nCategorization complete:")
    print(f"  Constants: {result['metadata']['total_constants']}")
    print(f"  Variables: {result['metadata']['total_variables']}")
    print(f"  Characters: {result['metadata']['total_characters']}")
    print(f"  Conflicts: {len(result['conflicts'])}")

    # Save to file if requested
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved to {args.output}")


if __name__ == '__main__':
    main()
