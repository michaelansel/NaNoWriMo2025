"""The Continuity Editor: one model call per review unit, then deterministic checks.

The model sees the unit text (earlier passages and the passage under review, by id) and
the canon slice for the passage (:func:`nanoif.bible.canon.select_canon`), quote-less.
Its answer is never trusted as is:

- a finding that does not quote the passage under review, names an unknown or third
  passage, or names the passage under review as the "other" source is dropped;
- every quote must be a whitespace-normalized substring of the passage it cites, and a
  ``path`` finding must quote both passages, else the finding goes to ``unverified``;
- severity is clamped to the range its type allows (:data:`TYPE_SEVERITY`);
- the key is computed from the type and the two passage names;
- a canon finding gets the fact's verbatim quote re-attached as its second quote.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from nanoif.bible.canon import CanonFact
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
from nanoif.review.units import ReviewStory, ReviewUnit

EDITOR = "continuity"
PROMPT = "continuity"
REASONING_EFFORT = "medium"

ANY_SEVERITY = ("minor", "critical")
TYPE_SEVERITY: dict[str, tuple[str, str]] = {
    "death_then_alive": ("critical", "critical"),
    "world_rule": ("major", "critical"),
    "name_typo": ("minor", "minor"),
}
"""Severity range per type; types not listed take the rubric answer as is."""


def build_prompt(
    story: ReviewStory, unit: ReviewUnit, canon: Sequence[CanonFact] = ()
) -> Prompt:
    """Render the Continuity Editor prompt for a unit.

    Args:
        story: The story (for canon passage ids).
        unit: The unit.
        canon: Canon facts to offer; nothing is rendered when empty.

    Returns:
        The rendered :class:`~nanoif.llm.prompts.Prompt`.
    """
    return render_prompt(
        PROMPT,
        unit_text=unit.text,
        passage_id=unit.under_review.id,
        canon=[
            {
                "id": fact.id,
                "entity": fact.entity,
                "claim": fact.claim,
                "passage_id": story.ids.get(fact.passage, fact.passage),
            }
            for fact in canon
        ],
    )


def review_unit(
    client: Completer,
    story: ReviewStory,
    unit: ReviewUnit,
    canon: Sequence[CanonFact] = (),
) -> UnitFindings:
    """Run the Continuity Editor on one unit.

    Args:
        client: The completer.
        story: The story.
        unit: The unit.
        canon: Canon facts offered as source ``[B]``.

    Returns:
        Verified, unverified, and dropped findings.

    Raises:
        LLMError: The call failed; the runner decides whether to re-attempt.
    """
    prompt = build_prompt(story, unit, canon)
    result = client.complete(
        system=prompt.system,
        user=prompt.user,
        schema=prompt_schema(PROMPT),
        reasoning_effort=REASONING_EFFORT,
        tag=unit.tag,
    )
    return postprocess(story, unit, result.data, canon)


def postprocess(
    story: ReviewStory,
    unit: ReviewUnit,
    data: Mapping[str, Any],
    canon: Sequence[CanonFact] = (),
) -> UnitFindings:
    """Turn the model's answer for one unit into findings.

    Args:
        story: The story.
        unit: The unit the model saw.
        data: The schema-valid answer.
        canon: The canon facts that were offered.

    Returns:
        Verified, unverified, and dropped findings.
    """
    out = UnitFindings()
    target = unit.under_review
    in_unit = unit.by_id
    facts = {fact.id: fact for fact in canon}
    for raw in data.get("findings", []):
        other_name: str | None = None
        fact_id: str | None = None
        if raw["source"] == "canon":
            fact = facts.get(raw["other"].get("fact_id") or "")
            if fact is not None and fact.passage in story.content:
                other_name, fact_id = fact.passage, fact.id
        else:
            entry = in_unit.get(raw["other"].get("passage_id") or "")
            if entry is not None and not entry.under_review:
                other_name = entry.name
        if other_name is None or other_name == target.name:
            out.dropped += 1
            continue

        allowed = {target.id: target.name}
        if raw["source"] == "path":
            allowed[story.ids[other_name]] = other_name
        cited = [(allowed.get(q["passage_id"]), q["text"]) for q in raw["quotes"]]
        if any(name is None for name, _ in cited) or not any(
            name == target.name for name, _ in cited
        ):
            out.dropped += 1
            continue

        quotes = tuple(Quote(name, clean_quote(text)) for name, text in cited if name)
        verified = all(
            quote_found(quote.text, passage_texts(story, quote.passage, unit)) for quote in quotes
        )
        if fact_id is not None:
            fact = facts[fact_id]
            if fact.quote and quote_found(fact.quote, passage_texts(story, fact.passage)):
                quotes = (*quotes, Quote(fact.passage, fact.quote))
        if raw["source"] == "path":
            verified = verified and any(quote.passage == other_name for quote in quotes)

        finding_type = raw["type"]
        finding = Finding(
            key=finding_key(finding_type, target.name, other_name),
            editor=EDITOR,
            type=finding_type,
            severity=clamp_severity(raw["severity"], TYPE_SEVERITY.get(finding_type, ANY_SEVERITY)),
            confidence=raw["confidence"],
            description=raw["description"].strip() or finding_type,
            passages=(passage_ref(story, target.name), passage_ref(story, other_name)),
            quotes=quotes,
            canon_fact_id=fact_id,
        )
        (out.findings if verified else out.unverified).append(finding)
    return out
