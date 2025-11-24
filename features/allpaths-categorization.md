# Feature PRD: AllPaths Progress Tracking

**Status:** ✅ Active Feature
**Owner:** Product Manager
**Priority:** Core Feature

---

## Executive Summary

Writers need to track progress and browse all story paths during active writing. AllPaths provides a comprehensive browsing interface showing all paths with their creation and modification dates, along with flexible filtering to find recent activity.

**Key Capabilities:**
- View all story paths in a single browsable HTML interface
- See when each path was created and last modified
- Filter by recent activity (created/modified in last day or week)
- Track validation status (which paths have been checked for continuity)
- Same consistent interface in PR preview and deployment

This browsing feature helps writers track NaNoWriMo progress, find recent work, and understand story evolution over time.

---

## User Needs

### Need 1: Browse All Story Paths
**Context:** Writing and reviewing the story

**User Goal:** See all possible paths through the story

**Questions Writers Need Answered:**
- What are all the possible ways players can experience the story?
- How many paths exist?
- What's the route through each path?
- What content appears in each path?

**Why This Matters:** Writers need to understand the full scope of the branching narrative and ensure all paths are intentional and complete.

---

### Need 2: Track Writing Progress
**Context:** Active writing during NaNoWriMo

**User Goal:** Monitor recent writing activity and progress toward goals

**Questions Writers Need Answered:**
- Which paths were created in the last day or week?
- Which paths were modified in the last day or week?
- When was each path first created and last modified?
- Where is the story growing and what's actively being worked on?
- How much progress have I made today/this week?

**Why This Matters:** Writers need to track progress toward NaNoWriMo goals (50,000 words), identify active versus stable content, and coordinate collaborative work.

---

### Need 3: Track Validation Status
**Context:** Reviewing story quality

**User Goal:** Know which paths have been checked for continuity

**Questions Writers Need Answered:**
- Which paths have been validated for continuity?
- Which paths still need review?
- Has this path been checked by the AI?
- Are there any known issues with this path?

**Why This Matters:** Writers need to ensure story quality and track which paths have been reviewed, avoiding duplicate work and maintaining confidence in the story.

---

### Need 4: Consistent Interface
**Context:** Viewing AllPaths in different environments (PR preview, deployment)

**User Goal:** Get the same information regardless of where I'm viewing

**Questions Writers Need Answered:**
- Will the deployed version look the same as the PR preview?
- Can I trust the PR preview to show what will be deployed?
- Do I need to learn different interfaces for different contexts?

**Why This Matters:** Writers need to validate changes in PR previews with confidence that the deployment will match what they see.

---

## User Stories

### Story 1: Browsing All Story Paths
**As a** writer working on the story
**I want** to see all possible paths in a single browsable interface
**So that** I can understand the full scope of the branching narrative

**Acceptance Criteria:**
- All paths displayed in a single HTML page
- Each path shows its route (sequence of passages)
- Path content is collapsible for easy navigation
- Statistics show total paths, lengths, and counts
- Paths are clearly numbered and identified
- Interface is usable on desktop and mobile

---

### Story 2: Tracking Writing Progress
**As a** writer during active NaNoWriMo writing
**I want** to see when paths were created and modified, with filters for recent activity
**So that** I can track my progress toward goals and find recent work

**Acceptance Criteria:**
- All paths display their creation date and last modification date
- Filter: "Created last day" shows paths created in the last 24 hours
- Filter: "Created last week" shows paths created in the last 7 days
- Filter: "Modified last day" shows paths modified in the last 24 hours
- Filter: "Modified last week" shows paths modified in the last 7 days
- Multiple filters can be active simultaneously
- Dates are shown in human-readable format with actual timestamps
- Filter buttons clearly indicate active state
- Statistics update when filters are applied

---

### Story 3: Tracking Validation Status
**As a** writer ensuring story quality
**I want** to see which paths have been validated for continuity
**So that** I can focus my review on unchecked paths

**Acceptance Criteria:**
- Paths show validation status badge ("Validated" or "New")
- Visual indicator distinguishes validated from unvalidated paths
- Can filter to show only validated or only new paths
- Statistics show count of validated vs new paths
- Validation status updates when paths are approved

---

### Story 4: Consistent Interface Everywhere
**As a** writer reviewing PR previews
**I want** to see the same AllPaths interface in PR preview and deployment
**So that** I can validate changes with confidence that deployment will match

**Acceptance Criteria:**
- PR preview AllPaths HTML matches deployment AllPaths HTML
- Same date filters available in both contexts
- Same validation status displayed in both contexts
- Same visual design and layout in both contexts
- No surprising differences between PR and deployment
- Documentation clarifies that interface is consistent

---

## Feature Behavior

AllPaths provides a consistent browsing interface showing all story paths with date metadata, filtering, and validation status.

### Path Display

**All paths are displayed with the following information:**

**Path Metadata:**
- **Path Number and ID** - Unique identifier for each path
- **Route** - Sequence of passages the path travels through
- **Length** - Number of passages in the path
- **Creation Date** - When the path first became complete (most recent passage in the path was added)
- **Modification Date** - When the path's content was last changed
- **Validation Status** - Whether the path has been checked for continuity

**Visual Presentation:**
- Each path is collapsible (click to expand/collapse content)
- Dates displayed in human-readable format (e.g., "2025-11-23 14:30 UTC")
- Validation status shown as badge ("Validated" or "New")
- Visual styling differentiates validated from unvalidated paths
- Statistics dashboard at top shows counts and totals

---

### Time-Based Filtering

**Purpose:** Find paths based on recent activity

**Available Filters:**
- **Created Last Day** - Paths created in the last 24 hours
- **Created Last Week** - Paths created in the last 7 days
- **Modified Last Day** - Paths modified in the last 24 hours
- **Modified Last Week** - Paths modified in the last 7 days

**Filter Behavior:**
- Multiple filters can be active simultaneously
- Combined filters use AND logic (e.g., "created last week AND modified last day")
- Filter buttons clearly indicate active state
- Statistics update to show filtered count
- Paths with missing dates excluded from filter results
- All paths always visible when no filters are active

**Use Cases:**
- Tracking NaNoWriMo daily and weekly progress
- Finding paths completed today or this week
- Identifying actively worked content (recently modified)
- Coordinating collaborative writing (see what teammates worked on)
- Monitoring writing velocity over time
- Reviewing path history and timeline

---

### Validation Status Display

**Purpose:** Track which paths have been checked for continuity

**Status Types:**
- **Validated** - Path has been reviewed and approved for continuity
- **New** - Path has not yet been validated

**Visual Indicators:**
- Badge showing status on each path
- Color-coded visual styling (green for validated, neutral for new)
- Filter buttons to show only validated or only new paths
- Statistics showing validated vs new counts

**How Status Changes:**
- Paths start as "New" when first created
- Status updates to "Validated" when approved via `/approve-path` command
- Status may reset to "New" if path content changes after validation

**Use Cases:**
- Tracking which paths still need review
- Focusing review effort on unvalidated paths
- Monitoring quality assurance progress
- Coordinating team validation work

---

### Consistent Behavior Across Contexts

**The same AllPaths HTML is generated for all builds:**
- PR preview builds show the same interface as deployment
- Same date filters available everywhere
- Same validation status displayed everywhere
- Same visual design and layout everywhere

**Why Consistency Matters:**
- Writers can validate PR changes with confidence that deployment will match
- No need to learn different interfaces for different contexts
- PR preview accurately represents what will be deployed
- Reduces confusion and builds trust in the automation

---

## Success Metrics

### User Understanding
- **Interface clarity:** Writers can explain what information is shown and how to use filters
- **Consistency:** Writers trust that PR preview matches deployment
- **Date interpretation:** Writers correctly interpret creation and modification dates

### Feature Usage
- **Active filtering:** Writers regularly use date filters to find paths of interest
- **Progress tracking:** Writers use date filters and metadata to monitor daily/weekly activity
- **Validation tracking:** Writers use validation status to coordinate review work
- **Collaboration:** Teams use date information to coordinate work and track progress

### Information Quality
- **Meaningful information:** Path data and filters provide actionable information for tracking progress
- **Accurate dates:** Creation and modification dates correctly reflect when paths became available and changed
- **Useful filters:** Time-based filter windows (1 day, 7 days) align with writing patterns and tracking needs
- **Reliable validation status:** Status accurately reflects which paths have been reviewed

### Qualitative Indicators
- Writers use filters to answer "what did I write today/this week?" questions
- Writers cite date information when discussing progress and coordinating work
- No confusion about interface differences between PR and deployment (because there are none)
- Date metadata cited as valuable for understanding story evolution and tracking progress
- Validation status helps teams coordinate review work

---

## Technical Requirements

These requirements define WHAT the system must do (not HOW to implement it).

### Path Display Requirements
The system displays all paths with complete metadata:
- **Path identification:** Unique ID and route for each path
- **Date metadata:** Creation date and modification date from validation cache
- **Validation status:** Whether path has been validated for continuity
- **Path content:** Full prose content, collapsible for navigation
- **Statistics:** Counts, lengths, and filtered results

### Date Data Requirements
Date metadata must be accurate and complete:
- **Creation date:** Most recent commit date of passages in the path (when path became complete)
- **Modification date:** Most recent modification date of any passage in the path
- **Format:** Human-readable display (e.g., "2025-11-23 14:30 UTC")
- **Missing data handling:** Display "Unknown" for missing dates, exclude from filters
- **Time zone:** All dates in UTC to avoid ambiguity

### Time-Based Filtering Requirements
The system provides flexible filtering based on time windows:
- **Filter windows:** 1 day (24 hours) and 1 week (7 days) from current time
- **Filter types:** Created and Modified for each window (4 total filters)
- **Filter logic:** Multiple filters can be active with AND logic
- **Filter state:** Clear visual indication of active filters
- **Filter application:** Client-side filtering for instant response
- **Statistics update:** Filtered counts displayed when filters are active

### Validation Status Requirements
The system tracks and displays validation status:
- **Status types:** "Validated" and "New"
- **Status source:** Validation cache `validated` field
- **Status display:** Badge on each path, visual styling
- **Status filters:** Can filter to show only validated or only new paths
- **Status updates:** Updates when paths are approved via `/approve-path` command

### Consistency Requirements
The system generates identical output across all contexts:
- **Single HTML generator:** Same code path for all builds
- **No context detection:** No special behavior for PR vs deployment
- **Same data displayed:** All builds show dates, filters, and validation status
- **Same visual design:** Layout and styling identical everywhere
- **PR preview matches deployment:** What you see in PR is what gets deployed

### Backward Compatibility
Changes preserve existing functionality:
- Validation cache format unchanged
- Validation modes (new-only, modified, all) work as before
- Date fields already present in cache
- No breaking changes to existing workflows

---

## Edge Cases

### Fresh Repository
**Scenario:** First build with no prior history

**Behavior:**
- All paths show creation dates from initial commit
- Filters work based on actual dates
- All paths likely match "created last day/week" filters
- Validation status shows all paths as "New"

**Why It Works:** Fresh repositories legitimately have all-new content with recent dates, filters accurately show what was created when.

---

### Inactive Repository
**Scenario:** No changes for extended period (60+ days)

**Behavior:**
- All filters show zero results (nothing created or modified recently)
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
- Dates displayed in UTC format with clear timezone indicator (e.g., "2025-11-23 14:30 UTC")
- "Last Day" and "Last Week" filters operate on UTC time
- Behavior consistent regardless of author or server time zones

**Why It Works:** UTC standardization eliminates ambiguity and ensures consistent filtering and date display.

---

### Path Content Changes After Validation
**Scenario:** Path is validated, then content changes

**Behavior:**
- Content-based hash detects the change
- Validation status may reset to "New" (depending on implementation)
- Path appears in "new" filter results if status resets
- Writers can re-validate using `/approve-path` command

**Why It Works:** Content changes may introduce new continuity issues, so re-validation ensures quality is maintained.

---

### Local Development Builds
**Scenario:** Developer runs build locally (no CI environment)

**Behavior:**
- Same interface as deployed version
- Shows all paths with creation/modification dates and filters
- Validation status displayed from cache
- No special behavior for local builds

**Why It Works:** Consistent behavior everywhere makes local testing reliable and predictable.

---

## Risk Considerations

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
**Risk:** Date filtering may slow page rendering or interaction

**Mitigation:**
- Dates already stored in validation cache (no expensive operations)
- Date comparisons are fast (simple arithmetic in browser JavaScript)
- Filtering happens client-side for instant response
- No additional build-time computation needed
- Test with large path counts (100+) to ensure responsiveness

**Monitoring:** Track page load and interaction performance

---

### Date Interpretation
**Risk:** Writers may misunderstand what creation vs modification dates mean

**Mitigation:**
- Clear labels explaining each date type
- Documentation defines "creation date" and "modification date"
- Help text or tooltips explaining the difference
- Consistent date formatting across the interface

**Monitoring:** Track user questions about date meanings

---

## Acceptance Criteria

These criteria define when the feature is working correctly.

### Core Functionality
- All builds display all paths with creation and modification dates
- Filter buttons provided: Created Last Day, Created Last Week, Modified Last Day, Modified Last Week
- Filter buttons work correctly and can be combined
- Dates displayed in human-readable format with timestamps
- Validation status displayed for each path (Validated or New)
- Statistics show total paths, filtered counts, and validation counts

### User Experience
- AllPaths page shows consistent interface in all contexts
- Date metadata visible on all paths
- Filter buttons clearly indicate active state
- Validation status badges clearly visible
- Help text explains available features
- UI maintains consistent design everywhere
- Statistics accurately reflect total paths and filter results
- No surprising differences between PR preview and deployment

### Data Requirements
- Date display uses validation cache `created_date` and `commit_date` fields
- Validation status uses validation cache `validated` field
- Missing date metadata handled gracefully (shows "Unknown", doesn't break page)
- Filter time windows: 24 hours (Last Day), 7 days (Last Week)
- Date comparisons use UTC to avoid time zone issues
- Paths with missing dates excluded from filter results

### Compatibility
- Validation cache format unchanged
- Validation modes (new-only, modified, all) work as before
- No breaking changes to automation or workflows
- Date fields already present in cache (no migration needed)

### Quality
- Feature behavior documented in README
- Edge cases handled appropriately
- Performance impact negligible (build times unchanged, filtering instant)
- Code maintainable and well-documented

---

## User Documentation

User-facing documentation explains how to use the AllPaths browsing interface.

### AllPaths README

The `formats/allpaths/README.md` includes a "Using AllPaths for Progress Tracking" section that explains:

**Browsing Paths:**
- All paths displayed in a single HTML file
- Each path shows its route, creation date, and modification date
- Click to expand/collapse path content
- Statistics show total paths and current filter results

**Tracking Progress:**
- Creation date: When the path first became complete
- Modification date: When the path's content was last changed
- Use date filters to find recent work
- Track daily and weekly progress toward NaNoWriMo goals

**Using Filters:**
- Created Last Day: Paths created in the last 24 hours
- Created Last Week: Paths created in the last 7 days
- Modified Last Day: Paths modified in the last 24 hours
- Modified Last Week: Paths modified in the last 7 days
- Multiple filters can be active simultaneously
- Statistics update to show filtered counts

**Validation Status:**
- "Validated" badge: Path has been checked for continuity
- "New" badge: Path has not yet been validated
- Filter to show only validated or only new paths
- Status updates when paths are approved

**Consistent Interface:**
- Same interface in PR preview and deployment
- What you see in PR preview is what gets deployed
- No surprising differences between contexts

### Contributing Guide

The CONTRIBUTING.md includes a section on PR build artifacts:

**AllPaths in PR Previews:**
- PR build artifacts include allpaths.html
- Shows the same interface that will be deployed
- Use date filters to see recent work
- Validate that PR preview matches expectations
- Deployment will match what you see in PR preview

---

## Related Documents

- [formats/allpaths/README.md](/home/user/NaNoWriMo2025/formats/allpaths/README.md) - AllPaths format and categorization documentation
- [PRINCIPLES.md](/home/user/NaNoWriMo2025/PRINCIPLES.md) - Core principles including "Transparency and Inspectability"
- [ROADMAP.md](/home/user/NaNoWriMo2025/ROADMAP.md) - Feature roadmap and priorities

---

## Design Decisions

### Consistent Interface Everywhere
**Decision:** Generate identical AllPaths HTML for all builds (PR and deployment)

**Rationale:**
- Writers need to validate PR changes with confidence that deployment will match
- Reduces confusion - same interface everywhere
- Simplifies implementation - single code path
- Aligns with principle: "PR build output should match deployment"
- No surprising differences between contexts

**Alternative Considered:** Context-aware UI with different displays for PR vs deployment (rejected - violates principle, confuses writers)

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

### Display Validation Status in HTML
**Decision:** Show validation status badges and filters in AllPaths HTML

**Rationale:**
- Writers need to see which paths have been validated
- Helps coordinate review work across team
- Integrates browsing with quality tracking
- Status already in cache - no additional computation
- Complements continuity checking feature

**Alternative Considered:** Hide validation status from HTML (rejected - less useful, status is valuable information)

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

## Design Principles Applied

This feature demonstrates several core principles:

**Writers First (Principle #1):**
- Consistent interface reduces cognitive load
- Progress tracking helps writers monitor NaNoWriMo goals
- Date filters provide actionable information for daily writing
- Validation status helps coordinate review work

**Transparency and Inspectability (Principle #5):**
- Actual dates always visible - no hidden information
- Filter behavior explicit and understandable
- Validation status clearly displayed
- No mysterious categories or hidden logic

**Fast Feedback Loops (Principle #3):**
- Date display happens automatically on every build
- Filters respond instantly in browser
- No manual work needed
- Writers get immediate, actionable information

**PR Preview Matches Deployment:**
- Same HTML generated for all builds
- Writers validate changes with confidence
- No surprising differences between contexts
- Reduces risk and builds trust
