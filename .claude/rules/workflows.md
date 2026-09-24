---
paths:
  - ".github/**"
---

# GitHub Actions

- Nothing pushes to a PR branch. Only `bible-extract`, the `/dismiss` job, and `pr-closed` have `contents: write`, and they write only under `ai/` on `main`. PR builds run with `contents: read`.
- No `|| true`, `exit 0`, or `continue-on-error` that hides a failure. If a step may fail without blocking, it must still produce a visible check run, comment, or step-summary line saying what did not run.
- Every AI job: `if: github.event.pull_request.head.repo.full_name == github.repository`, `timeout-minutes: 45`, `runs-on` from the `probe` job's output, and a sticky "unavailable" comment plus non-zero exit when the runner is offline.
- `issue_comment` handlers check `author_association` in `OWNER, MEMBER, COLLABORATOR` before anything that spends tokens.
- Sticky comments are found by HTML marker (`<!-- nano:build -->`, `<!-- nano:continuity -->`, `<!-- nano:style -->`) and edited in place; one per check type per PR.
- Concurrency: `ci-pr-${{ github.event.number }}` and `ai-cmd-pr-N`, cancel-in-progress on PRs; never on main.
- Pin tool versions in one top-level `env:` block (tweego, Harlowe URL + sha256, dotgraph) and actions by major tag. Python 3.13 with pip cache on hosted runners (the exe VM uses a venv); `pip install -e ".[dev]"`, never rely on the runner image.
- Every workflow has `workflow_dispatch`. Maintenance tasks are inputs to `ai-maintenance.yml`, not new workflows.
- No `pull_request_target`. No secrets in the AI jobs; the exe profile needs none.
- A workflow change is tested by a PR that exercises the changed path, and the PR description links the run.
- Run `actionlint` before committing when it is installed; the edit hook does this for you.
