"""The canon pack (``dist/canon-pack.json``) and per-passage retrieval (ADR-020).

The pack is built from the assembled Bible with no model. Each entity keeps at most
:data:`MAX_FACTS_PER_ENTITY` facts: pinned first, then by evidence (1 + the facts that
restate it), then newest. Duplicates, retired facts and scene state never reach it.

:func:`select_canon` picks the facts for one passage under review: a case-insensitive,
word-boundary, longest-first match of the alias index over the passage text, entities in
order of first mention. It leaves out facts drawn from the passage under review and facts
whose passage changed since extraction (stale), counting both, and offers at most
:data:`MAX_FACTS_PER_UNIT` facts, with the pinned facts of a mentioned entity on top of the
cap (AC-story-bible-21).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nanoif.bible.assemble import Bible, BibleFact
from nanoif.bible.ids import WORLD_SLUG, fact_number
from nanoif.schemas.artifacts import load_artifact, write_artifact

PACK_VERSION = 1
MAX_FACTS_PER_ENTITY = 6
MAX_FACTS_PER_UNIT = 40
MIN_ALIAS_LENGTH = 3
PRONOUNS = frozenset(
    """
    he she him her his hers they them their theirs it its i me my mine you your we us our
    himself herself themselves itself
    """.split()
)
_APOSTROPHES = str.maketrans({"‘": "'", "’": "'"})
_SPACE_RE = re.compile(r"\s+")
_ARTICLE_RE = re.compile(r"^(?:the|a|an)\s+")
_EDGE_RE = re.compile(r"^[^\w']+|[^\w']+$")


@dataclass(frozen=True)
class CanonFact:
    """A canon fact offered to the Continuity Editor.

    Attributes:
        id: Stable fact id, for example ``tamsin-reeve#2``.
        entity: Entity name.
        claim: The fact; the prompt shows it without the quote.
        passage: Name of the passage that established it.
        quote: Its verbatim quote, re-attached to a canon finding by the reporter.
        pinned: True for a ``pin:`` override.
    """

    id: str
    entity: str
    claim: str
    passage: str
    quote: str = ""
    pinned: bool = False


@dataclass(frozen=True)
class CanonSlice:
    """The canon offered for one passage.

    Attributes:
        facts: The facts, in entity order.
        entities: Slugs of the entities the passage mentions, in order of first mention.
        own_excluded: Facts left out because they come from the passage under review.
        stale_excluded: Facts left out because their passage changed since extraction.
        capped: Facts left out by :data:`MAX_FACTS_PER_UNIT`.
        intentional: Fact id to the intentional-conflict override that marks it.
    """

    facts: tuple[CanonFact, ...] = ()
    entities: tuple[str, ...] = ()
    own_excluded: int = 0
    stale_excluded: int = 0
    capped: int = 0
    intentional: dict[str, str] = field(default_factory=dict)


def index_form(name: str) -> str:
    """Return the alias-index form of a name: case-folded, plain apostrophes, no article.

    Args:
        name: A name or alias.

    Returns:
        The form matched against passage text.
    """
    form = _SPACE_RE.sub(" ", name.casefold().translate(_APOSTROPHES)).strip()
    return _EDGE_RE.sub("", _ARTICLE_RE.sub("", form))


def _pack_order(fact: BibleFact) -> tuple[int, int, int]:
    return (0 if fact.pinned else 1, -fact.evidence, -fact_number(fact.id))


def build_canon_pack(bible: Bible) -> dict[str, Any]:
    """Build the ``canon_pack`` artifact.

    Args:
        bible: The assembled Bible.

    Returns:
        The pack.
    """
    entities = []
    forms: dict[str, set[str]] = {}
    for entity in bible.entities:
        facts = sorted((*entity.facts, *entity.rules), key=_pack_order)[:MAX_FACTS_PER_ENTITY]
        entities.append(
            {
                "slug": entity.slug,
                "name": entity.name,
                "type": entity.type,
                "aliases": list(entity.aliases),
                "facts": [
                    {"id": f.id, "claim": f.claim, "quote": f.quote, "passage": f.passage,
                     "pinned": f.pinned}
                    for f in facts
                ],
            }
        )
        if entity.slug == WORLD_SLUG:
            continue
        for name in (entity.name, *entity.aliases):
            form = index_form(name)
            if len(form) >= MIN_ALIAS_LENGTH and form not in PRONOUNS:
                forms.setdefault(form, set()).add(entity.slug)
    conflicts = [
        {"id": c.id, "fact_ids": [f.id for f in c.facts], "intentional": False, "label": None}
        for c in bible.conflicts
    ] + [
        {"id": c.id, "fact_ids": [f.id for f in c.facts], "intentional": True,
         "label": c.intentional}
        for mystery in bible.mysteries
        for c in mystery.conflicts
    ]
    fresh = bible.freshness
    return {
        "version": PACK_VERSION,
        "source": {
            "commit": fresh.commit,
            "extracted_at": fresh.extracted_at,
            "cache_present": bible.cache_present,
        },
        "passages": dict(bible.passages),
        "entities": entities,
        "conflicts": sorted(conflicts, key=lambda c: c["id"]),
        "alias_index": {
            form: next(iter(slugs)) for form, slugs in sorted(forms.items()) if len(slugs) == 1
        },
    }


def write_canon_pack(bible: Bible, path: Path) -> dict[str, Any]:
    """Build the pack and write it, validated.

    Args:
        bible: The assembled Bible.
        path: ``dist/canon-pack.json``.

    Returns:
        The pack.

    Raises:
        ArtifactValidationError: The pack does not match its schema; nothing is written.
    """
    pack = build_canon_pack(bible)
    write_artifact(path, pack, "canon_pack")
    return pack


def load_canon_pack(path: Path) -> dict[str, Any]:
    """Read and validate ``dist/canon-pack.json``.

    Args:
        path: The pack file.

    Returns:
        The pack.

    Raises:
        BuildError: The file is missing or not JSON; a review never runs on no canon.
        ArtifactValidationError: It does not match the ``canon_pack`` schema.
    """
    return load_artifact(path, "canon_pack")


def _mentions(pack: Mapping[str, Any], text: str) -> list[str]:
    haystack = text.casefold().translate(_APOSTROPHES)
    claimed: list[tuple[int, int]] = []
    first: dict[str, int] = {}
    for form in sorted(pack["alias_index"], key=lambda f: (-len(f), f)):
        pattern = re.compile(r"(?<!\w)" + re.escape(form) + r"(?!\w)")
        for match in pattern.finditer(haystack):
            start, end = match.span()
            if any(start < b and a < end for a, b in claimed):
                continue
            claimed.append((start, end))
            slug = pack["alias_index"][form]
            first[slug] = min(first.get(slug, start), start)
    return sorted(first, key=lambda slug: (first[slug], slug))


def select_canon(
    pack: Mapping[str, Any], name: str, text: str, current_hashes: Mapping[str, str]
) -> CanonSlice:
    """Pick the canon facts for one passage under review.

    Args:
        pack: The canon pack.
        name: The passage under review.
        text: Its text now.
        current_hashes: Passage name to content hash of the story now.

    Returns:
        The slice, with what was left out counted.
    """
    by_slug = {entity["slug"]: entity for entity in pack["entities"]}
    mentioned = [slug for slug in _mentions(pack, text) if slug in by_slug]
    extracted = pack["passages"]
    facts: list[CanonFact] = []
    own = stale = capped = unpinned = 0
    for slug in mentioned:
        entity = by_slug[slug]
        for raw in entity["facts"]:
            if raw["passage"] == name:
                own += 1
                continue
            source = raw["passage"]
            if source in extracted and extracted[source] != current_hashes.get(source):
                stale += 1
                continue
            if not raw["pinned"]:
                if unpinned >= MAX_FACTS_PER_UNIT:
                    capped += 1
                    continue
                unpinned += 1
            facts.append(
                CanonFact(raw["id"], entity["name"], raw["claim"], source, raw["quote"],
                          raw["pinned"])
            )
    offered = {fact.id for fact in facts}
    intentional = {
        fid: conflict["label"] or conflict["id"]
        for conflict in pack["conflicts"]
        if conflict["intentional"]
        for fid in conflict["fact_ids"]
        if fid in offered
    }
    return CanonSlice(tuple(facts), tuple(mentioned), own, stale, capped, intentional)
