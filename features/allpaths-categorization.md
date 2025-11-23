# Feature PRD: AllPaths Categorization

**Status:** 🔴 Critical Issue - Trust Violation
**Owner:** Product Manager
**Last Updated:** 2025-11-23
**Priority:** HIGH

---

## Executive Summary

**THE PROBLEM:** Writers viewing allpaths.html on the deployed site see all paths marked "unchanged" (47 unchanged, 0 new, 0 modified), even immediately after merging a PR that showed meaningful categorization (1 new, 23 modified, 23 unchanged). This creates confusion and destroys trust in our automation.

**ROOT CAUSE:** Path categories are git-relative, comparing current build against a base branch. In PR builds, this comparison is meaningful (PR branch vs main). In deployment builds, everything compares against HEAD (itself), so all paths appear "unchanged."

**STRATEGIC IMPACT:** Violates our core principle of "Transparency and Inspectability." Users lose confidence when the same data shows different categories in different contexts without explanation.

**RECOMMENDED SOLUTION:** Context-aware categorization - use git-relative categories in PR context (what's changing in this PR?) and time-based categories in deployment context (what's recent in the story?).

---

## User Problem

**For writers viewing allpaths.html:**

### Problem 1: Broken Trust
A writer reviews PR #82 and sees:
- 1 new path
- 23 modified paths
- 23 unchanged paths

They merge the PR and immediately visit the deployed site, expecting similar information. Instead they see:
- 0 new paths
- 0 modified paths
- 47 unchanged paths

**Pain Point:** "I don't understand. The PR showed new and modified paths. Why does the deployed site say everything is unchanged? Can I trust any of this information?"

### Problem 2: Lost Context
After NaNoWriMo completion, a writer wants to understand the story's evolution:
- Which paths were added recently?
- Which paths have been updated this week?
- What's the writing activity timeline?

**Pain Point:** "The deployed site tells me everything is 'unchanged,' but that's obviously not true. How do I see what's actually been changing?"

### Problem 3: No Historical Tracking
During active writing, writers want to track progress:
- See what got completed today
- Identify paths that need updates
- Understand which content is fresh vs stale

**Pain Point:** "Categories only make sense during PR review. Once merged, all context disappears."

---

## User Stories

### Story 1: Writer Viewing Deployed Site
**As a** writer visiting the deployed allpaths.html
**I want** to see which paths were added or updated recently
**So that** I can understand the story's recent evolution and find new content

**Acceptance Criteria:**
- Categories on deployed site show meaningful information (not "all unchanged")
- Categories reflect time-based context: "Recent" vs "Older"
- Consistent interface between PR and deployment (same UI, different semantics)
- Clear indication of what "recent" means (e.g., "within 7 days")
- Writers can filter to "Recent" to see actively developed paths

**Current Status:** ❌ Failing - deployment shows all paths as "unchanged"

---

### Story 2: Writer Understanding PR Changes
**As a** writer reviewing a PR
**I want** to see which paths are new/modified/unchanged IN THIS PR
**So that** I can validate the changes and approve the merge

**Acceptance Criteria:**
- Categories in PR builds compare PR branch against base branch (main)
- "New" means new paths introduced by this PR
- "Modified" means paths changed by this PR
- "Unchanged" means paths not affected by this PR
- Writers understand categories are PR-specific (not historical)

**Current Status:** ✅ Working - PR categorization is correct

---

### Story 3: Writer Tracking Progress
**As a** writer during NaNoWriMo
**I want** to see which paths were completed recently
**So that** I can track daily/weekly progress and celebrate milestones

**Acceptance Criteria:**
- Can identify paths added "today," "this week," "this month"
- Can filter to recent activity to see what's fresh
- Categories help answer "what did we accomplish this week?"
- Progress tracking available in deployed site (not just PRs)

**Current Status:** ❌ Failing - no time-based tracking available

---

## Expected Behavior

### Context 1: Pull Request Builds

**When:** Build triggered by PR (GITHUB_BASE_REF is set)
**Purpose:** Show what's changing in THIS PR
**Comparison:** PR branch vs base branch (usually main)

**Categories:**
- **NEW** = Paths that don't exist on base branch (created by this PR)
- **MODIFIED** = Paths that exist but have different content (changed by this PR)
- **UNCHANGED** = Paths that match base branch exactly (not affected by this PR)

**Filter Buttons:**
- "New (N)" - paths added by this PR
- "Modified (M)" - paths changed by this PR
- "Unchanged (U)" - paths not affected by this PR

**Example Display:**
```
Path Categories:
- 1 new (created by this PR)
- 23 modified (changed by this PR)
- 23 unchanged (unaffected by this PR)
```

**Status:** ✅ This is working correctly

---

### Context 2: Deployment Builds (Main Branch)

**When:** Build triggered on main branch (GITHUB_BASE_REF is NOT set)
**Purpose:** Show what's recent in the story
**Comparison:** Time-based relative to current date

**Categories:**
- **RECENT** = Paths created or modified within configurable timeframe (default: 7 days)
- **UPDATED** = Paths modified within extended timeframe (default: 30 days)
- **OLDER** = Paths older than extended timeframe

**Filter Buttons:**
- "Recent (N)" - paths created/modified in last 7 days
- "Updated (M)" - paths modified in last 30 days (excluding Recent)
- "Older (U)" - paths older than 30 days

**Configuration Options:**
- Recent threshold: 7 days (configurable via environment variable)
- Updated threshold: 30 days (configurable via environment variable)
- Could adapt to NaNoWriMo: "Added this month" during November

**Example Display:**
```
Path Activity (Last 30 Days):
- 5 recent (last 7 days)
- 18 updated (last 30 days)
- 24 older (30+ days ago)
```

**Status:** ❌ Currently shows "47 unchanged" - needs implementation

---

## Success Metrics

### Primary Metrics
- **Trust metric:** Zero user confusion about category meanings
- **Consistency:** Categories always provide meaningful information (never "all unchanged")
- **Clarity:** Users can explain what categories mean without reading docs
- **Utility:** Writers actively use category filters to find content

### Secondary Metrics
- **PR review workflow:** Reviewers use categories to understand changes
- **Progress tracking:** Writers use deployment categories to track activity
- **Filter usage:** Writers regularly use filter buttons (logged via analytics)

### Qualitative Success
- Writer feedback: "Categories help me understand what's changing"
- No reports of confusion about why categories differ between PR and deployment
- Writers cite categories when discussing story progress

---

## Technical Requirements (What, Not How)

### Requirement 1: Context Detection
The system must detect whether it's running in PR context or deployment context and apply appropriate categorization logic.

**In PR context:** Use git-relative categorization
**In deployment context:** Use time-based categorization

### Requirement 2: Time-Based Categorization
When in deployment context, categorize paths based on their creation/modification dates:
- Use existing `created_date` and `commit_date` fields from validation cache
- Compare against current date to determine recency
- Configurable thresholds for "recent" and "updated"

### Requirement 3: Consistent UI with Context-Specific Semantics
The allpaths.html interface should look the same in both contexts but adapt labels and meanings:

**PR Context:**
- Filter buttons: "New (N) | Modified (M) | Unchanged (U)"
- Badges: "New" (blue), "Modified" (yellow), "Unchanged" (gray)
- Tooltip/help text: "Categories show changes IN THIS PR"

**Deployment Context:**
- Filter buttons: "Recent (N) | Updated (M) | Older (U)"
- Badges: "Recent" (blue), "Updated" (yellow), "Older" (gray)
- Tooltip/help text: "Categories show activity in last N days"

### Requirement 4: Explanatory Context
The page must clearly communicate what categories mean in the current context:

**PR builds:** Banner saying "Showing changes in this PR (comparing against main branch)"
**Deployment builds:** Banner saying "Showing recent activity (last 7/30 days)"

### Requirement 5: Zero Breaking Changes
Existing PR workflow must continue working without changes:
- PR categorization logic unchanged
- PR comment format unchanged
- Validation modes (new-only, modified, all) unchanged

---

## Edge Cases

### Edge Case 1: Fresh Repository
**Scenario:** First build with no validation cache history

**PR Context:**
- All paths are "new" (nothing exists on base branch yet)
- Expected: Works correctly ✓

**Deployment Context:**
- All paths have today's date (just created)
- All paths appear as "recent"
- Expected: Reasonable - everything IS recent in a new repo ✓

---

### Edge Case 2: Inactive Repository
**Scenario:** No changes for 60+ days, then view deployed site

**Deployment Context:**
- All paths categorized as "older"
- 0 recent, 0 updated, 47 older
- Expected: Accurate - shows repository is inactive ✓

---

### Edge Case 3: Missing Date Metadata
**Scenario:** Validation cache missing `created_date` or `commit_date` fields

**Deployment Context:**
- Fallback: Categorize as "older" (conservative approach)
- Or: Use git history to calculate dates (more accurate but slower)
- Expected: Graceful degradation - don't break the page ✓

---

### Edge Case 4: Time Zone Confusion
**Scenario:** Server time zone differs from author time zones

**Deployment Context:**
- Use UTC for all date comparisons
- Display dates in ISO format or UTC
- "Recent" means "within last 7 days UTC"
- Expected: Consistent behavior regardless of time zone ✓

---

### Edge Case 5: PR Against Non-Main Branch
**Scenario:** PR from feature-branch-B into feature-branch-A (not main)

**PR Context:**
- Compare against base branch (feature-branch-A)
- Categories show changes relative to feature-branch-A
- Expected: Works correctly - git-relative logic handles this ✓

---

### Edge Case 6: Local Development Build
**Scenario:** Developer runs build-allpaths.sh locally

**Context Detection:**
- No GITHUB_BASE_REF environment variable
- Could be either: local development or deployment
- Expected: Treat as deployment context (time-based categories)
- Acceptable: Both contexts could be useful locally ✓

---

## What Could Go Wrong?

### Risk 1: Users Don't Understand Context Switching
**Impact:** Medium - Users confused why categories differ between PR and deployment
**Mitigation:** Clear banners/help text explaining context
**Fallback:** Link to documentation explaining both modes

---

### Risk 2: "Recent" Definition Disagreement
**Impact:** Low - Users disagree about 7-day threshold
**Mitigation:** Make threshold configurable
**Fallback:** Document rationale for default value

---

### Risk 3: Missing Date Metadata
**Impact:** Medium - Old cache entries lack created_date
**Mitigation:** Graceful fallback to git history lookup
**Fallback:** Categorize as "older" if dates unavailable

---

### Risk 4: Performance Impact
**Impact:** Low - Time calculations add overhead
**Mitigation:** Dates already in cache, just comparison needed
**Fallback:** Pre-compute categories at cache update time

---

## Acceptance Criteria (Definition of Done)

### Must Have
- [ ] Deployment builds show time-based categories (not "all unchanged")
- [ ] PR builds continue showing git-relative categories (unchanged behavior)
- [ ] allpaths.html clearly indicates which mode it's in (banner/header)
- [ ] Filter buttons have context-appropriate labels
- [ ] Zero breaking changes to existing PR workflow

### Should Have
- [ ] Configurable thresholds for "recent" and "updated" timeframes
- [ ] Help text/tooltips explaining what categories mean
- [ ] PR comments explain validation was done in "modified" mode (git-relative)

### Could Have
- [ ] Analytics to track which filters users actually use
- [ ] Admin interface to adjust timeframes
- [ ] Custom thresholds per-project (e.g., NaNoWriMo-specific)

### Won't Have (This Iteration)
- [ ] Historical trend visualization (show activity over time)
- [ ] Per-author activity tracking
- [ ] Customizable category names

---

## User-Facing Documentation Updates

### allpaths/README.md Changes Needed

**Section: "Browsing Paths"**

Add clarity about context-aware categories:

```markdown
### Understanding Path Categories

Path categories adapt to the context:

**In Pull Requests (PR Builds):**
Categories show what's changing IN THIS PR:
- **New** - Paths that don't exist on the base branch
- **Modified** - Paths whose content changed in this PR
- **Unchanged** - Paths not affected by this PR

Use this to validate PR changes and review impact.

**On Deployed Site (Main Branch):**
Categories show recent activity:
- **Recent** - Paths created or modified in last 7 days
- **Updated** - Paths modified in last 30 days
- **Older** - Paths unchanged for 30+ days

Use this to track writing progress and find recent content.
```

### CONTRIBUTING.md Changes Needed

Add section explaining PR category behavior:

```markdown
### Understanding PR Build Artifacts

When you create a PR, the build will categorize paths relative to the base branch:
- **New paths** - Created by your PR
- **Modified paths** - Changed by your PR
- **Unchanged paths** - Not affected by your PR

This helps reviewers understand the impact of your changes.

Note: After merging, the deployed site will show time-based categories instead.
```

---

## Related Documents

- [formats/allpaths/README.md](/home/user/NaNoWriMo2025/formats/allpaths/README.md) - AllPaths format documentation
- [formats/allpaths/CATEGORIZATION_VALIDATION.md](/home/user/NaNoWriMo2025/formats/allpaths/CATEGORIZATION_VALIDATION.md) - Current categorization logic
- [architecture/001-allpaths-format.md](/home/user/NaNoWriMo2025/architecture/001-allpaths-format.md) - Technical architecture
- [PRINCIPLES.md](/home/user/NaNoWriMo2025/PRINCIPLES.md) - "Transparency and Inspectability" principle

---

## Open Questions for Architect/Developer

**Q1:** Should we use environment variables (GITHUB_BASE_REF) or git commands to detect context?
**PM Perspective:** Either works - optimize for reliability and clarity.

**Q2:** What thresholds for "recent" and "updated"?
**PM Recommendation:** 7 days / 30 days as defaults, configurable via environment variables.

**Q3:** Should we update validation cache or compute at display time?
**PM Perspective:** Either works - optimize for performance and maintainability.

**Q4:** Should we show date ranges in the UI (e.g., "Recent (last 7 days)")?
**PM Recommendation:** Yes - transparency is key. Show what "recent" means.

**Q5:** Should local builds use time-based or git-relative categories?
**PM Recommendation:** Time-based (same as deployment) - more useful for local testing.

---

## Success Definition

**This feature is successful when:**

1. **Zero trust violations:** Writers never see "all unchanged" on deployed site
2. **Clear context:** Writers understand what categories mean in each context
3. **Useful information:** Writers actively use categories to find content and track progress
4. **Consistent experience:** Same UI, adapted semantics, clear explanations
5. **No regressions:** PR workflow continues working exactly as before

**Failure modes to avoid:**

- ❌ Writers confused about why categories differ between PR and deployment
- ❌ Deployed site showing "all unchanged" (current bug)
- ❌ Categories provide meaningless information in any context
- ❌ Breaking changes to PR review workflow

---

## Timeline and Dependencies

**Priority:** HIGH - Trust violation affecting user confidence

**Dependencies:**
- Validation cache already has `created_date` and `commit_date` fields
- Git history available for fallback if dates missing
- Environment detection (GITHUB_BASE_REF) already in use

**Estimated Complexity:** Medium
- Core logic change is straightforward (time comparison vs git comparison)
- UI changes are minimal (labels and help text)
- Testing needed for both contexts

**Recommended Approach:**
1. Architect designs context detection and time-based categorization logic
2. Developer implements with feature flag for safe rollout
3. PM validates with test cases in both contexts
4. Document and deploy

---

## Lessons Learned

### What Went Wrong
- **Single-context design:** Originally designed only for PR context (git-relative)
- **Assumed context:** Didn't consider deployment build would compare HEAD to HEAD
- **Missing documentation:** Never specified expected behavior in deployment context
- **No user testing:** Didn't have writers review deployed site to catch confusion

### What We'd Do Differently
- **Multi-context thinking:** Always ask "how does this work in PR vs deployment?"
- **User perspective:** Test features from writer's POV, not just developer's
- **Explicit specifications:** Document expected behavior in ALL contexts
- **Trust validation:** Ensure automation provides consistent, trustworthy information

### What This Teaches Us
- **Principle #5 (Transparency):** Mysterious behavior destroys trust faster than bugs
- **Context matters:** Same data needs different interpretations in different contexts
- **User expectations:** Writers assume categories persist after merge (reasonable!)
- **Fast iteration:** Ship, learn from real usage, fix issues quickly
