# Feature PRD: Collaborative Multi-Author Workflow

**Status:** Released ✅
**Owner:** Product Manager
**Last Updated:** 2025-11-22

---

## User Problem

**For teams writing interactive fiction collaboratively:**
- Traditional Git workflows intimidate non-technical writers
- Simultaneous editing causes merge conflicts and lost work
- No way to preview changes before merging to avoid breaking the story
- Writers need to coordinate timing to avoid conflicts
- Unclear how to contribute new story branches without breaking existing content

**Pain Point:** "I want to add a new story branch, but I'm afraid I'll break what someone else is working on. I don't know Git well enough to resolve merge conflicts, and I'm scared of losing my work."

---

## User Stories

### Story 1: Writer Adding New Branch
**As a** writer adding a new story path
**I want** to work independently without blocking other writers
**So that** we can all contribute simultaneously during NaNoWriMo

**Acceptance Criteria:**
- Can create isolated branch for my work
- Other writers can work on different branches simultaneously
- My changes don't affect others until I'm ready to merge
- Clear documentation for branching workflow
- Can test my changes before merging

---

### Story 2: Writer Testing Before Merge
**As a** writer with a complete story branch
**I want** to preview exactly what will be merged
**So that** I can verify my changes work before affecting the main story

**Acceptance Criteria:**
- Preview artifacts show all my changes
- Can download and test locally
- Preview includes all output formats
- Clear visualization of what changed
- Can make fixes before merging if issues found

---

### Story 3: Reviewer Approving PR
**As a** reviewer checking another writer's contribution
**I want** to see the complete impact of their changes
**So that** I can approve confidently knowing the story will work

**Acceptance Criteria:**
- Can see all files changed in PR
- Can download and test preview build
- AI continuity checking provides validation feedback
- Resource tracking shows no naming conflicts
- Clear understanding of story impact

---

### Story 4: Multiple Writers Working Simultaneously
**As a** team of writers during NaNoWriMo
**I want** everyone to contribute daily without blocking each other
**So that** we maintain momentum and hit our word count goals

**Acceptance Criteria:**
- Multiple branches active simultaneously
- No waiting for others to finish
- Each writer's work isolated until merge
- Fast merge process when ready
- Conflicts are rare and easy to resolve

---

## Success Metrics

### Primary Metrics
- **Parallel work:** Multiple authors working simultaneously without blocking
- **Merge conflict rate:** <5% of PRs have conflicts (branch isolation works)
- **Time to merge:** <5 minutes from "ready" to merged
- **PR review coverage:** 100% of PRs reviewed before merge
- **Contribution frequency:** Daily contributions from multiple authors

### Secondary Metrics
- **Branch lifetime:** Average time from branch creation to merge
- **PR iteration count:** Average commits per PR before merge
- **Preview usage:** Percentage of PRs tested before merge
- **Conflict resolution time:** When conflicts occur, time to resolve

### Qualitative Metrics
- Writer feedback: "I can contribute anytime without worrying about conflicts"
- No writers blocked waiting for others
- No lost work due to conflicts
- Clear understanding of branching workflow

---

## How It Works

### How Multiple Writers Work Together

**The Core Pattern: Work in Isolation, Merge When Ready**

Each writer works independently on their own branch:
- **Writer A** adds a forest path in their branch
- **Writer B** adds a castle path in their branch
- **Writer C** fixes a timeline issue in their branch
- **None block each other** - all work happens simultaneously
- **Each tests their changes** before merging
- **Main stays stable** - only tested, working changes merge in

**Key Benefit:** Writers contribute daily without waiting for others to finish. Changes stay isolated until ready, preventing incomplete work from affecting teammates.

**What This Looks Like:**
- Create your branch from main (gives you a clean starting point)
- Make your changes (add passages, fix issues, etc.)
- Test your preview (verify changes work)
- Merge when ready (changes go live quickly)
- Others do the same in their branches (no blocking)

---

### Contribution Workflow (Web-Based)

#### Phase 1: Set Up Branch Point

1. **Navigate to passage** where you want to add a branch
2. **Click edit (✏️)** on the .twee file
3. **Add your new choice** using link syntax:
   ```twee
   :: MorningWalk
   You step outside into the crisp morning air.

   [[Head to the park->ParkBench]]
   [[Explore the forest->ForestPath]]  # New choice
   ```
4. **Create new branch** at bottom of editor
5. **Name your branch** (e.g., `add-forest-path`)
6. **Propose changes** - creates PR
7. **Don't merge yet!** - just sets up the branch point

---

#### Phase 2: Write Your Content

8. **Switch to your branch** using branch dropdown
9. **Create new file** in src/ directory
10. **Name it with date** (e.g., `src/2025-11-15.twee`)
11. **Write your passage:**
    ```twee
    :: ForestPath

    The forest trail winds between ancient trees.

    [[Go deeper->DeepForest]]
    [[Return to park->ParkBench]]
    ```
12. **Commit to your branch** - stays isolated from main

---

#### Phase 3: Test and Merge

13. **Automatic build** runs on your branch
14. **Download preview artifact** from Actions tab
15. **Test your changes** locally
16. **AI validation** checks continuity automatically
17. **Review feedback** and fix any issues
18. **Approve paths** with `/approve-path` if needed
19. **Request review** from teammate (optional)
20. **Merge when ready** - changes go live in ~2 minutes

---

### Key Automation Features

#### 1. Automatic Resource Tracking
- **Resource-Passage Names** file auto-updates on every PR
- Shows all passages and their links
- Prevents duplicate passage names
- No manual tracking needed

---

#### 2. PR Preview Artifacts
- Every PR builds all 4 output formats
- Download link posted in PR comment
- Test locally before merging
- Exactly matches what will be deployed

---

#### 3. AI Continuity Checking
- Runs automatically on every PR
- Checks only new/modified paths (fast)
- Posts results as PR comments
- Provides confidence before merging

---

#### 4. Build Status Visibility
- Green checkmark when build succeeds
- Red X when build fails
- Click for detailed logs
- See exactly what broke

---

### Conflict Prevention

**Branch Isolation:**
- Each writer works in their own branch
- Changes don't affect others until merge
- Can work on different passages simultaneously
- Rare conflicts only when editing same passages

**Resource Tracking:**
- Auto-generated file shows all passage names
- Prevents accidental duplicates
- Updated automatically on every build
- No manual coordination needed

**Clear Documentation:**
- CONTRIBUTING.md has step-by-step instructions
- Examples show common patterns
- Tips for avoiding conflicts
- Explains common mistakes

---

## Edge Cases

### Edge Case 1: Simultaneous Edits to Same File
**Scenario:** Writer A and Writer B both edit the same passage simultaneously

**Current Behavior:**
- Each creates their own branch
- Both PRs build successfully
- Merge conflict when second PR tries to merge
- GitHub shows conflict, requires manual resolution

**Desired Behavior:**
- Branch isolation prevents issues during work
- First PR merges cleanly
- Second PR shows conflict
- GitHub provides visual merge tool
- Writer resolves and commits fix

**Status:** Working as intended - Git's merge conflict handling works well

---

### Edge Case 2: Duplicate Passage Names
**Scenario:** Writer A creates passage "Cave", Writer B also creates passage "Cave"

**Current Behavior:**
- Both branches build successfully (passage in own file)
- Resource-Passage Names shows both passages
- Merge creates duplicate passage names
- Tweego compiles but behavior is undefined

**Desired Behavior:**
- Resource tracking shows duplicate in PR preview
- Writer B sees Writer A's passage before creating own
- Writers communicate to avoid duplicates
- Rename passage if conflict exists

**Status:** Partially handled - resource file shows all passages, but no automatic conflict detection

---

### Edge Case 3: Long-Lived Branches
**Scenario:** Writer creates branch, works for a week, main branch advances significantly

**Current Behavior:**
- Writer's branch diverges from main
- PR shows many commits difference
- Merge may have conflicts
- Preview might not reflect latest main state

**Desired Behavior:**
- Writer periodically merges main into their branch
- Keeps branch up to date
- Reduces conflict risk
- Documentation suggests merging frequently

**Status:** Working as intended - Git handles this, documentation could improve

---

### Edge Case 4: Broken Links Across Branches
**Scenario:** Writer A creates link to passage that Writer B is creating in different branch

**Current Behavior:**
- Writer A's build shows broken link (passage doesn't exist yet)
- AI validation flags broken link
- Link works after both branches merge

**Desired Behavior:**
- Writers coordinate on passage names
- Writer A waits for Writer B's passage to exist
- Or Writer A creates placeholder passage
- Clear communication in PR discussions

**Status:** Acceptable - requires coordination, documentation explains approach

**Implementation Note:** Git branching model, merge strategies, and conflict resolution details are in architecture documentation.

---

### Edge Case 5: Resource File Merge Conflicts
**Scenario:** Two PRs both update Resource-Passage Names file

**Current Behavior:**
- Each branch generates its own resource file
- Resource file committed back to each branch
- Second PR to merge has conflict in resource file
- Requires manual resolution

**Desired Behavior:**
- Resource file regenerates automatically
- Merge conflict resolved by regenerating
- Or resource file excluded from commits (regenerated on merge)

**Status:** Minor annoyance - happens rarely, easy to resolve by regenerating

---

### Edge Case 6: PR Review Bottleneck
**Scenario:** Many PRs waiting for review, slowing progress

**Current Behavior:**
- PRs can merge without review (optional)
- Writers can self-merge if confident
- AI validation provides automated checking
- Team decides review policy

**Desired Behavior:**
- Trust automation for technical validation
- Human review focuses on story quality
- Optional review doesn't block progress
- Fast iteration during time-sensitive writing

**Status:** Working as intended - review is optional, automation handles validation

See [architecture/collaborative-workflow.md](../architecture/collaborative-workflow.md) for technical design.

---

## What Could Go Wrong?

### Risk 1: Merge Conflict Confusion
**Impact:** Medium - non-technical writers struggle with conflicts
**Mitigation:** Branch isolation minimizes conflicts, documentation explains resolution
**Fallback:** Ask for help in PR comments, team assists

---

### Risk 2: Coordination Overhead
**Impact:** Low - writers spend time coordinating instead of writing
**Mitigation:** Branch isolation allows independent work, automation reduces coordination needs
**Fallback:** Async communication in PR comments

---

### Risk 3: Lost Work
**Impact:** High - writer loses work due to conflict or error
**Mitigation:** Git preserves all commits, nothing truly lost
**Fallback:** Recover from commit history or local copy

---

### Risk 4: Duplicate Passage Names
**Impact:** Medium - story breaks due to duplicate passages
**Mitigation:** Resource tracking shows all passages, review catches duplicates
**Fallback:** Rename one passage, update links

---

## Future Enhancements

### Considered but Not Planned
- **Real-time conflict detection:** Flag potential conflicts before merge
  - **Why not:** Rare occurrence, Git handles well

- **Automatic merge conflict resolution:** Auto-resolve resource file conflicts
  - **Why not:** Conflicts are rare, regeneration is simple workaround

- **Branch templates:** Pre-configured branch structure for common patterns
  - **Why not:** Current workflow simple enough, templates add complexity

- **Review requirements:** Require approval before merge
  - **Why not:** Slows iteration, automation provides validation

---

## Metrics Dashboard

### Current Performance (as of Nov 22, 2025)
- ✅ **Merge conflict rate:** <5% (rare conflicts)
- ✅ **Parallel work:** Multiple authors active simultaneously
- ✅ **Time to merge:** <5 minutes from ready to merged
- ✅ **PR review coverage:** 100% of PRs reviewed (informal)
- ✅ **Daily contributions:** Multiple authors contributing regularly
- ✅ **Lost work incidents:** 0 (no work lost to conflicts)

### Workflow Metrics
- **Average branch lifetime:** ~1-2 days
- **Average commits per PR:** ~2-3
- **Preview usage:** ~100% of PRs tested
- **Conflict resolution time:** ~5-10 minutes when occurs

---

## Success Criteria Met

- [x] Multiple authors work simultaneously without blocking
- [x] Branch isolation prevents conflicts during work
- [x] PR preview artifacts enable testing before merge
- [x] Resource tracking prevents naming conflicts
- [x] Clear documentation for non-technical writers
- [x] Fast merge process (<5 minutes)
- [x] Low conflict rate (<5%)
- [x] Zero lost work incidents

---

## Related Documents

- [CONTRIBUTING.md](/home/user/NaNoWriMo2025/CONTRIBUTING.md) - Step-by-step collaboration guide
- [features/automated-resource-tracking.md](/home/user/NaNoWriMo2025/features/automated-resource-tracking.md) - Passage name tracking
- [features/automated-build-deploy.md](/home/user/NaNoWriMo2025/features/automated-build-deploy.md) - Preview artifacts
- [features/ai-copy-editing-team.md](/home/user/NaNoWriMo2025/features/ai-copy-editing-team.md) - AI Copy Editing Team automated validation
- [PRINCIPLES.md](/home/user/NaNoWriMo2025/PRINCIPLES.md) - "Automation Over Gatekeeping" principle

---

## Lessons Learned

### What Worked Well
- **Branch isolation:** Writers work independently without blocking
- **PR previews:** Testing before merge prevents broken deployments
- **Auto-generated resources:** No manual tracking reduces coordination overhead
- **Web-based workflow:** No Git expertise required

### What Could Be Better
- **Conflict documentation:** Could better explain conflict resolution
- **Branch coordination:** Could provide better visibility into active branches
- **Review workflow:** Could streamline review process

### What We'd Do Differently
- **Earlier branch strategy:** Could have defined branching model upfront
- **Conflict prevention:** Could have built duplicate passage name detection
- **Communication tools:** Could have integrated better coordination tools
