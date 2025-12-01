# Architecture Design: Writing Metrics & Statistics

**Status:** Approved
**Date:** 2025-11-28
**Related PRD:** `features/writing-metrics.md`

---

## Overview

Writing Metrics provides word count statistics in two output formats: command-line interface (CLI) for active writing sessions, and HTML for persistent viewing via GitHub Pages. The feature analyzes Twee source files to compute word counts, passage statistics, file statistics, distributions, and identify top passages.

**Design Principles Applied:**
- **Separation of Concerns:** Core logic (Python), build orchestration (shell), output rendering (templates)
- **Single Source of Truth:** One Python script serves both CLI and HTML outputs
- **Consistency with Existing Patterns:** Follows AllPaths architecture (scripts/ + formats/)
- **Progressive Enhancement:** CLI works independently; HTML is an additional view

---

## System Components

### 1. Core Word Counter (`scripts/calculate-metrics.py`)

**Purpose:** Analyze Twee files and compute word count statistics

**Responsibilities:**
- Read Twee files from `src/` directory
- Filter files by prefix (`--include`, `--exclude`)
- Strip Harlowe syntax, links, HTML tags, passage headers
- Count prose words only
- Compute statistics (min, mean, median, max)
- Generate distribution buckets
- Identify top N longest passages
- Output results as text (CLI) or JSON (HTML generation)

**Key Functions:**
```python
def strip_harlowe_syntax(text: str) -> str:
    """Remove Harlowe macros, link markup, HTML tags from text."""

def count_words(text: str) -> int:
    """Count words in cleaned prose text."""

def parse_twee_file(file_path: Path) -> List[Passage]:
    """Extract passages from a Twee file."""

def calculate_passage_statistics(passages: List[Passage]) -> Dict:
    """Compute min/mean/median/max for passages."""

def calculate_file_statistics(files: List[TweeFile]) -> Dict:
    """Compute min/mean/median/max for files."""

def generate_distribution(values: List[int], buckets: List[Tuple]) -> Dict:
    """Bucket values into ranges for distribution."""

def filter_files(files: List[Path], include: List[str], exclude: List[str]) -> List[Path]:
    """Apply prefix filtering to file list."""

def format_text_output(metrics: Dict) -> str:
    """Format metrics as human-readable text for CLI."""

def format_json_output(metrics: Dict) -> str:
    """Format metrics as JSON for HTML generation."""
```

**Algorithm: Word Counting**

```
Input: Twee file text
Process:
  1. Split by passage headers (:: PassageName)
  2. For each passage:
     a. Remove Harlowe macros: (set:...), (if:...), (link:...), etc.
     b. Remove link syntax: [[Display->Target]] → "Display"
     c. Remove HTML tags: <div>, </div>, etc.
     d. Remove passage metadata (tags in square brackets)
     e. Split by whitespace, count tokens
  3. Aggregate word counts per passage and per file
Output: List of passages with word counts
```

**Regex Patterns:**
```python
# Harlowe macros: (macro-name: args)
HARLOWE_MACRO = r'\([a-z\-]+:.*?\)'

# Links: [[Display->Target]] or [[Target]]
HARLOWE_LINK_WITH_DISPLAY = r'\[\[(.+?)->(.+?)\]\]'  # capture display text
HARLOWE_LINK_SIMPLE = r'\[\[(.+?)\]\]'  # capture target as display

# HTML tags
HTML_TAG = r'<[^>]+>'

# Passage header: :: Name [tags]
PASSAGE_HEADER = r'^::\s+.*$'
```

---

### 2. Build Script (`scripts/build-metrics.sh`)

**Purpose:** Orchestrate metrics generation for both CLI and HTML

**Responsibilities:**
- Invoke Python script to generate metrics JSON
- Render HTML using Jinja2 template
- Place HTML in `dist/metrics.html`
- Provide clear progress messages
- Handle errors gracefully

**Script Structure:**
```bash
#!/bin/bash
# Build Writing Metrics & Statistics
# Generates metrics.html for GitHub Pages deployment

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
METRICS_SCRIPT="$SCRIPT_DIR/calculate-metrics.py"

mkdir -p "$DIST_DIR"

echo "=== Building Writing Metrics ==="

# Step 1: Generate metrics JSON
echo "[1/2] Calculating metrics..."
METRICS_JSON=$(python3 "$METRICS_SCRIPT" --json)

# Step 2: Render HTML template
echo "[2/2] Generating HTML..."
python3 -c "
from jinja2 import Template
import json
import sys

metrics = json.loads('''$METRICS_JSON''')
template = Template(open('$PROJECT_DIR/formats/metrics/template.html.jinja2').read())
html = template.render(metrics=metrics)
sys.stdout.write(html)
" > "$DIST_DIR/metrics.html"

echo "✓ Metrics generated: $DIST_DIR/metrics.html"
echo "=== Build Complete ==="
```

**Alternative Simpler Approach:**
- Python script generates HTML directly (no separate templating step)
- Inline HTML generation in `calculate-metrics.py` with `--html` flag
- Trade-off: Simpler build, but HTML embedded in Python

---

### 3. HTML Template (`formats/metrics/template.html.jinja2`)

**Purpose:** Render metrics as HTML for browser viewing

**Template Structure:**
```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Writing Metrics - {{ story_name }}</title>
    <style>
        /* Similar styling to AllPaths template */
        /* Clean, modern CSS with good readability */
    </style>
</head>
<body>
    <div class="header">
        <h1>Writing Metrics & Statistics</h1>
        <p class="subtitle">{{ story_name }}</p>
    </div>

    <div class="stats">
        <h2>Word Count Summary</h2>
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-label">Total Words</div>
                <div class="stat-value">{{ metrics.total_words | format_number }}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Files Analyzed</div>
                <div class="stat-value">{{ metrics.file_count }}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Passages</div>
                <div class="stat-value">{{ metrics.passage_count }}</div>
            </div>
        </div>
    </div>

    <div class="stats">
        <h2>Passage Statistics</h2>
        <table class="stats-table">
            <tr>
                <th>Metric</th>
                <th>Value</th>
            </tr>
            <tr>
                <td>Minimum</td>
                <td>{{ metrics.passage_stats.min }} words</td>
            </tr>
            <tr>
                <td>Mean</td>
                <td>{{ metrics.passage_stats.mean | round(1) }} words</td>
            </tr>
            <tr>
                <td>Median</td>
                <td>{{ metrics.passage_stats.median | round(1) }} words</td>
            </tr>
            <tr>
                <td>Maximum</td>
                <td>{{ metrics.passage_stats.max }} words</td>
            </tr>
        </table>
    </div>

    <!-- Similar sections for File Statistics, Distribution, Top Passages -->

</body>
</html>
```

**Design Notes:**
- Follow AllPaths template styling (consistent look)
- Responsive design (works on mobile)
- No JavaScript required (static display)
- Clear section headers and readable formatting

---

### 4. CLI Wrapper (Optional)

**Purpose:** Provide convenient CLI access via npm/make

**Implementation:**
```bash
# In package.json:
"scripts": {
  "metrics": "python3 scripts/calculate-metrics.py"
}

# Usage:
npm run metrics
npm run metrics -- --include KEB
npm run metrics -- --top 10
```

**Alternative: Makefile target** (if Makefile is added later):
```makefile
.PHONY: metrics
metrics:
    @python3 scripts/calculate-metrics.py

.PHONY: metrics-json
metrics-json:
    @python3 scripts/calculate-metrics.py --json
```

---

## Data Flow

### CLI Workflow

```
User runs: npm run metrics --include KEB
    ↓
npm executes: python3 scripts/calculate-metrics.py --include KEB
    ↓
Python script:
  1. Scan src/ for *.twee files
  2. Filter to KEB-*.twee
  3. Parse each file, extract passages
  4. Strip Harlowe syntax from prose
  5. Count words per passage
  6. Compute statistics
  7. Format as text
    ↓
Output printed to stdout
```

### HTML Build Workflow

```
User runs: npm run build (or npm run build:metrics)
    ↓
npm executes: ./scripts/build-metrics.sh
    ↓
build-metrics.sh:
  1. Run calculate-metrics.py --json
  2. Capture JSON output
  3. Render Jinja2 template with JSON data
  4. Write dist/metrics.html
    ↓
File available at dist/metrics.html
    ↓
Deployed to GitHub Pages (make deploy)
    ↓
Accessible at: https://username.github.io/NaNoWriMo2025/metrics.html
```

---

## File Structure

```
NaNoWriMo2025/
├── scripts/
│   ├── calculate-metrics.py        # Core metrics calculation (NEW)
│   ├── build-metrics.sh            # HTML build orchestration (NEW)
│   ├── build-allpaths.sh           # Existing
│   └── generate-resources.sh       # Existing
├── formats/
│   ├── allpaths/                   # Existing
│   └── metrics/                    # NEW
│       ├── template.html.jinja2    # HTML template
│       └── README.md               # Format documentation
├── dist/
│   ├── index.html                  # Harlowe story (existing)
│   ├── proofread.html              # Paperthin (existing)
│   ├── allpaths.html               # AllPaths (existing)
│   └── metrics.html                # Writing Metrics (NEW)
├── features/
│   └── writing-metrics.md          # PRD (existing)
├── architecture/
│   └── 009-writing-metrics-design.md  # This document (NEW)
└── package.json                    # Updated with build:metrics script
```

---

## Build Integration

### package.json Changes

```json
{
  "scripts": {
    "build": "npm run build:main && npm run build:proofread && npm run build:allpaths && npm run build:metrics",
    "build:main": "tweego src -o dist/index.html --format=harlowe-3.3.9",
    "build:proofread": "tweego src -o dist/proofread.html --format=paperthin-1.0.0",
    "build:allpaths": "./scripts/build-allpaths.sh",
    "build:metrics": "./scripts/build-metrics.sh",
    "metrics": "python3 scripts/calculate-metrics.py"
  }
}
```

**Changes:**
- Add `build:metrics` target (generates HTML)
- Add `metrics` target (CLI usage)
- Update `build` to include `build:metrics`

**Deployment:**
- `npm run build` generates all formats including metrics.html
- GitHub Pages deployment includes metrics.html automatically
- Accessible at `/metrics.html` alongside other formats

---

## Implementation Details

### Word Counting Rules

**Include:**
- Prose text visible to players
- Dialogue and narration
- Text within link display syntax

**Exclude:**
- Harlowe macros: `(set: $var to value)`, `(if: condition)[...]`, etc.
- Link targets: `[[Display->Target]]` counts "Display" only
- HTML tags: `<div>`, `<span>`, `<em>`, etc.
- Passage headers: `:: PassageName [tags]`
- Metadata lines

**Special Files (Always Excluded):**
- `src/StoryData.twee`
- `src/StoryTitle.twee`
- `src/StoryStyles.twee`

### Statistics Algorithms

**Mean:**
```python
mean = sum(word_counts) / len(word_counts)
```

**Median:**
```python
sorted_counts = sorted(word_counts)
n = len(sorted_counts)
if n % 2 == 0:
    median = (sorted_counts[n//2 - 1] + sorted_counts[n//2]) / 2
else:
    median = sorted_counts[n//2]
```

**Distribution Buckets:**
```python
buckets = [
    (0, 100, "0-100"),
    (101, 300, "101-300"),
    (301, 500, "301-500"),
    (501, 1000, "501-1000"),
    (1001, float('inf'), "1000+")
]
```

### Filter Implementation

**Prefix Matching:**
```python
def matches_prefix(filename: str, prefix: str) -> bool:
    """Check if filename starts with prefix (case-insensitive)."""
    return filename.lower().startswith(prefix.lower())

def filter_files(files: List[Path], include: List[str], exclude: List[str]) -> List[Path]:
    """
    Apply include/exclude filters to file list.

    Logic:
    1. If include specified: keep only files matching any include prefix
    2. Apply exclude: remove files matching any exclude prefix
    3. Return filtered list
    """
    if include:
        files = [f for f in files if any(matches_prefix(f.name, p) for p in include)]
    if exclude:
        files = [f for f in files if not any(matches_prefix(f.name, p) for p in exclude)]
    return files
```

---

## Testing Strategy

### Unit Testing (Future)

```python
# tests/test_word_counting.py
def test_strip_harlowe_macros():
    text = "Hello (set: $foo to 5) world"
    assert strip_harlowe_syntax(text) == "Hello  world"

def test_strip_links():
    text = "Click [[here->Target]] to continue"
    assert strip_harlowe_syntax(text) == "Click here to continue"

def test_count_words():
    text = "This is a test"
    assert count_words(text) == 4

def test_median_even_count():
    values = [1, 2, 3, 4]
    assert calculate_median(values) == 2.5

def test_median_odd_count():
    values = [1, 2, 3]
    assert calculate_median(values) == 2
```

### Manual Testing

**Test Cases:**
1. **Empty repository:** No story files → 0 words, clear message
2. **Single file:** Start.twee only → statistics computed correctly
3. **Filtered to nothing:** `--include NOTEXIST` → clear error message
4. **Large story:** All files → completes in <5 seconds
5. **HTML generation:** Build succeeds, metrics.html accessible
6. **CLI flags:** `--include KEB` filters correctly
7. **Top passages:** `--top 10` shows 10 longest passages

### Integration Testing

**Build Pipeline:**
```bash
# Clean build
npm run clean
npm run build

# Verify outputs
test -f dist/metrics.html || echo "FAIL: metrics.html not generated"
test -s dist/metrics.html || echo "FAIL: metrics.html is empty"

# Verify CLI
npm run metrics | grep "Total Words" || echo "FAIL: CLI output missing"
```

---

## Performance Considerations

### Expected Performance

**Target:** <5 seconds for metrics calculation and HTML generation

**Time Complexity:**
- File reading: O(n) where n = number of files
- Parsing: O(m) where m = total file size
- Statistics: O(p log p) where p = number of passages (for sorting/median)
- Total: O(n + m + p log p)

**Current Story Size:**
- ~35 files
- ~54 passages
- Expected: <1 second for metrics calculation

**Optimizations:**
- No need for optimization at current scale
- Future: Consider caching if file count exceeds 100

---

## Security Considerations

**Input Validation:**
- File paths: Restrict to `src/` directory only
- Filters: Validate prefix patterns (no path traversal)
- No code execution from Twee content

**Output Sanitization:**
- HTML output: Escape passage names and file names
- Prevent XSS from malicious passage names

**Dependencies:**
- Python standard library (no external deps for core)
- Jinja2 for templating (already used by AllPaths)

---

## Future Enhancements

### Core Library Integration

**Note**: The current implementation parses Twee files directly. Future enhancement will consume `story_graph.json` from the core library (see ADR-012):

- **Current**: Parses Twee files, strips Harlowe syntax, counts words
- **Future**: Consume `story_graph.json` which already has clean passage content
- **Benefits**: Eliminate duplication of parsing logic, consistent story structure handling
- **Migration**: Low priority (current implementation works well for metrics use case)

### Potential Additions (Out of Scope for Initial Implementation)

1. **Historical Tracking:** Compare metrics over time (requires git integration)
2. **Trend Visualization:** Charts showing writing patterns (requires charting library)
3. **Author Attribution:** Per-author statistics (requires metadata tracking)
4. **Reading Time Estimates:** Based on word count (requires reading speed assumptions)
5. **Complexity Metrics:** Flesch-Kincaid, sentence length (requires NLP)

These are **explicitly out of scope** for the initial implementation. Focus is on basic word counting and statistics.

---

## Success Criteria

**Functional:**
- [ ] CLI command produces accurate word counts
- [ ] HTML generated on every build
- [ ] Statistics match manual verification
- [ ] Filters work correctly (CLI)
- [ ] Edge cases handled gracefully

**Non-Functional:**
- [ ] Metrics calculation completes in <5 seconds
- [ ] HTML is readable and well-formatted
- [ ] Code follows STANDARDS.md conventions
- [ ] Documentation is complete

**Integration:**
- [ ] Integrated into `npm run build`
- [ ] Deployed to GitHub Pages automatically
- [ ] No impact on other build formats

---

## Open Questions

None. Design is ready for implementation.

---

## References

- **PRD:** `features/writing-metrics.md`
- **Architecture:** `ARCHITECTURE.md`
- **Standards:** `STANDARDS.md`
- **Similar Implementation:** AllPaths generator (`formats/allpaths/generator.py`)
- **Related ADR:** ADR-012: Core Library and Format Separation Architecture
