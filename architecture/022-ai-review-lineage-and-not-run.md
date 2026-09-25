# ADR-022: `ai-review.json`, review lineage, and results that did not run

## Status

Status: Accepted
Supersedes: ADR-019

## Context

ADR-019 made `ai-review.json` the only contract between the editors and the GitHub reporter and said `/dismiss` re-renders from "the last" uploaded artifact. Three gaps in that decision surfaced before November:

- `/check-continuity passage=<name>` rendered one passage's review as the whole result, so one clean passage turned a check green while other changed passages still had findings.
- When a push's build or runner probe failed, `ai-review` was skipped and the previous push's editor comments (possibly "No findings") stayed up as if current; the same happened to the Build comment when an early build step failed.
- `ai-review.json` records `commit_sha`, which on a `pull_request` run is GitHub's merge commit, not the pull-request head, so nothing said which push a stored review belongs to.

## Decision

`nanoif ai review --mode changed|all|passage` writes `ai-review.json`, validated against `nanoif/schemas/artifacts/ai_review.schema.json` (`version: 1`). It is the only contract between the editors and the GitHub reporter (`nanoif/github/`), which renders the sticky comments and check runs from it (ADR-014).

- **Shape.** `{version, generated_at, commit_sha, base_sha, mode, llm, editors[]}`; `llm` is `usage_summary()` plus the runner (`exe|hosted|local`). Each editor (`continuity`, `style`) has `status`, `reason`, `units[]`, `findings[]`, `suppressed[]`, `unverified[]`.
- **Honest status.** Editor `ok` means every unit was reviewed; `error` means at least one unit could not be; `skipped` means the editor did not run, with a reason. `nanoif.review.runner.editor_status` is the one function that derives editor status from units; the runner and the merge both call it. Unit status is `reviewed`, `error` or `skipped` with a reason. A unit is re-attempted once after an `LLMError`, then marked `error`. Zero findings is a pass only when the editor is `ok`.
- **Review units** (`nanoif.review.units`). Continuity: one unit per changed passage P (from `dist/changes.json`, ADR-017), holding P plus its ancestors in topological order, non-dominating ancestors marked, names replaced by passage ids. Over the unit token budget (default 20k, `NANOIF_REVIEW_UNIT_BUDGET`) it splits into at most 4 routes by greedy cover, then keeps the last 12 passages with a note, then is `skipped` as too long. Style: one unit per changed passage. Infrastructure passages are never units or context.
- **Findings.** Key `f-` + first 8 hex of SHA-256 of `type|a|b`, `a` and `b` the two passage names sorted. The same key from several units merges into one finding (`routes_seen`). Code, not the model, drops findings that do not involve P, verifies every quote (failures go to `unverified`, shown collapsed, never counted), and clamps severity by type.
- **The review artifact.** Each PR review uploads artifact `ai-review-pr-<N>` (90 days) holding `ai-review.json` and `ai-review-head-sha.txt`, the pull-request head the review is for. The sidecar is the only record of the head; a missing or unreadable sidecar means "commit unknown", never "same commit". "The last review" of a PR is its newest unexpired `ai-review-pr-<N>` artifact, found by `gh api .../actions/artifacts?name=`; jobs that look it up have `actions: read`.
- **Passage re-check lineage.** `/check-continuity passage=X` downloads the last review and runs `nanoif github merge-review` (`nanoif/github/merge.py`). Only when the sidecar equals the current head does it merge: X's units and every finding only X's unit could have made are replaced, everything else is kept (a finding that names another reviewed passage is kept, so a merge may repeat a finding, never hide one), editor status is recomputed, and the result keeps the earlier `mode` and is uploaded as the new last review. Otherwise the re-check is published alone as `mode: passage`, labelled "partial", and each editor's check run concludes `failure`: the other passages of this commit were not checked by it. A failed download (the step is `continue-on-error`) is reported by the merge step as a `::warning::`, a step-summary line, and the partial comment.
- **Did not run.** When `build` or `probe` does not succeed (including an invalid `vars.AI_RUNNER`, which the probe names), a hosted `ai-review-not-run` job (`if: !cancelled()`, `contents: read`, `pull-requests: write`, `checks: write`; in `build-and-deploy.yml` and, for `/check-continuity`, in `ai-command.yml`) runs `nanoif github not-run`: both editor comments say the review did not run for that commit and show no earlier result, both check runs on that commit fail, and the job exits 1. It uploads no artifact, so the last review stays an older commit's.
- **Re-rendering is head-checked.** Any re-render of a stored review without a model call (`/dismiss`) publishes comments and check runs only when the artifact's sidecar equals the current pull-request head, and posts check runs on that head explicitly. Otherwise it records the dismissal, leaves the comments alone, and says the next review will show it.
- **Dismissals.** `/dismiss <key> [reason]` appends `{key, passages with content_hash, by, pr, at, reason}` to `ai/dismissals.jsonl` on main, refusing a key that is not in the last review. A finding moves to `suppressed` while some dismissal of its key recorded the current `content_hash` of every passage it names. Intentional conflicts from `story-overrides.txt` suppress canon findings the same way once the canon pack exists (ADR-020).
- **Outcomes.** On merge, `pr-closed` appends each finding's outcome (`dismissed`, `fixed`, `ignored-at-merge`) to `ai/outcomes.jsonl`.
- **Build & Structure report** (ADR-014, ADR-018). The report step runs on `!cancelled()`, retries the package install with a warning if it is missing, and is told the structure step's outcome; without a structure result the comment says structure was not checked and the `Structure` check on the head fails.

## Consequences

### Positive

- A single-passage re-check can no longer make a check greener than the whole commit deserves.
- A failed build, probe or runner setting replaces stale editor results within the same run.
- The head sha makes "is this stored review about this push?" answerable, so merges and re-renders can refuse stale input.

### Negative

- Two contradictions between the same pair and type share one key. A schema change still needs `version` bumped and the reporter updated together.
- The head sha lives in an unvalidated sidecar rather than in the schema; it fails safe (unknown means not merged, not re-rendered). Moving it into `ai-review.json` is a `version: 2` change.
- A partial re-check shows red even when X is clean; `/check-continuity` restores the full picture.
- Accepted gap: if checkout, `setup-python` or the retried install fails, the Build report step cannot run and the previous Build comment stays; the `build` check on the new head is red. Every such cause (GitHub or PyPI outage) would also stop a separate report job on base-branch tooling, so that job is not built. Revisit if it is seen with the package installable.
- Accepted risk: `ai-review` in `ai-command.yml` and in `build-and-deploy.yml` use different concurrency groups, so a re-check of an older head can finish after a newer push's review and overwrite its comments; its check runs land on the older head, and the next merge or `/dismiss` refuses the stale artifact.

## Alternatives Considered

1. **Re-run the whole changed review for `passage=X`**: correct but costs every unit; the command exists to be cheap.
2. **Merge into any last review regardless of head**: shows an earlier push's results as current.
3. **Separate hosted Build report job on base tooling**: closes no failure mode that the in-job step leaves open, since both need checkout and install.
4. **Treat a partial re-check as neutral**: a download failure could then turn an earlier `failure` on the same commit into `neutral`.

## References

- ADR-014, ADR-016, ADR-017, ADR-018, ADR-020; `nanoif/review/`, `nanoif/github/merge.py`, `nanoif/github/report.py`
- `.github/actions/ai-review/action.yml`, `.github/workflows/build-and-deploy.yml`, `.github/workflows/ai-command.yml`
