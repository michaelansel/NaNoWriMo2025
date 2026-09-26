# Priorities

What matters now, in rank order, with dates. The goal is in [VISION.md](VISION.md); how we decide is
in [PRINCIPLES.md](PRINCIPLES.md).

## Trade order

When two things compete for time, the higher one wins:

1. Tooling reliable for writers
2. AI honest
3. Codebase clean
4. AI good

## Nov 1 must-haves

### P0: Tooling reliable for writers

**Goal:** every day of November, a writer goes from edit to pull request to preview to merge to live
from a browser, with nothing blocking them.

- Content reset done: `src/` holds only the infrastructure passages and the Start stub, AI state is
  fresh, and the story settings are filled in.
- Every pull request builds, previews and runs the structure check; every merge deploys; tests run
  in CI as a required check.
- No automation commits to a writer's branch or rewrites prose.
- Writer docs (`README.md`, `CONTRIBUTING.md`, `WRITING-WORKFLOW.md`) are current.

**Done by:** Oct 25, when `/nov1-checklist` prints `READY`.

### P1: AI honest

**Goal:** every AI result is either a verified read or a visible "could not check".

- The Continuity and Style editors review every pull request from a branch of this repository,
  with one comment and one check run each.
- Runner offline, model error, a passage too long to read, or the spend cap reached: the pull
  request says so and the check fails.
- On-demand commands answer collaborators only.

**Done by:** green on a real pull request by Oct 10 (critical path).

### P2: Codebase clean enough

**Goal:** one installable package that the next change can be made in safely.

- One `nanoif` package; pytest and ruff in CI; no tests that cannot fail; dead code deleted.

**Done by:** Oct 25. No restructuring in November.

### P3: AI good

**Goal:** findings worth a writer's minute.

- Story Bible v2 (per-entity merge, stable fact ids, the overrides file, freshness) is live and
  feeds canon to the Continuity Editor.
- An eval baseline is committed for the default profile, and every prompt change cites its eval
  delta.
- Quality keeps improving through November by prompt and config changes only.

**Done by:** Story Bible v2 Oct 18; eval tuning Oct 25. If Story Bible v2 is not green by Oct 25 it
does not ship on Nov 1: the Continuity Editor runs on earlier passages only, and the Story Bible
lands in December.

## Schedule (2026 season)

| When | Work |
|---|---|
| Sep 26 - Oct 2 | Package and CI tests, structure check, LLM client, eval story, runner online |
| Oct 3 - Oct 10 | Critical path: move to the new repository; Continuity and Style editors; workflows; green on a real pull request |
| Oct 11 - Oct 18 | Story Bible v2, overrides, dismissals and outcomes |
| Oct 19 - Oct 25 | Eval and prompt tuning, remaining bugs, docs, content reset; `/nov1-checklist` READY |
| Oct 26 - Oct 31 | Freeze: a dry-run pull request each day; fixes only |
| Nov 1 - Nov 30 | Writing. Only writer-blocking bugs and prompt or config changes; weekly false-positive review from `ai/outcomes.jsonl`; spend watch |
| December | Retro (`new-year-reset`), anything cut, structural changes |

**Change windows.** A structural change (module boundary, workflow job, persistent state,
dependency, data contract) lands by Oct 25 or waits for December. Prompt wording, model choice and
configuration variables may change in November, each with its eval delta.

## Constraints

### AI spend cap: $10 per calendar month

**Decision:** AI inference for this project costs at most $10 per calendar month (UTC), estimated at
list prices. The cap resets on the 1st. Only the owner raises it, and raising it is a spend
decision, not a code change.

**Why:** Inference runs on the owner's shared LLM token allocation. This project must never be able
to use it up.

**When the cap is reached:** AI review stops, and the pull request says so. It is a visible "not
run", never a silent pass. Builds and structure checks spend no tokens, so they keep running.

**Trade-off accepted:** The cap outranks P1's "every pull request". Late in an expensive month, a
pull request may get no AI read. An honest "not run" beats an unbounded bill.

## Not before Nov 1

- A local-model profile as the default (December at the earliest)
- Path comparison, analytics and retrospective tools
- New AI editors: choice, pacing and ending checks; grammar and proofreading; multi-model review
- AI check runs as required merge checks
- Advanced interactive fiction features: variables, inventory, game mechanics
- Custom story formats beyond the current outputs

## Not in scope

- Real-time collaborative editing: the pull request model fits an async team.
- A WYSIWYG editor: Twee is simple enough to edit anywhere, even on a phone.
- Alternatives to Git and GitHub: the automation is built on them.
- Story formats other than Harlowe.
- Per-path approval: writers disposition findings, not paths.
- Story Bible variables, scene state and timelines.

## Deciding what's next

Ask, in order:

1. Will a writer notice it on Nov 1?
2. Does it remove a silent failure?
3. Does it add a moving part that must be alive in November? Then its failure must be visible to a
   writer.
4. Can it be tested end to end in the real repository before the freeze?
5. Is it prompt or config (can change in November) or structure (must land by Oct 25)?
6. Does fixing the whole class cost about the same as fixing this one instance? Fix the class.
7. Does it need the user? Batch the question.

Say "not now" to good ideas that do not serve this season.
