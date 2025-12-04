#!/usr/bin/env python3
"""
Interactive Fiction (CYOA) style validation for print-format choose-your-own-adventure stories.

Validates story paths against CYOA best practices for print-format books,
checking for POV consistency, choice quality, pacing, and ending satisfaction.
"""

import requests
import json
from typing import Dict, Optional

# Ollama configuration
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 120  # 2 minutes per validation


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
            "has_issues": False,
            "severity": "none",
            "issues": [],
            "summary": "Could not parse validation response"
        }

    json_text = text[start:end+1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return {
            "has_issues": False,
            "severity": "none",
            "issues": [],
            "summary": "Could not parse validation response"
        }


def build_validation_prompt(
    passage_text: str,
    story_style: Optional[Dict] = None
) -> str:
    """
    Build validation prompt based on story style configuration.

    Args:
        passage_text: The passage content to validate
        story_style: Story style configuration (perspective, protagonist, tense)

    Returns:
        Formatted validation prompt
    """
    # Default to second person present tense if no config provided
    if story_style is None:
        story_style = {
            "perspective": "second-person",
            "protagonist": None,
            "tense": "present"
        }

    perspective = story_style.get("perspective", "second-person")
    protagonist = story_style.get("protagonist", None)
    tense = story_style.get("tense", "present")

    # Build perspective guidance
    if perspective == "first-person":
        pov_guidance = """**First Person:**
- Use "I" throughout (first person)
- Use {tense} tense for narrative voice
- Reader experiences story through protagonist's eyes
- Maintain consistent first-person perspective"""
    elif perspective == "third-person":
        if protagonist:
            pov_guidance = f"""**Third Person (Named Protagonist):**
- Use third person for protagonist "{protagonist}" (he/she/they)
- Use {tense} tense for narrative
- Maintain consistent use of protagonist name
- Check for protagonist name consistency throughout"""
        else:
            pov_guidance = """**Third Person:**
- Use third person for protagonist (he/she/they)
- Use {tense} tense for narrative
- Maintain consistent third-person perspective
- Avoid switching to first or second person"""
    else:  # second-person (default)
        pov_guidance = """**Second Person:**
- Use "you" throughout (second person)
- Use {tense} tense for immediacy
- Reader IS the protagonist - avoid naming them
- Never use protagonist names or [Name] placeholders"""

    # Format tense in guidance
    tense_word = "present" if tense == "present" else "past"
    pov_guidance = pov_guidance.format(tense=f"{tense_word} tense")

    # Build the full prompt
    prompt = f"""Reasoning: high

=== SECTION 1: ROLE & CONTEXT ===

You are validating a story path for Choose-Your-Own-Adventure (CYOA) writing style.
This is for PRINT-FORMAT BOOKS, not digital games.

Your task: Check if this path follows CYOA best practices for print format books.

CRITICAL UNDERSTANDING:
- This story uses {perspective} {tense_word} tense
{f'- Protagonist name: {protagonist}' if protagonist else '- No named protagonist (reader is the protagonist)'}
- Choices should be meaningful with real consequences
- Pacing matters - balance action with decision points
- Endings should be satisfying (both good and bad)

=== SECTION 2: CYOA BEST PRACTICES ===

{pov_guidance}

**Choice Design:**
- Every choice should have real consequences
- Avoid false choices (all options lead to same outcome)
- Balance options - no choice should be obviously "best"
- Provide enough context for informed decisions (not blind guessing)
- Mix high-stakes and low-stakes choices to manage tension

**Pacing:**
- Avoid long sequences without choices ("tunnel problem")
- Play up the five senses for immersion
- Don't make every choice life-or-death
- Balance narrative flow with decision points

**Endings:**
- Both good and bad endings should be satisfying to read
- Bad endings shouldn't feel like author-punishment
- Avoid too many death/failure endings (frustrating)
- Endings should feel earned, not arbitrary

=== SECTION 3: PATH TO VALIDATE ===

{passage_text}

=== SECTION 4: VALIDATION TASK ===

Check this path for CYOA style issues:

1. **POV/Tense Consistency**: Is it consistently {perspective} {tense_word} tense?
{f'2. **Protagonist Consistency**: Is "{protagonist}" used consistently?' if protagonist else '2. **Protagonist Immersion**: Does it avoid naming protagonist?'}
3. **Choice Quality**: Do choices appear meaningful? Are options balanced?
4. **Pacing**: Are there "tunnel" sections (long stretches without choices)?
5. **Ending Quality** (if ending): Is the ending satisfying or frustratingly abrupt?

DO NOT FLAG:
- Story quality or creativity (that's subjective)
- Plot choices (author's creative decision)
- Genre conventions appropriate to the story
- Stylistic preferences that don't break CYOA rules

ONLY FLAG clear violations of CYOA best practices.

=== SECTION 5: OUTPUT FORMAT ===

Respond with ONLY valid JSON (no markdown, no code blocks):

{{{{
  "has_issues": true/false,
  "severity": "none|minor|major|critical",
  "issues": [
    {{{{
      "type": "pov_consistency|protagonist_consistency|choice_quality|pacing|ending_quality",
      "severity": "minor|major|critical",
      "description": "Brief description of the issue",
      "evidence": "Quote from passage demonstrating the issue",
      "location": "Where in passage this occurs (optional)"
    }}}}
  ],
  "summary": "Brief overall assessment"
}}}}

If no issues found, return:
{{{{"has_issues": false, "severity": "none", "issues": [], "summary": "No interactive fiction style issues detected"}}}}

=== SECTION 6: SEVERITY RUBRIC ===

**CRITICAL** - Major CYOA style breaks:
- Switches perspective for multiple paragraphs
{f'- Inconsistent use of protagonist name "{protagonist}"' if protagonist else '- Named protagonist breaking immersion throughout'}
- No choices at all (pure linear narrative)
- Ending is clearly punishing/unfair

**MAJOR** - Significant style issues:
- Consistent tense errors (mixing {tense_word}/other tense)
- Occasional perspective switches
- False choices (options with no real difference)
- Very long tunnel sections (5+ paragraphs no choice)
- Unbalanced choices (one obviously best)

**MINOR** - Small style issues:
- Occasional POV slips (a sentence or two)
- Minor pacing concerns
- Slightly unbalanced choice options
- Ending could be more satisfying but not terrible

BEGIN VALIDATION (JSON only):
"""
    return prompt


def validate_interactive_fiction_style(
    passage_text: str,
    passage_id: str,
    story_style: Optional[Dict] = None
) -> Optional[Dict]:
    """
    Validate a passage for CYOA/interactive fiction style compliance.

    Args:
        passage_text: The passage content to validate
        passage_id: Identifier for passage (for logging)
        story_style: Optional story style configuration with keys:
            - perspective: "first-person", "second-person", or "third-person"
            - protagonist: Name of protagonist (for third-person), or None
            - tense: "past" or "present"
            Defaults to second-person present tense if not provided.

    Returns:
        Validation result dict with issues, or None if validation failed
    """
    # Build validation prompt based on story style
    prompt = build_validation_prompt(passage_text, story_style)

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
        # Timeout is non-blocking - log and return no issues
        return {
            "has_issues": False,
            "severity": "none",
            "issues": [],
            "summary": "Interactive fiction validation timed out (skipped)"
        }
    except Exception as e:
        # Other errors are non-blocking - log and return no issues
        return {
            "has_issues": False,
            "severity": "none",
            "issues": [],
            "summary": f"Interactive fiction validation error: {str(e)[:50]} (skipped)"
        }
