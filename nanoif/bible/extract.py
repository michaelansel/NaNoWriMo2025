"""Stage 1, extract: one ``bible_extract`` call per passage, then deterministic filtering.

The model's answer is never stored as is. Code drops, and counts per passage:

- every fact whose quote is not a whitespace-normalized substring of the passage
  (``unverified_quote``; pronoun references whose quote is not found count here too);
- every fact of kind ``state`` (``state``);
- every entity whose normalized name starts with a quantifier or number word, or is
  empty (``generic_entity``).

Nothing dropped is silent: the counts go to the cache and the diff.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nanoif.bible.cache import Dropped
from nanoif.bible.ids import WORLD_SLUG, is_generic_name, normalize_name
from nanoif.bible.source import SourcePassage
from nanoif.llm.client import Completer
from nanoif.llm.prompts import prompt_schema, render_prompt
from nanoif.twee.links import display_text
from nanoif.twee.quotes import clean_quote, quote_found

PROMPT = "bible_extract"
REASONING_EFFORT = "low"
EXTRACT_MAX_TOKENS = 12_000
MAX_REFERENCES = 20
WORLD_NAME = "World"
PRONOUNS = frozenset(
    "he she him her his hers they them their theirs it its i me my you we us our".split()
)


@dataclass(frozen=True)
class RosterEntry:
    """A known entity offered to the extractor so it reuses the canonical name."""

    name: str
    type: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExtractedFact:
    """A verified fact, before it has an id."""

    claim: str
    quote: str
    kind: str


@dataclass(frozen=True)
class ExtractedEntity:
    """An entity as one passage names it, before resolution."""

    name: str
    type: str
    aliases: tuple[str, ...]
    role: str | None
    facts: tuple[ExtractedFact, ...]


@dataclass(frozen=True)
class ExtractedReference:
    """A verified pronoun reference; ``entity`` is the name the model gave, or ``None``."""

    quote: str
    pronoun: str
    entity: str | None


@dataclass(frozen=True)
class PassageExtraction:
    """What one passage yields after filtering.

    Attributes:
        passage: The passage that was read.
        summary: One or two sentences on what happens.
        entities: Entities with verified facts, merged by normalized name.
        references: Verified pronoun references, at most :data:`MAX_REFERENCES`.
        dropped: What was discarded, by reason.
    """

    passage: SourcePassage
    summary: str
    entities: tuple[ExtractedEntity, ...]
    references: tuple[ExtractedReference, ...]
    dropped: Dropped


def extract_tag(name: str) -> str:
    """Return the completer tag of a passage's extraction call."""
    return f"bible-extract:{name}"


def extract_passage(
    client: Completer,
    passage: SourcePassage,
    roster: Sequence[RosterEntry],
    not_entities: Sequence[str],
) -> PassageExtraction:
    """Extract one passage.

    Args:
        client: The completer.
        passage: The passage to read.
        roster: Known entities, so the model reuses their names.
        not_entities: ``not-entity:`` phrases from the overrides.

    Returns:
        The filtered extraction.

    Raises:
        LLMError: The call failed; the caller decides whether to re-attempt.
    """
    prompt = render_prompt(
        PROMPT,
        passage_name=passage.name,
        passage_text=passage.text,
        roster=[
            {"name": entry.name, "type": entry.type, "aliases": list(entry.aliases)}
            for entry in roster
        ],
        not_entities=list(not_entities),
    )
    result = client.complete(
        system=prompt.system,
        user=prompt.user,
        schema=prompt_schema(PROMPT),
        max_tokens=EXTRACT_MAX_TOKENS,
        reasoning_effort=REASONING_EFFORT,
        tag=extract_tag(passage.name),
    )
    return filter_extraction(passage, result.data)


def _clean_aliases(name: str, aliases: Sequence[str]) -> list[str]:
    seen = {normalize_name(name)}
    kept: list[str] = []
    for alias in aliases:
        alias = alias.strip()
        key = normalize_name(alias)
        if not key or key in seen or key in PRONOUNS or is_generic_name(alias):
            continue
        seen.add(key)
        kept.append(alias)
    return kept


def filter_extraction(passage: SourcePassage, data: Mapping[str, Any]) -> PassageExtraction:
    """Apply the deterministic filters to a schema-valid ``bible_extract`` answer.

    Args:
        passage: The passage the answer is about.
        data: The answer.

    Returns:
        The filtered extraction.
    """
    texts = [passage.text, display_text(passage.text)]
    dropped = Dropped()
    merged: dict[str, dict[str, Any]] = {}
    for raw in data["entities"]:
        etype = raw["type"]
        name = WORLD_NAME if etype == "world" else raw["name"].strip()
        if not name or is_generic_name(name):
            dropped.generic_entity += 1
            continue
        facts: list[ExtractedFact] = []
        for fact in raw["facts"]:
            if fact["kind"] == "state":
                dropped.state += 1
                continue
            quote, claim = clean_quote(fact["quote"]), fact["claim"].strip()
            if not claim or not quote_found(quote, texts):
                dropped.unverified_quote += 1
                continue
            facts.append(ExtractedFact(claim, quote, fact["kind"]))
        key = WORLD_SLUG if etype == "world" else normalize_name(name)
        entry = merged.setdefault(
            key, {"name": name, "type": etype, "aliases": [], "role": None, "facts": []}
        )
        entry["aliases"] += list(raw["aliases"])
        role = (raw["role"] or "").strip()
        entry["role"] = entry["role"] or role or None
        entry["facts"] += facts
    entities = tuple(
        ExtractedEntity(
            name=entry["name"],
            type=entry["type"],
            aliases=tuple(_clean_aliases(entry["name"], entry["aliases"])),
            role=entry["role"],
            facts=tuple(entry["facts"]),
        )
        for entry in merged.values()
    )
    references: list[ExtractedReference] = []
    for raw in data["references"]:
        quote = clean_quote(raw["quote"])
        if not quote_found(quote, texts) or not raw["pronoun"].strip():
            dropped.unverified_quote += 1
            continue
        entity = (raw["entity"] or "").strip() or None
        references.append(ExtractedReference(quote, raw["pronoun"].strip(), entity))
    return PassageExtraction(
        passage=passage,
        summary=data["summary"].strip(),
        entities=entities,
        references=tuple(references[:MAX_REFERENCES]),
        dropped=dropped,
    )
