# AllPaths Format - Implementation Notes

## Overview

This document contains implementation-level details for developers maintaining the AllPaths format generator and related tools. For architecture and design decisions, see `/architecture/001-allpaths-format.md`.

## Test Coverage

### Unit Tests (`test_generator.py`)

**Path Hashing:**
- Hash consistency across builds
- Path identification via MD5 hash

**Path Categorization (Git-First):**
- NEW path detection (files with new prose via git diff)
- MODIFIED path detection (files with link-only changes via git diff)
- UNCHANGED path detection (no file changes in git)
- Passage split detection (same prose reorganized across files)
- Link addition detection - **PR #65 scenario**
- Fallback behavior when git unavailable (mark as NEW)
- Backward compatibility with old cache formats

**Link Stripping:**
- Simple link removal (`[[Target]]`)
- Arrow syntax (`[[Display->Target]]`)
- Whitespace normalization
- Same prose with different links produces identical stripped output

**Integration with Git:**
- Passage-to-file mapping
- Commit date retrieval for tracked files
- Handling of untracked files (returns None)
- Path similarity calculation

**Edge Cases:**
- Missing passages
- Very long paths (100+ passages)
- Very short paths (single passage)
- Special characters in passage names
- Empty passage text
- Cache save/load round-trip

### Integration Tests (`test_integration.py`)

**Full Workflow:**
1. Parse story HTML from Twee compilation
2. Build story graph from passages
3. Generate all paths using DFS
4. Calculate hashes and fingerprints
5. Categorize paths (new/modified/unchanged)
6. Generate passage ID mapping
7. Generate path text with IDs
8. Generate HTML output
9. Save and load validation cache

**Stress Scenarios:**
- Stories with cycles (limited by `max_cycles=1`)
- Content change detection
- Passage rename detection (structure unchanged)

**Backward Compatibility:**
- Old cache with deprecated fingerprint fields (ignored when reading)
- Cache with non-dict entries (metadata)
- Empty cache
- Real project data (if available)

**Real Data Tests:**
- Load actual validation cache
- Build passage-to-file mapping
- Git commit date retrieval

### What's NOT Tested

- **Network operations**: GitHub API calls in webhook service (would require mocking)
- **AI operations**: Ollama continuity checking (expensive, non-deterministic)
- **Webhook authentication**: GitHub webhook signature verification (would require test secrets)
- **Concurrency**: Thread safety of webhook job cancellation
- **File system edge cases**: Permissions errors, disk full, symlinks
- **Large-scale performance**: Behavior with 1000+ paths

## Known Limitations

### 1. Path Explosion with Cycles

**Issue:** Stories with many cycles can generate exponentially many paths.

**Current Mitigation:**
- `max_cycles=1` limits each passage to 2 visits maximum
- This prevents infinite loops but may miss some valid paths

**Example:**
```
A → B → A → C  (allowed, A visited twice)
A → B → A → B → A → C  (blocked, A visited 3 times)
```

**Impact:** Very branching stories may have hundreds of paths, slowing generation and validation.

**Future Improvement:** Could implement path length limit or detect when paths become too similar.

### 2. Git Dependency for Categorization

**Requirement:** Path categorization requires git integration.

**Git-First Architecture:**
- Uses `git show HEAD:path` to get previous file versions
- Compares prose content (with links stripped) to detect new prose
- Compares full content to detect link/structure changes
- Falls back to marking all paths as 'new' when git unavailable

**Fallback Behavior:** Without git:
- All paths marked as 'new' (conservative - ensures validation)
- No MODIFIED or UNCHANGED categories (requires git diff)

**Best Practice:** Always run in git repository with committed work.

### 3. Passage ID Mapping Size

**Issue:** 12-character hex IDs consume space in text files and AI prompts.

**Current Design:**
- MD5 hash truncated to 12 characters
- Provides ~281 trillion unique IDs (collision probability negligible)

**Alternative Considered:** 8 characters (same as path hashes) would save space but increase collision risk.

**Why Current Design:** 12 characters balance uniqueness with reasonable file sizes.

### 4. AI Prompt Injection Defense

**Issue:** Story text could contain instructions to trick the AI checker.

**Current Mitigations:**
1. Prompt explicitly warns AI to ignore story-embedded instructions
2. Heuristic validation flags suspiciously perfect responses
3. Manual review required for flagged responses

**Limitations:**
- Heuristics may false-positive on genuinely good stories
- Sophisticated attacks might bypass heuristics
- No formal proof of prompt injection resistance

**Best Practice:** Don't auto-approve paths with manual review flags.

### 5. File-Level Prose Change Detection Granularity

**Issue:** Detects changes at file level, not passage level.

**Scenario:**
```
File A contains: Passage 1, Passage 2
- Edit Passage 1 (new prose)
- Path using only Passage 2 is marked as NEW (even though Passage 2 unchanged)
```

**Current Behavior:** Conservative - marks entire path as NEW if any source file changed.

**Why Acceptable:**
- Safer to over-check than under-check
- Passage-level detection would require git blame parsing (complex)
- Edge case is rare in practice

**Impact:** May re-check some paths unnecessarily, but ensures no new content is missed.

### 6. HTML Output Size

**Issue:** Generated HTML files can be large for stories with many paths.

**Current Mitigations:**
- Paths collapsed by default (show/hide button)
- Filter buttons (new/modified/unchanged)
- Text files separated into `/allpaths-clean` and `/allpaths-metadata` directories

**Typical Sizes:**
- 10 paths: ~50-100 KB HTML
- 100 paths: ~500 KB - 1 MB HTML
- 1000 paths: ~5-10 MB HTML

**Browser Performance:** Most browsers handle up to ~10 MB HTML without issues.

### 7. Validation Cache Corruption Recovery

**Issue:** If cache file becomes corrupted (invalid JSON), validation state is lost.

**Current Mitigation:**
- `load_validation_cache()` returns empty dict on error
- Logs warning but continues
- Next build regenerates cache

**Improvement Opportunity:** Could implement cache backups or validation on save.

## Implementation Decisions

### Why Git-First Categorization?

**Design Evolution:** Originally used cached fingerprints (content_fingerprint, raw_content_fingerprint, route_hash) with multi-phase comparison. Simplified to git-first approach in 2025-11.

**Current Architecture:**
- Single source of truth: git diff against HEAD
- No fingerprint caching needed
- Simpler algorithm: check file changes directly

**Benefits:**
- Much simpler code (~40% reduction in categorize_paths complexity)
- Single-phase algorithm vs three-phase
- Easier to understand: "check git diff"
- Same correctness as fingerprint approach
- Git already available in CI environment

**Trade-offs:**
- Slightly slower: +3 seconds per build (3-4 seconds vs 100ms)
- Acceptable cost per strategic priorities (simplicity over 3 seconds)

**Why Not Fingerprints?**
- Optimized for machine time at cost of developer understanding
- Complex multi-phase algorithm hard to maintain
- Cache served dual purpose (categorization + validation tracking)
- Git provides same correctness more simply

### Why Passage ID Mapping?

**Problem:** AI sees passage names like "Day 5 KEB" and "Day 19 KEB", might flag timeline issues even when story is correct.

**Solution:** Replace passage names with random hex IDs in AI input.

**Trade-offs:**
- **Benefit:** AI judges continuity on content only, not misleading names
- **Cost:** Requires mapping file, translation step, larger prompt size
- **Decision:** Worth it - significantly reduces false positives

### Why Validation Modes?

**Problem:** Full validation is slow/expensive (5 min per path × 100 paths = 8+ hours).

**Solution:** Three modes balancing thoroughness vs speed:

1. **new-only** (default): Only genuinely new prose
   - Use: Automatic PR checks
   - Speed: Fast (only checks ~1-5 paths per PR)

2. **modified**: New + reorganizations/link changes
   - Use: Pre-merge validation
   - Speed: Medium (checks ~5-20 paths per PR)

3. **all**: Everything, ignoring cache
   - Use: Full audit, debugging
   - Speed: Slow (checks all paths)

**Key Insight:** Most PRs add 1-2 new passages, not 100. Selective checking is sufficient.

## Debugging Tips

### Path Categorization Issues

**Symptom:** Paths marked incorrectly (e.g., NEW when should be UNCHANGED).

**Debug Steps:**
1. Check git repo state: `git status` (should be clean, all changes committed)
2. Verify passage-to-file mapping: Run `scripts/show_twee_file_paths.py`
3. Test git diff manually:
   ```bash
   git show HEAD:src/yourfile.twee > /tmp/old.twee
   diff <(grep -v '^\[\[' /tmp/old.twee) <(grep -v '^\[\[' src/yourfile.twee)
   ```
4. Check categorization logic:
   ```python
   from generator import file_has_prose_changes, file_has_any_changes
   # Test on specific file
   ```

### AI Continuity Checker Not Working

**Symptom:** Ollama not responding or timing out.

**Debug Steps:**
1. Check Ollama is running: `curl http://localhost:11434/api/tags`
2. Check model is pulled: `ollama list | grep gpt-oss`
3. Test manually:
   ```bash
   curl -X POST http://localhost:11434/api/generate \
     -d '{"model":"gpt-oss:20b-fullcontext","prompt":"Test","stream":false}'
   ```
4. Check timeout (default 300s, may need increase for long paths)

### Webhook Not Triggering

**Symptom:** No AI check comments on PRs.

**Debug Steps:**
1. Check webhook service health: `curl http://localhost:5000/health`
2. Check GitHub webhook deliveries in repo settings
3. Verify webhook secret matches: Compare `WEBHOOK_SECRET` env var
4. Check service logs: Look for signature verification errors

## Performance Characteristics

### Generation (generator.py)

- **Time Complexity:** O(P × L) where P = num paths, L = avg path length
- **Typical Performance:**
  - 10 paths: < 1 second
  - 100 paths: ~5-10 seconds
  - 1000 paths: ~60-120 seconds

**Bottlenecks:**
- Git operations (1-2ms per file)
- File I/O for text file generation
- JSON serialization of large caches

### Validation (check-story-continuity.py)

- **Time Complexity:** O(N × T) where N = num new paths, T = AI response time
- **Typical Performance:**
  - 1 path: ~30-60 seconds
  - 10 paths: ~5-10 minutes
  - 100 paths: ~50-100 minutes (use `modified` or `new-only` mode!)

**Bottlenecks:**
- AI inference time (30-60s per path)
- Network latency to Ollama
- Prompt size (longer paths = slower)

## Maintenance Notes

### When to Regenerate Cache

The validation cache should be regenerated (deleted) when:
- Cache format changes (new fields added/removed)
- Git categorization logic changes significantly
- Major refactoring of passage structure

**Safe to Keep Cache When:**
- Adding new passages (incremental)
- Editing existing prose (category recomputed from git)
- Changing links only (category recomputed from git)
- Migrating from fingerprint to git-first architecture (backward compatible)

### Updating Test Fixtures

When modifying categorization logic:
1. Update `test_generator.py` with new scenarios
2. Run full test suite: `python3 formats/allpaths/test_generator.py`
3. Verify integration tests: `python3 formats/allpaths/test_integration.py`
4. Test with real project data: `npm run build` and check `allpaths.html`

### Adding New Validation Modes

To add a new mode (e.g., "quick" for only critical paths):
1. Add constant to `check-story-continuity.py`: `MODE_QUICK = 'quick'`
2. Update `VALID_MODES` list
3. Implement logic in `should_validate_path()`
4. Add CLI help text in `argparse` setup
5. Document in this file

---

**Last Updated:** 2025-11-22
**Maintainer:** Developer role in hierarchical workflow
