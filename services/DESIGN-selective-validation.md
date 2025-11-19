# Design Document: Selective Validation Modes

**Status:** Approved
**Date:** 2025-11-19
**Author:** Claude
**Reviewers:** michaelansel

## Problem Statement

The continuity checker currently validates all paths marked as unvalidated in the cache. This includes:
- Brand new paths (never seen before)
- Modified paths (content changed since last validation)
- Previously unvalidated paths

For active development, this means re-validating many paths whenever any passage changes, even if the developer only wants feedback on the new story branches they're actively working on. This slows down the development feedback loop.

## Goals

1. **Faster feedback loop** - Developers get quick validation on new content without waiting for modified paths
2. **Resource efficiency** - Reduce unnecessary AI calls by not re-validating unchanged content
3. **Flexibility** - Provide escalation path when comprehensive validation is needed
4. **Transparency** - Clear reporting of what was/wasn't checked
5. **Backward compatible** - Existing workflows continue working with sensible defaults

## Non-Goals

- Automatic mode escalation based on results
- Different validation modes per path
- Conditional approval workflows based on mode
- Validation result history tracking

## Proposed Solution

### Three Validation Modes

#### 1. `new-only` Mode (Default)
**Validates:** Only brand new paths (first time seen)
**Skips:** Modified paths (content changed) and unchanged paths
**Use case:** Quick validation during active development

**Example:**
```
✓ Checked 3 new paths
⊘ Skipped 5 modified paths (use `/check-continuity modified` to include)
⊘ Skipped 24 unchanged paths
```

#### 2. `modified` Mode
**Validates:** New paths + modified paths
**Skips:** Unchanged paths
**Use case:** Pre-merge validation - ensure all changes are checked

**Example:**
```
✓ Checked 3 new paths
✓ Checked 5 modified paths
⊘ Skipped 24 unchanged paths
```

#### 3. `all` Mode
**Validates:** Every single path
**Skips:** Nothing
**Use case:** Major refactoring, model changes, periodic full audits

**Example:**
```
✓ Checked all 32 paths (full validation)
```

### User Interface

#### CLI (scripts/check-story-continuity.py)
```bash
# Default (new-only)
python3 scripts/check-story-continuity.py dist/allpaths-text allpaths-validation-status.json

# Explicit mode selection
python3 scripts/check-story-continuity.py --mode new-only dist/allpaths-text allpaths-validation-status.json
python3 scripts/check-story-continuity.py --mode modified dist/allpaths-text allpaths-validation-status.json
python3 scripts/check-story-continuity.py --mode all dist/allpaths-text allpaths-validation-status.json
```

#### Webhook (GitHub PR Comments)
```
# Default (new-only) - implicit
/check-continuity

# Explicit mode selection
/check-continuity new-only
/check-continuity modified
/check-continuity all
```

#### GitHub Actions Workflow
- **Automatic PR triggers:** Always use `new-only` mode
- **Manual dispatch:** Allow mode selection via workflow input parameter

### Implementation Details

#### Path Categorization Logic

Use existing cache structure to categorize paths:

```python
def categorize_path(path_id: str, cache: dict) -> str:
    """Returns: 'new', 'modified', or 'unchanged'"""

    if path_id not in cache:
        return 'new'

    entry = cache[path_id]

    # If never validated, it's modified (existed before but changed)
    if not entry.get('validated', False):
        return 'modified'

    # If validated, it's unchanged (hash would change if content changed)
    return 'unchanged'
```

**Key insight:** The hash-based system automatically handles change detection:
- New path hash → never seen before → `new`
- Existing path hash, not validated → content changed, hash regenerated → `modified`
- Existing path hash, validated → no changes → `unchanged`

#### Mode Filtering

```python
def should_validate_path(path_id: str, category: str, mode: str) -> bool:
    """Determine if path should be validated based on mode"""

    if mode == 'all':
        return True

    if mode == 'modified':
        return category in ('new', 'modified')

    if mode == 'new-only':
        return category == 'new'

    raise ValueError(f"Unknown mode: {mode}")
```

#### Feedback Enhancement

Summary comment includes skip statistics:

```markdown
## Continuity Check Summary

**Mode:** new-only _(use `/check-continuity modified` or `/check-continuity all` for broader checking)_

### Validation Results
✓ **Checked:** 3 new paths
⊘ **Skipped:** 5 modified paths, 24 unchanged paths

### Issues Found
- 🟢 1 path with no issues
- 🟡 2 paths with minor issues
```

### Data Model Changes

No changes needed to `allpaths-validation-status.json` structure. Existing fields are sufficient:
- `first_seen`: Used to detect new vs. existing paths
- `validated`: Used to detect modified vs. unchanged paths
- Path hash: Automatic change detection

### Configuration

Default mode stored in constants, overridable via:
1. CLI: `--mode` flag
2. Webhook: Parse from comment command
3. Environment: Future enhancement (not in this design)

## User Experience Flow

### Scenario 1: Active Development

Developer is working on a new story branch with 2 new passages.

1. Developer pushes changes to PR
2. Workflow completes, webhook triggers
3. Service posts: "Found 2 new paths, 3 modified paths, 27 unchanged paths"
4. Service validates only 2 new paths (fast - ~2 minutes)
5. Developer gets quick feedback on new content
6. If issues found in new paths, developer can fix them
7. Before merge, developer runs `/check-continuity modified` to validate all changes

**Time savings:** 2 paths × 40s = 80s vs. 5 paths × 40s = 200s (60% faster)

### Scenario 2: Pre-Merge Validation

Developer has fixed all issues in new paths and is ready to merge.

1. Developer comments: `/check-continuity modified`
2. Service validates 2 new + 3 modified = 5 paths
3. All pass validation
4. PR is ready to merge

### Scenario 3: Major Refactoring

Developer refactored the story structure or updated the AI model.

1. Developer comments: `/check-continuity all`
2. Service validates all 32 paths (slow - ~20 minutes)
3. Full audit ensures nothing broke
4. Issues are addressed before merge

## Technical Decisions

### Decision 1: Default Mode is `new-only`
**Rationale:** Optimize for the common case (active development). Developers can escalate when needed.

### Decision 2: No Smart Mode
**Rationale:** Keep it simple. Explicit control over validation scope is clearer than automatic escalation.

### Decision 3: GitHub Actions Always Uses `new-only`
**Rationale:** Provide fast feedback on every push. Developers can manually trigger broader validation when needed.

### Decision 4: No Approval Workflow Changes
**Rationale:** Approval is about content review, not validation scope. Keep them separate.

## Testing Plan

### Unit Tests
1. Path categorization logic (`new`, `modified`, `unchanged`)
2. Mode filtering logic (`should_validate_path`)
3. Mode parsing from CLI args
4. Mode parsing from webhook comments

### Integration Tests
1. CLI with each mode on a test story with mixed path states
2. Webhook comment parsing with various formats
3. Summary comment generation with skip statistics

### Manual Testing
1. Create PR with new paths → verify only new paths validated
2. Comment `/check-continuity modified` → verify new + modified validated
3. Comment `/check-continuity all` → verify all paths validated
4. Verify skip statistics are accurate in comments

## Rollout Plan

### Phase 1: Implementation
1. Add mode parameter to CLI script
2. Add path categorization logic
3. Add mode filtering logic
4. Update summary output

### Phase 2: Webhook Integration
1. Parse mode from comment commands
2. Pass mode to CLI script
3. Update comment templates with mode info

### Phase 3: Documentation
1. Update `services/README.md` with mode descriptions
2. Add examples to CLI help text
3. Update GitHub Actions workflow comments

### Phase 4: Validation
1. Test all three modes on a real PR
2. Verify skip statistics are accurate
3. Verify performance improvements

## Success Metrics

- **Fast feedback:** Average validation time for `new-only` mode < 50% of `modified` mode
- **Adoption:** >50% of PR validations use default `new-only` mode
- **Quality:** No increase in merged continuity issues
- **Clarity:** Zero user confusion about mode behavior (measured by GitHub comments/issues)

## Future Enhancements

Potential future work (not in this design):
- Per-PR mode preferences (sticky mode selection)
- Auto-escalation suggestions ("new paths passed, consider running modified mode")
- Validation history visualization (show mode used for each validation)
- Environment-based defaults (dev vs. main branch)

## Open Questions

None - all questions resolved with reviewer.

## Approval

- [x] Product plan approved by michaelansel (2025-11-19)
- [ ] Implementation plan pending
- [ ] Implementation pending
- [ ] Testing pending
- [ ] Documentation pending

## References

- `scripts/check-story-continuity.py` - Main validation script
- `services/continuity-webhook.py` - Webhook service
- `formats/allpaths/generator.py` - Path generation and categorization
- `allpaths-validation-status.json` - Validation cache structure
