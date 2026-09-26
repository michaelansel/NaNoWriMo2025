"""Stage 4, assemble: the Bible from the cache, the overrides and current hashes (ADR-020).

Deterministic and model-free; it runs on every build and is the only input of the page
and the canon pack. Overrides apply here, so an edit to ``story-overrides.txt`` shows in
the next preview without extraction:

- ``alias:`` merges the entities it names under the canonical name;
- ``not-entity:`` removes an entity whose normalized name or alias is the phrase;
- ``pin:`` adds a pinned fact ``<slug>#pin-<hash>``, flagged when its quote is not found;
- ``intentional-conflict:`` moves the conflicts it names (by id, or by entity and quote
  fragment) to Intentional mysteries.

A line that has no effect is listed in :attr:`Bible.unmatched`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from nanoif.bible.cache import BibleCache, Entity, Fact
from nanoif.bible.ids import fact_number, normalize_name, pin_fact_id
from nanoif.check.overrides import (
    AliasOverride,
    NotEntityOverride,
    Overrides,
    Payload,
    PinOverride,
)
from nanoif.twee.links import display_text
from nanoif.twee.quotes import normalize_text, quote_found

EXTRACTION_RESULTS = ("success", "failure", "cancelled", "skipped")
SECTION_TYPES = {"cast": "character", "places": "location", "items": "item", "groups": "group"}


@dataclass(frozen=True)
class BibleFact:
    """A fact as the page and the canon pack show it.

    Attributes:
        id: Stable fact id (``<slug>#<n>`` or ``<slug>#pin-<hash>``).
        claim: The fact.
        quote: The verbatim quote behind it.
        passage: The passage the quote is from.
        kind: The fact kind (``trait`` for pins).
        pinned: True for a ``pin:`` override.
        quote_found: False when a pinned fact's quote is not in its passage.
        evidence: 1 plus the number of facts that restate it.
        restatements: Ids of the facts marked ``duplicate_of`` this one.
    """

    id: str
    claim: str
    quote: str
    passage: str
    kind: str
    pinned: bool = False
    quote_found: bool = True
    evidence: int = 1
    restatements: tuple[str, ...] = ()


@dataclass(frozen=True)
class BibleEntity:
    """One entry of Cast, Places, Items or Groups (or the world)."""

    slug: str
    name: str
    type: str
    aliases: tuple[str, ...]
    role: str | None
    passages: tuple[str, ...]
    facts: tuple[BibleFact, ...]
    rules: tuple[BibleFact, ...]
    pending: bool = False


@dataclass(frozen=True)
class BibleConflict:
    """Two facts of one entity that disagree.

    Attributes:
        id: ``c-<slug>-<n>``.
        entity: The entity's slug.
        entity_name: The entity's name.
        note: What disagrees.
        facts: The two facts, with quotes.
        intentional: The intentional-conflict override (id or label) that marks it.
    """

    id: str
    entity: str
    entity_name: str
    note: str
    facts: tuple[BibleFact, BibleFact]
    intentional: str | None = None


@dataclass(frozen=True)
class Mystery:
    """An ``intentional-conflict:`` line and the conflicts it moved."""

    label: str
    line: int
    conflicts: tuple[BibleConflict, ...]


@dataclass(frozen=True)
class Freshness:
    """How current the Bible is.

    Attributes:
        commit: Commit of the extraction shown, or ``None`` with no cache.
        extracted_at: When it ran (ISO 8601 UTC).
        mode: ``incremental`` or ``full``.
        extraction_result: How the latest extraction job ended (``success``, ``failure``,
            ``cancelled`` or ``skipped``).
        changed: Passages whose text changed since they were read.
        new: Passages the extraction never read.
        deleted: Passages the cache has that no longer exist.
        pending: Entities whose reconciliation is still pending.
    """

    commit: str | None
    extracted_at: str | None
    mode: str | None
    extraction_result: str
    changed: tuple[str, ...]
    new: tuple[str, ...]
    deleted: tuple[str, ...]
    pending: tuple[str, ...]

    @property
    def unread(self) -> tuple[str, ...]:
        """Passages the Bible has not read in their current form, sorted."""
        return tuple(sorted({*self.changed, *self.new}))


@dataclass(frozen=True)
class Bible:
    """The assembled Story Bible.

    Attributes:
        cache_present: False when there is no extraction yet (the placeholder).
        passage_count: Prose passages in the story now.
        entities: Every visible entity, sorted by name.
        conflicts: Open conflicts not marked intentional.
        mysteries: Intentional mysteries with the conflicts they hold.
        unmatched: ``(line, text)`` of override lines that had no effect.
        freshness: How current it is.
        passages: Passage name to the content hash the extraction read.
    """

    cache_present: bool
    passage_count: int
    entities: tuple[BibleEntity, ...]
    conflicts: tuple[BibleConflict, ...]
    mysteries: tuple[Mystery, ...]
    unmatched: tuple[tuple[int, str], ...]
    freshness: Freshness
    passages: dict[str, str] = field(default_factory=dict)

    def section(self, name: str) -> tuple[BibleEntity, ...]:
        """Entities of one page section: ``cast``, ``places``, ``items`` or ``groups``."""
        return tuple(e for e in self.entities if e.type == SECTION_TYPES[name])

    @property
    def cast(self) -> tuple[BibleEntity, ...]:
        """Characters."""
        return self.section("cast")

    @property
    def places(self) -> tuple[BibleEntity, ...]:
        """Locations."""
        return self.section("places")

    @property
    def items(self) -> tuple[BibleEntity, ...]:
        """Items."""
        return self.section("items")

    @property
    def groups(self) -> tuple[BibleEntity, ...]:
        """Groups."""
        return self.section("groups")

    @property
    def world_rules(self) -> tuple[tuple[str, BibleFact], ...]:
        """``(entity name, fact)`` for every fact of kind ``rule``."""
        return tuple((e.name, rule) for e in self.entities for rule in e.rules)

    def intentional_facts(self) -> dict[str, str]:
        """Fact id to the override that marks a conflict it is in as intentional."""
        return {
            fact.id: conflict.intentional
            for mystery in self.mysteries
            for conflict in mystery.conflicts
            for fact in conflict.facts
            if conflict.intentional is not None
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize for ``story-bible.json`` (schema ``story_bible``)."""
        def entity(e: BibleEntity) -> dict[str, Any]:
            data = asdict(e)
            data["aliases"], data["passages"] = list(e.aliases), list(e.passages)
            data["facts"] = [_fact_dict(f) for f in e.facts]
            data["rules"] = [_fact_dict(f) for f in e.rules]
            return data

        fresh = self.freshness
        return {
            "cache_present": self.cache_present,
            "passage_count": self.passage_count,
            **{name: [entity(e) for e in self.section(name)] for name in SECTION_TYPES},
            "world_rules": [{"entity": name, **_fact_dict(f)} for name, f in self.world_rules],
            "conflicts": [_conflict_dict(c) for c in self.conflicts],
            "intentional_mysteries": [
                {"label": m.label, "line": m.line,
                 "conflicts": [_conflict_dict(c) for c in m.conflicts]}
                for m in self.mysteries
            ],
            "unmatched_overrides": [{"line": line, "text": text} for line, text in self.unmatched],
            "freshness": {
                "commit": fresh.commit,
                "extracted_at": fresh.extracted_at,
                "mode": fresh.mode,
                "extraction_result": fresh.extraction_result,
                "changed": list(fresh.changed),
                "new": list(fresh.new),
                "deleted": list(fresh.deleted),
                "pending": list(fresh.pending),
            },
        }


def _fact_dict(fact: BibleFact) -> dict[str, Any]:
    data = asdict(fact)
    data["restatements"] = list(fact.restatements)
    return data


def _conflict_dict(conflict: BibleConflict) -> dict[str, Any]:
    return {
        "id": conflict.id,
        "entity": conflict.entity_name,
        "note": conflict.note,
        "facts": [_fact_dict(f) for f in conflict.facts],
        "intentional": conflict.intentional,
    }


@dataclass
class _Working:
    entity: Entity
    names: set[str]
    pins: list[BibleFact] = field(default_factory=list)


def _forms(entity: Entity) -> set[str]:
    return {normalize_name(name) for name in (entity.name, *entity.aliases)} - {""}


def _merge_aliases(entity: Entity, extra: list[str]) -> None:
    seen = {normalize_name(entity.name)} | {normalize_name(a) for a in entity.aliases}
    for alias in extra:
        key = normalize_name(alias)
        if key and key not in seen:
            seen.add(key)
            entity.aliases.append(alias)


def _copy(entity: Entity) -> Entity:
    return Entity(
        slug=entity.slug,
        name=entity.name,
        type=entity.type,
        aliases=list(entity.aliases),
        role=entity.role,
        passages=list(entity.passages),
        next_n=entity.next_n,
        reconcile=entity.reconcile,
        facts=[Fact(**asdict(fact)) for fact in entity.facts],
    )


def _describe(line: Payload) -> str:
    if isinstance(line, AliasOverride):
        return f"alias: {line.canonical} = {', '.join(line.aliases)}"
    if isinstance(line, NotEntityOverride):
        return f"not-entity: {line.phrase}"
    if isinstance(line, PinOverride):
        return f"pin: {line.entity} = {line.claim}"
    return f"intentional-conflict: {line.name}"


def assemble(
    cache: BibleCache | None,
    overrides: Overrides,
    current_hashes: Mapping[str, str],
    *,
    texts: Mapping[str, str] | None = None,
    extraction_result: str = "success",
) -> Bible:
    """Assemble the Bible.

    Args:
        cache: The cache, or ``None`` before the first extraction.
        overrides: The parsed ``story-overrides.txt``.
        current_hashes: Passage name to content hash of the story now.
        texts: Passage name to text now, to check pinned quotes; without it a pin's
            quote counts as not found.
        extraction_result: How the latest extraction job ended.

    Returns:
        The Bible.
    """
    texts = texts or {}
    if cache is None:
        return Bible(
            cache_present=False,
            passage_count=len(current_hashes),
            entities=(),
            conflicts=(),
            mysteries=(),
            unmatched=tuple((o.line, _describe(o)) for o in _all_lines(overrides)),
            freshness=Freshness(None, None, None, extraction_result, (),
                                tuple(sorted(current_hashes)), (), ()),
        )
    unmatched: list[tuple[int, str]] = []
    work = {e.slug: _Working(_copy(e), _forms(e)) for e in cache.live_entities()}
    moved: dict[str, str] = {}

    for alias in overrides.aliases:
        forms = {normalize_name(n) for n in (alias.canonical, *alias.aliases)}
        hits = [slug for slug, w in work.items() if w.names & forms]
        if not hits:
            unmatched.append((alias.line, _describe(alias)))
            continue
        canonical = normalize_name(alias.canonical)
        target = next((s for s in hits if normalize_name(work[s].entity.name) == canonical),
                      hits[0])
        keep = work[target].entity
        for slug in hits:
            if slug == target:
                continue
            other = work.pop(slug).entity
            moved[slug] = target
            _merge_aliases(keep, [other.name, *other.aliases])
            keep.facts.extend(other.facts)
            keep.passages.extend(p for p in other.passages if p not in keep.passages)
            keep.role = keep.role or other.role
            keep.reconcile = "pending" if "pending" in (keep.reconcile, other.reconcile) else "done"
        keep.name = alias.canonical
        _merge_aliases(keep, list(alias.aliases))
        work[target].names = _forms(keep)

    for line in overrides.not_entities:
        phrase = normalize_name(line.phrase)
        hits = [slug for slug, w in work.items() if phrase in w.names]
        if not hits:
            unmatched.append((line.line, _describe(line)))
        for slug in hits:
            del work[slug]

    for pin in overrides.pins:
        key = normalize_name(pin.entity)
        slug = next((s for s, w in work.items() if key in w.names), None)
        if slug is None:
            unmatched.append((pin.line, _describe(pin)))
            continue
        text = texts.get(pin.passage)
        found = text is not None and quote_found(pin.quote, [text, display_text(text)])
        work[slug].pins.append(
            BibleFact(pin_fact_id(slug, pin.claim), pin.claim, pin.quote, pin.passage, "trait",
                      pinned=True, quote_found=found)
        )

    entities = [_finish(w) for w in work.values()]
    entities = [e for e in entities if e.passages or e.facts or e.rules]
    entities.sort(key=lambda e: (e.name.casefold(), e.slug))
    visible = {e.slug: e for e in entities}

    conflicts: list[BibleConflict] = []
    for conflict in sorted(cache.conflicts.values(), key=lambda c: c.id):
        slug = moved.get(conflict.entity, conflict.entity)
        entity = visible.get(slug)
        if conflict.status != "open" or entity is None:
            continue
        facts = {f.id: f for f in work[slug].entity.facts}
        if not all(fid in facts for fid in conflict.fact_ids):
            continue
        pair = tuple(_plain(facts[fid]) for fid in conflict.fact_ids)
        conflicts.append(BibleConflict(conflict.id, slug, entity.name, conflict.note, pair))

    mysteries: list[Mystery] = []
    taken: set[str] = set()
    for line in overrides.intentional_conflicts:
        if line.conflict_id is not None:
            hits = [c for c in conflicts if c.id == line.conflict_id and c.id not in taken]
        else:
            key = normalize_name(line.entity or "")
            slug = next((s for s, w in work.items() if key in w.names), None)
            fragment = normalize_text(line.fragment or "").casefold()
            hits = [
                c for c in conflicts
                if c.entity == slug and c.id not in taken and fragment
                and any(fragment in normalize_text(f.quote).casefold() for f in c.facts)
            ]
        if not hits:
            unmatched.append((line.line, _describe(line)))
            continue
        taken |= {c.id for c in hits}
        marked = tuple(BibleConflict(c.id, c.entity, c.entity_name, c.note, c.facts, line.name)
                       for c in hits)
        mysteries.append(Mystery(line.name, line.line, marked))

    extraction = cache.extraction
    return Bible(
        cache_present=True,
        passage_count=len(current_hashes),
        entities=tuple(entities),
        conflicts=tuple(c for c in conflicts if c.id not in taken),
        mysteries=tuple(mysteries),
        unmatched=tuple(sorted(unmatched)),
        freshness=Freshness(
            commit=extraction.commit if extraction else None,
            extracted_at=extraction.extracted_at if extraction else None,
            mode=extraction.mode if extraction else None,
            extraction_result=extraction_result,
            changed=tuple(sorted(n for n, h in current_hashes.items()
                                 if n in cache.passages and cache.passages[n].content_hash != h)),
            new=tuple(sorted(n for n in current_hashes if n not in cache.passages)),
            deleted=tuple(sorted(n for n in cache.passages if n not in current_hashes)),
            pending=tuple(e.name for e in entities if e.pending),
        ),
        passages={name: record.content_hash for name, record in sorted(cache.passages.items())},
    )


def _all_lines(overrides: Overrides) -> list[Payload]:
    lines = [*overrides.aliases, *overrides.not_entities, *overrides.pins,
             *overrides.intentional_conflicts]
    return sorted(lines, key=lambda line: line.line)


def _plain(fact: Fact, evidence: int = 1, restatements: tuple[str, ...] = ()) -> BibleFact:
    return BibleFact(fact.id, fact.claim, fact.quote, fact.passage, fact.kind,
                     evidence=evidence, restatements=restatements)


def _finish(work: _Working) -> BibleEntity:
    entity = work.entity
    restated: dict[str, list[str]] = {}
    for fact in entity.facts:
        if fact.duplicate_of is not None:
            restated.setdefault(fact.duplicate_of, []).append(fact.id)
    shown = sorted(
        (_plain(f, 1 + len(restated.get(f.id, [])), tuple(restated.get(f.id, [])))
         for f in entity.facts if f.duplicate_of is None),
        key=lambda f: fact_number(f.id),
    )
    return BibleEntity(
        slug=entity.slug,
        name=entity.name,
        type=entity.type,
        aliases=tuple(entity.aliases),
        role=entity.role,
        passages=tuple(entity.passages),
        facts=tuple(work.pins) + tuple(f for f in shown if f.kind != "rule"),
        rules=tuple(f for f in shown if f.kind == "rule"),
        pending=entity.reconcile == "pending",
    )
