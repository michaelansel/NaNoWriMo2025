---
paths:
  - "*.md"
  - "docs/**"
  - "features/**"
  - "architecture/**"
---

# Documentation

- Describe current state. No changelogs, bug logs, status sections, or "recently changed"; git has the history.
- One home per fact. Link to it; do not restate it. If two docs disagree, fix the one that is not the home.
- Feature notes (`features/*.md`, via `/prd`) are 100-200 lines: user problem, stories, testable acceptance criteria, edge cases, and a one-line status. They stop at what the writer sees.
- ADRs (`architecture/NNN-*.md`, via `/adr`) record a decision and its trade-offs; a superseded ADR gets a `Superseded by` line, not a rewrite.
- `WRITING-WORKFLOW.md` stays under 150 lines and is written for a non-technical writer using the GitHub web UI. `ARCHITECTURE.md` stays under 200 lines.
- No year, repo name, real writer name, or absolute path in a doc. Examples use eval-story names and `<INITIALS>-<YYYYMMDD>`.
- Test every link you touch. A doc that links to a deleted file is a bug.
- Temporary working notes are fine while a task is open; delete them before the PR is ready.
- Reviewer agents can only read. If a review says a doc is wrong, you make the change.
