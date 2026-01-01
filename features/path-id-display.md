# Feature PRD: Path ID Display

**Status:** Draft
**Owner:** Product Manager
**Priority:** MEDIUM
**Target:** Future Enhancement

---

## Executive Summary

Players of branching narratives want to share their unique story experiences and compare outcomes with other players. The Path ID Display feature provides each player with a unique identifier for their specific path through the story, displayed at story endings. Players can reference their path when discussing the story or reporting issues, and can click the path ID to view a clean text version of their complete journey.

**Key Capabilities:**
- **Unique identification:** 8-character hex code uniquely identifies each path through the story
- **End-of-path display:** Path ID shown at passages with no outgoing links (story endings)
- **Readable summary:** Human-readable path summary shows key passage names (Start → Middle → End)
- **Full text access:** Clicking the hex code opens a clean text file showing the complete story path
- **Player sharing:** Players can share path IDs to compare experiences ("I got path abc123, what did you get?")
- **Bug reporting:** Players can reference specific paths when reporting issues

**What This Feature Does:**
- Displays path ID at story endings
- Generates clean text files for each unique path
- Provides clickable link from path ID to full path text
- Shows human-readable path summary alongside hex code

---

## User Problem

**For players experiencing branching narratives:**
- Players want to share their unique story experiences with friends
- "What ending did you get?" conversations lack concrete references
- Comparing story outcomes requires manually describing choices made
- Reporting bugs or issues requires vague descriptions ("I went left at the fork")
- No way to prove "I actually got this rare ending"
- Difficult to track which story branches have been explored
- Can't revisit the exact path taken without replaying and making identical choices

**Real-World Pain Points:**
- "I got a weird ending, but I can't remember exactly how I got there"
- "Did you find the secret character? What choices led to that?"
- "There's a bug in one of the endings, but I don't know how to describe my path"
- "I want to show someone the exact story I experienced, not just the final passage"
- "How do I know if I've seen all the content without tracking every choice manually?"

---

## User Stories

### Story 1: Player Sharing Story Experience
**As a** player who completed a branching story
**I want** to share a unique identifier for my specific path
**So that** I can compare experiences with other players

**Acceptance Criteria:**
- Path ID displayed at story endings (passages with no outgoing links)
- Path ID format: "Path ID: [8-char hex] (Start → Middle → End)"
- 8-character hex code uniquely identifies the path
- Human-readable summary shows key passage names
- Path ID visible without scrolling (positioned prominently at ending)
- Path ID appears only at endings, not at intermediate passages

---

### Story 2: Viewing Full Path Text
**As a** player who wants to review their complete journey
**I want** to click the path ID to see the full story text I experienced
**So that** I can read my complete path without metadata or UI chrome

**Acceptance Criteria:**
- Path ID hex code is a clickable link
- Link opens file: `dist/allpaths-clean/path-[hex].txt`
- Clean text file contains only passage content (no metadata, tags, or UI elements)
- Passages appear in order experienced by player
- File opens in browser or downloads (browser-dependent behavior acceptable)
- Link works in both local preview and deployed GitHub Pages

---

### Story 3: Bug Reporting with Path Reference
**As a** player encountering an issue in the story
**I want** to reference my specific path when reporting bugs
**So that** developers can reproduce and fix the issue

**Acceptance Criteria:**
- Player can copy path ID from ending screen
- Path ID uniquely identifies the sequence of passages taken
- Same path always generates same path ID (deterministic hashing)
- Different paths always generate different path IDs (collision rate <0.01% for stories with <10,000 unique paths)
- Path ID can be shared in text format (no special characters requiring escaping)
- Developers can map path ID to specific passage sequence for debugging

---

### Story 4: Comparing Paths with Friends
**As a** player discussing the story with friends
**I want** to quickly see if we experienced the same path
**So that** we can identify differences in our choices and outcomes

**Acceptance Criteria:**
- Path ID is short enough to communicate verbally or in chat (8 characters)
- Human-readable summary provides quick context without opening full text
- Path summary shows start, key middle passages, and ending passage names
- Path summary length adapts to path complexity (3-5 passage names shown)
- Players can visually compare path IDs at a glance
- Same ending reached via different paths shows different path IDs

---

## Feature Behavior

### Display Location and Format

**Where Displayed:**
- Path ID appears at story endings (passages with no outgoing links)
- Positioned below final passage text, above any restart/navigation UI
- Styled distinctly from passage content (different font, color, or border)

**Display Format:**
```
Path ID: a1b2c3d4 (Awakening → Forest Path → Hidden Cave → Secret Ending)
```

**Components:**
- Label: "Path ID:"
- Hex code: 8-character lowercase hex (clickable link)
- Path summary: (Start Passage → Middle Passages → End Passage)

**Path Summary Rules:**
- Always shows start passage and end passage
- Shows 1-3 key middle passages (selected based on passage length or story structure)
- Uses passage titles from Twee source
- Limited to ~80 characters total for readability
- If path is short (<5 passages), shows all passages
- If path is long (>10 passages), shows representative sample

---

### Clean Text File Generation

**File Location:**
- `dist/allpaths-clean/path-[8-char-hex].txt`
- Example: `dist/allpaths-clean/path-a1b2c3d4.txt`

**File Content:**
- Passage titles as headers
- Passage text content only (no Twee metadata, tags, or special syntax)
- Passages in order experienced by player
- Clear separation between passages (blank lines or visual dividers)
- No link text or choice UI (linear reading experience)

**File Generation Timing:**
- Generated during build process (pre-computed for all possible paths)
- No runtime generation required (player clicks open pre-existing file)
- Files deployed to GitHub Pages alongside story

**Performance Consideration:**
- Number of files equals number of unique paths
- For stories with exponential branching, file count may be large
- Clean text files are small (text only, no markup)
- Acceptable limit: ~10,000 unique paths (10,000 small text files)

---

### Path ID Generation (8-Character Hex Hash)

**Hashing Approach:**
- Deterministic hash of passage sequence (passage IDs or names)
- 8 hex characters = 32 bits = ~4 billion unique values
- Collision risk negligible for stories with <100,000 unique paths
- Same path always generates same hash (reproducible)
- Different paths always generate different hashes (or collision flagged)

**Hash Input:**
- Ordered list of passage IDs or passage names
- Consistent ordering (first passage to last passage)
- Normalized format (case-insensitive, whitespace-trimmed)

**Hash Algorithm:**
- Standard hash function (MD5, SHA-256, etc.) truncated to 8 hex chars
- Or custom hash optimized for short paths
- Deterministic and consistent across builds

**Collision Handling:**
- If collision detected during build, flag error
- Option: Use first 8 chars + incremental suffix (a1b2c3d4-1, a1b2c3d4-2)
- Goal: Zero collisions for typical story sizes (<10,000 paths)

---

### Integration with Existing Systems

**AllPaths Format:**
- Path ID Display uses same path data as AllPaths format
- Clean text files sourced from AllPaths generation
- No duplication of path enumeration logic

**Build Process:**
- Path ID generation integrated into AllPaths build step
- Clean text files generated alongside allpaths.html
- Path ID display code injected into Harlowe output (or added to story HTML template)

**Passage Detection (Story Endings):**
- Ending passages detected by absence of outgoing links
- Same logic as Twine/Twee standard ending detection
- Works for all endings (good, bad, neutral, secret, etc.)

---

## Edge Cases

### Edge Case 1: Multiple Endings from Same Path
**Scenario:** Story has multiple final passages reachable from identical earlier paths

**Expected Behavior:**
- Each ending passage shows different path ID (path includes the ending passage)
- Path summary shows same middle passages but different ending passage name
- Players can distinguish endings even if earlier path was identical

**Acceptance Criteria:**
- Path hash includes ending passage
- Different endings generate different path IDs
- Path summary clearly shows ending passage name

---

### Edge Case 2: Very Short Story (Single Passage)
**Scenario:** Story has only one passage (linear story or demo)

**Expected Behavior:**
- Path ID still displayed (single-passage path)
- Path summary shows only one passage name
- Clean text file contains only one passage

**Acceptance Criteria:**
- Path ID appears even for single-passage stories
- No errors or missing UI elements
- Clean text file generated successfully

---

### Edge Case 3: Very Long Path (50+ Passages)
**Scenario:** Player takes longest possible path through complex story

**Expected Behavior:**
- Path ID still 8 characters (hash length independent of path length)
- Path summary shows representative sample (5 key passages max)
- Clean text file contains all passages (may be very long)

**Acceptance Criteria:**
- Path summary does not exceed ~100 characters
- Clean text file renders all passages in order
- No truncation of clean text content

---

### Edge Case 4: Path ID Collision (Rare)
**Scenario:** Two different paths generate same 8-character hash (unlikely but possible)

**Expected Behavior:**
- Build process detects collision and flags error
- Option 1: Fails build with clear error message indicating collision
- Option 2: Uses collision resolution strategy (e.g., incremental suffix)

**Acceptance Criteria:**
- Collision detected during build (not at runtime)
- Clear error message if collision occurs
- Developer can resolve collision (adjust hash function or use suffix strategy)

---

### Edge Case 5: Passage Names with Special Characters
**Scenario:** Passage titles contain symbols, Unicode, or markup

**Expected Behavior:**
- Path summary displays passage names as-is (or sanitized for display)
- Clean text file uses original passage names
- No broken rendering or encoding issues

**Acceptance Criteria:**
- Unicode passage names render correctly in path summary
- Special characters in passage names do not break HTML rendering
- Clean text file encoding supports Unicode (UTF-8)

---

### Edge Case 6: Player Reaches Ending via Browser Back Button
**Scenario:** Player uses browser navigation to reach an ending (non-linear path)

**Expected Behavior:**
- Path ID reflects canonical path (forward navigation only)
- Browser history navigation does not affect path ID
- Path ID may not match player's actual browsing behavior if they used back button

**Acceptance Criteria:**
- Path ID based on Twine state history (forward choices only)
- Back button navigation does not alter displayed path ID
- Path ID matches what would be generated by making same choices without using back button

**Note:** This is an acceptable limitation. Path ID represents canonical story path, not browser navigation history.

---

### Edge Case 7: Clean Text File Missing or Not Generated
**Scenario:** Build process fails to generate clean text file for a path, or file is deleted

**Expected Behavior:**
- Path ID still displayed (hash can be generated without file)
- Clicking path ID link shows browser 404 error or "file not found"
- Player experience gracefully degrades (path ID visible, full text unavailable)

**Acceptance Criteria:**
- Path ID display does not depend on clean text file existence
- Broken link acceptable (browser handles 404)
- Build warnings if clean text generation incomplete

---

### Edge Case 8: Local Preview vs Deployed GitHub Pages
**Scenario:** Player tests locally (file:// protocol) vs deployed GitHub Pages (https://)

**Expected Behavior:**
- Path ID displays in both contexts
- Clean text file link works in both contexts (relative path)
- No environment-specific behavior differences

**Acceptance Criteria:**
- Path ID link uses relative path (e.g., `allpaths-clean/path-abc123.txt`)
- Works when opened from local `dist/` folder
- Works when deployed to GitHub Pages

---

## Success Metrics

**Primary Metrics:**
- Path ID displays at all story endings (100% of ending passages)
- Clicking path ID opens clean text file successfully (no 404 errors for generated files)
- Path IDs are unique (zero collisions for test story with <1,000 unique paths)
- Clean text files generated for all unique paths during build

**Quality Indicators (Testable):**
- Test story with 20 known paths: all 20 generate unique path IDs (100% uniqueness)
- Test story ending passages: path ID appears at all endings (100% coverage)
- Path summary length ≤100 characters for all paths in test story
- Clean text files contain only passage content (no metadata or markup)
- Same path replayed generates identical path ID (100% determinism)

**Qualitative Indicators:**
These are directional goals we cannot directly measure but inform our design decisions:
- Players find path IDs useful for sharing experiences
- Bug reports include path IDs for easier reproduction
- Players use path summary to quickly compare outcomes
- Path ID length is practical for verbal/chat communication

---

## Acceptance Criteria Summary

### Core Functionality
- [ ] Path ID displays at story endings (passages with no outgoing links)
- [ ] Path ID format: "Path ID: [hex] (passage summary)"
- [ ] 8-character hex code uniquely identifies path
- [ ] Human-readable path summary shows start, middle, and end passage names
- [ ] Path ID appears only at endings, not at intermediate passages

### Path ID Generation
- [ ] Deterministic hash of passage sequence (same path = same hash)
- [ ] 8-character lowercase hex code
- [ ] Collision rate <0.01% for stories with <10,000 unique paths
- [ ] Hash includes ending passage (different endings = different IDs)
- [ ] Collision detection during build (error if collision occurs)

### Clean Text File
- [ ] Clean text files generated for all unique paths
- [ ] File location: `dist/allpaths-clean/path-[hex].txt`
- [ ] File content: passage text only (no metadata, tags, or markup)
- [ ] Passages in order experienced by player
- [ ] UTF-8 encoding supports Unicode passage names

### Path ID Link
- [ ] Path ID hex code is clickable link
- [ ] Link target: `allpaths-clean/path-[hex].txt` (relative path)
- [ ] Link works in local preview (file:// protocol)
- [ ] Link works in deployed GitHub Pages (https://)
- [ ] File opens in browser or downloads (browser-dependent behavior acceptable)

### Path Summary
- [ ] Path summary shows start passage, key middle passages, and end passage
- [ ] Path summary length ≤100 characters
- [ ] Short paths (<5 passages) show all passages
- [ ] Long paths (>10 passages) show representative sample (3-5 passages)
- [ ] Passage names use Twee source titles
- [ ] Special characters and Unicode render correctly

### Display Styling
- [ ] Path ID positioned below final passage text
- [ ] Path ID visually distinct from passage content (different styling)
- [ ] Path ID visible without scrolling (positioned prominently)
- [ ] Path ID does not interfere with restart/navigation UI
- [ ] Mobile-friendly display (readable on small screens)

### Build Integration
- [ ] Path ID generation integrated into AllPaths build step
- [ ] Clean text files generated during build (no runtime generation)
- [ ] Build succeeds even if clean text generation incomplete (non-blocking)
- [ ] Build warnings if path ID collisions detected
- [ ] Path ID display code injected into Harlowe output

### Edge Case Handling
- [ ] Single-passage stories show path ID correctly
- [ ] Very long paths (50+ passages) display correctly
- [ ] Multiple endings from same earlier path generate different IDs
- [ ] Passage names with special characters render without breaking HTML
- [ ] Missing clean text file degrades gracefully (path ID still shown, link 404s)
- [ ] Browser back button navigation does not affect path ID

---

## Related Documents

**Strategic:**
- [VISION.md](/home/ubuntu/Code/NaNoWriMo2025/VISION.md) - Project vision (readers first, transparency)
- [ROADMAP.md](/home/ubuntu/Code/NaNoWriMo2025/ROADMAP.md) - Product roadmap and priorities

**Related Features:**
- [features/multiple-output-formats.md](/home/ubuntu/Code/NaNoWriMo2025/features/multiple-output-formats.md) - AllPaths format (source of path data)
- [features/landing-page.md](/home/ubuntu/Code/NaNoWriMo2025/features/landing-page.md) - Reader-focused entry point pattern

**Implementation (For Architect/Developer):**
- Technical design for path hashing, clean text generation, and UI integration to be documented separately
- This PRD focuses on WHAT players experience, not HOW it's built

---

## Non-Goals (Out of Scope)

**Not Included in This Feature:**
- **Path history tracking across multiple playthroughs:** Path ID identifies single playthrough, not aggregated history
- **Path comparison UI:** Players compare path IDs manually, no automated diff or comparison view
- **Path search or discovery:** No UI for browsing all possible path IDs
- **Analytics or usage tracking:** Path IDs are for player use, not telemetry
- **Path replay functionality:** Clicking path ID shows text, not interactive replay
- **Social sharing buttons:** Players copy/paste path ID manually, no built-in social features
- **Leaderboards or achievement tracking:** Path ID is informational, not gamified

**Future Considerations (Not In Scope):**
- Path visualization (graph showing player's specific path)
- Path statistics (e.g., "20% of players took this path")
- Path suggestions (e.g., "Try path xyz123 for a different ending")

---

## Timeline and Prioritization

**Target:** Future Enhancement
**Priority:** MEDIUM
**Rationale:** Path ID Display enhances player experience and supports community engagement, but is not essential for core story playback. Useful for players who want to share experiences or report issues, but not a blocking feature for initial release.

**Dependencies:**
- AllPaths format must be implemented (provides path enumeration)
- Clean text generation logic (may reuse existing AllPaths text extraction)

**Future Enhancements (Post-MVP):**
- Path comparison tools (automated diff between two path IDs)
- Path statistics (how many players reached each ending)
- Path visualization (graphical representation of specific path)

---

**End of PRD**
