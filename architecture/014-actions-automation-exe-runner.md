# ADR-014: GitHub Actions automation with a self-hosted exe.dev runner for AI jobs

## Status

Status: Accepted
Supersedes: ADR-003, ADR-005, ADR-013

## Context

AI review used to run in a long-lived webhook service (Flask, GitHub App auth, artifact downloads, commits through the Contents API) next to a GPU host that no longer exists. It had to stay alive unattended, failed silently when it was down, committed to writers' PR branches, and duplicated what Actions already gives: check runs, `author_association`, concurrency, durable logs. The default inference backend is now the exe.dev LLM gateway, which is reachable without a key only from an exe.dev VM. There is no paid fallback key.

## Decision

All automation is GitHub Actions. There is no webhook service, GitHub App, PAT or repository secret.

- **Hosted runners** run everything deterministic: `build` (tweego, `nanoif build`, `nanoif check structure`, `nanoif lint`), `test` (pytest + ruff, required), `render-and-deploy` to Pages, `probe`, and `Intent` (ADR-021).
- **A self-hosted runner on an exe.dev VM** (labels `self-hosted`, `exe`) runs only the AI jobs: `ai-review` on PRs, the `ai-command.yml` job, `bible-extract` on main, and the `ai-maintenance.yml` tasks. They use `NANOIF_LLM_PROFILE=exe` against the gateway. The VM holds the runner and `deploy/exe/healthz.py` and nothing secret; setup is `deploy/exe/setup.sh`, the runbook is `docs/exe-runner.md`.
- **Probe, never queue.** A hosted `probe` job curls `vars.EXE_HEALTH_URL` (5 s) and outputs `runner=exe|hosted`; `vars.AI_RUNNER` can force either. AI jobs take `runs-on` from it. On `hosted` the job does not call a model: it writes the sticky comment "AI review unavailable" with the reason, and its check fails. AI jobs have `timeout-minutes: 45`. `ai-maintenance` `runner-check` runs daily in November and opens or updates a tracking issue on failure.
- **No automation commits to a PR branch.** Workflows default to `contents: read`. Exactly three jobs have `contents: write`, all on `main`, all writing only under `ai/`: `bible-extract` (`ai/story-bible-cache.json`), the `/dismiss` job (`ai/dismissals.jsonl`), and `pr-closed` (`ai/outcomes.jsonl`). A rejected push rebases and retries once, then fails visibly.
- **No paid inference from an unauthenticated trigger.** AI jobs run only for same-repository PRs; fork workflows need approval (repository setting). `issue_comment` commands (`/check-continuity [all] [passage=<name>]`, `/extract-story-bible`, `/dismiss <key> [reason]`) run only when `author_association` is `OWNER`, `MEMBER` or `COLLABORATOR`. No `pull_request_target`.
- **One sticky comment per check type per PR**, found by an HTML marker and edited in place: `<!-- nano:build -->` for Build and Structure, `<!-- nano:<editor> -->` for each editor in `ai-review.json` (`nano:continuity`, `nano:style`). Never found by footer text. Each type also has a check run: success = pass, neutral = findings, failure = could not run (and broken links for Structure).
- **No hidden failure.** No `|| true`, `exit 0` or `continue-on-error` that hides a failure; a step allowed to fail without blocking still leaves a check, comment or step-summary line.
- Concurrency `ci-pr-<N>` and `ai-cmd-pr-<N>` cancel in progress on PRs, never on main. Every workflow has `workflow_dispatch`. Tool versions are pinned in one `env:` block.

## Consequences

### Positive

- Nothing long-lived to babysit except one runner, and its absence is loud within seconds.
- No key to leak or fund; the gateway's included tokens pay for inference.
- Writers' branches only ever contain writers' commits.

### Negative

- If the VM or gateway is down, there is no AI review until it is back; structural checks still run.
- A self-hosted runner on a public repository depends on the fork-approval setting being on.
- Main-branch jobs push to `main`; if `main` gets protection against Actions pushes, `ai/` must move to a data branch.

## Alternatives Considered

1. **Keep the webhook service on the VM**: moves one execution host but keeps 2.6k lines of plumbing and an SRE duty.
2. **Hosted runners with a paid provider key**: simplest, but the user declined a key; the profile stays available for local use.
3. **Self-hosted runner without a probe**: an offline runner makes jobs queue silently forever.
4. **Fallback to a paid provider when the VM is down**: declined with the key.

## References

- ADR-016 (LLM client), ADR-019 (`ai-review.json`), ADR-021 (Intent CI)
- `docs/exe-runner.md`, `deploy/exe/`, `.claude/rules/workflows.md`
