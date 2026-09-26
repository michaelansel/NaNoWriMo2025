"""``nanoif bible extract``: one extraction run from ``src/`` to the cache and the diff.

Order of work (ADR-020):

1. Read ``src/``, ``story-overrides.txt`` and the cache (an invalid cache stops the run).
2. Plan: ``incremental`` sends passages whose hash differs from the cache; ``full`` sends
   every passage. Deleted passages need no call. With nothing to do the run is
   ``up_to_date`` and calls no model.
3. ``check_spend`` with a pessimistic estimate before any call.
4. Extract (one re-attempt per passage), resolve, reconcile.
5. Save the cache only when the set of ``(passage, content_hash)`` changed and this is not a
   dry run; always write the diff.

An :class:`~nanoif.llm.errors.LLMRunHalted` anywhere stops the run with nothing written.
A passage that fails twice is left unrecorded, an entity whose resolve or reconcile failed
stays pending, and the run is ``partial`` (exit 3) but still saves what it paid for.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nanoif.bible.cache import (
    BibleCache,
    Conflict,
    Entity,
    Extraction,
    PassageRecord,
    Reference,
    diff_caches,
    load_cache,
    write_cache,
)
from nanoif.bible.extract import (
    EXTRACT_MAX_TOKENS,
    PassageExtraction,
    RosterEntry,
    extract_passage,
)
from nanoif.bible.extract import (
    PROMPT as EXTRACT_PROMPT,
)
from nanoif.bible.ids import (
    WORLD_SLUG,
    assign_fact_ids,
    conflict_id,
    entity_slug,
    fact_number,
    normalize_name,
    retire_passage_facts,
)
from nanoif.bible.reconcile import MAX_INPUT_TOKENS, reconcile
from nanoif.bible.resolve import Resolution, resolve
from nanoif.bible.source import SourcePassage, bible_passages
from nanoif.check.overrides import Overrides, read_overrides
from nanoif.errors import BibleError
from nanoif.git.service import GitService
from nanoif.llm.client import DEFAULT_MAX_TOKENS, Completer
from nanoif.llm.errors import LLMError, LLMRunHalted
from nanoif.llm.pricing import cap_rate, cap_usd
from nanoif.llm.profiles import DEFAULT_MAX_CONCURRENCY
from nanoif.llm.prompts import prompt_hash, render_prompt
from nanoif.schemas.artifacts import write_artifact

MODES = ("incremental", "full")
EXIT_OK = 0
EXIT_PARTIAL = 3
PROMPTS = ("bible_extract", "bible_resolve", "bible_reconcile")
PASSAGES_PER_RECONCILE_CALL = 10


@dataclass(frozen=True)
class ExtractOutcome:
    """What an extraction run did.

    Attributes:
        status: ``ok``, ``partial`` or ``up_to_date``.
        exit_code: ``0``, or ``3`` when partial.
        cache_written: Whether the cache file was written.
        diff: The ``bible_diff`` artifact.
        summary: One line for the log and the step summary, with the cost.
    """

    status: str
    exit_code: int
    cache_written: bool
    diff: dict[str, Any]
    summary: str


@dataclass
class _Run:
    failures: dict[str, str] = field(default_factory=dict)
    pending: dict[str, str] = field(default_factory=dict)
    touched: set[str] = field(default_factory=set)


class _Halt:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.error: LLMRunHalted | None = None

    def set(self, error: LLMRunHalted) -> None:
        with self._lock:
            if self.error is None:
                self.error = error


def _roster(cache: BibleCache | None, overrides: Overrides) -> list[RosterEntry]:
    roster = []
    known: set[str] = set()
    for entity in cache.live_entities() if cache else []:
        if entity.slug == WORLD_SLUG:
            continue
        roster.append(RosterEntry(entity.name, entity.type, tuple(entity.aliases)))
        known |= {normalize_name(n) for n in (entity.name, *entity.aliases)}
    for alias in overrides.aliases:
        if normalize_name(alias.canonical) not in known:
            roster.append(RosterEntry(alias.canonical, "character", alias.aliases))
    return roster


def estimate_usd(client: Completer, plan: Sequence[SourcePassage], roster_size: int) -> float:
    """Return the pessimistic cost of a run, for ``check_spend``.

    Every extract call is charged its prompt estimate plus the full ``max_tokens``; one
    resolve call and one reconcile call per :data:`PASSAGES_PER_RECONCILE_CALL` passages
    are charged a full input budget and the default ``max_tokens``.

    Args:
        client: The completer (its model and profile pick the rate).
        plan: Passages to extract.
        roster_size: Entities in the roster sent with each passage.

    Returns:
        Estimated USD at the monthly cap's rate (the unpriced rate for unknown models).
    """
    settings = getattr(client, "settings", None)
    summary = client.usage_summary()
    model = getattr(settings, "model", None) or str(summary.get("model") or "")
    profile = getattr(settings, "profile", None) or str(summary.get("profile") or "")
    rate, _known = cap_rate(model, profile)
    overhead = render_prompt(EXTRACT_PROMPT, passage_name="", passage_text="", roster=[],
                             not_entities=[])
    base = (len(overhead.system) + len(overhead.user)) // 4 + 1 + roster_size * 12
    total = sum(cap_usd(rate, base + len(p.text) // 4, EXTRACT_MAX_TOKENS) for p in plan)
    calls = 1 + -(-len(plan) // PASSAGES_PER_RECONCILE_CALL)
    return total + calls * cap_usd(rate, MAX_INPUT_TOKENS, DEFAULT_MAX_TOKENS)


def _extract_all(
    client: Completer,
    plan: Sequence[SourcePassage],
    roster: Sequence[RosterEntry],
    not_entities: Sequence[str],
    workers: int,
    run: _Run,
) -> dict[str, PassageExtraction]:
    halt = _Halt()

    def one(passage: SourcePassage) -> PassageExtraction | None:
        last: LLMError | None = None
        for _attempt in range(2):
            if halt.error is not None:
                return None
            try:
                return extract_passage(client, passage, roster, not_entities)
            except LLMRunHalted as exc:
                halt.set(exc)
                return None
            except LLMError as exc:
                last = exc
        run.failures[passage.name] = f"{type(last).__name__}: {last} (after one re-attempt)"
        return None

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(one, plan))
    if halt.error is not None:
        raise halt.error
    return {r.passage.name: r for r in results if r is not None}


def _create_entities(cache: BibleCache, resolution: Resolution, run: _Run) -> dict[str, str]:
    slugs: dict[str, str] = {}
    for key, new in resolution.new_entities.items():
        if key == WORLD_SLUG:
            slug = WORLD_SLUG
        else:
            slug = entity_slug(new.name, cache.entities)
        cache.entities[slug] = Entity(
            slug=slug, name=new.name, type=new.type, aliases=list(new.aliases), role=new.role,
            reconcile="pending" if new.pending else "done",
        )
        if new.pending:
            run.pending[slug] = f"resolve failed: {resolution.failed}"
        slugs[key] = slug
        run.touched.add(slug)
    return slugs


def _add_aliases(entity: Entity, names: Sequence[str]) -> None:
    seen = {normalize_name(entity.name)} | {normalize_name(a) for a in entity.aliases}
    for name in names:
        key = normalize_name(name)
        if key and key not in seen:
            seen.add(key)
            entity.aliases.append(name)


def _apply_passage(
    cache: BibleCache,
    extraction: PassageExtraction,
    targets: Mapping[int, str | None],
    commit: str,
    run: _Run,
) -> None:
    name = extraction.passage.name
    by_slug: dict[str, list[Any]] = {}
    local: dict[str, str] = {}
    for index, entity in enumerate(extraction.entities):
        slug = targets.get(index)
        if slug is None:
            continue
        by_slug.setdefault(slug, []).extend(entity.facts)
        target = cache.entities[slug]
        _add_aliases(target, [entity.name, *entity.aliases])
        target.role = target.role or entity.role
        for form in {normalize_name(n) for n in (entity.name, *entity.aliases)} - {""}:
            cache.resolution.setdefault(form, slug)
            local[form] = slug
    holders = {e.slug for e in cache.entities.values() if any(f.passage == name for f in e.facts)}
    for slug in sorted(set(by_slug) | holders):
        entity = cache.entities[slug]
        result = assign_fact_ids(entity, name, by_slug.get(slug, []), commit)
        if result.added or result.reworded or result.retired:
            run.touched.add(slug)
    mentions = sorted(by_slug)
    for entity in cache.entities.values():
        if entity.slug in by_slug and name not in entity.passages:
            entity.passages = sorted([*entity.passages, name])
        elif entity.slug not in by_slug and name in entity.passages:
            entity.passages.remove(name)
    references = []
    for ref in extraction.references:
        key = normalize_name(ref.entity) if ref.entity else ""
        slug = (local.get(key) or cache.resolution.get(key)) if key else None
        known = slug if slug in cache.entities else None
        references.append(Reference(ref.quote, ref.pronoun, known))
    cache.passages[name] = PassageRecord(
        content_hash=extraction.passage.content_hash,
        file=extraction.passage.file,
        summary=extraction.summary,
        mentions=mentions,
        references=references,
        fact_ids=[f.id for e in cache.entities.values() for f in e.facts if f.passage == name],
        dropped=extraction.dropped,
    )


def _retire_conflicts(cache: BibleCache) -> None:
    live = cache.live_fact_ids()
    for conflict in cache.conflicts.values():
        if conflict.status == "open" and not all(fid in live for fid in conflict.fact_ids):
            conflict.status = "retired"


def _reconcile(client: Completer, cache: BibleCache, run: _Run) -> None:
    wanted = sorted(
        slug for slug, entity in cache.entities.items()
        if entity.merged_into is None and (slug in run.touched or entity.reconcile == "pending")
    )
    results = reconcile(client, [cache.entities[slug] for slug in wanted])
    for slug, result in results.items():
        entity = cache.entities[slug]
        if not result.ok:
            entity.reconcile = "pending"
            run.pending[slug] = f"reconcile failed: {result.error}"
            continue
        if slug not in run.pending:
            entity.reconcile = "done"
        representative: dict[str, str] = {}
        for group in result.duplicates:
            head = min(group, key=fact_number)
            representative.update({fid: head for fid in group if fid != head})
        for fact in entity.facts:
            fact.duplicate_of = representative.get(fact.id)
        for a, b, note in result.conflicts:
            pair = {a, b}
            open_pairs = [set(c.fact_ids) for c in cache.conflicts.values() if c.status == "open"]
            if pair in open_pairs:
                continue
            cid = conflict_id(slug, cache.conflicts)
            ordered = sorted(pair, key=fact_number)
            cache.conflicts[cid] = Conflict(cid, slug, ordered, note or "These facts disagree.")


def _passage_set(cache: BibleCache | None) -> set[tuple[str, str]]:
    if cache is None:
        return set()
    return {(name, record.content_hash) for name, record in cache.passages.items()}


def _summary(status: str, diff: Mapping[str, Any]) -> str:
    usage = diff["usage"]
    cost = f"${usage['usd']:.4f}" + ("" if usage["usd_known"] else " (cost unknown)")
    if diff["cache_written"]:
        saved = "cache saved"
    elif diff["dry_run"]:
        saved = "dry run, nothing saved"
    else:
        saved = "cache unchanged, not saved"
    facts, entities, conflicts = diff["facts"], diff["entities"], diff["conflicts"]
    return (
        f"bible extract {diff['mode']}: {status}; {len(diff['passages_read'])} passage(s) read, "
        f"{len(diff['passages_failed'])} failed, {len(diff['passages_deleted'])} deleted; "
        f"entities +{len(entities['added'])} -{len(entities['removed'])} "
        f"~{len(entities['changed'])}; facts +{len(facts['added'])} "
        f"~{len(facts['reworded'])} -{len(facts['retired'])}; conflicts "
        f"+{len(conflicts['added'])} -{len(conflicts['retired'])}; "
        f"{len(diff['pending'])} pending; {saved}; {usage['calls']} call(s), {cost}"
    )


def extract_bible(
    repo: Path,
    mode: str,
    client: Completer,
    cache_path: Path,
    dry_run: bool,
    *,
    diff_out: Path | None = None,
    overrides_path: Path | None = None,
    now: datetime | None = None,
    max_workers: int | None = None,
) -> ExtractOutcome:
    """Run one extraction.

    Args:
        repo: Repository root (a git checkout with ``src/``).
        mode: ``incremental`` or ``full``.
        client: The completer.
        cache_path: ``ai/story-bible-cache.json``.
        dry_run: Write only the diff, never the cache.
        diff_out: Where the diff goes; defaults to ``<repo>/dist/bible-diff.json``.
        overrides_path: Defaults to ``<repo>/story-overrides.txt``.
        now: Timestamp for ``extracted_at``.
        max_workers: Concurrent extract calls; defaults to the client's ``max_concurrency``.

    Returns:
        The outcome; the diff file is written.

    Raises:
        BibleError: Unknown mode, or no ``src/``.
        BibleCacheError: The cache exists but is invalid; nothing is written.
        LLMRunHalted: The spend cap, token budget or ledger stopped the run; nothing is
            written.
        GitError: ``HEAD`` cannot be resolved.
    """
    if mode not in MODES:
        raise BibleError(f"unknown extraction mode {mode!r}; expected one of {MODES}")
    repo = Path(repo)
    sources = bible_passages(repo)
    overrides = read_overrides(overrides_path or repo / "story-overrides.txt")
    old = load_cache(cache_path)
    current = {p.name: p for p in sources}
    if mode == "full" or old is None:
        plan = list(sources)
    else:
        plan = [
            p for p in sources
            if p.name not in old.passages or old.passages[p.name].content_hash != p.content_hash
        ]
    deleted = sorted(n for n in (old.passages if old else {}) if n not in current)
    base = (
        {"commit": old.extraction.commit, "extracted_at": old.extraction.extracted_at}
        if old is not None and old.extraction is not None
        else None
    )
    run = _Run()
    new = copy.deepcopy(old) if old is not None else BibleCache()
    status = "up_to_date"
    if plan or deleted:
        roster = _roster(old, overrides)
        not_entities = [line.phrase for line in overrides.not_entities]
        if plan:
            client.check_spend(estimate_usd(client, plan, len(roster)))
        settings = getattr(client, "settings", None)
        workers = max_workers or getattr(settings, "max_concurrency", None)
        extractions = _extract_all(
            client, plan, roster, not_entities, workers or DEFAULT_MAX_CONCURRENCY, run
        )
        commit = GitService(repo).rev_parse("HEAD")
        ordered = [extractions[name] for name in sorted(extractions)]
        resolution = resolve(client, ordered, new, overrides)
        slugs = _create_entities(new, resolution, run)
        for extraction in ordered:
            name = extraction.passage.name
            targets = {}
            for (passage, index), key in resolution.assignments.items():
                if passage == name:
                    targets[index] = slugs.get(key, key) if key is not None else None
            _apply_passage(new, extraction, targets, commit, run)
        for name in deleted:
            for entity in new.entities.values():
                if retire_passage_facts(entity, name, commit, "passage_deleted"):
                    run.touched.add(entity.slug)
                if name in entity.passages:
                    entity.passages.remove(name)
            del new.passages[name]
        _retire_conflicts(new)
        _reconcile(client, new, run)
        usage = client.usage_summary()
        new.extraction = Extraction(
            commit=commit,
            extracted_at=(now or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            mode=mode,
            profile=str(usage.get("profile") or "unknown"),
            model=str(usage.get("model") or "unknown"),
            prompt_hashes={name: prompt_hash(name) for name in PROMPTS},
            usd=float(usage["usd"]) if usage.get("usd_known") else None,
            usd_known=bool(usage.get("usd_known")),
        )
        status = "partial" if run.failures or run.pending else "ok"
    changed = _passage_set(new) != _passage_set(old)
    written = False
    if changed and not dry_run and status != "up_to_date":
        write_cache(cache_path, new)
        written = True
    diff = {
        "status": status,
        "mode": mode,
        "dry_run": dry_run,
        "cache_written": written,
        "base": base,
        "passages_read": sorted(n for n in current if n in {p.name for p in plan}
                                and n not in run.failures),
        "passages_failed": [{"passage": n, "reason": r} for n, r in sorted(run.failures.items())],
        "passages_deleted": deleted,
        "pending": [
            {"entity": new.entities[slug].name, "reason": reason}
            for slug, reason in sorted(run.pending.items(), key=lambda i: new.entities[i[0]].name)
        ],
        **diff_caches(old, new),
        "usage": client.usage_summary(),
    }
    write_artifact(diff_out or repo / "dist" / "bible-diff.json", diff, "bible_diff")
    return ExtractOutcome(
        status=status,
        exit_code=EXIT_PARTIAL if status == "partial" else EXIT_OK,
        cache_written=written,
        diff=diff,
        summary=_summary(status, diff),
    )
