# Product Roadmap

**Last Updated:** 2025-11-22
**Current Phase:** NaNoWriMo 2025 Active Writing (November 2025)

## Vision Alignment

This roadmap supports our mission: **Make interactive fiction accessible to writers, not programmers.** Every feature prioritizes writer experience, automation over gatekeeping, and fast feedback loops.

---

## Released Features (Live in Production)

These features are fully operational and being used daily by the team.

### 1. GitHub Web-Based Editing Workflow
**Status:** ✅ Released
**Launched:** Project inception
**User Impact:** Writers contribute using only a web browser - no installation required

Writers can edit .twee files directly in GitHub's web interface, create branches, and open pull requests without installing any software. This removes the technical barrier of local development environments.

**Key Capabilities:**
- Edit files in browser with GitHub's built-in editor
- Automatic branch creation workflow
- Zero-setup contribution path
- Works on any device with a browser (including mobile)

**Success Metrics:**
- 100% of contributions made via GitHub web interface (goal achieved)
- Average time to first contribution: <5 minutes
- Zero blocked contributors due to setup issues

**Related Documents:** [features/github-web-editing.md](features/github-web-editing.md)

---

### 2. Multiple Output Formats
**Status:** ✅ Released
**Launched:** Project inception (AllPaths added Nov 2025)
**User Impact:** Same content, optimized views for different tasks

Every build generates four output formats from the same source .twee files, each optimized for a specific use case.

**Formats:**
- **Harlowe** - Playable interactive story (player experience)
- **Paperthin** - Linear text for proofreading (editing/review)
- **DotGraph** - Visual story structure graph (understanding branches)
- **AllPaths** - All possible paths enumerated (AI validation)

**Key Capabilities:**
- Single source of truth (.twee files)
- All formats generated automatically on every build
- Format-specific optimizations (e.g., AllPaths uses random IDs to prevent AI confusion)
- Formats published to GitHub Pages for easy access

**Success Metrics:**
- All 4 formats build successfully on every commit
- Average build time: <2 minutes (achieved)
- Format-specific usage: Harlowe for play testing, Paperthin for editing, AllPaths for validation

**Related Documents:** [features/multiple-output-formats.md](features/multiple-output-formats.md)

---

### 3. AI Continuity Checking
**Status:** ✅ Released
**Launched:** November 2025
**User Impact:** Automated detection of continuity errors across branching narratives

AI-powered webhook service automatically checks story paths for continuity issues (character consistency, plot coherence, timeline accuracy, contradictions) and posts detailed feedback to pull requests.

**Key Capabilities:**
- Webhook service triggered on PR workflow completion
- Ollama-based AI analysis of each story path
- Real-time progress updates as paths complete
- Detailed issue reporting with severity levels in PR comments
- Three validation modes: new-only (fast), modified (pre-merge), all (full audit)
- Path approval workflow to skip validated paths
- Content-based change detection using git-based categories (internal)

**How It Determines What to Validate:**
- Uses internal git-based categories (NEW/MODIFIED/UNCHANGED) to decide what needs checking
- NEW paths: Contain genuinely new prose, always need validation
- MODIFIED paths: Navigation changed but prose is same, may need validation
- UNCHANGED paths: Nothing changed, skip validation
- These categories are internal - not displayed in AllPaths HTML

**Key Innovation:** Uses random passage IDs in AI prompts to prevent confusion from semantic passage names that players never see.

**Success Metrics:**
- Validation runs automatically on every PR
- Average validation time (new-only mode): <2 minutes for typical changes
- Zero continuity errors merged to main branch
- Clear, actionable feedback that writers can address

**Related Documents:** [features/ai-continuity-checking.md](features/ai-continuity-checking.md)

---

### 4. Automated Build and Deployment
**Status:** ✅ Released
**Launched:** Project inception
**User Impact:** Changes go from commit to live website in under 2 minutes

GitHub Actions workflow automatically builds all output formats, generates preview artifacts for PRs, and deploys to GitHub Pages on merge to main.

**Key Capabilities:**
- Builds all 4 output formats on every push
- Uploads preview artifacts with download links
- Posts PR comment with build stats and instructions
- Deploys to GitHub Pages automatically on merge
- Fast feedback loop (<2 minutes commit to live)

**Key Innovation:** PR preview artifacts allow full testing before merge, preventing broken deployments.

**Success Metrics:**
- Build success rate: >99%
- Average build time: <2 minutes (achieved)
- Average deploy time: <2 minutes (achieved)
- Zero failed deployments to main

**Related Documents:** [features/automated-build-deploy.md](features/automated-build-deploy.md)

---

### 5. Collaborative Multi-Author Workflow
**Status:** ✅ Released
**Launched:** Project inception
**User Impact:** Multiple authors work simultaneously without conflicts

Branch-based contribution model with automated resource tracking prevents naming conflicts and enables parallel development.

**Key Capabilities:**
- Branch-based workflow isolates changes
- PR preview artifacts for reviewing changes before merge
- Automated resource passage tracking
- Clear branching documentation in CONTRIBUTING.md
- Multiple authors can work on different branches simultaneously

**Key Innovation:** Automated "Resource-Passage Names" file auto-updates on every PR, showing all passages and preventing naming conflicts.

**Success Metrics:**
- Authors work in parallel without blocking each other
- Zero merge conflicts from overlapping work
- Clear visualization of how changes affect story structure
- Automated resource tracking prevents naming conflicts

**Related Documents:** [features/collaborative-workflow.md](features/collaborative-workflow.md)

---

### 6. Automated Resource Tracking
**Status:** ✅ Released
**Launched:** November 2025
**User Impact:** Automatic tracking of passage names and links prevents conflicts

Build process automatically generates and commits a "Resource-Passage Names" file that lists all passages and their links, grouped by source file.

**Key Capabilities:**
- Automatic extraction of all passage definitions
- Groups links under their respective passages
- Organized by source file for easy navigation
- Auto-committed on every PR build
- Prevents accidental duplicate passage names

**Key Innovation:** Zero manual maintenance - always stays current with the codebase.

**Success Metrics:**
- Resource file auto-updates on 100% of PRs
- Zero duplicate passage name conflicts
- Quick reference for contributors (find any passage in seconds)

**Related Documents:** [features/automated-resource-tracking.md](features/automated-resource-tracking.md)

---

### 7. Path Validation Cache
**Status:** ✅ Released
**Launched:** November 2025
**User Impact:** Incremental validation avoids re-checking unchanged content

Validation cache tracks all story paths with unique IDs, validation status, and content fingerprints, enabling smart incremental checking.

**Key Capabilities:**
- Content-based hashing for automatic change detection
- Tracks validation status for each path
- Records path metadata (route, creation date, commit date)
- Enables three validation modes (new-only, modified, all)
- Path approval workflow marks paths as validated

**Key Innovation:** Hash-based system automatically detects when path content changes, triggering re-validation only when needed.

**Success Metrics:**
- Average paths checked per PR: ~2-5 (new-only mode)
- Time saved by selective validation: ~60% faster than full validation
- Accurate change detection (zero false negatives)

**Related Documents:** [features/ai-continuity-checking.md](features/ai-continuity-checking.md)

---

## Active Development

Features currently being built or refined based on usage.

### AllPaths Progress Tracking
**Status:** ✅ Active Feature
**Target:** Core Feature (Ongoing)
**Priority:** HIGH
**User Impact:** Writers track progress and browse all story paths

**Purpose:** Provide a comprehensive browsing interface for all story paths with progress tracking and validation status.

**How It Works:**
- **Consistent interface:** Same HTML generated for all builds (PR preview and deployment)
- **Date display:** Shows creation and modification dates for all paths
- **Time-based filters:** Created/Modified Last Day or Week filters for finding recent work
- **Validation status:** Shows which paths have been validated for continuity
- **Progress tracking:** Monitor NaNoWriMo daily and weekly writing progress

**Key Capabilities:**
- View all paths with route, dates, and validation status
- Filter by recent activity (1 day, 7 days)
- Filter by validation status (validated or new)
- Same interface in PR preview and deployment
- Client-side filtering for instant response

**User Benefits:**
- Track daily and weekly writing progress toward NaNoWriMo goals
- Find paths created or modified recently
- Coordinate collaborative writing (see what teammates worked on)
- Validate PR changes with confidence (preview matches deployment)
- Monitor which paths have been reviewed for quality

**Related Documents:** [features/allpaths-categorization.md](features/allpaths-categorization.md)

---

### Selective Validation Optimization
**Status:** 🚧 In Progress
**Target:** November 2025
**User Impact:** Faster feedback through smarter validation

Refinements to the three-mode validation system (new-only, modified, all) based on real-world usage patterns during NaNoWriMo.

**Planned Improvements:**
- Performance tuning for large stories (50+ paths)
- Enhanced skip statistics in PR comments
- Better mode recommendations based on PR context

---

## Planned Features

Features on the roadmap, prioritized by value to current phase.

### Post-NaNoWriMo Retrospective Tools
**Status:** 📋 Planned
**Target:** December 2025
**Priority:** Medium
**User Impact:** Learn from writing patterns and progress

**Problem:** After completing NaNoWriMo, the team wants to analyze writing patterns, contribution frequency, and path completion timeline to learn what worked well.

**Proposed Solution:**
- Analytics dashboard showing daily writing progress
- Path completion timeline visualization
- Author contribution patterns
- Story structure evolution over time

**Why Deferred:** Not needed during active writing; valuable for retrospective learning after completion.

---

### Path Comparison Tool
**Status:** 📋 Planned
**Target:** December 2025
**Priority:** Low
**User Impact:** See what changed between builds

**Problem:** Writers want to see exactly what changed in a path between builds, beyond just "modified" status.

**Proposed Solution:**
- Diff view showing before/after content for modified paths
- Highlighting of specific changes within passages
- Integration with AllPaths HTML interface

**Why Deferred:** Current change detection is sufficient for active writing phase.

---

## Deliberately Deferred

Features that are valuable but don't support the current phase priorities.

### Advanced IF Features (Variables, Inventory, Game Mechanics)
**Why Deferred:** Scope creep threatens core goal of completing the story. Complex game mechanics can be added in future iterations if the story requires them.

**Revisit:** Only if specific story requirements emerge.

---

### Custom Story Format Development
**Why Deferred:** Existing formats (Harlowe, Paperthin, DotGraph, AllPaths) serve current needs adequately. Building custom formats would be a distraction.

**Revisit:** If specific gaps identified in current tooling.

---

### Automated Grammar/Style Checking
**Why Deferred:** Proofreading and style consistency can happen during the editing phase after story completion. Not critical for maintaining continuity during active writing.

**Revisit:** During editing phase (December 2025).

---

### Enhanced Visualization Tools
**Why Deferred:** DotGraph provides sufficient structure visualization. More sophisticated tools would be nice-to-have but don't directly support completing the story.

**Revisit:** If team identifies specific visualization gaps during usage.

---

## Not In Scope

Features we've explicitly decided not to build.

### Real-Time Collaborative Editing
**Why Not:** Adds complexity without solving a real problem. Our async workflow (branch → PR → merge) works well for the team size and pace. Real-time editing would introduce technical overhead without meaningful benefit.

---

### WYSIWYG Editor
**Why Not:** Defeats the purpose of "edit anywhere, even on your phone" approach. Twee syntax is already extremely simple. A visual editor would require installation and lock writers into specific devices.

---

### Version Control Alternatives
**Why Not:** Git/GitHub is fundamental to our automation strategy. Alternative workflows would require rebuilding entire infrastructure. The investment would be massive with no clear benefit.

---

### Supporting Other Story Formats
**Why Not:** Harlowe serves our needs well. Supporting multiple formats (SugarCube, Chapbook, etc.) would fragment testing and complicate documentation. Focus beats flexibility for this project.

---

## Roadmap Evolution

### Phase Transitions

**Current Phase: Active Writing (November 2025)**
- **Focus:** Writer velocity, story quality automation, collaboration
- **Success:** Complete 50,000+ word interactive story collaboratively

**Next Phase: Refinement (December 2025)**
- **Focus:** Editing tools, analytics, retrospective learning
- **Success:** Polished, proofread story ready for publication

**Future Phase: Sharing (2026)**
- **Focus:** Publication polish, accessibility, documentation for others to use our approach
- **Success:** Other teams adopt our workflow for collaborative IF

### Review Triggers

Priorities and roadmap are reviewed when:
- **Major blockers emerge** - Blocking issues require immediate priority shift
- **Phase transitions occur** - Moving from writing to editing changes priorities
- **Strategic goals achieved** - Completing milestones opens up new possibilities
- **New information** - Discoveries that fundamentally change assumptions

### Decision Framework

When evaluating new features or changes:
1. **Does this support completing the story by November 30, 2025?** (Current phase)
2. **Does this reduce friction for daily author contributions?**
3. **Does this increase confidence in story quality?**
4. **Is this actually blocking, or just nice to have?**

Be ruthless about saying "not now" to good ideas that don't serve the current phase.

---

## Success Metrics Dashboard

### Overall Project Metrics (as of Nov 22, 2025)
- **Story Progress:** 21 passages, 11 complete paths
- **Build Performance:** <2 minutes commit to live (✅ goal achieved)
- **Contribution Velocity:** Daily contributions from multiple authors
- **Quality:** Zero continuity errors merged to main

### Feature-Specific Metrics

| Feature | Key Metric | Target | Current |
|---------|-----------|--------|---------|
| GitHub Web Editing | Time to first contribution | <5 min | ✅ Achieved |
| Build & Deploy | Build success rate | >99% | ✅ >99% |
| AI Continuity | Validation run rate | 100% of PRs | ✅ 100% |
| Selective Validation | Time saved (new-only vs all) | >50% | ✅ ~60% |
| Resource Tracking | Auto-update rate | 100% of PRs | ✅ 100% |

---

## Contributing to the Roadmap

**This is a living document.** As we learn from usage during NaNoWriMo, we'll adjust priorities and add features that support the core mission.

**Propose a feature:**
1. Open a GitHub issue with the "feature request" label
2. Describe the user problem (not the solution)
3. Explain how it aligns with our principles and priorities
4. Include success metrics (how will we know it works?)

**Product Manager will:**
- Evaluate against current phase priorities
- Add to appropriate roadmap section (Planned, Deferred, or Not In Scope)
- Create detailed PRD if prioritized for active development
