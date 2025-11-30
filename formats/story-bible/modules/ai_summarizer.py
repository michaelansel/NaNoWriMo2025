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

# AI prompt for summarization/deduplication
SUMMARIZATION_PROMPT = """=== SECTION 1: ROLE & CONTEXT ===

You are deduplicating facts extracted from multiple passages in an interactive fiction story.

Your task: Create a unified Story Bible by intelligently merging related facts while preserving complete evidence.

CRITICAL UNDERSTANDING:
- Input: Facts extracted from individual passages (may contain duplicates)
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
  "constants": {{
    "world_rules": [
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
    "setting": [...],
    "timeline": [...]
  }},
  "characters": {{
    "CharacterName": {{
      "identity": [...],
      "zero_action_state": [...],
      "variables": [...]
    }}
  }},
  "variables": {{
    "events": [...],
    "outcomes": [...]
  }},
  "conflicts": [
    {{
      "type": "contradictory_constants",
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

{per_passage_facts_json}

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


def summarize_facts(per_passage_extractions: Dict) -> Tuple[Optional[Dict], str]:
    """
    Deduplicate and merge facts from per-passage extractions using AI.

    Args:
        per_passage_extractions: Dict of passage_id -> extraction data

    Returns:
        Tuple of (summarized_facts, status) where:
        - summarized_facts: Dict with unified facts (or None if failed)
        - status: "success" or "failed"
    """
    try:
        # Build input for AI
        all_facts = build_summarization_input(per_passage_extractions)

        if not all_facts:
            logging.warning("No facts to summarize")
            return (None, "failed")

        # Format as JSON for prompt
        facts_json = json.dumps(all_facts, indent=2)

        # Build AI prompt
        prompt = SUMMARIZATION_PROMPT.format(per_passage_facts_json=facts_json)

        # Call Ollama API
        logging.info(f"Calling Ollama for summarization ({len(all_facts)} facts)...")

        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Lower temperature for consistent deduplication
                    "num_predict": 32000  # Enough for thinking + response
                },
                "think": "low"  # Key fix: minimize thinking for gpt-oss
            },
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()
        result = response.json()

        # Parse response
        raw_response = result.get('response', '')

        # Extract JSON from response
        summarized = parse_json_from_response(raw_response)

        # Validate structure
        if not validate_summarized_structure(summarized):
            logging.error("Summarization response missing required keys")
            return (None, "failed")

        logging.info("Summarization successful")
        return (summarized, "success")

    except requests.Timeout:
        logging.error("Summarization timeout (exceeded 300 seconds)")
        return (None, "failed")

    except requests.RequestException as e:
        logging.error(f"Ollama API error during summarization: {e}")
        return (None, "failed")

    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse summarization response as JSON: {e}")
        return (None, "failed")

    except Exception as e:
        logging.error(f"Unexpected error during summarization: {e}")
        return (None, "failed")


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
