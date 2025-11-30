#!/usr/bin/env python3
"""
Story Bible Quality Metrics

Calculates quality metrics for extraction validation.
"""

from typing import Dict


def calculate_extraction_stats(cache: Dict) -> Dict:
    """
    Calculate comprehensive extraction statistics.

    Args:
        cache: Story Bible cache dict

    Returns:
        Dict with extraction statistics:
        {
            'total_passages': int,
            'passages_with_facts': int,
            'passages_with_no_facts': int,
            'average_facts_per_passage': float,
            'character_coverage': float,
            'fact_distribution': Dict[str, int],
            'extraction_success_rate': float,
            'deduplication_effectiveness': float
        }
    """
    passage_extractions = cache.get('passage_extractions', {})
    summarized_facts = cache.get('summarized_facts', {})

    total_passages = len(passage_extractions)

    # Count passages with facts
    passages_with_facts = sum(
        1 for extraction in passage_extractions.values()
        if len(extraction.get('facts', [])) > 0
    )
    passages_with_no_facts = total_passages - passages_with_facts

    # Calculate average facts per passage
    total_facts = sum(
        len(extraction.get('facts', []))
        for extraction in passage_extractions.values()
    )
    average_facts_per_passage = total_facts / total_passages if total_passages > 0 else 0.0

    # Character coverage (number of unique characters detected)
    character_coverage = calculate_character_coverage(summarized_facts)

    # Fact distribution
    fact_distribution = calculate_fact_distribution(summarized_facts)

    # Extraction success rate (passages processed without errors)
    extraction_success_rate = passages_with_facts / total_passages if total_passages > 0 else 0.0

    # Deduplication effectiveness
    deduplication_effectiveness = calculate_dedup_ratio(passage_extractions, summarized_facts)

    return {
        'total_passages': total_passages,
        'passages_with_facts': passages_with_facts,
        'passages_with_no_facts': passages_with_no_facts,
        'average_facts_per_passage': round(average_facts_per_passage, 2),
        'character_coverage': character_coverage,
        'fact_distribution': fact_distribution,
        'extraction_success_rate': round(extraction_success_rate, 3),
        'deduplication_effectiveness': round(deduplication_effectiveness, 3)
    }


def calculate_character_coverage(summarized_facts: Dict) -> int:
    """
    Calculate character coverage (number of unique characters detected).

    Args:
        summarized_facts: Summarized facts dict

    Returns:
        Number of unique characters detected
    """
    if not summarized_facts:
        return 0

    characters = summarized_facts.get('characters', {})
    return len(characters)


def calculate_fact_distribution(summarized_facts: Dict) -> Dict[str, int]:
    """
    Calculate fact distribution by type.

    Args:
        summarized_facts: Summarized facts dict

    Returns:
        Dict mapping fact type to count:
        {'character_identity': 46, 'setting': 52, 'world_rule': 38, 'timeline': 24}
    """
    if not summarized_facts:
        return {}

    distribution = {}

    # Count facts in constants
    constants = summarized_facts.get('constants', {})
    for fact_type, facts in constants.items():
        distribution[fact_type] = len(facts)

    # Count character facts
    characters = summarized_facts.get('characters', {})
    char_fact_count = 0
    for char_data in characters.values():
        char_fact_count += len(char_data.get('identity', []))
        char_fact_count += len(char_data.get('zero_action_state', []))
        char_fact_count += len(char_data.get('variables', []))

    if char_fact_count > 0:
        distribution['character_identity'] = char_fact_count

    # Count variable facts
    variables = summarized_facts.get('variables', {})
    variable_fact_count = sum(len(facts) for facts in variables.values())
    if variable_fact_count > 0:
        distribution['variables'] = variable_fact_count

    return distribution


def calculate_dedup_ratio(passage_extractions: Dict, summarized_facts: Dict) -> float:
    """
    Calculate deduplication effectiveness (reduction in fact count).

    Args:
        passage_extractions: Dict of passage_id -> extraction data
        summarized_facts: Summarized facts dict

    Returns:
        Deduplication ratio (0.0 to 1.0)
        Example: 0.47 means 47% reduction (160 raw facts → 85 deduplicated facts)
    """
    # Count raw facts
    raw_count = sum(
        len(extraction.get('facts', []))
        for extraction in passage_extractions.values()
    )

    if raw_count == 0:
        return 0.0

    # Count summarized facts
    final_count = 0

    if summarized_facts:
        # Count facts in constants
        constants = summarized_facts.get('constants', {})
        final_count += sum(len(facts) for facts in constants.values())

        # Count character facts
        characters = summarized_facts.get('characters', {})
        for char_data in characters.values():
            final_count += len(char_data.get('identity', []))
            final_count += len(char_data.get('zero_action_state', []))
            final_count += len(char_data.get('variables', []))

        # Count variable facts
        variables = summarized_facts.get('variables', {})
        final_count += sum(len(facts) for facts in variables.values())

    # Calculate reduction ratio
    return 1.0 - (final_count / raw_count) if raw_count > 0 else 0.0
