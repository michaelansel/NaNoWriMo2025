# ADR-025: The formatting fixer commits to same-repository pull request branches, and the fixed commit is rebuilt by dispatch

Status: Accepted

Supersedes: ADR-018 in part (the report-only linter and the removal of the smart-quotes rule) and ADR-014 in part (no automation commits to a PR branch; the list of `contents: write` jobs). Accepted when the user approved the formatting exception in `PRINCIPLES.md` §2: curly quotes become ASCII, and only files the PR adds or changes are fixed.

## Context

ADR-018 stopped the 2025 linter from committing to writers' branches, because it rewrote prose and produced dozens of bot commits. The proposal reverses that for the formatting linter only (the exception in `PRINCIPLES.md` §2): it may commit fixes that change whitespace and quote characters, never wording, never inside Harlowe macros or links.

Four constraints shape how:
- A push made with `GITHUB_TOKEN` starts no `pull_request` or `push` run. A fixed commit would get no build, preview, AI review, `test` or `Intent` check of its own.
- There is no GitHub App, PAT or secret (ADR-014).
- A job's check run attaches to the commit its run started on. Only check runs posted through the API can name another sha.
- Writers edit in the GitHub web UI.

## Decision

### The fixer (`nanoif/twee/lint.py`)

- Eight rules: the seven layout rules plus `smart-quotes`. That rule maps U+2018, U+2019, U+201C and U+201D to ASCII.
- It never touches:
  - passage header lines, because a renamed passage breaks links from other files;
  - `[[links]]` and link macros, with spans from `nanoif.twee.links.find_links`;
  - Harlowe macro calls, including calls that span lines, nested parentheses and string literals;
  - HTML tags;
  - special passages (`StoryData`, `[stylesheet]`, `[script]`).
- Spans are computed over the whole passage text, not per line. The one macro-span scanner lives in `nanoif/twee/prose.py`, and `prose` uses it too. `prose.HARLOWE_MACRO_RE` and any linter-local link or macro regex are deleted.
- **Invariant.** `fix_text` checks two things before it returns, and raises `LintError` when either fails:
  - per file, passage names, tags and `find_links` targets are unchanged;
  - with whitespace removed and the four quotes mapped, the fixed text equals the original.
- Fixing twice gives the same text as fixing once.
- **CLI.** `nanoif lint --fix FILE... --summary-out PATH` takes only explicit `src/<INITIALS>-<YYYYMMDD>.twee` files. A directory or any other name is usage error 2.
  - It fixes every file in memory first and writes only when all of them pass: all or nothing.
  - The summary is the `lint_fix` artifact: `{files: [{file, fixed: {rule: count}}], total}`.
  - Exit 0 whether or not anything changed; exit 1 when nothing was written.
  - `nanoif lint` without `--fix` stays report-only for every file.

### The `format` job (`build-and-deploy.yml`, hosted)

- **When:** only on `pull_request` events from a branch of this repository. It never runs on `main`, on forks or in dispatched runs.
- `timeout-minutes: 5`.
- **Permissions:**
  - `contents: write`, to push to the head branch;
  - `actions: write`, to dispatch;
  - `pull-requests: write`, for the Build comment when the dispatch fails.
- **Tooling** comes from the base branch, checked out with `persist-credentials: false` and installed non-editable with no pip cache (a PR's own jobs can write that cache, and this job can push); `nanoif` runs as the installed script. The PR head sha is checked out separately, also without credentials, so no pull request code runs with a write token. The token reaches only the push, as an auth header.
- **Files:** the prose files the PR adds, modifies or renames against its merge base. Infrastructure files stay report-only.
- **Outdated branch:** when the head's `build-and-deploy.yml` has no `pr` dispatch input, the job refuses before fixing, with "update the branch from main". The rebuild runs the branch's copy of the workflow, so dispatching it would return HTTP 422 and leave a fixed commit that no workflow run can rebuild.
- **Loop guard:** the job does nothing when the head commit is by `github-actions[bot]` and carries the trailer `Nanoif-Format: <sha>`.
  - Structurally, only `pull_request` runs push, and a bot push starts no `pull_request` run.
  - The fixer is idempotent, so a rerun has nothing to fix.
- **Commit:** exactly one commit on top of the head sha.
  - Author `github-actions[bot]`.
  - Subject `style: fix N formatting issues in <files>`.
  - Trailer `Nanoif-Format: <previous head sha>`.
- **Push:** `HEAD:refs/heads/<head_ref>`, never forced, never retried.
  - Every push failure sets `pushed=false` and fails the job, including a non-fast-forward rejection because the writer pushed again (reason: "the branch moved while the bot was fixing it; the run for the newer push formats it"). One rule for every failure means a misread `git push` message cannot turn a failure into a quiet skip. The newer push's run joins `ci-pr-<N>`, cancels this one and rewrites the Build comment.
- **Outputs:** `pushed`, `new_sha`, `problem` (`refused` | `push-failed` | `dispatch-failed`) and `reason`. A final `!cancelled()` step sets them from the step outcomes and fails the job whenever `problem` is set. For `refused` and `push-failed`, `build` in the same run passes them to `nanoif github build-report --format-problem/--format-reason`. They travel as outputs, not a separate comment, because `build` rewrites the same `<!-- nano:build -->` comment after `format`.
- **Dispatch:** after a push the job starts `intent.yml`, then `build-and-deploy.yml -f pr=<N>`, both with `--ref <head_ref>` and each retried once after 10 s. Intent goes first because the rebuild joins `ci-pr-<N>` and cancels this run; if intent cannot be started, the rebuild is not started either.
  - If a dispatch still fails, the job writes the `<!-- nano:build -->` comment itself (`build-report --format-problem dispatch-failed`, since `build` is skipped after a push): "fixed in `<sha7>`, but the checks for that commit could not start: <reason>; edit any file or ask a maintainer to re-run". Then the job fails. It creates no `Structure` check run on the new head: it has no `checks: write`, and the one job that can push gets no more permissions than it needs.

### The run that pushed, and the dispatched run

- In the run that pushed, `build` has `needs: format` and `if: !cancelled() && needs.format.outputs.pushed != 'true'`.
- `ai-review-not-run` also requires `pushed != 'true'`. Without that it would post "did not run" for a commit that is no longer the head.
- Every job that needs `format` uses `!cancelled()`, because `format` is skipped on `main` and on forks and a plain `needs` would skip them silently.
- **Dispatch mode:** `workflow_dispatch` gains the input `pr`.
  - A hosted `context` job gives every PR job `pr`, `head_sha`, `head_ref`, `base_ref`, `base_sha` and `same_repo`, taken from the event or from `gh api pulls/<pr>`.
  - It fails with a reason when the PR is not open or when `github.sha` is not its head (a stale dispatch).
  - PR jobs read `needs.context.outputs`, never `github.event.pull_request.*`.
  - If `context` fails, `build` fails with that reason rather than being skipped, because a skipped required check counts as passing. No Build or editor comment is written then; the red `build` check is the signal (the accepted gap of ADR-022).
- **Concurrency:** the dispatched run joins `ci-pr-<pr>`, which cancels the run that pushed.
- **Merge commit:** GitHub updates the PR's merge commit asynchronously, so in dispatch mode `context` waits once, up to 5 retries 10 s apart, until `merge_commit_sha` has `head_sha` as its second parent. It outputs that commit as `merge_sha`, or fails with the reason (conflicts, or not ready after 50 s). `build`, `ai-review` and `ai-review-not-run` check out `merge_sha` itself, with no retry of their own; the ADR-026 preview's second-parent check still runs.
- **Intent:** `intent.yml` in dispatch mode runs `intent check` only. The bot commit touches only prose, which is not governed code.

### What the writer sees

- The Build comment of the dispatched run says: "Formatting: the bot fixed N issues in <files> as `<sha7>`; your next edit starts from it."
- When the fixer refuses, the run that did not push says: "Formatting could not be fixed automatically: <reason>". When the push fails it says "Formatting was not applied: <reason>". Either way the warnings are listed as before, and the `format` job is red.

### `contents: write`

- On `main`, writing only under `ai/`:
  - `bible-extract`;
  - the `/dismiss` job;
  - `pr-closed`, which ADR-014 and ADR-022 decided on but which is not built.
- On the head branch of a same-repository PR, writing only formatting in prose files: `format`.

## Consequences

### Positive

- Formatting is fixed without writer effort, and the fixed commit gets every check, including the required ones.
- The invariant makes "only whitespace and quotes" a checked property, not a promise.

### Negative

- A bot commit sits on the writer's branch. There are three effects:
  - A writer who opened the web editor before the bot pushed gets GitHub's "file changed" error, and must copy the text and reload.
  - A local clone must pull before its next push.
  - Every passage the fixer touches gets a new content hash. It is being re-read anyway, because the writer just changed it.
- Each PR push waits about 40 s for `format` before `build` starts.
- If the dispatch fails, the new head has no checks until the next push, and its required checks wait as "Expected" (merge blocked, never passed). The Build comment is the signal on the PR; the red `format` job belongs to the previous commit.
- A branch older than this decision is not formatted until the writer updates it from `main`, and its `format` job is red until then.
- Every PR job now takes its context from `context`. This is the largest workflow change before Oct 25.

## Alternatives Considered

1. **Continue the build on the fixed tree in the same run.** Rejected. Job check runs (`test`, `build`, `ai-review`) and `Intent` would attach to the old sha, so the required checks on the new head would wait forever.
2. **Push with an App or PAT token so CI retriggers.** Rejected: ADR-014 allows no secret.
3. **Fix on `main` after merge.** Rejected: it conflicts with writers' open branches, and it is not what was approved.
4. **Suggested changes in review comments.** Rejected in ADR-018.

## References

- ADR-014, ADR-018, ADR-021, ADR-022; `PRINCIPLES.md` §2
- `nanoif/twee/{lint,links,prose}.py`, `nanoif/github/formatting.py`, `.github/workflows/{build-and-deploy,intent}.yml`
