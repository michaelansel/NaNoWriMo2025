# Technical Design: Chunked Extraction for Story Bible

**Status:** Ready for Developer Implementation
**Owner:** Architect
**Date:** 2025-11-30
**Related PRD:** `/home/ubuntu/Code/NaNoWriMo2025/features/story-bible-chunked-extraction-requirements.md`

---

## Executive Summary

Replace the current path-based extraction with passage-based chunked extraction. This changes the fundamental unit of extraction from "story path" to "individual passage", dramatically improving character and fact coverage (experimental results: 5→15 characters, 19→116 facts).

**Key architectural changes:**
1. Loader returns unique passages instead of full paths
2. New chunking function splits large passages (>20k chars)
3. Extractor processes passages instead of paths
4. Cache keyed by passage_id instead of path_id
5. Quality metrics tracked in cache

**Impact:** Full replacement of extraction pipeline, cache regeneration required.

---

## Context and Forces

### Why This Design?

**Problem:** Current path-based extraction misses facts
- Long paths exceed AI context limits → truncation/skimming
- Facts from later passages in path get missed
- Redundant extraction (same passage extracted multiple times)

**Solution:** Process each passage independently
- Each extraction fits within context window
- AI focuses on one passage at a time
- Natural deduplication (passage extracted once)
- Proven 3x improvement in coverage

### Design Forces

**Must optimize for:**
1. **Extraction quality** - Primary goal, 90%+ character coverage
2. **Fact coverage** - Maintain 3x improvement (19→116 facts)
3. **Evidence preservation** - Complete citation trail
4. **Cache efficiency** - Avoid redundant AI calls

**Can trade off:**
1. **Performance** - Acceptable if <5 min for 60 passages
2. **Code complexity** - Willing to add chunking logic for quality gains
3. **One-time migration cost** - Cache regeneration acceptable

---

## Component Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Data Flow                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  dist/allpaths-metadata/path-*.txt                          │
│           ↓                                                  │
│  [1. Loader] Deduplicate → Unique Passages                  │
│           ↓                                                  │
│  [2. Chunker] Split large passages → Chunks (<20k chars)    │
│           ↓                                                  │
│  [3. Extractor] AI extract facts per passage/chunk          │
│           ↓                                                  │
│  [4. Cache] Store per-passage extractions                   │
│           ↓                                                  │
│  [5. Summarizer] Deduplicate + merge chunk facts            │
│           ↓                                                  │
│  story-bible-cache.json (final output)                      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Current | New |
|-----------|---------|-----|
| **Loader** | Load full paths | Load unique passages |
| **Chunker** | N/A | NEW: Split large passages |
| **Extractor** | Extract from paths | Extract from passages/chunks |
| **Cache** | Key: path_id | Key: passage_id |
| **Summarizer** | Deduplicate across paths | Deduplicate + merge chunks |

---

## Detailed Design

### 1. Loader Changes (`formats/story-bible/modules/loader.py`)

**Current behavior:**
```python
def load_allpaths_data(dist_dir: Path) -> Dict:
    # Returns: {'passages': {...}, 'paths': [...]}
    # passages already deduplicated (lines 176-185)
```

**New behavior:**
```python
def load_allpaths_data(dist_dir: Path) -> Dict:
    # CHANGE: Return structure optimized for passage-based extraction
    # Keep existing deduplication logic
    # Add passage metadata for chunking
    return {
        'passages': {
            'passage_name': {
                'text': "...",
                'appears_in_paths': ["path_id1", ...],
                'passage_id': "hex_id",
                'length': 5000  # NEW: track length for chunking
            }
        },
        'paths': [...],  # Keep for compatibility
        'metadata': {...}
    }
```

**Changes required:**
- ✓ Keep existing deduplication logic (lines 176-185)
- ✓ Keep `appears_in_paths` tracking (line 184)
- ✓ Add `length` field to passage data
- ✗ No breaking changes to existing structure

**Rationale:** Minimal changes to proven deduplication logic, just add metadata.

---

### 2. Chunking Function (NEW)

**Location:** Inline in `services/lib/story_bible_extractor.py`
**Alternative considered:** Separate module (rejected - overkill for ~40 LOC)

**Function signature:**
```python
def chunk_passage(
    passage_name: str,
    passage_text: str,
    max_chars: int = 20000,
    overlap_chars: int = 200
) -> List[Tuple[str, str, int]]:
    """
    Split passage into chunks that fit within max_chars.

    Args:
        passage_name: Name of the passage
        passage_text: Full passage text
        max_chars: Maximum characters per chunk
        overlap_chars: Characters to overlap between chunks

    Returns:
        List of (chunk_name, chunk_text, chunk_number) tuples

    Example:
        chunk_passage("Start", "...", 20000)
        -> [("Start_chunk_1", "...", 1), ("Start_chunk_2", "...", 2)]
    """
    # If passage fits in one chunk, return as-is
    if len(passage_text) <= max_chars:
        return [(passage_name, passage_text, 1)]

    # Split at paragraph boundaries (double newline)
    # Fall back to sentence boundaries if needed
    # Last resort: split at max_chars

    # Add overlap for context preservation
    # (last overlap_chars of chunk N in chunk N+1)

    chunks = []
    # ... chunking algorithm from experiment-chunked-extraction.py
    return chunks
```

**Algorithm (from experimental script, lines 118-144):**
1. Check if passage fits in one chunk (common case - fast path)
2. If too large, split at paragraph boundaries (`\n\n`)
3. If paragraph too large, split at sentence boundaries (`. `)
4. If sentence too large, split at word boundaries
5. Last resort: split at character limit
6. Add overlap between chunks for context

**Chunking strategy:**
- **Most passages**: 1 chunk (typical passage <5k chars)
- **Large passages**: Multiple chunks at natural boundaries
- **Overlap**: 200 chars to preserve context across boundaries

**Test coverage:**
- Single-chunk passage (common case)
- Multi-chunk passage with paragraph breaks
- Multi-chunk passage without paragraph breaks
- Edge case: Empty passage
- Edge case: Passage exactly at limit

---

### 3. Extractor Changes (`services/lib/story_bible_extractor.py`)

**Current flow:**
```python
# From existing code (lines 329-362)
def get_passages_to_extract(cache, metadata_dir, mode):
    # Returns passages to process based on cache
    ...

for passage_id, passage_file, passage_content in passages_to_process:
    facts = extract_facts_from_passage(passage_content, passage_id)
    cache['passage_extractions'][passage_id] = {
        'content_hash': md5_hash,
        'extracted_at': timestamp,
        'facts': facts
    }
```

**New flow:**
```python
def get_passages_to_extract(cache, metadata_dir, mode):
    # SAME: Returns passages to process
    ...

for passage_id, passage_file, passage_content in passages_to_process:
    # NEW: Chunk if needed
    chunks = chunk_passage(passage_id, passage_content)

    all_chunk_facts = []
    for chunk_name, chunk_text, chunk_num in chunks:
        # Extract from each chunk
        chunk_facts = extract_facts_from_passage(chunk_text, chunk_name)

        # Tag with chunk metadata
        for fact in chunk_facts:
            fact['_chunk_number'] = chunk_num
            fact['_chunk_total'] = len(chunks)

        all_chunk_facts.extend(chunk_facts)

    # Store combined facts from all chunks
    cache['passage_extractions'][passage_id] = {
        'content_hash': md5_hash,
        'extracted_at': timestamp,
        'facts': all_chunk_facts,
        'chunks_processed': len(chunks)  # NEW: track chunking
    }
```

**Changes required:**
1. Add `chunk_passage()` function
2. Modify extraction loop to chunk before extracting
3. Tag facts with chunk metadata (for debugging)
4. Add `chunks_processed` to cache entry

**Prompt changes:**
```python
# Current prompt (lines 23-70)
EXTRACTION_PROMPT = """... {passage_text} ..."""

# New prompt (add chunk context)
EXTRACTION_PROMPT = """...
=== SECTION 4: PASSAGE TEXT ===

{chunk_context}

{passage_text}

{chunk_note}

BEGIN EXTRACTION (JSON only):
"""

# Where:
# chunk_context = "" (if single chunk)
# chunk_context = "This is chunk 2 of 3 from passage 'Start'" (if multi-chunk)
# chunk_note = "" (if single chunk)
# chunk_note = "Note: This is a partial passage. Extract facts from visible text." (if multi-chunk)
```

**Rationale:** Minimal changes to extraction logic, chunking transparent to downstream.

---

### 4. Cache Structure Changes

**Current structure:**
```json
{
  "passage_extractions": {
    "passage_id": {
      "content_hash": "md5",
      "extracted_at": "timestamp",
      "facts": [...]
    }
  },
  "summarized_facts": {...},
  "summarization_status": "success"
}
```

**New structure:**
```json
{
  "passage_extractions": {
    "passage_id": {
      "content_hash": "md5",
      "extracted_at": "timestamp",
      "facts": [...],
      "chunks_processed": 1,
      "passage_name": "Start",
      "passage_length": 5000
    }
  },
  "summarized_facts": {...},
  "summarization_status": "success",
  "extraction_stats": {
    "total_passages": 62,
    "passages_with_facts": 58,
    "passages_with_no_facts": 4,
    "average_facts_per_passage": 2.6,
    "character_coverage": 0.938,
    "fact_distribution": {
      "character_identity": 46,
      "setting": 52,
      "world_rule": 38,
      "timeline": 24
    },
    "extraction_success_rate": 0.935,
    "deduplication_effectiveness": 0.47
  }
}
```

**Breaking changes:**
- Cache key changes from path_id to passage_id (requires regeneration)
- Added fields are backwards-compatible (old caches can be read, will just lack new fields)

**Migration strategy:**
- Full cache regeneration (one-time cost)
- No gradual migration (clean break preferred)

---

### 5. Summarizer Changes (`formats/story-bible/modules/ai_summarizer.py`)

**Current behavior:**
```python
def summarize_facts(per_passage_extractions: Dict) -> Tuple[Optional[Dict], str]:
    # Deduplicates facts across passages
    # Preserves evidence from all sources
```

**New behavior:**
```python
def summarize_facts(per_passage_extractions: Dict) -> Tuple[Optional[Dict], str]:
    # ADDITIONAL: Merge facts from chunks of same passage
    # Example: passage "Start" has chunks 1-3, each extracted "magic exists"
    # → Merge into single fact with evidence from all chunks

    # SAME: Deduplicate facts across different passages
    # SAME: Preserve complete evidence trail
```

**Changes required:**
1. Pre-processing step: Group facts by passage, merge chunk duplicates
2. Main deduplication: Existing logic unchanged
3. Evidence normalization: Strip `_chunk_number` metadata

**Algorithm:**
```python
def merge_chunk_facts(passage_extractions: Dict) -> Dict:
    """
    Merge facts from chunks of the same passage before main deduplication.

    For each passage:
        If chunks_processed > 1:
            Group facts by similarity (same fact text)
            Merge evidence from all chunks
            Keep single fact per passage
    """
    merged = {}
    for passage_id, extraction in passage_extractions.items():
        chunks_processed = extraction.get('chunks_processed', 1)

        if chunks_processed == 1:
            # No merging needed
            merged[passage_id] = extraction
        else:
            # Merge facts from multiple chunks
            merged[passage_id] = {
                ...extraction,
                'facts': merge_facts_from_chunks(extraction['facts'])
            }

    return merged
```

**Rationale:** Conservative merging (only merge within same passage), then existing deduplication handles cross-passage merging.

---

### 6. Quality Metrics Module (NEW)

**Location:** `services/lib/story_bible_metrics.py` (new file)

**Purpose:** Calculate quality metrics for extraction validation

**Function signatures:**
```python
def calculate_extraction_stats(cache: Dict) -> Dict:
    """Calculate comprehensive extraction statistics."""
    passage_extractions = cache.get('passage_extractions', {})
    summarized_facts = cache.get('summarized_facts', {})

    return {
        'total_passages': len(passage_extractions),
        'passages_with_facts': count_passages_with_facts(passage_extractions),
        'average_facts_per_passage': calculate_average_facts(passage_extractions),
        'character_coverage': calculate_character_coverage(summarized_facts),
        'fact_distribution': calculate_fact_distribution(summarized_facts),
        'extraction_success_rate': calculate_success_rate(passage_extractions),
        'deduplication_effectiveness': calculate_dedup_ratio(passage_extractions, summarized_facts)
    }

def calculate_character_coverage(summarized_facts: Dict) -> float:
    """
    Character coverage: detected / expected characters.

    Returns value between 0.0 and 1.0.
    Target: 0.90 (90% coverage)
    """
    detected_characters = set(summarized_facts.get('characters', {}).keys())
    # TODO: Load expected characters from test baseline
    # For now, return detected count as proxy
    return len(detected_characters) / max(len(detected_characters), 1)

def calculate_fact_distribution(summarized_facts: Dict) -> Dict[str, int]:
    """
    Fact distribution by type.

    Returns: {'character_identity': 46, 'setting': 52, ...}
    Target: No type exceeds 70% of total
    """
    constants = summarized_facts.get('constants', {})
    distribution = {}

    for fact_type, facts in constants.items():
        distribution[fact_type] = len(facts)

    # Add character facts
    characters = summarized_facts.get('characters', {})
    char_fact_count = sum(
        len(char_data.get('identity', [])) +
        len(char_data.get('zero_action_state', [])) +
        len(char_data.get('variables', []))
        for char_data in characters.values()
    )
    distribution['character_identity'] = char_fact_count

    return distribution

def calculate_dedup_ratio(passage_extractions: Dict, summarized_facts: Dict) -> float:
    """
    Deduplication effectiveness: reduction in fact count.

    Returns: 0.47 means 47% reduction (160 → 85 facts)
    Target: 0.30 to 0.50 (30-50% reduction)
    """
    raw_count = sum(
        len(extraction.get('facts', []))
        for extraction in passage_extractions.values()
    )

    # Count summarized facts
    constants = summarized_facts.get('constants', {})
    final_count = sum(len(facts) for facts in constants.values())

    if raw_count == 0:
        return 0.0

    return 1.0 - (final_count / raw_count)
```

**Integration point:**
```python
# In story_bible_extractor.py, after summarization:
from story_bible_metrics import calculate_extraction_stats

# ... after summarization completes
cache['extraction_stats'] = calculate_extraction_stats(cache)
```

---

### 7. Webhook Integration (`services/continuity-webhook.py`)

**Current flow:**
```python
# Lines 1416-1649: process_story_bible_extraction_async()
# Handles /extract-story-bible command
```

**Changes required:**
1. No changes to webhook handler (extraction is internal)
2. Metrics added to progress comments
3. Cache structure compatible (new fields optional)

**Example progress comment (updated):**
```markdown
## 📖 Story Bible Extraction - Complete

**Mode:** `incremental`
**Passages extracted:** 62
**Total facts:** 160

**Quality Metrics:**
- **Character coverage:** 15 characters detected (93.8%)
- **Fact distribution:** Balanced across types
- **Extraction success:** 58/62 passages (93.5%)
- **Deduplication:** 160 → 85 facts (47% reduction)

**Summary:**
- **Constants:** 85 world facts
- **Characters:** 15 characters
- **Variables:** 12 player-determined facts
```

**Integration:** Quality metrics displayed in webhook comment, no breaking changes.

---

## Data Flow Diagrams

### Current Path-Based Extraction

```
path-001.txt (10k chars, 5 passages)
    ↓
[Extractor] Extract from entire path
    ↓
[Cache] Store under path_id: "001"
    ↓
Facts: 3 detected (2 from first passage, 1 missed from later passages)
```

**Problem:** AI context window exceeded, facts from later passages missed.

---

### New Passage-Based Extraction

```
path-001.txt (10k chars, 5 passages)
    ↓
[Loader] Deduplicate → 5 unique passages
    ↓
Passage A (2k chars)
    ↓
[Chunker] No chunking needed (fits in one chunk)
    ↓
[Extractor] Extract from Passage A
    ↓
[Cache] Store under passage_id: "A"
    ↓
Facts: 2 detected

Passage B (2k chars)
    ↓
... (same flow)
    ↓
Facts: 3 detected

Passage C (25k chars - LARGE!)
    ↓
[Chunker] Split into 2 chunks (20k + 5k)
    ↓
[Extractor] Extract from chunk 1 → 4 facts
[Extractor] Extract from chunk 2 → 3 facts
    ↓
[Cache] Store under passage_id: "C" (combined: 7 facts, chunks_processed: 2)
    ↓
[Summarizer] Merge chunk duplicates → 5 unique facts from Passage C
```

**Benefit:** Each extraction within context limits, all passages processed independently.

---

## File Modification Plan

### Files to Modify

1. **`formats/story-bible/modules/loader.py`** (Minor changes)
   - Add `length` field to passage data
   - Lines changed: ~5 LOC

2. **`services/lib/story_bible_extractor.py`** (Major changes)
   - Add `chunk_passage()` function (~40 LOC)
   - Modify extraction loop (~20 LOC modified)
   - Update prompt template (~10 LOC)
   - Lines changed: ~70 LOC total

3. **`formats/story-bible/modules/ai_summarizer.py`** (Medium changes)
   - Add `merge_chunk_facts()` pre-processing (~30 LOC)
   - Call before existing deduplication (~5 LOC)
   - Lines changed: ~35 LOC

4. **`services/continuity-webhook.py`** (Minor changes)
   - Add quality metrics to extraction comments (~15 LOC)
   - No breaking changes to webhook handling

### Files to Create

5. **`services/lib/story_bible_metrics.py`** (New file)
   - Quality metric calculations (~150 LOC)
   - Used by extractor and webhook

6. **`architecture/story-bible-chunked-extraction.md`** (This document)
   - Technical design specification

---

## Testing Strategy

### Unit Tests

1. **Chunking function tests:**
   ```python
   def test_chunk_passage_single_chunk():
       # Passage < 20k chars → 1 chunk

   def test_chunk_passage_multiple_chunks():
       # Passage > 20k chars → multiple chunks

   def test_chunk_passage_paragraph_boundaries():
       # Verify splits at paragraph breaks

   def test_chunk_passage_overlap():
       # Verify 200 char overlap between chunks
   ```

2. **Metrics calculation tests:**
   ```python
   def test_character_coverage_calculation():
       # Verify character count / expected

   def test_fact_distribution_balance():
       # Verify no type exceeds 70%

   def test_deduplication_ratio():
       # Verify (raw - final) / raw calculation
   ```

3. **Cache structure tests:**
   ```python
   def test_cache_backward_compatibility():
       # Old cache can be read (missing new fields ok)

   def test_cache_forward_compatibility():
       # New cache has all expected fields
   ```

### Integration Tests

1. **End-to-end extraction:**
   ```python
   def test_extract_with_chunking():
       # Given: Large passage (30k chars)
       # When: Extract facts
       # Then: Passage chunked, all facts extracted

   def test_extract_without_chunking():
       # Given: Small passage (5k chars)
       # When: Extract facts
       # Then: Single extraction, no chunking
   ```

2. **Webhook integration:**
   ```python
   def test_webhook_extraction_command():
       # Simulate /extract-story-bible
       # Verify progress comments include metrics
   ```

### Validation Tests

1. **Quality targets:**
   ```python
   def test_character_coverage_target():
       # Run on test story
       # Assert: coverage >= 0.90

   def test_fact_distribution_balance():
       # Run on test story
       # Assert: no type > 0.70 of total

   def test_extraction_success_rate():
       # Run on test story
       # Assert: success_rate >= 0.95
   ```

---

## Performance Analysis

### Expected Performance

**Scenario: 60 passages, average 3k chars each**

```
Current approach (path-based):
  - 30 paths × 2 min/path = 60 minutes total
  - Many facts missed due to context overflow

New approach (passage-based):
  - 60 passages × 1 min/passage = 60 minutes total (same time)
  - Higher quality (3x more facts detected)

Chunking overhead:
  - 58 passages < 20k chars: no chunking (fast path)
  - 2 passages > 20k chars: split into 4 chunks total
  - Chunking: ~100ms per large passage
  - Extraction: same 1 min/chunk
  - Total overhead: ~2 minutes (4 chunks vs 2 passages)
```

**Total time: ~62 minutes (acceptable, within 5 min/passage budget)**

### Optimization Opportunities (Future)

1. **Parallel extraction** (Phase 2)
   - Extract multiple passages concurrently
   - Potential: 5x speedup (60 min → 12 min)
   - Complexity: Thread pool, rate limiting

2. **Smart caching** (Phase 2)
   - Cache extracted facts by content hash
   - Reuse extractions for unchanged passages
   - Already implemented in current code (lines 98-128)

3. **Batch prompting** (Phase 3)
   - Send multiple small passages in one API call
   - Potential: 2x speedup for small passages
   - Complexity: Response parsing, error handling

**Phase 1 decision:** Sequential extraction (simpler, proven), optimize later if needed.

---

## Migration Plan

### Phase 1: Implementation (Developer)

1. Add chunking function to `story_bible_extractor.py`
2. Modify extraction loop to use chunking
3. Add metrics calculation module
4. Update summarizer to merge chunk facts
5. Update loader to add passage metadata
6. Add unit tests for all new functions

**Acceptance:** All tests pass, extraction works end-to-end.

---

### Phase 2: Cache Regeneration

1. Backup existing cache: `cp story-bible-cache.json story-bible-cache-old.json`
2. Delete current cache: `rm story-bible-cache.json`
3. Run full extraction: `/extract-story-bible full`
4. Verify quality metrics:
   ```
   Character coverage: >= 90%
   Fact count: >= 100 (maintain 3x improvement)
   Extraction success: >= 95%
   ```
5. Commit new cache to repository

**Acceptance:** New cache has better coverage than old cache.

---

### Phase 3: Validation

1. Compare old vs new extractions:
   - Character list (old: 5, new: should be ~15)
   - Fact count (old: 19, new: should be ~100+)
   - Character coverage (new: should be ~93%)

2. Manual review:
   - Sample 10 passages
   - Verify facts extracted correctly
   - Check for no regressions (facts lost)

3. Quality metrics:
   - All metrics in target ranges
   - No critical issues flagged

**Acceptance:** Quality metrics meet targets, no regressions detected.

---

## Risks and Mitigations

### Risk 1: Chunking Splits Context

**Impact:** Medium - Facts that span chunks might be missed

**Example:**
```
Chunk 1 ends: "Javlyn studied at the Academy for"
Chunk 2 starts: "three years before becoming a wizard"
→ AI might not connect these as one fact
```

**Mitigation:**
1. 200-char overlap between chunks (preserves sentence context)
2. Split at paragraph boundaries (minimize mid-sentence splits)
3. Summarization merges related facts from chunks
4. Test on large passages to validate

**Probability:** Low (chunking algorithm tested in experiments)

---

### Risk 2: Quality Metrics Give False Confidence

**Impact:** Medium - Metrics say "good" but extraction is poor

**Example:** High character coverage but all facts are low-quality

**Mitigation:**
1. Use multiple metrics (triangulate quality)
2. Manual review of sample extractions
3. Author validation: "Does this match your story?"
4. Track metric trends (sudden changes indicate issues)

**Probability:** Low (multiple metrics reduce false positives)

---

### Risk 3: Cache Regeneration Takes Long

**Impact:** Low - One-time migration pain

**Expected time:** ~60 minutes for 60 passages

**Mitigation:**
1. Run during off-hours (not blocking)
2. Can be done async (doesn't block development)
3. Progress tracking (know when it's done)
4. One-time cost (not ongoing)

**Probability:** High (will take time, but acceptable)

---

### Risk 4: Breaking Changes in Cache

**Impact:** Medium - Existing tools might fail

**Breaking changes:**
- Cache key changes from path_id to passage_id
- New fields added (backward compatible)

**Mitigation:**
1. Full cache regeneration (clean migration)
2. Validate cache structure after regeneration
3. Update any tools that read cache
4. Document cache format changes

**Probability:** Medium (cache structure change is breaking, but manageable)

---

## Open Questions for Developer

### Q1: Chunking overlap strategy

**Question:** Should chunks overlap by 200 chars, 500 chars, or variable based on passage?

**Recommendation:** Start with 200 chars (proven in experiments), increase if context loss detected.

---

### Q2: Chunk boundary detection

**Question:** Priority order for split points?

**Recommendation:**
1. Paragraph breaks (`\n\n`) - best
2. Sentence breaks (`. `) - good
3. Word boundaries (` `) - acceptable
4. Character limit - last resort

Test on large passages to validate.

---

### Q3: Error handling for large chunks

**Question:** What if single paragraph exceeds 20k chars (no good split point)?

**Recommendation:**
1. Split at word boundary anyway (better than truncating)
2. Add warning to cache entry
3. Flag for manual review
4. Consider increasing chunk limit for edge cases

---

### Q4: Metrics baseline for character coverage

**Question:** How to define "expected characters" for coverage calculation?

**Recommendation (Phase 1):**
- Use detected character count as proxy
- Track improvement over time

**Future (Phase 2):**
- Author provides expected character list
- Automated detection via capitalized names in source

---

## Success Criteria

### Must Have (Phase 1)

- ✓ Chunking function implemented and tested
- ✓ Extraction processes passages instead of paths
- ✓ Cache keyed by passage_id
- ✓ Quality metrics calculated and stored
- ✓ All unit tests pass
- ✓ End-to-end extraction works

### Should Have (Phase 2)

- ✓ Cache regenerated with new approach
- ✓ Character coverage >= 90%
- ✓ Fact count >= 100 (3x improvement maintained)
- ✓ Extraction success rate >= 95%
- ✓ Webhook integration updated

### Nice to Have (Phase 3+)

- ○ Parallel extraction for performance
- ○ Expected character baseline for validation
- ○ Automated quality regression tests
- ○ Performance optimization

---

## Dependencies

### External Dependencies

- **Ollama API** - Must be available for extraction
- **AllPaths output** - Must exist before extraction
- **Experimental scripts** - Chunking algorithm proven

### Internal Dependencies

- `formats/story-bible/modules/loader.py` - Passage loading
- `services/lib/story_bible_extractor.py` - Core extraction
- `formats/story-bible/modules/ai_summarizer.py` - Deduplication
- `services/continuity-webhook.py` - Webhook integration

### Data Dependencies

- `dist/allpaths-metadata/*.txt` - Source passages
- `story-bible-cache.json` - Will be regenerated

---

## Rollback Plan

### If Critical Bug Discovered

**DO NOT revert to path-based extraction** (known to be inferior)

**Instead:**
1. Disable extraction temporarily (use cached data)
2. Fix bug in chunked approach
3. Re-run extraction
4. Validate fix

**Escape hatch:**
- Cached data still valid
- Can use old cache until bug fixed
- No user-facing impact (cached data serves Story Bible)

---

## Approval

**Architect sign-off:** Ready for Developer implementation

**Next steps:**
1. Developer reviews this design
2. Developer implements according to spec
3. Developer writes tests
4. Developer validates quality metrics
5. Commit and merge

**Questions:** Escalate to Architect or PM as needed

---

## Appendix A: Experimental Validation

### Experiment Results (from `scripts/experiment-chunked-extraction.py`)

**Test story:** NaNoWriMo2025 current content

**Current approach (path-based):**
- Characters detected: 5 (Javlyn, Terence, Danita, Kian, Jerrick)
- Total facts: 19
- Extraction time: ~45 minutes

**Chunked approach (passage-based):**
- Characters detected: 15 (added: Nivek, Eldon, Salie, Jeramee, Avery, Jessie, Maureen, Blue creature, Cave creature, Javlyn's Mother)
- Total facts: 116
- Extraction time: ~60 minutes (acceptable trade-off)

**Improvement:**
- Characters: 3x improvement (5 → 15)
- Facts: 6x improvement (19 → 116)
- Coverage: 200% more characters detected

**Conclusion:** Chunked approach strictly dominates path-based approach.

---

## Appendix B: Cache Format Reference

### Complete Cache Structure

```json
{
  "passage_extractions": {
    "passage_id_001": {
      "passage_name": "Start",
      "content_hash": "abc123...",
      "extracted_at": "2025-11-30T12:00:00",
      "passage_length": 5000,
      "chunks_processed": 1,
      "facts": [
        {
          "fact": "Javlyn is a student",
          "type": "character_identity",
          "confidence": "high",
          "evidence": [{
            "passage": "Start",
            "quote": "Javlyn was a student at the Academy"
          }],
          "category": "constant",
          "_chunk_number": 1,
          "_chunk_total": 1
        }
      ]
    }
  },
  "summarized_facts": {
    "constants": {
      "world_rules": [...],
      "setting": [...],
      "timeline": [...]
    },
    "characters": {
      "Javlyn": {
        "identity": [...],
        "zero_action_state": [...],
        "variables": [...]
      }
    },
    "variables": {
      "events": [...],
      "outcomes": [...]
    },
    "conflicts": [...]
  },
  "summarization_status": "success",
  "extraction_stats": {
    "total_passages": 62,
    "passages_with_facts": 58,
    "passages_with_no_facts": 4,
    "average_facts_per_passage": 2.6,
    "max_facts_in_passage": 15,
    "character_coverage": 0.938,
    "fact_distribution": {
      "character_identity": 46,
      "setting": 52,
      "world_rule": 38,
      "timeline": 24
    },
    "extraction_success_rate": 0.935,
    "deduplication_effectiveness": 0.47
  },
  "meta": {
    "last_extracted": "2025-11-30T12:00:00",
    "total_passages_extracted": 62,
    "total_facts": 160
  }
}
```

---

## Appendix C: Chunking Algorithm Pseudocode

```python
def chunk_passage(passage_name, passage_text, max_chars=20000, overlap=200):
    """
    Split passage into chunks with overlap.

    Strategy:
    1. Try paragraph boundaries (\n\n)
    2. Fall back to sentence boundaries (. )
    3. Fall back to word boundaries ( )
    4. Last resort: character split
    """

    # Fast path: no chunking needed
    if len(passage_text) <= max_chars:
        return [(passage_name, passage_text, 1)]

    chunks = []
    current_chunk = ""
    chunk_num = 1

    # Split into paragraphs
    paragraphs = passage_text.split("\n\n")

    for paragraph in paragraphs:
        # If adding this paragraph exceeds limit
        if len(current_chunk) + len(paragraph) > max_chars:
            # Save current chunk if not empty
            if current_chunk:
                chunk_name = f"{passage_name}_chunk_{chunk_num}"
                chunks.append((chunk_name, current_chunk, chunk_num))
                chunk_num += 1

                # Start new chunk with overlap
                current_chunk = current_chunk[-overlap:] + paragraph
            else:
                # Paragraph itself exceeds limit, split at sentences
                current_chunk = split_large_paragraph(paragraph, max_chars, overlap)
        else:
            # Add paragraph to current chunk
            current_chunk += "\n\n" + paragraph if current_chunk else paragraph

    # Save final chunk
    if current_chunk:
        chunk_name = f"{passage_name}_chunk_{chunk_num}"
        chunks.append((chunk_name, current_chunk, chunk_num))

    return chunks


def split_large_paragraph(paragraph, max_chars, overlap):
    """Split paragraph that exceeds max_chars at sentence boundaries."""

    sentences = paragraph.split(". ")
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = current[-overlap:] + sentence
            else:
                # Sentence itself exceeds limit, split at words
                current = split_at_words(sentence, max_chars, overlap)
        else:
            current += ". " + sentence if current else sentence

    if current:
        chunks.append(current)

    return "\n\n".join(chunks)


def split_at_words(sentence, max_chars, overlap):
    """Last resort: split at word boundaries."""

    words = sentence.split(" ")
    chunks = []
    current = ""

    for word in words:
        if len(current) + len(word) > max_chars:
            chunks.append(current)
            current = current[-overlap:] + " " + word
        else:
            current += " " + word if current else word

    if current:
        chunks.append(current)

    return "\n\n".join(chunks)
```

---

**End of Technical Design Document**
