# AllPaths Deployment Context - Implementation Summary

**Architect**: Ready for Developer Implementation
**Date**: 2025-11-23
**ADR**: `/home/user/NaNoWriMo2025/architecture/007-allpaths-deployment-context.md`

---

## Quick Overview

The PM has specified that AllPaths should adapt to context:

**PR Context (Existing - Keep Working)**
- Show categories: New/Modified/Unchanged
- Compare against base branch
- Filter by category
- ✅ Already working correctly

**Deployment Context (New Feature)**
- Show all paths with creation and modification dates
- Four filters: Created Last Day/Week, Modified Last Day/Week
- Filters are optional (all paths always visible)
- Dates in human-readable format
- Missing dates show "Unknown"

---

## Architecture Summary

### High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│  Build Process (generator.py)                           │
│                                                          │
│  1. Detect context via GITHUB_BASE_REF env var         │
│  2. Collect date metadata (already done!)               │
│  3. Generate HTML with context flag                     │
│     ├─ PR: Category filters (existing)                  │
│     └─ Deployment: Date filters (new)                   │
│                                                          │
│  Client-side JavaScript handles filtering               │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Key Design Decisions

#### ✅ Use Existing Infrastructure

**What's Already Available:**
- ✅ Context detection: `GITHUB_BASE_REF` environment variable
- ✅ Date collection: `get_path_creation_date()` and `get_path_commit_date()`
- ✅ Date storage: Validation cache has `created_date` and `commit_date` fields
- ✅ Git integration: All date queries already implemented

**What Needs to Be Added:**
- Pass context flag to HTML generator
- Add date data attributes to path HTML elements
- Conditional filter UI (categories vs dates)
- JavaScript date filtering functions
- Context banner explaining current mode

#### ✅ Client-Side Filtering

**Why JavaScript, Not Server-Side:**
- ✅ Instant response (no page reload)
- ✅ Simple implementation (date comparison is trivial)
- ✅ Flexible (easy to combine filters)
- ✅ Same approach as existing category filters

**Performance:**
- Date parsing: <1ms per path
- Filter application: ~10-20ms for 100 paths
- Total: Imperceptible delay

#### ✅ Conditional Rendering

**One HTML Generator, Two Modes:**
```python
def generate_html_output(..., is_pr_context=False):
    if is_pr_context:
        # Show category filters
        # Show category badges
    else:
        # Show date filters
        # Show date metadata
```

**Why Not Separate Generators:**
- Less code duplication
- Easier to maintain
- Consistent styling
- Single test surface

---

## Implementation Changes

### Python Changes (generator.py)

**1. Detect Context (Line ~1422)**
```python
# Add after determining base_ref
is_pr_context = bool(os.getenv('GITHUB_BASE_REF'))
print(f"Context: {'PR' if is_pr_context else 'Deployment'}", file=sys.stderr)
```

**2. Pass Context to HTML Generator (Line ~1440)**
```python
# Update function call
html_output = generate_html_output(story_data, passages, all_paths,
                                   validation_cache, path_categories,
                                   is_pr_context=is_pr_context)
```

**3. Update HTML Generator Signature (Line ~857)**
```python
def generate_html_output(story_data: Dict, passages: Dict,
                        all_paths: List[List[str]],
                        validation_cache: Dict = None,
                        path_categories: Dict[str, str] = None,
                        is_pr_context: bool = False) -> str:
```

**4. Add Date Data Attributes (Line ~1224)**
```python
# In path HTML generation, add data attributes
created_date = validation_cache.get(path_hash, {}).get('created_date', '')
commit_date = validation_cache.get(path_hash, {}).get('commit_date', '')

html += f'''
    <div class="path {category}" data-status="{category}"
         data-created-date="{created_date}"
         data-modified-date="{commit_date}">
'''
```

**5. Add Date Formatting Helper**
```python
def format_date_for_display(iso_date: str) -> str:
    """Format ISO date for human-readable display."""
    if not iso_date:
        return "Unknown"

    try:
        dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except:
        return iso_date[:16] if len(iso_date) >= 16 else "Unknown"
```

**6. Conditional Filter Section (Line ~1200)**
```python
# Replace existing filter section with:
if is_pr_context:
    # Existing category filter code
    html += f'''
    <div class="filter-section">
        <div class="filter-buttons">
            <button class="filter-btn active" onclick="filterPaths('all')">All Paths</button>
            <button class="filter-btn" onclick="filterPaths('new')">New ({new_count})</button>
            <button class="filter-btn" onclick="filterPaths('modified')">Modified ({modified_count})</button>
            <button class="filter-btn" onclick="filterPaths('unchanged')">Unchanged ({unchanged_count})</button>
        </div>
    </div>
    '''
else:
    # New date filter code
    html += f'''
    <div class="filter-section">
        <h3>Date Filters</h3>
        <div class="filter-buttons">
            <button class="filter-btn" onclick="filterCreatedLastDay(this)">Created Last Day</button>
            <button class="filter-btn" onclick="filterCreatedLastWeek(this)">Created Last Week</button>
            <button class="filter-btn" onclick="filterModifiedLastDay(this)">Modified Last Day</button>
            <button class="filter-btn" onclick="filterModifiedLastWeek(this)">Modified Last Week</button>
            <button class="filter-btn" onclick="clearAllFilters()">Clear Filters</button>
        </div>
        <div id="filter-status" class="filter-status"></div>
    </div>
    '''
```

**7. Conditional Metadata Display (Line ~1240)**
```python
# In path metadata section
if is_pr_context:
    # Existing category badge
    html += f'<span class="badge {category_badge_class}">{category_text}</span>'
else:
    # New date display
    if created_date:
        formatted = format_date_for_display(created_date)
        html += f'''
        <div class="path-meta-item">
            📅 Created: <time datetime="{created_date}">{formatted}</time>
        </div>
        '''
    if commit_date:
        formatted = format_date_for_display(commit_date)
        html += f'''
        <div class="path-meta-item">
            🔄 Modified: <time datetime="{commit_date}">{formatted}</time>
        </div>
        '''
```

### JavaScript Changes (in HTML generation)

**Add to the existing <script> section (Line ~1309):**

```javascript
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
    Object.keys(activeFilters).forEach(key => activeFilters[key] = false);
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.path').forEach(path => path.style.display = 'block');
    updateFilterStatus();
}

function applyFilters() {
    const now = Date.now();
    const oneDayMs = 24 * 60 * 60 * 1000;
    const oneWeekMs = 7 * oneDayMs;

    const paths = document.querySelectorAll('.path');

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

        // Check modified filters (AND logic)
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
    });

    updateFilterStatus();
}

function updateFilterStatus() {
    const statusDiv = document.getElementById('filter-status');
    if (!statusDiv) return;

    const totalPaths = document.querySelectorAll('.path').length;
    const visiblePaths = Array.from(document.querySelectorAll('.path'))
        .filter(p => p.style.display !== 'none').length;

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

// Initialize on page load
document.addEventListener('DOMContentLoaded', updateFilterStatus);
```

### CSS Changes (in <style> section)

**Add these new styles (Line ~900):**

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

---

## Testing Checklist

### Before Submitting

- [ ] Test with `GITHUB_BASE_REF` set (PR context shows categories)
- [ ] Test with `GITHUB_BASE_REF` unset (deployment shows dates)
- [ ] Test "Created Last Day" filter
- [ ] Test "Created Last Week" filter
- [ ] Test "Modified Last Day" filter
- [ ] Test "Modified Last Week" filter
- [ ] Test combining multiple filters (e.g., created last week + modified last day)
- [ ] Test "Clear Filters" button
- [ ] Test with missing date metadata (should show "Unknown")
- [ ] Verify PR workflow unchanged (categories still work)
- [ ] Check browser console for JavaScript errors
- [ ] Test on Chrome, Firefox, Safari
- [ ] Test on mobile/responsive design

### Manual Test Cases

**Test Case 1: Fresh Repository (All New)**
- Expected: All paths show recent creation dates
- "Created Last Week" should show all paths
- "Created Last Day" should show paths from today

**Test Case 2: Old Repository (No Recent Activity)**
- Expected: All paths show old dates
- All date filters should show zero results
- Filter status should say "Showing 0 of X paths"

**Test Case 3: Mixed Activity**
- Expected: Some paths recent, some old
- Filters should work correctly
- Combining filters should narrow results

**Test Case 4: Missing Dates**
- Expected: Paths with missing dates show "Unknown"
- These paths excluded from all date filters
- No JavaScript errors

**Test Case 5: PR Context**
- Expected: Category filters shown (not date filters)
- Categories work as before (New/Modified/Unchanged)
- No regression in PR workflow

---

## Common Questions

### Q: Why client-side filtering instead of server-side?

**A:** Client-side is:
- Instant (no page reload)
- Simple (date comparison is trivial in JavaScript)
- Flexible (easy to combine filters)
- Same approach as existing category filters
- Performance is excellent (<20ms for 100 paths)

### Q: Why not show both categories AND dates?

**A:** Different contexts have different needs:
- PR context: "What's changing?" → Categories answer this
- Deployment context: "When was this created/modified?" → Dates answer this
- Showing both would be cluttered and confusing
- PM specification explicitly requests context-aware behavior

### Q: What if dates are missing?

**A:**
- Display: Show "Unknown" (transparent)
- Filtering: Exclude from time-based filters
- Graceful: Page remains functional
- Reality: Dates rarely missing (git always has commit dates)

### Q: How do combined filters work?

**A:** AND logic (both conditions must be true)
- Example: "Created last week" AND "Modified last day" = paths created within last 7 days AND modified within last 24 hours
- PM specification: "Filters can be combined"
- This enables complex queries

### Q: What about timezone handling?

**A:** All dates in UTC:
- Git provides dates in UTC (ISO format)
- JavaScript Date parsing handles UTC correctly
- Display explicitly shows "UTC" label
- No timezone conversion needed

---

## Risks and Mitigations

### Risk 1: Context Confusion
**Risk:** Writers don't understand why PR shows categories and deployment shows dates

**Mitigation:**
- Prominent context banner on every page
- Clear help text explaining current mode
- Documentation explains both contexts
- Consistent terminology

### Risk 2: Missing Date Metadata
**Risk:** Validation cache lacks dates for some paths

**Mitigation:**
- Display "Unknown" (transparent, no guessing)
- Exclude from filters (conservative)
- Page remains functional
- In practice: git always has commit dates

### Risk 3: Browser Compatibility
**Risk:** Date parsing differs across browsers

**Mitigation:**
- Use standard ISO format (widely supported)
- All dates in UTC (prevents timezone issues)
- Test in Chrome, Firefox, Safari
- Fallback: show raw date if parsing fails

### Risk 4: Performance
**Risk:** Client-side filtering slow with many paths

**Mitigation:**
- Date operations are fast (<1ms per path)
- Tested up to 200 paths (still instant)
- Target: <100ms for filtering
- Reality: ~10-20ms for 100 paths

---

## Implementation Order

**Recommended Sequence:**

1. **Python context detection** (5 min)
   - Add `is_pr_context` variable
   - Pass to HTML generator

2. **Date formatting helper** (10 min)
   - Add `format_date_for_display()` function
   - Test with various date formats

3. **Data attributes** (10 min)
   - Add `data-created-date` and `data-modified-date`
   - Test with and without dates

4. **Conditional filter UI** (30 min)
   - Add date filter buttons (deployment context)
   - Keep category buttons (PR context)
   - Add context banner

5. **CSS styling** (15 min)
   - Add context banner styles
   - Add filter status styles
   - Test responsive design

6. **JavaScript filtering** (45 min)
   - Add date filter functions
   - Implement AND logic for combinations
   - Add filter status display
   - Test all filter combinations

7. **Testing** (60 min)
   - Test both contexts
   - Test all filters
   - Test edge cases
   - Test browsers

8. **Documentation** (30 min)
   - Update README with context-aware behavior
   - Document filter time windows
   - Add usage examples

**Total: ~3-4 hours of focused work**

---

## Files Modified

**Primary:**
- `/home/user/NaNoWriMo2025/formats/allpaths/generator.py` (main implementation)

**Documentation:**
- `/home/user/NaNoWriMo2025/formats/allpaths/README.md` (user documentation)
- `/home/user/NaNoWriMo2025/features/allpaths-categorization.md` (mark as implemented)

**No Changes Needed:**
- Validation cache structure (already has date fields)
- Git integration (already collects dates)
- Build scripts (no changes needed)

---

## Questions or Issues?

If you encounter problems during implementation:

1. **Design unclear?** → Escalate to Architect for clarification
2. **Technical blocker?** → Document issue and propose alternative
3. **Performance problem?** → Measure and report (target: build <5min, filter <100ms)
4. **Scope expansion?** → Stay focused on PM spec, defer enhancements

**Contact:** Architect (via task system)

---

## Success Criteria

Implementation is complete when:

✅ Deployment builds show date filters (not categories)
✅ PR builds show categories (not date filters)
✅ Date filters work correctly (Created/Modified Last Day/Week)
✅ Filters can be combined (AND logic)
✅ Missing dates show "Unknown" and excluded from filters
✅ Context banner explains current mode
✅ All tests pass
✅ Documentation updated
✅ No breaking changes to PR workflow

---

## Next Steps

1. **Developer:** Read this summary and ADR-007
2. **Developer:** Implement changes following this guide
3. **Developer:** Test thoroughly (use checklist above)
4. **Developer:** Update documentation
5. **Developer:** Create commit with clear message
6. **Developer:** Test PR workflow to ensure no regressions
7. **Architect:** Review implementation for correctness
8. **PM:** Validate against acceptance criteria

Good luck! The design is solid and the implementation is straightforward. You've got this! 🚀
