# Feature PRD: AI Continuity Checking

**Status:** Released ✅
**Owner:** Product Manager
**Last Updated:** 2025-11-22

---

## User Problem

**For collaborative branching narrative writers:**
- Branching narratives create exponential complexity - manually checking all paths is impossible
- Continuity errors multiply across branches (character names, timeline, plot consistency)
- One author's changes can introduce contradictions in another author's paths
- Testing every possible player journey manually takes hours or days
- Writers need confidence that the story maintains internal consistency across all branches

**Pain Point:** "I added a new path where the character learns the magic early, but I'm not sure if that breaks continuity in the 15 other paths where they don't know about it yet. I can't manually check every single path."

---

## User Stories

### Story 1: Writer Adding New Branch
**As a** writer adding a new story branch
**I want** automated validation of continuity across all affected paths
**So that** I can confidently add content without breaking existing story logic

**Acceptance Criteria:**
- AI checks all new paths automatically on every PR
- Results posted within minutes of PR creation
- Clear feedback on specific continuity issues
- Issues categorized by severity (minor, major, critical)
- Can see exactly where in the path the issue occurs

---

### Story 2: Reviewer Approving PR
**As a** reviewer checking another author's PR
**I want** to see AI validation results before approving
**So that** I can focus on creative feedback instead of hunting for continuity bugs

**Acceptance Criteria:**
- AI validation runs automatically on every PR
- Results appear as PR comment
- Can trust that technical continuity is checked
- Can focus review on story quality and creative choices

---

### Story 3: Writer Fixing Issues
**As a** writer addressing AI-flagged issues
**I want** to understand what's wrong and how to fix it
**So that** I can resolve continuity problems quickly

**Acceptance Criteria:**
- AI explains specific issue clearly
- Provides quotes from story showing the problem
- Suggests severity level (helps prioritize fixes)
- Can re-run validation after fixing to confirm resolution

---

### Story 4: Writer Approving Valid Paths
**As a** writer who has reviewed AI feedback
**I want** to mark paths as validated so they're not re-checked
**So that** future validations run faster and focus on new content

**Acceptance Criteria:**
- Can approve paths with `/approve-path` command
- Approved paths skipped in future validations
- Validation cache updated automatically
- Approved paths re-checked only if content changes

---

## Success Metrics

### Primary Metrics
- **Validation coverage:** 100% of PRs automatically validated
- **Feedback speed:** Results posted within minutes of PR workflow completion
- **Issue detection:** AI catches continuity errors before merge
- **Zero escaped errors:** No continuity issues merged to main branch

### Secondary Metrics
- **Validation efficiency:** New-only mode ~60% faster than full validation
- **Path approval rate:** Writers approve and dismiss issues regularly
- **False positive rate:** Low rate of incorrect issue flagging
- **Writer confidence:** Writers trust AI feedback and act on it

### Qualitative Metrics
- Writer feedback: "AI caught an issue I completely missed"
- No continuity errors discovered after merge
- Writers use validation modes appropriately (new-only → modified → all)

---

## How It Works

### System Architecture

```
GitHub PR Workflow
    ↓ Builds story formats
    ↓ Uploads AllPaths artifacts
    ↓ Workflow completes
    ↓
GitHub sends webhook
    ↓
Continuity Webhook Service
    ↓ Verifies signature
    ↓ Downloads artifacts
    ↓ Determines validation mode
    ↓ Categorizes paths (new/modified/unchanged)
    ↓
Runs AI Continuity Checker
    ↓ Loads validation cache
    ↓ Selects paths based on mode
    ↓ For each path:
    │   ↓ Sends to Ollama API
    │   ↓ Receives AI analysis
    │   ↓ Posts progress update to PR
    │   ↓ Updates validation cache
    ↓
Posts final summary to PR
```

---

### Three Validation Modes

#### Mode 1: new-only (Default)
**Validates:** Only brand new paths (never seen before)
**Skips:** Modified and unchanged paths
**Speed:** Fastest (~2-5 paths, 2-5 minutes typical)

**When to Use:**
- Automatic PR builds (default)
- Quick feedback during active development
- Testing new story branches

**Command:** `/check-continuity` or `/check-continuity new-only`

---

#### Mode 2: modified
**Validates:** New paths + modified paths (content changed)
**Skips:** Unchanged paths
**Speed:** Medium (~5-10 paths, 5-15 minutes typical)

**When to Use:**
- Before requesting PR review
- Pre-merge validation
- After fixing issues in new paths

**Command:** `/check-continuity modified`

---

#### Mode 3: all
**Validates:** Every single path, regardless of status
**Skips:** Nothing
**Speed:** Slow (~all paths, 20-40 minutes for large stories)

**When to Use:**
- After major story refactoring
- After updating AI model
- Periodic full story audits
- Investigating cross-path issues

**Command:** `/check-continuity all`

---

### AI Analysis Process

**For each path:**

1. **Load path content** from allpaths-metadata/*.txt
2. **Send to Ollama** with continuity checking prompt
3. **AI analyzes** for:
   - Character consistency (names, traits, relationships)
   - Plot coherence (events flow logically)
   - Timeline accuracy (event sequences make sense)
   - Setting/world consistency (locations, rules)
   - Contradictions or plot holes
4. **AI returns** structured JSON with issues
5. **Parse results** and extract:
   - Severity (none/minor/major/critical)
   - Issue type (character/plot/timeline/setting/contradiction)
   - Description and location
   - Specific quotes demonstrating the problem
6. **Post progress update** to PR with results
7. **Update validation cache** with results

---

### Key Innovation: Random Passage IDs

**Problem:** Passage names like "Day 5 KEB" contain semantic information (timeline markers) that players never see, but confuse AI models.

**Solution:** AllPaths format replaces passage names with random hex IDs in AI prompts:
- `[PASSAGE: a1b2c3d4e5f6]` instead of `[PASSAGE: Day 5 KEB]`
- AI only sees meaningless random IDs with zero semantic content
- Mapping file (`allpaths-passage-mapping.json`) translates IDs back to names for reporting
- AI focuses on actual prose players see, not internal passage structure

**Result:** Dramatically improved AI accuracy - no longer confused by timeline markers or technical passage names.

---

### PR Comment Format

**Initial Comment (Validation Start):**
```markdown
## 🔍 Continuity Check Started

**Mode:** new-only _(use `/check-continuity modified` for broader checking)_

**Paths to validate:**
- 2 new paths
- 3 modified paths (skipped)
- 25 unchanged paths (skipped)

Progress updates will appear below as each path completes...
```

**Progress Update (Per Path):**
```markdown
### 🟡 Path 2/2 Complete
**Path ID:** `a3f8b912`
**Route:** `Start → Continue on → Cave → Victory`
**Result:** minor
**Summary:** Small timeline inconsistency in character knowledge

<details>
<summary>Issues Found (1)</summary>

#### Issue 1: Timeline Inconsistency
- **Type:** timeline
- **Severity:** minor
- **Description:** Character knows about magic before learning about it
- **Location:** Passage a1b2c3d4e5f6

**Quotes:**
- Passage a1b2c3d4e5f6: "Javlyn used the defense spell..."
- Passage 9f8e7d6c5b4a: "Javlyn learned about magic for the first time..."

**Explanation:** Character uses magic before learning about it in this path.
</details>

💡 To approve this path: reply `/approve-path a3f8b912`
```

**Final Summary:**
```markdown
## ✅ Continuity Check Complete

**Mode:** new-only
**Validated:** 2 paths
**Skipped:** 3 modified, 25 unchanged

### Results by Severity
- 🟢 **1 path** with no issues
- 🟡 **1 path** with minor issues

### Next Steps
1. Review issues above
2. Fix or approve as appropriate
3. Use `/check-continuity modified` before merge for full validation
```

---

### Path Approval Workflow

**Writer reviews AI feedback and replies:**
```
Timeline issue is acceptable for story flow.
/approve-path a3f8b912
```

**Service responds:**
1. Verifies writer is repository collaborator
2. Downloads validation cache from PR artifacts
3. Marks path as validated
4. Commits updated cache to PR branch
5. Posts confirmation:

```markdown
✅ Successfully validated 1 path(s) by @username

**Approved paths:**
- `a3f8b912` (Start → Continue on → Cave → Victory)

These paths won't be re-checked unless their content changes.
```

---

## Edge Cases

### Edge Case 1: AI False Positives
**Scenario:** AI flags issue that isn't actually a problem (e.g., intentional plot mystery)

**Current Behavior:**
- Issue appears in PR comment
- Writer must evaluate and dismiss

**Desired Behavior:**
- Writer can approve path with `/approve-path` to skip future checks
- Can add comment explaining why issue is acceptable
- Path marked as validated in cache

**Status:** Handled by approval workflow

---

### Edge Case 2: AI Service Down
**Scenario:** Ollama service is unavailable or crashed

**Current Behavior:**
- Validation fails with error
- PR comment shows error message
- Does not block PR merge (validation is informational)

**Desired Behavior:**
- Clear error message explaining service issue
- Retry logic for transient failures
- Does not block PR workflow

**Status:** Error handling in place, does not block merges

---

### Edge Case 3: Very Long Paths
**Scenario:** Path exceeds AI model context window (20,000+ tokens)

**Current Behavior:**
- AI may truncate or fail
- Error reported in PR comment

**Desired Behavior:**
- Warn if path approaching context limits
- Suggest breaking story into smaller passages
- Graceful failure with clear message

**Status:** Rare - current paths well within limits

---

### Edge Case 4: Ambiguous Issues
**Scenario:** AI flags something that might or might not be an issue

**Current Behavior:**
- AI assigns severity based on analysis
- Writer reviews and makes judgment call

**Desired Behavior:**
- AI explains reasoning clearly
- Provides quotes demonstrating issue
- Writer makes final decision

**Status:** Working as intended - AI provides information, writer decides

---

### Edge Case 5: Cross-Path Issues
**Scenario:** Issue involves multiple paths (shared passage changes affect many paths)

**Current Behavior:**
- Each path validated independently
- Issue flagged in each affected path
- Can see pattern across multiple path results

**Desired Behavior:**
- AI identifies same issue in multiple paths
- Writer fixes once, resolves for all affected paths
- Cache invalidates all affected paths on content change

**Status:** Handled by content-based hashing - editing passage invalidates all paths containing it

---

### Edge Case 6: Validation Mode Confusion
**Scenario:** Writer doesn't understand which mode to use

**Current Behavior:**
- Default (new-only) runs automatically
- Writer can manually trigger other modes
- PR comments explain mode used

**Desired Behavior:**
- Clear mode descriptions in documentation
- PR comments suggest next mode if appropriate
- Usage patterns guide writers to correct mode

**Status:** Documentation in services/README.md, mode hints in PR comments

---

### Edge Case 7: Concurrent PR Validations
**Scenario:** Multiple PRs trigger validation simultaneously

**Current Behavior:**
- Each validation runs in separate thread
- Service tracks active jobs
- All validations complete successfully

**Desired Behavior:**
- Parallel processing without interference
- Status endpoint shows active jobs
- Resource limits prevent overload

**Status:** Working as intended - thread-based concurrency handles this

---

## Technical Implementation

### Components

**Webhook Service:** `services/continuity-webhook.py`
- Flask web service listening for GitHub webhooks
- Webhook signature verification (HMAC-SHA256)
- Artifact download from GitHub Actions
- Background thread processing
- PR comment posting
- Status endpoint for monitoring

**Continuity Checker:** `scripts/check-story-continuity.py`
- Path categorization (new/modified/unchanged)
- Mode filtering logic
- Ollama API integration
- Progress callback support
- Validation cache management
- Content fingerprinting

**AllPaths Generator:** `formats/allpaths/generator.py`
- Path enumeration via depth-first search
- Random ID generation for passages
- Metadata and clean format generation
- Validation cache initialization

---

### Validation Cache Structure

**File:** `allpaths-validation-status.json`

```json
{
  "a3f8b912": {
    "route": "Start → Continue on → Cave → Victory",
    "route_hash": "abc123...",
    "first_seen": "2025-11-10T07:06:05.514940",
    "validated": true,
    "content_fingerprint": "def456...",
    "raw_content_fingerprint": "ghi789...",
    "commit_date": "2025-11-12T15:30:00-05:00",
    "created_date": "2025-11-02T19:00:37-05:00",
    "category": "unchanged"
  }
}
```

**Path Categorization Logic:**
- **New:** Path ID not in cache (never seen before)
- **Modified:** Path ID in cache but not validated (content changed)
- **Unchanged:** Path ID in cache and validated (no changes)

**Content-Based Change Detection:**
- `content_fingerprint`: Hash of prose only (excludes link text)
- `raw_content_fingerprint`: Hash including link text
- Hash changes automatically when any passage in path is edited
- Triggers re-categorization from "unchanged" to "modified"

---

### AI Prompt Template

**Key Instructions to AI:**
```
IMPORTANT INSTRUCTIONS:
- Lines marked with "[PASSAGE: xxxxxxxxxxxx]" are METADATA ONLY containing random hex IDs
- These are INTERNAL IDENTIFIERS with NO MEANING - completely ignore them
- Only analyze the actual story text that appears between these markers
- Text marked "[unselected]" shows choices NOT taken - ignore these completely
- Focus ONLY on what the player actually sees in this specific path

Check for:
1. Character consistency
2. Plot coherence
3. Timeline accuracy
4. Setting/world consistency
5. Contradictions or plot holes

Respond with JSON:
{
  "has_issues": true/false,
  "severity": "none/minor/major/critical",
  "issues": [...],
  "summary": "..."
}
```

---

## What Could Go Wrong?

### Risk 1: AI Model Quality Issues
**Impact:** High - incorrect or missing issue detection
**Mitigation:** Use well-tested model (gpt-oss:20b-fullcontext), iterate on prompts
**Fallback:** Writers do manual review, treat AI as assistant not authority

---

### Risk 2: Service Downtime
**Impact:** Medium - validation unavailable
**Mitigation:** Service monitoring, auto-restart, health checks
**Fallback:** Validation is informational only, doesn't block merges

---

### Risk 3: Cost/Performance at Scale
**Impact:** Medium - validation takes too long for large stories
**Mitigation:** Selective validation modes optimize for common case
**Fallback:** Run full validation less frequently, rely on new-only for daily work

---

### Risk 4: False Positives Erode Trust
**Impact:** Medium - writers ignore AI if too many wrong flags
**Mitigation:** Iterate on prompt quality, make approval workflow easy
**Fallback:** Writers can always approve and move on

---

## Future Enhancements

### Considered but Not Planned
- **Multiple AI models:** Compare results from different models
  - **Why not:** Single model working well, added complexity not justified

- **Custom validation rules:** User-defined checks beyond AI
  - **Why not:** AI is flexible enough, rules would be brittle

- **Validation history tracking:** Track issues over time
  - **Why not:** Current cache is sufficient, added complexity

- **GitHub status checks:** Block merge on critical issues
  - **Why not:** Writers should make judgment call, not automatic blocks

---

## Dependencies

### External Dependencies
- **Ollama:** Local AI model API
- **gpt-oss:20b-fullcontext:** AI model for analysis
- **GitHub API:** Webhook delivery, artifact download, comment posting
- **GitHub Actions:** Build and artifact upload

### Internal Dependencies
- **AllPaths format:** Path enumeration and formatting
- **Validation cache:** Path tracking and state management
- **Webhook service:** Orchestration and PR communication
- **Build workflow:** Artifact generation

---

## Metrics Dashboard

### Current Performance (as of Nov 22, 2025)
- ✅ **Validation coverage:** 100% of PRs automatically validated
- ✅ **Average validation time (new-only):** ~2 minutes for typical PR
- ✅ **Average validation time (modified):** ~5 minutes for typical PR
- ✅ **Time saved (new-only vs all):** ~60% faster
- ✅ **False positive rate:** Low (exact rate TBD with more usage)
- ✅ **Escaped errors:** 0 (zero continuity issues merged to main)

---

## Success Criteria Met

- [x] AI validation runs automatically on every PR
- [x] Results posted within minutes of PR completion
- [x] Clear, actionable feedback with specific quotes
- [x] Severity categorization (none/minor/major/critical)
- [x] Three validation modes (new-only/modified/all)
- [x] Path approval workflow working
- [x] Content-based change detection accurate
- [x] Zero continuity errors merged to main

---

## Related Documents

- [services/README.md](/home/user/NaNoWriMo2025/services/README.md) - Webhook service documentation
- [services/DESIGN-selective-validation.md](/home/user/NaNoWriMo2025/services/DESIGN-selective-validation.md) - Validation mode design
- [formats/allpaths/README.md](/home/user/NaNoWriMo2025/formats/allpaths/README.md) - AllPaths format documentation
- [PRINCIPLES.md](/home/user/NaNoWriMo2025/PRINCIPLES.md) - "Automation Over Gatekeeping" principle

---

## Lessons Learned

### What Worked Well
- **Random passage IDs:** Dramatically improved AI accuracy
- **Selective validation modes:** Fast feedback for daily work, thorough validation when needed
- **Real-time progress updates:** Writers see results as paths complete, can start fixing while validation continues
- **Approval workflow:** Easy to mark paths as validated and move on

### What Could Be Better
- **Prompt tuning:** Could further improve AI accuracy with more examples
- **Performance:** Could optimize for very large stories (100+ paths)
- **Mode guidance:** Could better guide writers on which mode to use when

### What We'd Do Differently
- **Earlier planning:** Random IDs added later, could have designed upfront
- **More prompt testing:** Could have tested more prompt variations before launching
- **Performance benchmarks:** Could have established baseline performance metrics earlier
