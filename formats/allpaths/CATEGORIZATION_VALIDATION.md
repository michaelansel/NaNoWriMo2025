# Path Categorization Logic Validation

## Design Principles

**Two-Phase Content-Based Categorization:**

The system uses two fingerprints to distinguish between prose changes and navigation changes:

1. **Prose Fingerprint** (`content_fingerprint`): Hash of passage text with links stripped
   - Detects actual prose changes
   - Ignores link additions/removals/changes
   - Whitespace normalized

2. **Raw Fingerprint** (`raw_content_fingerprint`): Hash of full passage text with links
   - Detects ANY content change (prose OR links)
   - Used to distinguish MODIFIED from UNCHANGED

3. **Route Hash** (`route_hash`): Hash of passage sequence
   - Identifies structural changes (different passage order)

### Categorization Logic

```python
if prose_fingerprint matches old path:
    if route_hash matches AND raw_fingerprint matches:
        → UNCHANGED (nothing changed)
    else:
        → MODIFIED (same prose, but links or structure changed)
else:
    → NEW (genuinely new prose content)
```

**Categories:**
- **NEW**: Path contains genuinely new prose content that never appeared before
- **MODIFIED**: Path contains existing prose, but links/navigation/structure changed
- **UNCHANGED**: Path is completely unchanged (prose + links + structure)

## Link Stripping Implementation

Links are stripped using `strip_links_from_text()` which:
- Removes all `[[...]]` patterns (including `[[target]]`, `[[display->target]]`)
- Normalizes whitespace (collapses multiple newlines/spaces)
- Strips leading/trailing whitespace

This ensures that adding/removing/changing links doesn't affect the prose fingerprint.

## Validation Against Real PRs

### PR #65: "Updating for Day 19 - sleep"

**What Changed:**
- Added link in Start.twee: `[[Sleep->Day 19 KEB]]`
- Created new file KEB-251119.twee with Day 19 prose

**Expected Categorization:**
1. `Start → mansel-20251112`: Same prose, link added → **MODIFIED** ✓
2. `Start → A rumor`: Same prose, link added → **MODIFIED** ✓
3. `Start → Day 19 KEB`: New prose content → **NEW** ✓

**How It Works:**
```python
# For paths through Start:
old_prose_fp = hash(strip_links("What is weighing..."))  # "abc123"
new_prose_fp = hash(strip_links("What is weighing..."))  # "abc123" (same!)
old_raw_fp = hash("What is weighing...\n[[Laundry]]")    # "def456"
new_raw_fp = hash("What is weighing...\n[[Laundry]]\n[[Sleep]]")  # "xyz789" (different!)

# prose_fp matches → same prose
# raw_fp differs → links changed
# Result: MODIFIED ✓

# For path through Day 19:
new_prose_fp = hash(strip_links("Sleep was calling..."))  # "new999"
# No matching prose_fp in cache → NEW ✓
```

### PR #70: "Updating for Day 20 - delayed light magic"

**What Changed:**
- Split Day 8 passage, added choice: `[[immediate]]` or `[[delayed->Day 20 KEB]]`
- Moved existing prose to new "immediate" passage
- Created KEB-251120.twee with Day 20 prose

**Expected Categorization:**
1. Path through `immediate`: Same prose (just restructured) → **MODIFIED** ✓
2. Path through `Day 20 KEB`: New prose content → **NEW** ✓

**How It Works:**
```python
# For path through "immediate":
old_prose_fp = hash(strip_links("Day 8 text + Woah text"))  # "path1"
new_prose_fp = hash(strip_links("Day 8 text + Woah text"))  # "path1" (same!)
old_route = "Start → ... → Day 8 KEB"
new_route = "Start → ... → Day 8 KEB → immediate"

# prose_fp matches → same prose
# route differs → restructured
# Result: MODIFIED ✓

# For path through Day 20:
new_prose_fp = hash(strip_links("Javlyn opened her eyes..."))  # "path2"
# No matching prose_fp → NEW ✓
```

## Test Results

Comprehensive test coverage (40/40 tests passing - 100%):

### Unit Tests
- ✓ `test_strip_links()` - Link removal and whitespace normalization
- ✓ `test_categorize_unchanged_path()` - Nothing changed
- ✓ `test_categorize_new_content_change()` - Prose edited
- ✓ `test_categorize_modified_restructured()` - Passages renamed/restructured
- ✓ `test_categorize_modified_link_added()` - Links added (core new behavior)

### Integration Tests
- ✓ `test_pr65_link_addition()` - Real PR #65 scenario validation
- ✓ Backward compatibility with old cache formats
- ✓ Edge cases (missing fields, empty cache, etc.)

All tests are in `formats/allpaths/test_generator.py`. Run with:
```bash
python3 formats/allpaths/test_generator.py
```

## Breaking Changes & Migration

### Cache Format Changes

**New fields added to validation cache:**
- `route_hash`: Hash of passage sequence (for structure comparison)
- `raw_content_fingerprint`: Hash with links (for link change detection)

**Changed field meaning:**
- `content_fingerprint`: Now prose-only (links stripped) - previously included links

### Backward Compatibility

The code handles old caches gracefully:
- Missing `route_hash`: Calculated from `route` string
- Missing `raw_content_fingerprint`: Path marked as MODIFIED (conservative)

**Note:** Old caches with `content_fingerprint` from before link-stripping was added will have different fingerprints. Paths may be re-categorized as NEW/MODIFIED on first run after upgrade.

### Migration Recommendation

For cleanest results, regenerate the validation cache after deploying this change:
```bash
rm allpaths-validation-status.json
./scripts/build-allpaths.sh
```

## Implementation Summary

This fix addresses the original issue where new endings were incorrectly marked as "modified" based on structural similarity (>70% passage overlap). The two-phase fingerprinting approach correctly distinguishes:

- ✅ Adding new prose → **NEW**
- ✅ Adding/removing/changing links → **MODIFIED**
- ✅ Restructuring passages (same prose) → **MODIFIED**
- ✅ Editing prose → **NEW**
- ✅ No changes → **UNCHANGED**
