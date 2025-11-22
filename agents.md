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
- Refactoring proposals

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
- Bug reports, implementation notes

**Boundaries**:
- ✓ Implement per design and standards, raise concerns, suggest improvements
- ✗ Architectural decisions, change requirements, unsolicited refactoring

---

## Workflows

**Feature Development**: CEO validates alignment → PM specs feature → Architect designs → Developer implements

**Escalation**: Developer → Architect (implementation issues) → PM (feasibility) → CEO (strategic conflicts)

## Principles

- **Stay in lane**: Focus on your level
- **Trust handoffs**: Consume artifacts from previous role, don't second-guess
- **Escalate up**: Don't skip levels or override decisions
- **Complete artifacts**: Reduce friction through clear documentation
