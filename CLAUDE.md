# NaNoWriMo interactive fiction

Writers put Twee passages in `src/`, open a PR from the GitHub web UI, and GitHub Actions
builds a playable story, runs deterministic structure checks, and posts an honest AI read of
the new passages. Writers never run Claude in this repo; you are the developer of the tooling.

Two rules override everything else here:
1. Never edit writer prose (`src/<INITIALS>-<YYYYMMDD>.twee`) unless the user named the file.
2. A check that could not run says so. "No issues" is only ever a verified result.

## Commands

```
pip install -e ".[dev]"                   # package + pytest + ruff
pytest                                    # all tests (CI required check)
ruff check nanoif tests                   # lint, E722 (bare except) is an error
nanoif build all --repo .                 # dist/ artifacts: allpaths, metrics, story bible, passages
nanoif check structure src/               # broken links, duplicates, orphans, naming drift (report-only)
nanoif lint src/                          # twee formatting (report-only; --fix is denied)
nanoif ai review --repo . --mode changed  # Continuity + Style editors on a built repo; paid inference
nanoif ai eval --repo . [--baseline tests/eval/baselines/<profile>.json]  # score the editors on the eval story
nanoif intent check --repo .              # criteria, test citations, ADR statuses
tweego -o dist/play.html -f harlowe-3.3.9 src/   # play build (CI pins Harlowe 3.3.9 into storyformats/)
```

Inference env: `NANOIF_LLM_PROFILE` (`exe` default and the CI default, `fireworks`, `ollama`),
`NANOIF_LLM_BASE_URL|API_KEY|MODEL|TIMEOUT_S|MAX_RETRIES|MAX_CONCURRENCY|REASONING_EFFORT|MAX_TOKENS_PER_JOB|JSON_MODE`,
`NANOIF_LLM_MONTHLY_USD` (monthly spend cap, default 10, `off`) and `NANOIF_LLM_LEDGER_DIR` (ADR-023).

## Layout

```
src/                 writer prose + infra files (StoryData, StoryTitle, StoryStyles, PathIdDisplay; Start is tooling-owned prose)
story-overrides.txt  writer-editable bible overrides (alias / not-entity / pin / intentional-conflict)
ai/                  state written only by Actions on main: story-bible-cache.json, dismissals.jsonl, outcomes.jsonl
nanoif/              the package: twee/ graph/ git/ llm/ bible/ review/ check/ formats/ prompts/ schemas/ templates/ cli.py
tests/               pytest; fixtures/eval-story is the canonical test story with truth.json; eval/baselines/<profile>.json
.github/workflows/   build-and-deploy.yml, ai-command.yml, ai-maintenance.yml
deploy/exe/          self-hosted runner units for the exe.dev VM
features/ architecture/  feature notes (PRDs) and ADRs
dist/                build output, never committed
```

## Conventions

- Prose files: `src/<INITIALS>-<YYYYMMDD>.twee`; entry passage `:: Day <N> <INITIALS>`. No other pattern.
- Names in tests, prompts, and docs come from the eval story only. No real writers' characters or dates.
- Commit subject `<type>: <imperative summary>`; types `feat fix docs style refactor test chore prompt`.
  `prompt:` is for changes under `nanoif/prompts/` or `nanoif/schemas/`, and must cite the eval delta.
- Python: 3.11+, ruff clean, type hints, Google docstrings, `pathlib`, no cwd assumptions, typed errors.
- Prompts are Jinja files with a sibling `*.schema.json`; no prompt text in Python.
- TDD for `nanoif/**` only. Prompts are tested with `nanoif ai eval`; workflows with a PR that exercises them.

## Hard rules

- No automation ever commits to a PR branch. Only three main-branch jobs have `contents: write`.
- No paid inference from an unauthenticated trigger: slash commands are `author_association`-gated.
- No `|| true`, `exit 0`, or `continue-on-error` that hides a failure; every failure has a visible check or comment.
- One sticky comment per check type per PR, found by its HTML marker, never by footer text.
- Never delete or rewrite `ai/*` state locally; it is produced by Actions on main.

## Intent is owned and traceable

Intent has three layers, each with an owner who writes it. Behaviour may not drift from it silently.

| Layer | Documents | Owner (writes it) |
|---|---|---|
| Why | `VISION.md`, `PRINCIPLES.md`, `PRIORITIES.md` | `ceo` drafts, the user approves |
| What | `features/*.md`: every acceptance criterion is `- AC-<note>-<n>: ...` | `pm` |
| How | `ARCHITECTURE.md`, `architecture/NNN-*.md` ADRs (`Status:` line; superseded, never rewritten) | `architect` |

- Before changing behaviour a criterion or ADR describes, have its owner update that document in the
  same change. Removing or weakening a criterion or decision is an explicit edit by its owner, never
  a side effect.
- Every `verify: test` criterion needs a test marked `@pytest.mark.intent("AC-...")`.
  `nanoif intent check` fails on untested criteria, unknown citations, duplicate ids, missing ADR status.
- A commit that changes governed code (`nanoif/`, `.github/`, `scripts/`, `deploy/`, `landing/`,
  `pyproject.toml`, infra passages) without touching an intent document must carry
  `Intent: unchanged (<why the documented behaviour still holds>)`. The commit-msg hook and the
  Intent CI check enforce it; never bypass them (`--no-verify` is forbidden).

## How to work here

You are the developer. Owners are consulted per change, not per project:

| When | Do |
|---|---|
| Docs outside the three layers, tests, prompt wording, behaviour-preserving fixes | Just do it (trailer on governed code) |
| Anything a writer notices, or any change to a feature's acceptance criteria | `pm` reviews and edits `features/` before the PR |
| Module boundary, workflow job, persistent state, dependency, data contract, anything alive unattended in November | `architect` reviews before the first edit and writes the ADR |
| Scope, a Nov 1 must-have, spend past the cap, a principle or a date | `ceo` drafts; the user decides |

Owners write only their own layer (enforced by a write-scope hook). Skills: `/prd`, `/adr`,
`/eval-prompts`; `/nov1-checklist` and `/new-year-reset` are human-invoked only.

## Where the truth lives

- Why and what matters: `VISION.md`, `PRINCIPLES.md`, `PRIORITIES.md` (stack rank, dates, and the roadmap; there is no ROADMAP.md)
- What features do: `features/*.md`; how the system is shaped: `ARCHITECTURE.md`, `architecture/*.md` ADRs
- What writers read: `README.md`, `CONTRIBUTING.md`, `WRITING-WORKFLOW.md`
- What the AI must get right: `tests/fixtures/eval-story/truth.json` and `tests/eval/baselines/`
- Path-specific rules for this agent: `.claude/rules/*.md`
