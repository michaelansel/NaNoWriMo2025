# Feature PRD: Story Bible

**Status:** In Progress
**Owner:** Product Manager
**Priority:** HIGH
**Target:** Active (December 2025)

> **Note:** This is the detailed feature specification for the Story Bible output format, one of six formats listed in [Multiple Output Formats](multiple-output-formats.md). See that document for a high-level overview of all output formats. This document provides full acceptance criteria, user stories, and detailed requirements for the Story Bible format.

---

## Executive Summary

Writers creating branching narratives need a canonical reference that captures everything mentioned in their story—characters, locations, items, world rules—and distinguishes between **constants** (facts always true regardless of player choices) and **variables** (facts determined by player actions). The Story Bible automatically extracts and organizes this information, showing writers what's established as canon vs what varies by player choice.

**Key Capabilities:**
- **Complete entity detection:** Captures ALL named characters, locations, and items (including mentions in dialogue, possessive phrases, and indirect references)
- **Constants vs Variables:** Distinguishes facts true in all paths from player-determined outcomes
- **Zero Action State:** Shows what happens to each character if the player does nothing
- **Evidence-based:** Every fact cites source passages by name (verifiable in your source files)
- **Deduplication:** Merges duplicate facts while preserving all evidence citations
- **Published to GitHub Pages:** Automatically generated HTML after each build
- **Post-build artifact:** Generated automatically, never blocks deployment

**What This Feature Does:**
- Extracts and displays Story Bible after each build
- Human-readable HTML for authors on GitHub Pages
- NOT blocking CI—purely informational/additive

---

## User Problem

**For collaborative branching narrative writers:**
- Authors need to remember what's canon vs player-determined
- Easy to contradict your own world-building across different branches
- Characters mentioned only in dialogue don't appear in reference materials
- Possessive references like "Miss Rosie's beef stew" get overlooked
- No single source showing "what's always true" vs "what depends on player choices"
- Hard to explain to AI assistants which facts are immutable
- New collaborators lack context about established lore

**Real-World Pain Points:**
- "Is the magic system a constant (always exists) or a variable (player discovers it)?"
- "What's the character's starting state before any player action?"
- "Why isn't Marcie in the Story Bible? She's mentioned four times in dialogue."
- "Did we establish that the city is always on the coast, or does that vary by path?"
- "I'm writing a new branch—what facts must I preserve vs what can I change?"

---

## User Stories

### Story 1: Author Reviewing World Constants
**As a** writer adding new story content
**I want** to see what facts are established as constants
**So that** I can avoid contradicting the canon

**Acceptance Criteria:**
- Story Bible displays list of world constants (facts true in all paths)
- Constants organized by category (world rules, character identities, setting, timeline)
- Each constant shows evidence (which passages establish this fact)
- Clear distinction between constants and variables
- Can reference Story Bible before writing new content

---

### Story 2: Complete Character Census
**As a** writer reviewing my story
**I want** to see EVERY named character mentioned anywhere in the story
**So that** nothing mentioned in dialogue or passing references is lost

**Acceptance Criteria:**
- Story Bible captures all characters with speaking roles or significant mentions
- Includes characters mentioned only in dialogue ("when Marcie was with us")
- Includes characters in possessive form ("Miss Rosie's beef stew")
- Includes characters in indirect references ("Josie fell out of a tree")
- Minor characters appear alongside protagonists
- Each character shows ALL passages where they're mentioned (by passage name I can verify in source)

---

### Story 3: Collaborator Understanding Established Lore
**As a** new collaborator joining the project
**I want** to quickly understand what's been established about the world
**So that** I can write content that fits the existing story

**Acceptance Criteria:**
- Story Bible provides comprehensive overview of world facts
- Organized by topic for easy navigation
- Shows "zero action state" for each character
- Explains world rules and setting constants
- Can read Story Bible in browser (HTML format)
- Evidence references passage names I can find in source files

---

### Story 4: Distinguishing Constants from Variables
**As a** writer designing branching narratives
**I want** to understand what varies by player choice vs what's always true
**So that** I can design meaningful choices that respect established canon

**Acceptance Criteria:**
- Story Bible separates constants from variables
- Constants: facts true in all paths regardless of player action
- Variables: facts that depend on player choices
- Examples showing the distinction
- Clear definitions and categorization rules

---

### Story 5: Zero Action State Reference
**As a** writer creating character arcs
**I want** to know each character's "zero action state"
**So that** I understand the baseline before player intervention

**Acceptance Criteria:**
- Story Bible documents zero action state for each character
- Zero action state: what happens if player does nothing
- Shows character's starting situation, default trajectory
- Helps writers understand baseline vs player-influenced outcomes
- Distinguishes character constants (identity, background) from variables (fate, relationships)

---

### Story 6: Unified View Without Duplication
**As a** writer reviewing the Story Bible
**I want** to see each fact presented once with all supporting evidence
**So that** I can quickly understand the world without reading duplicate entries

**Acceptance Criteria:**
- Story Bible presents unified view of facts (not per-passage duplication)
- Each fact shows ALL passages that mention it (complete evidence trail)
- Facts mentioned in multiple passages are deduplicated intelligently
- Similar facts from different passages are combined when appropriate
- Contradictory facts are kept separate and flagged
- Can still verify evidence by searching for passage names in source files

---

## Feature Behavior

### What the Story Bible Contains

**Characters:**
- ALL named characters (including brief mentions, dialogue-only, possessive references)
- Character identities (constants): who they are, background, core traits
- Zero action state: what happens to them if player does nothing
- Character variables: outcomes that depend on player choices
- Evidence: which passages mention each character (by passage name)

**Locations:**
- Named places, buildings, geographic features
- Setting constants (city is on the coast, Academy is central institution)
- Location relationships (entrance to the cave, Academy library)

**Items/Objects:**
- Named items, artifacts, weapons, tools, food
- Unique objects referenced across passages
- Item relationships (Miss Rosie's beef stew → links character to item)

**World Rules:**
- Constants about how the world works (magic system exists, technology level)
- Rules true in all paths regardless of player action

**Timeline:**
- Events that happened before the story starts
- Historical facts established across all paths

**Organizations/Groups:**
- Named groups, institutions, collectives
- Group membership (current and former)

---

### Constants vs Variables vs Zero Action State

**Constants** (always true regardless of player action):
- **World Rules:** Magic system exists, technology level, physical laws
- **Character Identities:** Names, backgrounds, core traits
- **Setting:** Geography, landmarks, historical events before story start
- **Starting State:** The situation at the very beginning before player acts

**Variables** (determined by player choices):
- **Events:** What happens during the story
- **Character Fates:** Who lives or dies based on player choices
- **Relationships:** Character dynamics that evolve based on player actions
- **Items/Resources:** What the player finds or obtains
- **Outcomes:** Endings and consequences of player decisions

**Zero Action State** (default trajectory if player does nothing):
- What happens to each character if player makes no choices
- Baseline for understanding player impact
- Helps distinguish character constants (identity) from variables (fate)

**Example:**
- **Constant:** "Javlyn is a student at the Academy" (true in all paths)
- **Variable:** "Javlyn masters the magic" (depends on player helping them)
- **Zero Action State:** "Javlyn struggles with magic and eventually gives up" (default if player doesn't intervene)

---

### Complete Entity Detection

**Goal:** Extract named entities using all standard reference patterns. Prioritize recall over precision (better to include borderline entities than miss clear ones).

**Required Detection Patterns:**

1. **Direct character appearances:** Characters with dialogue or scenes
2. **Dialogue mentions:** "when Marcie was with us" → Marcie detected
3. **Possessive references:** "Miss Rosie's famous beef stew" → Miss Rosie detected
4. **Indirect references:** "Josie fell out of a tree" → Josie detected
5. **Items named after people:** "Miss Rosie's beef stew" → beef stew (item) + Miss Rosie (character)
6. **Locations mentioned in passing:** "the cave entrance" → cave detected
7. **Organizations via pronouns:** "we" and "us" in dialogue → group membership inferred

**Entity normalization:**
- Titles preserved: "Miss Rosie" (not "Rosie")
- Possessives stripped: "Rosie's" becomes "Rosie"
- Case-insensitive: "Marcie" = "marcie"
- Same entity across passages: aggregated into single entry

**Minimal information accepted:**
- Entities appear even if mentioned only once
- "Marcie (mentioned 4 times, former group member)" is valid
- "Miss Rosie (mentioned 1 time, makes beef stew)" is valid
- No entity excluded due to "not enough information"

---

### Deduplication: When to Merge vs Keep Separate

**Purpose:** Reduce duplication while preserving complete information and evidence.

**MERGE when:**
- **Identical facts, different wording:**
  - "Javlyn is a student at the Academy"
  - "Javlyn attends the Academy as a student"
  - **Result:** Single fact citing both passages

- **Same fact with additive details:**
  - "The city is on the coast"
  - "The city sits on the eastern coast"
  - **Result:** "The city is on the eastern coast" (combined details, both passages cited)

- **Repeated world rules:**
  - Multiple passages mention "Magic requires formal training"
  - **Result:** Single entry with complete evidence list

**KEEP SEPARATE when:**
- **Contradictory facts:**
  - "The war ended 10 years ago"
  - "The war ended 2 years ago"
  - **Result:** Both facts shown, flagged as "CONFLICT"

- **Path-specific variations:**
  - Path 1: "Javlyn masters the magic"
  - Path 2: "Javlyn gives up on magic"
  - **Result:** Listed under "Variables" section

- **Different aspects of same subject:**
  - "Javlyn is a student" (identity)
  - "Javlyn struggles with magic" (current state)
  - **Result:** Kept separate (different types of facts)

- **Uncertain whether same fact:**
  - "The city has a grand library"
  - "The Academy library contains ancient texts"
  - **Result:** Kept separate (conservative approach—unclear if same building)

**Conservative deduplication:** When uncertain, keep separate. Better slight redundancy than losing meaningful distinctions.

**Evidence preservation:** ALWAYS cite ALL passages that mention a fact. Merged facts show complete evidence list.

---

### Evidence and Verification

**Evidence format:**
- Each fact cites source passages by name
- Passage names match your Twee source files
- Can verify claims by searching for passage name (e.g., ":: Academy Entrance")
- No path hashes or implementation-dependent IDs

**Example:**
- Fact: "Magic system exists"
- Evidence: Passage "Start", Passage "Academy Introduction", Passage "Javlyn's Struggle"
- You can search your source for ":: Start" to verify the claim

---

### Output Format

**story-bible.html:**
- Published to GitHub Pages automatically after each build
- Organized sections: World Constants, Characters, Locations, Items, Variables
- Each fact shows evidence (passage names)
- Visual distinction between constants and variables
- "Zero action state" for each character
- Conflicts flagged prominently

**When Generated:**
- Automatically after each build when you push or merge changes
- Not in critical path (build succeeds even if Story Bible generation fails)
- Graceful degradation: missing Story Bible doesn't block deployment

---

### How It Works (User Perspective)

**Two-Phase Model:**
The Story Bible uses a two-phase approach to balance speed with thoroughness:

1. **Extract Phase (Webhook)** - AI-powered extraction updates the cache
2. **Render Phase (CI Build)** - Fast HTML generation from cache

This separation means:
- Every build is fast (no AI processing in CI)
- Extraction runs when you need it (auto after builds + manual webhook)
- Story Bible is always available but may be one build behind if extraction is in progress

---

**Webhook Command:**
```
/extract-story-bible
```
Use this webhook command (as a PR comment) to trigger Story Bible extraction and updates.

---

**Phase 1: Extract Phase (Updates Cache)**

**When it runs:**
- Automatically after every successful build (webhook triggered by CI)
- Manually via `/extract-story-bible` comment on PR

**What it does:**
1. Processes each passage in your Twee source files
2. Extracts all entities (characters, locations, items) and facts using Ollama AI
3. Deduplicates facts across passages
4. Commits results to repository cache (`cache/story-bible/`)

**Performance:**
- Uses AI (Ollama), so takes longer than build
- Changed passages re-extracted, unchanged passages reuse cached results (faster)
- Failed passages NOT cached (automatic retry next time)
- Partial results still useful (some facts better than none)

---

**Phase 2: Render Phase (Generates HTML)**

**When it runs:**
- Every build (every push, every merge)

**What it does:**
1. Reads cached extraction results from `cache/story-bible/`
2. Renders HTML and JSON (fast, deterministic, no AI needed)
3. Published to GitHub Pages automatically

**Performance:**
- Very fast (no AI, just rendering)
- Gracefully handles missing cache (shows informational placeholder)
- Build always succeeds (Story Bible is informational, not blocking)

---

**Typical Workflow:**

**First-time setup:**
1. Create a PR and comment with `/extract-story-bible` webhook command
2. Extract Phase runs (AI processes passages, commits cache)
3. Next build uses cache to render HTML instantly

**Daily writing:**
1. Push changes → Build runs (renders from cache if available)
2. Automatic webhook triggers Extract Phase after build completes
3. Extract Phase updates cache with new facts
4. Next build shows updated Story Bible

**If you need Story Bible immediately:**
1. Comment `/extract-story-bible` on your PR
2. Wait for Extract Phase to complete
3. Push a trivial change (or wait for next build)
4. Build renders updated HTML

**If extraction fails:**
- Build still succeeds (renders placeholder or stale cache)
- Failed passages NOT cached (automatic retry next extraction)
- Story Bible always available, just may be outdated

---

## Edge Cases (User Scenarios)

### Edge Case 1: Character Mentioned Only in Dialogue
**Scenario:** Marcie mentioned 4 times in dialogue but never appears directly

**User Experience:**
- Story Bible lists Marcie as a character
- Shows all 4 passages where she's mentioned
- Facts: "Former group member", "Left or lost"
- Marked as "lightly mentioned" character (limited direct appearance)

---

### Edge Case 2: Possessive Reference
**Scenario:** "Miss Rosie's famous beef stew" is the only mention

**User Experience:**
- Story Bible lists Miss Rosie (character) and beef stew (item)
- Shows relationship: beef stew associated with Miss Rosie
- Fact: "Makes beef stew (famous for it)"
- Evidence cites passage name where mention appears

---

### Edge Case 3: Contradictory Facts
**Scenario:** Different passages establish conflicting constants

**User Experience:**
- Story Bible shows both facts
- Flagged as "⚠️ CONFLICT: Authors need to resolve"
- Evidence shows which passages establish each version
- You decide which is canon and update passages accordingly

---

### Edge Case 4: Entity Mentioned Once
**Scenario:** "Josie fell out of a tree" (single passing reference)

**User Experience:**
- Story Bible lists Josie as a character
- Shows passage where mentioned
- Minimal facts: "Known to narrator", "Experienced tree-falling incident"
- Appears in Story Bible even with limited information

---

### Edge Case 5: Empty Story or Few Passages
**Scenario:** Story has very few passages, no constants established yet

**User Experience:**
- Story Bible generates with minimal content
- Shows: "Story Bible will populate as story develops"
- No errors, graceful handling
- Still shows "zero action state" of initial passages

---

### Edge Case 6: Summarization Fails
**Scenario:** AI summarization encounters error after successful extraction

**What You See:**
- Story Bible displays successfully with per-passage organization (not unified)
- Header message: "Showing per-passage view (summarization pending)"
- Facts appear under each passage heading (some duplication across passages)
- All extracted information is visible

**What You Can Do:**
- Read facts by passage to find information you need
- Search page (Ctrl+F) to find specific characters or facts
- Wait for summarization to retry on next build
- Report persistent failures to team

---

### Edge Case 7: Constants Change Over Time
**Scenario:** You revise world-building (e.g., change magic system)

**What You See:**
- Story Bible updates to reflect your latest changes after each build
- Current constants shown based on all current passages
- No historical comparison shown in Story Bible itself

**What You Can Do:**
- Review updated Story Bible to verify changes took effect
- Check git history to see previous versions if needed
- Update related passages to maintain consistency with new constants
- Future: System may flag new content that contradicts established constants

---

### Edge Case 8: Ambiguous Zero Action State
**Scenario:** Unclear what "doing nothing" means (all paths require player choice)

**User Experience:**
- Story Bible shows: "Zero action state ambiguous—all paths require player action"
- May show: "Default state unknown—player must choose"
- Not an error, just documenting the ambiguity

---

### Edge Case 9: Intentional Mysteries
**Scenario:** Character says "I'm a student" but later revealed as spy

**User Experience:**
- Story Bible may flag as contradiction
- You can note: "Intentional mystery—character identity revealed later"
- Future consideration: Could mark intentional mysteries to suppress warnings

---

### Edge Case 10: Same Fact, Richer Details Over Time
**Scenario:** Multiple passages add details to same fact

**User Experience:**
- Passage A: "The city is coastal"
- Passage B: "The city faces the eastern sea"
- **Story Bible:** "The city is on the eastern coast" (combined details)
- Evidence cites both passages
- Richer fact from merged information

---

### Edge Case 11: Dual-Type Entities
**Scenario:** "Academy" = location (building) + organization (institution)

**User Experience:**
- Story Bible shows Academy under both categories
- Location facts: "Is a building", "Has rooms/areas"
- Organization facts: "Teaches magic", "Has students"
- Or shown as single entity with dual type

---

### Edge Case 12: Generic vs Specific References
**Scenario:** "A lantern" (generic) vs "the lantern" (specific)

**User Experience:**
- Named items: Always appear ("Excalibur", "the One Ring")
- "The [noun]" (specific instance): Appears ("the lantern")
- "A [noun]" (generic): Generally not listed unless recurring
- Recurring generic: "the woman" appears multiple times → Listed as "unnamed woman"

---

### Edge Case 13: Missed Entity Detection
**Scenario:** AI fails to detect a named character you know exists

**What You See:**
- Story Bible doesn't list the character you know exists
- Character appears in source files but not in Story Bible output

**What You Can Do:**
- Report missed entity via GitHub issue or PR comment
- Development team can manually add to extraction results
- Future extraction runs may catch previously missed entities as AI improves
- Prioritize reporting characters with multiple mentions over single mentions

**System Behavior:**
- Extraction prioritizes recall over precision (better to include borderline entities)
- AI-based extraction will miss some entities—user reports help identify gaps
- Missed entities don't invalidate the usefulness of captured ones
- Manual verification and additions remain available

---

## Success Metrics

**Primary Metrics:**
- Story Bible generated successfully on every build
- HTML accessible on GitHub Pages
- JSON format valid and parseable
- All named characters extracted (verified by searching source files for character names)
- Authors reference Story Bible when writing new content

**Character Detection:**
- Captures named characters using all required detection patterns (dialogue mentions, possessive form, indirect references)
- Test by searching source files for character names and verifying they appear in Story Bible
- All recurring characters (mentioned 2+ times) appear in Story Bible
- Single-mention characters captured when using standard reference patterns
- User-reported misses addressed within one sprint (missed entities manually added if extraction gap confirmed)
- System prioritizes recall over precision (include borderline entities rather than miss clear ones)
- False positive rate acceptable (borderline entities included for completeness)

**Quality Indicators (Testable):**
- Fact distribution balanced: No single fact type exceeds 70% of total facts (testable by counting fact types)
- 100% of facts have evidence citations (testable by validation script)
- Evidence trails complete: All sources cited (testable against passage list)
- Deduplication reduces redundancy 30-50% (measurable: compare raw facts to deduplicated facts)
- Contradictions flagged (not hidden) (testable: verify conflict detection works)

**Qualitative Indicators:**
These are directional goals we cannot directly measure but inform our design decisions:
- Writers report Story Bible is useful for maintaining consistency
- New collaborators find Story Bible helpful for onboarding
- Team uses Story Bible terms in discussion ("is this a constant or variable?")
- AI assistants use Story Bible for context
- No surprises when searching for entities ("Why isn't X in here?")

**Future Considerations:**
- Validation runs automatically on PRs
- Contradictions flagged before merge
- False positive rate acceptable
- Writers trust validation feedback

---

## Acceptance Criteria Summary

### Core Functionality
- [ ] Story Bible generated as post-build artifact
- [ ] HTML format published to GitHub Pages as `/story-bible.html`
- [ ] Extracts constants, variables, and character states
- [ ] Each fact includes evidence (passage names from source)
- [ ] Clear distinction between constants and variables
- [ ] Zero action state documented for each character

### Entity Detection (Pattern Coverage)
- [ ] All required detection patterns implemented (dialogue mentions, possessive form, indirect references)
- [ ] Characters in dialogue captured ("when Marcie was with us")
- [ ] Characters in possessive form captured ("Miss Rosie's beef stew")
- [ ] Characters in indirect references captured ("Josie fell out of a tree")
- [ ] All recurring characters (2+ mentions) captured in test story
- [ ] Titles preserved in names ("Miss Rosie", not "Rosie")
- [ ] Minimal information acceptable (entities appear even if mentioned once)
- [ ] Each entity shows ALL passages where mentioned (by passage name)
- [ ] User-reported misses can be manually addressed
- [ ] System prioritizes recall over precision (includes borderline cases)

### Deduplication
- [ ] Identical facts merged with combined evidence
- [ ] Additive details from multiple passages combined
- [ ] Contradictory facts kept separate and flagged
- [ ] Conservative deduplication (when uncertain, keep separate)
- [ ] ALL evidence preserved in merged facts
- [ ] 30-50% fact reduction from deduplication

### Evidence Quality
- [ ] Evidence uses passage names (verifiable in Twee source)
- [ ] 100% of facts have evidence field populated
- [ ] Evidence citations match source passages
- [ ] Can search for passage names in source files (e.g., ":: Academy Entrance")
- [ ] Evidence contains fact claim (or strong synonym), not just entity name mention
- [ ] Test story with 20 known facts: ≥80% have relevant supporting evidence
- [ ] Evidence quotes demonstrate the fact being claimed

### Pronoun Resolution
- [ ] Same-passage unambiguous pronouns (he/she/they) resolve to entity names
- [ ] Test story pronoun resolution: ≥70% accuracy on known test cases
- [ ] False merge rate <10% on test story with known distinct entities
- [ ] Ambiguous pronouns remain unresolved (conservative approach)
- [ ] Pronoun resolution limited to same passage (not cross-passage)

### Semantic Fact Aggregation
- [ ] Semantically equivalent facts merged (e.g., "has red hair" = "hair is red")
- [ ] All evidence from merged facts preserved in combined fact
- [ ] Conservative merging: when uncertain, keep facts separate
- [ ] Test story semantic merging: false positive merge rate <5%
- [ ] Merged facts maintain all original passage citations

### Test Story Requirements
- [ ] Canonical test story created for validation
- [ ] Test story contains ≥20 known facts with verified evidence
- [ ] Test story includes known pronoun resolution cases (documented)
- [ ] Test story includes known semantic equivalents (documented)
- [ ] Test story includes known distinct entities (to measure false merge rate)
- [ ] Test story maintained in repository for regression testing
- [ ] Test story results tracked over time to measure quality improvements

### Build Integration (Two-Phase Model)
- [ ] **Render Phase**: Integrated into automated build pipeline (every push/merge)
- [ ] **Render Phase**: Reads cache, generates HTML (fast, deterministic, no AI)
- [ ] **Render Phase**: Graceful degradation if cache missing (informational placeholder)
- [ ] **Render Phase**: Build succeeds even if cache missing or rendering fails
- [ ] **Extract Phase**: Webhook-triggered (auto after builds + manual `/extract-story-bible`)
- [ ] **Extract Phase**: Uses Ollama AI to extract entities and facts
- [ ] **Extract Phase**: Commits results to cache for next build to render
- [ ] Does NOT block deployment (either phase failing is non-fatal)

### Extraction Quality
- [ ] All named characters extracted (test by searching source files for character names and verifying they appear in Story Bible)
- [ ] Extraction succeeds for all passages (failed passages not cached and automatically retry next time)
- [ ] Fact distribution balanced (no single fact type exceeds 70% of total facts)
- [ ] Failed passages NOT cached (automatic retry on next extraction)
- [ ] Summarization falls back to per-passage view if it fails

### HTML Output
- [ ] Human-readable format organized by category
- [ ] Sections: World Constants, Characters, Locations, Items, Variables
- [ ] Each fact shows source passages
- [ ] Visual distinction between constants and variables
- [ ] Conflicts flagged prominently
- [ ] Accessible on any device with browser
- [ ] Published to GitHub Pages automatically after each build

---

## Related Documents

**Strategic:**
- [VISION.md](/home/user/NaNoWriMo2025/VISION.md) - Project vision (writers first, automation over gatekeeping)
- [ROADMAP.md](/home/user/NaNoWriMo2025/ROADMAP.md) - Product roadmap and priorities
- [PRINCIPLES.md](/home/user/NaNoWriMo2025/PRINCIPLES.md) - Core principles (transparency, multiple perspectives)

**Related Features:**
- [features/ai-copy-editing-team.md](/home/user/NaNoWriMo2025/features/ai-copy-editing-team.md) - AI Copy Editing Team (World Fact Checker uses Story Bible)
- [features/multiple-output-formats.md](/home/user/NaNoWriMo2025/features/multiple-output-formats.md) - Build artifact generation pattern

**Implementation (For Architect/Developer):**
- Technical design and architecture details will be documented separately
- This PRD focuses on WHAT users experience, not HOW it's built

---

## Timeline and Prioritization

**Target:** Active (December 2025)
**Priority:** HIGH
**Rationale:** Story Bible provides essential reference for maintaining consistency in branching narratives

**Future Enhancements (Not In Scope):**
- Advanced validation integration with CI
- Custom validation rules beyond basic extraction
- Timeline depends on user feedback and demonstrated need

---

**End of PRD**
