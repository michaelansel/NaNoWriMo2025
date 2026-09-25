# ADR-019: `ai-review.json`, review units, finding keys and dismissals

## Status

Status: Superseded by ADR-022

## Context

Earlier AI review checked whole paths, so one contradiction was reported once per path that contained it (a PR once got 60+ bot comments), findings had random ids so nothing could be dismissed durably, and a failed call rendered as a clean result. The editors and the code that talks to GitHub also need to be built and tested separately: the editors run on the exe runner, and a `/dismiss` must re-render a comment without calling a model.

## Decision

`nanoif ai review --mode changed|all|passage` writes `ai-review.json`, validated against `nanoif/schemas/artifacts/ai_review.schema.json` (`version: 1`). It is the only contract between the editors and the GitHub reporter, which renders the sticky comments and check runs from it (ADR-014). The file is uploaded as a workflow artifact; `/dismiss` re-renders from the last one.

- **Shape.** `{version, generated_at, commit_sha, base_sha, mode, llm, editors[]}`; `llm` is `usage_summary()` plus the runner (`exe|hosted|local`). Each editor (`continuity`, `style`) has `status`, `reason`, `units[]`, `findings[]`, `suppressed[]`, `unverified[]`.
- **Honest status.** Editor `ok` means every unit was reviewed; `error` means at least one unit could not be; `skipped` means the editor did not run, with a reason. Unit status is `reviewed`, `error` or `skipped` with a reason (provider error, too long). A unit is re-attempted once after an `LLMError`, then marked `error`. Zero findings is a pass only when the editor is `ok`.
- **Review units** (`nanoif.review.units`). Continuity: one unit per changed passage P (from `dist/changes.json`, ADR-017), holding P plus its ancestors in the story graph in topological order, non-dominating ancestors marked, names replaced by passage ids. Over the unit token budget (default 20k, `NANOIF_REVIEW_UNIT_BUDGET`) it splits into at most 4 routes by greedy cover, then keeps the last 12 passages with a note, then is `skipped` as too long. Style: one unit per changed passage. Infrastructure passages are never units or context.
- **Findings.** Key `f-` + first 8 hex of SHA-256 of `type|a|b`, `a` and `b` the two passage names sorted (`a == b` for single-passage findings). The same key from several units merges into one finding (`routes_seen`). Code, not the model, drops findings that do not involve P, verifies every quote against the cited passage (failures go to `unverified`, shown collapsed and never counted), and clamps severity by type.
- **Dismissals.** `/dismiss <key> [reason]` appends `{key, passages with content_hash, by, pr, at, reason}` to `ai/dismissals.jsonl` on main. A finding is moved to `suppressed` while some dismissal of its key recorded the current `content_hash` of every passage it names; editing either passage brings it back. Intentional conflicts from `story-overrides.txt` suppress canon findings the same way once the canon pack exists (ADR-020).
- **Outcomes.** On merge, `pr-closed` appends each finding's outcome (`dismissed`, `fixed`, `ignored-at-merge`) to `ai/outcomes.jsonl` to measure false positives.

## Consequences

### Positive

- One contradiction is one finding with one stable key, however many routes contain it.
- The reporter is testable from fixture JSON with no model; the editors are testable with `FakeLLM` and no GitHub.
- "Could not check" has a place in the data, so it has a place in every comment.

### Negative

- Two distinct contradictions between the same passage pair and type share one key; they render as bullets of one finding.
- A schema change needs `version` bumped and the reporter updated in the same change.

## Alternatives Considered

1. **Editors post comments directly**: couples model code to the GitHub API and makes `/dismiss` re-run the model.
2. **Random finding ids**: no durable dismissal.
3. **Path-level units**: the duplication and cost this replaces.

## References

- ADR-014, ADR-016, ADR-017, ADR-020; `nanoif/review/` (being built)
