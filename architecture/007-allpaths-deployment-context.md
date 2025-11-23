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

## Implementation Plan

### Phase 1: Generator Changes (Python)

**File:** `/home/user/NaNoWriMo2025/formats/allpaths/generator.py`

**Changes:**

1. **Detect context in main()**
```python
# Around line 1422
is_pr_context = bool(os.getenv('GITHUB_BASE_REF'))
print(f"Context: {'PR' if is_pr_context else 'Deployment'}", file=sys.stderr)
```

2. **Pass context to HTML generator**
```python
# Around line 1440
html_output = generate_html_output(story_data, passages, all_paths,
                                   validation_cache, path_categories,
                                   is_pr_context=is_pr_context)
```

3. **Update HTML generator signature**
```python
# Around line 857
def generate_html_output(story_data: Dict, passages: Dict, all_paths: List[List[str]],
                        validation_cache: Dict = None, path_categories: Dict[str, str] = None,
                        is_pr_context: bool = False) -> str:
```

4. **Add date data attributes to path elements**
```python
# Around line 1224 (in path HTML generation)
created_date = validation_cache.get(path_hash, {}).get('created_date', '')
commit_date = validation_cache.get(path_hash, {}).get('commit_date', '')

html += f'''
    <div class="path {category}" data-status="{category}"
         data-created-date="{created_date}"
         data-modified-date="{commit_date}">
'''
```

5. **Conditional filter section rendering**
```python
# Around line 1200 (filter section)
if is_pr_context:
    # Render category filters (existing code)
    html += generate_pr_filter_section(new_count, modified_count, unchanged_count)
else:
    # Render date filters (new code)
    html += generate_deployment_filter_section()
```

6. **Conditional metadata display**
```python
# Around line 1240 (path metadata)
if is_pr_context:
    # Show category badge (existing)
    html += f'<span class="badge {category_badge_class}">{category_text}</span>'
else:
    # Show creation and modification dates (new)
    if created_date:
        html += f'<div class="path-meta-item">📅 Created: {format_date(created_date)}</div>'
    if commit_date:
        html += f'<div class="path-meta-item">🔄 Modified: {format_date(commit_date)}</div>'
```

7. **Add date formatting helper**
```python
def format_date_for_display(iso_date: str) -> str:
    """Format ISO date for human-readable display.

    Args:
        iso_date: ISO format datetime string from git

    Returns:
        Human-readable date string with UTC indicator
    """
    if not iso_date:
        return "Unknown"

    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except:
        # Fallback: show first 16 chars (date + time)
        return iso_date[:16] if len(iso_date) >= 16 else "Unknown"
```

### Phase 2: HTML/JavaScript Changes

**File:** Generated HTML in `generate_html_output()` function

**Changes:**

1. **Add context banner**
```html
<!-- Around line 1160 (after header) -->
<div class="context-banner {{'pr-context' if is_pr_context else 'deployment-context'}}">
    {{% if is_pr_context %}}
        📊 Pull Request View: Comparing changes against base branch
        <div class="context-help">
            Categories show what's changing in this PR. Use filters to focus on New or Modified paths.
        </div>
    {{% else %}}
        📅 Deployment View: All paths with creation and modification dates
        <div class="context-help">
            Filters help you find paths created or modified recently. All paths remain visible.
        </div>
    {{% endif %}}
</div>
```

2. **Add date filter buttons (deployment context)**
```html
<!-- Replaces category filters in deployment context -->
<div class="filter-section">
    <h3>Date Filters</h3>
    <div class="filter-buttons">
        <button class="filter-btn" onclick="filterCreatedLastDay(this)">
            Created Last Day
        </button>
        <button class="filter-btn" onclick="filterCreatedLastWeek(this)">
            Created Last Week
        </button>
        <button class="filter-btn" onclick="filterModifiedLastDay(this)">
            Modified Last Day
        </button>
        <button class="filter-btn" onclick="filterModifiedLastWeek(this)">
            Modified Last Week
        </button>
        <button class="filter-btn" onclick="clearAllFilters()">
            Clear Filters
        </button>
    </div>
    <div id="filter-status" class="filter-status"></div>
</div>
```

3. **Add CSS for context banner**
```css
.context-banner {
    background: white;
    margin: 2rem auto;
    max-width: 1200px;
    padding: 1.5rem;
    border-radius: 8px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    border-left: 5px solid #667eea;
}

.context-banner.pr-context {
    border-left-color: #007bff;
}

.context-banner.deployment-context {
    border-left-color: #28a745;
}

.context-help {
    margin-top: 0.5rem;
    font-size: 0.875rem;
    color: #666;
}

.filter-status {
    margin-top: 1rem;
    padding: 0.5rem;
    background: #f8f9fa;
    border-radius: 4px;
    font-size: 0.875rem;
    color: #666;
}
```

4. **Add JavaScript date filtering**
```javascript
// At bottom of HTML, in <script> section

// Date filter state
let activeFilters = {
    createdLastDay: false,
    createdLastWeek: false,
    modifiedLastDay: false,
    modifiedLastWeek: false
};

function filterCreatedLastDay(button) {
    toggleFilter('createdLastDay', button);
    applyFilters();
}

function filterCreatedLastWeek(button) {
    toggleFilter('createdLastWeek', button);
    applyFilters();
}

function filterModifiedLastDay(button) {
    toggleFilter('modifiedLastDay', button);
    applyFilters();
}

function filterModifiedLastWeek(button) {
    toggleFilter('modifiedLastWeek', button);
    applyFilters();
}

function toggleFilter(filterName, button) {
    activeFilters[filterName] = !activeFilters[filterName];
    button.classList.toggle('active');
}

function clearAllFilters() {
    // Reset all filters
    Object.keys(activeFilters).forEach(key => activeFilters[key] = false);

    // Remove active class from all buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show all paths
    document.querySelectorAll('.path').forEach(path => {
        path.style.display = 'block';
    });

    updateFilterStatus();
}

function applyFilters() {
    const now = Date.now();
    const oneDayMs = 24 * 60 * 60 * 1000;
    const oneWeekMs = 7 * oneDayMs;

    const paths = document.querySelectorAll('.path');
    let visibleCount = 0;

    paths.forEach(path => {
        let visible = true;

        // Check created filters
        if (activeFilters.createdLastDay || activeFilters.createdLastWeek) {
            const createdDate = path.dataset.createdDate;
            if (!createdDate || createdDate === 'Unknown') {
                visible = false;
            } else {
                const pathDate = new Date(createdDate).getTime();
                const threshold = activeFilters.createdLastDay ?
                    (now - oneDayMs) : (now - oneWeekMs);

                if (pathDate < threshold) {
                    visible = false;
                }
            }
        }

        // Check modified filters (AND logic with created filters)
        if (visible && (activeFilters.modifiedLastDay || activeFilters.modifiedLastWeek)) {
            const modifiedDate = path.dataset.modifiedDate;
            if (!modifiedDate || modifiedDate === 'Unknown') {
                visible = false;
            } else {
                const pathDate = new Date(modifiedDate).getTime();
                const threshold = activeFilters.modifiedLastDay ?
                    (now - oneDayMs) : (now - oneWeekMs);

                if (pathDate < threshold) {
                    visible = false;
                }
            }
        }

        path.style.display = visible ? 'block' : 'none';
        if (visible) visibleCount++;
    });

    updateFilterStatus();
}

function updateFilterStatus() {
    const statusDiv = document.getElementById('filter-status');
    if (!statusDiv) return;

    const totalPaths = document.querySelectorAll('.path').length;
    const visiblePaths = document.querySelectorAll('.path[style*="display: block"], .path:not([style*="display"])').length;

    const activeFilterNames = Object.keys(activeFilters)
        .filter(key => activeFilters[key])
        .map(key => key.replace(/([A-Z])/g, ' $1').trim())
        .map(s => s.charAt(0).toUpperCase() + s.slice(1));

    if (activeFilterNames.length === 0) {
        statusDiv.textContent = `Showing all ${totalPaths} paths`;
    } else {
        statusDiv.textContent = `Showing ${visiblePaths} of ${totalPaths} paths (filters: ${activeFilterNames.join(', ')})`;
    }
}

// Initialize filter status on page load
document.addEventListener('DOMContentLoaded', updateFilterStatus);
```

### Phase 3: Documentation Updates

**Files to Update:**

1. **`/home/user/NaNoWriMo2025/formats/allpaths/README.md`**
   - Add "Context-Aware Behavior" section
   - Explain PR context (categories)
   - Explain deployment context (dates + filters)
   - Document filter time windows
   - Show example screenshots or descriptions

2. **`/home/user/NaNoWriMo2025/features/allpaths-categorization.md`**
   - Mark as "Implemented" after completion
   - Add implementation notes
   - Document any deviations from spec

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

## Success Criteria

The deployment context feature is successful if:

1. ✅ Deployment builds show all paths with creation and modification dates
2. ✅ Date filters work correctly (Created/Modified Last Day/Week)
3. ✅ Filters can be combined (AND logic)
4. ✅ Missing dates displayed as "Unknown" and excluded from filters
5. ✅ PR builds continue to show categories (backward compatible)
6. ✅ Context clearly indicated on every page (banner)
7. ✅ Performance remains fast (build time <5 minutes, filtering instant)
8. ✅ No breaking changes to existing workflows

## Testing Strategy

### Unit Tests (Python)

1. **Context detection**
   - Test with GITHUB_BASE_REF set (PR context)
   - Test with GITHUB_BASE_REF unset (deployment context)

2. **Date formatting**
   - Test with valid ISO dates
   - Test with missing dates
   - Test with malformed dates (graceful degradation)

3. **HTML generation**
   - Test PR context HTML (category filters)
   - Test deployment context HTML (date filters)
   - Verify correct data attributes

### Integration Tests (Browser)

1. **Date filter functionality**
   - Click "Created Last Day" - verify only recent paths shown
   - Click multiple filters - verify AND logic
   - Click "Clear Filters" - verify all paths shown

2. **Context banner**
   - PR build: Verify PR context banner shown
   - Deployment build: Verify deployment context banner shown

3. **Date display**
   - Verify dates in human-readable format
   - Verify "Unknown" shown for missing dates
   - Verify dates in UTC

4. **Browser compatibility**
   - Test in Chrome, Firefox, Safari
   - Verify date parsing works consistently
   - Verify filtering works in all browsers

### Manual Testing

1. **PR workflow**
   - Create PR with new paths
   - Verify categories shown (not date filters)
   - Verify category filtering works

2. **Deployment workflow**
   - Deploy to main branch
   - Verify date filters shown (not categories)
   - Verify date filtering works
   - Verify date display accurate

3. **Edge cases**
   - Fresh repository (all new paths)
   - Old repository (no recent activity)
   - Missing date metadata
   - Very large number of paths (100+)

## Implementation Estimate

**Complexity:** Medium

**Estimated Effort:**
- Python changes: 2-3 hours
- HTML/JavaScript changes: 3-4 hours
- CSS styling: 1 hour
- Testing: 2-3 hours
- Documentation: 1-2 hours

**Total:** 9-13 hours of development work

**Dependencies:**
- None (all required data already available)

**Risks:**
- Low risk (incremental change, backward compatible)

## Future Enhancements

Possible improvements beyond this ADR:

1. **Configurable time windows**
   - Allow custom date ranges (e.g., "Last 3 days", "Last month")
   - Store preferences in localStorage

2. **Date range picker**
   - Visual calendar for selecting arbitrary date ranges
   - More flexible than fixed time windows

3. **Statistics by time period**
   - "15 paths created this week"
   - "8 paths modified today"
   - Progress graphs/charts

4. **Sort by date**
   - Sort paths by creation date (newest first)
   - Sort paths by modification date
   - Combined with filtering for powerful queries

5. **Export filtered results**
   - Download list of paths matching filters
   - JSON export for programmatic processing

6. **Path activity timeline**
   - Visual timeline showing when paths were created/modified
   - Heatmap of writing activity

## References

- **PM Specification**: `/home/user/NaNoWriMo2025/features/allpaths-categorization.md`
- **Current Implementation**: `/home/user/NaNoWriMo2025/formats/allpaths/generator.py`
- **Validation Cache ADR**: `/home/user/NaNoWriMo2025/architecture/002-validation-cache.md`
- **User Documentation**: `/home/user/NaNoWriMo2025/formats/allpaths/README.md`

## Related ADRs

- ADR-001: AllPaths Format for AI Continuity Validation
- ADR-002: Validation Cache Architecture (date fields defined here)
- ADR-004: Content-Based Hashing for Change Detection

## Approval

**Architect**: Ready for Developer implementation
**Date**: 2025-11-23
**Status**: Approved for implementation

---

## Implementation Guidance for Developer

When implementing this design, follow these guidelines:

### Code Organization

1. **Keep changes minimal**
   - Modify existing `generate_html_output()` function (don't create new one)
   - Add helper functions for date formatting and context-specific HTML
   - Keep JavaScript in same file (don't create separate .js)

2. **Maintain backward compatibility**
   - Test PR workflow after changes
   - Verify validation cache structure unchanged
   - Ensure existing scripts continue to work

3. **Follow existing patterns**
   - Date formatting similar to existing date display (line 1246-1258)
   - Filter buttons similar to existing category filters (line 1200-1208)
   - JavaScript filtering similar to existing `filterPaths()` (line 1323-1338)

### Critical Implementation Points

1. **Context detection** (line ~1422)
   - Use exact code from design: `is_pr_context = bool(os.getenv('GITHUB_BASE_REF'))`
   - Pass to `generate_html_output()` as parameter

2. **Data attributes** (line ~1224)
   - Add `data-created-date` and `data-modified-date` to each path div
   - Handle missing dates: use empty string, not null/None

3. **JavaScript date comparison**
   - All dates in UTC (already true from git)
   - Use `Date.getTime()` for numeric comparison
   - Check for "Unknown" before parsing

4. **CSS classes**
   - Add `.context-banner`, `.pr-context`, `.deployment-context` classes
   - Style consistently with existing components

### Testing Checklist

Before submitting:

- [ ] Test with GITHUB_BASE_REF set (PR context)
- [ ] Test with GITHUB_BASE_REF unset (deployment context)
- [ ] Test all four date filters individually
- [ ] Test combining multiple filters
- [ ] Test with missing date metadata
- [ ] Test "Clear Filters" button
- [ ] Verify PR workflow unchanged
- [ ] Check browser console for errors
- [ ] Validate HTML (no broken tags)
- [ ] Test on mobile (responsive design)

### Common Pitfalls to Avoid

1. **Don't break existing PR workflow**
   - Category filters must still work in PR context
   - Categorization logic unchanged

2. **Don't assume dates always present**
   - Check for None/empty before formatting
   - Show "Unknown" gracefully

3. **Don't use local timezone**
   - Keep everything in UTC
   - Label dates with "UTC"

4. **Don't hard-code strings**
   - Use variables for filter labels
   - Keep consistent with PM specification

### Questions or Concerns?

If you encounter any issues during implementation:

1. **Design ambiguity**: Escalate to Architect (me) for clarification
2. **Technical feasibility**: Document why and propose alternative
3. **Performance issues**: Measure and report (target: build <5min, filter <100ms)
4. **Scope creep**: Stay focused on PM specification, defer enhancements

Good luck with implementation!
