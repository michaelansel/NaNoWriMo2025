# Strategic Priorities

Stack-ranked priorities for the NaNoWriMo2025 project. Higher priorities get resources and attention first.

## Current Phase: NaNoWriMo 2025 Active Writing (November 2025)

### Priority 1: Writer Velocity

**Goal:** Nothing blocks a writer from contributing daily

**Why now:** NaNoWriMo is a time-bound challenge. Every day counts. A blocked writer is a demotivated writer.

**Success metrics:**
- Author can contribute a new passage in under 5 minutes (web UI only)
- Build pipeline completes in under 2 minutes
- Zero tolerance for blocking bugs in contribution workflow
- Documentation answers common questions in under 30 seconds of reading

**Focus areas:**
- Keep GitHub Actions build fast and reliable
- Maintain clear, actionable error messages
- Ensure CONTRIBUTING.md is current and complete
- Quick response to workflow issues

---

### Priority 2: Story Quality Through Automation

**Goal:** Writers trust that automation catches continuity errors

**Why now:** As the story grows and branches multiply, manual continuity checking becomes impossible. Writers need confidence to experiment.

**Success metrics:**
- AI continuity checker runs on every PR automatically
- New paths validated within minutes of PR creation
- Authors can approve/dismiss AI feedback with simple commands
- Zero continuity errors make it to published story

**Focus areas:**
- Reliable AI continuity checking service
- Clear, actionable AI feedback
- Efficient validation (check only what changed)
- Easy approval workflow for validated paths

**Strategic Decision: Focused Validation**

Writer Experience Goal:
- Writers receive fast feedback on only what they changed
- System never makes writers wait to revalidate unchanged content
- Validation results are relevant to the writer's contribution

Why This Matters:
- Full story validation can take hours as the story grows
- Writers contributing during NaNoWriMo need feedback in minutes
- Irrelevant validation feedback is noise that distracts from writing
- Waiting blocks momentum and breaks flow state

Success Metrics:
- PR validation completes in under 5 minutes for typical contributions
- Validation feedback mentions only paths affected by changes
- Writers can continue working while validation runs
- Zero false positives (checking things that didn't change)

Trade-off Accepted:
- More complex categorization/tracking to enable selective validation
- Worth it because writer time and focus are the scarcest resources

---

### Priority 3: Collaborative Workflow Excellence

**Goal:** Multiple authors work simultaneously without conflicts

**Why now:** This is fundamentally a collaborative project. Friction between authors kills momentum.

**Success metrics:**
- Authors work in parallel on different branches without blocking each other
- PRs provide complete preview of changes before merge
- Clear visualization of how changes affect story structure
- Automated resource tracking prevents naming conflicts

**Focus areas:**
- PR preview artifacts with all output formats
- Automated resource passage name generation
- Clear branching contribution documentation
- Graph visualization for story structure

---

### Priority 4: Visibility and Inspection

**Goal:** Everyone can see and understand the complete story state

**Why now:** Complex branching narratives are hard to reason about. Multiple output formats serve different needs.

**Success metrics:**
- Four output formats maintained: playable, proofread, graph, allpaths
- Path tracking shows when each branch was completed
- Easy to identify which paths need review
- Statistics show daily progress toward goals

**Focus areas:**
- Keep all output formats building reliably
- Maintain allpaths validation tracking
- Provide clear path statistics and metrics
- Documentation for each output format's purpose

---

## Deliberately Deferred (Important but not now)

### Post-NaNoWriMo Retrospective Tools
- **What:** Analytics on writing patterns, contribution frequency, path completion timeline
- **Why deferred:** Don't need during active writing; valuable for learning after completion
- **Revisit:** December 2025

### Advanced IF Features
- **What:** Variables, inventory systems, complex game mechanics
- **Why deferred:** Scope creep threatens the core goal - completing the story
- **Revisit:** Only if needed for specific story requirements

### Custom Story Format Development
- **What:** Building custom Tweego story formats beyond AllPaths
- **Why deferred:** Existing formats serve current needs adequately
- **Revisit:** If specific gaps identified in current tooling

### Automated Grammar/Style Checking
- **What:** AI-based proofreading and style consistency checking
- **Why deferred:** Proofreading can happen after story completion
- **Revisit:** During editing phase (December 2025)

---

## Not In Scope (Active "No" List)

### Real-time Collaborative Editing
- Adds complexity without solving a real problem for our async workflow
- GitHub PR model works well for our team size and pace

### WYSIWYG Editor
- Defeats the purpose of our "edit anywhere, even on your phone" approach
- Twee syntax is already extremely simple

### Version Control Alternatives
- Git/GitHub is fundamental to our automation strategy
- Alternative workflows would require rebuilding entire infrastructure

### Supporting Other Story Formats
- Harlowe serves our needs well
- Format fragmentation would complicate testing and documentation

---

## Priority Evolution

These priorities will shift as we move through phases:

**November 2025 (Active Writing):** Velocity, quality automation, collaboration
**December 2025 (Refinement):** Editing tools, analytics, retrospective
**Future (Sharing):** Publication polish, accessibility, documentation for others

Priorities are reviewed when:
- Major blockers emerge
- Phase transitions occur
- Strategic goals are achieved
- New information fundamentally changes assumptions

## Decision Framework

When prioritizing new work, ask:
1. Does this directly support completing the story by November 30, 2025?
2. Does this reduce friction for daily author contributions?
3. Does this increase confidence in story quality?
4. Is this actually blocking, or just nice to have?

Be ruthless about saying "not now" to good ideas that don't serve the current phase.
