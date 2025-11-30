# Feature PRD: Story Bible

**Status:** Planned
**Owner:** Product Manager
**Priority:** Medium (Phase 1: Informational Tool)
**Target:** December 2025 (Post-NaNoWriMo refinement phase)

---

## IMPORTANT: Bug Fixes and Behavioral Clarifications

**Updated:** 2025-11-30

This PRD has been updated to address two critical bugs and clarify correct behavior:

### Bug Fix 1: Failed Extractions Must NOT Be Cached
**Problem:** When Ollama fails to extract facts from a passage (timeout, error), the passage was being marked in the cache as if it succeeded. This caused incremental mode to skip failed passages on subsequent runs.

**Correct Behavior:**
- Only successful extractions are added to `story-bible-cache.json`
- Failed passages are logged with error details but NOT cached
- Next incremental run automatically retries failed passages (they're not in cache)
- See: Edge Case 8, Acceptance Criteria "Cache Handling"

### Bug Fix 2: Build Must Read Cache First (Not Extract)
**Problem:** The CI build was trying to call Ollama to extract facts, failing (no Ollama in CI), and generating empty placeholder HTML. But the cache was already committed to the repo by the webhook service.

**Correct Behavior:**
- Build checks for `story-bible-cache.json` in repository FIRST
- If cache exists → Render HTML/JSON from cache (no Ollama needed)
- If cache missing → Generate placeholder (no Ollama attempted)
- Build NEVER calls Ollama (extraction is webhook-only)
- See: "Workflow Separation: Build vs Webhook", Acceptance Criteria "Build Integration"

### Workflow Clarification:
```
/extract-story-bible (webhook) → Extracts with Ollama → Commits cache to repo
CI build → Reads cache from repo → Renders HTML/JSON from cache
```

**Key Changes:**
- Added "Workflow Separation: Build vs Webhook" section
- Updated "How It's Generated" with cache-first approach
- Added Edge Cases 8 & 9 for failed extractions and cache behavior
- Updated Acceptance Criteria with cache handling requirements
- Moved cache strategy from "Open Questions" to "Resolved Design Decisions"

---

## Executive Summary

Writers need a canonical source of truth about their story world that distinguishes between **constants** (facts always true regardless of player choices) and **variables** (facts determined by player actions). This Story Bible feature extracts and maintains world knowledge to help authors avoid contradictions and collaborators understand established lore.

**Key Capabilities:**
- Extract world constants vs variables from story passages
- Display "zero action state" for each character (what happens if player does nothing)
- Generate human-readable and machine-readable story bible
- Post-build artifact (HTML + JSON) for authors and AI assistants
- Frame extraction as "world reconstruction" not summarization

**Two-Phase Approach:**

**Phase 1 (Immediate - Informational):**
- Extract and display story bible after each build
- Human-readable HTML format for authors
- Machine-readable JSON format for future AI integration
- NOT blocking CI - purely informational/additive
- Post-build artifact (generated after successful build)

**Phase 2 (Future - Integration with Continuity Checking):**
- Integrate Story Bible validation into existing AI Continuity Checking
- When continuity checking runs, also validate against Story Bible
- Flag contradictions of constants in same PR comment
- Still informational, not blocking
- Combined report: path consistency + world consistency

**Strategic Alignment:**
This feature complements AI Continuity Checking:
- **AI Continuity Checking:** Validates individual story paths for internal consistency
- **Story Bible:** Extracts cross-path canonical facts about the world

---

## User Problem

**For collaborative branching narrative writers:**
- Authors need to remember what's canon vs player-determined
- Collaborators joining mid-project need to understand established lore
- Easy to contradict your own world-building across different branches
- No single reference for "what's always true" vs "what depends on player choices"
- Hard to explain to AI assistants what facts are immutable

**Pain Points:**
- "Is the magic system a constant (always exists) or a variable (player discovers it)?"
- "What's the character's starting state before any player action?"
- "Did we establish that the city is always on the coast, or does that vary by path?"
- "I'm writing a new branch - what facts must I preserve vs what can I change?"
- "New collaborator: What do I need to know about the world before I write?"

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

### Story 2: Collaborator Understanding Established Lore
**As a** new collaborator joining the project
**I want** to quickly understand what's been established about the world
**So that** I can write content that fits the existing story

**Acceptance Criteria:**
- Story Bible provides comprehensive overview of world facts
- Organized by topic for easy navigation
- Shows "zero action state" for each character
- Explains world rules and setting constants
- Can read Story Bible in browser (HTML format)

---

### Story 3: AI Assistant Using Story Bible
**As a** developer integrating AI continuity checking
**I want** machine-readable story bible data
**So that** AI can validate new content against established canon

**Acceptance Criteria:**
- Story Bible exported as JSON format
- Structured data: constants, variables, character states, world rules
- Each fact includes evidence (source passages)
- JSON schema documented for AI integration
- Can be consumed by AI validation tools (Phase 2)

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

## Feature Behavior

### Phase 1: Informational Extraction (Immediate)

**What Gets Generated:**
Story Bible is generated as a post-build artifact alongside existing formats (Harlowe, Paperthin, DotGraph, AllPaths, Metrics).

**Output Formats:**

1. **story-bible.html** (Human-readable)
   - Published to GitHub Pages
   - Organized by category (Characters, World Rules, Setting, Timeline)
   - Each fact shows evidence (passage references)
   - Clear visual distinction between constants and variables
   - "Zero action state" section for each character

2. **story-bible.json** (Machine-readable)
   - Structured data for future AI integration
   - Schema: constants, variables, character_states, world_rules, evidence
   - Can be consumed by validation tools in Phase 2

**When Generated:**
- After successful build (`make build`, `make deploy`)
- Not in critical path (build succeeds even if Story Bible generation fails)
- Graceful degradation: missing Story Bible doesn't block deployment

**How It's Generated:**

**Cache-First Approach:**
1. **Check for committed cache first:**
   - If `story-bible-cache.json` exists in repository → Read cache and render HTML/JSON from it (no Ollama needed)
   - If cache does not exist → Generate placeholder HTML/JSON with "Story Bible will be generated after first extraction"

2. **Cache generation (via webhook service):**
   - Webhook service (`/extract-story-bible`) extracts facts using Ollama
   - Uses AllPaths format as input (complete view of all paths)
   - Applies "world reconstruction" approach (not summarization)
   - Distinguishes constants (true in all paths) from variables (differ by path)
   - Identifies zero action state for each character
   - **Only successful extractions** are added to cache
   - Failed extractions (timeout, error) are NOT cached
   - Commits `story-bible-cache.json` to repository

3. **Subsequent builds:**
   - Read from committed cache (no extraction needed in CI)
   - Render HTML/JSON from cache contents
   - Fast and reliable (no Ollama dependency in build)

---

### Workflow Separation: Build vs Webhook

**Critical distinction between two workflows:**

```
WORKFLOW 1: Webhook Extraction (Populates Cache)
----------------------------------------------------
/extract-story-bible webhook triggered
  ↓
Webhook service loads AllPaths format
  ↓
For each passage:
  - Extract facts using Ollama
  - If successful → Add to cache
  - If failed (timeout/error) → Log error, do NOT cache
  ↓
Commit story-bible-cache.json to repository
  ↓
Report: "Extracted X of Y passages, Z failures"


WORKFLOW 2: Build (Renders from Cache)
----------------------------------------------------
make build / make deploy triggered
  ↓
Check if story-bible-cache.json exists in repo
  ↓
If cache exists:
  - Read cache contents
  - Render story-bible.html from cache
  - Render story-bible.json from cache
  - NO Ollama calls (fast, reliable)
  ↓
If cache missing:
  - Generate placeholder HTML/JSON
  - Placeholder message: "Use /extract-story-bible to populate"
  - NO Ollama calls (no Ollama in CI)
  ↓
Publish to GitHub Pages
```

**Key Points:**
- **Build NEVER calls Ollama** (only reads cache or generates placeholder)
- **Webhook ONLY calls Ollama** (not build)
- **Cache is source of truth** for build rendering
- **Failed extractions NOT cached** (automatic retry on next webhook run)

---

### Constants vs Variables: Definitions

**Constants** (always true regardless of player action):
- **World Rules:** Magic system exists, technology level, physical laws
- **Character Identities:** Character names, backgrounds, core traits
- **Setting:** Geography (city location, landmarks), historical events before story start
- **Timeline:** Events that happened before player's first choice
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

### Story Bible Structure

**HTML Format:**

```
Story Bible
===========

Last Updated: [Build timestamp]
Source: [Commit hash]

---

## World Constants

Facts that are true in all story paths, regardless of player choices.

### World Rules
- [Constant fact 1]
  Evidence: [Passage references]
- [Constant fact 2]
  Evidence: [Passage references]

### Setting
- [Geography constant]
  Evidence: [Passage references]
- [Historical constant]
  Evidence: [Passage references]

### Timeline
- [Event before story start]
  Evidence: [Passage references]

---

## Characters

### [Character Name]

**Identity (Constants):**
- [Core trait / background fact]
  Evidence: [Passage references]

**Zero Action State:**
- [What happens if player does nothing]
  Evidence: [Passage references]

**Variables (Player-Determined):**
- [Outcome that varies by player choice]
  Variations: [Different outcomes in different paths]

---

## Variables

Facts that change based on player choices.

### Events
- [Variable event 1]
  Paths where true: [Path IDs]
  Paths where false: [Path IDs]

### Outcomes
- [Variable outcome 1]
  Variations: [Different outcomes]

---

## Evidence

### [Passage Name / ID]
Establishes: [List of facts from this passage]
Appears in paths: [Path IDs]
```

**JSON Format:**

```json
{
  "meta": {
    "generated": "2025-12-01T10:30:00Z",
    "commit": "abc123",
    "version": "1.0"
  },
  "constants": {
    "world_rules": [
      {
        "fact": "Magic system exists",
        "evidence": ["passage_id_1", "passage_id_2"],
        "category": "world_rule"
      }
    ],
    "setting": [
      {
        "fact": "City is on the coast",
        "evidence": ["passage_id_3"],
        "category": "geography"
      }
    ],
    "timeline": [
      {
        "fact": "War ended 10 years ago",
        "evidence": ["passage_id_4"],
        "category": "historical_event"
      }
    ]
  },
  "characters": {
    "Javlyn": {
      "identity": [
        {
          "fact": "Student at the Academy",
          "evidence": ["passage_id_5"],
          "type": "constant"
        }
      ],
      "zero_action_state": [
        {
          "fact": "Struggles with magic and gives up",
          "evidence": ["path_id_default"],
          "type": "default_trajectory"
        }
      ],
      "variables": [
        {
          "fact": "Masters the magic",
          "condition": "Player helps Javlyn",
          "evidence": ["path_id_7", "path_id_8"],
          "type": "outcome"
        }
      ]
    }
  },
  "variables": {
    "events": [
      {
        "fact": "Player finds the artifact",
        "paths_true": ["path_1", "path_3"],
        "paths_false": ["path_2", "path_4"],
        "type": "player_action"
      }
    ]
  }
}
```

---

### Extraction Methodology

**World Reconstruction Approach:**
Story Bible uses AI to "reconstruct the world" from passages, not summarize the story.

**Key Principles:**
1. **Focus on facts, not plot:** Extract what IS, not what HAPPENS
2. **Identify constants:** Facts that appear consistently across all paths
3. **Distinguish variables:** Facts that differ based on player choices
4. **Request zero action state:** Ask AI "what happens if player does nothing?"
5. **Cite evidence:** Link every fact to source passages
6. **Cross-path validation:** Verify constants are truly consistent across all paths

**AI Extraction Prompt Template:**

```
You are reconstructing the world of an interactive fiction story.

Your task: Extract FACTS about the world, NOT plot summary.

Distinguish between:
- CONSTANTS: Facts true in all paths regardless of player choices
  (world rules, character identities, setting, timeline before story)
- VARIABLES: Facts determined by player actions
  (events, character fates, outcomes)

For each character, identify:
- Identity (constants): Who they are, background, core traits
- Zero Action State: What happens if player does nothing
- Variables: Outcomes that depend on player choices

Input: All story paths from AllPaths format
Output: Structured list of constants, variables, and character states with evidence

Focus on world reconstruction, not story summarization.
```

---

### Phase 2: Integration with Continuity Checking (Future)

**Approach: Integrate Story Bible validation into existing continuity checking workflow**

Instead of a separate validation service, Story Bible validation will be integrated directly into the existing AI Continuity Checking feature. When continuity checking runs on a PR, it will:

1. **Load Story Bible cache** (if exists)
2. **Validate paths for internal consistency** (existing behavior)
3. **Validate paths against Story Bible constants** (new behavior)
4. **Post combined results** in single PR comment

**Benefits of Integration:**
- Single workflow for writers (no separate command needed)
- Combined report shows both path consistency AND world consistency
- Automatic - runs whenever continuity checking runs
- Reuses existing infrastructure (webhook service, PR commenting, artifact handling)

---

**Validation Against Story Bible:**
- When continuity checking runs, load `story-bible-cache.json` from PR branch
- For each path being validated, check new content against established constants
- Flag contradictions with evidence from both sources
- Gracefully skip if Story Bible cache doesn't exist

**What Gets Validated:**
- **World constants**: Setting, world rules, timeline facts
- **Character identities**: Names, backgrounds, core traits
- **Established patterns**: Recurring themes or motifs

**What Does NOT Get Validated:**
- Plot events (those are variables, not constants)
- Player choices and outcomes (those are path-specific)
- Character fates (those vary by path)

---

**Validation Output Format:**

Integrated into continuity checking PR comment with two sections:

```markdown
## 🔍 Continuity Check Complete

**Mode:** new-only
**Validated:** 2 paths
**Story Bible:** ✅ Loaded (50 constants, 15 characters)

---

### 📊 Results Summary

**Path Consistency:**
- 🟢 1 path with no issues
- 🟡 1 path with minor issues

**Story Bible Validation:**
- 🟢 1 path consistent with canon
- 🔴 1 path with contradictions

---

### Path Continuity Issues

[Existing continuity checking output]

---

### Story Bible Violations

#### Path: `b4c9d213` (Start → Mountain → City)
**Result:** 🔴 critical

<details>
<summary>Contradictions Found (1)</summary>

**Issue 1: Setting Contradiction**
- **Type:** setting_constant
- **Severity:** critical
- **Established Constant:** "The city is on the coast" (from passage Start, Academy Introduction)
- **New Content:** "The city sprawled across the desert plains"
- **Location:** Passage x9y8z7w6

**Evidence:**
- **Established (Story Bible):** "...the salty coastal breeze filled the air..." (passage Start)
- **New Content:** "The city sprawled across the desert plains..." (passage x9y8z7w6)

**Explanation:** This passage describes the city as being in a desert, contradicting the established constant that the city is coastal.

**Possible Actions:**
- Fix the new passage to match established canon
- Clarify that this refers to a different city
- Use `/update-canon` if this constant needs to change (future feature)

</details>
```

**When Story Bible Cache Missing:**

```markdown
**Story Bible Validation:**
- ⚠️ Skipped - Story Bible cache not found
- Use `/extract-story-bible` to enable world consistency validation
```

**Severity Levels:**
- **critical**: Contradicts core world constant or character identity
- **major**: Contradicts timeline constant or setting detail
- **minor**: Ambiguous whether contradiction or intentional variation

---

**Integration Benefits:**
- Writers get comprehensive feedback in one place
- No separate validation command needed
- Automatic validation whenever continuity checking runs
- Same approval workflow (existing `/approve-path` command)
- Still informational, not blocking merges

---

## Success Metrics

### Phase 1 (Informational Tool)

**Primary Metrics:**
- Story Bible generated successfully on every build
- HTML accessible on GitHub Pages
- JSON format valid and parseable
- Authors reference Story Bible when writing new content

**Secondary Metrics:**
- Collaborators cite Story Bible when learning project
- Reduced contradictions in new content (anecdotal)
- Writers understand constants vs variables distinction
- Zero action state helps guide character development

**Qualitative Indicators:**
- Writers report Story Bible is useful for maintaining consistency
- New collaborators find Story Bible helpful for onboarding
- Team uses Story Bible terms in discussion ("is this a constant or variable?")
- AI assistants (like Claude) use Story Bible for context

### Phase 2 (CI Validation)

**Metrics (Future):**
- Validation runs automatically on PRs
- Contradictions flagged before merge
- False positive rate acceptable
- Writers trust validation feedback

---

## Edge Cases

### Edge Case 1: Contradictory Passages (What Is Canon?)
**Scenario:** Different passages establish contradictory "constants"

**Example:**
- Passage A: "The city has been here for centuries"
- Passage B: "The city was founded 20 years ago"

**Phase 1 Behavior:**
- AI detects contradiction during extraction
- Story Bible flags both as "conflicting constants"
- Lists evidence for each version
- Notes: "CONFLICT: Authors need to resolve"

**Phase 2 Behavior:**
- Validation service flags this during PR review
- Asks authors to resolve before merging
- Suggests: "Which fact is canon? Update passages or clarify in Story Bible"

---

### Edge Case 2: Player Choices Branch Early
**Scenario:** Player choice in passage 2 creates fundamentally different worlds

**Example:**
- Path 1 (magic path): Magic is real and widely known
- Path 2 (mundane path): Magic is a myth, doesn't actually exist

**Behavior:**
- Story Bible notes this as "world-level variable"
- Constants are facts true BEFORE the branching choice
- Both "magic world" and "mundane world" have separate sub-constants
- Zero action state shows default path (if player doesn't choose)

---

### Edge Case 3: Intentional Mysteries vs Actual Contradictions
**Scenario:** Story deliberately obscures facts (unreliable narrator, mystery plot)

**Example:**
- Passage A: Character says "I'm a student"
- Passage B: Character is revealed to be a spy

**Behavior:**
- AI may flag as contradiction
- Story Bible notes: "Character identity variable or mystery"
- Authors can annotate: "Intentional mystery - character identity revealed later"
- Phase 2: Allow authors to mark intentional mysteries to suppress warnings

---

### Edge Case 4: Empty or Early Story
**Scenario:** Story has very few passages, no constants established yet

**Behavior:**
- Story Bible generates with minimal content
- HTML shows: "Story Bible will populate as story develops"
- No errors, graceful handling of sparse data
- JSON contains empty or minimal arrays
- Still useful: shows "zero action state" of initial passages

---

### Edge Case 5: Ambiguous Zero Action State
**Scenario:** Unclear what "doing nothing" means (all paths require player choice)

**Behavior:**
- AI attempts to infer default/most likely path
- Story Bible notes: "Zero action state ambiguous - all paths require player action"
- May show: "Default state unknown - player must choose"
- Phase 2: Authors can explicitly define zero action state

---

### Edge Case 6: Constants Change Over Time
**Scenario:** Authors revise world-building (e.g., change magic system)

**Behavior:**
- Story Bible regenerates on every build
- Shows current constants based on current passages
- Git history preserves previous versions of Story Bible
- Phase 2: Validation flags when new content contradicts previous constants
- Authors can confirm: "Yes, we're changing this constant across all passages"

---

### Edge Case 7: Cache Missing During Build
**Scenario:** Build runs but `story-bible-cache.json` doesn't exist in repository

**Behavior:**
- Build checks for `story-bible-cache.json` in repository
- Cache not found → Generate placeholder HTML/JSON
- Placeholder shows: "Story Bible will be generated after first extraction. Use `/extract-story-bible` webhook to populate."
- Build succeeds (Story Bible is post-build artifact)
- Does NOT block deployment of other formats
- Does NOT attempt to call Ollama (no Ollama in CI environment)

---

### Edge Case 8: Failed Extraction (Individual Passages)
**Scenario:** Ollama fails to extract facts from a passage (timeout, network error, parse error)

**Behavior:**
- **Failed passage NOT added to cache**
- Error logged with passage ID and failure reason
- Extraction continues with remaining passages
- Partial cache committed (only successful extractions)
- Next incremental run will retry failed passages
- HTML/JSON rendered from successful extractions only
- Failed passages noted in extraction logs for debugging

**Critical:** Incremental mode must NOT skip failed passages on subsequent runs.

---

### Edge Case 9: Extraction Timeout During Webhook
**Scenario:** Webhook service times out while extracting facts (Ollama slow or unresponsive)

**Behavior:**
- Webhook returns 202 Accepted (processing continues async)
- Extraction attempts each passage with per-passage timeout
- Successfully extracted passages committed to cache
- Failed passages logged but NOT cached
- Webhook reports: "Extracted X of Y passages, Z failures logged"
- Next incremental run can retry failures

---

## Risk Considerations

### Risk 1: AI Extraction Accuracy
**Impact:** High - incorrect facts in Story Bible mislead authors

**Mitigation:**
- Use well-tested AI model (same as continuity checking)
- Cite evidence for every fact (authors can verify)
- Mark confidence level for ambiguous facts
- Iterative prompt refinement based on usage
- Phase 1 is informational - authors validate output

**Monitoring:** Track author feedback on accuracy

---

### Risk 2: Contradictions in Source Material
**Impact:** Medium - Story Bible flags contradictions authors intended

**Mitigation:**
- Phase 1: Simply report all facts, note conflicts
- Allow authors to annotate intentional mysteries
- Trust authors to resolve or accept contradictions
- Phase 2: Allow override/annotation of flagged conflicts

**Monitoring:** Track frequency of flagged contradictions

---

### Risk 3: Performance and Cost
**Impact:** Medium - AI extraction may be slow or expensive

**Mitigation:**
- Run post-build (not blocking critical path)
- Cache previous extractions, only process changed passages
- Use efficient AI model
- Fail gracefully if extraction times out
- Phase 1: Generate once per successful build

**Monitoring:** Track extraction time and costs

---

### Risk 4: Scope Creep
**Impact:** Low - temptation to add complex features

**Mitigation:**
- Stick to Phase 1 scope: extraction and display only
- No interactive editing of Story Bible in Phase 1
- No blocking validation in Phase 1
- Defer advanced features to Phase 2
- CEO constraint: informational/additive only

**Monitoring:** Stick to PRD scope

---

### Risk 5: Format Consistency
**Impact:** Low - Story Bible format changes break AI integration

**Mitigation:**
- Define JSON schema upfront
- Version schema (allow evolution)
- Document schema for future integrations
- Test JSON validity on every build
- Maintain backward compatibility

**Monitoring:** Track schema changes, validate format

---

## Acceptance Criteria Summary

### Phase 1: Informational Tool

**Core Functionality:**
- [ ] Story Bible generated as post-build artifact
- [ ] HTML format published to GitHub Pages as `/story-bible.html`
- [ ] JSON format generated as `story-bible.json`
- [ ] AI extracts constants, variables, and character states
- [ ] Each fact includes evidence (passage references)
- [ ] Clear distinction between constants and variables
- [ ] Zero action state documented for each character

**HTML Output:**
- [ ] Human-readable format organized by category
- [ ] Sections: World Constants, Characters, Variables, Evidence
- [ ] Each fact shows source passages
- [ ] Visual distinction between constants and variables
- [ ] Accessible on any device with browser
- [ ] Updates automatically with each build

**JSON Output:**
- [ ] Machine-readable structured data
- [ ] Schema documented and versioned
- [ ] Valid JSON format (no parse errors)
- [ ] Includes: constants, variables, character_states, evidence, meta
- [ ] Can be consumed by future AI tools

**Build Integration:**
- [ ] Integrated into `make build` and `make deploy`
- [ ] **Cache-first approach:** Build checks for `story-bible-cache.json` in repository FIRST
- [ ] If cache exists → Render HTML/JSON from cache (no Ollama needed)
- [ ] If cache missing → Generate placeholder HTML/JSON (no Ollama attempted)
- [ ] Build NEVER attempts to call Ollama (extraction is webhook-only)
- [ ] Runs after successful build (post-build artifact)
- [ ] Build continues if Story Bible generation fails (graceful degradation)
- [ ] Clear build output showing Story Bible generation status
- [ ] Does NOT block deployment of other formats

**Cache Handling:**
- [ ] **Failed extractions NOT cached:** Only successful passage extractions added to cache
- [ ] Failed passages logged with error details (passage ID, failure reason)
- [ ] Partial cache committed (successful extractions only)
- [ ] Cache file (`story-bible-cache.json`) committed to repository by webhook service
- [ ] Cache includes metadata: timestamp, commit hash, extraction statistics

**Incremental Extraction (Webhook Service):**
- [ ] `/extract-story-bible` webhook extracts facts using Ollama
- [ ] Incremental mode: Only extract passages not already in cache
- [ ] **Failed passages retried:** Passages that failed previously are NOT in cache, so they're retried on next run
- [ ] Per-passage timeout to prevent single failure blocking all extraction
- [ ] Extraction continues even if individual passages fail
- [ ] Webhook reports extraction statistics: "Extracted X of Y passages, Z failures"
- [ ] Commits cache to repository after successful extraction (partial or complete)

**Extraction Quality:**
- [ ] Constants are facts true in all paths
- [ ] Variables are facts that differ by player choices
- [ ] Zero action state identified for each character
- [ ] Evidence cited for every fact
- [ ] Contradictions flagged (not resolved, just noted)

**Documentation:**
- [ ] Usage guide in README or documentation
- [ ] Explanation of constants vs variables
- [ ] Definition of zero action state
- [ ] Instructions for referencing Story Bible
- [ ] Examples showing extraction output

### Phase 2: CI Validation (Future)

**Validation Functionality (Future):**
- [ ] Validate new content against Story Bible constants
- [ ] Flag contradictions in PR comments
- [ ] Severity levels (minor, major, critical)
- [ ] Suggest corrections or ask for clarification
- [ ] Still informational, not blocking CI

**Not in Phase 1 Scope:**
- ✗ Blocking CI on contradictions
- ✗ Interactive editing of Story Bible
- ✗ Manual annotation of facts
- ✗ Complex confidence scoring
- ✗ Multi-version Story Bible tracking

---

## Corrections to User Guidance

The user provided excellent guidance with solid concepts. A few clarifications and corrections:

### ✅ Correct Concepts:
- **Constants vs Variables:** Excellent distinction, well-explained
- **Zero Action State:** Brilliant framing for understanding defaults
- **World Reconstruction:** Correct approach (facts, not plot summary)
- **Evidence Citation:** Critical for verifiability
- **AI Integration:** Right to design for future AI consumption

### 📝 Clarifications Needed:

1. **"Story Bible in Critical Path"**
   - **User Guidance:** Implied Story Bible might be in build pipeline
   - **Correction:** Story Bible is POST-build artifact (CEO constraint)
   - **Why:** Must not block builds, purely informational/additive

2. **"CI Validation Now"**
   - **User Guidance:** Suggested CI validation checks immediately
   - **Correction:** Phase 1 = extraction/display only, Phase 2 = validation
   - **Why:** CEO constraint (inspection first, validation later) + we're on last day of NaNoWriMo

3. **"Constants Always Universal"**
   - **User Guidance:** Constants are always true across ALL paths
   - **Clarification:** Some "constants" may be scoped to branches (world-level variables)
   - **Example:** If path 2 chooses "magic exists" vs "magic is myth", that's a world-level variable with branch-specific constants

4. **"Zero Action State Always Exists"**
   - **User Guidance:** Every character has a zero action state
   - **Clarification:** Some stories force player choice (no "do nothing" option)
   - **Behavior:** Story Bible notes when zero action state is ambiguous

5. **"Story Bible is Source of Truth"**
   - **User Guidance:** Story Bible becomes canonical reference
   - **Clarification:** PASSAGES are source of truth, Story Bible is DERIVED
   - **Important:** Story Bible extracts from passages, not vice versa
   - **If conflict:** Passages win, Story Bible regenerates

### ✨ Enhancements to User Guidance:

1. **Add "Evidence" as First-Class Concept**
   - Every fact must cite source passages
   - Enables verification and trust

2. **Add "Conflicting Constants" Handling**
   - What happens when passages contradict?
   - Story Bible flags, doesn't resolve (authors decide)

3. **Add "World-Level Variables"**
   - Some branches create fundamentally different worlds
   - Story Bible handles multi-world scenarios

4. **Add "Graceful Degradation"**
   - Story Bible generation can fail without blocking deploy
   - Missing data handled transparently

---

## Related Documents

**Strategic:**
- [VISION.md](/home/user/NaNoWriMo2025/VISION.md) - Project vision (writers first, automation over gatekeeping)
- [ROADMAP.md](/home/user/NaNoWriMo2025/ROADMAP.md) - Product roadmap and priorities
- [PRINCIPLES.md](/home/user/NaNoWriMo2025/PRINCIPLES.md) - Core principles (transparency, multiple perspectives)

**Technical Context:**
- [features/ai-continuity-checking.md](/home/user/NaNoWriMo2025/features/ai-continuity-checking.md) - Related AI validation feature
- [features/multiple-output-formats.md](/home/user/NaNoWriMo2025/features/multiple-output-formats.md) - Build artifact generation pattern

**Implementation (Future):**
- [architecture/] - Technical design documents (to be created by Architect)
- [formats/story-bible/] - Story Bible format specifications (to be created by Architect)

---

## Design Principles Applied

This feature demonstrates several core principles:

**Writers First (Principle #1):**
- Story Bible helps writers maintain consistency
- Human-readable format for easy reference
- Clear distinction between constants and variables
- Zero action state helps guide character development

**Automation Over Gatekeeping (Principle #2):**
- Automated extraction from passages
- Generated on every build
- Informational, not blocking
- Phase 2: Validation suggests, doesn't block

**Multiple Perspectives, Same Source (Principle #4):**
- One .twee source, multiple derived artifacts
- Story Bible is another perspective on the story
- HTML for humans, JSON for machines
- Same extraction, different presentation formats

**Transparency and Inspectability (Principle #5):**
- Every fact cites evidence (source passages)
- Contradictions flagged, not hidden
- Clear distinction between constants, variables, zero action state
- Authors can verify AI extraction accuracy

**Incremental Progress Over Perfection (Principle #6):**
- Phase 1: Extraction and display (ship now)
- Phase 2: Validation (add later based on learning)
- Simple extraction first, refinement based on usage
- Graceful degradation (missing data doesn't break page)

**Smart Defaults, Escape Hatches (Principle #7):**
- Automatic extraction works for most cases
- Phase 2: Authors can override/annotate when needed
- Default behavior: extract and display
- Advanced behavior: custom annotations (future)

---

## Timeline and Prioritization

**Phase 1: Informational Tool**
- **Target:** December 2025 (Post-NaNoWriMo refinement phase)
- **Priority:** Medium
- **Dependencies:** Requires AllPaths format as input
- **Why December:**
  - Not blocking NaNoWriMo completion (last day is Nov 29)
  - Story Bible more valuable after story reaches substantial size
  - Refinement phase focus shifts to editing and polish

**Phase 2: CI Validation**
- **Target:** TBD (After Phase 1 learning)
- **Priority:** Low (validate concept first)
- **Dependencies:** Phase 1 working well, clear need identified

**Relationship to NaNoWriMo Timeline:**
- **Nov 29:** Focus on completing 50,000 words (Story Bible deferred)
- **December:** Refinement tools like Story Bible become valuable
- **Rationale:** Extraction more useful with substantial content, not blocking writing momentum

---

## Resolved Design Decisions

These decisions have been made and are now part of the requirements:

1. **Cache Strategy:** ✅ RESOLVED
   - **Decision:** Cache-first approach with incremental extraction
   - Build reads from `story-bible-cache.json` (no Ollama in CI)
   - Webhook service (`/extract-story-bible`) populates cache using Ollama
   - Only successful extractions cached (failures retried on next run)
   - Cache committed to repository by webhook service

2. **Extraction Frequency:** ✅ RESOLVED
   - **Decision:** Webhook-based extraction (on-demand via `/extract-story-bible`)
   - Build reads cache and renders HTML/JSON (every build)
   - Incremental mode: Only extract passages not already in cache
   - Failed passages NOT cached, so they're retried automatically

---

## Open Questions

Questions to resolve during implementation (for Architect and Developer):

1. **AI Model Choice:**
   - Same model as continuity checking, or different?
   - **Recommendation:** Same model (gpt-oss:20b-fullcontext)

2. **Evidence Format:**
   - Passage IDs (random) or passage names (semantic)?
   - **Recommendation:** Both (ID for uniqueness, name for readability)

3. **JSON Schema Version:**
   - How to handle schema evolution over time?
   - **Recommendation:** Semver schema versioning

4. **Conflict Resolution:**
   - How to handle contradictory constants?
   - **Recommendation:** Flag all, let authors resolve (Phase 1 doesn't resolve)

5. **Per-Passage Timeout:**
   - What timeout value for individual passage extraction?
   - **Recommendation:** 30 seconds per passage (prevents single passage blocking all extraction)

These questions should be addressed during technical design (Architect phase).

---

## Success Criteria Met

Phase 1 will be considered successful when:

- [x] Story Bible PRD documented (this document)
- [ ] Story Bible generated on every build
- [ ] HTML format accessible and useful to authors
- [ ] JSON format valid and documented
- [ ] Authors reference Story Bible when writing
- [ ] New collaborators use Story Bible for onboarding
- [ ] Constants vs variables distinction clear and useful
- [ ] Zero action state helps guide character development
- [ ] No blocking of CI or deployment
- [ ] Graceful degradation if generation fails

Phase 2 planning begins when:
- Phase 1 successful and valuable to authors
- Clear use cases for validation identified
- Team expresses need for automated contradiction checking

---

## Next Steps

**Immediate (Product Manager):**
- [x] Document PRD (this document)
- [ ] Review with CEO for strategic alignment
- [ ] Prioritize in roadmap (December 2025 target)

**After Approval (Architect):**
- [ ] Design technical architecture
- [ ] Define JSON schema
- [ ] Plan AI extraction pipeline
- [ ] Design build integration approach
- [ ] Document in architecture/

**After Design (Developer):**
- [ ] Implement AI extraction logic
- [ ] Build HTML format generator
- [ ] Build JSON format generator
- [ ] Integrate into build pipeline
- [ ] Test with current story content
- [ ] Document usage in README

---

## Appendix: Example Story Bible Output

### Example HTML Output (Partial)

```html
<!DOCTYPE html>
<html>
<head>
  <title>Story Bible - NaNoWriMo2025</title>
</head>
<body>
  <h1>Story Bible</h1>

  <p><strong>Last Updated:</strong> 2025-12-05 14:30 UTC</p>
  <p><strong>Source Commit:</strong> abc123def</p>

  <hr>

  <h2>World Constants</h2>
  <p>Facts that are true in all story paths, regardless of player choices.</p>

  <h3>World Rules</h3>
  <ul>
    <li><strong>Magic system exists</strong>
      <br>Evidence: Passage "Start" (passage_id_1), Passage "Academy Introduction" (passage_id_5)
    </li>
    <li><strong>Technology level is medieval-fantasy</strong>
      <br>Evidence: Passage "City Description" (passage_id_3)
    </li>
  </ul>

  <h3>Setting</h3>
  <ul>
    <li><strong>City is on the coast</strong>
      <br>Evidence: Passage "City Description" (passage_id_3)
    </li>
    <li><strong>Academy is the central institution</strong>
      <br>Evidence: Passage "Academy Introduction" (passage_id_5)
    </li>
  </ul>

  <hr>

  <h2>Characters</h2>

  <h3>Javlyn</h3>

  <h4>Identity (Constants):</h4>
  <ul>
    <li><strong>Student at the Academy</strong>
      <br>Evidence: Passage "Meet Javlyn" (passage_id_7)
    </li>
    <li><strong>Struggling with magic studies</strong>
      <br>Evidence: Passage "Meet Javlyn" (passage_id_7)
    </li>
  </ul>

  <h4>Zero Action State:</h4>
  <ul>
    <li><strong>Continues to struggle and eventually gives up on magic</strong>
      <br>Evidence: Path "Default Ending" (path_id_default)
    </li>
    <li><strong>Leaves the Academy after failing exams</strong>
      <br>Evidence: Path "Default Ending" (path_id_default)
    </li>
  </ul>

  <h4>Variables (Player-Determined):</h4>
  <ul>
    <li><strong>Masters the magic</strong>
      <br>Condition: Player helps Javlyn study
      <br>Evidence: Path "Help Javlyn" (path_id_7), Path "Victory Together" (path_id_8)
    </li>
    <li><strong>Becomes player's rival</strong>
      <br>Condition: Player competes against Javlyn
      <br>Evidence: Path "Rivalry" (path_id_9)
    </li>
  </ul>

  <hr>

  <h2>Variables</h2>
  <p>Facts that change based on player choices.</p>

  <h3>Events</h3>
  <ul>
    <li><strong>Player finds the ancient artifact</strong>
      <br>Paths where true: path_id_2, path_id_4, path_id_7
      <br>Paths where false: path_id_1, path_id_3, path_id_5
    </li>
  </ul>

  <h3>Outcomes</h3>
  <ul>
    <li><strong>Academy is saved from threat</strong>
      <br>Variations:
        - Saved by player alone (path_id_3)
        - Saved by player and Javlyn together (path_id_8)
        - Not saved, Academy falls (path_id_default)
    </li>
  </ul>

</body>
</html>
```

### Example JSON Output (Partial)

```json
{
  "meta": {
    "generated": "2025-12-05T14:30:00Z",
    "commit": "abc123def",
    "version": "1.0",
    "schema_version": "1.0.0"
  },
  "constants": {
    "world_rules": [
      {
        "fact": "Magic system exists",
        "evidence": ["passage_id_1", "passage_id_5"],
        "category": "world_rule",
        "confidence": "high"
      }
    ],
    "setting": [
      {
        "fact": "City is on the coast",
        "evidence": ["passage_id_3"],
        "category": "geography",
        "confidence": "high"
      }
    ]
  },
  "characters": {
    "Javlyn": {
      "identity": [
        {
          "fact": "Student at the Academy",
          "evidence": ["passage_id_7"],
          "type": "constant",
          "confidence": "high"
        }
      ],
      "zero_action_state": [
        {
          "fact": "Continues to struggle and eventually gives up on magic",
          "evidence": ["path_id_default"],
          "type": "default_trajectory",
          "confidence": "medium"
        }
      ],
      "variables": [
        {
          "fact": "Masters the magic",
          "condition": "Player helps Javlyn study",
          "evidence": ["path_id_7", "path_id_8"],
          "type": "outcome",
          "confidence": "high"
        }
      ]
    }
  },
  "variables": {
    "events": [
      {
        "fact": "Player finds the ancient artifact",
        "paths_true": ["path_id_2", "path_id_4", "path_id_7"],
        "paths_false": ["path_id_1", "path_id_3", "path_id_5"],
        "type": "player_action"
      }
    ]
  }
}
```

---

**End of PRD**
