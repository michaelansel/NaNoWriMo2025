# Path Categorization Logic Validation

## Design Principles

**Content-Based Categorization:**
- **NEW**: Path contains genuinely new prose content that never appeared before
- **MODIFIED**: Path contains existing prose (may be restructured across different passages)
- **UNCHANGED**: Path contains identical prose delivered through identical structure

## PR #70 Validation: "Updating for Day 20 - delayed light magic"

### What Changed

PR #70 introduced a choice in the "Day 8 KEB" passage:

**Before:**
```twee
:: Day 8 KEB
[prose content...]
"Woah," Terence murmured.
[continued...]
```

**After:**
```twee
:: Day 8 KEB
[prose content...]
Working was [[immediate]] or [[delayed->Day 20 KEB]]

:: Immediate
"Woah," Terence murmured.
[continued...]
```

Plus a new file `KEB-251120.twee` with "Day 20 KEB" passage containing entirely new prose.

### Expected Categorization

1. **Path ending in "immediate"**: Same prose as old path (just split into more passages)
   - Old: Start → ... → Day 8 KEB → [contains "Woah" inline]
   - New: Start → ... → Day 8 KEB → immediate → [same "Woah" text]
   - **Expected: MODIFIED** (same content, restructured)

2. **Path ending in "Day 20 KEB"**: Brand new prose content
   - New: Start → ... → Day 8 KEB → Day 20 KEB → [new prose: "Javlyn opened her eyes..."]
   - **Expected: NEW** (genuinely new content)

### How the Logic Works

```python
# For path through "immediate":
old_content_fingerprint = hash("Day 8 prose + Woah prose")
new_content_fingerprint = hash("Day 8 prose + Woah prose")  # Same!
old_route_hash = hash("Start → ... → Day 8 KEB")
new_route_hash = hash("Start → ... → Day 8 KEB → immediate")  # Different!

# Same content, different route → MODIFIED ✓

# For path through "Day 20 KEB":
new_content_fingerprint = hash("Day 8 prose + Day 20 new prose")
# No matching fingerprint in old cache → NEW ✓
```

## Recent PR Validation

### Day 19 KEB (commits 1b149c7, f757bb2)

- Added new link from Start: `[[Sleep->Day 19 KEB]]`
- Created new file with new prose content
- **Status in cache**: `"category": "new"`
- **Expected**: NEW ✓
- **Reason**: Genuinely new prose content

### Content Edits (Nov 19-20)

Paths marked as "modified" in current cache (e.g., path `a93cb8ed`):
- Route: Start → A rumor → Continue on → No one → Javlyn continued → Day 10 KEB
- Old fingerprint: `7a68c812` (Nov 19)
- New fingerprint: `936b3bf7` (Nov 20)
- **Current status**: "modified" (generated with old logic)
- **With new logic**: Should be "new" (content changed, different prose)

Note: Current cache was generated before the fix, so some paths have incorrect categorization.

## Test Results

Tests updated to match content-based logic:
- **36/37 passing (97.3% success rate)**
- All categorization tests pass
- One unrelated failure in `format_passage_text`

Key test cases:
1. ✓ NEW path (empty cache)
2. ✓ UNCHANGED path (same content, same route)
3. ✓ NEW path (content changed)
4. ✓ MODIFIED path (same content, restructured/renamed passages)
5. ✓ Missing fingerprint field (backward compatibility)

## Validation Summary

The content-based categorization logic correctly identifies:
- ✅ New endings with new prose → **NEW**
- ✅ Restructured passages with same prose → **MODIFIED**
- ✅ Edited prose in existing routes → **NEW**
- ✅ No changes → **UNCHANGED**

This fixes the original issue where new endings were incorrectly marked as "modified" based on structural similarity (>70% passage overlap).
