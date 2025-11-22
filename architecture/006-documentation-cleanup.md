# ADR-006: Documentation Structure Cleanup

## Status

Proposed

## Context

The project has evolved to use a hierarchical agent workflow (CEO→PM→Architect→Developer) with structured documentation artifacts. However, the documentation landscape has accumulated redundancies and gaps:

**Current Documentation State:**
- CEO docs: VISION.md, PRIORITIES.md, PRINCIPLES.md (new, authoritative)
- PM docs: ROADMAP.md, features/*.md (7 PRDs) (new, authoritative)
- Architect docs: ARCHITECTURE.md, STANDARDS.md, architecture/*.md (5 ADRs) (new, authoritative)
- Legacy docs: README.md, CONTRIBUTING.md, WORKFLOWS.md (pre-hierarchical)
- Service docs: services/README.md, services/DESIGN-selective-validation.md, services/IMPLEMENTATION-selective-validation.md
- Format docs: formats/allpaths/README.md, formats/allpaths/CATEGORIZATION_VALIDATION.md
- Meta-docs: CLAUDE.md (hierarchical workflow guide)

**Problems Identified:**

1. **Spurious Design/Implementation Docs**: `services/DESIGN-selective-validation.md` and `services/IMPLEMENTATION-selective-validation.md` blur the line between product design (PM), architecture (Architect), and implementation (Developer)

2. **Missing Cross-References**: User-facing docs (README.md, CONTRIBUTING.md) don't reference strategic docs (VISION.md, PRINCIPLES.md, ROADMAP.md)

3. **Overlap in Workflow Documentation**: WORKFLOWS.md vs CLAUDE.md - one is for daily story writing, one is for development workflow

4. **Inconsistent Service Documentation**: services/README.md has been updated with validation modes content that duplicates DESIGN-selective-validation.md

5. **No Clear Documentation Navigation**: Developers/contributors don't have a clear entry point to understand the documentation hierarchy

## Decision

### 1. Remove Spurious Documentation

**Remove entirely:**
- `services/IMPLEMENTATION-selective-validation.md` - Too detailed for architecture, belongs in implementation notes or deleted
- **Rationale**: Implementation plans at this level of detail are transient working documents, not permanent architecture. They become stale quickly and create maintenance burden.

**Consolidate:**
- `services/DESIGN-selective-validation.md` → Move validation mode design decisions into `architecture/002-validation-cache.md` (existing ADR)
- **Rationale**: The selective validation design is an architectural decision about the validation system, not a separate product feature. It's an enhancement to the existing validation cache architecture.

### 2. Clarify Document Purposes

**Update README.md:**
- Add "Documentation Guide" section pointing to:
  - VISION.md - Project mission and goals
  - CONTRIBUTING.md - How to contribute story content
  - ROADMAP.md - What features exist and what's planned
  - CLAUDE.md - For developers working on the codebase
- **Rationale**: Provide clear navigation from entry point

**Rename WORKFLOWS.md → WRITING-WORKFLOW.md:**
- Clarify this is about daily story writing, not development workflow
- **Rationale**: Disambiguation from CLAUDE.md development workflow

**Keep CLAUDE.md separate:**
- Meta-documentation for developers using hierarchical agent pattern
- Different audience than project documentation
- **Rationale**: Serves a distinct purpose

### 3. Update Cross-References

**In CONTRIBUTING.md:**
- Add reference to PRINCIPLES.md ("Writers First, Always")
- Add reference to VISION.md (why this project exists)
- **Rationale**: Connect operational docs to strategic vision

**In README.md:**
- Link to ROADMAP.md in "Outputs" section
- Reference VISION.md in project description
- **Rationale**: Help users understand the bigger picture

**In services/README.md:**
- Remove detailed validation mode documentation (keep only brief summary)
- Reference features/path-validation-cache.md and architecture/002-validation-cache.md
- **Rationale**: Single source of truth, avoid duplication

### 4. Consolidate Validation Documentation

**features/path-validation-cache.md (PM-level):**
- User stories, success metrics, acceptance criteria
- What the feature does and why it exists
- Keep as-is (authoritative product spec)

**architecture/002-validation-cache.md (Architect-level):**
- Update to include selective validation modes design
- Technical decisions, trade-offs, alternatives
- How the system is structured

**services/README.md (Operational):**
- Brief overview of validation modes with examples
- Commands and usage
- Reference deeper docs for details

### 5. Create Documentation Map

**Add DOCUMENTATION.md at root:**
- Clear hierarchy: CEO → PM → Architect → Developer
- Explanation of each document's purpose and audience
- Navigation guide for different personas

## Consequences

### Positive

1. **Clear Separation of Concerns**: Product (PM), Architecture (Architect), Implementation (Developer) clearly separated
2. **Reduced Redundancy**: Single source of truth for each aspect of the system
3. **Better Navigation**: Users can find relevant docs quickly
4. **Maintainability**: Less duplication means less to update
5. **Alignment with Hierarchical Model**: Documentation structure matches agent workflow

### Negative

1. **Breaking Change**: Links to removed/moved docs will break
2. **Migration Effort**: Need to update cross-references
3. **Learning Curve**: Contributors need to understand doc hierarchy
4. **Temporarily Incomplete**: Some docs will reference others that are being updated

### Mitigations

- Update all cross-references atomically in single PR
- Add redirects or notes in removed doc locations
- Update DOCUMENTATION.md to explain new structure
- Test all internal links before merge

## Alternatives Considered

### Alternative 1: Keep All Documentation As-Is
**Rejected because:**
- Redundancy creates maintenance burden
- Unclear which doc is authoritative
- Doesn't align with hierarchical agent workflow

### Alternative 2: Merge All Docs Into Single DOCUMENTATION.md
**Rejected because:**
- Single file would be too large
- Harder to maintain and navigate
- Doesn't support role-based workflow

### Alternative 3: Create docs/ Directory with Subdirectories
**Rejected because:**
- Current structure (root-level + architecture/ + features/) is working well
- Moving root-level docs would break existing references
- Additional indirection doesn't add value

## Implementation Plan

### Phase 1: Remove Redundant Docs
1. Delete `services/IMPLEMENTATION-selective-validation.md`
2. Extract design decisions from `services/DESIGN-selective-validation.md`
3. Update `architecture/002-validation-cache.md` with selective validation design
4. Delete `services/DESIGN-selective-validation.md`

### Phase 2: Rename and Clarify
1. Rename `WORKFLOWS.md` → `WRITING-WORKFLOW.md`
2. Update git history to preserve file history

### Phase 3: Update Cross-References
1. Update README.md with documentation guide section
2. Update CONTRIBUTING.md with references to VISION and PRINCIPLES
3. Update services/README.md to reference authoritative docs
4. Update all internal links in existing docs

### Phase 4: Create Documentation Map
1. Create DOCUMENTATION.md at root
2. Document hierarchy and purpose of each doc
3. Add navigation guide for different personas

### Phase 5: Validation
1. Test all internal links
2. Verify no broken references
3. Review with team
4. Merge atomically

## References

- [CLAUDE.md](/home/user/NaNoWriMo2025/CLAUDE.md) - Hierarchical agent workflow
- [ARCHITECTURE.md](/home/user/NaNoWriMo2025/ARCHITECTURE.md) - System architecture
- [STANDARDS.md](/home/user/NaNoWriMo2025/STANDARDS.md) - Documentation standards
- [features/path-validation-cache.md](/home/user/NaNoWriMo2025/features/path-validation-cache.md) - Path validation cache PRD
