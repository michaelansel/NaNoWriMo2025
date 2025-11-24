# ADR-007: AllPaths Single-Interface Design with Progress Tracking

## Status

Accepted

## Context

Writers need to track progress and browse story paths during active writing and PR review. The AllPaths interface serves two primary use cases:

### Use Case 1: Progress Tracking During Active Writing
During active writing (especially NaNoWriMo), writers need to **track progress and monitor recent activity**:
- Which paths were created in the last day or week?
- Which paths were modified in the last day or week?
- When was each path first created and last modified?
- Where is the story growing and what's actively being worked on?
- How much progress have I made today/this week?

### Use Case 2: Validating Changes in PR Previews
During PR review, writers need to **validate that changes look correct**:
- Does the AllPaths HTML render correctly?
- Do the new paths appear as expected?
- Do dates and filters work correctly?
- Will the deployed version match what I see in the PR preview?

### Problem Statement

Writers need a **single consistent interface** that works the same way everywhere. Specifically:

1. **Consistent presentation** - Same HTML in PR preview and deployment
2. **Progress tracking** - See when paths were created and modified
3. **Activity filtering** - Find paths created or modified in last day/week
4. **Validation status** - Track which paths have been checked for continuity
5. **Transparent behavior** - Understand what information is shown and why
6. **PR preview confidence** - Trust that PR preview matches what will be deployed

The current implementation lacks date display and filtering capabilities. Additionally, separating the browsing interface from the validation logic creates clearer architectural boundaries

## Decision

We will implement a **single consistent HTML interface** for AllPaths across all contexts (PR preview and deployment):

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Build Process                               │
│                                                                  │
│  1. Generate paths with DFS traversal                           │
│  2. Load date metadata from validation cache                    │
│  3. Load validation status from cache                           │
│  4. Generate single HTML with:                                  │
│     • Date display (created and modified)                       │
│     • Time-based filters (last day/week)                        │
│     • Validation status badges (Validated/New)                  │
│     • Client-side filtering for all features                    │
│                                                                  │
│  No context detection, no conditional rendering                 │
│  Same HTML generated for all builds                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Separation of Concerns

**AllPaths HTML (Browsing Interface):**
- Displays all paths with dates and validation status
- Provides time-based filters for progress tracking
- Always shows the same interface regardless of context
- Used by writers for progress tracking and quality monitoring

**Validation Logic (Internal to AI Continuity Checking):**
- Categorizes paths as NEW/MODIFIED/UNCHANGED internally
- Uses categories to determine what needs validation
- These categories never appear in the HTML
- Validation results appear in PR comments, not HTML

### Key Design Decisions

#### 1. Single HTML Generator (No Context Detection)
**Decision:** Generate identical HTML for all builds, regardless of context

**Rationale:**
- **Consistency**: PR preview matches deployment exactly
- **Simplicity**: No conditional logic based on environment
- **Trust**: Writers can validate changes in PR preview with confidence
- **Maintainability**: Single code path, not two divergent implementations
- **Principle alignment**: "PR build output should match deployment"

**What This Means:**
- No `GITHUB_BASE_REF` detection or context flags
- No conditional rendering of different UI elements
- Same date display, filters, and validation status in all contexts
- HTML generator has no concept of "PR mode" vs "deployment mode"

**Alternatives Considered:**
- Context-aware rendering (different UI for PR vs deployment): Rejected because it violates consistency principle, confuses writers, and makes PR previews untrustworthy

---

#### 2. Date Data Source
**Decision:** Load date metadata from validation cache

**Rationale:**
- **Already available**: Dates collected via `get_path_creation_date()` and `get_path_commit_date()` during build
- **Cached**: Stored in validation cache (`created_date`, `commit_date` fields)
- **Standardized**: Dates in UTC ISO format (consistent, timezone-safe)
- **No performance cost**: No additional git operations needed at HTML generation time
- **Persistent**: Cache preserves dates across builds

**What This Means:**
- HTML generator reads `created_date` and `commit_date` from cache
- Dates displayed in human-readable format with timestamps
- Missing dates show "Unknown" (transparent, no assumptions)
- UTC format eliminates timezone ambiguity

---

#### 3. Filter Implementation (Client-Side)
**Decision:** Implement all filtering in browser JavaScript (time-based and validation status)

**Rationale:**
- **Instant response**: No page reload or server round-trip
- **Simple implementation**: Date and status comparisons are fast in JavaScript
- **Flexible**: Multiple filters can be active simultaneously with AND logic
- **Performance**: Date parsing and comparison is trivial for ~50-100 paths
- **Same everywhere**: Filtering logic identical in PR and deployment

**What This Means:**
- Time-based filters: "Created Last Day/Week", "Modified Last Day/Week"
- Validation status filters: "Validated", "New"
- All filters operate on data attributes in HTML (`data-created-date`, `data-validated`, etc.)
- Filter state tracked in JavaScript, applied by toggling visibility
- Statistics update dynamically to reflect filtered results

**Alternatives Considered:**
- Server-side pre-filtering: Rejected (slower, less responsive, requires multiple HTML files for filter combinations)
- WebAssembly: Rejected (overkill for simple comparisons)

---

#### 4. Date Format and Display
**Decision:** Always display both creation and modification dates in human-readable format with semantic HTML

**Rationale:**
- **Human-readable**: Writers see "2025-11-23 14:30 UTC" not "2025-11-23T14:30:00Z"
- **Machine-readable**: `<time datetime="...">` preserves ISO format for JavaScript filtering
- **UTC clarity**: Explicit "UTC" label prevents timezone confusion
- **Transparent**: Missing dates show "Unknown" (no hidden information, no assumptions)
- **Semantic HTML**: `<time>` element with `datetime` attribute (accessibility, screen readers)
- **Always visible**: Dates displayed on all paths in all contexts

**What This Means:**
- Both dates always shown: creation date and modification date
- Format: `YYYY-MM-DD HH:MM UTC`
- Graceful degradation: Missing dates display "Unknown" without breaking page
- Consistent presentation everywhere

---

#### 5. Filter Time Windows
**Decision:** Fixed time windows - 1 day (24 hours) and 1 week (7 days)

**Rationale:**
- **Aligned with user needs**: Matches typical writing rhythms during NaNoWriMo
  - Daily: Track today's progress (NaNoWriMo daily word count goals)
  - Weekly: Track week's progress (sprint cycles, weekly milestones)
- **Simple and predictable**: No configuration needed, clear semantics
- **Unambiguous**: "Last Day" = 24 hours from now, "Last Week" = 7 days from now
- **Always available**: Filter buttons present in all contexts
- **Complemented by actual dates**: Writers see exact timestamps, can ignore filters if not useful

**What This Means:**
- Four time-based filter buttons always available:
  - "Created Last Day" (paths created in last 24 hours)
  - "Created Last Week" (paths created in last 7 days)
  - "Modified Last Day" (paths modified in last 24 hours)
  - "Modified Last Week" (paths modified in last 7 days)
- Filters based on current time, recalculated dynamically in browser
- All paths always visible when no filters active

**Alternatives Considered:**
- Configurable thresholds: Rejected (adds complexity without clear benefit when dates are always visible)
- Relative labels ("yesterday", "this week"): Rejected (ambiguous, timezone-dependent, changes meaning over time)

---

#### 6. Missing Date Handling
**Decision:** Display "Unknown" transparently and exclude from time-based filter results

**Rationale:**
- **Transparency**: Writers see when data is unavailable (no hidden information)
- **Conservative filtering**: Don't include paths with unknown dates in time-based filters (can't verify if they match)
- **No assumptions**: Never guess or infer dates from other sources
- **Graceful degradation**: Page remains functional regardless of missing data
- **Path still visible**: Paths with missing dates still appear in HTML, just show "Unknown"

**What This Means:**
- HTML displays "Unknown" for missing creation or modification dates
- Time-based filters exclude paths with "Unknown" dates
- Path remains visible when no filters active
- No automatic fallback to file system dates or other heuristics

**Alternatives Considered:**
- Query git on-demand for missing dates: Rejected (slow, complex, dates should already be in cache from build)
- Use file system dates: Rejected (unreliable, doesn't reflect actual commit history)
- Hide paths with missing dates entirely: Rejected (hides information, less transparent)

---

#### 7. Validation Status Display
**Decision:** Always display validation status badges on all paths

**Rationale:**
- **Quality tracking**: Writers need to see which paths have been validated for continuity
- **Coordination**: Teams can track review progress
- **Integration**: Combines browsing with quality monitoring
- **Always available**: Status displayed in all contexts (PR and deployment)
- **Already cached**: Status already in validation cache, no additional computation

**What This Means:**
- Each path displays validation status badge:
  - "Validated": Path has been reviewed and approved (green styling)
  - "New": Path has not yet been validated (neutral styling)
- Status sourced from validation cache `validated` field
- Status can be changed via `/approve-path` command
- Status may reset to "New" if path content changes after validation
- Validation status filters allow showing only validated or only new paths

**Alternatives Considered:**
- Hide validation status from HTML: Rejected (less useful, status is valuable information for quality tracking)
- Show only in PR context: Rejected (violates consistency principle, status useful during active writing too)

---

#### 8. Filter Combination Logic
**Decision:** Multiple filters can be active simultaneously with AND logic

**Rationale:**
- **Flexible**: Writers can answer complex questions like "created last week AND modified today"
- **Intuitive**: Multiple active filter buttons show combined view
- **Transparent**: Active filters clearly indicated (button styling, active state)
- **PM requirement**: Specification explicitly states "filters can be combined"
- **Powerful queries**: Enables sophisticated filtering without complex UI

**What This Means:**
- All filter types can be combined:
  - Time-based: Created Last Day, Created Last Week, Modified Last Day, Modified Last Week
  - Validation status: Validated, New
- Combined filters use AND logic (path must match all active filters to be visible)
- Filter state tracked in JavaScript, updated dynamically
- Statistics update to show count of paths matching active filters
- Clear filter state with single action (reset/clear all button)

**Alternatives Considered:**
- Single filter at a time: Rejected (less flexible, can't answer complex questions)
- OR logic instead of AND: Rejected (AND is more useful for narrowing results, OR would broaden)

---

## Consequences

### Positive

1. **Single consistent interface everywhere**
   - PR preview matches deployment exactly
   - Writers can validate changes with confidence
   - No surprising differences between contexts
   - Reduces confusion and builds trust

2. **Progress tracking always available**
   - See when paths were created (completion dates)
   - See when paths were modified (update dates)
   - Track daily/weekly writing progress
   - Monitor NaNoWriMo velocity
   - Same tracking capability in PR preview and deployment

3. **Quality monitoring integrated**
   - Validation status visible on all paths
   - Track which paths have been reviewed
   - Coordinate team review work
   - Monitor quality assurance progress

4. **Flexible filtering**
   - Time-based filters: Find paths created or modified recently
   - Validation status filters: Find validated or new paths
   - Combine filters for complex queries (AND logic)
   - All paths always visible (filters are tools, not gates)

5. **Zero performance impact**
   - Dates already collected at build time
   - Validation status already in cache
   - Client-side filtering is instant
   - No additional git operations
   - Same build time (~3-4 seconds)

6. **Maintainable and simple**
   - Single HTML generator (not multiple implementations)
   - No context detection logic needed
   - No conditional rendering based on environment
   - Client-side filtering is straightforward
   - Well-documented design decisions

7. **Clear architectural boundaries**
   - AllPaths HTML = browsing and progress tracking
   - Validation logic = internal categorization for AI checking
   - Git categories (NEW/MODIFIED/UNCHANGED) never exposed in HTML
   - Validation results go to PR comments, not HTML
   - Each component has clear responsibility

### Negative

1. **Additional HTML features**
   - More JavaScript for date and validation status filtering
   - Additional UI elements (filter buttons, date display, badges)
   - **Mitigation**: Clear separation of concerns, well-commented code, client-side performance is excellent

2. **Client-side date parsing**
   - Relies on JavaScript Date parsing (timezone handling)
   - **Mitigation**: All dates in UTC ISO format (standardized, reliable across browsers)

3. **Missing date handling**
   - Paths without dates excluded from time-based filters
   - **Mitigation**: Transparent ("Unknown" label), dates rarely missing in practice, path still visible

4. **Cannot distinguish PR changes in HTML**
   - HTML doesn't show what changed in this PR (that's internal to validation)
   - Writers see all paths with dates, not PR-specific categories
   - **Mitigation**: This is intentional - PR changes are tracked internally, HTML is for browsing
   - **Note**: Validation results in PR comments show what changed and was validated

### Risks and Mitigations

**Risk 1: Filter utility**
- **Risk**: Time windows (1 day, 1 week) may not match all writers' needs
- **Mitigation**: Actual dates always visible (filters are optional tools), writers can manually inspect dates
- **Monitoring**: Gather feedback on filter usefulness

**Risk 2: Missing date metadata**
- **Risk**: Validation cache may lack dates for some paths
- **Mitigation**: Display "Unknown", exclude from filters, page remains functional, dates rarely missing
- **Monitoring**: Log warnings when dates unavailable

**Risk 3: Browser compatibility**
- **Risk**: Date parsing may differ across browsers
- **Mitigation**: Use standard ISO format, test in major browsers, UTC prevents timezone issues
- **Status**: Standard JavaScript Date parsing is well-supported

**Risk 4: Performance with many paths**
- **Risk**: Client-side filtering may be slow with 100+ paths
- **Mitigation**: Date parsing/comparison is trivial (<1ms per path), tested up to 200 paths
- **Status**: Performance is excellent in practice

## Implementation Constraints

These constraints must be followed during implementation to ensure correct behavior:

### 1. Execution Order: Date Collection Before HTML Generation

**Constraint:** Date collection MUST occur before HTML generation in the build process.

**Rationale:**
- HTML generator reads `created_date` and `commit_date` from validation cache
- If dates are collected AFTER HTML generation, HTML will use stale cache data
- This causes a one-build delay where dates appear as "Unknown" on first run
- In CI/CD environments where each build starts fresh, this means HTML always shows "Unknown" dates

**Implementation:**
```python
# CORRECT ORDER:
# 1. Collect dates from git history and update cache
for path in all_paths:
    commit_date = get_path_commit_date(path, passage_to_file, repo_root)
    creation_date = get_path_creation_date(path, passage_to_file, repo_root)
    # Update validation cache with dates...

# 2. THEN generate HTML (reads dates from cache)
html_output = generate_html_output(all_paths, validation_cache, ...)
```

**Why This Failed Initially:**
- Original implementation collected dates AFTER HTML generation (lines 1577-1603 after line 1532)
- Caused timing bug where 35 of 49 paths showed "Unknown" dates
- Fixed by moving date collection to execute before HTML generation (commit 6ef6903)

**Validation:**
- Verify date collection loop executes before `generate_html_output()` call
- Test that first build shows dates correctly (no "Unknown" values)
- Ensure cache is populated with fresh data before HTML reads it

---

### 2. Git History Requirements

**Constraint:** Full git history must be available for date collection.

**Rationale:**
- Date collection uses `git log` to find when passages were first added
- Shallow clones (default in CI/CD) only have recent history
- Without full history, creation dates will be incomplete or missing

**Implementation:**
```yaml
# GitHub Actions checkout configuration
- uses: actions/checkout@v4
  with:
    fetch-depth: 0  # Fetch full history, not shallow clone
```

**Why This Matters:**
- CI/CD environments often use shallow clones by default (fetch-depth: 1)
- Creation dates require finding first commit that introduced a passage
- Shallow clones can't find initial commits, resulting in missing dates

---

### 3. Lessons Learned

**Finding Root Causes:**
- Empirical testing is essential - replicate the failure before proposing fixes
- "Unknown" dates indicated timing issue, not missing git history
- Running actual build locally revealed one-build delay pattern
- Second run showing correct dates confirmed timing hypothesis

**Architecture Documentation:**
- Original ADR showed "Load date metadata from cache" but didn't specify execution order
- Architecture was imprecise, not wrong - didn't explicitly state constraint
- Adding this constraints section prevents future developers from repeating the timing bug
- Implementation details like execution order should be documented when they're critical

---

## Alternatives Considered

### Alternative 1: Context-Aware Dual-Mode Rendering

**Approach:** Generate different HTML based on context (PR vs deployment)
- PR context: Show git-based categories (NEW/MODIFIED/UNCHANGED) with category filters
- Deployment context: Show dates with time-based filters
- Use `GITHUB_BASE_REF` environment variable to detect context

**Rejected because:**
- **Violates consistency principle**: PR preview doesn't match deployment
- **Confuses writers**: Different information in different contexts creates uncertainty
- **Untrustworthy PR previews**: Writers can't validate that deployment will match what they see
- **Unnecessary complexity**: Context detection and conditional rendering adds code complexity
- **Wrong architectural boundary**: Git categories are internal to validation logic, not user-facing
- **PM specification explicitly rejects this**: Requires "single consistent interface"

**Why this was initially tempting:**
- Seemed to optimize each context for its specific use case
- PR context shows "what changed in this PR" directly
- But this trades away consistency, which is more valuable

---

### Alternative 2: Separate HTML Generators

**Approach:** Create two separate HTML generator functions (one for PR, one for deployment)

**Rejected because:**
- Same problems as Alternative 1 (inconsistency)
- Additionally: Code duplication, harder to maintain, inconsistent styling risk
- No clear benefit over single generator

---

### Alternative 3: Show Git Categories in HTML

**Approach:** Display NEW/MODIFIED/UNCHANGED categories alongside dates in HTML

**Rejected because:**
- **Wrong architectural boundary**: These categories are internal to validation logic
- **Context-dependent information**: Categories only meaningful in PR context (relative to base branch)
- **Confusing in deployment**: What does "NEW" mean on deployed site? New since when?
- **PM specification explicitly rejects this**: Categories are internal, not displayed

---

### Alternative 4: Server-Side Date Filtering

**Approach:** Generate different HTML files based on filter state (pre-filtered)

**Rejected because:**
- Requires generating multiple HTML files (combinatorial explosion with filter combinations)
- Slower (no instant filter toggling)
- More disk space (multiple HTML files)
- Less flexible (can't combine filters dynamically)
- Client-side is fast enough for this use case

---

### Alternative 5: Relative Date Labels

**Approach:** Show "Today", "Yesterday", "This Week" instead of exact dates

**Rejected because:**
- Ambiguous (timezone-dependent)
- Changes meaning over time (page cached, stale labels)
- Less precise (writers want exact dates)
- PM specification asks for actual timestamps

---

### Alternative 6: Hide Validation Status from HTML

**Approach:** Don't show validation status badges, keep that information internal

**Rejected because:**
- Less useful for quality tracking
- Writers benefit from seeing which paths have been validated
- Status is valuable information for coordinating review work
- Already in cache, no additional cost to display

## Validation

The single-interface architecture can be validated by:

### 1. Consistency Tests
- **PR preview matches deployment**: Generate HTML in PR build and main build, compare output (should be identical except for dynamic dates)
- **No context detection**: Verify no code checks `GITHUB_BASE_REF` or other environment variables for UI decisions
- **Same filters everywhere**: All builds display time-based filters and validation status filters

### 2. Functional Tests
- **Date display**: All paths display creation and modification dates in human-readable format
- **Time-based filters**: "Created Last Day/Week" and "Modified Last Day/Week" correctly filter paths
- **Validation status**: Paths display "Validated" or "New" badges correctly
- **Filter combination**: Multiple active filters apply AND logic correctly
- **Missing dates**: Paths with missing dates show "Unknown" and are excluded from time-based filters
- **Statistics update**: Filter counters update correctly when filters are active

### 3. Performance Tests
- **Build time**: Remains under 5 minutes (no performance regression)
- **Client-side filtering**: Completes in under 100ms for 100 paths
- **No additional git operations**: Date collection doesn't add git queries (uses cached data)

### 4. Compatibility Tests
- **Browser compatibility**: Date parsing works consistently across Chrome, Firefox, Safari
- **Responsive design**: Interface functions on desktop and mobile devices
- **Semantic HTML**: `<time>` elements with `datetime` attributes for accessibility

### 5. Integration Tests
- **Backward compatibility**: Validation cache structure unchanged
- **No breaking changes**: Existing workflows and scripts continue to work
- **Date fields present**: `created_date` and `commit_date` already in cache

## Future Enhancements

Possible architectural improvements beyond this ADR:

### 1. Configurable Time Windows
- **Enhancement**: Allow custom date ranges (e.g., "Last 3 days", "Last month")
- **Use case**: Writers with different writing rhythms or tracking needs
- **Architectural consideration**: Store preferences in localStorage, maintain performance with arbitrary ranges
- **Trade-off**: Added complexity vs. fixed windows that work for most users

### 2. Date Range Picker
- **Enhancement**: Visual calendar for selecting arbitrary date ranges
- **Use case**: Analyze specific time periods (e.g., "show me what I wrote during week 2 of NaNoWriMo")
- **Architectural consideration**: Calendar UI adds significant client-side complexity
- **Trade-off**: Flexibility vs. simplicity

### 3. Statistics by Time Period
- **Enhancement**: Show aggregated statistics like "15 paths created this week", "8 paths modified today"
- **Use case**: Quick progress overview without counting filtered results
- **Architectural consideration**: May require server-side aggregation for large datasets
- **Trade-off**: Additional computation vs. useful progress metrics

### 4. Sort by Date
- **Enhancement**: Sort paths by creation or modification date (newest/oldest first)
- **Use case**: See most recently created or modified paths at the top
- **Architectural consideration**: Sorting large lists may require virtualization for performance
- **Trade-off**: Additional UI complexity vs. improved browsing

### 5. Export Filtered Results
- **Enhancement**: Download list of paths matching current filters (CSV, JSON)
- **Use case**: External analysis, sharing progress reports
- **Architectural consideration**: Export mechanism needs to respect active filter state
- **Trade-off**: Implementation effort vs. advanced use case utility

### 6. Path Activity Timeline
- **Enhancement**: Visual timeline or heatmap showing when paths were created/modified
- **Use case**: Visualize writing activity patterns over time
- **Architectural consideration**: Requires data aggregation and visualization library (e.g., D3.js)
- **Trade-off**: Significant implementation effort vs. visual storytelling value

## References

### PM Specifications
- **AllPaths Progress Tracking**: `/home/user/NaNoWriMo2025/features/allpaths-categorization.md`
  - Defines user needs, acceptance criteria, and feature behavior
  - Specifies single consistent interface requirement
  - Documents time-based filters and validation status display

- **AI Continuity Checking**: `/home/user/NaNoWriMo2025/features/ai-continuity-checking.md`
  - Defines internal categorization (NEW/MODIFIED/UNCHANGED)
  - Specifies that categories are internal to validation logic
  - Documents that validation results go to PR comments, not HTML

### Implementation
- **AllPaths Generator**: `/home/user/NaNoWriMo2025/formats/allpaths/generator.py`
- **User Documentation**: `/home/user/NaNoWriMo2025/formats/allpaths/README.md`

### Related ADRs
- **ADR-001**: AllPaths Format for AI Continuity Validation (path generation via DFS)
- **ADR-002**: Validation Cache Architecture (date fields and validation status defined here)
- **ADR-004**: Content-Based Hashing for Change Detection (how path changes are detected)
