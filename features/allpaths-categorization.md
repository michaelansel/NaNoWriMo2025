# Feature PRD: AllPaths Context-Aware Categorization

**Status:** ✅ Active Feature
**Owner:** Product Manager
**Last Updated:** 2025-11-23
**Priority:** Core Feature

---

## Executive Summary

Writers need different information when viewing paths in different contexts. During pull request review, they need to see **what's changing in this PR**. On the deployed site, they need to see **when paths were created and modified**.

AllPaths adapts to context, providing the right information at the right time:
- **PR Context:** Git-relative categories show changes in this PR (New, Modified, Unchanged)
- **Deployment Context:** All paths displayed with creation/modification dates and flexible filters (created/modified in last day or week)

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
- Which paths were created in the last day or week?
- Which paths were modified in the last day or week?
- When was each path first created and last modified?
- Where is the story growing and what's actively being worked on?

**Why This Matters:** Writers need to track progress toward NaNoWriMo goals, identify active versus stable content, and coordinate collaborative work.

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
**I want** to see all paths with their creation and modification dates, with filters to view recent activity
**So that** I can track progress and coordinate with other authors

**Acceptance Criteria:**
- All paths display their creation date and last modification date
- Filter: "Created last day" shows paths created in the last 24 hours
- Filter: "Created last week" shows paths created in the last 7 days
- Filter: "Modified last day" shows paths modified in the last 24 hours
- Filter: "Modified last week" shows paths modified in the last 7 days
- Multiple filters can be active simultaneously
- Dates are shown in human-readable format with actual timestamps
- Clear indicators explain what each filter does

**How We Deliver:** Display all paths with metadata, provide flexible filtering options based on creation and modification dates from validation cache.

---

### Story 3: Understanding Context-Specific Information
**As a** writer using AllPaths in different contexts
**I want** to understand what information is shown and how to use it
**So that** I can interpret the data correctly and make informed decisions

**Acceptance Criteria:**
- Banner or header clearly indicates current context (PR or Deployment)
- In PR context: Categories (New/Modified/Unchanged) are clearly labeled
- In deployment context: Filters and date metadata are clearly explained
- Help text explains available features in current context
- Documentation explains why information differs between contexts
- Consistent UI design across both contexts

**How We Deliver:** Context detection determines environment, UI adapts to show categories (PR) or filters (deployment), clear documentation explains both modes.

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

**Purpose:** Show when paths were created and modified, with flexible filtering for recent activity

**Display Method:** All paths shown with creation and modification date metadata

**Path Metadata:**
- **Creation Date** - When the path first became complete (last passage added)
- **Modification Date** - When the path's content was last changed
- Both dates displayed in human-readable format with actual timestamps

**Filters:**
- **Created Last Day** - Paths created in the last 24 hours
- **Created Last Week** - Paths created in the last 7 days
- **Modified Last Day** - Paths modified in the last 24 hours
- **Modified Last Week** - Paths modified in the last 7 days
- Filters can be combined (e.g., "created last week AND modified last day")

**User Interface:**
- All paths listed with visible creation and modification dates
- Filter buttons allow showing specific subsets
- Context banner: "Showing all paths with activity filters"
- Statistics: "X total paths, Y match active filters"
- Clear indication when filters are active

**Use Cases:**
- Tracking NaNoWriMo daily and weekly progress
- Finding paths completed today or this week
- Identifying actively worked content (recently modified)
- Coordinating collaborative writing (see what teammates worked on)
- Monitoring writing velocity over time
- Reviewing path history and timeline

---

## Success Metrics

### User Understanding
- **Information clarity:** Writers can explain what information is shown in each context
- **Context awareness:** Writers understand why PR shows categories and deployment shows dates/filters
- **Trust:** Writers cite path information (categories, dates, filters) when making decisions

### Feature Usage
- **Active filtering:** Writers regularly use filters to find paths of interest
- **PR workflow:** Reviewers use categories to understand PR scope
- **Progress tracking:** Writers use date filters and metadata to monitor activity
- **Collaboration:** Teams use date information to coordinate work and track progress

### Information Quality
- **Meaningful information:** Path data and filters provide actionable information in both contexts
- **Accurate detection:** Context detection reliably identifies PR vs deployment environments
- **Useful filters:** Time-based filter windows (1 day, 7 days) align with writing patterns and tracking needs

### Qualitative Indicators
- Writers reference PR categories in review discussions
- Writers use filters and dates to answer "what changed?" and "what's recent?" questions
- No confusion or misinterpretation of context-specific information
- Date metadata and filters cited as valuable for understanding story evolution and tracking progress

---

## Technical Requirements

These requirements define WHAT the system must do (not HOW to implement it).

### Context Detection
The system detects build context and selects appropriate categorization:
- **PR context:** Triggered when GITHUB_BASE_REF environment variable is set
- **Deployment context:** Triggered when GITHUB_BASE_REF is not set
- Detection is reliable and unambiguous

### Context-Specific Display Logic
The system provides two display modes:

**Git-Relative Mode (PR Context):**
- Compares PR branch against base branch
- Identifies new, modified, and unchanged paths relative to base
- Categorization reflects PR-specific changes

**Date-Based Mode (Deployment Context):**
- Displays all paths with creation and modification dates from validation cache
- Provides filters based on time thresholds (1 day, 7 days)
- No categorization - paths shown with metadata and flexible filtering
- Supports multiple simultaneous filters

### Adaptive User Interface
The allpaths.html interface adapts to context while maintaining consistent design:

**Context Indicators:**
- Banner clearly states current mode (PR comparison or deployment view)
- Help text explains available features for current context

**Context-Appropriate Controls:**
- PR context: Category filter buttons (New/Modified/Unchanged) with badges
- Deployment context: Time-based filter buttons (Created/Modified Last Day/Week) with date display
- Clear indication of which filters are active
- Filter controls appropriate to the information being shown

**Consistent Visual Design:**
- Same layout and structure across contexts
- Same interaction patterns (filters, collapsible content, statistics)
- Dates displayed in consistent, human-readable format

### Filter Time Windows
Time-based filters use fixed, meaningful windows:
- "Last Day" filters: 24 hours from current time
- "Last Week" filters: 7 days from current time
- These windows align with typical writing rhythms and NaNoWriMo tracking needs
- Filter labels clearly indicate the time window being used

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
- Deployment context: All paths show creation dates from initial commit, filters work based on actual dates
- Both behaviors are correct and expected

**Why It Works:** Fresh repositories legitimately have all-new content with recent dates, filters accurately show what was created when.

---

### Inactive Repository
**Scenario:** No changes for extended period (60+ days)

**Behavior:**
- Deployment context: All filters show zero results (nothing created or modified recently)
- All paths display with their actual (old) creation and modification dates
- Statistics show 0 paths matching any time-based filter
- Accurately represents repository inactivity

**Why It Works:** Date display and filters correctly show no recent activity, helping writers see when work has stalled.

---

### Missing Date Metadata
**Scenario:** Validation cache lacks `created_date` or `commit_date` fields

**Behavior:**
- System displays "Unknown" for missing dates
- Alternative: Query git history to calculate dates (slower but accurate)
- Paths with missing dates excluded from time-based filters
- Page remains functional regardless of missing data

**Why It Works:** Graceful degradation prevents broken pages, transparency shows when data is unavailable rather than making assumptions.

---

### Time Zone Differences
**Scenario:** Authors and servers in different time zones

**Behavior:**
- All date comparisons use UTC
- Dates displayed in UTC or ISO format with clear timezone indicator
- "Last Day" and "Last Week" filters operate on UTC time
- Behavior consistent regardless of author or server time zones

**Why It Works:** UTC standardization eliminates ambiguity and ensures consistent filtering and date display.

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
- System treats as deployment context (date display with filters)
- Local builds show all paths with creation/modification dates and filters

**Why It Works:** Default to deployment context provides useful information for local testing, developers can manually set environment variable if needed.

---

## Risk Considerations

### Context Confusion
**Risk:** Writers may not understand why information differs between PR and deployment views

**Mitigation:**
- Prominent context banners on every allpaths page
- Clear help text explaining available features (categories vs filters)
- Documentation section addressing "why does this differ between contexts?"
- Consistent terminology within each context

**Monitoring:** Track user questions and feedback about context-specific features

---

### Filter Utility
**Risk:** The "Last Day" and "Last Week" filters may not match writers' needs

**Mitigation:**
- Choose meaningful time windows (24 hours, 7 days) that align with typical writing rhythms
- All paths always visible with actual dates (filters are optional, not required)
- Writers can use the raw date information if filters don't fit their needs
- Document rationale for filter time windows

**Monitoring:** Gather feedback on whether filter windows are useful and sufficient

---

### Missing Metadata
**Risk:** Validation cache may lack date fields for some paths

**Mitigation:**
- Display "Unknown" for missing dates (transparency over assumptions)
- Exclude paths with missing dates from filter results
- Alternative: Query git history to calculate dates (slower but accurate)
- Never break page rendering due to missing data
- Log warnings when dates are unavailable

**Monitoring:** Track frequency of missing metadata to identify cache issues

---

### Performance Concerns
**Risk:** Date filtering may slow page rendering

**Mitigation:**
- Dates already stored in validation cache (no expensive operations)
- Date comparisons are fast (simple arithmetic in browser JavaScript)
- Filtering happens client-side for instant response
- No additional build-time computation needed

**Monitoring:** Track page load and interaction performance

---

## Acceptance Criteria

These criteria define when the feature is working correctly.

### Core Functionality
- Deployment builds display all paths with creation and modification dates
- Deployment builds provide filters: Created Last Day, Created Last Week, Modified Last Day, Modified Last Week
- PR builds display git-relative categories (New/Modified/Unchanged)
- Context detection correctly identifies PR vs deployment environment
- PR categorization logic produces accurate results
- Filter buttons work correctly and can be combined
- Dates displayed in human-readable format with timestamps

### User Experience
- AllPaths page clearly indicates active context (banner or header)
- PR context shows category labels (New/Modified/Unchanged)
- Deployment context shows filter buttons and date metadata
- Help text explains available features in current context
- Documentation addresses why information differs between contexts
- UI maintains consistent design across both contexts
- Statistics accurately reflect total paths and filter results

### Data Requirements
- Date display uses validation cache `created_date` and `commit_date` fields
- Missing date metadata handled gracefully (shows "Unknown", doesn't break page)
- Filter time windows: 24 hours (Last Day), 7 days (Last Week)
- Date comparisons use UTC to avoid time zone issues
- Paths with missing dates excluded from filter results

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

User-facing documentation explains how path information works and why it differs between contexts.

### AllPaths README

The `formats/allpaths/README.md` includes a "Understanding Path Categories" section that explains:

**Context-Aware Behavior:**
- Information adapts based on where you're viewing paths
- Different contexts answer different questions

**Pull Request Context:**
- Shows what's changing in the PR
- Categories: New, Modified, Unchanged
- Use case: Validating PR changes and understanding impact

**Deployment Context:**
- Shows all paths with creation and modification dates
- Filters: Created Last Day/Week, Modified Last Day/Week
- Use case: Tracking progress, finding recent work, monitoring writing velocity

**Why Information Differs:**
- PR view focuses on changes (what's different in this PR?)
- Deployment view focuses on timeline (when were things created/modified?)
- This is expected and correct behavior
- Each view optimized for its specific purpose

### Contributing Guide

The CONTRIBUTING.md includes a section on PR build artifacts:

**Understanding PR Information:**
- Explains that PR builds show changes relative to base branch (New/Modified/Unchanged)
- Clarifies that deployed site shows different information (dates and filters)
- Helps contributors understand what they'll see in build artifacts
- Sets expectations about why information differs between contexts

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

### Filter Time Windows
**Decision:** Fixed time windows - 1 day (24 hours) and 1 week (7 days)

**Rationale:**
- 1 day enables tracking daily writing progress during NaNoWriMo
- 1 week aligns with typical weekly writing rhythm and sprint cycles
- Simple, clear time periods that writers understand intuitively
- All paths always visible with actual dates - filters are optional tools
- No need for configuration - windows chosen to match common use cases

**Alternative Considered:** Configurable thresholds (rejected - adds complexity without clear benefit when dates are always visible)

---

### Filter Application Timing
**Decision:** Apply filters at display time in browser (client-side filtering)

**Rationale:**
- Dates stored in validation cache, filters computed on-demand in browser
- Enables instant, responsive filter toggling without page reload
- Filter results change over time (today's "last day" differs from tomorrow's)
- Simple JavaScript date arithmetic is very fast
- No server-side computation needed

**Alternative Considered:** Pre-filter on server (rejected - slower, less responsive, no benefit)

---

### UI Transparency
**Decision:** Always show actual dates and make filter behavior explicit

**Rationale:**
- Aligns with "Transparency and Inspectability" principle
- Actual dates always visible - no hidden information
- Filters are clearly labeled tools, not mysterious categories
- Prevents confusion about what's being shown
- Builds trust by making all data and behavior explicit

**Alternative Considered:** Show only filtered results without dates (rejected - hides information, reduces flexibility)

---

### Local Build Behavior
**Decision:** Local builds default to deployment context (date display with filters)

**Rationale:**
- More useful for local testing (see when paths were created/modified)
- Consistent with deployed site behavior
- Developers can manually set GITHUB_BASE_REF if PR context needed
- Reasonable default for most use cases

**Alternative Considered:** No date display in local builds (rejected as less useful)

---

## Design Principles Applied

This feature demonstrates several core principles:

**Writers First (Principle #1):**
- Information provides value in both contexts
- Display adapted to writer's current need (changes vs timeline)
- All data transparent and accessible
- Clear explanations prevent confusion

**Transparency and Inspectability (Principle #5):**
- Context clearly indicated on every page
- Actual dates always visible - no hidden information
- Filter behavior explicit and understandable
- No mysterious categories or hidden logic

**Multiple Perspectives, Same Source (Principle #4):**
- Same underlying data, different views
- PR view shows changes, deployment view shows timeline
- Each optimized for its specific purpose

**Fast Feedback Loops (Principle #3):**
- Date display happens automatically on every build
- Filters respond instantly in browser
- No manual work needed
- Writers get immediate, actionable information
