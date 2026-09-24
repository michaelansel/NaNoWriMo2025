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
| LLM gateway | OpenAI-compatible endpoint reached from the exe runner with no key | [016](architecture/016-llm-client-and-prompt-contract.md) |
| `ai/` | State written only by Actions jobs on `main` | [014](architecture/014-actions-automation-exe-runner.md), [019](architecture/019-ai-review-contract.md), [020](architecture/020-story-bible-v2.md) |
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
        └─ nanoif build story-bible ─→ story-bible.html, story-bible.json (from the cache, no model)
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

The Actions integration below is being implemented; the workflows currently in the tree are the
earlier single build workflow plus `intent.yml`.

```
PR opened / pushed
  ├─ build   (hosted, contents: read) → story-preview artifact, Structure check run,
  │                                     <!-- nano:build --> comment
  ├─ test    (hosted) → pytest + ruff, required
  ├─ Intent  (hosted) → nanoif intent check + intent range, required
  ├─ probe   (hosted) → curl EXE_HEALTH_URL → runner = exe | hosted
  └─ ai-review (needs build, probe; same-repo PRs only; timeout 45 min)
        runner=exe:    nanoif ai review --mode changed → ai-review.json
                       → <!-- nano:continuity --> and <!-- nano:style --> comments + check runs
        runner=hosted: "AI review unavailable" comment, failing check, no model call
```

- One sticky comment per check type, found by its HTML marker and edited in place; one check
  run per type (success = pass, neutral = findings, failure = could not run)
  ([014](architecture/014-actions-automation-exe-runner.md)).
- `ai-review.json` is the only contract between the editors and the GitHub reporter; it
  records per-editor and per-unit status so "could not check" is always visible
  ([019](architecture/019-ai-review-contract.md)).
- Review units are built per changed passage from `story_graph.json` and `changes.json`;
  findings have stable keys `f-<8 hex>` so a contradiction is reported once and can be
  dismissed ([019](architecture/019-ai-review-contract.md)).
- Slash commands on a PR (`/check-continuity [all] [passage=<name>]`, `/extract-story-bible`,
  `/dismiss <key> [reason]`) run in `ai-command.yml` only for owners, members and
  collaborators ([014](architecture/014-actions-automation-exe-runner.md)).

## Main branch flow

```
push to main
  ├─ build (hosted)
  ├─ bible-extract (exe, contents: write) → nanoif bible extract --incremental
  │                                        → commit ai/story-bible-cache.json if changed
  └─ render-and-deploy (hosted, always runs) → rebuild with the current cache → Pages
```

- A failed extraction still deploys, with the previous cache and a freshness notice
  ([020](architecture/020-story-bible-v2.md), Proposed; the current renderer reads the
  earlier cache format per [010](architecture/010-story-bible-design.md)).
- `ai-maintenance.yml` (manual, and a daily `runner-check` in November) runs `extract-full`,
  `check-all`, `eval` and `runner-check`; `pr-closed` records finding outcomes on merge.

## State

| File | Written by | Read by |
|---|---|---|
| `ai/story-bible-cache.json` (v2) | `bible-extract` on main | `nanoif build story-bible`, canon pack |
| `ai/dismissals.jsonl` | `/dismiss` job on main | `nanoif ai review` (suppression) |
| `ai/outcomes.jsonl` | `pr-closed` on main | false-positive review |
| `story-overrides.txt` | writers | `nanoif check structure`, Story Bible |
| `dist/**`, `lib/artifacts/**` | every build | pages, AI jobs via `story-preview` |

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
| `ai-review.json` | `ai_review` | `ai review` → GitHub reporter, `/dismiss` ([019](architecture/019-ai-review-contract.md)) |
| model output | `nanoif/prompts/<name>.schema.json` | model → editors ([016](architecture/016-llm-client-and-prompt-contract.md)) |

Other contracts: comment markers `<!-- nano:build -->` and `<!-- nano:<editor> -->`, env
`NANOIF_LLM_*` and `NANOIF_REVIEW_UNIT_BUDGET`, repository variables `LLM_PROFILE`,
`LLM_MODEL`, `EXE_HEALTH_URL`, `AI_RUNNER`.

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
| `llm/` | client, profiles, schema parsing, pricing, test doubles ([016](architecture/016-llm-client-and-prompt-contract.md)) |
| `prompts/` | Jinja prompts with sibling output schemas |
| `review/` | review units, Continuity and Style editors, finding keys (being built, [019](architecture/019-ai-review-contract.md)) |
| `bible/` | Story Bible v2 stages and canon pack (planned, [020](architecture/020-story-bible-v2.md)) |
| `eval/` | scoring against `tests/fixtures/eval-story/truth.json` and baseline diffs |
| `intent/` | criterion and ADR index, citation check, commit gate ([021](architecture/021-intent-gate.md)) |

## Failure handling

- A build step that cannot read or validate its input raises a typed error; the CLI prints one
  `error:` line and exits 1, and the job fails.
- An AI job that cannot reach its runner or model says "unavailable" or marks the unit `error`;
  an editor reports zero findings as a pass only when every unit was reviewed.
- No `|| true`, `exit 0` or `continue-on-error` hides a failure; report-only steps still leave
  annotations, a check run or a step-summary line.
- The token budget per job (`NANOIF_LLM_MAX_TOKENS_PER_JOB`) stops a runaway job with an error.

## Intent

Feature notes (`features/`), ADRs and this page are checked by `nanoif intent check`, and
governed code changes carry an intent update or an `Intent: unchanged (...)` trailer
([021](architecture/021-intent-gate.md)).
