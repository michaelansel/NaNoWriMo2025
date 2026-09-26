# ADR-020: Story Bible v2: extract, resolve, reconcile, assemble, pack

## Status

Status: Accepted
Supersedes: ADR-010

## Context

The first Story Bible (ADR-010) extracted facts per path in a webhook, deduplicated by exact text, listed noise such as *no one* as characters, and produced hundreds of restated "setting" facts. The Continuity Editor needs a small, stable canon to check against, and writers need a page they trust and a way to correct it without editing JSON. The feature targets (`features/story-bible.md`) are measured on the eval story: 8/8 cast, at least 20 of 25 facts, no distractor entities, no scene-state facts, 5 of 6 pronouns plus both ambiguous cases, both real conflicts, and the intentional one kept apart. A full extraction of 100 passages must cost at most $1 at the default profile's prices, inside the $10 monthly cap (ADR-023). It must ship by Oct 25 and run unattended in November.

## Decision

`nanoif/bible/` builds the bible in four stages. Only three calls go to a model, all through `LLMClient` (ADR-016, ADR-023), and the model never writes text that code does not verify.

### Stages

1. **Extract** (model, one call per passage, `bible_extract`, `reasoning_effort=low`, `max_tokens=12000`). Only passages whose `content_hash` differs from the cache are sent. Input: passage name and text, plus a roster of known entities (`name`, `type`, `aliases`) and the `not-entity:` phrases. Code then drops every fact whose `quote` is not a whitespace-normalized substring of the passage, every fact of kind `state`, and every entity whose normalized name starts with a quantifier or number word (`no`, `some`, `any`, `every`, `each`, `all`, `none`, digits, `one`..`twenty`). It counts what it drops per passage. Nothing dropped is silent.
2. **Resolve** (deterministic, then at most one model call per run, `bible_resolve`, `reasoning_effort=medium`). First, names are matched by exact `normalize_name` equality against `resolution` and extracted aliases. The remaining new names go to one batched call as clusters `{key, type, names, sample_claims<=2, passages}`, along with existing entities. The call returns `merges[{into, members, confidence}]` and `drop[{key, reason}]`. Code applies only `high` merges of the same type, with each key used at most once. `story-overrides.txt` wins over both steps.
3. **Reconcile** (model, only for entities touched in this run, batched to at most 8k input tokens per call, `bible_reconcile`, `reasoning_effort=medium`). Input per entity: `{slug, name, aliases, facts[{id, claim, passage}]}`. Output: `duplicates[[id,...]]` and `conflicts[{a, b, note}]`, by fact id only. Code checks that every id exists and belongs to that entity, that no id is in two duplicate groups, and that a conflict does not pair two duplicates. An entity whose result fails these checks keeps its facts unreconciled with `reconcile: "pending"` and is retried next run.
4. **Assemble** (deterministic, no model, on every build). Input: the cache, `story-overrides.txt`, and current passage hashes. Output: Cast, Places, Items, Groups, World rules (facts of kind `rule` from any entity), Conflicts, Intentional mysteries and Freshness. Overrides are applied here, so an override edit shows in the next preview without extraction.

**Deferred past Nov 1:** a per-entity model merge (`keep|reword|retire`), model rewording of facts, cross-entity semantic dedupe, and a data-branch fallback for the cache. A fact is reworded only when its passage changes and is re-extracted.

### Modules and prompts

| File | Public surface |
|---|---|
| `bible/source.py` | `bible_passages(repo) -> list[SourcePassage(name, file, text, content_hash)]` |
| `bible/extract.py` | `extract_passage(client, passage, roster, not_entities) -> PassageExtraction` |
| `bible/resolve.py` | `normalize_name(name)`, `resolve(client, extractions, cache, overrides) -> Resolution` |
| `bible/reconcile.py` | `reconcile(client, entities) -> dict[slug, ReconcileResult]` |
| `bible/ids.py` | `entity_slug`, `assign_fact_ids(entity, passage, facts, commit)`, `pin_fact_id` |
| `bible/cache.py` | `load_cache(path) -> BibleCache \| None`, `write_cache(path, cache)`, `diff_caches(old, new)` |
| `bible/assemble.py` | `assemble(cache, overrides, current_hashes) -> Bible` (the page's and the pack's only input) |
| `bible/canon.py` | `CanonFact`, `build_canon_pack(bible)`, `load_canon_pack(path)`, `select_canon(pack, name, text, current_hashes) -> CanonSlice` |
| `bible/run.py` | `extract_bible(repo, mode, client, cache_path, dry_run) -> ExtractOutcome` |

- `clean_quote` and `quote_found` move from `review/findings.py` to `twee/quotes.py`. That keeps one quote verifier and keeps imports one-way: `twee <- bible <- review`.
- The new errors `BibleError(NanoifError)` and `BibleCacheError(BuildError)` go in `errors.py`.
- `formats/story_bible/` keeps only rendering from `Bible`.
- Each prompt has a sibling `*.schema.json`, written first:
  - `bible_extract`: `{summary, entities[{name, type, aliases, role|null, facts[{claim, quote, kind}]}], references[{quote, pronoun, entity|null}]}`. `kind` includes `state`, so the model has somewhere to put scene state, and code drops it. `references` covers each third-person pronoun that refers to a named entity, or is ambiguous between two (`entity: null`), at most 20 per passage.
  - `bible_resolve`: `{merges[{into, members[], confidence: high|medium|low}], drop[{key, reason: generic|not_named}]}`.
  - `bible_reconcile`: `{entities[{slug, duplicates[[id]], conflicts[{a, b, note}]}]}`.
  - Few-shot examples use eval-story names.

### Overrides (one parser)

`nanoif/check/overrides.py` is the only parser of `story-overrides.txt`. It gains typed payloads, and `nanoif check structure` reports payload errors (ADR-018). The bible consumes the typed result and never re-parses the file.
- `alias: <canonical> = <alias>, <alias>...`. Matching is by `normalize_name` against an entity's name and aliases. The named entities merge under `<canonical>`.
- `not-entity: <phrase>`. An entity whose normalized name or alias equals the phrase is removed. The phrase is also given to the extract and resolve prompts.
- `pin: <entity> = <claim> | "<quote>" @ <passage>`. Fact id `<entity-slug>#pin-<first 8 hex of sha256(claim)>`. When the quote is not found in the passage, the fact is shown flagged `quote not found` and is still pinned.
- `intentional-conflict:` has two forms. `c-<id>` names a conflict id shown on the page. `<label> = <entity> | <quote fragment>` names a mystery. It is listed under Intentional mysteries with its label. Any detected conflict on that entity with a quote containing the fragment moves there, and canon findings on those facts are suppressed. A line that matches nothing has no effect and is listed on the page as `unmatched`. The eval fixture uses the second form: `c-widow-never-wife = Widow Kestle | never anyone's wife`.

### Cache v2: `ai/story-bible-cache.json`, schema `story_bible_cache`

The cache is JSON with sorted keys, 2-space indent and a trailing newline. It is validated when written and when read, and written atomically (temp file + rename). Only `bible-extract` commits it.

```
version: 2
extraction: {commit, extracted_at (ISO 8601 UTC), mode: incremental|full, profile, model,
             prompt_hashes: {bible_extract, bible_resolve, bible_reconcile} (sha256[:12]),
             usd: number|null, usd_known: bool}
passages: {<passage name>: {content_hash, file, summary, mentions: [slug],
             references: [{quote, pronoun, entity: slug|null}], fact_ids: [id],
             dropped: {unverified_quote: int, state: int, generic_entity: int}}}
entities: {<slug>: {slug, name, type: character|location|item|group|world, aliases: [str],
             role: str|null, passages: [name], next_n: int, reconcile: done|pending,
             merged_into: slug|null,
             facts: [{id, claim, quote, passage, kind, duplicate_of: id|null}],
             retired: [{id, claim, passage, retired_commit, reason:
                        passage_changed|passage_deleted|not_entity|merged}]}}
resolution: {<normalized name>: slug}
conflicts: {<c-slug-n>: {id, entity, fact_ids: [a, b], note, status: open|retired}}
```

- **Ids.** An entity slug is `slug(name)` at creation, `-2`, `-3`... on collision, and never changes. A fact id is `<slug>#<n>` with `n = next_n++` and is never reused. A conflict id is `c-<slug>-<n>`. On re-extraction of a changed passage, a new fact keeps the id of the live fact from the same passage and entity when the normalized quote is equal, or else when the claim token overlap is at least 0.6 (a reworded fact keeps its id). Otherwise it gets a new id. Live facts from that passage that nothing matched move to `retired`. A merged entity keeps its facts' ids, and the absorbed slug stays with `merged_into`.
- **World rules.** `kind` is one of `trait|relationship|location|possession|event|rule` (`state` is never stored). The reserved slug `world` holds rules with no other entity.
- **Invalid cache.** A cache that exists but is unreadable, is not `version: 2`, fails the schema, or has a dangling reference raises `BibleCacheError(BuildError)`. A dangling reference is a `fact_ids`, `duplicate_of`, conflict or `merged_into` value that points nowhere. The build fails and writes no page over the last good one; extraction fails and writes nothing. A missing cache renders the placeholder. The root `story-bible-cache.json` (v1) and the v1 renderer code are deleted, and there is no migration. Recovery from a bad commit is `git revert`.

### Canon pack: `dist/canon-pack.json`, schema `canon_pack`

`nanoif build canon-pack` (part of `build all`) builds it from the assembled bible, with no model:
`{version: 1, source: {commit, extracted_at, cache_present}, passages: {<name>: content_hash}, entities: [{slug, name, type, aliases, facts: [{id, claim, quote, passage, pinned}]}], conflicts: [{id, fact_ids, intentional}], alias_index: {<normalized form>: slug}}`.
- Each entity has at most 6 facts: pinned first, then by evidence count (1 + facts that are `duplicate_of` it), then newest `n`. Duplicates, retired facts and `state` are excluded. Alias forms are at least 3 characters, and there are no pronouns.
- **Retrieval** (`select_canon`) is a case-insensitive, word-boundary, longest-first match of `alias_index` over the passage under review, with entities ordered by first mention. It excludes facts from the passage under review and facts whose source passage's current hash differs from `passages` (stale), and counts both. The cap is 40 facts per unit, and pinned facts of a mentioned entity are exempt (AC-story-bible-21).
- **Consumption.** `CanonFact` moves to `nanoif/bible/canon.py` and gains `quote`. The runner passes each continuity unit its slice, and the prompt's existing `[B]` block renders `{id, entity, claim, passage_id}` without the quote. The reporter re-attaches `quote` as the second quote of a canon finding. Findings on a fact in an intentional conflict go to `suppressed` with reason `intentional-conflict:<id or label>` (ADR-022).
- **Status is always stated.** `ai-review.json` gains the optional `canon: {status: used|no_cache, extracted_at, commit, facts_offered, stale_excluded, passages_not_in_bible: [name]}`, and the Continuity header states it. A pack with `cache_present: false` means path-only review, and the header says so. A missing or invalid pack file is an error, never an empty canon.

### CLI

`nanoif bible extract --repo . [--incremental | --full] [--dry-run] [--cache PATH] [--diff-out PATH]`. It reads `src/` through `nanoif.twee.parse` (no build artifacts, no tweego), uses the `nanoif.twee` passage hash, and excludes infrastructure passages.
- Before planning it calls `check_spend(<pessimistic estimate>)`. It makes no model call when no hash changed ("up to date"). `--full` re-extracts every passage but keeps ids through matching. It writes the cache only when the set of `(passage, content_hash)` changed.
- Every run writes `dist/bible-diff.json` (schema `bible_diff`: `{base, passages_read, passages_failed, entities{added, removed, changed}, facts{added, reworded, retired}, conflicts{added, retired}, usage}`) and prints one summary line with the USD cost.
- `--dry-run` writes only the diff, never `ai/`.
- Exit codes: `0` ok; `1` error, nothing written (typed error, invalid cache, `LLMRunHalted`, per ADR-023); `2` usage; `3` partial. On exit 3 the passages that failed after one re-attempt are left unrecorded, and entities whose resolve or reconcile failed are left `pending`. The cache is written, and those passages are listed in the diff and in Freshness.
- `nanoif build story-bible` reads v2 through `assemble` and accepts `--extraction-result success|failure|cancelled|skipped`. When the value is not `success`, the page states that the latest extraction did not complete and gives the date of the one shown. Freshness lists every passage whose hash is missing from the cache or differs, and cache passages that no longer exist. The Build comment states the count.
- `nanoif ai eval` runs `--full` extraction on the scratch eval repo with the fixture overrides, then reviews with the resulting canon pack. It scores `entities`, `facts`, `pronouns` (from `references`) and `conflicts` (bible conflicts). Review-derived conflicts move to a separate `review_conflicts` section. `EXTRACTION_SKIPPED` is deleted. An extraction halt marks those sections skipped with the reason, and the eval exits non-zero. `normalize_name` in `nanoif/bible/` and the scorer's own normalizer stay separate on purpose, so the judge is independent.

### Workflows

- `probe` also runs on `push` to `main` and on `workflow_dispatch`.
- `bible-extract` has `needs: [build, probe]` and runs on push or dispatch to `main`, never on `pull_request`. It uses `runs-on` from the probe, `timeout-minutes: 45`, `permissions: contents: write`, and the `pages` concurrency group, and it has no `vars.BIBLE_EXTRACT` gate.
  - On `hosted` it makes no model call: it writes `::error::` and a step-summary line with the reason, then exits 1.
  - On `exe` it checks out `ref: main` (latest, so it includes earlier bot commits) and runs `nanoif bible extract --incremental`, or `--full` from the dispatch input `bible-mode`.
  - On exit 0 or 3 with a changed cache, it commits only `ai/story-bible-cache.json` to `main` as `chore: update story bible cache`. A rejected push runs `git pull --rebase` and retries once, else the job fails. Exit 3 fails the job after the push.
  - It uploads the cache as artifact `bible-cache`.
- `deploy` runs when the build succeeded, whatever the extraction result. It checks out `github.sha` and re-renders `story-bible.html`, `story-bible.json` and `canon-pack.json` into the site. It uses the `bible-cache` artifact when present, otherwise the checked-out cache, and passes `--extraction-result ${{ needs.bible-extract.result }}`. A `GITHUB_TOKEN` push starts no workflow, so this is the only place the new cache reaches Pages.
- `/extract-story-bible` (`ai-command.yml`, collaborator-gated, probe, exe) checks out `refs/pull/<N>/merge`, whose tree carries `main`'s cache. It runs `--incremental --dry-run` and posts the diff as the sticky comment `<!-- nano:bible -->` headed "dry run: nothing was saved". When the runner is unavailable or the run fails, the same comment says "did not run" with the reason, and the job fails. `contents: read`.
- `ai-maintenance.yml` has no extraction task, because only these three jobs may write to `main` (ADR-014).

### Cost (fireworks/gpt-oss-120b, $0.15 / $0.60 per M)

| Part of a full run (100 passages) | Expected cost | Worst case |
|---|---|---|
| Extract, 100 calls: about 4k input and 3k output tokens each | $0.06 in + $0.18 out | `max_tokens` 12k on every call: $0.78 |
| Resolve and reconcile: about 6 calls | about $0.03 | |
| One repair round on 20% of calls | +$0.05 | |
| **Total** | **about $0.32** | **about $0.85** |

A daily incremental run of about 5 passages costs under $0.03.

## Consequences

### Positive

- One entity per real character, a verbatim quote behind every fact, and conflicts shown, not merged away.
- Canon is data with history in git, rendered and packed without a model, and ids stay stable across merges.
- Every stage failure is named in the diff, the job, the page and the Continuity header. A partial run still saves what it paid for.

### Negative

- Duplicate facts are only marked, never rewritten, so the Cast still shows some restated facts until the per-entity merge ships.
- Stable ids and tombstones make the cache the hardest contract to change. v1 history is dropped.
- A persistently failing passage keeps `bible-extract` red every merge until someone looks. That is loud, not silent.
- The PR preview shows the Bible as of `main`. The PR's own passages feed canon only after merge.

## Alternatives Considered

1. **Per-entity model merge now** (the earlier draft): rewording and retiring through the model costs one call per touched entity and adds the hardest failure mode (index accounting). Marking duplicates by id meets the Nov 1 targets.
2. **Rebuild from scratch every merge**: fact ids would churn, so dismissals and conflicts could not reference them.
3. **Cache in the Actions cache or a data branch**: loses reviewable history. A data branch stays the fallback if `main` gets push protection.
4. **All-or-nothing writes on any failure**: one bad passage would freeze the whole Bible for the month.
5. **Share the scorer's normalizer**: the eval would agree with the bugs it is meant to catch.

## References

- ADR-010 (superseded), ADR-014, ADR-016, ADR-018, ADR-022, ADR-023
- `features/story-bible.md`, `features/continuity-review.md`, `nanoif/check/overrides.py`, `tests/fixtures/eval-story/truth.json`
