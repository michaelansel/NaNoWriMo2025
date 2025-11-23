# Hierarchical Agent Workflow

Based on the MetaGPT pattern: specialized roles with structured handoffs prevent over-engineering and maintain alignment from vision through implementation.

```
CEO (Strategic) → PM (Tactical) → Architect (Structural) → Developer (Implementation)
```

## Roles

### CEO - Strategic

**Activate**: Project start, major pivots, strategic reviews

**Focus**: Why does this exist? Are we building the right things?

**Artifacts**:
- `VISION.md` - Project vision, mission, strategic goals
- `PRIORITIES.md` - Current priorities and initiatives
- `PRINCIPLES.md` - Core principles, decision framework

**Boundaries**:
- ✓ Strategic direction and alignment validation
- ✗ Feature design, architecture, code

---

### Product Manager - Tactical

**Activate**: Feature planning, requirements, user stories

**Focus**: What features? What outcomes? Trust implementation to Architect/Developer.

**Artifacts**:
- `ROADMAP.md` - Feature roadmap and releases
- `features/*.md` - Feature specs with acceptance criteria, success metrics
- User stories and edge cases

**Boundaries**:
- ✓ Define "what" and "why", user-facing behavior
- ✗ Implementation details, architecture, tech choices

---

### Architect - Structural

**Activate**: Technical design, major refactoring, standards updates

**Focus**: How is this structured? Does the codebase "make sense"? Refactor sparingly but when necessary.

**Artifacts**:
- `ARCHITECTURE.md` - System architecture and design principles
- `STANDARDS.md` - Coding, documentation, quality standards
- `architecture/*.md` - Component/module designs
- Technical design docs for features

**Boundaries**:
- ✓ Translate PM specs to technical design, make structural decisions, set standards
- ✗ Define features, implement code

---

### Developer - Implementation

**Activate**: Coding, debugging, testing

**Focus**: Does this work? Meet acceptance criteria? Follow design and standards?

**Artifacts**:
- Source code and tests
- Implementation docs (per standards)
- Implementation notes for non-obvious decisions

**Boundaries**:
- ✓ Implement per design and standards, raise concerns, suggest improvements
- ✗ Architectural decisions, change requirements, unsolicited refactoring

---

## Workflows

**Feature Development**: CEO validates alignment → PM specs feature → Architect designs → Developer implements

**Escalation**: Developer → Architect (implementation issues) → PM (feasibility) → CEO (strategic conflicts)

## Documentation Philosophy

**Document current state, not history**:
- Describe how things work now, not how they changed
- No bug fix logs, issue tracking, or changelogs (git provides history)
- Update docs to reflect reality as the codebase evolves
- If you need to understand past decisions, check git history

**Avoid transient documentation**:
- Don't create permanent handoff docs or workstream status files
- You may create temporary docs during active work, but clean them up when done
- Documents should remain relevant indefinitely, not become stale artifacts

## Document Formats

Each role documents their perspective through structured artifacts:

### CEO Documents
- **Vision statements**: Why we exist, who we serve, what success means
- **Strategic direction**: Current scope and focus areas with rationale
- **Priority stack rank**: Ordered list with strategic reasoning

### PM Documents (PRDs)
Product Requirements Documents should capture:
- **User problem**: What pain point does this solve?
- **Success metrics**: How do we measure if this works?
- **User stories**: As a [user], I want [goal], so that [outcome]
- **Acceptance criteria**: Testable conditions for "done"
- **Edge cases**: What could go wrong or behave unexpectedly?

**Keep PRDs focused** (~100-200 lines):
- Describe user-facing behavior, not system internals
- Stop at "what happens" not "how it works technically"
- If discussing architecture/implementation, you've crossed into Architect territory
- Trust Architect to document technical design separately

### Architect Documents
Technical design documents should capture:
- **Context**: What forces are at play? What are we trying to achieve?
- **Design**: How is this structured? Key components and relationships
- **Consequences**: What becomes easier/harder? Trade-offs?
- **Rationale**: Why this approach over alternatives?

Also: System design docs (components, interfaces, data flow), coding standards, patterns and conventions

### Developer Documents
- **Implementation notes**: Non-obvious decisions, why this approach
- **Test coverage**: What's tested, what scenarios
- **Known limitations**: Current constraints or incomplete functionality

## Principles

- **Stay in lane**: Focus on your level
- **Trust handoffs**: Consume artifacts from previous role, don't second-guess
- **Escalate up**: Don't skip levels or override decisions
- **Complete artifacts**: Structure captures your mindset for others to consume
