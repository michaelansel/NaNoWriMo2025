---
name: new-year-reset
description: Ordered checklist for resetting the repo for a new writing year. Human-invoked; confirms every destructive step before doing it.
disable-model-invocation: true
---

# New year reset

Work through the steps in order. Before each step marked **destructive**, show exactly what will be deleted or overwritten and wait for a yes. Never batch destructive steps. Read `PRIORITIES.md` first: if a Nov 1 must-have is still open, say so and stop.

## 1. Retro (before anything is deleted)

- Read `ai/outcomes.jsonl` and summarize: findings total, dismissed, fixed, ignored-at-merge; false-positive proxy.
- List every skill, agent, rule, and workflow task, and whether it was used this season (`git log`, `gh run list`). Propose retiring the unused ones.
- Write the retro as a short section in `PRIORITIES.md` under the new year's heading. This is the only place last year's numbers live.

## 2. Content reset (**destructive**)

- Delete every `src/<INITIALS>-<YYYYMMDD>.twee`. Keep `StoryStyles.twee` and `PathIdDisplay.twee` as they are.
- Replace `Start.twee` with the stub: one passage `:: Start`, no links, a comment stating the naming rule.
- `StoryData.twee`: new uppercase UUIDv4 IFID; `format-version` pinned to what the bundled tweego ships; `storyStyle` placeholders for `perspective`, `protagonist`, `tense`.
- `StoryTitle.twee`: placeholder title.

## 3. State reset (**destructive**)

- Delete `ai/story-bible-cache.json`; truncate `ai/dismissals.jsonl` and `ai/outcomes.jsonl` to empty; reset `story-overrides.txt` to its comment header.
- Confirm no other cache or generated file is tracked: `git ls-files | grep -Ei 'cache|status|Resource'`.

## 4. Strings and examples

- `git grep` for last year's writer initials, character names, dates, and repo name across code, tests, prompts, and docs. Replace with eval-story names or `<INITIALS>-<YYYYMMDD>`. `architecture/` ADRs are history and may keep them.
- Landing, metrics, and story-bible titles read from `StoryTitle`/`StoryData`; verify no title is hardcoded.

## 5. Docs

- `README.md` "Before Nov 1" checklist reset to unchecked. `WRITING-WORKFLOW.md` and `CONTRIBUTING.md` re-read for anything year-specific.
- `PRIORITIES.md` gets the new year's stack rank; `VISION.md` and `PRINCIPLES.md` change only if a principle changed.

## 6. Configuration review

- Retire the skills, agents, and rules the retro marked unused. Check `CLAUDE.md` is still under 120 lines and every command in it exists.
- Review `.claude/settings.json`: deny list still covers prose and generated files; hooks still point at commands that exist.

## 7. Verify

- `pytest -q` green, `nanoif check src/` clean, `nanoif build` produces a play page showing the Start stub.
- Open a PR with the reset and confirm the workflows post exactly one Build, one Continuity, and one Style comment and no bot commits.
- Run `/nov1-checklist` and stop when it prints `READY`.
