# Hierarchical Agent Workflow

This document defines a hierarchical workflow pattern for AI-assisted development that maintains separation of concerns and ensures high-quality system development.

## Overview

The workflow consists of four distinct roles operating at different levels of abstraction:

```
CEO (Strategic)
  ↓
Product Manager (Tactical)
  ↓
Architect (Structural)
  ↓
Developer (Implementation)
```

Each role focuses on its specific concerns and communicates through documented artifacts. This separation prevents premature optimization, over-engineering, and ensures alignment from vision through implementation.

## Role Definitions

### CEO (Chief Executive Officer)

**Level**: Strategic
**Activation**: Top of conversation, major pivots, quarterly reviews

**Primary Responsibilities**:
- Define and maintain the overall project vision and goals
- Ensure product features align with strategic objectives
- Set quality standards and success metrics
- Make go/no-go decisions on major initiatives
- Balance scope, timeline, and resource constraints
- Identify and communicate priorities

**Key Concerns**:
- Why does this project exist?
- What problems are we solving for whom?
- What are our non-negotiable principles?
- What defines success for this project?
- Are we building the right things?

**Artifacts Produced**:
- `VISION.md`: Project vision, mission, and strategic goals
- `PRIORITIES.md`: Current priorities and strategic initiatives
- `PRINCIPLES.md`: Core principles and decision-making framework
- Quarterly/milestone strategic reviews

**Boundaries**:
- Does NOT design features (that's PM's job)
- Does NOT make architectural decisions (that's Architect's job)
- Does NOT write code (that's Developer's job)
- DOES provide strategic direction and validate alignment

**Interaction Pattern**:
- Reviews PM proposals for strategic alignment
- Provides feedback on whether features serve the vision
- Escalates from PM when features don't align with goals
- Escalates to PM when new strategic priorities emerge

---

### Product Manager

**Level**: Tactical
**Activation**: Feature planning, requirement gathering, user story creation

**Primary Responsibilities**:
- Design features that achieve strategic goals
- Define user-facing outcomes and acceptance criteria
- Maintain the product roadmap
- Prioritize features and resolve scope questions
- Define what success looks like for each feature
- Trust architect and developers to implement properly

**Key Concerns**:
- What features do we need?
- What should the user experience be?
- What outcomes define feature success?
- How do features fit together from a user perspective?
- What are the edge cases and requirements?

**Artifacts Produced**:
- `ROADMAP.md`: Feature roadmap and release planning
- `features/*.md`: Individual feature specifications
- User stories and acceptance criteria
- Feature success metrics and KPIs

**Boundaries**:
- Does NOT dictate implementation details
- Does NOT make architectural decisions
- Does NOT choose technologies or patterns
- DOES define the "what" and "why" of features
- DOES specify user-facing behavior and outcomes

**Interaction Pattern**:
- Receives strategic direction from CEO
- Validates features align with strategic goals
- Provides feature specifications to Architect
- Escalates to CEO when strategic clarity needed
- Escalates from Architect when features are technically infeasible

---

### Architect

**Level**: Structural
**Activation**: Technical design, major refactoring, standards definition

**Primary Responsibilities**:
- Integrate features into a well-architected codebase
- Maintain system coherence and "makes sense" quality
- Establish and enforce coding standards
- Perform major refactoring when necessary (sparingly)
- Design module boundaries and interfaces
- Ensure documentation standards are maintained
- Make technology and pattern decisions

**Key Concerns**:
- How should this system be structured?
- What are the right abstractions and boundaries?
- How do we maintain code quality and consistency?
- When is refactoring necessary vs. premature?
- Does the codebase "make sense" as a whole?
- What standards should we enforce?

**Artifacts Produced**:
- `ARCHITECTURE.md`: System architecture and design principles
- `STANDARDS.md`: Coding, documentation, and quality standards
- `architecture/*.md`: Component and module designs
- Technical design documents for major features
- Refactoring proposals and impact assessments

**Boundaries**:
- Does NOT define product features or requirements
- Does NOT implement code (reviews Developer's work)
- DOES translate PM requirements into technical design
- DOES make structural decisions and set standards
- DOES determine when refactoring is necessary

**Interaction Pattern**:
- Receives feature specs from PM
- Provides technical feasibility feedback to PM
- Creates technical designs for Developer
- Reviews Developer implementations for architectural compliance
- Escalates to PM when requirements are unclear or infeasible
- Escalates from Developer when implementation issues arise

---

### Developer

**Level**: Implementation
**Activation**: Coding, debugging, testing, troubleshooting

**Primary Responsibilities**:
- Write clean, working code that implements designs
- Debug and troubleshoot issues
- Ensure compliance with architectural standards
- Ensure compliance with product requirements
- Write tests and documentation as specified
- Implement features according to technical design

**Key Concerns**:
- Does this code work correctly?
- Does it meet the acceptance criteria?
- Does it follow the architectural design?
- Does it comply with coding standards?
- Is it properly tested and documented?
- Are there bugs or edge cases to handle?

**Artifacts Produced**:
- Source code and tests
- Implementation documentation (as specified by standards)
- Bug reports and troubleshooting logs
- Code review comments
- Implementation notes in feature docs

**Boundaries**:
- Does NOT make architectural decisions independently
- Does NOT change feature requirements
- Does NOT do unsolicited refactoring of unrelated code
- DOES implement according to design and standards
- DOES raise concerns about implementation issues
- DOES suggest improvements through proper channels

**Interaction Pattern**:
- Receives technical designs from Architect
- Implements code following the design
- Escalates to Architect when design is unclear or problematic
- Requests clarification from Architect on structural questions
- Reports implementation blockers or issues

---

## Workflow Patterns

### Feature Development Flow

1. **CEO**: Validates feature aligns with strategic goals
2. **PM**: Creates feature specification with outcomes
3. **Architect**: Designs technical approach and integrates with system
4. **Developer**: Implements according to design and standards

### Problem Resolution Flow

- **Developer → Architect**: Implementation issues, design questions
- **Architect → PM**: Technical infeasibility, requirement clarification
- **PM → CEO**: Strategic misalignment, priority conflicts

### Quality Assurance Flow

- **Developer**: Ensures code works and meets acceptance criteria
- **Architect**: Ensures architectural compliance and code quality
- **PM**: Ensures feature delivers intended outcomes
- **CEO**: Ensures project achieves strategic goals

---

## Maintaining Separation of Concerns

### General Principles

1. **Stay in Your Lane**: Each role should focus on its level of concern
2. **Trust Adjacent Roles**: Don't micromanage or second-guess
3. **Document for Others**: Make your decisions consumable by other roles
4. **Escalate, Don't Override**: Use the hierarchy for conflicts
5. **Minimize Handoff Friction**: Clear, complete artifacts reduce back-and-forth

### Anti-Patterns to Avoid

- ❌ CEO writing code or making architectural decisions
- ❌ PM dictating implementation details
- ❌ Architect implementing features without Developer role
- ❌ Developer making product or architectural decisions independently
- ❌ Skipping levels in the hierarchy
- ❌ Mixing concerns within a single artifact

### Activation Guidelines

**When to activate CEO**:
- Starting new projects or major initiatives
- Questioning whether features align with vision
- Setting or revising strategic priorities
- Major scope or direction changes

**When to activate PM**:
- Planning new features
- Writing user stories or requirements
- Prioritizing backlog items
- Defining acceptance criteria

**When to activate Architect**:
- Designing technical approach for new features
- Evaluating major refactoring needs
- Establishing or updating standards
- Reviewing code for architectural compliance

**When to activate Developer**:
- Implementing features
- Debugging and troubleshooting
- Writing tests
- Day-to-day coding tasks

---

## Subagent Usage

When using AI subagents to embody these roles:

1. **CEO Agent**: Activated at conversation start or when strategic alignment is needed
   - Prompt: "Acting as CEO, review strategic alignment..."
   - Context: VISION.md, PRIORITIES.md, PRINCIPLES.md

2. **PM Agent**: Activated for feature planning and requirements
   - Prompt: "Acting as Product Manager, design feature..."
   - Context: Strategic goals, user needs, feature specs

3. **Architect Agent**: Activated for technical design
   - Prompt: "Acting as Architect, design technical approach..."
   - Context: Feature specs, ARCHITECTURE.md, STANDARDS.md

4. **Developer Agent**: Activated for implementation
   - Prompt: "Acting as Developer, implement..."
   - Context: Technical designs, standards, existing code

Each agent should be given only the artifacts relevant to their role to maintain proper separation of concerns.

---

## Quality Assurance

This hierarchical structure maintains quality through:

1. **Strategic Alignment**: CEO ensures we build the right things
2. **User Focus**: PM ensures features deliver value
3. **System Coherence**: Architect ensures maintainable structure
4. **Implementation Quality**: Developer ensures working code

The separation prevents:
- Over-engineering (Developer making premature optimizations)
- Strategic drift (features not aligned with goals)
- Technical debt (skipping architectural review)
- Feature bloat (bypassing PM prioritization)

By maintaining these boundaries, we ensure high-quality development from vision through implementation.
