---
name: nov1-checklist
description: Read-only pass/fail check that the repo is ready for writers on Nov 1. Human-invoked; changes nothing.
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git *), Bash(gh *), Bash(pytest*), Bash(nanoif check*), Bash(nanoif build*), Bash(ls *), Bash(curl -sI *)
---

# Nov 1 readiness checklist

Run every check, then print one table: check, pass/fail, evidence (a command output line or file path). Do not fix anything; report only. A check that cannot run is reported as FAIL with the reason, never skipped.

| Check | How |
|---|---|
| Main is green | `gh run list --branch main --limit 1` shows success for `build-and-deploy.yml` |
| Pages serves the landing page | `curl -sI` on the Pages URL from `README.md` returns 200 |
| Play shows the Start stub | `nanoif build` succeeds and `dist/play.html` contains the `Start` passage |
| StoryData is filled | `src/StoryData.twee` has a fresh uppercase UUIDv4 IFID, a pinned `format-version`, and `storyStyle` with `perspective`, `protagonist`, `tense` set (no placeholders) |
| StoryTitle is set | `src/StoryTitle.twee` is not the placeholder text |
| `src/` holds only infra files | exactly `Start`, `StoryData`, `StoryTitle`, `StoryStyles`, `PathIdDisplay` plus zero or more `<INITIALS>-<YYYYMMDD>.twee` |
| No caches tracked | `git ls-files` shows no `allpaths-validation-status.json`, no `Resource-Passage Names`, and `ai/story-bible-cache.json` only if written by Actions |
| `ai/` state exists | `ai/dismissals.jsonl`, `ai/outcomes.jsonl`, and `story-overrides.txt` exist (may be empty) |
| No previous-year names | `git grep -n` for the retired writers' initials, character names, and last year's dates returns nothing outside `architecture/` |
| Structure check clean | `nanoif check src/` reports no broken links, duplicates, or naming drift |
| Tests green | `pytest -q` passes |
| Runner reachable | `curl -sI` on `vars.EXE_HEALTH_URL` (from `gh variable list`) returns 200 |
| Repo variables set | `gh variable list` shows `LLM_PROFILE`, `LLM_MODEL`, `EXE_HEALTH_URL` |
| One comment per check type | the most recent test PR (`gh pr list --state all --limit 1`) has exactly one Build, one Continuity, one Style comment |
| No bot commits on branches | `gh pr view <n> --json commits` for that PR shows no `github-actions[bot]` author |
| Eval baseline committed | `tests/eval/baselines/exe.json` exists and `/eval-prompts` reports no regression |
| Writer docs current | `WRITING-WORKFLOW.md` under 150 lines, `README.md` "Before Nov 1" checklist has no unchecked items |

End with a single line: `READY` if every row passes, otherwise `NOT READY: <n> failing`.
