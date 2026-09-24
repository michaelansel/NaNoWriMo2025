---
name: documentation-philosophy
description: How this repo writes docs that stay true. Loaded for the reviewer agents and whenever a Markdown doc, feature note, or ADR is being created or changed.
user-invocable: false
paths:
  - "*.md"
  - "features/**"
  - "architecture/**"
  - "docs/**"
---

# Documentation philosophy

## Core principles

**Create durable artifacts**
- A doc is something you can validate against: a linter, a test, an eval, a checklist, an audit.
- Two kinds of durability: contracts (slow-changing: principles, acceptance criteria, data contracts, ADRs) and state (evolves with the code: architecture, feature behavior, setup).

**Document current state, not history**
- Say how things work now. No bug-fix logs, no "changed in", no status timelines; git provides history.
- Keep state docs synchronized with the code in the same PR that changes the behavior.

**Avoid transient documentation**
- No permanent handoff notes, workstream trackers, or "next steps" files.
- Working notes during a task are fine; delete them before the PR is ready.

**One home per fact**
- Each concern has one authoritative doc. Others link to it rather than restating it.
- When two docs disagree, the non-home doc is the bug.

**Change contracts deliberately**
- Update state docs freely.
- A contract change (acceptance criteria, data contract, principle, hard rule) gets a reviewer consult per the delegation table in `CLAUDE.md`, and an ADR when it changes how the system is shaped.
- If reality diverges from a contract, either fix the code or change the contract in the open; do not leave both standing.

## Formats

- **Vision, principles, priorities** (`VISION.md`, `PRINCIPLES.md`, `PRIORITIES.md`): why we exist, how we decide, what matters now in rank order with dates.
- **Feature notes** (`features/*.md`, `/prd`): user problem, user stories, testable acceptance criteria, edge cases, one status line. Stop at what the writer sees; implementation belongs in an ADR or the code.
- **ADRs** (`architecture/NNN-*.md`, `/adr`): context, decision, consequences, alternatives. Superseded ADRs get a pointer, not a rewrite.
- **Writer docs** (`README.md`, `CONTRIBUTING.md`, `WRITING-WORKFLOW.md`): written for a non-technical writer in the GitHub web UI.
- **Tests and eval baselines** are contracts too: `tests/fixtures/eval-story/truth.json` defines what the AI must get right.
