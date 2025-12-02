---
name: workflow-collaboration
description: PROACTIVELY use when personas need to collaborate on features, provide peer feedback, or coordinate work. Apply when Router is coordinating multi-persona work, personas need consultation patterns, or alignment verification is required. Use during feature development, peer consultation, iterative collaboration, and before claiming work complete.
---

# Workflow Collaboration

This skill provides detailed workflow patterns for persona collaboration, peer feedback, and alignment verification.

## Feature Development (Collaborative Peer Flow with Alignment Checkpoints)

```
User: "Add feature X"
  ↓
Router: Analyze request → Determine persona(s) to consult
  ↓
[Spawn CEO subagent]
  ├─> Read VISION.md, PRIORITIES.md
  ├─> Consider: Does feature X align with strategic goals?
  ├─> ALIGNMENT CHECK: Does strategic perspective align with VISION.md, PRINCIPLES.md?
  └─> Output: Strategic perspective + recommendations (advisory)
  ↓
Router: Share CEO perspective, consult PM
  ↓
[Spawn PM subagent]
  ├─> Read ROADMAP.md, features/*.md, CEO's strategic input
  ├─> Consider CEO feedback, define user-facing behavior
  ├─> Define: User stories, acceptance criteria, edge cases
  ├─> ALIGNMENT CHECK: Requirements align with VISION.md? Acceptance criteria measurable per guidelines?
  ├─> If misalignment: Consult CEO for strategic clarity OR revise requirements
  └─> Output: PRD for feature X (verified aligned)
  ↓
Router: Share PRD, consult Architect
  ↓
[Spawn Architect subagent]
  ├─> Read ARCHITECTURE.md, STANDARDS.md, PRD
  ├─> Design: Technical approach, components, interfaces
  ├─> ALIGNMENT CHECK: Design meets requirements in features/*.md? Follows STANDARDS.md, ARCHITECTURE.md?
  ├─> If misalignment: Consult PM about requirement adjustments OR revise design
  ├─> If design concerns arise: Provide feedback to PM (they decide on requirements changes)
  └─> Output: Technical design doc (verified aligned) + any feedback for PM
  ↓
Router: Share design (and any PM feedback), consult Developer
  ↓
[Spawn Developer subagent]
  ├─> SCOPE CHECK: Requirements defined? Design specified? Work is implementation (HOW)?
  ├─> Read STANDARDS.md, PRD, design doc
  ├─> Implement: Code + tests following design (TDD: Red-Green-Refactor)
  ├─> ALIGNMENT CHECK: Tests pass? Cover all acceptance criteria? Follows design? Complies with STANDARDS.md?
  ├─> If misalignment: Consult PM (requirements) or Architect (design) to resolve before completion
  ├─> If implementation concerns arise: Provide feedback to Architect/PM (they consider it)
  └─> Output: Implementation + tests + commit (verified aligned) + any peer feedback

Note: At any stage, personas may provide feedback to each other AND must verify alignment before completion.
Router coordinates consultation with relevant peers. Feedback is advisory - each persona owns their domain.
But claiming "done" requires alignment with governing documentation.
```

## Simple Implementation (Single-Persona Flow with Alignment)

```
User: "Fix bug in file.py line 42"
  ↓
Router: This is implementation work → Consult Developer
  ↓
[Spawn Developer subagent]
  ├─> SCOPE CHECK: Is bug behavior defined? Is fix approach clear? Is this implementation (HOW)?
  ├─> If scope unclear: Can proceed with preliminary fix, but MUST consult peers before completion
  ├─> Read file.py, STANDARDS.md, relevant features/*.md (for expected behavior)
  ├─> Fix bug following standards (TDD: test first, then fix)
  ├─> ALIGNMENT CHECK: Test passes? Bug fix matches expected behavior in docs? Complies with STANDARDS.md?
  ├─> If misalignment: Consult PM (behavior unclear) or Architect (design unclear) to resolve
  └─> Output: Fix + test + commit (verified aligned) (+ any peer consultation notes if scope was initially unclear)

Note: Even "simple" fixes require alignment check. Developer can explore preliminary fixes if scope unclear,
but claiming "done" requires verification that fix aligns with documented behavior and standards.
If bug behavior is ambiguous or fix requires defining new user-facing behavior, Developer MUST consult peers before completion.
```

## TDD Implementation Flow (Developer Persona with Alignment)

```
[Spawn Developer subagent with PRD and design]
  ↓
SCOPE CHECK:
  ├─> Requirements defined in features/*.md? Design in architecture/*.md? Work is implementation?
  ├─> If unclear: Can proceed with exploration, but MUST align before completion
  └─> Proceed to TDD
  ↓
RED Phase:
  ├─> Read acceptance criteria from features/*.md
  ├─> Write failing test case(s)
  ├─> Run tests to confirm failure
  └─> Output: Failing test(s) with clear failure messages
  ↓
GREEN Phase:
  ├─> Write minimal implementation code
  ├─> Run tests to confirm passing
  └─> Output: Passing tests + implementation
  ↓
REFACTOR Phase:
  ├─> Apply STANDARDS.md
  ├─> Remove duplication, improve clarity
  ├─> Run tests to confirm still passing
  └─> Output: Refactored code + passing tests
  ↓
REPEAT until all acceptance criteria satisfied
  ↓
ALIGNMENT CHECK (before claiming complete):
  ├─> Do tests pass? ✓
  ├─> Do tests cover ALL acceptance criteria in features/*.md? ✓
  ├─> Does implementation follow design in architecture/*.md? ✓
  ├─> Does code comply with STANDARDS.md? ✓
  ├─> If ANY misalignment: Consult peers to resolve (PM for requirements, Architect for design)
  └─> Output: Complete implementation + tests + docs (verified aligned with requirements and design)
```

## Peer Feedback Within Subagents

When a persona subagent needs input from peers or encounters boundary questions:

```
Developer discovers design concern
  └─> Report to Router: "Design concern: [description]. Suggest consulting with Architect about [specific issue]."
      └─> Router consults Architect subagent for design feedback

Developer encounters unclear requirements
  └─> Report to Router: "Requirements question: [gap]. Suggest consulting with PM about [specific clarification]."
      └─> Router consults PM subagent for requirements feedback
      └─> Developer can still proceed with documented assumptions if needed

Developer asked to define user behavior
  └─> Report to Router: "This touches user-facing behavior (PM's domain). Suggest consulting with PM. I can offer implementation perspective."
      └─> Router consults PM subagent, shares Developer's input

Developer discovers persona boundary question
  └─> Report to Router: "Persona boundary question: [issue]. Suggest consulting with HR about workflow."
      └─> Router consults HR subagent for workflow guidance

Architect finds requirements unclear
  └─> Report to Router: "Requirements question: [question]. Suggest consulting with PM."
      └─> Router consults PM subagent for clarification

Architect encounters persona definition question
  └─> Report to Router: "Workflow question: [description]. Suggest consulting with HR."
      └─> Router consults HR subagent for guidance

PM identifies strategic question
  └─> Report to Router: "Strategic consideration: [question]. Suggest consulting with CEO."
      └─> Router consults CEO subagent for strategic input

PM discovers workflow friction
  └─> Report to Router: "Workflow observation: [pattern]. Suggest consulting with HR about peer collaboration."
      └─> Router consults HR subagent to analyze

CEO observes persona system concern
  └─> Report to Router: "Workflow observation: [issue]. Suggest consulting with HR about team dynamics."
      └─> Router consults HR subagent to address

Any persona encounters repeated feedback loops
  └─> Report to Router: "Collaboration pattern: [observation]. Suggest consulting with HR about boundaries."
      └─> Router consults HR subagent to refine workflow
```

**Key principle**: Subagents don't spawn other subagents. They request peer consultation via Router, which coordinates with the appropriate persona. Feedback is advisory - personas remain autonomous in their domains. All personas can consult with HR about persona definitions or workflow effectiveness.

## Iterative Multi-Role Collaboration

Large projects involve multiple rounds of peer consultation and feedback rather than single handoffs. This is the normal workflow, not an exception.

**Typical Flow** (collaborative progression):
```
CEO provides strategic perspective
  → PM considers strategy, defines requirements
    → Architect considers requirements, designs technical approach
      → Developer considers design, implements phase
        → All peers provide feedback to each other as needed
        → Return to any peer for refinement based on learnings
```

**Feedback Flow** (peer consultation and iteration):
```
Developer discovers design concern → Provides feedback to Architect → Architect considers, may revise
Developer discovers requirements question → Consults with PM → PM clarifies (may adjust based on implementation realities)
Architect discovers technical challenge → Provides feedback to PM → PM considers scope adjustment
Architect raises strategic question → Consults with CEO → CEO provides input
PM raises priority question → Consults with CEO → CEO provides direction
```

## Consultation Patterns

When to seek peer input:

| From | To | When to Consult |
|------|-----|---------|
| Developer | Architect | Design concern, structural question, implementation reveals design gap |
| Developer | PM | Requirements question, edge case discovered, user intent unclear |
| Developer | HR | Persona boundary question, peer collaboration concern |
| Developer | CEO | Strategic question discovered (rare but valid) |
| Architect | PM | Requirements seem infeasible, scope question, need requirements clarification |
| Architect | HR | Workflow question, boundary uncertainty with PM/Developer |
| Architect | CEO | Architecture principles vs feature goals tradeoff |
| PM | HR | Repeated feedback loops, collaboration friction with peers |
| PM | CEO | Feature priority question, strategic alignment concern |
| CEO | HR | Workflow observation, concerns about peer collaboration effectiveness |
| Any persona | HR | Persona definition question, boundary disputes, workflow improvements |

## Collaboration Checkpoints

When to gather peer input and verify alignment:

| Event | Consult With | Purpose |
|-------|-----------|---------|
| Before claiming work complete | Self-check + relevant peers | Verify alignment with governing documentation (requirements, design, standards) |
| Phase complete | Architect + Developer | Plan next phase based on implementation learnings, verify current phase aligned |
| Implementation complete | All peers | Review outcomes, verify goals met and aligned with requirements, gather feedback |
| Major milestone | PM + CEO | Check strategic alignment, verify deliverables meet vision, adjust priorities if needed |
| Blocking issue discovered | Relevant peer | Get input to unblock, iterate on approach, ensure resolution aligns with docs |
| Misalignment discovered | Relevant peer | Drive resolution immediately (don't proceed with assumptions), update docs or outputs to align |

## Incremental Planning

Each planning role (CEO, PM, Architect) should plan incrementally rather than exhaustively upfront:
- **Architect**: Plan one implementation phase at a time, not entire project
- **PM**: Refine requirements as technical constraints emerge
- **CEO**: Adjust priorities as project reveals new information

This allows plans to adapt based on learnings from implementation. Developer discovers ground truth (what's actually used, what's actually complex) and feeds this back to planning roles.

## Parallel Work

Not everything is sequential. While waiting for peer feedback:
- Developer can work on unblocked parts
- Architect can design independent components
- PM can clarify other requirements

## Documentation Scaffolding

During large projects, planning roles create temporary artifacts (implementation plans, phase tracking, open questions). These are scaffolding—useful during construction, removed when done:

```
Architect creates scaffolding (detailed implementation plan)
  → Developer uses scaffolding (executes steps, tracks progress)
    → Architect removes scaffolding (cleans docs to final state)
```

After implementation completes:
- Remove implementation plans and tracking (git history preserves this)
- Update architecture docs to describe final state only
- Remove "migration", "phases", "before/after" language
- Ensure docs describe WHAT IS, not HOW WE GOT HERE

## Alignment Before Completion

**Core principle**: Divergence during work is healthy. Alignment before completion is mandatory.

**Why alignment matters**:
- Peer collaboration allows exploration, proposals, and alternative approaches during work
- BUT claiming "done" requires verification that outputs align with governing documentation
- Each persona is responsible for driving alignment in their domain before completion
- Alignment ensures the system works cohesively even as personas work autonomously

**What alignment means for each persona**:
- **CEO**: Strategic direction aligns with VISION.md, PRINCIPLES.md, PRIORITIES.md
- **PM**: Requirements align with strategic direction, acceptance criteria are measurable and testable per guidelines
- **Architect**: Design aligns with PM requirements (features/*.md) and follows STANDARDS.md, ARCHITECTURE.md
- **Developer**: Implementation aligns with PM requirements (features/*.md), Architect design (architecture/*.md), and STANDARDS.md
- **HR**: Workflow changes align with how personas actually work and improve collaboration effectiveness

**How to drive alignment**:
1. **Explore divergently**: Propose alternatives, challenge assumptions, offer different approaches during work
2. **Verify alignment**: Before claiming complete, check your outputs against governing documentation
3. **Resolve misalignment**: If conflicts exist, consult with relevant peers to resolve (don't just document and proceed)
4. **Ensure consistency**: Your outputs should be testable against documented requirements, designs, or standards
5. **Own alignment**: Don't wait for others to catch misalignment - proactively verify and resolve

**Examples of alignment checks**:
- Developer finishing implementation: Do tests pass? Do they cover all acceptance criteria in features/*.md? Does code follow architecture/*.md design? Complies with STANDARDS.md?
- PM finishing PRD: Does it align with VISION.md? Are acceptance criteria measurable per guidelines? Has relevant peer feedback (CEO strategic input, Architect feasibility) been incorporated?
- Architect finishing design: Does it meet requirements in features/*.md? Follows ARCHITECTURE.md principles and STANDARDS.md patterns?
- CEO finishing strategic analysis: Is it consistent with VISION.md and PRINCIPLES.md?

**What is NOT acceptable**:
- ✗ Claiming work complete with "documented assumptions" that haven't been validated
- ✗ Implementing features that don't match acceptance criteria and calling it done
- ✗ Finishing designs that don't meet requirements without resolving conflicts
- ✗ Completing PRDs with unmeasurable acceptance criteria
- ✗ Proceeding with misalignment "for now" and planning to fix later

**The original intent**: The Developer SCOPE CHECK was about ensuring alignment, not enforcing hierarchy. This principle extends that to all personas: collaborate as peers, but ensure your outputs align with what the system needs.
