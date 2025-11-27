# Feature PRD: AI Continuity Checking

**Status:** Released ✅
**Owner:** Product Manager
**Last Updated:** 2025-11-22

---

## Feature Overview

AI Continuity Checking is a **validation feature** that automatically checks story paths for consistency issues. It determines which paths need validation based on what changed in a PR, then analyzes those paths and reports results in PR comments.

**Relationship to AllPaths:**
- **AllPaths HTML** is a separate browsing/tracking feature (see [allpaths-categorization.md](./allpaths-categorization.md))
- AllPaths shows dates, filters, and validation status for progress tracking
- Continuity checking uses internal git-based categories (NEW/MODIFIED/UNCHANGED) to determine what to validate
- These internal categories don't appear in the AllPaths HTML
- Validation results appear in PR comments, validation status appears as badges in HTML

---

## User Problem

**For collaborative branching narrative writers:**
- Branching narratives create exponential complexity - manually checking all paths is impossible
- Continuity errors multiply across branches (character names, timeline, plot consistency)
- One author's changes can introduce contradictions in another author's paths
- Testing every possible player journey manually takes hours or days
- Writers need confidence that the story maintains internal consistency across all branches

**Pain Point:** "I added a new path where the character learns the magic early, but I'm not sure if that breaks continuity in the 15 other paths where they don't know about it yet. I can't manually check every single path."

---

## User Stories

### Story 1: Writer Adding New Branch
**As a** writer adding a new story branch
**I want** automated validation of continuity across all affected paths
**So that** I can confidently add content without breaking existing story logic

**Acceptance Criteria:**
- AI checks all new paths automatically on every PR
- Results posted within minutes of PR creation
- Clear feedback on specific continuity issues
- Issues categorized by severity (minor, major, critical)
- Can see exactly where in the path the issue occurs

---

### Story 2: Reviewer Approving PR
**As a** reviewer checking another author's PR
**I want** to see AI validation results before approving
**So that** I can focus on creative feedback instead of hunting for continuity bugs

**Acceptance Criteria:**
- AI validation runs automatically on every PR
- Results appear as PR comment
- Can trust that technical continuity is checked
- Can focus review on story quality and creative choices

---

### Story 3: Writer Fixing Issues
**As a** writer addressing AI-flagged issues
**I want** to understand what's wrong and how to fix it
**So that** I can resolve continuity problems quickly

**Acceptance Criteria:**
- AI explains specific issue clearly
- Provides quotes from story showing the problem
- Suggests severity level (helps prioritize fixes)
- Can re-run validation after fixing to confirm resolution

---

### Story 4: Writer Approving Valid Paths
**As a** writer who has reviewed AI feedback
**I want** to mark paths as validated so they're not re-checked
**So that** future validations run faster and focus on new content

**Acceptance Criteria:**
- Can approve paths with `/approve-path` command
- Approved paths skipped in future validations
- Validation cache updated automatically
- Approved paths re-checked only if content changes

---

## Success Metrics

### Primary Metrics
- **Validation coverage:** 100% of PRs automatically validated
- **Feedback speed:** Results posted within minutes of PR workflow completion
- **Issue detection:** AI catches continuity errors before merge
- **Zero escaped errors:** No continuity issues merged to main branch

### Secondary Metrics
- **Validation efficiency:** New-only mode ~60% faster than full validation
- **Path approval rate:** Writers approve and dismiss issues regularly
- **False positive rate:** Low rate of incorrect issue flagging
- **Writer confidence:** Writers trust AI feedback and act on it

### Qualitative Metrics
- Writer feedback: "AI caught an issue I completely missed"
- No continuity errors discovered after merge
- Writers use validation modes appropriately (new-only → modified → all)

---

## How It Works

---

### How Continuity Checking Determines What to Validate

When you make changes to your story, the continuity checker analyzes each path to determine what needs validation. This analysis happens internally and helps the checker focus on paths that actually need review.

**Critical Principle:** Categories are about **PATH EXISTENCE**, not file changes. The fundamental question is: "Did this route through the story exist before this PR?" NOT "Did file content change?"

**Key Terms:**
- **Path/Route:** A sequence of passages from Start to an ending. "Path" and "route" are used interchangeably - both refer to a specific journey a player can take through the story.
- **Novel prose:** New story content (narrative text, dialogue, descriptions) that has never been validated before. This does NOT include: formatting changes (smart quotes, spacing), navigation changes (adding/removing links), or reorganization of existing prose (passage splits, content moves).
- **Content change:** ANY modification to a passage file, including: prose edits, formatting, navigation (links), or structure. Much broader than "novel prose."

**The Two-Level Test:**

The checker uses a two-level decision process:

1. **PRIMARY: Path Existence Test** - Did this exact sequence of passages exist in the base branch?
   - If YES → Path is either MODIFIED or UNCHANGED (never NEW)
   - If NO → Path is either NEW or MODIFIED (depends on prose novelty)

2. **SECONDARY: Content/Prose Test** - What changed?
   - If path existed: Did any passage content change? → MODIFIED or UNCHANGED
   - If path is new: Does it contain novel prose? → NEW or MODIFIED

**Decision Table:**

| Path existed before? | Contains novel prose? | Category | Reasoning |
|---------------------|----------------------|----------|-----------|
| YES | N/A (doesn't matter) | MODIFIED or UNCHANGED | Existing paths are never NEW, even if you added novel prose to them |
| YES | N/A | UNCHANGED | Path existed, no content changed in any passage |
| YES | N/A | MODIFIED | Path existed, at least one passage had content changes |
| NO | YES | NEW | New route with new story content needs first validation |
| NO | NO | MODIFIED | New route structure but prose was already validated (reorganization) |

The checker categorizes paths into three internal states to decide what needs validation:

#### NEW Paths (Internal Category)
**What it means:** This path did NOT exist before this PR AND contains novel prose (new story content never validated before).

**How to identify:**
1. Path existence test: Did this sequence of passages exist in base branch? → NO
2. Prose novelty test: Does it contain novel prose? → YES
3. Result: NEW

**What causes this:**
- Created new passage with new story content, and a path goes through it
- Added new link creating a path that didn't exist before, and that path includes novel prose
- Players can take a journey they couldn't before, reading prose they've never seen

**Example:** You create `KEB-251121.twee` with a new scene about discovering the cave. A path `Start → Forest → Cave → Victory` is NEW because:
1. This sequence didn't exist before (PATH test: NO)
2. The cave scene has novel prose (PROSE test: YES)
3. Result: NEW - needs first-time validation

**Why this matters:** NEW paths must be validated because they're routes with novel content that have never been reviewed.

---

#### MODIFIED Paths (Internal Category)
**What it means:** EITHER (Type A) this path existed before and content changed in at least one passage, OR (Type B) this path is new but contains no novel prose (reorganization).

**How to identify - Type A (Existing path with changes):**
1. Path existence test: Did this sequence exist in base branch? → YES
2. Content change test: Did any passage in the path change? → YES
3. Result: MODIFIED

**How to identify - Type B (New path, no novel prose):**
1. Path existence test: Did this sequence exist in base branch? → NO
2. Prose novelty test: Does it contain novel prose? → NO
3. Result: MODIFIED (reorganization case)

**What causes this:**
- **Type A:** Edited prose, formatting, or navigation in an existing path's passages
- **Type B:** Reorganized existing prose (passage splits, content moves) creating new navigation sequences

**Example 1 - Prose edits (Type A):**
Path `Start → Continue on → Village → End` existed before. You fix a typo in Village passage.
- PATH test: YES (existed before)
- CONTENT test: YES (Village changed)
- Result: MODIFIED

**Example 2 - Adding novel prose to existing path (Type A):**
Path `Start → Continue on → Village → End` existed before. You add a new paragraph with novel prose to Village.
- PATH test: YES (existed before) ← **This takes priority**
- Result: MODIFIED (path existed, so NEVER NEW even though prose is novel)

**Example 3 - Linter reformats files (Type A):**
Linter reformats 55 files (smart quotes, spacing). All paths through these files are MODIFIED.
- PATH test: YES (paths existed before)
- CONTENT test: YES (formatting changed)
- PROSE test: NO (prose not novel, just reformatted)
- Result: MODIFIED

**Example 4 - Passage split (Type B - CRITICAL CASE):**

**Before split:**
- Passage: `LongPassage` contains "First part. Second part."
- Path exists: `Start → LongPassage → End`

**After split:**
- `LongPassage` becomes "First part." with link `[[Continue→PartTwo]]`
- New passage `PartTwo` contains "Second part."
- Two paths now exist:
  1. `Start → LongPassage → PartTwo → End` (new sequence)
  2. `Start → LongPassage → End` (original sequence, but LongPassage changed)

**Analysis:**
- **New path** `Start → LongPassage → PartTwo → End`:
  - PATH test: NO (this sequence didn't exist before)
  - PROSE test: NO (prose from LongPassage, just reorganized)
  - Result: MODIFIED (Type B - reorganization)
- **Original path** `Start → LongPassage → End`:
  - PATH test: YES (this sequence existed before)
  - CONTENT test: YES (LongPassage changed - added link, removed prose)
  - Result: MODIFIED (Type A - existing path with changes)

**Why this matters:** MODIFIED paths may need re-validation because either the reading experience changed (Type A) or the navigation structure changed (Type B).

---

#### UNCHANGED Paths (Internal Category)
**What it means:** This path existed before this PR AND no passage in the path changed.

**How to identify:**
1. Path existence test: Did this sequence exist in base branch? → YES
2. Content change test: Did any passage in the path change? → NO
3. Result: UNCHANGED

**What causes this:**
- Made changes to other parts of the story
- This path doesn't include any passages you touched
- Path exists in both base and PR with identical content

**Example:** You add a new passage in one story branch. Paths in completely different branches are UNCHANGED:
- PATH test: YES (paths existed before)
- CONTENT test: NO (no passages in these paths changed)
- Result: UNCHANGED

**Why this matters:** UNCHANGED paths don't need re-validation - already validated, nothing changed.

---

### Understanding the Distinction: Paths vs Files

**Common confusion:** "I changed 55 files, so I have 55 NEW paths, right?"

**No.** The question isn't "Did files change?" It's "Did these paths exist before?"

**Mental model:**
- Think of your story as a map with paths from START to various endings
- NEW = A path that wasn't on the map before AND contains novel prose
- MODIFIED = Either (A) a path that was on the map before and the journey changed, OR (B) a new path structure with no novel prose
- UNCHANGED = A path that was on the map before and the journey is identical

**Quick reference:**
- Linter reformats 55 files → All paths MODIFIED (existed before + content changed)
- Split passage into two → New path sequence MODIFIED (new structure + no novel prose), original path MODIFIED (existed before + content changed)
- Add novel prose to existing path → Path MODIFIED (existed before, so never NEW)
- Create new passage with novel prose → Paths through it are NEW (didn't exist + novel prose)

---

### Three Validation Modes

Based on these internal categories, you can choose how thoroughly to validate:

**Important:** These categories (NEW/MODIFIED/UNCHANGED) are used internally by the continuity checker to determine what to validate. They don't appear in the AllPaths HTML interface. The AllPaths HTML shows date-based filters (created/modified last day/week) and validation status (validated or not), which serve different purposes (progress tracking and quality monitoring).

---

#### Mode 1: new-only (Default)
**Validates:** Only NEW paths (routes that didn't exist before with novel prose)
**Skips:** MODIFIED and UNCHANGED paths
**Speed:** Fastest (~2-5 paths, 2-5 minutes typical)

**When to Use:**
- Automatic PR builds (default)
- Daily writing - get fast feedback on new routes you created today
- You added new passages/routes and want to validate just those new journeys

**Command:** `/check-continuity` or `/check-continuity new-only`

**Why this is the default:**
Your daily workflow adds 1 new passage with a new route. That creates 1 NEW path (a route that never existed before) and potentially 10+ MODIFIED paths (existing routes where you added a navigation option). You want fast feedback on your new routes, not to wait for re-validation of existing routes where you only tweaked navigation.

---

#### Mode 2: modified
**Validates:** NEW paths + MODIFIED paths (new routes + existing routes with revisions)
**Skips:** UNCHANGED paths only
**Speed:** Medium (~5-10 paths, 5-15 minutes typical)

**When to Use:**
- Before requesting PR review
- Pre-merge validation - ensure all affected routes checked
- After fixing issues in new paths
- After formatting/linter changes (these create MODIFIED paths, not NEW)

**Command:** `/check-continuity modified`

**When to use this:**
Eventually you want those MODIFIED paths checked. Even though the routes existed before, the content changed (could be prose edits, navigation tweaks, or even just formatting). Run this before merging to ensure the revised reading experience is validated.

---

#### Mode 3: all
**Validates:** Every single path (NEW, MODIFIED, and UNCHANGED)
**Skips:** Nothing
**Speed:** Slow (~all paths, 20-40 minutes for large stories)

**When to Use:**
- After major story refactoring
- Periodic full story audits
- Investigating cross-path issues
- After updating AI model

**Command:** `/check-continuity all`

---

### What AI Checks

**For each path, AI analyzes:**
- Character consistency (names, traits, relationships)
- Plot coherence (events flow logically)
- Timeline accuracy (event sequences make sense)
- Setting/world consistency (locations, rules)
- Contradictions or plot holes

**AI provides:**
- Severity rating (none/minor/major/critical)
- Issue type (character/plot/timeline/setting/contradiction)
- Description and location of issues
- Specific quotes demonstrating problems

---

### Where Validation Results Appear

**Validation results are surfaced in two places:**

1. **PR Comments (Primary Interface)**
   - Detailed validation results posted as GitHub PR comments
   - Shows progress updates as paths are checked
   - Lists issues found in each path with severity and quotes
   - Provides summary statistics (paths checked, issues found)
   - Writers can respond with `/approve-path` command

2. **Validation Cache (Status Tracking)**
   - Validation status stored in `allpaths-validation-status.json`
   - Tracks which paths have been validated
   - Status displayed in AllPaths HTML as badges
   - "Validated" badge: Path has been reviewed and approved
   - "New" badge: Path has not yet been validated

**Note:** The internal categorization (NEW/MODIFIED/UNCHANGED) is used by the checker to determine what to validate, but is not displayed in the HTML. The HTML shows validation status (validated or not) and date filters for progress tracking.

---

### PR Comment Format

**Initial Comment (Validation Start):**
```markdown
## 🔍 Continuity Check Started

**Mode:** new-only _(use `/check-continuity modified` for broader checking)_

**Paths to validate:**
- 2 new paths (routes that didn't exist before)
- 3 modified paths (existing routes with revisions - skipped in new-only mode)
- 25 unchanged paths (existing routes with no changes - skipped)

Progress updates will appear below as each path completes...
```

**Progress Update (Per Path):**
```markdown
### 🟡 Path 2/2 Complete
**Path ID:** `a3f8b912`
**Route:** `Start → Continue on → Cave → Victory`
**Result:** minor
**Summary:** Small timeline inconsistency in character knowledge

<details>
<summary>Issues Found (1)</summary>

#### Issue 1: Timeline Inconsistency
- **Type:** timeline
- **Severity:** minor
- **Description:** Character knows about magic before learning about it
- **Location:** Passage a1b2c3d4e5f6

**Quotes:**
- Passage a1b2c3d4e5f6: "Javlyn used the defense spell..."
- Passage 9f8e7d6c5b4a: "Javlyn learned about magic for the first time..."

**Explanation:** Character uses magic before learning about it in this path.
</details>

💡 To approve this path: reply `/approve-path a3f8b912`
```

**Final Summary:**
```markdown
## ✅ Continuity Check Complete

**Mode:** new-only
**Validated:** 2 paths
**Skipped:** 3 modified, 25 unchanged

### Results by Severity
- 🟢 **1 path** with no issues
- 🟡 **1 path** with minor issues

### Next Steps
1. Review issues above
2. Fix or approve as appropriate
3. Use `/check-continuity modified` before merge for full validation
```

---

### Path Approval Workflow

**Writer reviews AI feedback and replies:**
```
Timeline issue is acceptable for story flow.
/approve-path a3f8b912
```

**Service responds:**
1. Verifies writer is repository collaborator
2. Downloads validation cache from PR artifacts
3. Marks path as validated
4. Commits updated cache to PR branch
5. Posts confirmation:

```markdown
✅ Successfully validated 1 path(s) by @username

**Approved paths:**
- `a3f8b912` (Start → Continue on → Cave → Victory)

These paths won't be re-checked unless their content changes.
```

---

## Edge Cases

### Edge Case 1: AI False Positives
**Scenario:** AI flags issue that isn't actually a problem (e.g., intentional plot mystery)

**Current Behavior:**
- Issue appears in PR comment
- Writer must evaluate and dismiss

**Desired Behavior:**
- Writer can approve path with `/approve-path` to skip future checks
- Can add comment explaining why issue is acceptable
- Path marked as validated in cache

**Status:** Handled by approval workflow

---

### Edge Case 2: AI Service Down
**Scenario:** Ollama service is unavailable or crashed

**Current Behavior:**
- Validation fails with error
- PR comment shows error message
- Does not block PR merge (validation is informational)

**Desired Behavior:**
- Clear error message explaining service issue
- Retry logic for transient failures
- Does not block PR workflow

**Status:** Error handling in place, does not block merges

---

### Edge Case 3: Very Long Paths
**Scenario:** Path exceeds AI model context window (20,000+ tokens)

**Current Behavior:**
- AI may truncate or fail
- Error reported in PR comment

**Desired Behavior:**
- Warn if path approaching context limits
- Suggest breaking story into smaller passages
- Graceful failure with clear message

**Status:** Rare - current paths well within limits

---

### Edge Case 4: Ambiguous Issues
**Scenario:** AI flags something that might or might not be an issue

**Current Behavior:**
- AI assigns severity based on analysis
- Writer reviews and makes judgment call

**Desired Behavior:**
- AI explains reasoning clearly
- Provides quotes demonstrating issue
- Writer makes final decision

**Status:** Working as intended - AI provides information, writer decides

---

### Edge Case 5: Cross-Path Issues
**Scenario:** Issue involves multiple paths (shared passage changes affect many paths)

**Current Behavior:**
- Each path validated independently
- Issue flagged in each affected path
- Can see pattern across multiple path results

**Desired Behavior:**
- AI identifies same issue in multiple paths
- Writer fixes once, resolves for all affected paths
- Cache invalidates all affected paths on content change

**Status:** Handled by content-based hashing - editing passage invalidates all paths containing it

---

### Edge Case 6: Validation Mode Confusion
**Scenario:** Writer doesn't understand which mode to use

**Current Behavior:**
- Default (new-only) runs automatically
- Writer can manually trigger other modes
- PR comments explain mode used

**Desired Behavior:**
- Clear mode descriptions in documentation
- PR comments suggest next mode if appropriate
- Usage patterns guide writers to correct mode

**Status:** Documentation in services/README.md, mode hints in PR comments

---

### Edge Case 7: Concurrent PR Validations
**Scenario:** Multiple PRs trigger validation simultaneously

**Current Behavior:**
- Each validation runs in separate thread
- Service tracks active jobs
- All validations complete successfully

**Desired Behavior:**
- Parallel processing without interference
- Status endpoint shows active jobs
- Resource limits prevent overload

**Status:** Working as intended - thread-based concurrency handles this

---

### Edge Case 8: Unreachable Paths
**Scenario:** A path becomes unreachable due to removed links, but still exists in the story structure

**Example:** You remove the link `[[Go to secret cave]]` from the Forest passage. The path `Start → Forest → SecretCave → End` still exists in the graph (all passages and links are present) but players can't reach it anymore.

**Current Behavior:**
- Path is categorized as MODIFIED (the Forest passage changed - link removed)
- Path is validated if in validation mode scope
- AI may flag that the path is unreachable

**Desired Behavior:**
- Path is correctly categorized based on content changes
- Writers can approve path if unreachability is intentional (dead branch)
- Or fix by restoring link if unintentional

**Status:** Working as intended - categorization is about content changes, not reachability

---

### Edge Case 9: Compound Changes
**Scenario:** A single PR makes multiple types of changes affecting the same path

**Example:** In one PR, you:
1. Fix typos in passage A (content change)
2. Add novel prose to passage B (content change with novel prose)
3. Add a new link in passage C (navigation change)
All three passages are part of path `Start → A → B → C → End`

**Question:** Is this path NEW or MODIFIED?

**Answer:**
- PATH test: Did `Start → A → B → C → End` exist before? → YES (sequence existed)
- Result: MODIFIED (path existed, so never NEW, even though passage B has novel prose)
- The novel prose in passage B doesn't make the path NEW because the path sequence already existed

**Current Behavior:**
- Path correctly categorized as MODIFIED
- Validation checks the entire path including the novel prose in passage B
- Single validation covers all changes

**Status:** Working as intended - PATH EXISTENCE test takes priority

See [architecture/ai-continuity-checking.md](../architecture/ai-continuity-checking.md) for technical design.

---

## What Could Go Wrong?

### Risk 1: AI Model Quality Issues
**Impact:** High - incorrect or missing issue detection
**Mitigation:** Use well-tested model (gpt-oss:20b-fullcontext), iterate on prompts
**Fallback:** Writers do manual review, treat AI as assistant not authority

---

### Risk 2: Service Downtime
**Impact:** Medium - validation unavailable
**Mitigation:** Service monitoring, auto-restart, health checks
**Fallback:** Validation is informational only, doesn't block merges

---

### Risk 3: Cost/Performance at Scale
**Impact:** Medium - validation takes too long for large stories
**Mitigation:** Selective validation modes optimize for common case
**Fallback:** Run full validation less frequently, rely on new-only for daily work

---

### Risk 4: False Positives Erode Trust
**Impact:** Medium - writers ignore AI if too many wrong flags
**Mitigation:** Iterate on prompt quality, make approval workflow easy
**Fallback:** Writers can always approve and move on

---

## Future Enhancements

### Considered but Not Planned
- **Multiple AI models:** Compare results from different models
  - **Why not:** Single model working well, added complexity not justified

- **Custom validation rules:** User-defined checks beyond AI
  - **Why not:** AI is flexible enough, rules would be brittle

- **Validation history tracking:** Track issues over time
  - **Why not:** Current cache is sufficient, added complexity

- **GitHub status checks:** Block merge on critical issues
  - **Why not:** Writers should make judgment call, not automatic blocks

---

## Metrics Dashboard

### Current Performance (as of Nov 22, 2025)
- ✅ **Validation coverage:** 100% of PRs automatically validated
- ✅ **Average validation time (new-only):** ~2 minutes for typical PR
- ✅ **Average validation time (modified):** ~5 minutes for typical PR
- ✅ **Time saved (new-only vs all):** ~60% faster
- ✅ **False positive rate:** Low (exact rate TBD with more usage)
- ✅ **Escaped errors:** 0 (zero continuity issues merged to main)

---

## Success Criteria Met

- [x] AI validation runs automatically on every PR
- [x] Results posted within minutes of PR completion
- [x] Clear, actionable feedback with specific quotes
- [x] Severity categorization (none/minor/major/critical)
- [x] Three validation modes (new-only/modified/all)
- [x] Path approval workflow working
- [x] Content-based change detection accurate
- [x] Zero continuity errors merged to main

---

## Related Documents

**User-facing:**
- [services/README.md](../services/README.md) - Webhook service usage and commands
- [PRINCIPLES.md](../PRINCIPLES.md) - "Automation Over Gatekeeping" principle

**Architecture/Implementation:**
- [architecture/002-validation-cache.md](../architecture/002-validation-cache.md) - How selective validation works (categorization, cache, fingerprinting)
- [formats/allpaths/README.md](../formats/allpaths/README.md) - AllPaths format technical documentation
- [architecture/001-allpaths-format.md](../architecture/001-allpaths-format.md) - AllPaths architecture decision record

---

## Lessons Learned

### What Worked Well
- **Random passage IDs:** Dramatically improved AI accuracy
- **Selective validation modes:** Fast feedback for daily work, thorough validation when needed
- **Real-time progress updates:** Writers see results as paths complete, can start fixing while validation continues
- **Approval workflow:** Easy to mark paths as validated and move on

### What Could Be Better
- **Prompt tuning:** Could further improve AI accuracy with more examples
- **Performance:** Could optimize for very large stories (100+ paths)
- **Mode guidance:** Could better guide writers on which mode to use when

### What We'd Do Differently
- **Earlier planning:** Random IDs added later, could have designed upfront
- **More prompt testing:** Could have tested more prompt variations before launching
- **Performance benchmarks:** Could have established baseline performance metrics earlier
