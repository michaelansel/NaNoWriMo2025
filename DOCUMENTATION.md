# Documentation Guide

## Overview

This project uses a hierarchical documentation model based on the MetaGPT pattern: specialized roles with structured handoffs prevent over-engineering and maintain alignment from vision through implementation.

```
CEO (Strategic) → PM (Tactical) → Architect (Structural) → Developer (Implementation)
```

Each role has specific documentation artifacts that capture their perspective and decisions.

---

## Documentation Hierarchy

### Tier 1: Strategic (CEO)

**Audience:** Project leadership, stakeholders, strategic decision-makers

**Documents:**
- **[VISION.md](VISION.md)** - Project mission, goals, and north star
- **[PRIORITIES.md](PRIORITIES.md)** - Stack-ranked priorities for current phase
- **[PRINCIPLES.md](PRINCIPLES.md)** - Core principles guiding all decisions

**Purpose:** Define WHY the project exists, WHAT we value, and WHERE we're headed strategically.

---

### Tier 2: Product (PM)

**Audience:** Product managers, feature planners, UX designers

**Documents:**
- **[ROADMAP.md](ROADMAP.md)** - Feature roadmap, releases, and timelines
- **[features/](features/)** - Product requirement documents (PRDs) for each feature
  - `ai-continuity-checking.md`
  - `automated-build-deploy.md`
  - `automated-resource-tracking.md`
  - `collaborative-workflow.md`
  - `github-web-editing.md`
  - `multiple-output-formats.md`
  - `path-validation-cache.md`

**Purpose:** Define WHAT features exist, WHO they serve, and HOW we measure success (acceptance criteria, metrics).

---

### Tier 3: Architecture (Architect)

**Audience:** Architects, technical leads, senior engineers

**Documents:**
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - System architecture and design principles
- **[STANDARDS.md](STANDARDS.md)** - Coding standards, documentation requirements
- **[architecture/](architecture/)** - Architecture decision records (ADRs)
  - `001-allpaths-format.md` - AllPaths format for AI validation
  - `002-validation-cache.md` - Validation cache and selective modes
  - `003-webhook-service.md` - GitHub webhook service architecture
  - `004-content-hashing.md` - Content-based change detection
  - `005-github-actions-workflow.md` - CI/CD pipeline design
  - `006-documentation-cleanup.md` - Documentation structure decisions

**Purpose:** Define HOW the system is structured, WHY we made technical decisions, and WHAT trade-offs we accepted.

---

### Tier 4: Implementation (Developer)

**Audience:** Developers, contributors, implementers

**Documents:**
- **Code comments** - Implementation rationale and non-obvious decisions
- **Service READMEs** - Operational guides (setup, configuration, troubleshooting)
  - [services/README.md](services/README.md) - Webhook service setup
- **Format READMEs** - Technical specifications for data formats
  - [formats/allpaths/README.md](formats/allpaths/README.md) - AllPaths format spec

**Purpose:** Guide actual implementation, setup, and operation of the system.

---

### Tier 5: User Documentation (Writers/Contributors)

**Audience:** Story writers, content contributors

**Documents:**
- **[README.md](README.md)** - Project overview and quick start
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - How to contribute story content
- **[WRITING-WORKFLOW.md](WRITING-WORKFLOW.md)** - Daily writing workflow checklist

**Purpose:** Enable writers to contribute without technical expertise.

---

### Tier 6: Meta-Documentation (Development Process)

**Audience:** Developers using hierarchical agent workflow

**Documents:**
- **[CLAUDE.md](CLAUDE.md)** - Hierarchical agent workflow guide

**Purpose:** Explain how to use the CEO→PM→Architect→Developer pattern when working on the project.

---

## Finding What You Need

### "I want to contribute a story passage"

Start with [README.md](README.md), then [CONTRIBUTING.md](CONTRIBUTING.md) for detailed steps.

Daily checklist: [WRITING-WORKFLOW.md](WRITING-WORKFLOW.md)

---

### "I want to understand why this project exists"

Read [VISION.md](VISION.md) and [PRINCIPLES.md](PRINCIPLES.md) to understand our mission and values.

---

### "I want to know what features are planned"

Check [ROADMAP.md](ROADMAP.md) for released features, active development, and future plans.

Detailed feature specs: [features/](features/) directory

---

### "I want to understand how the system works"

Read [ARCHITECTURE.md](ARCHITECTURE.md) for system overview.

Deep dive on specific decisions: [architecture/](architecture/) ADRs

Technical standards: [STANDARDS.md](STANDARDS.md)

---

### "I want to implement a feature"

1. Read the PRD in [features/](features/)
2. Review related ADRs in [architecture/](architecture/)
3. Follow [STANDARDS.md](STANDARDS.md) for coding/docs
4. Use [CLAUDE.md](CLAUDE.md) for hierarchical development workflow

---

### "I want to set up a service"

Check the README.md in the relevant directory:
- [services/README.md](services/README.md) - Webhook service setup
- [formats/allpaths/README.md](formats/allpaths/README.md) - AllPaths format

---

## Document Lifecycle

### Strategic Docs (CEO)

- **Updated:** Major phase transitions, strategic pivots
- **Owner:** CEO role
- **Review:** Quarterly or on major changes

**Example Triggers:**
- Completing NaNoWriMo and shifting to editing phase
- Deciding to support additional story formats
- Changing target audience

---

### Product Docs (PM)

- **Updated:** Feature launches, roadmap changes
- **Owner:** PM role
- **Review:** Monthly or per feature

**Example Triggers:**
- Launching new feature (update ROADMAP.md)
- Feature reaching "Released" status (update PRD)
- Changing acceptance criteria based on usage

---

### Architecture Docs (Architect)

- **Updated:** Major technical decisions, refactoring
- **Owner:** Architect role
- **Review:** Per ADR or major change

**Example Triggers:**
- Choosing new technology or pattern (create ADR)
- Major refactoring (update ARCHITECTURE.md)
- Changing coding standards (update STANDARDS.md)

---

### User Docs

- **Updated:** Feature changes, workflow improvements
- **Owner:** PM/Architect (depending on content)
- **Review:** After each user-facing change

**Example Triggers:**
- New workflow command available
- Contribution process changes
- Setup instructions updated

---

## Documentation Principles

Following [PRINCIPLES.md](PRINCIPLES.md) and [STANDARDS.md](STANDARDS.md):

### 1. Single Source of Truth

Each concern has one authoritative document. Cross-reference, don't duplicate.

**Example:**
- Validation cache architecture → `architecture/002-validation-cache.md`
- Path validation feature → `features/path-validation-cache.md`
- Operational setup → `services/README.md` (references the above)

---

### 2. Hierarchical Clarity

Respect role boundaries (CEO→PM→Architect→Developer). Don't skip levels or override decisions.

**Example:**
- CEO defines "Writers First" principle
- PM creates GitHub web editing feature (aligned with principle)
- Architect designs zero-install browser-based workflow
- Developer implements file editing UI

---

### 3. Cross-Reference, Don't Duplicate

Link to authoritative sources rather than copying content.

**Example:**
- `services/README.md` references `architecture/002-validation-cache.md` for design decisions
- `CONTRIBUTING.md` references `PRINCIPLES.md` for philosophy
- `README.md` references `ROADMAP.md` for features

---

### 4. Audience-Focused

Write for the intended reader. Different tiers serve different audiences.

**Example:**
- `VISION.md` uses strategic language (goals, mission, impact)
- `features/*.md` uses product language (user stories, acceptance criteria)
- `architecture/*.md` uses technical language (trade-offs, alternatives, consequences)
- `CONTRIBUTING.md` uses beginner-friendly language (step-by-step, examples)

---

### 5. Living Documents

Keep current, archive deprecated content. Update docs when reality changes.

**Example:**
- Feature status in `ROADMAP.md` updated when shipped
- ADRs marked "Superseded" when replaced
- Architecture docs updated after refactoring

---

## Diagram: Documentation Flow

```
VISION.md (Why we exist)
    ↓
PRIORITIES.md (What matters now)
    ↓
PRINCIPLES.md (How we decide)
    ↓
ROADMAP.md (What we're building)
    ↓
features/*.md (Product specs)
    ↓
ARCHITECTURE.md (System design)
    ↓
architecture/*.md (Design decisions)
    ↓
STANDARDS.md (How to build)
    ↓
Code (Implementation)
```

Each level informs the next, creating alignment from vision through implementation.

---

## When to Create New Documentation

### Create a New PRD (features/*.md) When:

- Adding a new user-facing feature
- Feature has distinct user stories and acceptance criteria
- Feature requires its own success metrics

**Don't create a PRD for:**
- Minor enhancements to existing features (update existing PRD)
- Internal refactoring (create ADR instead)
- Bug fixes (document in code or issue tracker)

---

### Create a New ADR (architecture/*.md) When:

- Making a major technical decision with long-term impact
- Choosing between multiple architectural approaches
- Decision has significant trade-offs to document
- Future developers will ask "why did we do it this way?"

**Don't create an ADR for:**
- Routine implementation choices
- Decisions easily explained in code comments
- Temporary workarounds

---

### Update README.md When:

- Onboarding flow changes
- Quick start steps modified
- New output format added

**Don't update README.md for:**
- Detailed feature documentation (use features/*.md)
- Implementation details (use architecture/*.md)

---

## Common Documentation Tasks

### Adding a New Feature

1. **PM creates PRD** in `features/new-feature.md`
2. **Architect creates ADR** (if needed) in `architecture/NNN-new-feature.md`
3. **PM updates ROADMAP.md** with feature status
4. **Developer implements** following ADR and standards
5. **PM updates PRD** with "Released" status when shipped
6. **Update README.md** if user-facing workflow changes

---

### Making an Architectural Decision

1. **Architect creates ADR** in `architecture/NNN-decision-name.md`
2. **Document context, decision, consequences, alternatives**
3. **Reference from ARCHITECTURE.md** if system-wide impact
4. **Update STANDARDS.md** if affects coding standards
5. **Link from relevant PRDs** if affects features

---

### Updating Project Direction

1. **CEO updates VISION.md** or **PRIORITIES.md**
2. **PM reviews ROADMAP.md** for alignment
3. **PM updates feature priorities** in PRDs
4. **Architect reviews architecture** for needed changes
5. **Update README.md** if positioning changes

---

## Documentation Checklist

When creating or updating documentation:

- [ ] Identified correct tier (CEO/PM/Architect/Developer/User)
- [ ] Wrote for intended audience
- [ ] Cross-referenced authoritative sources
- [ ] Avoided duplication
- [ ] Updated related documents
- [ ] Added to DOCUMENTATION.md if new tier
- [ ] Tested all links
- [ ] Followed STANDARDS.md guidelines

---

## Questions?

- **"Where should this documentation go?"** → Check the hierarchy above
- **"Is this redundant?"** → Check for existing authoritative source
- **"Who updates this doc?"** → Check the Owner in Document Lifecycle
- **"What format should I use?"** → Check STANDARDS.md

For process questions, see [CLAUDE.md](CLAUDE.md).

For contribution questions, see [CONTRIBUTING.md](CONTRIBUTING.md).
