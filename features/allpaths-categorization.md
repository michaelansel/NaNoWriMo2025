# Feature PRD: AllPaths Context-Aware Categorization

**Status:** ✅ Active Feature
**Owner:** Product Manager
**Last Updated:** 2025-11-23
**Priority:** Core Feature

---

## Executive Summary

Writers need different information when viewing paths in different contexts. During pull request review, they need to see **what's changing in this PR**. On the deployed site, they need to see **what's recent in the story**.

AllPaths categorization adapts to context, providing the right information at the right time:
- **PR Context:** Git-relative categories show changes in this PR (New, Modified, Unchanged)
- **Deployment Context:** Time-based categories show recent writing activity (Recent, Updated, Older)

This context-aware approach ensures writers always get meaningful, actionable information regardless of where they're viewing paths.

---

## User Needs

Writers interact with AllPaths in two distinct contexts, each with different information needs:

### Need 1: Understanding PR Changes
**Context:** Reviewing a pull request before merging

**User Goal:** Understand the impact of proposed changes on the story

**Questions Writers Need Answered:**
- Which paths are new in this PR?
- Which existing paths will change if we merge?
- Which paths are unaffected by this PR?
- What's the scope of this change?

**Why This Matters:** Writers need to validate changes, catch unintended consequences, and approve PRs with confidence.

---

### Need 2: Tracking Writing Progress
**Context:** Viewing the deployed site during active writing

**User Goal:** Monitor recent writing activity and story evolution

**Questions Writers Need Answered:**
- Which paths were completed recently?
- What writing activity happened this week?
- Which paths are actively being developed vs stable?
- Where is the story growing?

**Why This Matters:** Writers need to track progress toward NaNoWriMo goals, identify stale content, and coordinate collaborative work.

---

### Need 3: Clear Context Indicators
**Context:** Using AllPaths in either PR or deployment context

**User Goal:** Understand what the categories mean in the current view

**Questions Writers Need Answered:**
- What do these categories represent right now?
- Why do categories differ between PR and deployed site?
- How should I interpret this information?

**Why This Matters:** Writers need transparency to trust the automation and make informed decisions.

---

## User Stories

### Story 1: Reviewing Pull Request Changes
**As a** writer reviewing a pull request
**I want** to see which paths are affected by this PR
**So that** I can validate the changes and understand the impact before merging

**Acceptance Criteria:**
- Categorization shows changes relative to base branch
- "New" category identifies paths introduced by this PR
- "Modified" category identifies paths whose content changed in this PR
- "Unchanged" category identifies paths not affected by this PR
- Filter buttons allow focusing on new or modified paths
- Clear indicators show this is PR-specific comparison

**How We Deliver:** Git-relative categorization compares PR branch against base branch, providing a diff-style view of story changes.

---

### Story 2: Monitoring Writing Progress
**As a** writer viewing the deployed site during active writing
**I want** to see which paths were completed or updated recently
**So that** I can track progress and coordinate with other authors

**Acceptance Criteria:**
- Categorization shows time-based activity
- "Recent" category identifies paths created or updated in last 7 days
- "Updated" category identifies paths modified in last 30 days
- "Older" category identifies stable paths unchanged for 30+ days
- Filter buttons allow focusing on recent work
- Clear indicators show timeframes for each category

**How We Deliver:** Time-based categorization uses path creation and modification dates from validation cache, providing progress tracking view.

---

### Story 3: Understanding Category Meanings
**As a** writer using AllPaths in different contexts
**I want** to understand what categories mean in my current view
**So that** I can interpret the information correctly

**Acceptance Criteria:**
- Banner or header clearly indicates current context (PR or Deployment)
- Category labels are context-appropriate ("New/Modified/Unchanged" in PRs, "Recent/Updated/Older" on deployed site)
- Help text explains what each category means in current context
- Documentation explains why categories differ between contexts
- Consistent UI design across both contexts

**How We Deliver:** Context detection determines environment, UI adapts labels and help text accordingly, clear documentation explains both modes.

---

## Feature Behavior

AllPaths categorization adapts based on the build context, providing relevant information for each situation.

### Pull Request Context

**When Active:** Pull request builds (GITHUB_BASE_REF environment variable is set)

**Purpose:** Show what's changing in this specific PR

**Categorization Method:** Git-relative comparison between PR branch and base branch

**Categories:**
- **NEW** - Paths that don't exist on base branch (introduced by this PR)
- **MODIFIED** - Paths that exist but have different content (changed by this PR)
- **UNCHANGED** - Paths that match base branch exactly (not affected by this PR)

**User Interface:**
- Filter buttons: "New (N) | Modified (M) | Unchanged (U)"
- Category badges: "New" (blue), "Modified" (yellow), "Unchanged" (gray)
- Context banner: "Showing changes in this PR (comparing against [base-branch])"
- Statistics: "X new, Y modified, Z unchanged paths"

**Use Cases:**
- Validating PR changes before merge
- Understanding PR impact on story
- Reviewing scope of proposed changes
- Identifying unintended consequences

---

### Deployment Context

**When Active:** Main branch builds (GITHUB_BASE_REF is not set)

**Purpose:** Show recent writing activity and story evolution

**Categorization Method:** Time-based comparison using path creation and modification dates

**Categories:**
- **RECENT** - Paths created or modified in last 7 days
- **UPDATED** - Paths modified in last 30 days (excluding those in Recent)
- **OLDER** - Paths unchanged for more than 30 days

**User Interface:**
- Filter buttons: "Recent (N) | Updated (M) | Older (U)"
- Category badges: "Recent" (blue), "Updated" (yellow), "Older" (gray)
- Context banner: "Showing recent activity (last 7/30 days)"
- Statistics: "X recent, Y updated, Z older paths"

**Configuration:**
- Recent threshold: 7 days (configurable)
- Updated threshold: 30 days (configurable)
- Thresholds can be adjusted via environment variables

**Use Cases:**
- Tracking NaNoWriMo progress
- Finding recently completed paths
- Identifying actively developed content
- Coordinating collaborative writing
- Monitoring writing velocity

---

## Success Metrics

### User Understanding
- **Category clarity:** Writers can explain what categories mean in each context
- **Context awareness:** Writers understand why categories differ between PR and deployment
- **Trust:** Writers cite category information when making decisions

### Feature Usage
- **Active filtering:** Writers regularly use category filters to find paths
- **PR workflow:** Reviewers use categories to understand PR scope
- **Progress tracking:** Writers use deployment categories to monitor activity
- **Collaboration:** Teams use categories to coordinate work

### Information Quality
- **Meaningful categorization:** Categories always provide actionable information in both contexts
- **Accurate detection:** Context detection reliably identifies PR vs deployment environments
- **Useful thresholds:** Time-based thresholds (7/30 days) align with writing patterns

### Qualitative Indicators
- Writers reference categories in PR discussions
- Writers use categories to answer "what changed?" and "what's recent?" questions
- No confusion or misinterpretation of category meanings
- Categories cited as valuable for understanding story evolution

---

## Technical Requirements

These requirements define WHAT the system must do (not HOW to implement it).

### Context Detection
The system detects build context and selects appropriate categorization:
- **PR context:** Triggered when GITHUB_BASE_REF environment variable is set
- **Deployment context:** Triggered when GITHUB_BASE_REF is not set
- Detection is reliable and unambiguous

### Dual Categorization Logic
The system provides two categorization modes:

**Git-Relative Mode (PR Context):**
- Compares PR branch against base branch
- Identifies new, modified, and unchanged paths relative to base
- Categorization reflects PR-specific changes

**Time-Based Mode (Deployment Context):**
- Uses path creation and modification dates from validation cache
- Compares dates against current time to determine recency
- Categorization reflects writing activity timeline

### Adaptive User Interface
The allpaths.html interface adapts to context while maintaining consistent design:

**Context Indicators:**
- Banner clearly states current mode and what categories represent
- Help text explains category meanings for current context

**Context-Appropriate Labels:**
- PR context: "New / Modified / Unchanged" terminology
- Deployment context: "Recent / Updated / Older" terminology
- Filter buttons use context-appropriate labels
- Category badges use context-appropriate labels

**Consistent Visual Design:**
- Same color scheme across contexts (blue/yellow/gray)
- Same layout and structure
- Same interaction patterns (filters, collapsible content)

### Configurable Thresholds
Time-based categorization supports configurable thresholds:
- Recent threshold (default: 7 days)
- Updated threshold (default: 30 days)
- Configuration via environment variables
- Clear indication of active thresholds in UI

### Backward Compatibility
Changes preserve existing functionality:
- PR categorization behavior unchanged
- Validation cache format unchanged
- Validation modes (new-only, modified, all) work in both contexts
- No breaking changes to existing workflows

---

## Edge Cases

### Fresh Repository
**Scenario:** First build with no prior history

**Behavior:**
- PR context: All paths categorized as "new" (nothing exists on base branch)
- Deployment context: All paths categorized as "recent" (everything just created)
- Both behaviors are correct and expected

**Why It Works:** Fresh repositories legitimately have all-new content, so categorization accurately reflects reality.

---

### Inactive Repository
**Scenario:** No changes for extended period (60+ days)

**Behavior:**
- Deployment context: All paths categorized as "older"
- Statistics show 0 recent, 0 updated, all older
- Accurately represents repository inactivity

**Why It Works:** Time-based categorization correctly identifies stale content, helping writers see when work has stalled.

---

### Missing Date Metadata
**Scenario:** Validation cache lacks `created_date` or `commit_date` fields

**Behavior:**
- System uses fallback: categorize as "older" (conservative approach)
- Alternative: Query git history to calculate dates (slower but accurate)
- Page remains functional regardless of missing data

**Why It Works:** Graceful degradation prevents broken pages, conservative categorization avoids false "recent" claims.

---

### Time Zone Differences
**Scenario:** Authors and servers in different time zones

**Behavior:**
- All date comparisons use UTC
- Dates displayed in UTC or ISO format
- "Recent" consistently means "within last 7 days UTC"
- Behavior consistent regardless of author or server time zones

**Why It Works:** UTC standardization eliminates ambiguity and ensures consistent categorization.

---

### Non-Main Branch PRs
**Scenario:** PR from feature-branch-B into feature-branch-A

**Behavior:**
- Git-relative categorization compares against actual base branch (feature-branch-A)
- Categories show changes relative to target branch, not main
- Works correctly for any branch combination

**Why It Works:** Git comparison logic uses actual base branch reference, not hardcoded "main" assumption.

---

### Local Development Builds
**Scenario:** Developer runs build locally (no CI environment)

**Behavior:**
- No GITHUB_BASE_REF environment variable present
- System treats as deployment context (time-based categories)
- Local builds show recent writing activity

**Why It Works:** Default to deployment context provides useful information for local testing, developers can manually set environment variable if needed.

---

## Risk Considerations

### Context Confusion
**Risk:** Writers may not understand why categories differ between PR and deployment views

**Mitigation:**
- Prominent context banners on every allpaths page
- Clear help text explaining category meanings
- Documentation section addressing "why are categories different?"
- Consistent terminology within each context

**Monitoring:** Track user questions and feedback about category meanings

---

### Threshold Disagreement
**Risk:** Writers may prefer different timeframes for "recent" and "updated" categories

**Mitigation:**
- Make thresholds configurable via environment variables
- Document rationale for default values (7/30 days)
- UI clearly shows active thresholds
- Allow per-project customization if needed

**Monitoring:** Gather feedback on whether defaults align with writing patterns

---

### Missing Metadata
**Risk:** Validation cache may lack date fields for some paths

**Mitigation:**
- Graceful fallback: categorize as "older" if dates unavailable
- Alternative: Query git history to calculate dates (slower)
- Never break page rendering due to missing data
- Log warnings when falling back to conservative categorization

**Monitoring:** Track frequency of missing metadata to identify cache issues

---

### Performance Concerns
**Risk:** Time-based categorization may slow build process

**Mitigation:**
- Dates already stored in validation cache (no expensive operations)
- Date comparisons are fast (simple arithmetic)
- Pre-compute categories during cache update if needed
- Monitor build times to detect regressions

**Monitoring:** Track build duration across both contexts

---

## Acceptance Criteria

These criteria define when the feature is working correctly.

### Core Functionality
- Deployment builds display time-based categories (Recent/Updated/Older)
- PR builds display git-relative categories (New/Modified/Unchanged)
- Context detection correctly identifies PR vs deployment environment
- Categorization logic produces accurate results in both contexts
- Filter buttons work correctly for all categories
- Category badges display with appropriate colors and labels

### User Experience
- AllPaths page clearly indicates active context (banner or header)
- Category labels are context-appropriate (different in PR vs deployment)
- Help text explains what categories mean in current context
- Documentation addresses why categories differ between contexts
- UI maintains consistent design across both contexts
- Statistics accurately reflect category distribution

### Data Requirements
- Time-based categorization uses validation cache date fields
- Missing date metadata handled gracefully (doesn't break page)
- Configurable thresholds for "recent" (default 7 days) and "updated" (default 30 days)
- Date comparisons use UTC to avoid time zone issues

### Compatibility
- PR workflow behavior unchanged (backward compatible)
- Validation modes (new-only, modified, all) work in both contexts
- Validation cache format unchanged
- Existing PR comment format preserved
- No breaking changes to automation or workflows

### Quality
- Feature behavior documented in README
- Edge cases handled appropriately
- Performance impact negligible (build times unchanged)
- Code maintainable and well-documented

---

## User Documentation

User-facing documentation explains how categorization works and why it differs between contexts.

### AllPaths README

The `formats/allpaths/README.md` includes a "Understanding Path Categories" section that explains:

**Context-Aware Behavior:**
- Categories adapt based on where you're viewing paths
- Different contexts answer different questions

**Pull Request Context:**
- Shows what's changing in the PR
- Categories: New, Modified, Unchanged
- Use case: Validating PR changes and understanding impact

**Deployment Context:**
- Shows recent writing activity
- Categories: Recent (7 days), Updated (30 days), Older (30+ days)
- Use case: Tracking progress and finding recent content

**Why Categories Differ:**
- Same paths may have different categories in different contexts
- This is expected and correct behavior
- Each view optimized for its specific purpose

### Contributing Guide

The CONTRIBUTING.md includes a section on PR build artifacts:

**Understanding PR Categories:**
- Explains that PR builds show changes relative to base branch
- Clarifies that deployed site shows different (time-based) categories
- Helps contributors understand what they'll see in build artifacts
- Sets expectations about category meanings in different contexts

---

## Related Documents

- [formats/allpaths/README.md](/home/user/NaNoWriMo2025/formats/allpaths/README.md) - AllPaths format and categorization documentation
- [PRINCIPLES.md](/home/user/NaNoWriMo2025/PRINCIPLES.md) - Core principles including "Transparency and Inspectability"
- [ROADMAP.md](/home/user/NaNoWriMo2025/ROADMAP.md) - Feature roadmap and priorities

---

## Design Decisions

### Context Detection Method
**Decision:** Use GITHUB_BASE_REF environment variable to detect PR context

**Rationale:**
- Reliable indicator of PR builds (set by GitHub Actions)
- No additional git commands needed
- Clear and unambiguous
- Easy to override for testing if needed

**Alternative Considered:** Git commands to check branch status (rejected due to complexity and potential errors)

---

### Default Time Thresholds
**Decision:** 7 days for "Recent", 30 days for "Updated"

**Rationale:**
- 7 days aligns with typical weekly writing rhythm
- 30 days captures monthly progress (important for NaNoWriMo)
- Thresholds configurable via environment variables for flexibility
- UI clearly shows active thresholds for transparency

**Alternative Considered:** Fixed thresholds (rejected to allow project-specific customization)

---

### Category Computation Timing
**Decision:** Compute categories at display time (not stored in cache)

**Rationale:**
- Time-based categories change over time (today's "recent" is tomorrow's "updated")
- Git-relative categories depend on comparison context
- Computation is fast (simple date arithmetic or git comparison)
- Avoids cache invalidation complexity

**Alternative Considered:** Pre-compute and store in cache (rejected due to staleness issues)

---

### UI Transparency
**Decision:** Always show context indicators and explain category meanings

**Rationale:**
- Aligns with "Transparency and Inspectability" principle
- Prevents confusion about why categories differ between contexts
- Builds trust by making behavior explicit
- Helps writers interpret information correctly

**Alternative Considered:** Minimal UI with hidden context (rejected as it would cause confusion)

---

### Local Build Behavior
**Decision:** Local builds default to deployment context (time-based categories)

**Rationale:**
- More useful for local testing (see recent writing activity)
- Consistent with deployed site behavior
- Developers can manually set GITHUB_BASE_REF if PR context needed
- Reasonable default for most use cases

**Alternative Considered:** No categories in local builds (rejected as less useful)

---

## Design Principles Applied

This feature demonstrates several core principles:

**Writers First (Principle #1):**
- Categories provide value in both contexts
- Information adapted to writer's current need
- Clear explanations prevent confusion

**Transparency and Inspectability (Principle #5):**
- Context clearly indicated on every page
- Category meanings explicitly explained
- No mysterious behavior or hidden logic

**Multiple Perspectives, Same Source (Principle #4):**
- Same underlying data, different views
- PR view shows changes, deployment view shows history
- Each optimized for its purpose

**Fast Feedback Loops (Principle #3):**
- Categorization happens automatically on every build
- No manual categorization needed
- Writers get immediate, actionable information
