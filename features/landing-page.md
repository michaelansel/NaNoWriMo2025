# Landing Page for Output Formats

**Status:** Approved (strategically aligned)
**Created:** 2025-11-30
**Priority:** HIGH (supports Priority 1 - Writer Velocity, Priority 4 - Visibility)

## User Problem

Writers and contributors currently need to:
1. Navigate through README documentation to find output format links
2. Download PR artifacts and manually open each HTML file to preview changes
3. Remember which URL corresponds to which output format
4. Scroll through long lists in PR comments to find the format they need

The playable story (index.html) should be the primary entry point, but it's buried in documentation alongside technical outputs like graph visualization and metrics.

This friction slows down the core use case: **playing the story**.

## User Stories

### Primary User Story
**As a reader**, I want to play the interactive story with one click, so that I can experience the narrative without navigating documentation.

**Acceptance Criteria:**
- Landing page prominently features "Play" link/button at the top
- "Play" link uses action-oriented language ("Play the Story", not "View Harlowe Format")
- Visual hierarchy makes play button the most prominent element
- Landing page is the default entry point (served at root URL or linked first)

### Secondary User Stories

**As a writer**, I want to access all output formats from one page, so that I don't have to hunt through documentation.

**Acceptance Criteria:**
- All 6 output formats accessible from landing page
- Each format includes brief description of its purpose
- Formats organized by use case (reader vs. writer vs. technical)
- No duplication - each format listed once with clear purpose

**As a contributor**, I want to preview all output formats in a PR, so that I can verify my changes across all views.

**Acceptance Criteria:**
- PR comments link to landing page instead of listing all URLs
- Landing page works for both deployed (main branch) and PR preview artifacts
- Same landing page structure for previews and production

**As a new contributor**, I want to understand what each output format is for, so that I can choose the right view for my task.

**Acceptance Criteria:**
- Each format has a 1-2 sentence description
- Descriptions focus on user task ("Proofread text" not "Paperthin format")
- Clear visual distinction between reader-facing and writer-facing outputs

## Output Formats (Current State)

The build process generates 6 HTML outputs to `dist/`:

1. **index.html** (Harlowe) - Playable interactive story
2. **proofread.html** (Paperthin) - Linear text for proofreading
3. **graph.html** (DotGraph) - Interactive story structure visualization
4. **allpaths.html** (AllPaths) - All possible story paths for AI validation
5. **metrics.html** (Metrics) - Writing statistics and word counts
6. **story-bible.html** (Story Bible) - World consistency tracking and character info

All deployed to GitHub Pages at: `https://michaelansel.github.io/NaNoWriMo2025/`

## Requirements

### Landing Page Content

**Must Include:**
1. **Prominent "Play" Section (Top)**
   - Primary call-to-action button/link
   - Action-oriented text: "Play the Story" or "Start Reading"
   - Visual prominence (larger, colored, or highlighted)
   - Brief tagline (1 sentence describing the story)

2. **Reader Outputs Section**
   - Play (index.html) - already featured prominently above
   - Option: could repeat here for consistency, or omit to avoid duplication

3. **Writer Outputs Section**
   - Proofread (proofread.html) - "Read as linear text for editing"
   - Metrics (metrics.html) - "View writing statistics and word counts"
   - AllPaths (allpaths.html) - "Browse all story paths and track progress"
   - Story Bible (story-bible.html) - "Track world-building facts and character info"

4. **Technical Outputs Section**
   - Graph (graph.html) - "Visualize story structure and branching"

**Format Descriptions (Testable):**
Each output link must include:
- Format name (user-facing, not technical)
- 1-2 sentence purpose description
- Direct link to the HTML file

**Visual Organization:**
- Clear sections (Reader / Writer / Technical)
- Prominent "Play" at top
- Consistent spacing and typography
- Mobile-friendly layout

### File Location and Entry Point

**Product Decision (Finalized):**
Landing page replaces index.html as the default entry point. Playable story (current index.html) moves to play.html.

**Rationale:**
- Landing page makes "Play" the most prominent action (aligns with "readers first")
- Single entry point for all output formats reduces friction
- Moving playable story to play.html is a small cost for significantly better UX
- First-time visitors immediately understand "this is a story to play"

**Impact on existing URLs:**
- `index.html`: Landing page (NEW - what users see first)
- `play.html`: Harlowe playable story (MOVED from index.html)
- All other format URLs unchanged (proofread.html, graph.html, etc.)

**Implementation note:** Technical details (build process, file naming, HTML structure) are documented in architecture specs.

### Documentation Cleanup

**README.md Changes:**

Current "Outputs" section (lines 86-91):
```markdown
## Outputs

- **Harlowe format** (`index.html`): Interactive playable story
- **Paperthin format** (`proofread.html`): Linear text view for proofreading - [view live](https://michaelansel.github.io/NaNoWriMo2025/proofread.html)
- **DotGraph format** (`graph.html`): Interactive story structure visualization - [view live](https://michaelansel.github.io/NaNoWriMo2025/graph.html)
- **AllPaths format** (`allpaths.html`): All possible story paths for AI continuity checking - [view live](https://michaelansel.github.io/NaNoWriMo2025/allpaths.html) | [documentation](formats/allpaths/README.md)
```

**Replace with:**
```markdown
## Outputs

All output formats are available from the [landing page](https://michaelansel.github.io/NaNoWriMo2025/).

- **Play the story:** [https://michaelansel.github.io/NaNoWriMo2025/](https://michaelansel.github.io/NaNoWriMo2025/)
- **Browse all formats:** Proofread, metrics, story paths, story bible, and structure visualization
```

**Acceptance Criteria:**
- "Outputs" section reduced from 4+ bullet points to 2-3 lines
- Primary "Play" link preserved and prominent
- Other formats referenced generically with link to landing page
- No duplicate URL lists

**Workflow PR Comment Changes:**

Current PR comment (lines 147-173 in build-and-deploy.yml):
- Lists 5 file sizes
- Lists 7 preview steps
- Lists 5 deployment URLs

**Replace with:**
```markdown
## ✅ Build Successful

Your story has been built successfully!

**📊 Build Stats:**
- [Build stats details preserved]

**🎮 Preview Your Changes:**
1. Download the `story-preview` artifact from the [workflow run](...)
2. Extract the zip file
3. Open `index.html` (landing page) to access all output formats

**💡 Tip:** Once merged to main, this will be live at:
- https://[owner].github.io/[repo]/ (landing page with links to all formats)
```

**Acceptance Criteria:**
- PR comment "Preview" section reduced from 7 steps to 3 steps
- Deployment URL list reduced from 5 URLs to 1 landing page URL
- Build stats preserved (still useful for performance monitoring)
- Clear instruction to open landing page for format access

## Edge Cases

### Missing Outputs
**Scenario:** Story Bible build fails (it's optional, continue-on-error: true)
**Expected Behavior:** Landing page shows all 6 formats; story-bible link shows graceful error or "not available" message if file missing
**Acceptance Criteria:** Landing page doesn't break if story-bible.html is missing

### PR Preview vs Production
**Scenario:** Landing page accessed from PR artifact download vs deployed GitHub Pages
**Expected Behavior:** Same landing page content and structure in both contexts
**Acceptance Criteria:** No environment-specific behavior; all links are relative paths

### Mobile Access
**Scenario:** User accesses landing page on mobile device
**Expected Behavior:** Responsive layout, readable text, clickable buttons
**Acceptance Criteria:** Landing page is mobile-friendly (responsive design)

### First-Time Visitor
**Scenario:** Someone discovers the project via GitHub Pages URL
**Expected Behavior:** Immediately clear that this is an interactive story; "Play" is obvious
**Acceptance Criteria:** Landing page communicates purpose within 3 seconds of viewing

### Direct Format Access
**Scenario:** User has bookmarked a specific format URL (e.g., proofread.html)
**Expected Behavior:** Direct links still work; landing page doesn't break existing bookmarks
**Acceptance Criteria:** All existing URLs continue to work (no breaking changes)

## Success Metrics

**Quantitative:**
- README "Outputs" section reduced by >50% (4 bullets → 2-3 lines)
- PR comment reduced by >40% (12 lines → 7 lines)
- Landing page loads in <1 second (static HTML, no dependencies)
- All 6 format links functional on landing page

**Qualitative:**
- First-time visitors understand "this is a story to play" within 3 seconds
- Writers can find any output format from landing page without hunting
- PR reviewers access all previews through one entry point

## Non-Goals (Out of Scope)

- **Dynamic landing page generation:** Landing page is static HTML, not generated from metadata
- **Format switching UI:** Landing page links to formats; it doesn't embed them or provide in-page switching
- **Analytics/tracking:** No usage tracking or visitor analytics on landing page
- **Branding/styling beyond basics:** Simple, functional design; not a marketing page
- **Search functionality:** With only 6 formats, search is unnecessary
- **Historical version access:** Landing page shows current build only, not past versions

## Dependencies

**Reads:**
- Current build outputs (all 6 HTML files in dist/)
- README.md (to understand current documentation)
- Workflow configuration (to update PR comments)

**Does Not Depend On:**
- Build process changes (landing page is static, added to dist/ manually or via simple script)
- Story content (landing page describes formats, not story content)
- GitHub Pages configuration (uses existing deployment)

## Handoff to Architect

**What PM Has Decided (WHAT):**
- Landing page becomes index.html (default entry point)
- Playable story moves to play.html
- Landing page content: 3 sections (Reader/Writer/Technical) with 6 format links
- "Play" action featured prominently at top
- Each format has name, description, and direct link
- Mobile-friendly, static HTML

**What Architect Decides (HOW):**
- HTML template approach (hand-written vs generated)
- Build process integration (file renaming, copying, generation)
- Responsive layout implementation
- Error handling for missing outputs
- Source file location and organization

**PM Preferences (Not Requirements):**
- Hand-written HTML preferred (6 static links don't need generation complexity)
- If format file missing, browser 404 is acceptable (no complex error handling needed)
