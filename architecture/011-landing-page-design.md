# Architecture Design: Landing Page for Output Formats

## Status

**Approved** - Ready for implementation

**Created:** 2025-11-30
**Author:** Architect
**Related PRD:** `/home/user/NaNoWriMo2025/features/landing-page.md`

## Context

### Problem

Currently, users must navigate through README documentation or PR artifacts to find specific output formats. The playable story (index.html) is the primary use case but is buried alongside technical outputs. Writers and contributors experience friction when trying to access different output formats.

### Requirements Summary (from PM)

1. Landing page with **prominent "Play" section** at top
2. All 6 output formats accessible with descriptions
3. Organized by use case: Reader / Writer / Technical
4. Landing page becomes default entry point (index.html)
5. README and PR comments simplified to reference landing page
6. Static HTML, mobile-friendly, no build dependencies

### PM Recommendation

**Option A**: Landing page IS index.html, playable story moves to play.html.

**Rationale**: Better UX - the landing page makes "Play" the first thing users see. Moving the playable story to play.html is a small cost for significantly better discoverability.

## Decision

### File Structure: Option A (Landing Page as Index)

**Adopted File Structure:**

```
dist/
├── index.html          # Landing page (NEW - default entry point)
├── play.html           # Playable story (RENAMED from index.html)
├── proofread.html      # Proofreading format
├── graph.html          # Structure visualization
├── allpaths.html       # All paths browser
├── metrics.html        # Writing statistics
└── story-bible.html    # World consistency tracking (optional)
```

**Rationale for Option A:**

1. **Better Discoverability**: Root URL shows all options, making "Play" more prominent than if it were the only option
2. **Lower Barrier to Entry**: First-time visitors immediately understand this is an interactive story with multiple views
3. **Alignment with Requirements**: PM's acceptance criteria state "Play in a place of prominence" - landing page accomplishes this better than burying play at root
4. **Non-Breaking for Direct Access**: All existing bookmarks to specific formats (proofread.html, graph.html, etc.) continue to work
5. **Small Migration Cost**: Only index.html → play.html needs updating in bookmarks/docs

**Trade-offs:**

- ❌ Existing "play at root" bookmarks break (acceptable - can add note in README)
- ❌ One extra click to play (mitigated by prominent CTA on landing page)
- ✅ Much better for new visitors
- ✅ Better for writers accessing multiple formats
- ✅ Aligns with "landing page as hub" pattern

### Landing Page Source Location

**Source:** `/home/user/NaNoWriMo2025/landing/index.html`

**Rationale:**
- Separate from story source (`/src/*.twee`)
- Easy to locate and edit
- Clear ownership (not auto-generated)
- Follows project's directory organization principles (STANDARDS.md)

### HTML Implementation Approach

**Decision:** Hand-written static HTML (no templating)

**Rationale:**
1. **Simplicity**: 6 static links don't require generation
2. **No Build Dependencies**: Static file, no Jinja2/templating needed
3. **Easy to Edit**: Writers/contributors can update directly
4. **Fast Loading**: No server-side rendering, instant load
5. **Alignment with PM Preference**: PRD explicitly prefers hand-written

**Alternative Considered:** Generated from metadata
- Rejected: Adds unnecessary complexity for 6 static links
- Overhead of maintaining generator > overhead of editing HTML directly

## Technical Design

### HTML Structure

**Layout:**

```
┌─────────────────────────────────────────┐
│  Header (Purple Gradient)               │
│  - Project Title                        │
│  - Brief Tagline                        │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  Hero Section - Play CTA (Large, Bold)  │
│  [▶ Play the Story]                     │
│  "An interactive narrative..."          │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  Writer Tools Section                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │Proofread │ │ Metrics  │ │All Paths ││
│  │Description│ │Description│ │Description││
│  └──────────┘ └──────────┘ └──────────┘│
│  ┌──────────┐                           │
│  │Story Bible│                          │
│  │Description│                          │
│  └──────────┘                           │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│  Technical Tools Section                │
│  ┌──────────┐                           │
│  │  Graph   │                           │
│  │Description│                          │
│  └──────────┘                           │
└─────────────────────────────────────────┘
```

**Responsive Behavior:**
- Desktop (>768px): Grid layout, 3 columns for Writer Tools
- Mobile (≤768px): Single column stack
- Touch-friendly: 44px minimum touch targets
- Readable: 16px base font size, 1.6 line height

### Visual Design

**Design System:**

Consistent with existing formats (metrics.html):

```css
Colors:
  - Primary Gradient: #667eea → #764ba2 (purple)
  - Background: #f5f5f5 (light gray)
  - Card Background: #ffffff (white)
  - Text Primary: #333333
  - Text Secondary: #666666
  - Accent (hover): #e8eaf6

Typography:
  - Font Family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif
  - Header: 2rem (32px), bold
  - Section Title: 1.5rem (24px), bold, color: #667eea
  - Card Title: 1.25rem (20px), bold
  - Body: 1rem (16px), line-height: 1.6
  - Description: 0.875rem (14px), color: #666

Spacing:
  - Container padding: 2rem (desktop), 1rem (mobile)
  - Card padding: 1.5rem
  - Section margin: 2rem bottom
  - Grid gap: 1.5rem

Components:
  - Cards: white background, 8px border-radius, subtle shadow
  - Buttons/Links: Consistent hover states (transform, color change)
  - Hero CTA: Large button, gradient background, prominent placement
```

**Visual Hierarchy:**

1. **Most Prominent**: Hero Play button
   - Largest size (2rem font, 3rem height)
   - Gradient background (#667eea → #764ba2)
   - White text, bold
   - Centered, full-width on mobile

2. **Secondary**: Section headings (Writer Tools, Technical Tools)
   - 1.5rem font
   - Purple accent color (#667eea)
   - Bottom border for separation

3. **Tertiary**: Individual format cards
   - Equal visual weight within sections
   - Consistent card styling
   - Hover states for interactivity

### Content Structure

**Format Descriptions (Testable from PRD):**

```html
<!-- Hero Section -->
<div class="hero">
  <a href="play.html" class="play-button">▶ Play the Story</a>
  <p class="tagline">An interactive narrative with branching paths</p>
</div>

<!-- Writer Tools Section -->
<section class="writer-tools">
  <h2>Writer Tools</h2>
  <div class="format-grid">

    <div class="format-card">
      <h3>Proofread</h3>
      <p>Read as linear text for editing and proofreading</p>
      <a href="proofread.html">Open Proofread View</a>
    </div>

    <div class="format-card">
      <h3>Metrics</h3>
      <p>View writing statistics and word counts</p>
      <a href="metrics.html">View Metrics</a>
    </div>

    <div class="format-card">
      <h3>All Paths</h3>
      <p>Browse all story paths and track progress</p>
      <a href="allpaths.html">Browse All Paths</a>
    </div>

    <div class="format-card">
      <h3>Story Bible</h3>
      <p>Track world-building facts and character info</p>
      <a href="story-bible.html">View Story Bible</a>
    </div>

  </div>
</section>

<!-- Technical Tools Section -->
<section class="technical-tools">
  <h2>Technical Tools</h2>
  <div class="format-grid">

    <div class="format-card">
      <h3>Graph Visualization</h3>
      <p>Visualize story structure and branching</p>
      <a href="graph.html">View Graph</a>
    </div>

  </div>
</section>
```

**Descriptions Alignment with PRD:**

| Format | PRD Description | Landing Page Description |
|--------|-----------------|--------------------------|
| Play | "Play the Story" or "Start Reading" | "Play the Story" (button text) |
| Proofread | "Read as linear text for editing" | "Read as linear text for editing and proofreading" |
| Metrics | "View writing statistics and word counts" | "View writing statistics and word counts" ✓ |
| AllPaths | "Browse all story paths and track progress" | "Browse all story paths and track progress" ✓ |
| Story Bible | "Track world-building facts and character info" | "Track world-building facts and character info" ✓ |
| Graph | "Visualize story structure and branching" | "Visualize story structure and branching" ✓ |

### Accessibility

**WCAG 2.1 AA Compliance:**

1. **Semantic HTML**: Use `<main>`, `<section>`, `<nav>` elements
2. **Heading Hierarchy**: Proper h1 → h2 → h3 structure
3. **Link Text**: Descriptive ("Open Proofread View" not "Click here")
4. **Color Contrast**:
   - Text on white: 4.5:1 minimum (using #333)
   - Button text on gradient: 4.5:1 minimum (white on purple)
5. **Touch Targets**: 44x44px minimum (buttons, links)
6. **Keyboard Navigation**: All interactive elements keyboard-accessible
7. **Screen Readers**: ARIA labels where helpful
8. **Focus Indicators**: Visible focus states on all interactive elements

**No JavaScript Required**: Fully functional without JavaScript

### Error Handling

**Missing story-bible.html:**

Per PM's preference (PRD line 272):
- Landing page shows link to story-bible.html
- If file missing, browser native 404 page shown
- Acceptable: Story Bible is optional (continue-on-error in workflow)

**Alternative Considered:** JavaScript to check file existence
- Rejected: Adds complexity, breaks "no JavaScript" requirement
- Browser 404 is standard web behavior for missing resources

## Build Process Changes

### Modified Workflow Steps

**File:** `.github/workflows/build-and-deploy.yml`

**Change 1: Rename Harlowe output to play.html**

```yaml
# Current (line 79-82):
- name: Build Harlowe version (main)
  run: |
    mkdir -p dist
    tweego src -o dist/index.html -f harlowe-3

# Modified:
- name: Build Harlowe version (playable story)
  run: |
    mkdir -p dist
    tweego src -o dist/play.html -f harlowe-3
```

**Change 2: Copy landing page to dist/**

```yaml
# NEW step (insert after line 82, before Paperthin build):
- name: Copy landing page
  run: |
    cp landing/index.html dist/index.html
```

**No other build steps change**: All other outputs (proofread, graph, allpaths, metrics, story-bible) remain unchanged.

### Build Order

```
1. Generate resources file
2. Auto-fix formatting (PRs only)
3. Download and install tweego
4. Download dotgraph format
5. Build Harlowe → dist/play.html          # MODIFIED
6. Copy landing page → dist/index.html     # NEW
7. Build Paperthin → dist/proofread.html
8. Build DotGraph → dist/graph.html
9. Build AllPaths → dist/allpaths.html
10. Build Metrics → dist/metrics.html
11. Build Story Bible → dist/story-bible.html (optional)
12. Upload artifacts
13. Deploy to GitHub Pages
```

**Rationale for Order:**
- Landing page copied after Harlowe build ensures dist/ exists
- Placed early to match conceptual importance (entry point)
- No dependencies on other build outputs

### Validation

**Post-Build Checks** (manual, for Developer):

```bash
# After local build, verify:
ls -lh dist/index.html    # Landing page exists
ls -lh dist/play.html     # Playable story exists
open dist/index.html      # Visual inspection:
                          #   - All 6 links present
                          #   - Play button prominent
                          #   - Mobile responsive
                          #   - Descriptions match PRD
```

## Documentation Changes

### README.md Changes

**File:** `/home/user/NaNoWriMo2025/README.md`

**Current (lines 86-91):**

```markdown
## Outputs

- **Harlowe format** (`index.html`): Interactive playable story
- **Paperthin format** (`proofread.html`): Linear text view for proofreading - [view live](https://michaelansel.github.io/NaNoWriMo2025/proofread.html)
- **DotGraph format** (`graph.html`): Interactive story structure visualization - [view live](https://michaelansel.github.io/NaNoWriMo2025/graph.html)
- **AllPaths format** (`allpaths.html`): All possible story paths for AI continuity checking - [view live](https://michaelansel.github.io/NaNoWriMo2025/allpaths.html) | [documentation](formats/allpaths/README.md)
```

**Replacement:**

```markdown
## Outputs

All output formats are available from the [landing page](https://michaelansel.github.io/NaNoWriMo2025/).

- **Play the story:** [https://michaelansel.github.io/NaNoWriMo2025/play.html](https://michaelansel.github.io/NaNoWriMo2025/play.html)
- **Browse all formats:** Proofread, metrics, story paths, story bible, and structure visualization - [view all](https://michaelansel.github.io/NaNoWriMo2025/)
```

**Impact:**
- Reduced from 4 detailed bullets to 2 concise lines ✓
- Primary "Play" link preserved and prominent ✓
- Other formats referenced generically with link to landing page ✓
- No duplicate URL lists ✓
- Meets PRD acceptance criteria (lines 138-142)

**Note:** "Quick Start" section (line 5) needs update:

```markdown
# Current:
**Play the story:** https://michaelansel.github.io/NaNoWriMo2025/

# Updated:
**Play the story:** https://michaelansel.github.io/NaNoWriMo2025/play.html
```

### Workflow PR Comment Changes

**File:** `.github/workflows/build-and-deploy.yml`

**Current (lines 147-173):**

```javascript
body: `## ✅ Build Successful

Your story has been built successfully!

**📊 Build Stats:**
- Harlowe version: ${(indexSize / 1024).toFixed(2)} KB
- Paperthin version: ${(proofreadSize / 1024).toFixed(2)} KB
- DotGraph version: ${(graphSize / 1024).toFixed(2)} KB
- AllPaths version: ${(allpathsSize / 1024).toFixed(2)} KB (${pathCount} paths)
- Metrics version: ${(metricsSize / 1024).toFixed(2)} KB

**🎮 Preview Your Changes:**
1. Download the \`story-preview\` artifact from the [workflow run](https://github.com/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId})
2. Extract the zip file
3. Open \`index.html\` to play the story
4. Open \`proofread.html\` for linear proofreading
5. Open \`graph.html\` to visualize the story structure
6. Open \`allpaths.html\` to browse all ${pathCount} story paths
7. Open \`metrics.html\` to view writing statistics

**💡 Tip:** Once merged to main, this will be live at:
- https://${context.repo.owner}.github.io/${context.repo.repo}/
- https://${context.repo.owner}.github.io/${context.repo.repo}/proofread.html
- https://${context.repo.owner}.github.io/${context.repo.repo}/graph.html
- https://${context.repo.owner}.github.io/${context.repo.repo}/allpaths.html
- https://${context.repo.owner}.github.io/${context.repo.repo}/metrics.html`
```

**Replacement:**

```javascript
body: `## ✅ Build Successful

Your story has been built successfully!

**📊 Build Stats:**
- Playable story: ${(playSize / 1024).toFixed(2)} KB
- Paperthin version: ${(proofreadSize / 1024).toFixed(2)} KB
- DotGraph version: ${(graphSize / 1024).toFixed(2)} KB
- AllPaths version: ${(allpathsSize / 1024).toFixed(2)} KB (${pathCount} paths)
- Metrics version: ${(metricsSize / 1024).toFixed(2)} KB

**🎮 Preview Your Changes:**
1. Download the \`story-preview\` artifact from the [workflow run](https://github.com/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId})
2. Extract the zip file
3. Open \`index.html\` (landing page) to access all output formats

**💡 Tip:** Once merged to main, this will be live at:
- https://${context.repo.owner}.github.io/${context.repo.repo}/ (landing page with links to all formats)`
```

**JavaScript Changes Required:**

```javascript
// Current:
const indexSize = fs.statSync('dist/index.html').size;

// Modified:
const playSize = fs.statSync('dist/play.html').size;
// Note: Don't stat index.html since it's the landing page (static, small)
```

**Impact:**
- "Preview" section reduced from 7 steps to 3 steps ✓
- Deployment URL list reduced from 5 URLs to 1 landing page URL ✓
- Build stats preserved (performance monitoring) ✓
- Clear instruction to open landing page ✓
- Meets PRD acceptance criteria (lines 169-173)

## Testing Strategy

### Developer Testing (Manual)

**After implementing landing page HTML:**

```bash
# 1. Build locally
npm run build

# 2. Check file structure
ls -l dist/
# Expected:
#   - index.html (landing page)
#   - play.html (playable story)
#   - proofread.html, graph.html, allpaths.html, metrics.html, story-bible.html

# 3. Visual inspection
open dist/index.html
# Verify:
#   - Play button is largest, most prominent element
#   - All 6 formats listed with descriptions
#   - Sections organized: Writer Tools, Technical Tools
#   - Mobile responsive (resize browser)
#   - All links work

# 4. Link validation
# Click each link on landing page, verify:
#   - play.html loads playable story
#   - All other formats load correctly
#   - story-bible.html shows 404 if not built (acceptable)

# 5. Accessibility check
# Keyboard navigation:
#   - Tab through all links
#   - Focus indicators visible
#   - Enter key activates links
```

**After modifying workflow:**

```bash
# 1. Push to PR branch
git checkout -b test/landing-page
# ... make changes ...
git push -u origin test/landing-page
gh pr create

# 2. Wait for workflow to complete

# 3. Download artifact from Actions tab

# 4. Extract and verify:
unzip story-preview.zip
ls -l dist/
# Expected: index.html (landing), play.html (story), others unchanged

# 5. Open index.html, verify landing page loads

# 6. Verify PR comment shows simplified preview instructions
```

### Acceptance Criteria Validation

**From PRD (lines 24-53), validate:**

- [x] Landing page prominently features "Play" link/button at the top
- [x] "Play" link uses action-oriented language ("Play the Story")
- [x] Visual hierarchy makes play button the most prominent element
- [x] Landing page is the default entry point (served at root URL)
- [x] All 6 output formats accessible from landing page
- [x] Each format includes brief description of its purpose
- [x] Formats organized by use case (reader vs. writer vs. technical)
- [x] No duplication - each format listed once with clear purpose
- [x] Each format has a 1-2 sentence description
- [x] Descriptions focus on user task
- [x] Clear visual distinction between reader-facing and writer-facing outputs

**Edge Cases (from PRD lines 176-200):**

1. **Missing story-bible.html**: Landing page shows link; browser 404 if missing ✓
2. **PR Preview vs Production**: Same landing page content in both contexts ✓
3. **Mobile Access**: Responsive layout, readable text, clickable buttons ✓
4. **First-Time Visitor**: Purpose clear within 3 seconds ✓
5. **Direct Format Access**: All existing URLs continue to work ✓

### Performance Validation

**Targets (from PRD line 207):**

- [x] Landing page loads in <1 second (static HTML, ~10KB estimated)
- [x] All 6 format links functional

**Measurement:**

```bash
# File size check
ls -lh dist/index.html
# Expected: <20KB (static HTML + embedded CSS)

# Load time (local)
time curl -s http://localhost:8000/index.html > /dev/null
# Expected: <100ms local, <1s on GitHub Pages
```

## Security Considerations

**No New Attack Surface:**

- Static HTML file, no server-side processing
- No user input, no forms
- No JavaScript execution
- All links are relative paths (no external URLs)
- No cookies, no tracking, no third-party resources

**Existing Security Model:**

- GitHub Pages serves static files over HTTPS
- Content Security Policy inherited from GitHub Pages defaults
- No changes to authentication, authorization, or data handling

## Deployment

### Rollout Plan

**Phase 1: Implementation (Developer)**
1. Create `/home/user/NaNoWriMo2025/landing/index.html`
2. Test locally: `open landing/index.html`
3. Validate accessibility, mobile responsiveness

**Phase 2: Build Integration (Developer)**
1. Modify workflow: Change Harlowe output to `play.html`
2. Add step to copy `landing/index.html` → `dist/index.html`
3. Test in PR: Verify artifact structure

**Phase 3: Documentation Update (Developer)**
1. Update README.md lines 5, 86-91
2. Update workflow PR comment template
3. Commit all changes in same PR

**Phase 4: Validation (Developer)**
1. Create test PR with landing page changes
2. Download artifact, verify structure
3. Visual inspection of landing page
4. Verify PR comment shows new template
5. Merge when all acceptance criteria met

**Phase 5: Monitor (Post-Merge)**
1. Verify GitHub Pages deployment succeeds
2. Check live landing page: https://michaelansel.github.io/NaNoWriMo2025/
3. Verify all links work on production
4. Check mobile responsiveness on real devices

### Rollback Plan

**If landing page has issues:**

```bash
# Emergency rollback (main branch)
# 1. Revert the PR that added landing page
git revert <commit-hash>
git push origin main

# 2. GitHub Pages will re-deploy previous version
# 3. index.html reverts to playable story
# 4. All bookmarks/links restored

# Temporary: <5 minutes downtime while re-deployment occurs
```

**Low Risk:**
- All existing URLs (proofread.html, graph.html, etc.) unaffected
- Only index.html changes
- Worst case: Revert restores previous behavior immediately

## Open Questions for Developer

**None** - Design is complete and ready for implementation.

Developer should:
1. Read this design document thoroughly
2. Implement landing page HTML at `/home/user/NaNoWriMo2025/landing/index.html`
3. Modify workflow as specified
4. Update README.md and PR comment template
5. Test using strategy above
6. Create PR with all changes

If implementation questions arise during TDD, escalate back to Architect.

## Success Metrics

**Quantitative (from PRD lines 204-208):**

- [x] README "Outputs" section reduced by >50% (4 bullets → 2-3 lines)
- [x] PR comment reduced by >40% (12 lines preview/deployment → 7 lines)
- [x] Landing page loads in <1 second (static HTML)
- [x] All 6 format links functional

**Qualitative (from PRD lines 210-213):**

- [x] First-time visitors understand "this is a story to play" within 3 seconds
- [x] Writers can find any output format from landing page without hunting
- [x] PR reviewers access all previews through one entry point

## References

- **PRD:** `/home/user/NaNoWriMo2025/features/landing-page.md`
- **Current Architecture:** `/home/user/NaNoWriMo2025/ARCHITECTURE.md`
- **Standards:** `/home/user/NaNoWriMo2025/STANDARDS.md`
- **Metrics Template** (styling reference): `/home/user/NaNoWriMo2025/formats/metrics/template.html.jinja2`
- **GitHub Workflow:** `/home/user/NaNoWriMo2025/.github/workflows/build-and-deploy.yml`

## Appendix: Complete Landing Page HTML Structure

**File:** `/home/user/NaNoWriMo2025/landing/index.html`

**Structure Overview:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NaNoWriMo 2025 - Interactive Fiction</title>
  <style>
    /* Embedded CSS - consistent with metrics.html */
    /* Sections: Reset, Layout, Header, Hero, Cards, Responsive */
  </style>
</head>
<body>
  <header class="header">
    <h1>NaNoWriMo 2025</h1>
    <p class="subtitle">Interactive Fiction Project</p>
  </header>

  <main class="container">

    <!-- Hero Section: Play CTA -->
    <section class="hero">
      <a href="play.html" class="play-button">▶ Play the Story</a>
      <p class="tagline">An interactive narrative with branching paths</p>
    </section>

    <!-- Writer Tools Section -->
    <section class="section">
      <h2>Writer Tools</h2>
      <div class="format-grid">
        <!-- 4 cards: Proofread, Metrics, All Paths, Story Bible -->
      </div>
    </section>

    <!-- Technical Tools Section -->
    <section class="section">
      <h2>Technical Tools</h2>
      <div class="format-grid">
        <!-- 1 card: Graph Visualization -->
      </div>
    </section>

  </main>
</body>
</html>
```

**Developer will implement full HTML based on this structure and design specifications above.**
