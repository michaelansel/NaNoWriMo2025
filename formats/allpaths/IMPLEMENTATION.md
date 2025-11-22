# AllPaths Format - Implementation Notes

## Overview

This document contains implementation-level details for developers maintaining the AllPaths format generator and related tools. For architecture and design decisions, see `/architecture/001-allpaths-format.md`.

## Test Coverage

### Unit Tests (`test_generator.py`)

**Path Hashing & Fingerprinting:**
- Hash consistency across builds
- Hash changes with content modifications
- Hash changes with structure changes
- Content fingerprint independence from passage names
- Route hash calculation

**Path Categorization:**
- New path detection
- Unchanged path detection (exact match)
- Modified path detection (content changes)
- Modified path detection (restructuring/renames)
- Modified path detection (link additions) - **PR #65 scenario**
- Backward compatibility with old cache formats
- Handling of missing fingerprint fields
- Handling of non-dict cache entries

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
- Old cache without fingerprint field
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

### 2. Git Dependency for Optimal Categorization

**Issue:** Accurate detection of modified vs new paths requires git integration.

**Current Mitigation:**
- Falls back to cache-based detection when git unavailable
- All paths marked as 'modified' if in cache but no file-level data
- All paths marked as 'new' if not in cache

**Impact:** Without git:
- May re-check unchanged reorganizations (marked as 'modified')
- May miss some legitimate new content detection

**Workaround:** Always run in git repository with clean working tree.

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

### Why Three Fingerprints?

1. **path_hash**: Full identity (route + content + links) - uniquely identifies a specific path
2. **content_fingerprint**: Prose-only - detects content changes vs reorganizations
3. **raw_content_fingerprint**: Content + links - detects link changes vs prose changes
4. **route_hash**: Route structure only - detects passage renames

**Rationale:** Different operations need different granularity:
- Categorization needs to distinguish new content from reorganization
- Caching needs unique IDs that change on any modification
- Split detection needs to ignore whitespace and links

### Why Git Integration?

**Alternatives Considered:**
1. Only use path-level fingerprints (would miss file-level reorganizations)
2. Store all old passage content in cache (would bloat cache file)
3. Use file timestamps (unreliable with git operations)

**Why Git:**
- Already available in CI environment
- Provides authoritative "what changed" data
- Minimal overhead (uses existing git log)

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

**Symptom:** Paths marked as 'new' when should be 'unchanged'.

**Debug Steps:**
1. Check if git repo is clean: `git status`
2. Verify passage-to-file mapping: Run `scripts/show_twee_file_paths.py`
3. Compare fingerprints:
   ```python
   from generator import calculate_content_fingerprint, calculate_route_hash
   # Calculate for old and new, compare
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
- Fingerprint algorithm changes
- Major refactoring of passage structure

**Safe to Keep Cache When:**
- Adding new passages (incremental)
- Editing existing prose (fingerprints update automatically)
- Changing links only (fingerprints update automatically)

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
