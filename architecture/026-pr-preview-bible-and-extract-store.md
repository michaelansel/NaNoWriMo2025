# ADR-026: PR preview Story Bible and a shared stage-1 extraction store

Status: Accepted
Supersedes: ADR-020 in part (the PR preview shows the Bible as of `main`; every changed passage is re-sent to the model on `main`)

## Context

A PR preview's `story-bible.html` is `main`'s cache plus a freshness banner. The `features/story-bible.md` criteria AC-33 to AC-36 ask for more:
- The preview adds the PR's own passages.
- After merge, a passage whose text the PR already extracted is not sent to the model again.

Three constraints apply:
- There is one exe runner (`nano-runner`), and it runs one job at a time.
- The $10 monthly cap is shared with the AI review (ADR-023).
- The design must land by Oct 25 and run unattended.

## Decision

### Store (`nanoif/bible/store.py`, the only code that reads or writes it)

**Location.** `NANOIF_BIBLE_STORE_DIR`, default `$XDG_STATE_HOME/nanoif/extract-store` (`~/.local/state/...`). It is created if missing. It is never in the checkout, in git or under `ai/`.

**Entries.**
- **Path:** `<dir>/<key[:2]>/<key>.json`, with schema `extract_store_entry`.
- **Contents:** `{version: 1, key_fields, answer, created_at, run}`.
- **`answer`** is the raw, schema-valid `bible_extract` output.
- **`key`** is the SHA-256 of the canonical JSON of `key_fields`: `{passage_name, content_hash, prompt_hash, schema_hash, profile, model, reasoning_effort, max_tokens}`.
- **Left out of the key on purpose:** the roster and the `not-entity:` phrases (AC-story-bible-36).
  - Resolve on `main` realigns names.
  - Assemble removes not-entities.

**Read.** An entry is a hit only when all of these hold:
- the file parses;
- it validates;
- its `key_fields` equal the requested ones;
- `answer` validates against the current prompt schema.

On a hit, `filter_extraction` runs again, so every quote is verified against the current text.

Anything else is a miss, counted as `invalid`, with a `::warning::` that names the path. An unreadable directory makes every lookup a miss, with status `unavailable` and the reason.

**Write.** The entry goes to a temp file in the same directory and is then renamed into place. A failure is counted as `write_failed`, a warning is printed, and the run goes on.

**Errors.** Store problems never raise. The code catches only `OSError`, JSON errors and validation errors, never `Exception`. Losing the store means paying to extract again; it never fails a run.

**Who uses it.**

| Run | Reads | Writes |
|---|---|---|
| `bible extract` incremental, `--dry-run`, `--preview` | yes | yes |
| `bible extract --full` | no (`--full` exists to redo) | yes |
| `nanoif ai eval`, and library calls without a store | no | no |

**Spend.** Lookups happen before `check_spend`, and the estimate counts misses only. A hit makes no call and writes no ledger line: it costs $0.

**Reporting.** `bible_diff` gains the required key `store: {status: used|unavailable|bypassed, hits: [passage], misses, invalid, write_failed, reason}`. The one-line summary names the hits.

`story_bible_cache` does not change. Reuse is a property of the run, and a reused answer is by construction the answer that request was given.

**Size.** There is no eviction. An entry is about 10 KB, so a season stays under 100 MB. `new-year-reset` deletes the directory.

### Preview extraction

The command is `nanoif bible extract --preview --cache-out PATH`. It runs the same pipeline as the dry run:
- incremental;
- never writes `ai/`;
- extracts through the store, then resolves (deterministic, plus the one batched call);
- **no reconcile:** conflicts, final ids and merges come only from `main`;
- writes the would-be cache to `PATH`, validated as `story_bible_cache`, plus the diff.

`nanoif build story-bible --cache PATH --preview-passages dist/changes.json` renders the page:
- Facts from the PR's passages are marked "from this pull request (not merged)".
- The page says that ids and merged names may change, and that conflicts are found after merge.
- The `fact` definition in `story_bible` gains the optional `provisional`.

The preview never builds `canon-pack.json`.

`/extract-story-bible` keeps using this same CLI and store. Whether to retire it is the pm's call.

### Where it runs

The preview runs as steps in the `ai-review` job, after the review has published. It is not a second exe job, because a second job per push would queue behind reviews on the single runner. Running after the review also gives the review first claim on the monthly budget.

The steps, in order:
1. Base-branch tooling in its own venv. `src/`, `story-overrides.txt` and `ai/story-bible-cache.json` come from the merge ref, after checking that its second parent is the head.
2. Extract, with `timeout-minutes: 10` and the exit code captured.
3. Upload the `story-bible-preview` artifact.
4. Report, with `!cancelled()`: the `<!-- nano:bible -->` comment for the head sha and a `Story Bible preview` check run.

The `story-preview` artifact is never overwritten. An overwrite would change its id and break the link in the Build comment while someone is downloading.

### Failure paths

Each case below is a visible "did not run" or a failure. None of them is an empty page.

| Case | What the writer sees |
|---|---|
| Runner is `hosted` | Comment "did not run: <probe reason>; the preview shows `main`'s Bible"; check fails |
| `ai-review-not-run` | Also rewrites `<!-- nano:bible -->` with "did not run", so the previous push's preview does not stay up |
| Spend cap reached | The ADR-023 reason, with the reset date |
| Extraction partial | Comment lists the failed passages; the check fails |
| Push with no changed passages | "Nothing to read"; the check succeeds |

Fork PRs get no extraction. Their Freshness section lists the passages as not read (AC-story-bible-35).

### Canon for the PR's review

The review still uses `main`'s canon pack, for three reasons:
- A preview failure must never become a review failure.
- Provisional ids must never reach findings or dismissals.
- Reviewing against facts from the same PR changes continuity behaviour and needs an eval delta.

## Consequences

### Positive

- The preview shows the PR's passages. After merge, `main` usually pays only for resolve and reconcile.
- Losing the store or a corrupt entry costs money, not correctness, and it is counted in the diff.

### Negative

- **New recurring spend.** Each PR push that changes text pays for extraction of the changed passages plus one resolve call, about $0.005 to $0.01.
  - This estimate assumes about 300 pushes in November, adding about $2 to $3 against the cap.
  - Busier months compete with reviews. Whether the preview needs its own ceiling is a spend decision for the ceo.
- **Stale roster.** An answer reused across a roster change may name an entity differently. Resolve on `main` usually merges it; otherwise a duplicate entity appears until an `alias:` line joins it.
- **Trust.** `ai-review` installs the merge ref's package, so a same-repository PR's code can write store entries that `main` later reads.
  - The trust given to write collaborators already covers this.
  - Re-validation and re-verification of quotes limit the damage to claims backed by real quotes.
- **Latency.** The `ai-review` job takes a few minutes longer, and the preview arrives after the review.

## Alternatives Considered

1. **Full dry run, with reconcile, on every push.** Rejected: it doubles the per-push model calls, and conflicts found under provisional merges are the least trustworthy thing on the page.
2. **A separate exe job.** Rejected: it queues on the single runner, and a probe-to-start gap can leave it queued.
3. **Roster in the key.** Rejected: reuse would almost never happen after another merge, which fails AC-story-bible-36.
4. **Store in the Actions cache or under `ai/`.** Rejected: the Actions cache has eviction and scope rules that are not ours, and `ai/` would add commits.
5. **Treat a corrupt store as fatal, like the ledger.** Rejected: a lost ledger under-counts spend, whereas a lost store only costs money, and that cost is capped.

## References

- ADR-014, ADR-020, ADR-022, ADR-023; `features/story-bible.md` (AC-story-bible-33 to AC-story-bible-36)
- `nanoif/bible/{run,extract,store}.py`, `.github/actions/ai-review/`, `deploy/exe/`
