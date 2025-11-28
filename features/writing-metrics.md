# Feature PRD: Writing Metrics & Statistics

**Status:** Planned
**Owner:** Product Manager
**Priority:** HIGH

---

## Executive Summary

Writers need quantitative insights into their writing output and patterns. This feature provides metrics in two formats: a command-line interface for quick checks during writing, and an HTML build format for persistent viewing and sharing.

**Key Capabilities:**
- Calculate total word counts across the entire story
- Compute per-passage and per-file statistics (min/mean/median/max word counts)
- Show word count distributions (bucketed ranges)
- Filter metrics by file prefix (e.g., only KEB files, only mansel files, or all)
- Identify longest passages and files

**Dual Output Formats:**
- **CLI**: Quick on-demand metrics for active writing sessions (`make metrics`)
- **HTML**: Persistent metrics view generated on every build, published to GitHub Pages alongside other story formats (Harlowe, Paperthin, DotGraph, AllPaths)

This tool helps writers answer questions like "How much have I written?" and "What's my typical passage length?" both during active writing (CLI) and when reviewing the project in a browser (HTML).

**Timing Context:**
- **Ideally available:** Throughout November for understanding writing output and patterns
- **Foundation for:** December retrospective analysis of writing patterns and evolution

---

## Phase Applicability

This is an **active-writing tool** that serves writers during different phases:

### During Active Writing (November 2025)
**Primary Use:** Understanding writing output and patterns
- Check total word count and writing volume
- Stay motivated by seeing quantitative output
- Understand typical passage lengths while writing
- Analyze writing patterns in real-time

### After Active Writing (Late November/Early December)
**Primary Use:** Final metrics and contribution analysis
- Analyze individual author contributions
- Identify longest passages for potential refactoring
- Understand final story structure and distribution

### Foundation for Retrospectives (December 2025+)
**Secondary Use:** Input data for advanced analytics
- Provides baseline metrics for trend analysis
- Word count data feeds into timeline visualizations
- Passage statistics inform pattern analysis
- File distribution data supports evolution tracking

**Relationship to Other Features:**
- **Complementary to AllPaths Progress Tracking:** AllPaths focuses on path-level tracking (how many paths created/modified), while Writing Metrics focuses on word-level tracking (how many words written, passage lengths)
- **Different from Post-NaNoWriMo Retrospective Tools:** This provides basic metrics during active writing; retrospective tools will add advanced trend analysis, timelines, and pattern evolution over time

---

## User Needs

### Need 1: Understand Total Writing Output
**Context:** Active writing during NaNoWriMo

**User Goal:** Know how much content I've created

**Questions Writers Need Answered:**
- How many total words have I written?
- How much content exists in the story?
- What is the current size of the project?

**Why This Matters:** Writers need clear, quantitative feedback on their output to stay motivated and understand the scope of their work.

---

### Need 2: Understand Writing Patterns
**Context:** Reviewing writing habits and style

**User Goal:** Understand my typical passage length and writing distribution

**Questions Writers Need Answered:**
- What's my typical passage length (mean/median)?
- What's my shortest and longest passage?
- How many passages fall into each word count range?
- Do I write consistently or have large variations?
- What's my average file size?

**Why This Matters:** Understanding writing patterns helps writers identify habits (e.g., consistently writing short passages vs. long passages), spot outliers that may need editing, and develop awareness of their writing style.

---

### Need 3: Filter by Author or Content Type
**Context:** Multi-author collaborative project

**User Goal:** See metrics for specific authors or story sections

**Questions Writers Need Answered:**
- How many words did each author contribute?
- What are the statistics for just my files (e.g., KEB-* files)?
- How do different authors' writing patterns compare?
- What's the breakdown between different story branches?

**Why This Matters:** In collaborative projects, authors need to track individual contributions, ensure balanced participation, and understand how different authors' styles compare.

---

### Need 4: Identify Outliers and Opportunities
**Context:** Reviewing story structure and editing

**User Goal:** Find exceptionally long or short passages

**Questions Writers Need Answered:**
- Which passages are over 1000 words (may need splitting)?
- Which passages are under 100 words (may need expansion)?
- What are the top 5 longest passages?
- Which files contain the most content?

**Why This Matters:** Outliers may indicate structural issues (passages that are too long for comfortable reading, or too short to be meaningful), helping writers identify candidates for refactoring or expansion.

---

### Need 5: View Metrics in Browser
**Context:** Reviewing project in browser, sharing metrics with collaborators

**User Goal:** See persistent metrics alongside other story outputs

**Questions Writers Need Answered:**
- What are the current metrics without running CLI commands?
- Can I share metrics with collaborators via a URL?
- Can I view metrics on any device with a browser?
- Are metrics always up-to-date with the latest build?

**Why This Matters:** HTML output makes metrics accessible without command-line access, enables sharing via GitHub Pages, and provides a persistent view that updates automatically with each build. This aligns with the other build formats (Harlowe, Paperthin, DotGraph, AllPaths) that provide different views of the story.

---

## User Stories

### Story 1: Check Total Word Count
**As a** writer working on the story
**I want** to see my total word count
**So that** I understand how much content I've created

**Acceptance Criteria:**
- Command displays total word count across all story files
- Word count excludes special files (StoryData, StoryTitle, StoryStyles)
- Word count excludes Harlowe syntax (macros, link markup, HTML tags)
- Word count includes only actual prose content
- Output is clear and easy to read

---

### Story 2: View Passage Statistics
**As a** writer reviewing my writing patterns
**I want** to see min/mean/median/max word counts per passage
**So that** I understand my typical passage length and variation

**Acceptance Criteria:**
- Command displays passage count (total number of passages)
- Min, mean, median, and max word counts shown per passage
- Statistics are accurate (calculated from actual passage content)
- Statistics exclude passages from special files
- Clear labels distinguish passage vs. file statistics

---

### Story 3: View File Statistics
**As a** writer organizing content across multiple files
**I want** to see min/mean/median/max word counts per file
**So that** I understand how content is distributed across files

**Acceptance Criteria:**
- Command displays file count (total number of story files)
- Min, mean, median, and max word counts shown per file
- Statistics calculated from all story files (KEB-*, mansel-*, Start.twee)
- Special files excluded from statistics
- File names shown for min and max (identify which files)

---

### Story 4: Filter by Prefix
**As a** collaborating author
**I want** to filter metrics by file prefix (e.g., only KEB files)
**So that** I can see statistics for specific authors or story sections

**Acceptance Criteria:**
- `--include` flag filters to specific prefixes (e.g., `--include KEB`)
- `--exclude` flag excludes specific prefixes (e.g., `--exclude mansel`)
- Multiple prefixes can be specified (comma-separated or multiple flags)
- Filtered results show totals and statistics for matching files only
- Clear indication of what filter is applied
- Default: include all story files (no filter)

---

### Story 5: View Word Count Distribution
**As a** writer analyzing my content structure
**I want** to see how many passages fall into each word count range
**So that** I can identify patterns and outliers

**Acceptance Criteria:**
- Distribution shows passage counts in meaningful ranges (e.g., 0-100, 101-300, 301-500, 501-1000, 1000+)
- Distribution shows file counts in meaningful ranges
- Clear labels for each range
- Counts are accurate
- Ranges chosen to be useful for identifying structure issues

---

### Story 6: Identify Top Passages
**As a** writer reviewing content length
**I want** to see the longest passages by word count
**So that** I can identify candidates for splitting or refactoring

**Acceptance Criteria:**
- Command shows top N longest passages (default: top 5)
- Each entry shows passage name, word count, and source file
- Passages sorted by word count (descending)
- Clear threshold indicator (e.g., "passages over 1000 words")
- Helps identify outliers quickly

---

### Story 7: View Metrics in Browser
**As a** writer reviewing the project online
**I want** to view writing metrics in my browser
**So that** I can see current statistics without using command-line tools

**Acceptance Criteria:**
- HTML file generated on every build (alongside Harlowe, Paperthin, DotGraph, AllPaths)
- Accessible via GitHub Pages at a consistent URL
- Shows all metric sections: word count summary, passage statistics, file statistics, distribution, top passages
- Updates automatically with each build (reflects current story state)
- No CLI access required to view metrics
- Basic, readable HTML format (similar to Paperthin format simplicity)
- Can be viewed on any device with a browser
- Published alongside other build formats in the same GitHub Pages structure

---

## Feature Behavior

### Command Interface

**Command:** `make metrics` or `npm run metrics`

**Options:**
- `--include PREFIX` - Only include files matching prefix (e.g., `--include KEB`)
- `--exclude PREFIX` - Exclude files matching prefix (e.g., `--exclude mansel`)
- `--top N` - Show top N longest passages (default: 5)
- `--help` - Display usage information

**Output Sections:**
1. **Word Count Summary** - Total word count, files analyzed, passage count
2. **Passage Statistics** - Count, min/mean/median/max word counts per passage
3. **File Statistics** - Count, min/mean/median/max word counts per file
4. **Distribution** - Passage and file counts by word count ranges
5. **Top Passages** - Longest passages with names and counts

---

### HTML Output Format

**Generated:** On every build via `make build` or `make deploy`

**Published:** To GitHub Pages alongside other formats:
- `/index.html` - Harlowe playable story
- `/paperthin.html` - Linear proofing text
- `/graph.svg` - Visual story structure
- `/allpaths.html` - All possible paths
- `/metrics.html` - Writing metrics (NEW)

**Content Sections:**
1. **Word Count Summary** - Total word count, files analyzed, passage count
2. **Passage Statistics** - Count, min/mean/median/max word counts per passage
3. **File Statistics** - Count, min/mean/median/max word counts per file
4. **Distribution** - Passage and file counts by word count ranges (table or visual representation)
5. **Top Passages** - Longest passages with names and counts

**Filtering in HTML:**
- HTML shows metrics for ALL story files (no filtering in HTML view)
- Users needing filtered metrics use CLI with `--include` or `--exclude` flags
- HTML provides comprehensive overview; CLI provides flexible analysis

**Format Characteristics:**
- Basic, readable HTML (similar to Paperthin's simplicity)
- No complex interactivity required (static display)
- Clean formatting for easy reading
- Shows same information as CLI output
- Updates automatically on every build

---

### Word Counting Rules

**Include in word count:**
- All prose text within passage content
- Dialogue and narration
- Text visible to players

**Exclude from word count:**
- Harlowe macro syntax (e.g., `(set: $var to value)`)
- Link markup syntax (e.g., `[[Display text->target]]` counts only "Display text")
- HTML tags (e.g., `<div>`, `</div>`)
- Passage headers (e.g., `:: PassageName`)
- Metadata and special passage directives

**Special file exclusions:**
- StoryData.twee
- StoryTitle.twee
- StoryStyles.twee

**File inclusion rules:**
- Start.twee (always included unless filtered)
- KEB-*.twee (date-stamped story files)
- mansel-*.twee (date-stamped story files)

---

### Output Format

**Human-readable text format:**
- Clear section headers
- Aligned columns for statistics tables
- Distribution shown as ASCII bar charts or tables
- Top passages listed with clear formatting

**Example output structure:**
```
Writing Metrics & Statistics
============================

Word Count Summary:
  Total Words: 22,589
  Files Analyzed: 31 story files
  Passages: 54 total

Passage Statistics:
  Min:     7 words
  Mean:    418.3 words
  Median:  296.5 words
  Max:     1,644 words

File Statistics:
  Min:     224 words (Start.twee)
  Mean:    670.4 words
  Median:  672.0 words
  Max:     1,490 words (KEB-251126.twee)

Word Count Distribution (Passages):
  0-100:     5 passages
  101-300:   23 passages
  301-500:   15 passages
  501-1000:  7 passages
  1000+:     4 passages

Top 5 Longest Passages:
  1. Passage Name (1,644 words) - KEB-251120.twee
  2. Another Passage (1,200 words) - KEB-251125.twee
  ...
```

---

## Success Metrics

### User Understanding
- Writers can explain what each metric means and how to interpret it
- Writers cite metrics when discussing writing output and patterns
- Writers use filters correctly to analyze specific content (CLI)
- Writers know where to find metrics HTML on GitHub Pages

### Feature Usage
- Writers run CLI metrics regularly (weekly or more) during active writing for quick checks
- Writers view HTML metrics when reviewing project in browser
- Metrics cited in team discussions about writing output
- Filters used to compare author contributions (CLI)
- Top passages list used to identify refactoring candidates
- HTML metrics shared via URL with collaborators

### Format Usage
- **CLI**: Used for on-demand analysis during active writing sessions
- **HTML**: Used for reviewing project state, sharing with collaborators, viewing on mobile devices

### Qualitative Indicators
- Writers report feeling motivated by seeing quantitative output
- Metrics help answer "how much have I written?" questions instantly
- Team uses metrics to ensure balanced participation
- Post-NaNoWriMo retrospectives reference these metrics
- HTML format makes metrics accessible to non-technical collaborators
- Metrics viewed alongside other formats (Harlowe, Paperthin, etc.) for comprehensive project review

---

## Edge Cases

### Empty Repository
**Scenario:** No story files exist yet

**Behavior:**
- CLI reports 0 words, 0 passages, 0 files
- HTML shows 0 words, 0 passages, 0 files
- No statistics shown (cannot compute min/max with no data)
- Clear message: "No story files found"
- CLI exits gracefully without errors
- HTML still generated (shows empty state, not missing file)

---

### Single Passage
**Scenario:** Only one passage exists

**Behavior:**
- Min, mean, median, and max are all the same value
- Distribution shows single entry
- Statistics still displayed (not skipped)
- Median is well-defined for single value

---

### All Files Filtered Out
**Scenario:** Filter excludes all files (e.g., `--include NOTEXIST`)

**Behavior:**
- Command reports 0 words, 0 passages, 0 files after filtering
- Clear message: "No files match filter: --include NOTEXIST"
- Suggestion: "Try removing filters or using different criteria"
- Exits gracefully

---

### Very Long Passages
**Scenario:** Passages exceed 5,000 words

**Behavior:**
- Statistics accurately reflect actual word counts
- Top passages list shows these outliers
- Distribution may show custom bucket (e.g., "2000+", "5000+")
- No artificial limits or truncation

---

### Mixed Authorship Files
**Scenario:** Cannot determine author from filename

**Behavior:**
- Files without clear prefix still included in totals
- Filters based on prefix patterns only
- Files that don't match any prefix can still be counted
- Graceful handling of naming variations

---

### Build Failure During HTML Generation
**Scenario:** HTML generation fails during build process

**Behavior:**
- Build reports error clearly
- Build continues (doesn't block other formats)
- Missing metrics.html on GitHub Pages
- CLI still works (independent of HTML generation)
- Error logged for debugging
- Graceful degradation: other formats still published

---

## Risk Considerations

### Word Counting Accuracy
**Risk:** Harlowe syntax may be counted incorrectly, inflating word counts

**Mitigation:**
- Clear documentation of what's counted and what's excluded
- Test against known passages with known word counts
- Match behavior of established word count tools where possible
- Strip macros, link syntax, and HTML before counting

**Monitoring:** Compare manual counts to automated counts for sample passages

---

### Performance with Large Stories
**Risk:** Metrics calculation may be slow for very large stories (100+ files, 1000+ passages)

**Mitigation:**
- Word counting should be fast (simple text processing)
- Statistics computation is O(n) where n = passage count
- No expensive operations needed
- Test with realistic story sizes (50+ files)

**Monitoring:** Track execution time, warn if exceeds reasonable threshold

---

### Filter Confusion
**Risk:** Writers may not understand how `--include` and `--exclude` interact

**Mitigation:**
- Clear help text explaining filter behavior
- Examples in documentation
- Clear output showing what filter was applied
- Simple semantics: include first, then exclude

**Monitoring:** Track user questions about filter behavior

---

### Build Integration Complexity
**Risk:** Adding HTML generation to build process may slow builds or introduce failures

**Mitigation:**
- Metrics generation should be fast (simple text processing, same as CLI)
- HTML generation is simple template rendering
- Build continues if metrics generation fails (graceful degradation)
- Test build integration thoroughly
- Monitor build times to ensure no significant impact

**Monitoring:** Track build times, track metrics generation failures

---

## Acceptance Criteria Summary

### Core Functionality
- [ ] Command calculates total word count across all story files
- [ ] Word count excludes special files (StoryData, StoryTitle, StoryStyles)
- [ ] Word count excludes Harlowe syntax (macros, links, HTML)
- [ ] Passage statistics computed: count, min, mean, median, max
- [ ] File statistics computed: count, min, mean, median, max
- [ ] Distribution shows passage and file counts by word count ranges

### CLI Output
- [ ] Human-readable text format in CLI
- [ ] Clear section headers and labels
- [ ] Statistics properly aligned and formatted
- [ ] Distribution easy to interpret
- [ ] Top passages list shows passage names and word counts

### HTML Output
- [ ] HTML file generated on every build
- [ ] Published to GitHub Pages as `/metrics.html`
- [ ] Shows all metric sections (summary, statistics, distribution, top passages)
- [ ] Updates automatically with each build
- [ ] Basic, readable HTML format
- [ ] No CLI access required to view
- [ ] Accessible on any device with a browser
- [ ] Shows metrics for all story files (no filtering in HTML)

### Filtering (CLI Only)
- [ ] `--include` flag filters files by prefix
- [ ] `--exclude` flag filters files by prefix
- [ ] Filters can be combined
- [ ] Clear indication of active filters in output
- [ ] Default behavior: include all story files

### Data Accuracy
- [ ] Word counts match manual verification for sample passages
- [ ] Statistics computed correctly (verified against known datasets)
- [ ] Filters apply correctly (CLI)
- [ ] Edge cases handled gracefully (empty repo, single passage, etc.)
- [ ] HTML shows same data as CLI (when no filters applied)

### Build Integration
- [ ] Integrated into `make build` and `make deploy`
- [ ] HTML generated alongside Harlowe, Paperthin, DotGraph, AllPaths
- [ ] Build fails gracefully if metrics generation fails
- [ ] Clear build output showing metrics generation

### Documentation
- [ ] Usage examples in README or documentation
- [ ] Clear explanation of word counting rules
- [ ] Filter behavior documented (CLI)
- [ ] HTML format documented
- [ ] Integration with existing tooling (make/npm)

---

## Related Documents

- [VISION.md](../VISION.md) - Project vision and success criteria
- [ROADMAP.md](../ROADMAP.md) - Post-NaNoWriMo retrospective tools (planned)
- [PRINCIPLES.md](../PRINCIPLES.md) - Core principles including "Fast Feedback Loops"
