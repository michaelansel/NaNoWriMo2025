# NaNoWriMo interactive fiction

Writers put Twee passages in `src/`, open a PR from the GitHub web UI, and GitHub Actions
builds a playable story, runs deterministic structure checks, and posts an honest AI read of
the new passages. Writers never run Claude in this repo; you are the developer of the tooling.

Two rules override everything else here:
1. Never edit writer prose (`src/<INITIALS>-<YYYYMMDD>.twee`) unless the user named the file.
2. A check that could not run says so. "No issues" is only ever a verified result.

## Commands

The `nanoif` CLI is being built in Phase 1; until it lands, `tweego` and `pytest` are the working commands.

```
pip install -e ".[dev]"            # package + pytest + ruff
pytest                             # all tests (CI required check)
ruff check nanoif tests            # lint, E722 (bare except) is an error
nanoif build                       # dist/: play, proofread, graph, allpaths, metrics, story bible, passages
nanoif check structure src/        # broken links, duplicates, orphans, naming drift (report-only)
nanoif lint src/                   # twee formatting (report-only; --fix is denied)
nanoif ai review --mode changed    # Continuity + Style editors; paid inference
nanoif ai eval                     # score prompts against tests/fixtures/eval-story
nanoif bible extract --incremental # Story Bible v2; paid inference
tweego -o dist/play.html -f harlowe-3 src/   # raw build fallback
```

Inference env: `NANOIF_LLM_PROFILE` (`exe` default and the CI default, `fireworks`, `ollama`),
`NANOIF_LLM_BASE_URL|API_KEY|MODEL|TIMEOUT_S|MAX_RETRIES|MAX_CONCURRENCY|REASONING_EFFORT|MAX_TOKENS_PER_JOB|JSON_MODE`.

## Layout

```
src/                 writer prose + infra passages (Start, StoryData, StoryTitle, StoryStyles, PathIdDisplay)
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

## How to work here

You are the developer. Consult a reviewer agent once per change, at the point named below, then
apply what you take and record what you decline in the PR description.

| Tier | When | Do |
|---|---|---|
| 0 | Docs, config, tests, prompt wording, twee infra passages, behavior-preserving fixes | Just do it |
| 1 | Anything a writer notices: comment text, check-run names, landing page, CLI messages, WRITING-WORKFLOW | Ask `pm` once before opening the PR |
| 2 | Module or package boundary, workflow job, persistent state, dependency, data contract, anything that must stay alive unattended in November | Ask `architect` before the first edit; write an ADR with `/adr` if it changes a contract |
| 3 | Scope, cutting a Nov 1 must-have, spend past the cap, changing a principle or a date | Ask `ceo`, then the user decides |

Reviewer agents are read-only. They answer in a fixed order (verdict first) so you can act on the first line.
Skills: `/prd` for feature notes, `/adr` for decisions, `/eval-prompts` after any prompt change,
`/nov1-checklist` and `/new-year-reset` are human-invoked only.

## Where the truth lives

- Why and what matters: `VISION.md`, `PRINCIPLES.md`, `PRIORITIES.md` (stack rank, dates, and the roadmap; there is no ROADMAP.md)
- What features do: `features/*.md`; how the system is shaped: `ARCHITECTURE.md`, `architecture/*.md` ADRs
- What writers read: `README.md`, `CONTRIBUTING.md`, `WRITING-WORKFLOW.md`
- What the AI must get right: `tests/fixtures/eval-story/truth.json` and `tests/eval/baselines/`
- Path-specific rules for this agent: `.claude/rules/*.md`
