# Architecture

Writers add Twee passages to `src/` through pull requests. GitHub Actions builds a playable
story and reading aids, runs deterministic checks, and runs AI editors that read only the new
and changed passages. Every result lands on the PR as one sticky comment and one check run per
check type, and nothing a check could not do is ever shown as a pass.

Decisions are recorded in [`architecture/`](architecture/); this page describes the system as
it is and links the ADR that explains each part. Superseded ADRs are kept for their record.

## Components

| Component | What it is | Decided in |
|---|---|---|
| `src/` | Writer prose `<INITIALS>-<YYYYMMDD>.twee` plus infrastructure passages (`Start`, `StoryData`, `StoryTitle`, `StoryStyles`, `PathIdDisplay`) | [018](architecture/018-structure-check-and-report-only-lint.md) |
| `story-overrides.txt` | Writer-editable Story Bible corrections, syntax-checked on every build | [020](architecture/020-story-bible-v2.md) |
| `nanoif/` | The one Python package and `nanoif` CLI | [015](architecture/015-nanoif-package.md) |
| `.github/workflows/` | `build-and-deploy.yml`, `ai-command.yml`, `ai-maintenance.yml`, `intent.yml` | [014](architecture/014-actions-automation-exe-runner.md), [021](architecture/021-intent-gate.md) |
| exe runner | Self-hosted Actions runner on an exe.dev VM, label `exe`; runs only AI jobs; `deploy/exe/`, `docs/exe-runner.md` | [014](architecture/014-actions-automation-exe-runner.md) |
| LLM gateway | OpenAI-compatible endpoint reached from the exe runner with no key; our spend on it is capped monthly | [016](architecture/016-llm-client-and-prompt-contract.md), [023](architecture/023-monthly-spend-cap.md) |
| `ai/` | State written only by Actions jobs on `main` | [014](architecture/014-actions-automation-exe-runner.md), [022](architecture/022-ai-review-lineage-and-not-run.md), [020](architecture/020-story-bible-v2.md) |
| `dist/` | Build output; uploaded as `story-preview` on PRs, deployed to Pages from `main`; never committed | [017](architecture/017-git-based-categorization.md) |
| `landing/` | Static landing page copied to `dist/index.html` | [011](architecture/011-landing-page-design.md) |

## Build pipeline

Runs on a hosted runner for every PR and every push to `main`, and locally with the same commands.

```
src/*.twee
  ├─ tweego -f paperthin ─→ dist/story-paperthin.html
  │     └─ nanoif build core ─→ lib/artifacts/story_graph.json
  │                             lib/artifacts/passages_deduplicated.json
  │                             src/PathIdLookup.twee (generated, git-ignored)
  ├─ tweego -f harlowe   ─→ dist/play.html        (includes the path-id lookup)
  ├─ tweego -f paperthin ─→ dist/proofread.html
  ├─ tweego -f dotgraph  ─→ dist/graph.html
  └─ story_graph.json + git base
        ├─ nanoif build allpaths    ─→ allpaths.html, allpaths-{clean,metadata,raw}/,
        │                              allpaths-index.json, changes.json
        ├─ nanoif build metrics     ─→ metrics.html
        ├─ nanoif build passages    ─→ passages.html
        ├─ nanoif build story-bible ─→ story-bible.html, story-bible.json (cache + overrides, no model)
        └─ nanoif build canon-pack  ─→ canon-pack.json (≤ 6 facts per entity, for the Continuity Editor)
```

- Tweego versions and story formats are pinned in the workflow; `scripts/build-*.sh` are thin
  wrappers around tweego and `nanoif` ([015](architecture/015-nanoif-package.md)).
- `nanoif build core` parses once; every format reads the core artifacts and never another
  format's output ([015](architecture/015-nanoif-package.md)).
- Categories (new / modified / unchanged) and `changes.json` come from comparing the working
  tree with the PR's merge base in git; there is no validation cache
  ([017](architecture/017-git-based-categorization.md)).
- `nanoif check structure src/` and `nanoif lint src/` report on the same source; neither
  writes to it ([018](architecture/018-structure-check-and-report-only-lint.md)).

## Pull request flow

```
PR opened / pushed
  ├─ build   (hosted, contents: read) → story-preview artifact, Structure check run,
  │                                     <!-- nano:build --> comment (report step on !cancelled())
  ├─ test    (hosted) → pytest + ruff, required
  ├─ Intent  (hosted) → nanoif intent check + intent range, required
  ├─ probe   (hosted) → curl EXE_HEALTH_URL, or vars.AI_RUNNER → runner = exe | hosted
  ├─ ai-review (needs build, probe; same-repo PRs only; timeout 45 min)
  │     runner=exe:    nanoif ai review --mode changed → ai-review.json + head sha
  │                    → <!-- nano:continuity --> and <!-- nano:style --> comments + check runs
  │     runner=hosted: "AI review unavailable" comment, failing check, no model call
  └─ ai-review-not-run (hosted; when build or probe did not succeed)
        → both editor comments "did not run for <sha>", failing checks, job fails
```

- One sticky comment per check type, found by its HTML marker and edited in place; one check
  run per type (success = pass, neutral = findings, failure = could not run or only partly
  checked) ([014](architecture/014-actions-automation-exe-runner.md)).
- `ai-review.json` is the only contract between the editors and the GitHub reporter; it
  records per-editor and per-unit status so "could not check" is always visible. Each PR
  review is uploaded as `ai-review-pr-<N>` with `ai-review-head-sha.txt`; the newest is "the
  last review" ([022](architecture/022-ai-review-lineage-and-not-run.md)).
- Review units are built per changed passage from `story_graph.json` and `changes.json`;
  findings have stable keys `f-<8 hex>` so a contradiction is reported once and can be
  dismissed ([022](architecture/022-ai-review-lineage-and-not-run.md)).
- Slash commands on a PR (`/check-continuity [all] [passage=<name>]`, `/extract-story-bible`,
  `/dismiss <key> [reason]`) run in `ai-command.yml` only for owners, members and
  collaborators ([014](architecture/014-actions-automation-exe-runner.md)). A `passage=`
  re-check merges into the last review only when both are for the current head, otherwise
  it is published as partial; `/dismiss` re-renders only a review of the current head
  ([022](architecture/022-ai-review-lineage-and-not-run.md)).

## Main branch flow

```
push to main (or dispatch with bible-mode=full)
  ├─ build, probe (hosted)
  ├─ bible-extract (probe runner, contents: write) → checkout main HEAD
  │     exe:    nanoif bible extract --incremental|--full → commit ai/story-bible-cache.json
  │             if changed (rebase-retry once); exit 3 = partial: commit, then fail
  │     hosted: no model call, ::error:: + step summary, job fails
  └─ deploy (hosted, whenever build succeeded) → re-render story-bible + canon-pack from the
        new cache (or the previous one) with --extraction-result → Pages
```

- Stages: extract per changed passage (model), resolve names (deterministic, then one batched
  model pass), reconcile touched entities (model returns fact ids only), assemble with
  `story-overrides.txt` (deterministic). Fact ids `<slug>#<n>` are never reused
  ([020](architecture/020-story-bible-v2.md)).
- A failed or skipped extraction still deploys, with the previous cache and a banner naming
  the failure and the date of the Bible shown.
- `ai-maintenance.yml` (manual, and a daily `runner-check` in November) runs `check-all`,
  `eval` and `runner-check`; `pr-closed` records finding outcomes on merge.

## State

| File | Written by | Read by |
|---|---|---|
| `ai/story-bible-cache.json` (v2) | `bible-extract` on main | `nanoif build story-bible`, canon pack |
| `ai/dismissals.jsonl` | `/dismiss` job on main | `nanoif ai review` (suppression) |
| `ai/outcomes.jsonl` | `pr-closed` on main | false-positive review |
| `story-overrides.txt` | writers | `nanoif check structure`, Story Bible |
| `dist/**`, `lib/artifacts/**` | every build | pages, AI jobs via `story-preview` |
| spend ledger `<NANOIF_LLM_LEDGER_DIR>/YYYY-MM.jsonl` (on the exe VM, not in git) | every model call | the monthly cap ([023](architecture/023-monthly-spend-cap.md)) |

Only those three `main` jobs have `contents: write`, and only for `ai/`. No automation commits
to a PR branch ([014](architecture/014-actions-automation-exe-runner.md)). Until Story Bible v2
lands, the renderer reads the earlier cache format from `story-bible-cache.json` at the
repository root ([010](architecture/010-story-bible-design.md)).

## Data contracts

Every JSON artifact that crosses a job or process boundary has a schema in
`nanoif/schemas/artifacts/` and is validated when written and when read
([015](architecture/015-nanoif-package.md)).

| Artifact | Schema | Producer → consumer |
|---|---|---|
| `story_graph.json` | `story_graph` | `build core` → every format, review units |
| `passages_deduplicated.json` | `passages_deduplicated` | `build core` → Story Bible |
| `allpaths-index.json` | `allpaths_index` | `build allpaths` → pages, tools ([017](architecture/017-git-based-categorization.md)) |
| `changes.json` | `changes` | `build allpaths` → `ai review --mode changed` ([017](architecture/017-git-based-categorization.md)) |
| `structure --format json` | `structure_findings` | `check structure` → Structure check run ([018](architecture/018-structure-check-and-report-only-lint.md)) |
| `ai-review.json` | `ai_review` | `ai review`, `github merge-review` → GitHub reporter, `/dismiss` ([022](architecture/022-ai-review-lineage-and-not-run.md)) |
| model output | `nanoif/prompts/<name>.schema.json` | model → editors ([016](architecture/016-llm-client-and-prompt-contract.md)) |
| spend ledger line | `spend_ledger_line` | `LLMClient` → `LLMClient` in later jobs ([023](architecture/023-monthly-spend-cap.md)) |

Other contracts: `ai-review-head-sha.txt` beside `ai-review.json` in the `ai-review-pr-<N>`
artifact (unvalidated; missing means commit unknown), comment markers `<!-- nano:build -->`
and `<!-- nano:<editor> -->`, env
`NANOIF_LLM_*` (including `MONTHLY_USD` and `LEDGER_DIR`) and `NANOIF_REVIEW_UNIT_BUDGET`,
repository variables `LLM_PROFILE`, `LLM_MODEL`, `LLM_MONTHLY_USD`, `EXE_HEALTH_URL`, `AI_RUNNER`.

## Where each concern lives in `nanoif/`

| Module | Concern |
|---|---|
| `cli.py` | `nanoif` commands; every path derived from `--repo` or an explicit argument |
| `errors.py` | package error hierarchy (`NanoifError`) |
| `twee/` | the one header regex (`files`), link parser (`links`), story parser (`parse`), prose and word counts, passage hashes, report-only linter (`lint`) |
| `graph/` | path enumeration (`paths`), base comparison and categories (`categorize`), passage ids and the path-id lookup (`ids`) |
| `git/` | the one `git` service: cached, timed, one `git log` per build |
| `build/` | repository layout (`paths`) and `build core` |
| `formats/` | `allpaths`, `metrics`, `passages`, `story_bible` pages from core artifacts; HTML in `templates/html/` |
| `check/` | `structure` checks and the `story-overrides.txt` syntax parser |
| `schemas/` | artifact schemas and write/read validation |
| `llm/` | client, profiles, schema parsing, pricing, spend ledger (`ledger`), test doubles ([016](architecture/016-llm-client-and-prompt-contract.md), [023](architecture/023-monthly-spend-cap.md)) |
| `prompts/` | Jinja prompts with sibling output schemas |
| `review/` | review units, Continuity and Style editors, finding keys, editor status (`runner.editor_status`) ([022](architecture/022-ai-review-lineage-and-not-run.md)) |
| `github/` | the GitHub reporter: sticky comments and check runs, `/dismiss` records, passage re-check merge (`merge`), slash-command parsing ([014](architecture/014-actions-automation-exe-runner.md), [022](architecture/022-ai-review-lineage-and-not-run.md)) |
| `bible/` | Story Bible v2 stages and canon pack (planned, [020](architecture/020-story-bible-v2.md)) |
| `eval/` | scoring against `tests/fixtures/eval-story/truth.json` and baseline diffs |
| `intent/` | criterion and ADR index, citation check, commit gate ([021](architecture/021-intent-gate.md)) |

## Failure handling

- A build step that cannot read or validate its input raises a typed error; the CLI prints one
  `error:` line and exits 1, and the job fails.
- An AI job that cannot reach its runner or model says "unavailable" or marks the unit `error`;
  an editor reports zero findings as a pass only when every unit was reviewed. A review that
  never started (build or probe failed) replaces both editor comments with "did not run"
  ([022](architecture/022-ai-review-lineage-and-not-run.md)).
- When checkout or the package install fails, the Build report cannot run and the previous
  Build comment stays; the red `build` check is the signal (accepted gap,
  [022](architecture/022-ai-review-lineage-and-not-run.md)).
- No `|| true`, `exit 0` or `continue-on-error` hides a failure; report-only steps still leave
  annotations, a check run or a step-summary line.
- The token budget per job (`NANOIF_LLM_MAX_TOKENS_PER_JOB`) stops a runaway job with an error.
  The monthly spend cap (`NANOIF_LLM_MONTHLY_USD`, default $10) refuses a call before it
  would pass the cap; the review then shows both editors as not run, with the reset date. An
  unreadable ledger blocks calls rather than counting as zero ([023](architecture/023-monthly-spend-cap.md)).

## Intent

Feature notes (`features/`), ADRs and this page are checked by `nanoif intent check`, and
governed code changes carry an intent update or an `Intent: unchanged (...)` trailer
([021](architecture/021-intent-gate.md)).
