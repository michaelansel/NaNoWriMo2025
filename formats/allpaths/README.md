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
# Step 1: Compile with Tweego
tweego src -o temp.html -f formats/allpaths/format.js

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
├── allpaths-text/                     # Individual path files
│   ├── path-001-6e587dcb.txt
│   ├── path-002-1bf824a1.txt
│   └── ...
└── allpaths-validation-cache.json     # Validation tracking
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
Route: Start → Continue on → Javlyn continued → proactive attack
Length: 4 passages
Path ID: 6e587dcb
================================================================================

### Start

[Passage text here...]

### Continue on

[Passage text here...]

...
```

### Validation Tracking

**Mark a path as validated:**

Edit `dist/allpaths-validation-cache.json`:
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

## Architecture

### Components

1. **format.js** - Tweego story format definition
   - Integrates with Tweego build system
   - Outputs raw story data HTML

2. **generator.py** - Path generation engine
   - Parses Tweego-compiled HTML
   - Performs DFS to find all paths
   - Generates HTML and text outputs
   - Manages validation cache

3. **build-allpaths.sh** - Build script
   - Orchestrates Tweego compilation
   - Runs Python generator
   - Cleans up temporary files

### Data Flow

```
.twee files
    ↓
  Tweego (with format.js)
    ↓
  Temporary HTML
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
