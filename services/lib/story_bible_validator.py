#!/usr/bin/env python3
"""
Story Bible validation against established world constants.

Validates new story content against extracted Story Bible constants to detect
world-building contradictions.
"""

import requests
import json
from typing import Dict, List, Optional

# Ollama configuration
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 120  # 2 minutes per validation

# AI prompt for world consistency validation
VALIDATION_PROMPT = """Reasoning: high

=== SECTION 1: ROLE & CONTEXT ===

You are validating a story passage against established world constants.

Your task: Detect CONTRADICTIONS between the passage and known world facts.

CRITICAL UNDERSTANDING:
- World constants are CANONICAL - they represent established lore
- This passage is NEW CONTENT being validated
- Only flag DIRECT CONTRADICTIONS, not missing details
- Constants are true across ALL story paths

=== SECTION 2: WORLD CONSTANTS ===

The following facts are ESTABLISHED CONSTANTS about this story world:

{world_constants}

These constants are:
- **World Rules**: Magic systems, technology level, physical laws
- **Setting**: Geography, landmarks, historical events
- **Timeline**: Established chronology before story starts

=== SECTION 3: PASSAGE TO VALIDATE ===

{passage_text}

=== SECTION 4: VALIDATION TASK ===

Compare the passage against the world constants and detect:

1. **Direct Contradictions**: Passage states something that conflicts with constants
2. **Inconsistent Details**: Passage describes world differently than constants
3. **Timeline Violations**: Events contradict established chronology

DO NOT FLAG:
- Missing information (constants don't require all details to be mentioned)
- Character choices/outcomes (these are variables, not constants)
- Plot events (story progression is independent of world constants)
- Stylistic differences (same fact described differently is OK)

ONLY FLAG if passage DIRECTLY CONTRADICTS a constant.

=== SECTION 5: OUTPUT FORMAT ===

Respond with ONLY valid JSON (no markdown, no code blocks):

{{
  "has_violations": true/false,
  "severity": "none|minor|major|critical",
  "violations": [
    {{
      "type": "world_rule|setting|timeline|contradiction",
      "severity": "minor|major|critical",
      "description": "Brief description of the contradiction",
      "constant_fact": "The established constant being violated",
      "passage_statement": "Quote from passage that contradicts it",
      "evidence": {{
        "constant_source": "Passage where constant was established",
        "conflict_location": "Location in this passage"
      }}
    }}
  ],
  "summary": "Brief overall assessment"
}}

If no violations found, return:
{{"has_violations": false, "severity": "none", "violations": [], "summary": "No world consistency issues detected"}}

=== SECTION 6: SEVERITY RUBRIC ===

**CRITICAL** - Fundamental world-building contradictions:
- Magic system works differently than established
- Geography contradicts (city on coast vs mountains)
- Technology level inconsistent (medieval vs modern)
- Major historical events contradicted

**MAJOR** - Significant world detail contradictions:
- Landmark description differs from constant
- World rule details inconsistent
- Timeline order contradicted

**MINOR** - Small detail variations:
- Minor setting details differ
- Slight chronology ambiguity
- Non-essential world fact variance

BEGIN VALIDATION (JSON only):
"""


def format_constants_for_validation(story_bible_cache: Dict) -> str:
    """
    Format Story Bible constants into text for validation prompt.

    Args:
        story_bible_cache: Story Bible cache with categorized facts

    Returns:
        Formatted string of constants for prompt
    """
    categorized = story_bible_cache.get('categorized_facts', {})
    constants = categorized.get('constants', {})

    formatted_lines = []

    # World Rules
    world_rules = constants.get('world_rules', [])
    if world_rules:
        formatted_lines.append("**World Rules:**")
        for fact in world_rules:
            fact_text = fact.get('fact', 'Unknown')
            evidence = fact.get('evidence', '')
            formatted_lines.append(f"  - {fact_text}")
            if evidence:
                formatted_lines.append(f"    Evidence: \"{evidence}\"")
        formatted_lines.append("")

    # Setting
    setting = constants.get('setting', [])
    if setting:
        formatted_lines.append("**Setting:**")
        for fact in setting:
            fact_text = fact.get('fact', 'Unknown')
            evidence = fact.get('evidence', '')
            formatted_lines.append(f"  - {fact_text}")
            if evidence:
                formatted_lines.append(f"    Evidence: \"{evidence}\"")
        formatted_lines.append("")

    # Timeline
    timeline = constants.get('timeline', [])
    if timeline:
        formatted_lines.append("**Timeline:**")
        for fact in timeline:
            fact_text = fact.get('fact', 'Unknown')
            evidence = fact.get('evidence', '')
            formatted_lines.append(f"  - {fact_text}")
            if evidence:
                formatted_lines.append(f"    Evidence: \"{evidence}\"")
        formatted_lines.append("")

    if not formatted_lines:
        return "(No world constants established yet)"

    return "\n".join(formatted_lines)


def parse_json_from_response(text: str) -> Dict:
    """
    Extract JSON object from AI response that may contain extra text.

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
        return {
            "has_violations": False,
            "severity": "none",
            "violations": [],
            "summary": "Could not parse validation response"
        }

    json_text = text[start:end+1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return {
            "has_violations": False,
            "severity": "none",
            "violations": [],
            "summary": "Could not parse validation response"
        }


def merge_validation_results(path_result: Dict, world_result: Optional[Dict]) -> Dict:
    """
    Merge path consistency and world consistency validation results.

    Args:
        path_result: Result from path consistency checking
        world_result: Result from Story Bible validation (may be None)

    Returns:
        Combined result dict
    """
    # Start with path result
    combined = path_result.copy()

    # If no world validation, return path result as-is
    if not world_result:
        combined['world_validation'] = None
        return combined

    # Add world validation section
    combined['world_validation'] = world_result

    # Merge issues and recalculate severity
    # Don't merge into single list - we'll format separately in PR comment

    # Recalculate combined severity (take max of path and world)
    path_severity = path_result.get('severity', 'none')
    world_severity = world_result.get('severity', 'none')

    severity_order = {'none': 0, 'minor': 1, 'major': 2, 'critical': 3}
    combined_severity_value = max(
        severity_order.get(path_severity, 0),
        severity_order.get(world_severity, 0)
    )
    combined_severity = [k for k, v in severity_order.items() if v == combined_severity_value][0]

    combined['severity'] = combined_severity
    combined['has_issues'] = (
        path_result.get('has_issues', False) or
        world_result.get('has_violations', False)
    )

    return combined


def validate_against_story_bible(
    passage_text: str,
    story_bible_cache: Dict,
    passage_id: str
) -> Optional[Dict]:
    """
    Validate a passage against Story Bible constants.

    Args:
        passage_text: The passage content to validate
        story_bible_cache: Story Bible cache with categorized facts
        passage_id: Identifier for passage (for logging)

    Returns:
        Validation result dict with violations, or None if validation failed
    """
    # Check if Story Bible has constants
    categorized = story_bible_cache.get('categorized_facts', {})
    constants = categorized.get('constants', {})

    # If no constants, skip validation
    if not constants or not any(constants.values()):
        return {
            "has_violations": False,
            "severity": "none",
            "violations": [],
            "summary": "No Story Bible constants available for validation"
        }

    # Format constants for prompt
    world_constants = format_constants_for_validation(story_bible_cache)

    # Build validation prompt
    prompt = VALIDATION_PROMPT.format(
        world_constants=world_constants,
        passage_text=passage_text
    )

    # Call Ollama API
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,  # Low temperature for consistent validation
                    "num_predict": 1500
                }
            },
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()
        result = response.json()

        # Parse response
        raw_response = result.get('response', '')

        # Extract JSON from response
        validation_result = parse_json_from_response(raw_response)

        return validation_result

    except requests.Timeout:
        # Timeout is non-blocking - log and return no violations
        return {
            "has_violations": False,
            "severity": "none",
            "violations": [],
            "summary": "Story Bible validation timed out (skipped)"
        }
    except Exception as e:
        # Other errors are non-blocking - log and return no violations
        return {
            "has_violations": False,
            "severity": "none",
            "violations": [],
            "summary": f"Story Bible validation error: {str(e)[:50]} (skipped)"
        }
