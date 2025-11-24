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

The checker categorizes paths into three internal states to decide what needs validation:

#### NEW Paths (Internal Category)
**What it means internally:** The path contains genuinely new prose that's never existed before.

**What causes this:**
- You created a new passage file with new story content
- A path goes through that new passage for the first time
- Players will read prose they've never seen before

**Example:** You create `KEB-251121.twee` with a new scene. Any path that includes this passage is categorized as NEW internally.

**Why this matters:** NEW paths always need validation because they contain content that hasn't been checked yet.

---

#### MODIFIED Paths (Internal Category)
**What it means internally:** The path already existed, but you changed the navigation (added/removed/changed links).

**What causes this:**
- You added a new choice to an existing passage (new `[[link]]`)
- You removed a choice from an existing passage
- You changed where a link points
- The prose in the passages didn't change, just the navigation options

**Example:** You edit an existing passage to add `[[Empty kitchen->Day 21 KEB]]`. All paths that go through this passage are categorized as MODIFIED internally - same prose, but now there's an additional choice available.

**Why this matters:** MODIFIED paths may need re-validation if navigation changes affect flow or coherence.

**Common scenario:** When you add a link to a passage near the story root (like the Start passage), this can create 10+ MODIFIED paths. But you only added one line - the link - so there's very little new prose to validate.

---

#### UNCHANGED Paths (Internal Category)
**What it means internally:** Nothing changed at all. Same prose, same links, same structure.

**What causes this:**
- You made changes to other parts of the story
- This path doesn't include any passages you touched

**Example:** You add a new passage for one story branch. Paths in completely different branches remain UNCHANGED internally.

**Why this matters:** UNCHANGED paths don't need re-validation - you already validated them, nothing changed.

---

### Three Validation Modes

Based on these internal categories, you can choose how thoroughly to validate:

**Important:** These categories (NEW/MODIFIED/UNCHANGED) are used internally by the continuity checker to determine what to validate. They don't appear in the AllPaths HTML interface. The AllPaths HTML shows date-based filters (created/modified last day/week) and validation status (validated or not), which serve different purposes (progress tracking and quality monitoring).

---

#### Mode 1: new-only (Default)
**Validates:** Only NEW paths (genuinely new prose content)
**Skips:** MODIFIED and UNCHANGED paths
**Speed:** Fastest (~2-5 paths, 2-5 minutes typical)

**When to Use:**
- Automatic PR builds (default)
- Daily writing - get fast feedback on what you wrote today
- Don't wait for link-only changes to be validated

**Command:** `/check-continuity` or `/check-continuity new-only`

**Why this is the default:**
Your daily workflow adds 1 new passage. That creates 1 NEW path (what you care about) and potentially 10+ MODIFIED paths (same prose, just new link added). You want fast feedback on your new content, not to wait for re-validation of prose you didn't change.

---

#### Mode 2: modified
**Validates:** NEW paths + MODIFIED paths (prose changes + navigation changes)
**Skips:** UNCHANGED paths only
**Speed:** Medium (~5-10 paths, 5-15 minutes typical)

**When to Use:**
- Before requesting PR review
- Pre-merge validation - ensure all affected paths checked
- After fixing issues in new paths

**Command:** `/check-continuity modified`

**When to use this:**
Eventually you want those MODIFIED paths checked (even though prose is the same, navigation changes could affect flow). Run this before merging, but not necessarily on every commit during development.

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
- 2 new paths
- 3 modified paths (skipped)
- 25 unchanged paths (skipped)

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
