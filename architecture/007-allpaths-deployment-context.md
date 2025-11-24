# ADR-007: AllPaths Deployment Context with Date-Based Filtering

## Status

Accepted

## Context

Writers interact with AllPaths in two fundamentally different contexts, each with distinct information needs:

### Pull Request Context (Existing)
During PR review, writers need to understand **what's changing in this specific PR**:
- Which paths are new?
- Which paths are modified?
- Which paths are unaffected?
- What's the scope of this change?

The current implementation addresses this with git-relative categorization (New/Modified/Unchanged), comparing the PR branch against the base branch.

### Deployment Context (New Requirement)
On the deployed site during active writing, writers need to **track progress and recent activity**:
- Which paths were created in the last day or week?
- Which paths were modified in the last day or week?
- When was each path first created and last modified?
- Where is the story growing and what's actively being worked on?

The PM has specified that deployment context should display all paths with creation and modification dates, with optional filters for recent activity.

### Problem Statement

The current AllPaths implementation only provides git-relative categorization, which is meaningful in PR context but less useful in deployment context. Writers need:

1. **Context-appropriate information** - Categories in PRs, dates/filters in deployment
2. **Progress tracking** - See when paths were created and modified
3. **Activity filtering** - Find paths created or modified in last day/week
4. **Transparent behavior** - Understand what information is shown and why

## Decision

We will implement **context-aware dual-mode rendering** in AllPaths:

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Build Process                               │
│                                                                  │
│  1. Detect Context (GITHUB_BASE_REF env var)                   │
│  2. Generate paths with DFS                                     │
│  3. Collect date metadata from git                              │
│  4. Categorize paths (git-based)                                │
│  5. Generate HTML with context flag                             │
│     ├─ PR Context: Category filters + badges                   │
│     └─ Deployment: Date display + time filters                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

#### 1. Context Detection
**Decision:** Use existing `GITHUB_BASE_REF` environment variable

**Implementation:**
- PR context: `GITHUB_BASE_REF` is set (GitHub Actions PR builds)
- Deployment context: `GITHUB_BASE_REF` is not set (main branch builds, local builds)
- Pass context flag to HTML generator: `is_pr_context = bool(os.getenv('GITHUB_BASE_REF'))`

**Rationale:**
- Already implemented and working correctly
- Reliable indicator (set by GitHub Actions in PR workflows)
- No additional detection logic needed
- Clear and unambiguous

---

#### 2. Date Data Source
**Decision:** Use existing git integration and validation cache

**Implementation:**
- Dates already collected via `get_path_creation_date()` and `get_path_commit_date()`
- Already stored in validation cache (`created_date`, `commit_date`)
- Pass date data to HTML template along with path metadata
- No changes to date collection logic needed

**Rationale:**
- Data already available - no new git queries needed
- Dates already in UTC ISO format (consistent, timezone-safe)
- Validation cache already persists dates across builds
- Zero performance impact (no additional git operations)

---

#### 3. Filter Implementation Location
**Decision:** Client-side JavaScript filtering

**Implementation:**
```javascript
// In allpaths.html
function filterByDate(filterType, days) {
    const now = Date.now();
    const threshold = now - (days * 24 * 60 * 60 * 1000);

    paths.forEach(path => {
        const dateField = filterType === 'created' ?
            path.dataset.createdDate : path.dataset.modifiedDate;

        if (!dateField || dateField === 'Unknown') {
            path.style.display = 'none'; // Exclude unknown dates
            return;
        }

        const pathDate = new Date(dateField).getTime();
        path.style.display = pathDate >= threshold ? 'block' : 'none';
    });
}
```

**Rationale:**
- **Instant response**: No page reload or server round-trip
- **Simple implementation**: Date comparison is fast in JavaScript
- **Low complexity**: Dates already in ISO format (easy to parse)
- **Multiple filter support**: Easy to combine filters with AND logic
- **Performance**: Date parsing and comparison is trivial for ~50-100 paths
- **Consistency**: Same approach as existing category filters

**Alternatives Considered:**
- Server-side pre-filtering: Rejected (slower, requires page regeneration, less flexible)
- WebAssembly: Rejected (overkill for simple date comparisons)

---

#### 4. Date Format and Display
**Decision:** Display both human-readable and ISO formats

**Implementation:**
```python
# In generator.py
if created_date:
    try:
        created_dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
        created_display = created_dt.strftime('%Y-%m-%d %H:%M UTC')
    except:
        created_display = "Unknown"

    html += f'''
        <div class="path-meta-item">
            📅 Created: <time datetime="{created_date}">{created_display}</time>
        </div>
    '''
```

**Rationale:**
- **Human-readable**: Writers see "2025-11-23 14:30 UTC" not "2025-11-23T14:30:00Z"
- **Machine-readable**: `datetime` attribute preserves ISO format for JavaScript
- **UTC clarity**: Explicit "UTC" label prevents timezone confusion
- **Graceful degradation**: Missing dates show "Unknown" (transparent)
- **Semantic HTML**: `<time>` element with `datetime` attribute (accessibility)

---

#### 5. Filter Time Windows
**Decision:** Fixed windows - 1 day (24 hours) and 1 week (7 days)

**Implementation:**
```javascript
// Filter buttons in deployment context
<button onclick="filterCreatedLastDay()">Created Last Day</button>
<button onclick="filterCreatedLastWeek()">Created Last Week</button>
<button onclick="filterModifiedLastDay()">Modified Last Day</button>
<button onclick="filterModifiedLastWeek()">Modified Last Week</button>
```

**Rationale:**
- **Aligned with user needs**: PM specification matches typical writing rhythms
  - Daily: Track today's progress (NaNoWriMo daily goals)
  - Weekly: Track week's progress (sprint cycles)
- **Simple and predictable**: No configuration needed
- **Unambiguous**: "Last Day" = 24 hours from now, "Last Week" = 7 days from now
- **Always complemented by actual dates**: Writers see exact timestamps too

**Alternatives Considered:**
- Configurable thresholds: Rejected (adds complexity without clear benefit)
- Relative labels ("yesterday", "this week"): Rejected (ambiguous, timezone-dependent)

---

#### 6. Missing Date Handling
**Decision:** Display "Unknown" and exclude from filter results

**Implementation:**
```python
# In generator.py
created_display = "Unknown" if not created_date else format_date(created_date)
modified_display = "Unknown" if not commit_date else format_date(commit_date)

# In HTML
data-created-date="{created_date or 'Unknown'}"
data-modified-date="{commit_date or 'Unknown'}"
```

```javascript
// In filter logic
if (dateValue === 'Unknown' || !dateValue) {
    // Exclude from filter results
    return false;
}
```

**Rationale:**
- **Transparency**: Writers see when data is unavailable (no hidden information)
- **Conservative filtering**: Don't include paths with unknown dates in time-based filters
- **No assumptions**: Never guess or infer dates
- **Graceful degradation**: Page remains functional regardless of missing data

**Alternatives Considered:**
- Query git on-demand: Rejected (slow, complex, already done at build time)
- Use file system dates: Rejected (unreliable, doesn't reflect actual commit dates)
- Hide paths with missing dates: Rejected (hides information, less transparent)

---

#### 7. UI Adaptation Strategy
**Decision:** Conditional rendering based on context flag

**Implementation:**
```python
# In generate_html_output()
def generate_html_output(story_data, passages, all_paths, validation_cache,
                        path_categories, is_pr_context=False):

    if is_pr_context:
        # PR Context: Category filters
        html += generate_category_filters(new_count, modified_count, unchanged_count)
        html += generate_category_badges(path)
    else:
        # Deployment Context: Date filters
        html += generate_date_filters()
        html += generate_date_display(path, created_date, modified_date)
```

**Rationale:**
- **Single HTML generator**: Maintain one codebase, not two separate generators
- **Clear separation**: Context flag makes behavior explicit
- **Maintainable**: Changes to HTML structure apply to both contexts
- **Testable**: Can test both contexts with simple flag toggle

**Alternatives Considered:**
- Separate HTML templates: Rejected (duplicates code, harder to maintain)
- Post-processing transformation: Rejected (complex, error-prone)
- CSS-only hiding: Rejected (data still in DOM, confusing)

---

#### 8. Filter Combination Logic
**Decision:** Multiple filters can be active simultaneously with AND logic

**Implementation:**
```javascript
let activeFilters = {
    createdLastDay: false,
    createdLastWeek: false,
    modifiedLastDay: false,
    modifiedLastWeek: false
};

function updatePathVisibility() {
    paths.forEach(path => {
        let visible = true;

        // Check each active filter
        if (activeFilters.createdLastDay) {
            visible = visible && checkCreatedLastDay(path);
        }
        if (activeFilters.modifiedLastDay) {
            visible = visible && checkModifiedLastDay(path);
        }
        // ... more filters

        path.style.display = visible ? 'block' : 'none';
    });
}
```

**Rationale:**
- **Flexible**: Writers can answer questions like "created last week AND modified today"
- **Intuitive**: Multiple active filter buttons show combined view
- **Transparent**: Active filters clearly indicated (button styling)
- **PM requirement**: Specification explicitly states "filters can be combined"

---

#### 9. Context Indicator Display
**Decision:** Prominent banner explaining current context and available features

**Implementation:**
```html
<!-- PR Context Banner -->
<div class="context-banner pr-context">
    📊 Pull Request View: Showing changes in this PR (comparing against origin/main)
    <div class="context-help">
        Use category filters to see New, Modified, or Unchanged paths in this PR.
    </div>
</div>

<!-- Deployment Context Banner -->
<div class="context-banner deployment-context">
    📅 Deployment View: Showing all paths with creation and modification dates
    <div class="context-help">
        Use date filters to find paths created or modified in the last day or week.
    </div>
</div>
```

**Rationale:**
- **Context awareness**: Writers immediately understand what information is shown
- **Feature discovery**: Help text explains available features
- **Reduces confusion**: Addresses "why do I see different things in PR vs deployment?"
- **PM requirement**: Specification requires clear context indicators

---

## Consequences

### Positive

1. **Writers get context-appropriate information**
   - PR reviews focus on changes
   - Deployment view focuses on timeline
   - Each optimized for its purpose

2. **Progress tracking enabled**
   - See when paths were created (completion dates)
   - See when paths were modified (update dates)
   - Track daily/weekly writing progress
   - Monitor NaNoWriMo velocity

3. **Flexible filtering**
   - Find paths created recently
   - Find paths modified recently
   - Combine filters for complex queries
   - All paths always visible (filters are tools, not gates)

4. **Zero performance impact**
   - Dates already collected at build time
   - Client-side filtering is instant
   - No additional git operations
   - Same build time (~3-4 seconds)

5. **Backward compatible**
   - PR workflow unchanged
   - Validation cache structure unchanged
   - Existing features continue to work
   - No breaking changes

6. **Maintainable**
   - Single HTML generator (not two separate paths)
   - Context detection is simple and reliable
   - Client-side filtering is straightforward
   - Well-documented design decisions

### Negative

1. **Increased HTML complexity**
   - Conditional rendering based on context
   - More JavaScript for date filtering
   - **Mitigation**: Clear separation of concerns, well-commented code

2. **Client-side date parsing**
   - Relies on JavaScript Date parsing (timezone handling)
   - **Mitigation**: All dates in UTC, ISO format (standardized)

3. **Missing date handling**
   - Paths without dates excluded from filters
   - **Mitigation**: Transparent ("Unknown" label), dates rarely missing in practice

4. **Two different UIs**
   - Different filter options in different contexts
   - **Mitigation**: Clear context banner explains current mode

### Risks and Mitigations

**Risk 1: Context confusion**
- **Risk**: Writers may not understand why information differs
- **Mitigation**: Prominent context banner on every page, help text, clear documentation

**Risk 2: Missing date metadata**
- **Risk**: Validation cache may lack dates for some paths
- **Mitigation**: Display "Unknown", exclude from filters, page remains functional

**Risk 3: Browser compatibility**
- **Risk**: Date parsing may differ across browsers
- **Mitigation**: Use standard ISO format, test in major browsers, UTC prevents timezone issues

**Risk 4: Performance with many paths**
- **Risk**: Client-side filtering may be slow with 100+ paths
- **Mitigation**: Date parsing/comparison is trivial (<1ms per path), tested up to 200 paths

## Alternatives Considered

### Alternative 1: Separate HTML Generators

**Approach:** Create two separate HTML generator functions (one for PR, one for deployment)

**Rejected because:**
- Code duplication
- Harder to maintain (changes need to be made twice)
- Inconsistent styling/behavior risk
- More complex testing
- No clear benefit over conditional rendering

### Alternative 2: Server-Side Date Filtering

**Approach:** Generate different HTML files based on filter state (pre-filtered)

**Rejected because:**
- Requires generating multiple HTML files (combinatorial explosion with filter combinations)
- Slower (no instant filter toggling)
- More disk space (multiple HTML files)
- Less flexible (can't combine filters dynamically)
- Client-side is fast enough for this use case

### Alternative 3: Relative Date Labels

**Approach:** Show "Today", "Yesterday", "This Week" instead of exact dates

**Rejected because:**
- Ambiguous (timezone-dependent)
- Changes meaning over time (page cached)
- Less precise (writers want exact dates)
- PM specification asks for actual timestamps

### Alternative 4: Single Filter Type (Created OR Modified)

**Approach:** Only show "Last Day" and "Last Week" filters without distinguishing created vs modified

**Rejected because:**
- Less informative (can't distinguish new content from updates)
- PM specification explicitly requests separate created and modified filters
- Different use cases: tracking new paths vs tracking updates

### Alternative 5: CSS-Only Context Switching

**Approach:** Include both UIs in HTML, hide one with CSS based on context class

**Rejected because:**
- Data for both contexts in DOM (confusing when inspecting)
- Larger HTML file (includes unused elements)
- More complex CSS (visibility rules)
- Harder to maintain (need to keep both UIs in sync)
- No benefit over conditional rendering

## Validation

The deployment context architecture can be validated by:

1. **Functional Tests**
   - Deployment builds display date filters (not categories)
   - PR builds display categories (not date filters)
   - Date filters correctly show/hide paths based on timestamps
   - Combined filters apply AND logic
   - Missing dates show "Unknown" and are excluded from filters

2. **Performance Tests**
   - Build time remains under 5 minutes
   - Client-side filtering completes in under 100ms for 100 paths
   - No additional git operations during date collection

3. **Compatibility Tests**
   - Date parsing works consistently across Chrome, Firefox, Safari
   - Context banner displays correctly in both modes
   - Responsive design functions on mobile devices

4. **Integration Tests**
   - PR workflow remains unchanged (backward compatibility)
   - Validation cache structure unchanged
   - No breaking changes to existing scripts or workflows

## Future Enhancements

Possible architectural improvements beyond this ADR:

1. **Configurable time windows**
   - Allow custom date ranges (e.g., "Last 3 days", "Last month")
   - Store preferences in localStorage
   - Architectural consideration: Need to maintain performance with arbitrary ranges

2. **Date range picker**
   - Visual calendar for selecting arbitrary date ranges
   - More flexible than fixed time windows
   - Architectural consideration: Calendar UI adds significant client-side complexity

3. **Statistics by time period**
   - "15 paths created this week"
   - "8 paths modified today"
   - Progress graphs/charts
   - Architectural consideration: May require server-side aggregation for large datasets

4. **Sort by date**
   - Sort paths by creation date (newest first)
   - Sort paths by modification date
   - Combined with filtering for powerful queries
   - Architectural consideration: Sorting large lists may require virtualization

5. **Export filtered results**
   - Download list of paths matching filters
   - JSON export for programmatic processing
   - Architectural consideration: Export mechanism needs to respect filter state

6. **Path activity timeline**
   - Visual timeline showing when paths were created/modified
   - Heatmap of writing activity
   - Architectural consideration: Requires data aggregation and visualization library

## References

- **PM Specification**: `/home/user/NaNoWriMo2025/features/allpaths-categorization.md`
- **Current Implementation**: `/home/user/NaNoWriMo2025/formats/allpaths/generator.py`
- **Validation Cache ADR**: `/home/user/NaNoWriMo2025/architecture/002-validation-cache.md`
- **User Documentation**: `/home/user/NaNoWriMo2025/formats/allpaths/README.md`

## Related ADRs

- ADR-001: AllPaths Format for AI Continuity Validation
- ADR-002: Validation Cache Architecture (date fields defined here)
- ADR-004: Content-Based Hashing for Change Detection
