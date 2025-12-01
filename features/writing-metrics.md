# Feature PRD: Writing Metrics & Statistics

**Status:** Active
**Owner:** Product Manager
**Priority:** HIGH

---

## Executive Summary

Writers need quantitative insights into their writing output and patterns. This feature provides an HTML metrics page automatically generated with each build and published to GitHub Pages alongside other story formats.

**Key Capabilities:**
- Calculate total word counts across the entire story
- Compute aggregate passage statistics (min/mean/median/max word counts)
- Compute aggregate file statistics (min/mean/median/max word counts per file)
- Show word count distributions (fixed ranges: 0-100, 101-300, 301-500, 501-1000, 1000+)
- Identify top 5 longest passages
- View metrics on any device with a browser

**Scope (MVP):**
- Single aggregate view showing all files and passages
- No per-author filtering or drill-down
- No per-file detailed breakdowns
- Simple, comprehensive overview of entire project

**Output Format:**
- **HTML**: Persistent metrics view generated automatically on every build
- Published to GitHub Pages at `/metrics.html`
- Always up-to-date with the latest build
- No special tools needed—just view in your browser

This tool helps writers answer questions like "How much have I written?" and "What's my typical passage length?" when reviewing the project in a browser.

**Use Cases:**
- **Understanding writing output:** Check total word count and writing volume
- **Staying motivated:** See quantitative progress toward goals
- **Analyzing patterns:** Understand typical passage lengths and writing distribution
- **Identifying refactoring candidates:** Find exceptionally long or short passages
- **Tracking contributions:** View overall project metrics in collaborative projects

**Relationship to Other Features:**
- **Complementary to AllPaths Progress Tracking:** AllPaths tracks path-level progress (paths created/modified), while Writing Metrics tracks word-level progress (words written, passage lengths)
- **Foundation for advanced analytics:** Provides baseline metrics that could feed into retrospective analysis tools

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

### Need 3: Understand Collaborative Contributions
**Context:** Multi-author collaborative project

**User Goal:** See overall project metrics and understand the story's scope

**Questions Writers Need Answered:**
- How much content exists in the story overall?
- What are the typical passage and file lengths across the project?
- How is content distributed across the story?
- What's the overall structure and scale?

**Why This Matters:** In collaborative projects, authors need to understand the project's overall scope and structure.

**Scope (MVP):** Single aggregate view showing all files combined. No per-author filtering or individual author breakdowns. Writers see the project as a whole, not segmented by contributor.

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

### Need 5: Access Metrics Anywhere
**Context:** Reviewing project in browser, sharing metrics with collaborators

**User Goal:** See persistent metrics alongside other story outputs

**Questions Writers Need Answered:**
- What are the current metrics as of the latest build?
- Can I share metrics with collaborators via a URL?
- Can I view metrics on any device with a browser?
- Are metrics always up-to-date with the latest build?

**Why This Matters:** HTML output makes metrics accessible from any device with a browser, enables sharing via GitHub Pages, and provides a persistent view that updates automatically with each build. This aligns with the other build formats (Harlowe, Paperthin, DotGraph, AllPaths) that provide different views of the story.

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

---

### Story 5: View Word Count Distribution
**As a** writer analyzing my content structure
**I want** to see how many passages fall into each word count range
**So that** I can identify patterns and outliers

**Acceptance Criteria:**
- Distribution shows passage counts in fixed ranges: 0-100, 101-300, 301-500, 501-1000, 1000+
- Distribution shows file counts in same ranges: 0-100, 101-300, 301-500, 501-1000, 1000+
- Clear labels for each range
- Counts are accurate
- Ranges identify common structure patterns (short passages, medium passages, long passages, very long passages)

---

### Story 6: Identify Top Passages
**As a** writer reviewing content length
**I want** to see the longest passages by word count
**So that** I can identify candidates for splitting or refactoring

**Acceptance Criteria:**
- Shows top 5 longest passages (fixed, not configurable)
- Each entry shows passage name, word count, and source file
- Passages sorted by word count (descending)
- Clear heading: "Top 5 Longest Passages"
- Helps identify outliers quickly

---

### Story 7: View Metrics on GitHub Pages
**As a** writer reviewing the project online
**I want** to view writing metrics in my browser
**So that** I can see current statistics from any device

**Acceptance Criteria:**
- HTML file generated on every build (alongside Harlowe, Paperthin, DotGraph, AllPaths)
- Accessible via GitHub Pages at `/metrics.html`
- Shows all metric sections: word count summary, passage statistics, file statistics, distribution, top passages
- Updates automatically with each build (reflects current story state)
- Basic, readable HTML format (similar to Paperthin format simplicity)
- Can be viewed on any device with a browser
- Published alongside other build formats in the same GitHub Pages structure

---

## Feature Behavior

### HTML Output Format

**Generated:** Automatically on every build when you push or merge changes

**Published:** To GitHub Pages alongside other formats:
- `/index.html` - Harlowe playable story
- `/paperthin.html` - Linear proofing text
- `/graph.svg` - Visual story structure
- `/allpaths.html` - All possible paths
- `/metrics.html` - Writing metrics (NEW)

**Content Sections:**
1. **Word Count Summary** - Total word count, files analyzed, passage count
2. **Passage Statistics** - Count, min/mean/median/max word counts (aggregate across all passages)
3. **File Statistics** - Count, min/mean/median/max word counts (aggregate across all files)
4. **Distribution** - Passage and file counts by fixed word count ranges: 0-100, 101-300, 301-500, 501-1000, 1000+
5. **Top 5 Passages** - Five longest passages with names, word counts, and source files

**Single Aggregate View (MVP):**
- HTML shows metrics for ALL story files combined
- Provides complete overview of the entire project
- No per-author filtering or drill-down UI
- No per-file detailed views (only aggregate file statistics)
- Simple, comprehensive view of project as a whole

**Format Characteristics:**
- Basic, readable HTML (similar to Paperthin's simplicity)
- No complex interactivity required (static display)
- Clean formatting for easy reading
- Comprehensive metrics and statistics
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

## Success Metrics

### User Understanding
- Writers can explain what each metric means and how to interpret it
- Writers cite metrics when discussing writing output and patterns
- Writers know where to find metrics on GitHub Pages (`/metrics.html`)
- Writers understand metrics update automatically with each build

### Feature Usage
- Writers view HTML metrics when reviewing project in browser
- Metrics cited in team discussions about writing output
- Top passages list used to identify refactoring candidates
- HTML metrics shared via URL with collaborators
- Metrics viewed alongside other formats (Harlowe, Paperthin, etc.)

### Qualitative Indicators
- Writers report feeling motivated by seeing quantitative output
- Metrics help answer "how much have I written?" questions
- Team uses metrics to understand project scope and progress
- Post-NaNoWriMo retrospectives reference these metrics
- HTML format makes metrics accessible from any device
- Metrics viewed alongside other formats for comprehensive project review

---

## Edge Cases

### Empty Repository
**Scenario:** No story files exist yet

**Behavior:**
- HTML shows 0 words, 0 passages, 0 files
- No statistics shown (cannot compute min/max with no data)
- Clear message: "No story files found"
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

---

### Very Long Passages
**Scenario:** Passages exceed 5,000 words

**Behavior:**
- Statistics accurately reflect actual word counts
- Top 5 passages list shows these outliers
- Distribution uses 1000+ bucket for all passages above 1000 words
- No artificial limits or truncation in reported word counts

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

---

### Build Integration Complexity
**Risk:** Adding HTML generation to build process may slow builds or introduce failures

**Mitigation:**
- Metrics generation should be fast (simple text processing)
- HTML generation is simple template rendering
- Build continues if metrics generation fails (graceful degradation)
- Test build integration thoroughly
- Monitor build times to ensure no significant impact

**Monitoring:** Track build times, track metrics generation failures

---

## Acceptance Criteria Summary

### Core Functionality
- [ ] Metrics calculate total word count across all story files
- [ ] Word count excludes special files (StoryData, StoryTitle, StoryStyles)
- [ ] Word count excludes Harlowe syntax (macros, links, HTML)
- [ ] Passage statistics computed: count, min, mean, median, max (aggregate view)
- [ ] File statistics computed: count, min, mean, median, max (aggregate view)
- [ ] Distribution shows passage and file counts by fixed ranges: 0-100, 101-300, 301-500, 501-1000, 1000+
- [ ] Top 5 longest passages displayed (fixed, not configurable)

### HTML Output
- [ ] HTML file generated on every build
- [ ] Published to GitHub Pages as `/metrics.html`
- [ ] Shows all metric sections (summary, statistics, distribution, top 5 passages)
- [ ] Updates automatically with each build
- [ ] Basic, readable HTML format
- [ ] Accessible on any device with a browser
- [ ] Shows single aggregate view of all story files (no per-author or per-file drill-downs)
- [ ] Clear section headers and labels
- [ ] Statistics properly formatted and easy to read

### Data Accuracy
- [ ] Word counts match manual verification for sample passages
- [ ] Statistics computed correctly (verified against known datasets)
- [ ] Edge cases handled gracefully (empty repo, single passage, etc.)

### Build Integration
- [ ] Integrated into automated build pipeline
- [ ] HTML generated alongside Harlowe, Paperthin, DotGraph, AllPaths
- [ ] Build fails gracefully if metrics generation fails
- [ ] Clear build output showing metrics generation

### Documentation
- [ ] Clear explanation of word counting rules
- [ ] HTML format documented
- [ ] URL location documented (`/metrics.html`)
- [ ] Metric sections and statistics explained

---

## Related Documents

- [VISION.md](../VISION.md) - Project vision and success criteria
- [ROADMAP.md](../ROADMAP.md) - Post-NaNoWriMo retrospective tools (planned)
- [PRINCIPLES.md](../PRINCIPLES.md) - Core principles including "Fast Feedback Loops"
