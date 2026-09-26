"""Cache v2, ``ai/story-bible-cache.json``: the model, load, atomic write, and diff (ADR-020).

The cache is the Story Bible's only persistent state. It is JSON with sorted keys, 2-space
indent and a trailing newline, validated against the ``story_bible_cache`` schema and
checked for dangling references both when written and when read, and written atomically
(temporary file, then rename). A cache that exists but is unusable raises
:class:`~nanoif.errors.BibleCacheError`; a missing cache is ``None``.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from nanoif.bible.ids import fact_number
from nanoif.errors import ArtifactValidationError, BibleCacheError
from nanoif.schemas.artifacts import validate_artifact

CACHE_VERSION = 2
SCHEMA = "story_bible_cache"


@dataclass
class Fact:
    """A live fact: a claim about one entity, quoted verbatim from one passage."""

    id: str
    claim: str
    quote: str
    passage: str
    kind: str
    duplicate_of: str | None = None


@dataclass
class RetiredFact:
    """A fact that is no longer live; its id is never reused."""

    id: str
    claim: str
    passage: str
    retired_commit: str
    reason: str


@dataclass
class Entity:
    """One character, location, item, group, or the reserved ``world``."""

    slug: str
    name: str
    type: str
    aliases: list[str] = field(default_factory=list)
    role: str | None = None
    passages: list[str] = field(default_factory=list)
    next_n: int = 1
    reconcile: str = "done"
    merged_into: str | None = None
    facts: list[Fact] = field(default_factory=list)
    retired: list[RetiredFact] = field(default_factory=list)

    def fact(self, fact_id: str) -> Fact | None:
        """Return the live fact with this id, or ``None``."""
        return next((fact for fact in self.facts if fact.id == fact_id), None)


@dataclass
class Reference:
    """A pronoun and the entity it refers to (``None`` when ambiguous)."""

    quote: str
    pronoun: str
    entity: str | None


@dataclass
class Dropped:
    """What extraction discarded from one passage, by reason."""

    unverified_quote: int = 0
    state: int = 0
    generic_entity: int = 0


@dataclass
class PassageRecord:
    """What the last successful extraction of a passage recorded."""

    content_hash: str
    file: str
    summary: str
    mentions: list[str] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    fact_ids: list[str] = field(default_factory=list)
    dropped: Dropped = field(default_factory=Dropped)


@dataclass
class Conflict:
    """Two facts of one entity that cannot both be true."""

    id: str
    entity: str
    fact_ids: list[str]
    note: str
    status: str = "open"


@dataclass
class Extraction:
    """Provenance of the extraction the cache holds."""

    commit: str
    extracted_at: str
    mode: str
    profile: str
    model: str
    prompt_hashes: dict[str, str]
    usd: float | None
    usd_known: bool


@dataclass
class BibleCache:
    """The whole cache.

    Attributes:
        extraction: Provenance; ``None`` only while a first run is building the cache.
        passages: Passage name to its record.
        entities: Slug to entity (merged entities stay, with ``merged_into``).
        resolution: Normalized name to slug.
        conflicts: Conflict id to conflict.
    """

    extraction: Extraction | None = None
    passages: dict[str, PassageRecord] = field(default_factory=dict)
    entities: dict[str, Entity] = field(default_factory=dict)
    resolution: dict[str, str] = field(default_factory=dict)
    conflicts: dict[str, Conflict] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BibleCache:
        """Build from a schema-valid cache dictionary.

        Args:
            data: The parsed JSON.

        Returns:
            The cache.
        """
        return cls(
            extraction=Extraction(**data["extraction"]),
            passages={
                name: PassageRecord(
                    content_hash=record["content_hash"],
                    file=record["file"],
                    summary=record["summary"],
                    mentions=list(record["mentions"]),
                    references=[Reference(**ref) for ref in record["references"]],
                    fact_ids=list(record["fact_ids"]),
                    dropped=Dropped(**record["dropped"]),
                )
                for name, record in data["passages"].items()
            },
            entities={
                slug: Entity(
                    slug=entity["slug"],
                    name=entity["name"],
                    type=entity["type"],
                    aliases=list(entity["aliases"]),
                    role=entity["role"],
                    passages=list(entity["passages"]),
                    next_n=entity["next_n"],
                    reconcile=entity["reconcile"],
                    merged_into=entity["merged_into"],
                    facts=[Fact(**fact) for fact in entity["facts"]],
                    retired=[RetiredFact(**fact) for fact in entity["retired"]],
                )
                for slug, entity in data["entities"].items()
            },
            resolution=dict(data["resolution"]),
            conflicts={cid: Conflict(**conflict) for cid, conflict in data["conflicts"].items()},
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize in the ``story_bible_cache`` shape."""
        return {
            "version": CACHE_VERSION,
            "extraction": asdict(self.extraction) if self.extraction is not None else None,
            "passages": {name: asdict(record) for name, record in self.passages.items()},
            "entities": {slug: asdict(entity) for slug, entity in self.entities.items()},
            "resolution": dict(self.resolution),
            "conflicts": {cid: asdict(conflict) for cid, conflict in self.conflicts.items()},
        }

    def live_entities(self) -> list[Entity]:
        """Entities not merged into another, in slug order."""
        return [self.entities[slug] for slug in sorted(self.entities)
                if self.entities[slug].merged_into is None]

    def live_fact_ids(self) -> dict[str, str]:
        """Every live fact id to the slug of the entity holding it."""
        return {fact.id: entity.slug for entity in self.entities.values() for fact in entity.facts}


def dangling_references(cache: BibleCache) -> list[str]:
    """List every reference in the cache that points nowhere.

    Checked: passage ``fact_ids`` and ``mentions``, reference entities, ``duplicate_of``
    (a live fact of the same entity), ``merged_into``, conflict entities and fact ids
    (live or retired facts of that entity), ``resolution`` values, and ``next_n`` above
    every fact number the entity has used.

    Args:
        cache: The cache.

    Returns:
        One line per problem; empty when the cache is consistent.
    """
    problems: list[str] = []
    live = cache.live_fact_ids()
    for name, record in cache.passages.items():
        problems += [f"passage {name!r} fact_ids: {fid}" for fid in record.fact_ids
                     if fid not in live]
        problems += [f"passage {name!r} mentions: {slug}" for slug in record.mentions
                     if slug not in cache.entities]
        problems += [f"passage {name!r} reference: {ref.entity}" for ref in record.references
                     if ref.entity is not None and ref.entity not in cache.entities]
    for slug, entity in cache.entities.items():
        own = {fact.id for fact in entity.facts}
        for fact in entity.facts:
            if fact.duplicate_of is not None and fact.duplicate_of not in own - {fact.id}:
                problems.append(f"entity {slug!r} fact {fact.id} duplicate_of: {fact.duplicate_of}")
        if entity.merged_into is not None and (
            entity.merged_into not in cache.entities or entity.merged_into == slug
        ):
            problems.append(f"entity {slug!r} merged_into: {entity.merged_into}")
        used = [fact_number(f.id) for f in [*entity.facts, *entity.retired]]
        if used and max(used) >= entity.next_n:
            problems.append(f"entity {slug!r} next_n {entity.next_n} is not above {max(used)}")
    for cid, conflict in cache.conflicts.items():
        entity = cache.entities.get(conflict.entity)
        if entity is None:
            problems.append(f"conflict {cid!r} entity: {conflict.entity}")
            continue
        known = {f.id for f in entity.facts} | {f.id for f in entity.retired}
        problems += [f"conflict {cid!r} fact_ids: {fid}" for fid in conflict.fact_ids
                     if fid not in known]
    problems += [f"resolution {name!r}: {slug}" for name, slug in cache.resolution.items()
                 if slug not in cache.entities]
    return problems


def _check(data: dict[str, Any], cache: BibleCache | None, path: Path) -> BibleCache:
    try:
        validate_artifact(data, SCHEMA)
    except ArtifactValidationError as exc:
        raise BibleCacheError(f"Story Bible cache {path} fails its schema: {exc}") from exc
    cache = cache or BibleCache.from_dict(data)
    problems = dangling_references(cache)
    if problems:
        more = f"; and {len(problems) - 5} more" if len(problems) > 5 else ""
        shown = "; ".join(problems[:5]) + more
        kind = "next_n" if all("next_n" in p for p in problems) else "dangling reference(s)"
        raise BibleCacheError(f"Story Bible cache {path} has {kind}: {shown}")
    return cache


def load_cache(path: Path) -> BibleCache | None:
    """Read and check the cache.

    Args:
        path: ``ai/story-bible-cache.json``.

    Returns:
        The cache, or ``None`` when the file does not exist.

    Raises:
        BibleCacheError: The file is unreadable, not JSON, not version 2, fails the
            schema, or has a dangling reference.
    """
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BibleCacheError(f"Story Bible cache {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
        raise BibleCacheError(f"Story Bible cache {path} is not version {CACHE_VERSION}")
    return _check(data, None, path)


def serialize(cache: BibleCache) -> str:
    """Return the cache's file text: sorted keys, 2-space indent, trailing newline."""
    return json.dumps(cache.to_dict(), indent=2, sort_keys=True) + "\n"


def write_cache(path: Path, cache: BibleCache) -> None:
    """Validate the cache and write it atomically.

    Args:
        path: Destination; its directory is created.
        cache: The cache.

    Raises:
        BibleCacheError: The cache fails its schema or has a dangling reference; the
            file on disk is left as it was.
    """
    data = cache.to_dict()
    _check(data, cache, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    )
    try:
        with handle:
            handle.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        os.replace(handle.name, path)
    except OSError:
        Path(handle.name).unlink(missing_ok=True)
        raise


def diff_caches(old: BibleCache | None, new: BibleCache) -> dict[str, dict[str, list[str]]]:
    """Say what changed between two caches.

    Args:
        old: The cache a run started from, or ``None``.
        new: The cache it produced.

    Returns:
        ``entities {added, removed, changed}``, ``facts {added, reworded, retired}`` and
        ``conflicts {added, retired}``, each a sorted list of slugs or ids.
    """
    old = old or BibleCache()
    old_live = {e.slug: e for e in old.live_entities()}
    new_live = {e.slug: e for e in new.live_entities()}
    old_facts = {f.id: f for e in old.entities.values() for f in e.facts}
    new_facts = {f.id: f for e in new.entities.values() for f in e.facts}
    new_retired = {f.id for e in new.entities.values() for f in e.retired}
    changed = [
        slug
        for slug in sorted(set(old_live) & set(new_live))
        if asdict(old_live[slug]) != asdict(new_live[slug])
    ]
    return {
        "entities": {
            "added": sorted(set(new_live) - set(old_live)),
            "removed": sorted(set(old_live) - set(new_live)),
            "changed": changed,
        },
        "facts": {
            "added": sorted(set(new_facts) - set(old_facts) - new_retired, key=_fact_order),
            "reworded": sorted(
                (fid for fid in set(old_facts) & set(new_facts)
                 if old_facts[fid].claim != new_facts[fid].claim),
                key=_fact_order,
            ),
            "retired": sorted(set(old_facts) & new_retired, key=_fact_order),
        },
        "conflicts": {
            "added": sorted(set(new.conflicts) - set(old.conflicts)),
            "retired": sorted(
                cid for cid, conflict in new.conflicts.items()
                if conflict.status == "retired"
                and (cid not in old.conflicts or old.conflicts[cid].status == "open")
            ),
        },
    }


def _fact_order(fact_id: str) -> tuple[str, int]:
    slug, _hash, _tail = fact_id.rpartition("#")
    return slug, fact_number(fact_id)
