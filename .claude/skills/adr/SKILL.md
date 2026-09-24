---
name: adr
description: Write an architecture decision record in architecture/. Use after an architect consult that changes a module boundary, workflow job, persistent state, dependency, or data contract.
arguments: slug
---

# Architecture decision record

Existing ADRs (the next number is one past the highest):

!`ls "${CLAUDE_PROJECT_DIR}"/architecture/ 2>/dev/null | grep -E '^[0-9]{3}-' | sort | tail -5`

Write `architecture/NNN-$ARGUMENTS.md` using the template below. Read `ARCHITECTURE.md` and any ADR this one touches first. If this decision replaces an earlier ADR, change that ADR's `Status:` line to `Superseded by ADR-NNN` and leave the rest of it alone. `nanoif intent check --repo .` must pass afterwards.

## Template

```markdown
# ADR-{number}: {Title}

Status: {Proposed | Accepted | Superseded by ADR-NNN}

## Context

Background and motivation for this decision.
What problem are we solving?

## Decision

The decision we made and why.
What specific approach did we choose?

## Consequences

Positive and negative outcomes of this decision.

### Positive

- Benefit 1
- Benefit 2

### Negative

- Trade-off 1
- Trade-off 2

## Alternatives Considered

1. **Alternative 1**: Why rejected
2. **Alternative 2**: Why rejected

## References

- Related docs
- External resources
```

Naming: `{number}-{slug}.md`, sequential three-digit number, lowercase hyphenated slug. Keep it under 150 lines; an ADR records a decision, it is not a design document. If `ARCHITECTURE.md` describes the affected area, update it in the same PR.
