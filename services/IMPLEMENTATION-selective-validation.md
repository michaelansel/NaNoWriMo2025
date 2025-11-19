# Implementation Plan: Selective Validation Modes

**Design Doc:** DESIGN-selective-validation.md
**Status:** Ready for review
**Date:** 2025-11-19

## Overview

This document provides a detailed, step-by-step implementation plan for adding selective validation modes to the continuity checker.

## Architecture Changes

### 1. Core Logic (scripts/check-story-continuity.py)

#### 1.1 Add Mode Constants
```python
# Validation modes
MODE_NEW_ONLY = 'new-only'
MODE_MODIFIED = 'modified'
MODE_ALL = 'all'
VALID_MODES = [MODE_NEW_ONLY, MODE_MODIFIED, MODE_ALL]
DEFAULT_MODE = MODE_NEW_ONLY
```

**Location:** After imports, around line 27

#### 1.2 Add Path Categorization Function
```python
def categorize_path(path_id: str, cache: dict) -> str:
    """Categorize a path as 'new', 'modified', or 'unchanged'.

    Args:
        path_id: The 8-character path hash
        cache: The validation cache dictionary

    Returns:
        One of: 'new', 'modified', 'unchanged'

    Logic:
        - 'new': Path ID not in cache at all (never seen before)
        - 'modified': Path ID in cache but not validated (hash changed, needs re-check)
        - 'unchanged': Path ID in cache and validated (no changes)
    """
    if path_id not in cache:
        return 'new'

    path_info = cache[path_id]

    # If it's not a dict (e.g., "last_updated" metadata), treat as new
    if not isinstance(path_info, dict):
        return 'new'

    # If validated flag is True, no changes
    if path_info.get('validated', False):
        return 'unchanged'

    # In cache but not validated = content changed
    return 'modified'
```

**Location:** After `load_validation_cache`, around line 230

#### 1.3 Add Mode Filtering Function
```python
def should_validate_path(category: str, mode: str) -> bool:
    """Determine if a path should be validated based on its category and the mode.

    Args:
        category: Path category ('new', 'modified', 'unchanged')
        mode: Validation mode ('new-only', 'modified', 'all')

    Returns:
        True if path should be validated, False to skip
    """
    if mode == MODE_ALL:
        return True

    if mode == MODE_MODIFIED:
        return category in ('new', 'modified')

    if mode == MODE_NEW_ONLY:
        return category == 'new'

    raise ValueError(f"Invalid mode: {mode}")
```

**Location:** After `categorize_path`

#### 1.4 Modify `get_unvalidated_paths` Function

**Current signature (line 231):**
```python
def get_unvalidated_paths(cache: Dict, text_dir: Path) -> List[Tuple[str, Path]]:
```

**New signature:**
```python
def get_unvalidated_paths(cache: Dict, text_dir: Path, mode: str = DEFAULT_MODE) -> Tuple[List[Tuple[str, Path]], Dict[str, int]]:
    """Get list of paths that need validation based on mode.

    Args:
        cache: Validation cache dictionary
        text_dir: Directory containing path text files
        mode: Validation mode ('new-only', 'modified', 'all')

    Returns:
        Tuple of:
        - List of (path_id, text_file_path) tuples to validate
        - Dictionary of statistics: {'new': N, 'modified': N, 'unchanged': N, 'checked': N, 'skipped': N}
    """
```

**Implementation changes:**
1. Loop through all text files
2. Categorize each path using `categorize_path()`
3. Track statistics for each category
4. Filter based on `should_validate_path(category, mode)`
5. Return both filtered list and statistics

**Pseudo-code:**
```python
stats = {'new': 0, 'modified': 0, 'unchanged': 0}
to_validate = []

for txt_file in sorted(text_dir.glob("*.txt")):
    path_id = extract_path_id(txt_file)
    category = categorize_path(path_id, cache)
    stats[category] += 1

    if should_validate_path(category, mode):
        to_validate.append((path_id, txt_file))

stats['checked'] = len(to_validate)
stats['skipped'] = sum(stats[c] for c in ['new', 'modified', 'unchanged']) - stats['checked']

return to_validate, stats
```

#### 1.5 Update `check_paths_with_progress` Function

**Current signature (line 371):**
```python
def check_paths_with_progress(
    text_dir: Path,
    cache_file: Path,
    progress_callback: Optional[Callable[[int, int, Dict], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    id_to_name: Optional[Dict[str, str]] = None
) -> Dict:
```

**New signature:**
```python
def check_paths_with_progress(
    text_dir: Path,
    cache_file: Path,
    progress_callback: Optional[Callable[[int, int, Dict], None]] = None,
    cancel_event: Optional[threading.Event] = None,
    id_to_name: Optional[Dict[str, str]] = None,
    mode: str = DEFAULT_MODE
) -> Dict:
```

**Changes:**
1. Add `mode` parameter
2. Pass `mode` to `get_unvalidated_paths()`
3. Capture statistics from `get_unvalidated_paths()`
4. Include statistics in return value
5. Update console output to show mode and statistics

**Return value update:**
```python
return {
    "checked_count": checked_count,
    "paths_with_issues": paths_with_issues,
    "summary": f"Checked {checked_count} path(s), found issues in {len(paths_with_issues)}",
    "mode": mode,
    "statistics": stats  # {'new': N, 'modified': N, 'unchanged': N, 'checked': N, 'skipped': N}
}
```

#### 1.6 Update `main()` Function

**Current usage parsing (line 479-486):**
```python
if len(sys.argv) < 3:
    print("Usage: check-story-continuity.py <text_dir> <cache_file>", file=sys.stderr)
    sys.exit(1)

text_dir = Path(sys.argv[1])
cache_file = Path(sys.argv[2])
```

**New usage parsing:**
```python
import argparse

def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description='AI-based story continuity checker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check only new paths (default)
  %(prog)s dist/allpaths-text allpaths-validation-status.json

  # Check new and modified paths
  %(prog)s --mode modified dist/allpaths-text allpaths-validation-status.json

  # Check all paths
  %(prog)s --mode all dist/allpaths-text allpaths-validation-status.json
        """
    )

    parser.add_argument('text_dir', type=Path,
                        help='Directory containing path text files')
    parser.add_argument('cache_file', type=Path,
                        help='Path to validation cache JSON file')
    parser.add_argument('--mode', choices=VALID_MODES, default=DEFAULT_MODE,
                        help=f'Validation mode (default: {DEFAULT_MODE})')

    args = parser.parse_args()

    if not args.text_dir.exists() or not args.text_dir.is_dir():
        parser.error(f"{args.text_dir} is not a valid directory")

    # Run checks with specified mode
    result = check_paths_with_progress(
        args.text_dir,
        args.cache_file,
        mode=args.mode
    )

    # Output results with statistics
    print("\n=== RESULTS ===", file=sys.stderr)
    print(f"Mode: {result['mode']}", file=sys.stderr)
    if 'statistics' in result:
        stats = result['statistics']
        print(f"New paths: {stats['new']}", file=sys.stderr)
        print(f"Modified paths: {stats['modified']}", file=sys.stderr)
        print(f"Unchanged paths: {stats['unchanged']}", file=sys.stderr)
        print(f"Checked: {stats['checked']}", file=sys.stderr)
        print(f"Skipped: {stats['skipped']}", file=sys.stderr)
    print(json.dumps(result, indent=2))
```

**Location:** Replace existing `main()` function (lines 477-499)

---

### 2. Webhook Service (services/continuity-webhook.py)

#### 2.1 Add Mode Parsing Function

```python
def parse_check_command_mode(comment_body: str) -> str:
    """Parse validation mode from /check-continuity command.

    Supported formats:
        /check-continuity           -> 'new-only' (default)
        /check-continuity new-only  -> 'new-only'
        /check-continuity modified  -> 'modified'
        /check-continuity all       -> 'all'

    Args:
        comment_body: The comment text

    Returns:
        One of: 'new-only', 'modified', 'all'
    """
    # Match /check-continuity optionally followed by a mode
    match = re.search(r'/check-continuity(?:\s+(new-only|modified|all))?', comment_body, re.IGNORECASE)

    if not match:
        return 'new-only'  # Default if command not found

    mode = match.group(1)
    if mode:
        return mode.lower()

    return 'new-only'  # Default if no mode specified
```

**Location:** After `is_authorized()` function, around line 940

#### 2.2 Add Check Continuity Command Handler

```python
def handle_check_continuity_command(payload):
    """Handle /check-continuity command from PR comments."""
    comment_body = payload['comment']['body']
    pr_number = payload['issue']['number']
    username = payload['comment']['user']['login']
    comment_id = payload['comment']['id']

    # Deduplication check
    with metrics_lock:
        now = time.time()
        expired_ids = [cid for cid, ts in processed_comment_ids.items() if now - ts > COMMENT_DEDUP_TTL]
        for cid in expired_ids:
            del processed_comment_ids[cid]

        if comment_id in processed_comment_ids:
            app.logger.info(f"Ignoring duplicate /check-continuity for comment {comment_id}")
            return jsonify({"message": "Duplicate webhook"}), 200

        processed_comment_ids[comment_id] = now

    # Parse mode from command
    mode = parse_check_command_mode(comment_body)

    app.logger.info(f"Received /check-continuity command for PR #{pr_number} with mode={mode}")

    # Get PR info
    pr_info = get_pr_info(pr_number)
    if not pr_info:
        post_pr_comment(pr_number, "⚠️ Could not retrieve PR information")
        return jsonify({"message": "PR info error"}), 500

    # Trigger workflow re-run with manual webhook (simulated workflow_run)
    # Actually, we should just process directly like workflow_run does
    # Spawn background thread for processing
    thread = threading.Thread(
        target=process_pr_check_async,
        args=(pr_number, pr_info['head']['sha'], pr_info['head']['ref'], mode),
        daemon=True
    )
    thread.start()

    return jsonify({"message": "Check started", "mode": mode}), 202
```

**Location:** After `parse_check_command_mode()`, around line 960

#### 2.3 Update `handle_comment_webhook` Function

**Current location:** Line 855

**Changes:**
1. Add check for `/check-continuity` command
2. Route to `handle_check_continuity_command()` if found
3. Keep existing `/approve-path` logic

**Updated function:**
```python
def handle_comment_webhook(payload):
    """Handle issue_comment webhooks for commands."""
    action = payload.get('action')
    if action != 'created':
        return jsonify({"message": "Not a new comment"}), 200

    # Check if it's a PR (not an issue)
    if 'pull_request' not in payload.get('issue', {}):
        return jsonify({"message": "Not a PR comment"}), 200

    comment_body = payload['comment']['body']

    # Route to appropriate handler
    if re.search(r'/check-continuity\b', comment_body):
        return handle_check_continuity_command(payload)
    elif re.search(r'/approve-path\b', comment_body):
        return handle_approve_path_command(payload)
    else:
        return jsonify({"message": "No recognized command"}), 200
```

**Note:** Extract existing `/approve-path` logic into new `handle_approve_path_command()` function (lines 870-922)

#### 2.4 Update `process_pr_check_async` Function

**Current location:** Lines 476-774

**Changes:**
1. Add `mode` parameter (default: 'new-only')
2. Pass `mode` to `check_paths_with_progress()`
3. Update initial comment to show mode
4. Update summary comment with statistics

**Function signature update:**
```python
def process_pr_check_async(pr_number: int, commit_sha: str, branch_name: str, mode: str = 'new-only'):
```

**Initial comment update:**
```python
initial_comment = f"""## 🤖 AI Continuity Check - Starting

**Mode:** `{mode}` _{mode_explanation[mode]}_

Found **{total_paths}** path(s) to check.

**Paths to validate:**
{path_list}

_This may take up to 5 minutes per passage. Updates will be posted as each path completes._

💡 **Commands:**
- Check with different scope: `/check-continuity modified` or `/check-continuity all`
- Approve paths: `/approve-path abc12345 def67890`

----
_Powered by Ollama (gpt-oss:20b-fullcontext)_
"""
```

Where `mode_explanation` is:
```python
mode_explanation = {
    'new-only': '(checking only new paths)',
    'modified': '(checking new and modified paths)',
    'all': '(checking all paths)'
}
```

**Summary comment update:**
Add statistics section:
```python
# Build statistics section
stats = results.get('statistics', {})
stats_text = ""
if stats:
    stats_text = f"""
### Validation Scope
- ✓ **Checked:** {stats['checked']} path(s)
- ⊘ **Skipped:** {stats['skipped']} path(s)
  - {stats['new']} new, {stats['modified']} modified, {stats['unchanged']} unchanged

_Used `{mode}` mode. Use `/check-continuity modified` or `/check-continuity all` for broader checking._
"""
```

#### 2.5 Update `handle_workflow_webhook` Function

**Current location:** Line 800

**Changes:**
Pass default mode when triggering from workflow_run webhook:

```python
def handle_workflow_webhook(payload):
    # ... existing validation code ...

    # Spawn background thread for processing
    thread = threading.Thread(
        target=process_pr_check_async,
        args=(pr_number, commit_sha, branch_name, 'new-only'),  # Always use new-only for auto-triggers
        daemon=True
    )
    thread.start()
```

---

### 3. GitHub Actions Workflow

**File:** `.github/workflows/build-and-deploy.yml`

No changes required for Phase 1. The workflow will continue to automatically trigger validation on PR builds, which will use the default `new-only` mode.

**Optional (Future):** Add manual workflow_dispatch trigger with mode selection:
```yaml
on:
  workflow_dispatch:
    inputs:
      mode:
        description: 'Validation mode'
        required: true
        type: choice
        options:
          - new-only
          - modified
          - all
        default: new-only
```

---

### 4. Documentation Updates

#### 4.1 Update services/README.md

**Location:** Line 265 (Approving Validated Paths section)

**Add new section before "Approving Validated Paths":**

```markdown
## Validation Modes

The continuity checker supports three validation modes:

### 🆕 `new-only` Mode (Default)
**Validates:** Only brand new paths (never seen before)
**Skips:** Modified and unchanged paths
**Use case:** Quick validation during active development

Example:
```
/check-continuity
```
or
```
/check-continuity new-only
```

### 📝 `modified` Mode
**Validates:** New paths + modified paths (content changed since last validation)
**Skips:** Unchanged paths
**Use case:** Pre-merge validation - ensure all changes are checked

Example:
```
/check-continuity modified
```

### 🔍 `all` Mode
**Validates:** Every single path, regardless of validation status
**Skips:** Nothing
**Use case:** Major refactoring, model changes, periodic full audits

Example:
```
/check-continuity all
```

### Default Behavior

- **Automatic PR builds:** Always use `new-only` mode for fast feedback
- **Manual commands:** Default to `new-only` if no mode specified
- **CLI usage:** Default to `new-only` unless `--mode` flag provided

### Understanding Path Categories

The checker categorizes paths as:
- **New:** Path never seen before (new story branch)
- **Modified:** Path existed before but content changed (hash changed)
- **Unchanged:** Path validated and no changes since last validation

The content-based hash system automatically detects changes. If you edit any passage in a validated path, it becomes "modified" and requires re-validation.

### Recommended Workflow

1. **During development:** Let automatic checks run with `new-only` mode
2. **Before requesting review:** Run `/check-continuity modified` to validate all changes
3. **After major refactoring:** Run `/check-continuity all` for full audit
```

#### 4.2 Update CLI Help Text

Already covered in section 1.6 (argparse epilog)

#### 4.3 Update formats/allpaths/README.md

**Add section about validation modes:**

```markdown
## Validation Modes

When running continuity checks, you can specify different validation modes:

- `new-only`: Check only new paths (default)
- `modified`: Check new and modified paths
- `all`: Check all paths

See `services/README.md` for detailed documentation.
```

---

## Testing Plan

### Phase 1: Unit Testing

#### Test 1: Path Categorization
```python
def test_categorize_path():
    # Test new path
    cache = {}
    assert categorize_path('abc12345', cache) == 'new'

    # Test modified path (in cache but not validated)
    cache = {'abc12345': {'validated': False}}
    assert categorize_path('abc12345', cache) == 'modified'

    # Test unchanged path (in cache and validated)
    cache = {'abc12345': {'validated': True}}
    assert categorize_path('abc12345', cache) == 'unchanged'
```

#### Test 2: Mode Filtering
```python
def test_should_validate_path():
    # new-only mode
    assert should_validate_path('new', 'new-only') == True
    assert should_validate_path('modified', 'new-only') == False
    assert should_validate_path('unchanged', 'new-only') == False

    # modified mode
    assert should_validate_path('new', 'modified') == True
    assert should_validate_path('modified', 'modified') == True
    assert should_validate_path('unchanged', 'modified') == False

    # all mode
    assert should_validate_path('new', 'all') == True
    assert should_validate_path('modified', 'all') == True
    assert should_validate_path('unchanged', 'all') == True
```

#### Test 3: Mode Parsing
```python
def test_parse_check_command_mode():
    assert parse_check_command_mode('/check-continuity') == 'new-only'
    assert parse_check_command_mode('/check-continuity new-only') == 'new-only'
    assert parse_check_command_mode('/check-continuity modified') == 'modified'
    assert parse_check_command_mode('/check-continuity all') == 'all'
    assert parse_check_command_mode('/check-continuity ALL') == 'all'  # case insensitive
```

### Phase 2: Integration Testing

#### Test 4: CLI with Each Mode
```bash
# Create test data with mixed path states
mkdir test-paths
# Create new, modified, unchanged paths

# Test new-only mode
python3 scripts/check-story-continuity.py test-paths test-cache.json --mode new-only
# Verify only new paths checked

# Test modified mode
python3 scripts/check-story-continuity.py test-paths test-cache.json --mode modified
# Verify new + modified paths checked

# Test all mode
python3 scripts/check-story-continuity.py test-paths test-cache.json --mode all
# Verify all paths checked
```

#### Test 5: Statistics Accuracy
```bash
# Verify output statistics match actual categorization
python3 scripts/check-story-continuity.py dist/allpaths-text allpaths-validation-status.json --mode new-only
# Check that stats.new + stats.modified + stats.unchanged == total files
# Check that stats.checked + stats.skipped == total files
```

### Phase 3: Webhook Testing

#### Test 6: Comment Command Parsing
1. Create test PR
2. Comment `/check-continuity` → should use new-only mode
3. Comment `/check-continuity modified` → should use modified mode
4. Comment `/check-continuity all` → should use all mode
5. Verify webhook logs show correct mode parsing

#### Test 7: End-to-End PR Flow
1. Create PR with new paths
2. Wait for automatic check (should use new-only)
3. Verify initial comment shows mode
4. Verify summary shows statistics
5. Comment `/check-continuity modified`
6. Verify re-check with modified mode
7. Compare execution times (new-only should be faster)

### Phase 4: Manual Validation

#### Test 8: Real Story Changes
1. Create branch with 2 new passages
2. Push to PR
3. Verify only 2 new paths checked
4. Modify existing passage
5. Push to PR
6. Verify still only new paths checked (modified path skipped)
7. Run `/check-continuity modified`
8. Verify modified path now checked

#### Test 9: Performance Validation
1. PR with N new paths, M modified paths
2. Time `new-only` mode: ~N × 40s
3. Time `modified` mode: ~(N+M) × 40s
4. Verify `new-only` is significantly faster when M > 0

---

## Implementation Order

### Step 1: Core Logic (2-3 hours)
- [ ] Add mode constants
- [ ] Add `categorize_path()` function
- [ ] Add `should_validate_path()` function
- [ ] Modify `get_unvalidated_paths()` to return statistics
- [ ] Update `check_paths_with_progress()` with mode parameter
- [ ] Update `main()` with argparse and mode flag
- [ ] Test CLI locally with all three modes

### Step 2: Webhook Integration (2-3 hours)
- [ ] Add `parse_check_command_mode()` function
- [ ] Add `handle_check_continuity_command()` function
- [ ] Extract `/approve-path` logic into `handle_approve_path_command()`
- [ ] Update `handle_comment_webhook()` to route commands
- [ ] Update `process_pr_check_async()` with mode parameter and statistics
- [ ] Update `handle_workflow_webhook()` to pass default mode
- [ ] Test locally with simulated webhooks

### Step 3: Documentation (1 hour)
- [ ] Update `services/README.md` with modes section
- [ ] Update `formats/allpaths/README.md`
- [ ] Verify CLI help text is clear

### Step 4: Testing & Validation (2-3 hours)
- [ ] Run unit tests
- [ ] Test CLI with real story data
- [ ] Create test PR and test all three modes
- [ ] Verify statistics are accurate
- [ ] Verify performance improvements
- [ ] Test edge cases (empty paths, all unchanged, etc.)

### Step 5: Deployment (1 hour)
- [ ] Commit all changes
- [ ] Push to feature branch
- [ ] Restart webhook service with new code
- [ ] Monitor first real PR for issues

**Total estimated time:** 8-11 hours

---

## Rollback Plan

If issues are discovered post-deployment:

1. **Webhook service:** Restart with previous commit
   ```bash
   git checkout HEAD~1 services/continuity-webhook.py
   systemctl --user restart continuity-webhook
   ```

2. **CLI:** Previous version still works (backward compatible)
   ```bash
   # Old usage still works (mode defaults to new-only)
   python3 scripts/check-story-continuity.py dist/allpaths-text cache.json
   ```

3. **Data:** No schema changes, cache format unchanged

---

## Success Criteria

- [ ] All three modes work correctly (new-only, modified, all)
- [ ] Default mode (new-only) provides 50%+ time savings when modified paths exist
- [ ] Statistics are accurate in all cases
- [ ] PR comments clearly show mode and skip statistics
- [ ] `/check-continuity` command parses modes correctly
- [ ] Backward compatibility maintained (old calls still work)
- [ ] No regressions in existing functionality
- [ ] Documentation is clear and complete

---

## Future Enhancements

Not included in this implementation:

1. Environment-based defaults (dev vs. main branch)
2. Workflow dispatch with mode selection
3. Per-PR mode preferences (sticky settings)
4. Auto-escalation suggestions
5. Validation history tracking
6. Web dashboard with mode analytics

---

## Questions for Review

1. Should CLI default to `new-only` or `modified`? ✓ Answered: new-only
2. Should we add workflow dispatch? Not in Phase 1
3. Should statistics be in separate comment? No, inline is fine
4. Should we add `/check-continuity help` command? Optional, not required

---

## Approval

- [ ] Implementation plan approved
- [ ] Ready to begin implementation
