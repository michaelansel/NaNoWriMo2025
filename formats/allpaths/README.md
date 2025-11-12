# AllPaths Story Format

A Tweego story format that generates all possible story paths for AI-based continuity checking.

## Overview

The AllPaths format uses depth-first search (DFS) to explore the entire story graph and generate every possible path from start to end. This allows you to:

- **Review all story branches** in a single browsable HTML file
- **Feed paths to AI models** for automated continuity checking
- **Track validation status** of each path across builds
- **Identify new paths** that need review after story updates

## Features

### 1. Complete Path Enumeration
- Generates all unique paths from start node to all end nodes
- Handles branching narratives with multiple choices
- Detects and handles cycles (terminates after first visit by default)

### 2. Multiple Output Formats

**HTML Browser (`allpaths.html`)**
- Interactive web interface for browsing all paths
- Collapsible path content
- Filter by validation status (all/new/validated)
- Statistics dashboard showing path counts and lengths
- Visual route diagrams for each path

**Individual Text Files (`allpaths-text/*.txt`)**
- One file per path
- Plain text format perfect for AI processing
- Includes path metadata (route, length, ID)
- Stable filenames with path hash for tracking

**Validation Cache (`allpaths-validation-cache.json`)**
- Tracks all discovered paths with unique IDs
- Records first seen date
- Stores validation status
- Enables incremental checking

### 3. Path Identification
- Each path has a stable MD5-based ID from its route
- Paths maintain the same ID across builds if route doesn't change
- Easy to track which paths have been validated

### 4. Incremental Validation
- Cache persists between builds
- New paths are flagged automatically
- Previously validated paths are marked in the UI
- Avoids re-checking unchanged content

## Usage

### Building AllPaths Output

**Via npm script:**
```bash
npm run build:allpaths
```

**Via shell script:**
```bash
./scripts/build-allpaths.sh
```

**Manual (requires tweego installed):**
```bash
# Step 1: Compile with Tweego (using paperthin format to get story data)
tweego src -o temp.html -f paperthin-1

# Step 2: Generate paths
python3 formats/allpaths/generator.py temp.html dist/

# Step 3: Clean up
rm temp.html
```

### Output Files

After building, you'll find:

```
dist/
├── allpaths.html                      # Browse all paths in browser
├── allpaths-text/                     # Individual path files (with random IDs)
│   ├── path-001-6e587dcb.txt
│   ├── path-002-1bf824a1.txt
│   └── ...
├── allpaths-passage-mapping.json      # Maps random IDs back to passage names
└── allpaths-validation-cache.json     # Validation tracking (at repository root)
```

### Browsing Paths

Open `dist/allpaths.html` in a web browser to:

1. **View statistics** - See total paths, lengths, new vs validated
2. **Filter paths** - Show all, only new, or only validated paths
3. **Browse paths** - Click "Show Content" to read each path
4. **Track routes** - See the exact sequence of passages in each path

### AI Continuity Checking

The text files in `allpaths-text/` are formatted for AI processing:

**Example workflow:**
```bash
# Process all paths with an AI model
for path in dist/allpaths-text/*.txt; do
    echo "Checking: $path"
    # Send to AI model for continuity analysis
    ai-model check-continuity "$path" > "${path}.report"
done
```

**Text file format:**
```
================================================================================
PATH 1 of 11
================================================================================
Route: a1b2c3d4e5f6 → 9f8e7d6c5b4a → 1234567890ab → fedcba098765
Length: 4 passages
Path ID: 6e587dcb
================================================================================

[PASSAGE: a1b2c3d4e5f6]

[Passage text here...]

[PASSAGE: 9f8e7d6c5b4a]

[Passage text here with selected choice visible]
[other choice] (not selected)

...
```

**Important notes about the format:**
- **Random IDs for AI processing**: Passage names are replaced with random hex IDs (e.g., `a1b2c3d4e5f6`)
- This prevents the AI from being confused by passage names like "Day 5 KEB" which players never see
- The IDs are meaningless random identifiers with zero semantic content
- Only the selected choice in each passage is shown as visible text
- Other choices are marked with `(not selected)` to indicate they weren't taken in this path
- The mapping from IDs back to passage names is saved in `allpaths-passage-mapping.json`
- This ensures continuity checking focuses only on what players actually experience

### Validation Tracking

**Mark a path as validated:**

Edit `allpaths-validation-cache.json`:
```json
{
  "6e587dcb": {
    "route": "Start → Continue on → ...",
    "first_seen": "2025-11-10T07:06:05.514940",
    "validated": true  // Change this to true
  }
}
```

On the next build, validated paths will:
- Appear with a green "Validated" badge
- Have a green left border
- Be filterable via "Validated Only" button

**Clearing the validation cache:**

If the text generation format changes (e.g., how passages or choices are displayed), you should clear the validation cache to get fresh AI analysis:
```bash
rm allpaths-validation-cache.json
```

This will mark all paths as "new" and they will be re-checked with the updated format.

**Understanding the Passage Mapping:**

The `allpaths-passage-mapping.json` file contains a bidirectional mapping:
```json
{
  "name_to_id": {
    "Start": "a1b2c3d4e5f6",
    "Day 5 KEB": "9f8e7d6c5b4a",
    "Continue on": "1234567890ab"
  },
  "id_to_name": {
    "a1b2c3d4e5f6": "Start",
    "9f8e7d6c5b4a": "Day 5 KEB",
    "1234567890ab": "Continue on"
  }
}
```

The continuity checker automatically:
1. Loads this mapping file
2. Receives AI results with random IDs
3. Translates IDs back to passage names before reporting
4. Ensures human-readable output even though AI sees only random IDs

This prevents the AI from being confused by passage names that contain timeline markers, character names, or other semantic information that isn't visible to players.

## Architecture

### Components

1. **generator.py** - Path generation engine
   - Parses Tweego-compiled HTML
   - Performs DFS to find all paths
   - Generates HTML and text outputs
   - Manages validation cache

2. **build-allpaths.sh** - Build script
   - Orchestrates Tweego compilation (using paperthin format)
   - Runs Python generator
   - Cleans up temporary files

### Data Flow

```
.twee files
    ↓
  Tweego (paperthin format)
    ↓
  Temporary HTML (with story data)
    ↓
  generator.py
    ↓
  ┌─────────────┬──────────────────┬────────────────────┐
  ↓             ↓                  ↓                    ↓
allpaths.html  allpaths-text/  validation-cache.json
```

### Algorithm

**Depth-First Search (DFS):**
1. Start at the beginning passage (usually "Start")
2. For each outgoing link:
   - If passage has been visited before, skip (avoid cycles)
   - Otherwise, recursively explore that path
3. When a passage with no links is reached, record the complete path
4. Backtrack and explore other branches
5. Return all unique paths found

**Time Complexity:** O(V + E) where V = passages, E = links
**Space Complexity:** O(V) for the recursion stack

### Path Identification

Paths are identified by MD5 hash of their route:
- Route: `Start → Continue on → Javlyn continued → Attack`
- Hash: `6e587dcb` (first 8 chars of MD5)
- Filename: `path-001-6e587dcb.txt`

This ensures:
- Same path = same ID across builds
- Easy tracking of which paths are new
- Stable references for validation tracking

## Configuration

### Cycle Handling

By default, the generator stops at cycles (max_cycles=1 in `generator.py`). To allow cycles:

Edit `formats/allpaths/generator.py`:
```python
# Line ~92
all_paths = generate_all_paths_dfs(graph, start_passage, max_cycles=2)
```

⚠️ **Warning:** Allowing cycles can cause exponential growth in path count!

### Custom Start Passage

The generator automatically detects the start passage from `StoryData`. To override:

Edit `formats/allpaths/generator.py`:
```python
# Line ~88
start_passage = 'YourCustomStart'
```

## Integration

### GitHub Actions

The format is integrated into `.github/workflows/build-and-deploy.yml`:

```yaml
- name: Build AllPaths version (AI continuity checking)
  run: |
    chmod +x scripts/build-allpaths.sh
    ./scripts/build-allpaths.sh
```

### npm Scripts

Added to `package.json`:

```json
{
  "scripts": {
    "build": "... && npm run build:allpaths",
    "build:allpaths": "./scripts/build-allpaths.sh"
  }
}
```

## Troubleshooting

### "tweego not found"
Install Tweego first:
```bash
# Download from https://github.com/tmedwards/tweego/releases
wget https://github.com/tmedwards/tweego/releases/download/v2.1.1/tweego-2.1.1-linux-x64.zip
unzip tweego-2.1.1-linux-x64.zip
sudo mv tweego /usr/local/bin/
```

### "python3 not found"
Install Python 3:
```bash
# Ubuntu/Debian
sudo apt-get install python3

# macOS
brew install python3
```

### No paths generated
Check that:
1. Your story has a "Start" passage (or matches the start node in StoryData)
2. Your passages have links using `[[...]]` syntax
3. There's at least one path from start to an end node

### Too many paths
If you have exponential paths:
1. Review your story structure for unintended loops
2. Consider breaking the story into chapters
3. Check for passages that link back to earlier passages

## Examples

### Current Story Stats
```
Total passages: 21
Total paths: 11
Shortest path: 2 passages
Longest path: 7 passages
Average length: 5.2 passages
```

### Sample Path
```
Route: Start → Continue on → Javlyn continued →
       proactive attack → Find the lantern → Check the creature

This path represents the player choosing to:
1. Continue immediately (not delay)
2. Enter the cave
3. Attack the monster proactively
4. Find the lantern in the dark
5. Check the creature's body
```

## Future Enhancements

Possible additions:
- [ ] JSON output format for programmatic access
- [ ] Diff mode to show what changed between builds
- [ ] Path comparison tool
- [ ] AI integration examples
- [ ] Custom validators/linters
- [ ] Watch mode for continuous generation
- [ ] Integration with LLM APIs for automated checking

## License

Part of the NaNoWriMo2025 project.

## Contributing

See the main project README for contribution guidelines.
