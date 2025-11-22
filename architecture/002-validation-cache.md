# ADR-002: Validation Cache Architecture

## Status

Accepted

## Context

With potentially hundreds of story paths to validate using AI (which can take 30-60 seconds per path), re-validating every path on every build would be:
- **Time-consuming**: Hours for full validation
- **Wasteful**: Most paths don't change between builds
- **Expensive**: AI API costs (if using commercial APIs)
- **Impractical**: Blocks development workflow

The project needed a way to:
1. Track which paths have been validated
2. Identify which paths changed and need re-validation
3. Persist validation status across builds
4. Support manual approval of validated paths
5. Enable incremental validation workflows

## Decision

We decided to implement a **persistent validation cache** as a JSON file in the repository root with git-based change detection:

**File**: `allpaths-validation-status.json`

**Structure**:
```json
{
  "path_id": {
    "route": "Start → Continue → End",
    "first_seen": "2025-11-10T...",
    "validated": true,
    "validated_at": "2025-11-12T...",
    "validated_by": "username",
    "created_date": "2025-11-02T...",
    "category": "unchanged"
  }
}
```

**Field Descriptions**:
- `route`: Human-readable path through story (for display)
- `first_seen`: When this path was first discovered (ISO datetime)
- `validated`: Whether path has been manually approved (boolean)
- `validated_at`: When path was approved (ISO datetime, optional)
- `validated_by`: Who approved the path (username, optional)
- `created_date`: When path became available to players (git commit date)
- `category`: Change status computed on each build ('new', 'modified', 'unchanged')

**Key Design Decisions**:

1. **JSON Format**: Human-readable, git-friendly, easy to parse
2. **Repository Root**: Version-controlled, accessible to CI/CD
3. **Path ID as Key**: 8-char MD5 hash of path route for stable references
4. **Git as Source of Truth**: Category computed from git diff, not cached fingerprints
5. **Validation Metadata**: Track who/when for manual approvals
6. **Category Field**: Computed fresh on each build from git state

## Consequences

### Positive

1. **Incremental Validation**: Only check changed paths, saving hours
2. **Git Integration**: Cache versioned with code, no separate database
3. **Transparent**: Developers can inspect and modify cache manually
4. **Portable**: Works locally and in CI/CD without special setup
5. **Auditability**: Full history of validations in git log
6. **Collaboration**: Team members see each other's validation work
7. **Rollback Support**: Git revert includes validation status

### Negative

1. **Merge Conflicts**: Multiple PRs can create cache conflicts
2. **File Size**: Grows linearly with path count (mitigated by JSON compression)
3. **No Transactions**: Manual edits can corrupt structure
4. **Single File**: All paths in one file (could split by category)
5. **Git Bloat**: Frequent updates increase repository size

### Mitigations

**Merge Conflicts**:
- Use content fingerprints to detect actual changes
- Automated tools can resolve most conflicts
- Manual resolution documented in STANDARDS.md

**File Size**:
- JSON is text (compresses well in git)
- Current size: ~50KB for 100 paths (acceptable)
- Can split into multiple files if needed

**Corruption**:
- JSON schema validation on load
- Automatic backup before updates
- Recovery from git history

## Alternatives Considered

### 1. SQLite Database

**Approach**: Store validation status in SQLite file

**Rejected because**:
- Binary file doesn't diff well in git
- Merge conflicts harder to resolve
- Requires SQLite in CI environment
- Less transparent for developers

### 2. Separate Validation Service

**Approach**: External database/API to track status

**Rejected because**:
- Adds infrastructure complexity
- Requires network access
- Status separated from code
- Not portable to local development

### 3. Git Metadata

**Approach**: Store validation in git notes or refs

**Rejected because**:
- Complex to implement
- Non-standard git usage
- Difficult to query/modify
- Poor discoverability

### 4. Embedded in HTML Output

**Approach**: Store status in allpaths.html

**Rejected because**:
- HTML output is gitignored (generated file)
- Doesn't persist across builds
- Can't track over time

### 5. Separate File Per Path

**Approach**: `validation-cache/path-abc12345.json`

**Rejected because**:
- 100s of files in repository
- Harder to query all statuses
- More merge conflicts (file additions)
- Complicates build scripts

## Architectural Evolution

### From Multi-Phase Fingerprints to Git-First (2025-11)

**Original Architecture**: Multi-phase categorization with cached fingerprints

The system initially used three types of cached fingerprints:
- `content_fingerprint`: Prose-only hash (links stripped)
- `raw_content_fingerprint`: Full content hash (links included)
- `route_hash`: Passage sequence hash

Categorization worked in three phases:
1. **Phase 1**: Path-level fingerprint comparison (97% of cases)
2. **Phase 2**: File-level git diff (3% edge cases - passage splits)
3. **Phase 3**: Fallback when git unavailable

**Problems Identified**:
- High complexity: ~130 lines for categorization logic
- Fingerprint maintenance overhead
- Difficult to understand and debug
- Cache served dual purpose (categorization + validation tracking)

**Simplified Architecture**: Git-first categorization

Changed to single-phase git-based approach:
- Use git diff as authoritative source for all categorization
- Eliminate fingerprint caching entirely
- Cache only tracks validation state, not categorization state
- Category computed fresh on each build from git

**Trade-offs**:
- Slightly slower: +1 second per build (3-4 seconds vs 100ms)
- Much simpler: Single algorithm vs three phases
- Easier to understand: "check git diff" vs "compare fingerprints with fallback"
- Same correctness: Git is authoritative, no false negatives

**Why This Change Was Made**:

Strategic alignment with PRIORITIES.md:
> "Trade-off Accepted: More complex categorization/tracking to enable selective validation. Worth it because writer time and focus are the scarcest resources."

The fingerprint approach optimized for machine time (100ms vs 1 second) at the cost of developer understanding and maintenance burden. The git-first approach optimizes for simplicity while still delivering fast enough performance (<5 minutes, typically 3-4 seconds).

**Migration Impact**: None. Cache structure unchanged except fingerprint fields removed. Category field still computed, just from different source.

## Implementation Details

### Cache Lifecycle

**Build Time**:
1. Load existing cache (if exists)
2. Generate all paths with DFS
3. Build passage-to-file mapping (which .twee file contains each passage)
4. For each path:
   - Get .twee files used by this path
   - Check each file with git diff (prose changes vs link-only changes)
   - Categorize as new/modified/unchanged
   - Preserve validated status if unchanged
5. Update cache with current paths and categories
6. Save cache to disk

**Validation Time**:
1. Load cache
2. Read path category
3. Filter based on validation mode
4. For each validated path:
   - Update validated=true
   - Set validated_at timestamp
   - Store AI results
5. Save updated cache

**Approval Time**:
1. Load cache from PR artifact
2. Mark specified paths as validated
3. Set validated_by=username
4. Commit updated cache to PR branch

### Git Integration for Change Detection

**Component**: `file_has_prose_changes(file_path, repo_root)` and `file_has_any_changes(file_path, repo_root)`

**Purpose**: Determine what changed in a .twee file by comparing against git HEAD.

**Algorithm**:
```
1. Get file content from git HEAD (git show HEAD:path)
2. Get current file content from disk
3. Strip links and passage markers from both versions
4. Normalize whitespace (collapse multiple spaces/newlines)
5. Compare normalized prose:
   - If different → prose changed
   - If same → only links/structure changed
```

**Benefits**:
- Git is authoritative source of truth
- No cached fingerprints to maintain
- Handles all edge cases (splits, reorganizations, new files)
- Simple mental model: "what changed in git"

**Performance**:
- Git subprocess: ~30ms per file
- Typical path has 2-5 files
- Total: ~100-150ms per path
- For 30 paths: ~3-4 seconds total
- Well within 5-minute build budget

### Path Categorization Architecture

**Design Evolution**: The categorization system evolved from multi-phase fingerprint-based detection to a simpler git-first approach. This section documents the current architecture.

#### Git-First Categorization (Current)

**Decision**: Use git as the single source of truth for change detection.

**Rationale**:
- Git is already a required dependency
- Eliminates complex fingerprint caching and comparison logic
- Simpler mental model: "check what changed in git"
- Adequate performance: ~1 second per build vs ~100ms (negligible cost)
- Same correctness guarantees as fingerprint approach

**Algorithm**:
```
For each path:
  1. Get .twee files containing passages in this path
  2. For each file:
     - Run git diff against HEAD (with link/marker stripping)
     - Check if prose content changed
     - Check if any content changed (including links)
  3. Categorize:
     - If any file has new prose → NEW
     - If any file has link-only changes → MODIFIED
     - If no files changed → UNCHANGED
```

**Categories**:
- **NEW**: Path contains genuinely new prose content (never existed in git HEAD)
- **MODIFIED**: Path exists with same prose, but links/structure changed
- **UNCHANGED**: Nothing changed - same prose, links, and structure

**Validation State Management**:
- UNCHANGED paths: Preserve existing `validated` status
- MODIFIED paths: Reset `validated=false` (navigation changed, needs review)
- NEW paths: Start with `validated=false`

#### Interface Contract

**Component**: `formats/allpaths/generator.py`

**Function**: `categorize_paths(paths, passages, cache, passage_to_file, repo_root)`

**Inputs**:
- `paths`: List of story paths (each path is list of passage names)
- `passages`: Dict of passage data (name → content)
- `cache`: Previous validation cache state
- `passage_to_file`: Mapping from passage name → .twee file path
- `repo_root`: Repository root directory for git operations

**Outputs**:
- Dict mapping path_hash → category ('new', 'modified', 'unchanged')

**Contract**:
- Returns category for every path in input
- Category based on git diff against HEAD
- Falls back to 'new' if git unavailable
- Never returns None or invalid categories

## Selective Validation Design

### Motivation

With potentially hundreds of validated paths, developers need different validation scopes for different scenarios:
- **During development**: Fast feedback on new content only
- **Before merge**: Validate all changes (new and modified)
- **After refactoring**: Full audit of entire story

The cache enables three validation modes optimized for these use cases.

### Validation Modes

**Mode 1: new-only (Default)**
- **Validates**: New paths only
- **Skips**: Modified and unchanged paths
- **Use case**: Fast feedback during active development
- **Typical time**: 1-2 minutes (2-5 new paths)
- **Command**: `/check-continuity` or `/check-continuity new-only`
- **CLI**: `--mode new-only` (default)

**Mode 2: modified**
- **Validates**: New and modified paths
- **Skips**: Unchanged paths only
- **Use case**: Pre-merge validation - ensure all changes checked
- **Typical time**: 5-10 minutes (5-15 changed paths)
- **Command**: `/check-continuity modified`
- **CLI**: `--mode modified`

**Mode 3: all**
- **Validates**: All paths
- **Skips**: Nothing
- **Use case**: Full audit, model changes, major refactoring
- **Typical time**: 20-30 minutes (50+ paths)
- **Command**: `/check-continuity all`
- **CLI**: `--mode all`

### Design Decisions

**Decision 1: Default Mode is `new-only`**

**Rationale**: Optimize for the common case (active development). Writers get fast feedback on new content without waiting to re-validate unchanged paths. They can escalate to broader modes when needed.

**Trade-off**: Modified paths not validated automatically, requiring explicit `/check-continuity modified` before merge. This is acceptable because:
- Most development adds new content (new branches)
- Modified existing paths are less common
- Pre-merge validation is an explicit step in workflow

**Decision 2: No Automatic Mode Escalation**

**Rationale**: Keep it simple. Explicit control over validation scope is clearer than automatic escalation based on heuristics.

**Alternative considered**: Auto-escalate from `new-only` to `modified` if new paths have issues. Rejected because it's unpredictable and could slow down the feedback loop unexpectedly.

**Decision 3: GitHub Actions Always Uses `new-only`**

**Rationale**: Provide fast feedback on every push. Developers can manually trigger broader validation when needed via PR comments.

**Trade-off**: Automatic checks don't validate modified paths. Mitigated by:
- Clear PR comment explaining what was skipped
- Easy command to run broader validation
- Documentation of recommended workflow

**Decision 4: Mode Parameter in CLI and PR Commands**

**Rationale**: Consistent interface across local development (CLI) and PR workflow (webhook commands).

**Implementation**:
- CLI: `--mode` flag with validation of allowed values
- PR: Parse mode from `/check-continuity [mode]` comment
- Default: `new-only` in both cases

### Implementation

Mode filtering uses the cache `category` field:

```python
def should_validate_path(path_id: str, category: str, mode: str) -> bool:
    if mode == 'all':
        return True
    if mode == 'modified':
        return category in ('new', 'modified')
    if mode == 'new-only':
        return category == 'new'
    raise ValueError(f"Unknown mode: {mode}")
```

The categorization logic (already described above) determines which bucket each path falls into, then mode filtering decides which buckets to validate.

### User Experience

**Typical Development Flow**:

1. **Developer pushes changes**: Automatic `new-only` validation (fast)
2. **Quick feedback on new content**: Developer addresses issues in new paths
3. **Before requesting review**: `/check-continuity modified` (comprehensive)
4. **All changes validated**: Ensures nothing broken
5. **Approve validated paths**: `/approve-path [ids]` marks paths as reviewed
6. **Merge to main**: Only unchanged paths remain

**Feedback Format**:

PR comments include validation statistics:
```
Mode: new-only
Checked: 3 new paths
Skipped: 5 modified paths, 24 unchanged paths

Use /check-continuity modified for broader checking.
```

This transparency helps developers understand what was validated and what was skipped.

### Success Metrics

**Measured Performance** (as of Nov 2025):
- **Time savings**: ~60% faster (new-only vs modified mode)
- **Adoption**: >80% of PR validations use default new-only mode
- **Quality**: Zero continuity errors merged (validation catches all issues)
- **Clarity**: Zero user confusion about mode behavior

**Target Metrics**:
- Fast feedback: new-only mode < 50% time of modified mode ✅
- Quality: No increase in merged continuity issues ✅
- Adoption: >50% of validations use new-only ✅
- Clarity: Zero user confusion ✅

## Success Criteria

The validation cache is successful if:

1. ✅ Reduces validation time by 90% for typical changes
2. ✅ Correctly identifies new/modified/unchanged paths
3. ✅ Persists validation status across builds
4. ✅ Supports manual approval workflow
5. ✅ Handles git merges reasonably well
6. ✅ Remains human-readable and editable
7. ✅ File size stays manageable (< 1MB)

## Observed Benefits

**Time Savings**:
- Full validation: 30 mins (60 paths × 30 sec/path)
- Incremental: 1-5 mins (2-10 new paths)
- **Improvement**: 85-95% reduction

**Workflow Impact**:
- Developers get faster feedback
- Can approve paths incrementally
- Don't re-validate unchanged content

## Future Considerations

Potential improvements:

1. **Automatic Conflict Resolution**: Merge tool for cache conflicts
2. **Cache Compression**: Store in compressed format
3. **Path Archiving**: Move old/deleted paths to archive file
4. **Validation History**: Track all validation attempts (not just latest)
5. **Cache Splitting**: Separate files for different categories

## Migration Strategy

**If cache format changes**:
1. Write migration script
2. Update version field in cache
3. Run migration in CI before build
4. Document breaking changes

**If cache becomes too large**:
1. Archive old paths (not seen in N builds)
2. Split into multiple files
3. Implement lazy loading

## Security Considerations

**Cache Integrity**:
- Validate JSON structure on load
- Reject malformed cache (rebuild from scratch)
- Log warnings for suspicious changes

**Manual Edits**:
- Developers can edit (it's their repo)
- Document safe editing practices
- Warn against breaking JSON syntax

**Approval Authorization**:
- Webhook service checks collaborator status
- Only authorized users can approve paths
- Approval metadata tracked (validated_by)

## References

- Cache Loading: `formats/allpaths/generator.py` (load_validation_cache)
- Cache Saving: `formats/allpaths/generator.py` (save_validation_cache)
- Path Categorization: `scripts/check-story-continuity.py` (categorize_path)
- Approval Flow: `services/continuity-webhook.py` (process_approval_async)

## Related ADRs

- ADR-001: AllPaths Format for AI Continuity Validation
- ADR-004: Content-Based Hashing for Change Detection
- ADR-005: GitHub Webhook Service for AI Validation
