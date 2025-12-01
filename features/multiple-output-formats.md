# Feature PRD: Multiple Output Formats

**Status:** Released ✅
**Owner:** Product Manager
**Last Updated:** 2025-11-22

---

## User Problem

**For collaborative interactive fiction authors:**
- **Playing** the story requires one format (interactive, clickable)
- **Proofreading** requires another (linear, no distractions)
- **Understanding structure** requires another (visual graph)
- **Validating continuity** requires another (all paths enumerated)
- Manually maintaining multiple versions of the same content creates errors and wastes time

**Pain Point:** "I need to proofread the story, but the interactive format makes it hard to read linearly. I need to see the structure, but Harlowe doesn't show me a graph. I can't maintain separate versions without introducing inconsistencies."

---

## User Stories

### Story 1: Proofreader
**As a** writer reviewing story content
**I want to** read the entire story as linear text without game mechanics
**So that** I can focus on prose quality, grammar, and style without distractions

**Acceptance Criteria:**
- Linear text format with no interactive elements
- Clean prose without code or markup
- All passages visible in reading order
- Easy navigation between sections
- Paperthin format generated automatically on every build

---

### Story 2: Story Architect
**As a** writer planning story structure
**I want to** visualize the branching narrative as a graph
**So that** I can see how choices connect and identify structural issues

**Acceptance Criteria:**
- Visual graph showing all passages as nodes
- Arrows showing links between passages
- Interactive graph (zoom, pan, click nodes)
- DotGraph format generated automatically on every build
- Published to web for easy access

---

### Story 3: Player Tester
**As a** contributor testing the story
**I want to** play the interactive story exactly as readers will experience it
**So that** I can verify choices work correctly and the story flows well

**Acceptance Criteria:**
- Fully interactive playable story
- Harlowe format with all game mechanics
- Same experience as published version
- Generated automatically on every build
- Available in PR preview for testing

---

### Story 4: Continuity Validator
**As a** writer checking for continuity errors
**I want to** review all possible story paths individually
**So that** I can ensure consistency across every possible player journey

**Acceptance Criteria:**
- All possible paths enumerated from start to end
- Each path as separate text file
- Metadata showing route and path ID
- AllPaths format generated automatically on every build
- Integrated with AI continuity checking service

---

## Success Metrics

### Primary Metrics
- **Build reliability:** All 6 formats build successfully on every commit
- **Build speed:** Total build time <2 minutes
- **Format usage:** Each format used for its intended purpose
- **Maintenance burden:** Zero manual format maintenance

### Secondary Metrics
- **Testing coverage:** Players test all formats before merge
- **Validation thoroughness:** All paths checked for continuity

### Qualitative Indicators
These are directional goals we cannot directly measure but inform our design decisions:
- Linear format makes editing and proofreading easier
- Graph format reveals structure issues clearly
- Writer feedback: "I use Paperthin for proofreading every day"
- Writers intuitively know which format to use for each task
- No inconsistencies between formats (single source of truth works)

---

## How It Works

### The Six Formats

**Organization:** Formats 1-3 are third-party tools we use (details inline). Formats 4-6 are custom features we built (linked to dedicated feature specs).

---

### Third-Party Formats (1-3)

#### 1. Harlowe (Interactive Playable Story)
**Purpose:** Player experience - how readers will play the story

**Format Details:**
- Full interactive fiction experience
- Clickable links for choices
- Harlowe 3 game mechanics (variables, conditionals, etc.)
- Styled with custom CSS
- Hosted on GitHub Pages

**Use Cases:**
- Play testing new passages
- Experiencing the story as a player
- Sharing with readers
- Verifying game mechanics work

**Output:** `dist/index.html`
**Live URL:** `https://michaelansel.github.io/NaNoWriMo2025/`

---

#### 2. Paperthin (Linear Proofreading)
**Purpose:** Editing and review - clean prose for proofreading

**What You Get:**
- Linear text presentation (all passages in reading order)
- Clean prose without interactive elements or game mechanics
- Minimal formatting for distraction-free reading
- Easy-to-read format for editing and review

**Use Cases:**
- Proofreading for grammar and style
- Reviewing prose quality
- Linear reading of the story
- Editing without game distractions

**Output:** `dist/proofread.html`
**Live URL:** `https://michaelansel.github.io/NaNoWriMo2025/proofread.html`

**Technical Note:** Implementation details (how linear text is generated) are in architecture documentation.

---

#### 3. DotGraph (Story Structure Visualization)
**Purpose:** Understanding - visual map of story branches

**What You Get:**
- Interactive graph showing story structure
- Visual nodes (passages) and edges (choices/links)
- Zoom, pan, and click to explore the graph
- Story branching visible at a glance
- Identify dead ends, loops, and connection patterns

**Use Cases:**
- Visualizing branching structure
- Identifying dead ends or loops
- Understanding story flow
- Planning new branches

**Output:** `dist/graph.html`
**Live URL:** `https://michaelansel.github.io/NaNoWriMo2025/graph.html`

**Technical Note:** Implementation details (graph generation library, rendering approach) are in architecture documentation.

---

### Custom Formats (4-6)

#### 4. AllPaths (allpaths.html)

**Purpose:** Enumerate all possible paths through the story for validation and testing

**What You Get:**
- Every possible path through the story listed
- Progress tracking with creation and modification dates
- Filtering by recent activity (last day/week)
- Validation status tracking (which paths have been checked)
- Integration with AI continuity checking
- Browsable web interface and text files for AI validation

**Use Cases:**
- AI continuity checking
- Exhaustive story validation
- Tracking which paths are new vs. modified
- Browsing all possible player journeys
- Monitoring NaNoWriMo daily and weekly progress

**Output:** `dist/allpaths.html`
**Live URL:** `https://michaelansel.github.io/NaNoWriMo2025/allpaths.html`

**Detailed Feature Spec:** See [AllPaths Progress Tracking](allpaths-categorization.md) for full acceptance criteria and user stories.

---

#### 5. Metrics (Writing Statistics)
**Purpose:** Quantitative writing statistics and progress tracking

**What You Get:**
- Total word count across the entire story
- Aggregate passage statistics (min/mean/median/max word counts)
- Aggregate file statistics (min/mean/median/max word counts per file)
- Word count distributions (fixed ranges: 0-100, 101-300, 301-500, 501-1000, 1000+)
- Top 5 longest passages for review
- Accessible on any device with a browser

**Use Cases:**
- Understanding writing output and volume
- Staying motivated with quantitative progress
- Analyzing writing patterns and typical passage lengths
- Identifying refactoring candidates (exceptionally long or short passages)
- Tracking contributions in collaborative projects

**Output:** `dist/metrics.html`
**Live URL:** `https://michaelansel.github.io/NaNoWriMo2025/metrics.html`

**Detailed Feature Spec:** See [Writing Metrics](writing-metrics.md) for full acceptance criteria, user stories, and detailed requirements.

---

#### 6. Story Bible (World Consistency Reference)
**Purpose:** Canonical reference for characters, locations, items, and world facts

**What You Get:**
- Complete entity detection (ALL named characters, locations, items)
- Constants vs Variables distinction (facts always true vs player-determined)
- Zero Action State (what happens if player does nothing)
- Evidence-based (every fact cites source passages)
- Deduplication (merged facts with preserved evidence)
- Searchable entity database extracted from prose

**Use Cases:**
- Maintaining world consistency across branches
- Onboarding new collaborators with established lore
- Distinguishing canon from player-determined outcomes
- Understanding character baselines before player intervention
- Avoiding contradictions in collaborative writing

**Output:** `dist/story-bible.html`
**Live URL:** `https://michaelansel.github.io/NaNoWriMo2025/story-bible.html`

**Detailed Feature Spec:** See [Story Bible](story-bible.md) for full acceptance criteria, user stories, and detailed requirements.

---

## Edge Cases

### Edge Case 1: Format-Specific Bugs
**Scenario:** Story works in Harlowe but breaks in Paperthin

**Current Behavior:**
- Build succeeds for all formats
- Bug only visible in one format
- Could miss format-specific issues

**Desired Behavior:**
- Test all formats in PR preview
- Document format limitations
- Flag format-specific issues early

**Status:** Mitigated by testing all formats in PR preview

---

### Edge Case 2: Large Story Performance
**Scenario:** Story grows to 100+ passages, 200+ paths

**Current Behavior:**
- All formats build successfully
- DotGraph may become cluttered
- AllPaths generates many files
- Build time increases

**Desired Behavior:**
- Monitor build performance
- Optimize if build time exceeds 2 minutes
- DotGraph remains usable with large graphs
- AllPaths handles large path counts

**Status:** Not yet encountered, monitoring as story grows

---

### Edge Case 3: Format Version Updates
**Scenario:** New version of Harlowe or Paperthin released

**Current Behavior:**
- Formats pinned to specific versions in build
- Manual update required to use new features
- Breaking changes could affect story

**Desired Behavior:**
- Evaluate new versions before upgrading
- Test thoroughly with preview
- Document any breaking changes

**Status:** Controlled by version pinning in workflow

---

### Edge Case 4: Broken Links in Formats
**Scenario:** Link points to passage that doesn't exist

**Current Behavior:**
- Tweego compiles successfully with broken link
- Broken link appears in all formats
- Playable format shows broken link
- DotGraph shows edge to missing node
- AllPaths may terminate path early

**Desired Behavior:**
- Build warns about broken links
- AI continuity checker flags broken links
- Writers fix before merge

**Status:** Handled by AI continuity checking

---

### Edge Case 5: Format Output Size
**Scenario:** AllPaths generates very large files (10+ MB HTML)

**Current Behavior:**
- Files build successfully
- May be slow to load in browser
- GitHub Pages has limits

**Desired Behavior:**
- Monitor output sizes
- Optimize if approaching limits
- Consider pagination for very large outputs

**Status:** Current output sizes are manageable (<1 MB)

---

### Edge Case 6: AllPaths Cycles
**Scenario:** Story has loops (passage links back to earlier passage)

**What You See:**
- AllPaths terminates path when it revisits a passage
- Each path shown once through the loop (no infinite repetition)
- Prevents exponential explosion of paths

**What You Can Do:**
- Review how loops are represented in AllPaths
- Verify loop behavior matches your story design
- If you need different cycle handling, discuss with team

**Status:** Working as intended - cycles handled to prevent infinite loops

**For All Edge Cases:**
Implementation details (how formats are generated, error handling, performance optimization) are documented in architecture specs.

---

## What Could Go Wrong?

### Risk 1: Format Incompatibilities
**Impact:** Medium - story works in one format but not another
**Mitigation:** Test all formats in PR preview before merge
**Fallback:** Fix format-specific issues case by case

---

### Risk 2: Build Time Exceeds Target
**Impact:** Medium - slower feedback loop frustrates writers
**Mitigation:** Monitor build performance, optimize if needed
**Fallback:** Parallelize builds if time increases

---

### Risk 3: Format Breaking Changes
**Impact:** Low - upstream format update breaks our build
**Mitigation:** Pin format versions, test updates before deploying
**Fallback:** Stick with working version until issues resolved

---

### Risk 4: GitHub Pages Limits
**Impact:** Low - output exceeds GitHub Pages size limits
**Mitigation:** Monitor output sizes, optimize before hitting limits
**Fallback:** Host large files elsewhere (e.g., GitHub releases)

---

## Future Enhancements

### Considered but Deferred
- **PDF export:** Generate printable PDF version
  - **Why deferred:** Not needed during active writing phase

- **EPUB/Kindle formats:** E-reader formats
  - **Why deferred:** Post-publication feature, not critical for NaNoWriMo

- **Diff format:** Show changes between builds
  - **Why deferred:** AllPaths validation cache handles this need

- **Statistics format:** Word counts, branch stats, etc.
  - **Why deferred:** Valuable for retrospective, not needed during writing

---

## Metrics Dashboard

### Current Performance (as of Nov 22, 2025)
- ✅ **Build success rate:** 100% (all formats build on every commit)
- ✅ **Build speed:** <2 minutes for all 6 formats
- ✅ **Output quality:** All formats usable for intended purposes
- ✅ **Format sizes:** Harlowe 51KB, Paperthin 42KB, DotGraph 38KB, AllPaths 165KB, Metrics ~20KB, Story Bible ~50KB
- ✅ **Path count:** 11 paths enumerated successfully

### Format-Specific Metrics
- **Harlowe:** Used for play testing in 100% of PRs
- **Paperthin:** Used for proofreading regularly
- **DotGraph:** Used for structure visualization
- **AllPaths:** Used for AI validation on every PR

---

## Success Criteria Met

- [x] All 6 formats build automatically on every commit
- [x] Build completes in <2 minutes
- [x] Single source of truth (no manual format maintenance)
- [x] Each format optimized for specific use case
- [x] Formats published to GitHub Pages for easy access
- [x] AllPaths integrated with AI continuity checking
- [x] Metrics provides quantitative writing insights
- [x] Story Bible maintains world consistency reference
- [x] No inconsistencies between formats
- [x] Writers use appropriate format for each task

---

## Related Documents

- [formats/allpaths/README.md](/home/user/NaNoWriMo2025/formats/allpaths/README.md) - AllPaths format documentation
- [features/ai-copy-editing-team.md](/home/user/NaNoWriMo2025/features/ai-copy-editing-team.md) - AI Copy Editing Team using AllPaths
- [features/automated-build-deploy.md](/home/user/NaNoWriMo2025/features/automated-build-deploy.md) - Build automation
- [PRINCIPLES.md](/home/user/NaNoWriMo2025/PRINCIPLES.md) - "Multiple Perspectives, Same Source" principle

---

## Lessons Learned

### What Worked Well
- **Single source, multiple views:** .twee files compile to all formats without issues
- **Format specialization:** Each format excels at its specific purpose
- **Fast builds:** All 6 formats in <2 minutes keeps feedback loop tight
- **AllPaths innovation:** Random IDs prevent AI confusion from semantic passage names
- **Comprehensive tooling:** Six distinct perspectives serve different writing and review needs

### What Could Be Better
- **Format documentation:** Could better explain when to use each format
- **DotGraph customization:** Limited styling options for large graphs
- **AllPaths UI:** Could improve browsing experience for many paths

### What We'd Do Differently
- **Earlier format planning:** AllPaths added later, could have designed upfront
- **Format testing:** Could automate format-specific validation
- **Performance benchmarks:** Could track build time per format separately
