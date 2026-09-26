"""The Style Editor: point of view, tense, and protagonist naming, one passage at a time.

Settings come from ``storyStyle`` in StoryData. Findings are single-passage: the key is
``type|P|P``. Quotes must come from the passage under review; a finding whose quote is not
found goes to ``unverified``. A finding for a setting the story does not define is dropped,
and severity is clamped to the range its type allows.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from nanoif.llm.client import Completer
from nanoif.llm.prompts import Prompt, prompt_schema, render_prompt
from nanoif.review.findings import (
    Finding,
    Quote,
    UnitFindings,
    clamp_severity,
    clean_quote,
    finding_key,
    passage_ref,
    passage_texts,
    quote_found,
)
from nanoif.review.units import STORY_STYLE_KEYS, ReviewStory, ReviewUnit

EDITOR = "style"
PROMPT = "style"
REASONING_EFFORT = "low"

TYPE_SETTING = {"pov_slip": "perspective", "tense_slip": "tense", "protagonist_name": "protagonist"}
TYPE_SEVERITY: dict[str, tuple[str, str]] = {
    "pov_slip": ("minor", "major"),
    "tense_slip": ("minor", "major"),
    "protagonist_name": ("minor", "minor"),
}


def build_prompt(story: ReviewStory, unit: ReviewUnit) -> Prompt:
    """Render the Style Editor prompt for a unit.

    Args:
        story: The story (for ``storyStyle``).
        unit: A single-passage unit.

    Returns:
        The rendered prompt.
    """
    style = {key: story.style.values.get(key) for key in STORY_STYLE_KEYS}
    return render_prompt(
        PROMPT, unit_text=unit.text, passage_id=unit.under_review.id, style=style
    )


def review_unit(client: Completer, story: ReviewStory, unit: ReviewUnit) -> UnitFindings:
    """Run the Style Editor on one passage.

    Args:
        client: The completer.
        story: The story.
        unit: A single-passage unit.

    Returns:
        Verified, unverified, and dropped findings.

    Raises:
        LLMError: The call failed; the runner decides whether to re-attempt.
    """
    prompt = build_prompt(story, unit)
    result = client.complete(
        system=prompt.system,
        user=prompt.user,
        schema=prompt_schema(PROMPT),
        reasoning_effort=REASONING_EFFORT,
        tag=unit.tag,
    )
    return postprocess(story, unit, result.data)


def postprocess(story: ReviewStory, unit: ReviewUnit, data: Mapping[str, Any]) -> UnitFindings:
    """Turn the model's answer for one passage into findings.

    Args:
        story: The story.
        unit: The unit the model saw.
        data: The schema-valid answer.

    Returns:
        Verified, unverified, and dropped findings.
    """
    out = UnitFindings()
    name = unit.under_review.name
    texts = passage_texts(story, name, unit)
    for raw in data.get("findings", []):
        finding_type = raw["type"]
        if TYPE_SETTING[finding_type] not in story.style.values:
            out.dropped += 1
            continue
        quotes = tuple(Quote(name, clean_quote(q["text"])) for q in raw["quotes"])
        verified = bool(quotes) and all(quote_found(q.text, texts) for q in quotes)
        finding = Finding(
            key=finding_key(finding_type, name, name),
            editor=EDITOR,
            type=finding_type,
            severity=clamp_severity(raw["severity"], TYPE_SEVERITY[finding_type]),
            confidence=raw["confidence"],
            description=raw["description"].strip() or finding_type,
            passages=(passage_ref(story, name),),
            quotes=quotes or (Quote(name, "(no quote given)"),),
        )
        (out.findings if verified else out.unverified).append(finding)
    return out
