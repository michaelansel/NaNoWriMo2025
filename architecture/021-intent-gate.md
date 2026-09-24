# ADR-021: The intent gate: owned layers, criterion ids, test citations, commit trailer

## Status

Status: Accepted
Supersedes: ADR-006

## Context

Documents drifted from the code for a year: feature notes described checks that no longer ran, ADRs described a service that was gone, and nothing noticed. Most changes here are made by agents, which follow what is written and do not notice drift either. Intent has to be owned, addressable and checked by a machine, or it rots.

## Decision

Intent lives in three layers, each written only by its owner: why (`VISION.md`, `PRINCIPLES.md`, `PRIORITIES.md`; `ceo` drafts, the user approves), what (`features/*.md`; `pm`), how (`ARCHITECTURE.md`, `architecture/NNN-*.md`; `architect`). Owner agents are restricted to their layer by a write-scope hook (`.claude/hooks/scope-writes.sh`).

- **Criterion ids.** Every acceptance criterion is one line `- AC-<note-file-stem>-<n>: ...`, optionally ending `(verify: test|workflow|manual|planned)`; the default is `test`. Ids are unique and never reused. A feature note with no criteria is an error.
- **ADR status.** Every `architecture/NNN-<slug>.md` has a `Status:` line: `Proposed`, `Accepted`, or `Superseded by ADR-NNN` naming an ADR that exists. Numbers are unique. A changed decision is a new ADR; the old one only gets its status changed.
- **Test citations.** A test proves a criterion or ADR with `@pytest.mark.intent("AC-...", "ADR-NNN")`. Every `verify: test` criterion must be cited; every citation must resolve. `planned` is reported as info.
- **`nanoif intent check --repo .`** (`nanoif.intent.check`) enforces the three rules above.
- **Commit trailer.** A commit that changes governed code (`nanoif/`, `.github/`, `scripts/`, `deploy/`, `landing/`, `pyproject.toml`, infrastructure passages) and no intent document must carry `Intent: unchanged (<reason>)` with a non-empty reason (`nanoif.intent.gate`). Tests, writer prose, writer docs and `.claude/` are not governed.
- **Enforcement.** Locally, `.githooks/commit-msg` runs `nanoif intent commit-msg` (enabled by the session-start hook via `core.hooksPath`); if `nanoif` is not importable it says the commit was not checked. In CI, the `Intent` workflow (hosted, `contents: read`) runs `intent check` and `intent range` over every non-merge commit of the PR or push. `--no-verify` is forbidden; CI is the backstop.

## Consequences

### Positive

- Drift fails a check instead of waiting for a reader to notice.
- Every behaviour a writer relies on points at the test that proves it.
- Removing a criterion or decision is always an explicit edit by its owner.

### Negative

- Every governed commit costs a trailer or a doc edit, including trivial ones.
- The gate checks that intent moved or was declared unchanged, not that the declaration is true; review still has to read it.
- Citations are matched by id only; a test can cite a criterion it does not really prove.

## Alternatives Considered

1. **Review-only discipline**: already failed.
2. **Requirements in a tracker**: invisible to the agents that change the code.
3. **Block every governed commit without a doc change**: pushes people to make meaningless doc edits; the trailer records the reason instead.

## References

- `CLAUDE.md` ("Intent is owned and traceable"), `.claude/rules/docs.md`, `nanoif/intent/`, `.github/workflows/intent.yml`, `tests/test_intent.py`
