"""``nanoif bible extract``: one extraction run from ``src/`` to the cache and the diff.

Order of work (ADR-020):

1. Read ``src/``, ``story-overrides.txt`` and the cache (an invalid cache stops the run).
2. Plan: ``incremental`` sends passages whose hash differs from the cache; ``full`` sends
   every passage. Deleted passages need no call. With nothing to do the run is
   ``up_to_date`` and calls no model.
3. Look each planned passage up in the extraction store (ADR-026), except with ``full``;
   a hit is filtered against the current text again and costs no call.
4. ``check_spend`` with a pessimistic estimate of the misses before any call.
5. Extract the misses (one re-attempt per passage) and save each answer to the store,
   then resolve and reconcile.
6. Save the cache only when the set of ``(passage, content_hash)`` changed and this is not a
   dry run; always write the diff.

A ``preview`` run (ADR-026) is an incremental dry run without reconcile: conflicts, final
ids and merges come only from ``main``. It writes the would-be cache to ``cache_out``,
never to ``ai/``, for the pull request's preview Story Bible.

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
    extract_answer,
    filter_extraction,
    store_key,
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
from nanoif.bible.store import ExtractStore, StoreKey, bypassed_report
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
NO_STORE = "no extraction store for this run"
FULL_BYPASS = "--full re-reads every passage: answers are saved to the store, never read from it"
MAX_NAMED_HITS = 10


@dataclass(frozen=True)
class ExtractOutcome:
    """What an extraction run did.

    Attributes:
        status: ``ok``, ``partial`` or ``up_to_date``.
        exit_code: ``0``, or ``3`` when partial.
        cache_written: Whether the cache file was written.
        diff: The ``bible_diff`` artifact.
        summary: One line for the log and the step summary, with the cost.
        warnings: Extraction store problems that cost money, not correctness.
        cache_out_written: Whether the would-be cache was written to ``cache_out``.
    """

    status: str
    exit_code: int
    cache_written: bool
    diff: dict[str, Any]
    summary: str
    warnings: tuple[str, ...] = ()
    cache_out_written: bool = False


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


def _identity(client: Completer) -> tuple[str, str]:
    """The completer's ``(profile, model)``, from its settings or its usage summary."""
    settings = getattr(client, "settings", None)
    summary = client.usage_summary()
    model = getattr(settings, "model", None) or str(summary.get("model") or "")
    profile = getattr(settings, "profile", None) or str(summary.get("profile") or "")
    return profile, model


def estimate_usd(
    client: Completer,
    plan: Sequence[SourcePassage],
    roster_size: int,
    *,
    planned: int | None = None,
) -> float:
    """Return the pessimistic cost of a run, for ``check_spend``.

    Every extract call is charged its prompt estimate plus the full ``max_tokens``; one
    resolve call and one reconcile call per :data:`PASSAGES_PER_RECONCILE_CALL` passages
    are charged a full input budget and the default ``max_tokens``.

    Args:
        client: The completer (its model and profile pick the rate).
        plan: Passages to extract with a model call (store hits are not among them).
        roster_size: Entities in the roster sent with each passage.
        planned: Passages the run reads in all, hits included, which size the reconcile
            calls; defaults to ``len(plan)``.

    Returns:
        Estimated USD at the monthly cap's rate (the unpriced rate for unknown models).
    """
    profile, model = _identity(client)
    rate, _known = cap_rate(model, profile)
    overhead = render_prompt(EXTRACT_PROMPT, passage_name="", passage_text="", roster=[],
                             not_entities=[])
    base = (len(overhead.system) + len(overhead.user)) // 4 + 1 + roster_size * 12
    total = sum(cap_usd(rate, base + len(p.text) // 4, EXTRACT_MAX_TOKENS) for p in plan)
    count = len(plan) if planned is None else planned
    calls = 1 + -(-count // PASSAGES_PER_RECONCILE_CALL)
    return total + calls * cap_usd(rate, MAX_INPUT_TOKENS, DEFAULT_MAX_TOKENS)


def _extract_all(
    client: Completer,
    plan: Sequence[SourcePassage],
    roster: Sequence[RosterEntry],
    not_entities: Sequence[str],
    workers: int,
    run: _Run,
    store: ExtractStore | None = None,
    keys: Mapping[str, StoreKey] | None = None,
) -> dict[str, PassageExtraction]:
    halt = _Halt()

    def one(passage: SourcePassage) -> PassageExtraction | None:
        last: LLMError | None = None
        for _attempt in range(2):
            if halt.error is not None:
                return None
            try:
                answer = extract_answer(client, passage, roster, not_entities)
                if store is not None and keys is not None:
                    store.save(keys[passage.name], answer)
                return filter_extraction(passage, answer)
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


def _store_summary(store: Mapping[str, Any]) -> str:
    if store["status"] != "used":
        return f"store {store['status']} ({store['reason']})"
    hits = store["hits"]
    named = ""
    if hits:
        more = f" and {len(hits) - MAX_NAMED_HITS} more" if len(hits) > MAX_NAMED_HITS else ""
        named = f" ({', '.join(hits[:MAX_NAMED_HITS])}{more})"
    return (
        f"store used: {len(hits)} hit(s){named}, {store['misses']} miss(es), "
        f"{store['invalid']} invalid, {store['write_failed']} write failed"
    )


def _summary(status: str, diff: Mapping[str, Any], preview: bool) -> str:
    usage = diff["usage"]
    cost = f"${usage['usd']:.4f}" + ("" if usage["usd_known"] else " (cost unknown)")
    if diff["cache_written"]:
        saved = "cache saved"
    elif preview:
        saved = "preview, not reconciled, nothing saved to ai/"
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
        f"{len(diff['pending'])} pending; {saved}; {_store_summary(diff['store'])}; "
        f"{usage['calls']} call(s), {cost}"
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
    store: ExtractStore | None = None,
    preview: bool = False,
    cache_out: Path | None = None,
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
        store: The extraction store (ADR-026). ``incremental`` reads and writes it,
            ``full`` only writes it; ``None`` (``nanoif ai eval``, library calls) neither
            reads nor writes one.
        preview: An incremental dry run that skips reconcile (ADR-026).
        cache_out: Where to write the would-be cache, validated as ``story_bible_cache``;
            never the saved cache. Nothing is written when there is no extraction at all.

    Returns:
        The outcome; the diff file is written.

    Raises:
        BibleError: Unknown mode, no ``src/``, a preview in ``full`` mode, or a
            ``cache_out`` that is the saved cache.
        BibleCacheError: The cache exists but is invalid; nothing is written.
        LLMRunHalted: The spend cap, token budget or ledger stopped the run; nothing is
            written.
        GitError: ``HEAD`` cannot be resolved.
    """
    if mode not in MODES:
        raise BibleError(f"unknown extraction mode {mode!r}; expected one of {MODES}")
    if preview and mode != "incremental":
        raise BibleError("a preview extraction is incremental; --full re-reads what main has")
    if cache_out is not None and cache_out.resolve() == Path(cache_path).resolve():
        raise BibleError(
            f"{cache_out} is the saved cache; a dry run or preview never writes ai/"
        )
    dry_run = dry_run or preview
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
        keys: dict[str, StoreKey] = {}
        reused: dict[str, PassageExtraction] = {}
        if store is not None and plan:
            profile, model = _identity(client)
            keys = {p.name: store_key(p, profile, model) for p in plan}
        if store is not None and mode != "full":
            for passage in plan:
                answer = store.lookup(keys[passage.name])
                if answer is not None:
                    reused[passage.name] = filter_extraction(passage, answer)
        misses = [p for p in plan if p.name not in reused]
        if plan:
            client.check_spend(estimate_usd(client, misses, len(roster), planned=len(plan)))
        settings = getattr(client, "settings", None)
        workers = max_workers or getattr(settings, "max_concurrency", None)
        extractions = _extract_all(
            client, misses, roster, not_entities, workers or DEFAULT_MAX_CONCURRENCY, run,
            store, keys,
        )
        extractions.update(reused)
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
        if not preview:
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
    cache_out_written = cache_out is not None and new.extraction is not None
    if cache_out is not None and cache_out_written:
        write_cache(cache_out, new)
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
        "store": (
            bypassed_report(NO_STORE) if store is None
            else store.report(read=mode != "full", reason=FULL_BYPASS)
        ),
    }
    write_artifact(diff_out or repo / "dist" / "bible-diff.json", diff, "bible_diff")
    return ExtractOutcome(
        status=status,
        exit_code=EXIT_PARTIAL if status == "partial" else EXIT_OK,
        cache_written=written,
        diff=diff,
        summary=_summary(status, diff, preview),
        warnings=tuple(store.warnings) if store is not None else (),
        cache_out_written=cache_out_written,
    )
