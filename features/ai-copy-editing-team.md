# Feature PRD: AI Copy Editing Team

**Status:** Released ✅
**Owner:** Product Manager
**Last Updated:** 2025-12-01

---

## Feature Overview

The AI Copy Editing Team is a **validation feature** that automatically checks story paths for consistency issues. Think of it as a team of specialized editors, each with their own expertise, reviewing your story together.

**How it works:**
- Determines which paths need validation based on what changed in a PR
- Each team member analyzes those paths from their specialty perspective
- All team members report results together in a single PR comment

**Relationship to AllPaths:**
- **AllPaths HTML** is a separate browsing/tracking feature (see [allpaths-categorization.md](./allpaths-categorization.md))
- AllPaths shows dates, filters, and validation status for progress tracking
- The Team uses internal git-based categories (NEW/MODIFIED/UNCHANGED) to determine what to validate
- These internal categories don't appear in the AllPaths HTML
- Validation results appear in PR comments, validation status appears as badges in HTML

---

## Meet the Team

### Team Member #1: Continuity Checker

**Specialty:** Path internal consistency

**What they check:**
- Character consistency (names, traits, relationships) within a single story path
- Plot coherence (events flow logically)
- Timeline accuracy (event sequences make sense)
- Setting consistency (locations, rules)
- Contradictions or plot holes within the path

**What they provide:**
- Severity rating (none/minor/major/critical)
- Issue type (character/plot/timeline/setting/contradiction)
- Description and location of issues
- Specific quotes demonstrating problems

---

### Team Member #2: World Fact Checker

**Specialty:** Validates against established canon in the Story Bible

**What they check:**
- World constants (setting, geography, world rules, magic systems)
- Character identity constants (names, backgrounds, core traits, relationships)
- Timeline facts (historical events before story start)

**What they DON'T check:**
- Plot events (those are variables, not constants)
- Player choices and outcomes (path-specific)
- Character fates (vary by path)

**What they provide:**
- Issue type (setting_constant, character_identity, timeline_fact)
- Severity (critical/major/minor)
- Established constant from Story Bible
- Contradicting content from new passage
- Evidence quotes from both sources
- Suggested resolution actions

**Note:** World Fact Checker only runs if the Story Bible cache exists. If missing, they sit this one out and suggest running `/extract-story-bible`.

For complete Story Bible feature details, see [features/story-bible.md](./story-bible.md)

---

### Future Team Members (Deferred)

Per PRIORITIES.md Phase 3, these specialists will join the team later:

- **Grammar Editor:** Checks spelling, punctuation, grammar
- **Style Editor:** Checks consistency in tone, voice, prose quality

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
- Team checks all new paths automatically on every PR
- Results posted within minutes of PR creation
- Clear feedback on specific continuity issues
- Issues categorized by severity (minor, major, critical)
- Can see exactly where in the path the issue occurs

---

### Story 2: Reviewer Approving PR
**As a** reviewer checking another author's PR
**I want** to see Team validation results before approving
**So that** I can focus on creative feedback instead of hunting for continuity bugs

**Acceptance Criteria:**
- Team validation runs automatically on every PR
- Results appear as PR comment
- Can trust that technical continuity is checked
- Can focus review on story quality and creative choices

---

### Story 3: Writer Fixing Issues
**As a** writer addressing Team-flagged issues
**I want** to understand what's wrong and how to fix it
**So that** I can resolve continuity problems quickly

**Acceptance Criteria:**
- Team explains specific issue clearly
- Provides quotes from story showing the problem
- Suggests severity level (helps prioritize fixes)
- Can re-run validation after fixing to confirm resolution

---

### Story 4: Writer Approving Valid Paths
**As a** writer who has reviewed Team feedback
**I want** to mark paths as validated so they're not re-checked
**So that** future validations run faster and focus on new content

**Acceptance Criteria:**
- Can approve paths with `/approve-path` command
- Approved paths skipped in future validations
- Validation cache updated automatically
- Approved paths re-checked only if content changes

---

### Story 5: Understanding Team Member Feedback
**As a** writer reviewing validation results
**I want** to know which team member flagged each issue
**So that** I understand the nature of the problem (path consistency vs. world canon)

**Acceptance Criteria:**
- PR comments have separate sections for each team member
- Clear headings show which team member found which issues
- Can distinguish between "path internal issues" and "Story Bible violations"
- Each section shows team member's specialty and what they checked

---

## Success Metrics

### Primary Metrics
- **Validation coverage:** 100% of PRs automatically validated
- **Feedback speed:** Results posted within minutes of PR workflow completion
- **Issue detection:** Team catches continuity errors before merge
- **Zero escaped errors:** No continuity issues merged to main branch

### Secondary Metrics
- **Validation efficiency:** New-only mode ~60% faster than full validation
- **Path approval rate:** Writers approve and dismiss issues regularly
- **False positive rate:** Low rate of incorrect issue flagging
- **Writer confidence:** Writers trust Team feedback and act on it

### Qualitative Metrics
- Writer feedback: "Team caught an issue I completely missed"
- No continuity errors discovered after merge
- Writers use validation modes appropriately (new-only → modified → all)

---

## Acceptance Criteria Summary

**Core Functionality:**
- [ ] Team validation runs automatically on every PR
- [ ] Results posted within minutes of PR workflow completion
- [ ] Clear, actionable feedback with specific quotes from passages
- [ ] Severity categorization (none/minor/major/critical)
- [ ] Issue location information (passage IDs) provided
- [ ] Three validation modes available (new-only/modified/all)
- [ ] Content-based change detection accurately categorizes paths

**Path Approval Workflow:**
- [ ] Writers can approve paths with `/approve-path` command
- [ ] Approved paths skipped in future validations
- [ ] Validation cache updated automatically on approval
- [ ] Approved paths re-checked only if content changes
- [ ] Path approval requires repository collaborator permissions

**Error Handling:**
- [ ] Service downtime does not block PR merges (validation is informational)
- [ ] Clear error messages for AI service failures
- [ ] Retry logic for transient failures
- [ ] Graceful handling of very long paths (context window limits)
- [ ] Concurrent PR validations handled without interference

**Team Member Integration:**
- [ ] Continuity Checker validates path internal consistency
- [ ] World Fact Checker loads Story Bible cache (if exists)
- [ ] World Fact Checker validates new content against established constants
- [ ] PR comments have separate sections per team member
- [ ] Clear distinction between team member findings in PR comments
- [ ] Works gracefully if Story Bible doesn't exist yet (World Fact Checker sits out)
- [ ] Single PR comment combines all team member reports

---

## How It Works

**Webhook Commands:**
```
/check-continuity              # Validate in new-only mode (default)
/check-continuity new-only     # Explicitly specify new-only mode
/check-continuity modified     # Validate NEW + MODIFIED paths
/check-continuity all          # Validate everything (full audit)
/approve-path <path-id>        # Mark path as validated
```
Use these webhook commands (as PR comments) to trigger Team validation or approve paths.

---

### How the Team Determines What to Validate

The Team automatically categorizes paths as **NEW**, **MODIFIED**, or **UNCHANGED** based on whether the path existed before and what content changed. This determines which paths need validation in each mode.

**Quick summary:**
- **NEW:** Route didn't exist before + contains novel prose → Always validated
- **MODIFIED:** Route existed but content changed, OR new route without novel prose → Validated in `modified` mode
- **UNCHANGED:** Route existed with no changes → Only validated in `all` mode

**Don't worry about the technical details** - the Team figures out what needs validation automatically. Just choose the validation mode based on what you changed and how thorough you want the check to be.

For detailed explanation of the categorization logic (two-level tests, decision tables, examples of passage splits, linter reformats, and compound changes), see [Understanding Path Categorization](../services/README.md#understanding-path-categorization-detailed) in the services documentation.

---

### Three Validation Modes

Based on these internal categories, you can choose how thoroughly to validate:

**Important:** These categories (NEW/MODIFIED/UNCHANGED) are used internally by the Team to determine what to validate. They don't appear in the AllPaths HTML interface. The AllPaths HTML shows date-based filters (created/modified last day/week) and validation status (validated or not), which serve different purposes (progress tracking and quality monitoring).

---

### Which Mode Should I Use?

**Quick Decision Guide:**

| What You Did | Recommended Mode | Why |
|--------------|------------------|-----|
| Added new passages/routes | **new-only** (default) | Fast feedback on your new story journeys |
| Daily writing (1-3 new passages) | **new-only** (default) | Validates new routes, skips existing paths you only linked to |
| Fixed issues from previous validation | **modified** | Check your fixes plus any paths affected by changes |
| Reformatted or linted passages | **modified** | Formatting creates MODIFIED paths that need re-checking |
| Ready to merge PR | **modified** | Ensure all affected routes validated before merge |
| Major refactoring or rewrites | **all** | Full story audit after significant structural changes |
| Monthly quality check | **all** | Periodic comprehensive validation |
| Updated AI model | **all** | Re-validate everything with new model |

**Still not sure?**
- **Default to new-only** for daily work - it's fast and covers what you just wrote
- **Use modified before merging** - ensures your changes didn't break existing paths
- **Use all sparingly** - only when you need comprehensive validation

---

#### Mode 1: new-only (Default)
**Validates:** Only NEW paths (routes that didn't exist before with novel prose)
**Skips:** MODIFIED and UNCHANGED paths
**Speed:** Fastest (~2-5 paths, 2-5 minutes typical)

**When to Use:**
- Automatic PR builds (default)
- Daily writing - get fast feedback on new routes you created today
- You added new passages/routes and want to validate just those new journeys

**Command:** `/check-continuity` or `/check-continuity new-only`

**Why this is the default:**
Your daily workflow adds 1 new passage with a new route. That creates 1 NEW path (a route that never existed before) and potentially 10+ MODIFIED paths (existing routes where you added a navigation option). You want fast feedback on your new routes, not to wait for re-validation of existing routes where you only tweaked navigation.

---

#### Mode 2: modified
**Validates:** NEW paths + MODIFIED paths (new routes + existing routes with revisions)
**Skips:** UNCHANGED paths only
**Speed:** Medium (~5-10 paths, 5-15 minutes typical)

**When to Use:**
- Before requesting PR review
- Pre-merge validation - ensure all affected routes checked
- After fixing issues in new paths
- After formatting/linter changes (these create MODIFIED paths, not NEW)

**Command:** `/check-continuity modified`

**When to use this:**
Eventually you want those MODIFIED paths checked. Even though the routes existed before, the content changed (could be prose edits, navigation tweaks, or even just formatting). Run this before merging to ensure the revised reading experience is validated.

---

#### Mode 3: all
**Validates:** Every single path (NEW, MODIFIED, and UNCHANGED)
**Skips:** Nothing
**Speed:** Slow (~all paths, 20-40 minutes for large stories)

**When to Use:**
- After major story refactoring
- Periodic full story audits
- Investigating cross-path issues
- After updating AI model

**Command:** `/check-continuity all`

---

### Where Validation Results Appear

**Validation results are surfaced in two places:**

1. **PR Comments (Primary Interface)**
   - Detailed validation results posted as GitHub PR comments
   - Shows progress updates as paths are checked
   - Organized by team member - each specialist has their own section
   - Lists issues found in each path with severity and quotes
   - Provides summary statistics (paths checked, issues found)
   - Writers can respond with `/approve-path` command

2. **Validation Cache (Status Tracking)**
   - Validation status stored in `allpaths-validation-status.json`
   - Tracks which paths have been validated
   - Status displayed in AllPaths HTML as badges
   - "Validated" badge: Path has been reviewed and approved
   - "New" badge: Path has not yet been validated

**Note:** The internal categorization (NEW/MODIFIED/UNCHANGED) is used by the Team to determine what to validate, but is not displayed in the HTML. The HTML shows validation status (validated or not) and date filters for progress tracking.

---

### PR Comment Format

**Validation results appear as GitHub PR comments with the following structure:**

**Start of validation:**
- Validation mode being used (new-only/modified/all)
- Count of paths in each category (new, modified, unchanged)
- Explanation of which paths will be validated in this mode

**For each validated path:**

**Team Member #1: Continuity Checker**
- Path ID and route description
- Overall result (none/minor/major/critical)
- Issues found with details:
  - Issue type (character/plot/timeline/setting/contradiction)
  - Severity level
  - Description of the problem
  - Specific quotes from passages demonstrating the issue
  - Location information (passage IDs)

**Team Member #2: World Fact Checker** (if Story Bible exists)
- Story Bible load status (loaded, missing, or outdated)
- Count of constants and characters validated against
- Story Bible violations found (if any) with:
  - Issue type (setting_constant, character_identity, timeline_fact)
  - Severity (critical/major/minor)
  - Established constant from Story Bible
  - Contradicting content from new passage
  - Evidence quotes from both sources
  - Suggested resolution actions

**Path approval instructions:**
- How to approve the path if issues are acceptable

**Validation complete:**
- Summary statistics (paths validated, paths skipped)
- Results breakdown by severity level per team member
- Next steps and recommendations

---

### Path Approval Workflow

**Writer reviews Team feedback and replies:**
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

### Edge Case 1: Team False Positives
**Scenario:** A team member flags issue that isn't actually a problem (e.g., intentional plot mystery)

**Current Behavior:**
- Issue appears in team member's section of PR comment
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
**Scenario:** A team member flags something that might or might not be an issue

**Current Behavior:**
- Team member assigns severity based on analysis
- Writer reviews and makes judgment call

**Desired Behavior:**
- Team member explains reasoning clearly
- Provides quotes demonstrating issue
- Writer makes final decision

**Status:** Working as intended - Team provides information, writer decides

---

### Edge Case 5: Cross-Path Issues
**Scenario:** Issue involves multiple paths (shared passage changes affect many paths)

**Current Behavior:**
- Each path validated independently
- Issue flagged in each affected path
- Can see pattern across multiple path results

**Desired Behavior:**
- Team identifies same issue in multiple paths
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

### Edge Case 8: Missing Story Bible
**Scenario:** World Fact Checker can't find Story Bible cache

**Current Behavior:**
- World Fact Checker sits out this validation
- PR comment shows informational note about missing Story Bible
- Only Continuity Checker section appears

**Desired Behavior:**
- Graceful handling - validation still succeeds
- Clear message that Story Bible validation was skipped
- Suggestion to run `/extract-story-bible` to enable World Fact Checker

**Status:** Working as intended - World Fact Checker is optional

See [architecture/002-validation-cache.md](../architecture/002-validation-cache.md) for technical design. For additional edge cases related to path categorization (unreachable paths, compound changes), see [services/README.md](../services/README.md#edge-cases-categorization).

---

## What Could Go Wrong?

### Risk 1: AI Model Quality Issues
**Impact:** High - incorrect or missing issue detection
**Mitigation:** Use well-tested model (gpt-oss:20b-fullcontext), iterate on prompts
**Fallback:** Writers do manual review, treat Team as assistants not authority

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
**Impact:** Medium - writers ignore Team if too many wrong flags
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

### Future Team Members (Phase 3)

Per PRIORITIES.md, these specialists will join the team in Phase 3:
- **Grammar Editor:** Spelling, punctuation, grammar checks
- **Style Editor:** Tone, voice, prose quality consistency

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

- [x] Team validation runs automatically on every PR
- [x] Results posted within minutes of PR completion
- [x] Clear, actionable feedback with specific quotes
- [x] Severity categorization (none/minor/major/critical)
- [x] Three validation modes (new-only/modified/all)
- [x] Path approval workflow working
- [x] Content-based change detection accurate
- [x] Zero continuity errors merged to main
- [x] PR comments organized by team member
- [x] World Fact Checker integrates Story Bible validation

---

## Related Documents

**User-facing:**
- [services/README.md](../services/README.md) - Webhook service usage and commands
- [PRINCIPLES.md](../PRINCIPLES.md) - "Automation Over Gatekeeping" principle
- [features/story-bible.md](./story-bible.md) - Story Bible feature PRD

**Architecture/Implementation:**
- [architecture/002-validation-cache.md](../architecture/002-validation-cache.md) - How selective validation works (categorization, cache, fingerprinting)
- [architecture/010-story-bible-design.md](../architecture/010-story-bible-design.md) - Story Bible architecture and Phase 2 integration
- [formats/allpaths/README.md](../formats/allpaths/README.md) - AllPaths format technical documentation
- [architecture/001-allpaths-format.md](../architecture/001-allpaths-format.md) - AllPaths architecture decision record

---

## Lessons Learned

### What Worked Well
- **Random passage IDs:** Dramatically improved AI accuracy
- **Selective validation modes:** Fast feedback for daily work, thorough validation when needed
- **Real-time progress updates:** Writers see results as paths complete, can start fixing while validation continues
- **Approval workflow:** Easy to mark paths as validated and move on
- **Team member organization:** Clear separation helps writers understand nature of each issue

### What Could Be Better
- **Prompt tuning:** Could further improve Team accuracy with more examples
- **Performance:** Could optimize for very large stories (100+ paths)
- **Mode guidance:** Could better guide writers on which mode to use when

### What We'd Do Differently
- **Earlier planning:** Random IDs added later, could have designed upfront
- **More prompt testing:** Could have tested more prompt variations before launching
- **Performance benchmarks:** Could have established baseline performance metrics earlier
- **Team metaphor from start:** Would have organized PR comments by specialty from day one
