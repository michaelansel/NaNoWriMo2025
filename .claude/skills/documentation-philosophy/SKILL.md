---
name: documentation-philosophy
description: PROACTIVELY use when PERSONA SUBAGENTS (CEO, PM, Architect, Developer, HR) are creating or updating documentation artifacts. Apply when writing VISION.md, ARCHITECTURE.md, STANDARDS.md, features/*.md, or any project documentation. Persona-only skill for documentation decisions about durability, structure, and format. NOT for Router use.
---

# Documentation Philosophy (Persona Guidance)

This skill provides persona guidance on creating durable, testable documentation artifacts.

## Core Principles

**Create durable artifacts**:
- Documentation should serve as testable sources of truth for years
- Write docs you can validate against (linters, tests, audits)
- Two types of durability:
  - **Contracts** (slow-changing): Standards, principles, architecture patterns
  - **State** (evolves with code): System design, feature behavior, implementation details

**Document current state, not history**:
- Describe how things work now, not how they changed
- No bug fix logs, issue tracking, or changelogs (git provides history)
- Keep docs synchronized with code as it evolves
- If you need to understand past decisions, check git history

**Avoid transient documentation**:
- Don't create permanent handoff docs or workstream status files
- You may create temporary docs during active work, but clean them up when done
- Documents should remain relevant indefinitely, not become stale artifacts

**When to update vs consult**:
- **Update freely**: Current state descriptions, implementation notes, known limitations
- **Consult for review**: Standards, principles, architecture patterns (these are contracts - get peer input)
- **Consult with HR**: Persona definitions, boundaries, workflow structure (CLAUDE.md changes)
- Changing a standard means changing what's acceptable across the codebase - get peer feedback first
- Changing a persona means changing how the team operates—consult with HR
- If reality diverges from the standard, either fix the code or consult with peers to revise the standard
- If a persona diverges from their definition, consult with HR to clarify/update the persona

## Document Formats by Persona

### CEO Documents

**Contracts** (validate alignment against these):
- **Vision statements**: Why we exist, who we serve, what success means
- **Principles**: Core values and decision-making framework

**Current state**:
- **Strategic direction**: Current scope and focus areas with rationale
- **Priority stack rank**: Ordered list with strategic reasoning

### PM Documents (PRDs)

**Contracts** (test implementations against these):
- **Acceptance criteria**: Testable conditions that define "done"
- **User stories**: As a [user], I want [goal], so that [outcome]
- **Edge cases**: Required behaviors in exceptional scenarios

**Context** (clarifies intent):
- **User problem**: What pain point does this solve?
- **Success metrics**: How do we measure if this works?

**Keep PRDs focused** (~100-200 lines):
- Describe user-facing behavior, not system internals
- Write acceptance criteria that can be turned into automated tests
- Stop at "what happens" not "how it works technically"
- If discussing architecture/implementation, you've crossed into Architect territory
- Trust Architect to document technical design separately

### Architect Documents

**Contracts** (lint/audit code against these):
- **Coding standards**: Required patterns, forbidden anti-patterns
- **Architecture patterns**: Structural rules (layering, dependency flow, module boundaries)
- **Quality standards**: Performance budgets, security requirements, accessibility rules

**Current state** (describes how things work):
- **System design**: Components, interfaces, data flow
- **Technical design**: How features are structured
- **Rationale**: Why this approach? What forces led here?

Each design doc should capture:
- **Context**: What forces are at play? What are we trying to achieve?
- **Design**: How is this structured? Key components and relationships
- **Consequences**: What becomes easier/harder with this design?
- **Trade-offs**: What did we optimize for? What did we sacrifice?

### Developer Documents

**Current state** (describes implementation):
- **Test coverage**: What's tested, what scenarios are validated
- **Implementation notes**: Non-obvious decisions, why this approach
- **Known limitations**: Current constraints or incomplete functionality

Tests themselves serve as contracts: they define expected behavior that must not regress.

### HR Documents

**Contracts** (defines how the team operates):
- **Persona definitions in CLAUDE.md**: Focus, boundaries, invocation criteria, prompt templates
- **Workflow structure**: How personas interact, peer feedback patterns, collaboration protocols

**Current state** (describes team health):
- **Feedback pattern observations**: How are personas collaborating as peers?
- **Boundary clarifications**: When boundaries need refinement (then integrated into CLAUDE.md)

HR's primary artifact is CLAUDE.md itself—the source of truth for how personas operate. When HR identifies persona issues, the solution is to update persona definitions in CLAUDE.md, not to create separate documentation. Temporary analysis documents may exist during HR work but are cleaned up once persona definitions are updated.
