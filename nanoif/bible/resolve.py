"""Stage 2, resolve: which extracted names are which entity (ADR-020).

1. ``story-overrides.txt`` first: an entity whose name or alias is a ``not-entity:`` phrase
   is removed, and names in one ``alias:`` line are one entity under its canonical name.
2. Deterministic: occurrences that share a normalized name or alias form one cluster; a
   cluster whose forms are in the cache's ``resolution`` (or name a live entity) joins it.
3. At most one ``bible_resolve`` call per run for the clusters left, as
   ``{key, type, names, sample_claims<=2, passages}`` beside the existing entities. Code
   applies only ``high`` merges of one type whose keys are each used at most once, and
   drops of new clusters. When the call fails (after one re-attempt) the clusters become
   entities of their own marked pending, and the run is partial.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from nanoif.bible.cache import BibleCache
from nanoif.bible.extract import PassageExtraction
from nanoif.bible.ids import WORLD_SLUG, normalize_name
from nanoif.check.overrides import Overrides
from nanoif.llm.client import Completer
from nanoif.llm.errors import LLMError, LLMRunHalted
from nanoif.llm.prompts import prompt_schema, render_prompt

__all__ = ["RESOLVE_TAG", "NewEntity", "Resolution", "normalize_name", "resolve"]

PROMPT = "bible_resolve"
REASONING_EFFORT = "medium"
RESOLVE_TAG = "bible-resolve"
SAMPLE_CLAIMS = 2

Occurrence = tuple[str, int]
"""``(passage name, index of the entity in that passage's extraction)``."""


@dataclass(frozen=True)
class NewEntity:
    """An entity this run creates.

    Attributes:
        key: Its key in :attr:`Resolution.assignments` (``k<n>``, or ``world``).
        name: The name it is shown under.
        type: ``character``, ``location``, ``item``, ``group`` or ``world``.
        aliases: Other names, never equal to ``name`` once normalized.
        role: A few words on who or what it is, when a passage said.
        pending: True when the resolve call failed, so nobody checked it is new.
    """

    key: str
    name: str
    type: str
    aliases: tuple[str, ...]
    role: str | None
    pending: bool = False


@dataclass
class Resolution:
    """Where every extracted entity goes.

    Attributes:
        assignments: Occurrence to an existing slug, a :attr:`new_entities` key, or
            ``None`` when it is not an entity (override or model drop).
        new_entities: Entities to create, by key.
        merges: Model merges applied, as ``{into, members: [names]}``.
        dropped: Model drops applied, as ``{names, reason}``.
        failed: Why the resolve call failed, or ``None``.
    """

    assignments: dict[Occurrence, str | None] = field(default_factory=dict)
    new_entities: dict[str, NewEntity] = field(default_factory=dict)
    merges: list[dict[str, Any]] = field(default_factory=list)
    dropped: list[dict[str, Any]] = field(default_factory=list)
    failed: str | None = None


@dataclass
class _Cluster:
    key: str
    occurrences: list[Occurrence]
    names: list[str]
    forms: set[str]
    types: list[str]
    roles: list[str]
    claims: list[str]
    passages: list[str]
    group: int | None = None

    @property
    def type(self) -> str:
        return Counter(self.types).most_common(1)[0][0]

    @property
    def name(self) -> str:
        counts = Counter(self.names[: len(self.occurrences)])
        return max(self.names[: len(self.occurrences)], key=lambda n: counts[n])


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: int, b: int) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self.parent[max(root_a, root_b)] = min(root_a, root_b)


def _live_slug(cache: BibleCache, slug: str | None) -> str | None:
    seen: set[str] = set()
    while slug is not None and slug in cache.entities and slug not in seen:
        seen.add(slug)
        target = cache.entities[slug].merged_into
        if target is None:
            return slug
        slug = target
    return None


def _existing_index(cache: BibleCache) -> dict[str, str]:
    index: dict[str, str] = {}
    for form, slug in cache.resolution.items():
        live = _live_slug(cache, slug)
        if live is not None:
            index.setdefault(form, live)
    for entity in cache.live_entities():
        for name in (entity.name, *entity.aliases):
            index.setdefault(normalize_name(name), entity.slug)
    index.pop("", None)
    return index


def _unique(names: Sequence[str], exclude: str) -> tuple[str, ...]:
    seen = {normalize_name(exclude)}
    kept = []
    for name in names:
        key = normalize_name(name)
        if key and key not in seen:
            seen.add(key)
            kept.append(name)
    return tuple(kept)


def resolve(
    client: Completer,
    extractions: Sequence[PassageExtraction],
    cache: BibleCache | None,
    overrides: Overrides,
) -> Resolution:
    """Resolve every extracted entity to an existing or new entity, or to nothing.

    Args:
        client: The completer (called at most twice: one call and one re-attempt).
        extractions: This run's successful extractions.
        cache: The cache the run started from, or ``None``.
        overrides: The parsed ``story-overrides.txt``.

    Returns:
        The resolution.

    Raises:
        LLMRunHalted: The client will make no more calls; the run must stop.
    """
    cache = cache or BibleCache()
    out = Resolution()
    blocked = {normalize_name(n.phrase) for n in overrides.not_entities}
    groups: dict[str, int] = {}
    for number, alias in enumerate(overrides.aliases):
        for name in (alias.canonical, *alias.aliases):
            groups.setdefault(normalize_name(name), number)

    occurrences: list[Occurrence] = []
    forms: list[set[str]] = []
    for extraction in extractions:
        for index, entity in enumerate(extraction.entities):
            occurrence = (extraction.passage.name, index)
            names = {normalize_name(n) for n in (entity.name, *entity.aliases)} - {""}
            if entity.type == "world":
                out.assignments[occurrence] = WORLD_SLUG
                continue
            if names & blocked:
                out.assignments[occurrence] = None
                continue
            occurrences.append(occurrence)
            forms.append(names)

    union = _UnionFind(len(occurrences))
    owner: dict[str, int] = {}
    for position, names in enumerate(forms):
        group_keys = {f"group:{groups[n]}" for n in names if n in groups}
        for key in names | group_keys:
            if key in owner:
                union.union(owner[key], position)
            else:
                owner[key] = position

    by_passage = {extraction.passage.name: extraction for extraction in extractions}
    clusters: dict[int, _Cluster] = {}
    for position, occurrence in enumerate(occurrences):
        root = union.find(position)
        entity = by_passage[occurrence[0]].entities[occurrence[1]]
        cluster = clusters.setdefault(
            root, _Cluster("", [], [], set(), [], [], [], [])
        )
        cluster.occurrences.append(occurrence)
        cluster.names.insert(len(cluster.occurrences) - 1, entity.name)
        cluster.names.extend(entity.aliases)
        cluster.forms |= forms[position]
        cluster.types.append(entity.type)
        cluster.roles += [entity.role] if entity.role else []
        cluster.claims += [fact.claim for fact in entity.facts]
        if occurrence[0] not in cluster.passages:
            cluster.passages.append(occurrence[0])
        hits = sorted({groups[n] for n in forms[position] if n in groups})
        if hits and cluster.group is None:
            cluster.group = hits[0]

    existing = _existing_index(cache)
    taken = set(cache.entities) | {WORLD_SLUG}
    counter = 0

    def next_key() -> str:
        nonlocal counter
        counter += 1
        while f"k{counter}" in taken:
            counter += 1
        return f"k{counter}"

    if WORLD_SLUG in out.assignments.values() and _live_slug(cache, WORLD_SLUG) is None:
        out.new_entities[WORLD_SLUG] = NewEntity(WORLD_SLUG, "World", "world", (), None)

    unmatched: list[_Cluster] = []
    for cluster in clusters.values():
        target: str | None = None
        if cluster.group is not None:
            alias = overrides.aliases[cluster.group]
            group_forms = [normalize_name(n) for n in (alias.canonical, *alias.aliases)]
            target = next((existing[f] for f in group_forms if f in existing), None)
            if target is None:
                target = next((existing[f] for f in sorted(cluster.forms) if f in existing), None)
            if target is None:
                cluster.key = next_key()
                out.new_entities[cluster.key] = NewEntity(
                    cluster.key,
                    alias.canonical,
                    cluster.type,
                    _unique([*alias.aliases, *cluster.names], alias.canonical),
                    cluster.roles[0] if cluster.roles else None,
                )
                target = cluster.key
        else:
            ordered = [normalize_name(n) for n in cluster.names]
            target = next((existing[f] for f in ordered if f in existing), None)
        if target is None:
            cluster.key = next_key()
            unmatched.append(cluster)
            continue
        for occurrence in cluster.occurrences:
            out.assignments[occurrence] = target

    if not unmatched:
        return out
    answer = _call(client, unmatched, cache, overrides, out)
    targets = {cluster.key: cluster.key for cluster in unmatched}
    if answer is not None:
        _apply(answer, unmatched, cache, targets, out)
    by_key = {cluster.key: cluster for cluster in unmatched}
    absorbed: dict[str, list[str]] = {}
    for key, target in targets.items():
        if target is not None and target != key and target in by_key:
            absorbed.setdefault(target, []).extend(by_key[key].names)
    for cluster in unmatched:
        target = targets[cluster.key]
        for occurrence in cluster.occurrences:
            out.assignments[occurrence] = target
        if target == cluster.key:
            out.new_entities[cluster.key] = NewEntity(
                cluster.key,
                cluster.name,
                cluster.type,
                _unique([*cluster.names, *absorbed.get(cluster.key, [])], cluster.name),
                cluster.roles[0] if cluster.roles else None,
                pending=out.failed is not None,
            )
    return out


def _call(
    client: Completer,
    unmatched: Sequence[_Cluster],
    cache: BibleCache,
    overrides: Overrides,
    out: Resolution,
) -> dict[str, Any] | None:
    prompt = render_prompt(
        PROMPT,
        clusters=[
            {
                "key": cluster.key,
                "type": cluster.type,
                "names": list(_unique(cluster.names, "")),
                "sample_claims": cluster.claims[:SAMPLE_CLAIMS],
                "passages": cluster.passages,
            }
            for cluster in unmatched
        ],
        existing=[
            {"key": e.slug, "type": e.type, "names": [e.name, *e.aliases]}
            for e in cache.live_entities()
            if e.slug != WORLD_SLUG
        ],
        not_entities=[n.phrase for n in overrides.not_entities],
    )
    last: LLMError | None = None
    for _attempt in range(2):
        try:
            result = client.complete(
                system=prompt.system,
                user=prompt.user,
                schema=prompt_schema(PROMPT),
                reasoning_effort=REASONING_EFFORT,
                tag=RESOLVE_TAG,
            )
        except LLMRunHalted:
            raise
        except LLMError as exc:
            last = exc
            continue
        return result.data
    out.failed = f"{type(last).__name__}: {last} (after one re-attempt)"
    return None


def _apply(
    answer: dict[str, Any],
    unmatched: Sequence[_Cluster],
    cache: BibleCache,
    targets: dict[str, str | None],
    out: Resolution,
) -> None:
    by_key = {cluster.key: cluster for cluster in unmatched}
    live = {entity.slug: entity for entity in cache.live_entities()}
    used: set[str] = set()
    for drop in answer["drop"]:
        key = drop["key"]
        if key in by_key and key not in used:
            used.add(key)
            targets[key] = None
            out.dropped.append({"names": list(_unique(by_key[key].names, "")),
                                "reason": drop["reason"]})
    for merge in answer["merges"]:
        into, members = merge["into"], list(dict.fromkeys(merge["members"]))
        if merge["confidence"] != "high" or not members or into in members:
            continue
        if into not in by_key and into not in live:
            continue
        if any(member not in by_key for member in members):
            continue
        if used & {into, *members}:
            continue
        into_type = by_key[into].type if into in by_key else live[into].type
        if any(by_key[member].type != into_type for member in members):
            continue
        used |= {into, *members}
        for member in members:
            targets[member] = into
        out.merges.append(
            {"into": into, "members": [by_key[member].name for member in members]}
        )
