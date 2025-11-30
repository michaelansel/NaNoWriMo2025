# Feature Requirements: Chunked Extraction for Story Bible

**Status:** Ready for Architect Review
**Owner:** Product Manager
**Priority:** High (Improves extraction quality significantly)
**CEO Approval:** Granted (2025-11-30)

---

## Executive Summary

Replace the current path-based extraction approach with a chunked per-passage extraction method to dramatically improve character and fact coverage in the Story Bible. Experimental results show:

- **Current approach:** 5 characters, 19 total facts (extracts from assembled story paths)
- **Chunked approach:** 15 characters, 116 total facts (extracts from individual passages)

The chunked approach catches characters and facts that path-based extraction misses because it processes each passage independently rather than trying to extract from entire assembled paths.

---

## Problem Statement

The current Story Bible extraction reads from `dist/allpaths-metadata/path-*.txt` files, which contain complete story paths assembled from multiple passages. This creates two problems:

1. **Context window overflow:** Long paths exceed AI model context limits, forcing the model to truncate or skim
2. **Diluted focus:** When extracting from a 10-passage path, the AI struggles to extract facts from middle/end passages that appear later in the input

**Evidence from experiments:**
- Current method (path-based): 5 characters detected (Javlyn, Terence, Danita, Kian, Jerrick)
- Chunked method (passage-based): 15 characters detected (adds Nivek, Eldon, Salie, Jeramee, Avery, Jessie, Maureen, Blue creature, Cave creature, Javlyn's Mother)
- Character identity facts: 365 total in current cache, but only 5 unique characters vs 15 in chunked

**Root cause:** The current approach loads full story paths, which can be very long. The AI model processes these as single extraction requests, leading to incomplete extraction from later passages in each path.

---

## User Stories

### Story 1: Author Reviewing Complete Character List
**As a** writer reviewing the Story Bible
**I want** to see ALL characters mentioned in my story
**So that** I can verify completeness and avoid missing minor characters

**Acceptance Criteria:**
- Story Bible captures all characters with speaking roles or significant mentions
- Minor characters (Nivek, Eldon, Salie, etc.) are detected, not just protagonists
- Character list matches author's mental model of "who appears in my story"
- Extraction does not miss characters due to position in long paths

---

### Story 2: Author Understanding Fact Coverage
**As a** writer using the Story Bible
**I want** to know how many facts were extracted per passage
**So that** I can identify passages with rich world-building vs sparse content

**Acceptance Criteria:**
- Metadata shows extraction statistics per passage
- Can see which passages contributed most facts
- Can identify passages that failed extraction or had low yield
- Statistics help validate extraction quality

---

### Story 3: Validating Extraction Quality
**As a** developer maintaining the Story Bible feature
**I want** to verify that extraction quality is high
**So that** I can trust the Story Bible as a reliable reference

**Acceptance Criteria:**
- Clear metrics for extraction quality beyond raw fact count
- Can measure: character coverage, fact distribution, extraction success rate
- Can compare extraction quality across different approaches
- Quality metrics inform when to improve prompts or methods

---

## Requirements

### REQ-1: Passage-Based Extraction (Primary Change)

**Requirement:** Extract facts from individual passages, not assembled story paths.

**Current behavior (path-based):**
```
For each path in dist/allpaths-metadata/path-*.txt:
    Load entire path (all passages concatenated)
    Extract facts from complete path
    Store facts with path context
```

**New behavior (passage-based):**
```
For each unique passage across all paths:
    Load single passage text
    Extract facts from this passage only
    Store facts with passage context and evidence
    Track which paths contain this passage
```

**Rationale:**
- Each passage extraction stays well within context window limits
- AI focuses on one passage at a time, improving extraction quality
- Natural deduplication: same passage appears in multiple paths but only extracted once
- Experimental evidence: 3x character coverage, 6x fact coverage

**Implementation Notes:**
- Modify loader to collect unique passages instead of loading paths
- Use existing passage deduplication logic from `formats/story-bible/modules/loader.py`
- Each passage already has `appears_in_paths` tracking which paths contain it
- Extraction prompt focuses on single passage, not path narrative flow

---

### REQ-2: Chunking for Large Passages

**Requirement:** If a single passage exceeds safe context limits, split it into chunks.

**Threshold:** 20,000 characters per chunk (conservative, allows room for prompt template)

**Behavior:**
- Most passages fit in single chunk (typical passage is < 5,000 chars)
- Large passages split at natural boundaries (paragraph breaks preferred)
- Each chunk extracted independently
- Facts from chunks of same passage are merged during summarization

**Edge case handling:**
- If passage has no natural break points, split at character limit
- Preserve context by including passage name in each chunk
- Tag extracted facts with chunk number for debugging
- Summarization step merges facts from same passage chunks

**Rationale:**
- Experimental script uses 20k char chunks successfully
- Most passages won't need chunking (optimization for rare large passages)
- Chunking is transparent to downstream processing (summarization handles it)

---

### REQ-3: Per-Passage Fact Count Metric

**Requirement:** Track and report number of facts extracted per passage.

**Metadata to collect:**
```json
{
  "extraction_stats": {
    "total_passages": 62,
    "passages_with_facts": 58,
    "passages_with_no_facts": 4,
    "average_facts_per_passage": 2.6,
    "max_facts_in_passage": 15,
    "passages_by_fact_count": {
      "0": ["passage_id_1", "passage_id_2"],
      "1-5": ["passage_id_3", ...],
      "6-10": [...],
      "11+": [...]
    }
  }
}
```

**Display in extraction report:**
```
Extraction complete: 62 passages processed
  Facts extracted: 160 total (avg 2.6 per passage)
  High-yield passages: 5 passages with 11+ facts
  No facts: 4 passages (empty or system passages)
```

**Rationale:**
- Helps validate extraction quality (too many "0 fact" passages suggests problem)
- Identifies rich world-building passages (high fact count)
- Debugging aid: passages with surprisingly low/high fact counts
- Quality metric: distribution should match passage content density

---

### REQ-4: Character Coverage Threshold

**CEO Question 1:** What character coverage threshold defines success?

**Answer:** Aim for 90%+ character coverage of "named characters with roles."

**Definition of "character with role":**
- Has a name (capitalized, not a generic "the guard")
- Appears in dialogue, description, or narrative
- Not meta/system text (not "Player", "Narrator", etc.)

**Measurement approach:**
1. Manual baseline: Author lists all expected characters
2. Extraction output: Count unique characters detected
3. Coverage = (detected / expected) * 100%

**Success criteria:**
- 90%+ coverage of author's expected character list
- All protagonist/major characters detected (100% of these)
- Most minor characters detected (80%+ of these)
- Experimental baseline: 15 characters detected (should maintain or exceed this)

**Failure modes to detect:**
- Character mentioned only in late passages of long paths (chunked approach fixes this)
- Character names embedded in complex sentences (prompt engineering issue)
- Character name variations (Javlyn vs Jav, need normalization in summarization)

**Implementation:**
- Document expected characters in test stories
- Add character coverage metric to extraction stats
- Include character list in extraction report
- Allow manual verification: "Did we miss any characters you expected?"

---

### REQ-5: Quality Metrics Beyond Count

**CEO Question 3:** How do we validate extraction quality beyond count?

**Answer:** Use multiple quality indicators to triangulate extraction health.

**Quality Metrics:**

1. **Character Coverage** (see REQ-4)
   - Percentage of expected characters detected
   - Character name variations normalized
   - Target: 90%+

2. **Fact Distribution Balance**
   - Facts should be spread across fact types (not 95% one type)
   - Expected distribution (approximate):
     - Character identity: 40-50%
     - Setting: 20-30%
     - World rules: 10-20%
     - Timeline: 10-20%
   - Target: No single type exceeds 70% of total facts

3. **Evidence Quality**
   - Percentage of facts with valid evidence citations
   - Evidence quotes match source passage
   - Target: 100% of facts have evidence field populated

4. **Extraction Success Rate**
   - Percentage of passages successfully extracted (no errors/timeouts)
   - Target: 95%+ success rate
   - Acceptable: 90%+ (some passages legitimately have no extractable facts)

5. **Deduplication Effectiveness**
   - Reduction in fact count after summarization
   - Raw facts → Deduplicated facts ratio
   - Expected: 30-50% reduction (experimental: 160 → 85 = 47% reduction)
   - Too high (>70%): Over-merging, losing distinctions
   - Too low (<20%): Under-merging, too much duplication

6. **Contradiction Detection**
   - Number of conflicts flagged during summarization
   - Presence indicates thorough extraction (found conflicting info)
   - Absence could mean missed facts OR consistent story
   - Manual review: Are flagged contradictions real issues?

**Reporting:**
```
EXTRACTION QUALITY REPORT
=========================
Character Coverage: 15/16 expected (93.8%) ✓
Fact Distribution:
  - Character identity: 46/160 (28.8%) ✓
  - Setting: 52/160 (32.5%) ✓
  - World rules: 38/160 (23.8%) ✓
  - Timeline: 24/160 (15.0%) ✓
  - Balance score: GOOD
Evidence Quality: 160/160 facts cited (100%) ✓
Extraction Success: 58/62 passages (93.5%) ✓
Deduplication: 160 → 85 facts (47% reduction) ✓
Contradictions Found: 2 flagged for review

Overall Quality: EXCELLENT
```

---

### REQ-6: Extraction Method Decision

**CEO Question 4:** Should old extraction method remain as fallback, or full replacement?

**Answer:** Full replacement. The chunked approach strictly dominates the path-based approach.

**Rationale:**

**Why NOT keep path-based as fallback:**
1. **No scenario where path-based is better:** Chunked approach always extracts more facts
2. **Maintenance burden:** Keeping two extraction pipelines means double testing, double maintenance
3. **Confusion:** Which approach is "canonical"? When to use which?
4. **Quality regression risk:** Fallback might mask extraction failures instead of surfacing them

**Migration approach:**
1. Replace current loader and extraction logic entirely
2. Existing cache structure supports both (passage-based is more granular)
3. Regenerate full cache using chunked approach (one-time migration)
4. Monitor extraction quality for first few runs
5. If issues arise, fix chunked approach (don't revert to path-based)

**Escape hatch (if needed):**
- If critical bug discovered after deployment, temporarily disable extraction (use cached data)
- Fix bug and re-run extraction
- Do NOT revert to path-based extraction (known to be inferior)

**Decision:** Full replacement, no fallback.

---

## Acceptance Criteria

### Core Functionality

- [ ] Extraction processes individual passages, not assembled paths
- [ ] Passages extracted independently (one AI call per passage)
- [ ] Large passages (>20k chars) split into chunks automatically
- [ ] Each passage extracted exactly once (deduplication works)
- [ ] Facts from chunked passages merged during summarization
- [ ] Extraction cache stores per-passage results (not per-path)

### Metadata & Reporting

- [ ] Extraction stats include total passages, facts per passage distribution
- [ ] Report shows high-yield passages (most facts extracted)
- [ ] Report shows passages with no facts (for investigation)
- [ ] Character coverage metric calculated and reported
- [ ] Fact distribution balance calculated and reported
- [ ] Evidence quality metric (% of facts with citations) reported
- [ ] Deduplication effectiveness metric calculated

### Quality Targets

- [ ] Character coverage: 90%+ of expected characters detected
- [ ] Extraction success rate: 95%+ passages extracted without errors
- [ ] Evidence quality: 100% of facts have evidence field populated
- [ ] Fact distribution: No single type exceeds 70% of total facts
- [ ] Deduplication: 30-50% reduction in fact count (indicates effective merging)

### Performance

- [ ] Extraction completes in reasonable time (< 5 minutes for 60 passages)
- [ ] Chunking overhead minimal (most passages don't need chunking)
- [ ] Cache reuse works (unchanged passages skip re-extraction)
- [ ] Failed passages don't block entire extraction (graceful degradation)

### Integration

- [ ] Works with existing webhook service (`/extract-story-bible`)
- [ ] Works with existing cache structure (`story-bible-cache.json`)
- [ ] Works with existing summarization pipeline
- [ ] Build process renders from chunked extraction results
- [ ] No breaking changes to published story-bible.html/json format

---

## Edge Cases

### Edge Case 1: Empty Passages
**Scenario:** Passage contains only system/meta text, no extractable content

**Behavior:**
- AI returns `{"facts": []}` (empty fact list)
- Passage recorded in stats as "no facts extracted"
- Cache stores empty result (prevents re-extraction)
- Not counted as extraction failure (legitimate empty result)

---

### Edge Case 2: Very Large Single Passage
**Scenario:** Passage is 50k+ characters (exceeds chunk limit)

**Behavior:**
- Split into chunks at 20k character boundaries
- Each chunk extracted independently
- Facts tagged with chunk number (for debugging)
- Summarization merges facts from same passage
- Evidence citations reference original passage (not chunk)

---

### Edge Case 3: Passage Appears in Many Paths
**Scenario:** Common passage appears in 20+ different paths

**Behavior:**
- Extracted exactly once (first time encountered)
- Cache lookup prevents re-extraction for remaining paths
- `appears_in_paths` field lists all 20+ paths
- Facts cite passage, not specific path (passage is source of truth)
- Summarization doesn't over-weight facts from common passages

---

### Edge Case 4: Passage Modified Between Extraction Runs
**Scenario:** Author edits passage after initial extraction

**Behavior:**
- Content hash changes (MD5 of passage text)
- Cache lookup fails (hash mismatch)
- Passage re-extracted with new content
- Old facts discarded, new facts stored
- Summarization uses latest extraction only

---

### Edge Case 5: Chunk Boundary Splits Sentence
**Scenario:** 20k character limit falls mid-sentence

**Behavior:**
- Chunking attempts to split at paragraph boundaries first
- If no paragraph boundary near limit, split at sentence boundary
- If no sentence boundary, split at word boundary
- Last resort: split at character limit (rare)
- Overlapping context: last 200 chars of chunk N included in chunk N+1 prompt
- AI prompt instructs: "This is a partial passage, extract facts from visible text"

---

### Edge Case 6: Character Name Appears in Different Forms
**Scenario:** Character referred to as "Javlyn", "Jav", "the student"

**Behavior:**
- Per-passage extraction captures all variations as separate character_identity facts
- Summarization step normalizes character names (AI task)
- If uncertain whether "Jav" = "Javlyn", keep separate (conservative)
- Evidence preserved for all variations
- Author can manually verify during review

---

### Edge Case 7: Zero Facts Extracted Across All Passages
**Scenario:** Extraction runs but extracts zero facts from entire story

**Behavior:**
- Check if Ollama is responding (health check)
- Check if passages are loading (loader debug)
- Check extraction prompt (possibly malformed)
- Flag as critical failure (don't commit empty cache)
- Alert: "Extraction produced zero facts, investigation needed"
- Do NOT overwrite existing cache with empty result

---

### Edge Case 8: Fact Cited in Multiple Chunks of Same Passage
**Scenario:** Large passage split into chunks, both mention "magic system exists"

**Behavior:**
- Each chunk extracts the fact independently
- Both facts tagged with same passage name, different chunk numbers
- Summarization treats as duplicates (same passage source)
- Merged into single fact with evidence from both chunks
- No over-counting (two mentions in same passage = one fact)

---

## Quality Criteria for Success

**This feature will be considered successful when:**

1. **Character coverage:** 90%+ of expected characters detected in test stories
2. **Fact coverage:** 3x improvement over path-based approach maintained (current: 19 → 116)
3. **Extraction reliability:** 95%+ success rate, <5% passage failures
4. **Quality metrics:** All quality indicators (distribution, evidence, deduplication) in target ranges
5. **Performance:** Extraction completes in <5 minutes for 60-passage story
6. **No regressions:** Build and webhook integration work without breaking existing features
7. **Author validation:** Authors report Story Bible captures characters/facts they expect

---

## Answers to CEO Questions

### Q1: What character coverage threshold defines success?

**Answer:** 90%+ coverage of named characters with roles.

**Measurement:**
- Manual baseline: Author lists expected characters
- Extraction output: Count unique characters detected
- Coverage = (detected / expected) * 100%
- Experimental baseline: 15 characters detected (maintain or exceed)

**Implementation:** See REQ-4

---

### Q2: Should per-passage fact count be a quality metric?

**Answer:** Yes, it's a valuable diagnostic metric but not a standalone quality indicator.

**Why track it:**
- Helps identify high-yield passages (rich world-building)
- Helps identify extraction failures (0 facts from content-rich passage)
- Helps validate extraction is working (distribution matches content)

**Why not rely on it alone:**
- Raw count doesn't indicate quality (10 low-quality facts < 3 high-quality facts)
- Different passages have different information density (expected variation)
- Should be combined with other metrics (distribution, evidence quality, coverage)

**Implementation:** See REQ-3

---

### Q3: How do we validate extraction quality beyond count?

**Answer:** Use multiple quality indicators to triangulate extraction health.

**Quality Metrics:**
1. Character coverage (90%+ target)
2. Fact distribution balance (no type exceeds 70%)
3. Evidence quality (100% of facts cited)
4. Extraction success rate (95%+ passages)
5. Deduplication effectiveness (30-50% reduction)
6. Contradiction detection (manual review of flagged conflicts)

**Implementation:** See REQ-5

---

### Q4: Should old extraction method remain as fallback, or full replacement?

**Answer:** Full replacement. No fallback.

**Rationale:**
- Chunked approach strictly dominates path-based (always better)
- Maintaining two pipelines is unnecessary complexity
- If issues arise, fix chunked approach (don't revert to inferior method)

**Migration:**
- Replace loader and extraction logic entirely
- Regenerate cache using chunked approach
- Monitor quality metrics for first few runs
- Escape hatch: disable extraction temporarily if critical bug (don't revert to path-based)

**Implementation:** See REQ-6

---

## Technical Context for Architect

### Current Architecture

**Path-based extraction (current):**
```
dist/allpaths-metadata/path-*.txt
  ↓
Loader: Load full paths (concatenated passages)
  ↓
Extractor: Extract facts from each path
  ↓
Cache: Store per-path extractions
  ↓
Summarization: Deduplicate facts across paths
```

**Issues:**
- Long paths exceed context window
- Facts from late passages in path get missed
- Redundant extraction: same passage extracted multiple times (once per path)

---

### Proposed Architecture

**Passage-based extraction (new):**
```
dist/allpaths-metadata/path-*.txt
  ↓
Loader: Deduplicate to get unique passages (existing logic)
  ↓
Chunker: Split large passages into <20k char chunks (NEW)
  ↓
Extractor: Extract facts from each passage/chunk
  ↓
Cache: Store per-passage extractions
  ↓
Summarization: Deduplicate facts, merge chunks of same passage
```

**Advantages:**
- Each extraction within context window limits
- No redundant extraction (each passage once)
- Better fact coverage (3x experimental improvement)
- Natural alignment with passage-level caching

---

### Existing Code to Leverage

**Deduplication logic:** `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/loader.py` (lines 176-185)
- Already deduplicates passages across paths
- Already tracks `appears_in_paths` for each passage
- Can be reused directly for passage collection

**Experimental chunking:** `/home/ubuntu/Code/NaNoWriMo2025/scripts/experiment-chunked-extraction.py` (lines 118-144)
- Proven chunking algorithm
- Splits at 20k char boundaries
- Handles chunk metadata

**Experimental deduplication:** `/home/ubuntu/Code/NaNoWriMo2025/scripts/experiment-dedup-facts.py`
- AI-based fact merging
- Character profile building
- Evidence preservation

**Current extraction:** `/home/ubuntu/Code/NaNoWriMo2025/services/lib/story_bible_extractor.py`
- Ollama integration
- Prompt templates
- Error handling
- Cache management

---

### Changes Required

**1. Modify Loader** (`formats/story-bible/modules/loader.py`):
- Change: Return unique passages instead of paths
- Keep: Existing passage deduplication logic
- Keep: `appears_in_paths` tracking

**2. Add Chunker** (new module or inline in extractor):
- Function: `chunk_passage(text, max_chars=20000) -> List[str]`
- Split at paragraph boundaries if possible
- Tag chunks with passage name and chunk number

**3. Modify Extractor** (`services/lib/story_bible_extractor.py`):
- Change: Iterate over passages (not paths)
- Add: Chunk large passages before extraction
- Change: Cache key is passage_id (not path_id)
- Keep: Ollama API calls, error handling, prompt template

**4. Modify Summarizer** (existing):
- Add: Merge facts from chunks of same passage
- Keep: Existing deduplication logic
- Keep: Evidence preservation

**5. Update Stats** (extraction report):
- Add: Per-passage fact count distribution
- Add: Character coverage metric
- Add: Quality metrics (distribution, evidence, success rate)

---

### Data Structure Changes

**Cache structure (no breaking changes):**
```json
{
  "passage_extractions": {
    "passage_id_1": {
      "passage_name": "Start",
      "content_hash": "md5_hash",
      "extracted_at": "timestamp",
      "facts": [...],
      "chunks_processed": 1
    }
  },
  "summarized_facts": { ... },
  "summarization_status": "success",
  "extraction_stats": {
    "total_passages": 62,
    "passages_with_facts": 58,
    "average_facts_per_passage": 2.6,
    "character_coverage": 0.938,
    "fact_distribution": {
      "character_identity": 46,
      "setting": 52,
      "world_rule": 38,
      "timeline": 24
    }
  }
}
```

**Changes from current:**
- `passage_extractions` keyed by passage_id (not path_id) ← BREAKING but cache regenerated anyway
- Added `chunks_processed` field (1 for most passages, >1 for large passages)
- Added `extraction_stats` section with quality metrics
- No change to `summarized_facts` structure (downstream consumers unaffected)

---

## Open Questions for Architect

1. **Chunking strategy:** Inline in extractor or separate module?
   - Recommendation: Inline function (not worth separate module for ~30 LOC)

2. **Chunk overlap:** Should chunks overlap to preserve context?
   - Recommendation: Yes, 200 character overlap (last 200 chars of chunk N in chunk N+1 prompt)

3. **Cache migration:** Regenerate or migrate existing cache?
   - Recommendation: Regenerate (structure change, full extraction warranted)

4. **Error handling:** If 50% of passages fail, abort or continue?
   - Recommendation: Abort if >50% fail (something fundamentally broken)

5. **Performance:** Parallel extraction or sequential?
   - Recommendation: Sequential for Phase 1 (simpler), parallel in Phase 2 if needed

---

## Success Metrics

**Immediate (Phase 1):**
- [ ] Character coverage: 90%+ of expected characters
- [ ] Fact coverage: Maintain 3x improvement from experiments (19 → 116 facts)
- [ ] Extraction success: 95%+ passages extracted without errors
- [ ] Quality metrics: All in target ranges (distribution, evidence, deduplication)
- [ ] Performance: <5 minutes for 60-passage story

**Long-term (Phase 2+):**
- [ ] Authors report Story Bible accurately reflects their story world
- [ ] New collaborators use Story Bible for onboarding successfully
- [ ] AI Continuity Checking uses Story Bible for validation (future integration)
- [ ] No complaints about missing characters or facts

---

## Risks & Mitigations

### Risk 1: Chunking Overhead Slows Extraction
**Impact:** Medium - Longer extraction times for large stories

**Mitigation:**
- Most passages don't need chunking (optimization for rare large passages)
- Chunk only when passage >20k chars (threshold can be adjusted)
- Cache prevents re-chunking on subsequent runs
- Parallel extraction in Phase 2 if needed

---

### Risk 2: Character Coverage Metric Hard to Validate
**Impact:** Low - Difficult to measure success objectively

**Mitigation:**
- Start with manual baseline (author lists expected characters)
- Automate detection of capitalized names in source (heuristic baseline)
- Compare extraction output to heuristic (catch major misses)
- Allow manual verification: "Did we miss anyone?"

---

### Risk 3: Quality Metrics Give False Confidence
**Impact:** Medium - Metrics say "good" but extraction is actually poor

**Mitigation:**
- Use multiple metrics (triangulate quality)
- Manual review of sample extractions (spot check)
- Author validation: "Does this match your story?"
- Track metric trends over time (sudden changes indicate issues)

---

### Risk 4: Cache Regeneration Takes Long Time
**Impact:** Low - One-time migration pain

**Mitigation:**
- Regeneration is one-time (not ongoing cost)
- Can be done async (doesn't block development)
- Incremental cache rebuild (process new passages first)
- Parallel extraction in future if needed

---

## Next Steps

**For Architect:**
1. Review this requirements document
2. Design technical implementation approach
3. Identify any technical risks or constraints
4. Propose module structure and interfaces
5. Document in `architecture/story-bible-chunked-extraction.md`

**For Developer (after Architect design):**
1. Implement chunking logic (inline or module)
2. Modify loader to collect unique passages
3. Modify extractor to process passages (not paths)
4. Add quality metrics to extraction stats
5. Test with current story content
6. Regenerate cache using chunked approach
7. Validate quality metrics in target ranges

---

## Related Documents

- **CEO Approval:** (Context provided in this conversation)
- **Feature PRD:** `/home/ubuntu/Code/NaNoWriMo2025/features/story-bible.md`
- **Experimental Scripts:**
  - `/home/ubuntu/Code/NaNoWriMo2025/scripts/experiment-chunked-extraction.py`
  - `/home/ubuntu/Code/NaNoWriMo2025/scripts/experiment-dedup-facts.py`
- **Current Implementation:**
  - `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/loader.py`
  - `/home/ubuntu/Code/NaNoWriMo2025/services/lib/story_bible_extractor.py`
  - `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/ai_extractor.py`

---

**End of Requirements Document**
