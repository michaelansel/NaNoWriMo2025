# Path ID Display Feature

## Overview

The Path ID Display feature automatically shows a unique identifier for each story path when readers reach an ending. This helps with:

- **Bug reporting**: Readers can report which specific path they took
- **Analytics**: Track which endings readers reach
- **Testing**: Identify specific paths during QA

## How It Works

### Build Time (Precomputation)

1. **Story Graph Generation** (`build:core`)
   - Parses all `.twee` files to build story structure
   - Identifies all passages and their links
   - Outputs `lib/artifacts/story_graph.json`

2. **Path Generation** (`generate-path-lookup.py`)
   - Uses depth-first search to enumerate all possible paths
   - Calculates unique 8-character hash for each path
   - Creates lookup table: `"Start→Middle→End"` → `"abc12345"`
   - Generates `src/PathIdLookup.twee` with embedded JavaScript

3. **Story Compilation** (`build:main`)
   - Tweego compiles all `.twee` files including `PathIdLookup.twee`
   - Path ID lookup table is embedded in the final HTML
   - `PathIdDisplay.twee` footer is included on all passages

### Runtime (Player Experience)

1. **During Play**
   - Harlowe tracks which passages the player visits using `(history:)`
   - No path ID computation happens during play

2. **At Endings**
   - `PathIdDisplay.twee` footer checks if current passage has outgoing links
   - If no links (ending), JavaScript runs:
     - Reads Harlowe's `(history:)` output from a hidden DOM element
     - Joins passage names with `→` to create lookup key
     - Looks up path ID in `window.pathIdLookup`
     - Displays: "Path ID: abc12345"

## File Structure

```
formats/allpaths/modules/
├── path_generator.py          # DFS path generation
├── path_id_lookup.py          # NEW: Lookup table generation
└── test_path_id_lookup.py     # NEW: Tests for lookup generation

scripts/
├── generate-path-lookup.py    # NEW: Main script to generate lookup
├── test_generate_path_lookup.py  # NEW: Integration tests
└── build-core.sh              # MODIFIED: Added Step 5/5 for lookup generation

src/
├── PathIdLookup.twee          # GENERATED: JavaScript lookup table
└── PathIdDisplay.twee         # NEW: Footer that displays path ID at endings
```

## Example

### Story Structure

```twee
:: Start
Choose your path:
[[Go left->Left]]
[[Go right->Right]]

:: Left
You went left.
[[End1]]

:: Right
You went right.
[[End2]]

:: End1
Left ending. (no outgoing links)

:: End2
Right ending. (no outgoing links)
```

### Generated Lookup (PathIdLookup.twee)

```javascript
window.pathIdLookup = {
  "Start→Left→End1": "a1b2c3d4",
  "Start→Right→End2": "e5f6g7h8"
};

window.getPathId = function(history) {
  var route = history.join('→');
  return window.pathIdLookup[route] || 'unknown';
};
```

### Player Experience

When a player reaches `End1`, they see:

```
Left ending.

────────────────────
Path ID: a1b2c3d4
```

## Technical Details

### Path ID Calculation

Path IDs are 8-character MD5 hashes of:
- Passage names in the path
- Content of each passage

This means the ID changes when:
- Path structure changes (added/removed passages)
- Passage names change
- Passage content changes

### Ending Detection

A passage is an "ending" if:
- It has zero outgoing links
- `(passage:)'s links's length` equals 0

The `PathIdDisplay.twee` footer uses Harlowe's `(if: not $hasLinks)` to only display on endings.

### Harlowe History Bridge

Harlowe doesn't expose a JavaScript API, so we use a DOM bridge:

1. Harlowe's `(history:)` macro outputs visited passage names
2. `(text: ...(history:))` converts the array to comma-separated text
3. Text is placed in a hidden `<span>` element
4. JavaScript reads and parses the text to reconstruct the history array

```twee
<!-- In PathIdDisplay.twee -->
<span id="harlowe-history-data" style="display:none">(text: ...(history:))</span>
```

```javascript
// JavaScript reads from the hidden element
var historyText = document.getElementById('harlowe-history-data').textContent;
var history = historyText.split(', ');  // ["Start", "Left", "End1"]
```

## Maintenance

### Adding New Passages

When you add new passages:

1. Edit `.twee` files as normal
2. Run `npm run build` (or `npm run build:core`)
3. Path lookup is automatically regenerated

### Debugging

If path IDs don't appear or show incorrectly:

1. **Check lookup generation**: `cat src/PathIdLookup.twee`
   - Should contain `window.pathIdLookup` with many entries
   - Should have entries matching your story paths

2. **Check history element**: Open browser console at an ending, type:
   ```javascript
   document.getElementById('harlowe-history-data').textContent
   ```
   - Should show comma-separated passage names like "Start, Left, End1"

3. **Check lookup key**: In browser console:
   ```javascript
   var h = document.getElementById('harlowe-history-data').textContent;
   var route = h.split(', ').join('→');
   console.log(route, window.pathIdLookup[route]);
   ```
   - Should show the route and its path ID

4. **Check for mismatches**: Compare history to lookup keys
   - Passage names must match exactly
   - Arrow character must be `→` (U+2192) not `->` (ASCII)

## Testing

```bash
# Test path ID lookup generation
python3 -m pytest formats/allpaths/modules/test_path_id_lookup.py -v

# Test script integration
python3 -m pytest scripts/test_generate_path_lookup.py -v

# Full build test (requires tweego)
npm run build:core
cat src/PathIdLookup.twee  # Verify generated lookup
```

## Performance

### Build Time
- Path generation: O(paths × passages)
- For typical stories (100 passages, 1000 paths): < 1 second
- Lookup generation: O(paths)
- Total overhead: negligible

### Runtime
- Lookup: O(1) hash table access
- Display: Only at endings (minimal impact)
- JavaScript overhead: < 100 KB for typical stories

## Future Enhancements

Potential improvements:

1. **Compressed lookup**: Use shorter keys (remove passage names)
2. **Path metadata**: Include path length, difficulty rating
3. **Analytics integration**: Send path IDs to analytics service
4. **Copy button**: Let players easily copy their path ID
5. **QR code**: Generate QR code of path ID for mobile sharing

## References

- [Harlowe (history:) documentation](https://twine2.neocities.org/)
- [Path generation algorithm](../formats/allpaths/modules/path_generator.py)
- [Build pipeline](../scripts/build-core.sh)
