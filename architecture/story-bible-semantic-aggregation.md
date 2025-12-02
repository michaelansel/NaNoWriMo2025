# Architecture: Story Bible Semantic Fact Aggregation

## Status

**Proposed** - Technical design for LLM-based semantic fact merging
**Parent PRD**: `/home/user/NaNoWriMo2025/features/story-bible.md`
**Related**: `architecture/story-bible-noun-extraction.md`, `architecture/010-story-bible-design.md`

## Context

The Story Bible extraction pipeline currently uses deterministic exact-text matching for fact deduplication. This misses semantically equivalent facts that use different wording.

**Current Behavior** (exact-text matching only):
```
Character: Javlyn
  Identity Facts:
    - "has red hair" (evidence: passage A)
    - "hair is red" (evidence: passage B)
    - "red-haired" (evidence: passage C)
  → Result: 3 separate facts (should be 1 merged fact with 3 evidence citations)
```

**Desired Behavior** (semantic merging):
```
Character: Javlyn
  Identity Facts:
    - "has red hair" (evidence: passages A, B, C)
  → Result: 1 merged fact with complete evidence trail
```

**Impact on User Experience**:
- **Current**: Redundant facts clutter the Story Bible, making it harder to read
- **Desired**: Clean, unified view with each fact appearing once but citing all supporting passages
- **PRD Requirement**: "Deduplication reduces redundancy 30-50%"

**Problem Scope**:
This affects character identity facts, location facts, and item facts across all entity types. The exact-text deduplication in `ai_summarizer.py` (lines 158-172, 237-250, 313-327) needs semantic enhancement.

## Design Forces

1. **Evidence Preservation**: MUST preserve ALL evidence citations when merging facts (PRD requirement)
2. **Conservative Merging**: When uncertain about equivalence, keep facts separate (PRD: "Better slight redundancy than losing meaningful distinctions")
3. **Performance**: Additional AI calls will increase processing time (acceptable trade-off for better quality)
4. **Non-determinism**: LLM-based merging introduces variability (acceptable for quality improvement)
5. **Backward Compatibility**: Must work with existing cache structure and fact format
6. **Failure Resilience**: LLM failures should degrade gracefully to exact-text deduplication
7. **Contradiction Detection**: Must NOT merge contradictory facts (PRD: "Contradictory facts kept separate and flagged")

## Decision

### 1. Pipeline Architecture Change

Add a new **Stage 2.75: Semantic Fact Merging** between the existing aggregation and categorization stages.

**Current Pipeline** (`ai_summarizer.py`):
```
summarize_from_entities()
  ↓
Stage 2: aggregate_entities_from_extractions()  # Exact-text deduplication
  ↓
Stage 3: categorize_fact()  # Keyword-based classification
  ↓
Final output
```

**New Pipeline**:
```
summarize_from_entities()
  ↓
Stage 2: aggregate_entities_from_extractions()  # Exact-text deduplication
  ↓
Stage 2.75: semantic_merge_facts()  # NEW: LLM-based semantic merging
  ↓
Stage 3: categorize_fact()  # Keyword-based classification
  ↓
Final output
```

**Why Between Aggregation and Categorization**:
- Aggregation produces entity-grouped facts (characters, locations, items)
- Semantic merging operates within each entity's fact list
- Categorization happens after merging (operates on unified facts)
- Clean separation of concerns: aggregate → merge → classify

### 2. LLM Prompt Design

**Equivalence Checking Prompt**:
```python
SEMANTIC_EQUIVALENCE_PROMPT = """You are a fact equivalence checker for a story bible. Your job is to determine if two facts about the same entity are semantically equivalent (same meaning despite different wording).

Entity: {entity_name}
Fact 1: "{fact_1}"
Fact 2: "{fact_2}"

Are these facts semantically equivalent? Consider:

EQUIVALENT if:
- Same core meaning with different wording ("has red hair" vs "hair is red")
- One adds minor details to the other ("is a student" vs "is a student at the Academy")
- Different grammatical structures expressing same fact ("red-haired" vs "has red hair")

NOT EQUIVALENT if:
- Facts describe different attributes ("is a student" vs "is skilled in magic")
- Facts contradict each other ("hair is red" vs "hair is black")
- Facts describe different time periods ("was a student" vs "is a student")
- Uncertain whether same fact (when in doubt, say NOT equivalent)

Respond with JSON:
{
  "equivalent": true or false,
  "confidence": "high" or "medium" or "low",
  "merged_fact": "the unified wording (if equivalent, otherwise null)",
  "reasoning": "brief explanation"
}

Use conservative merging: if uncertain, mark as NOT equivalent.
"""
```

**Batch Prompt for Efficiency** (optional enhancement):
```python
SEMANTIC_BATCH_PROMPT = """You are a fact equivalence checker. Given a list of facts about {entity_name}, identify groups of semantically equivalent facts.

Facts:
{fact_list}

For each group of equivalent facts:
1. Assign a group ID
2. Provide merged wording
3. Explain equivalence

Respond with JSON:
{
  "groups": [
    {
      "group_id": 1,
      "fact_indices": [0, 2, 5],
      "merged_fact": "unified wording",
      "confidence": "high",
      "reasoning": "brief explanation"
    }
  ],
  "ungrouped_indices": [1, 3, 4]
}
"""
```

### 3. Semantic Merging Algorithm

**Function Signature**:
```python
def semantic_merge_facts(
    aggregated_entities: Dict,
    ollama_client: OllamaClient,
    confidence_threshold: str = "medium"
) -> Dict:
    """
    Merge semantically equivalent facts within each entity using LLM.

    Args:
        aggregated_entities: Output from aggregate_entities_from_extractions()
                            {'characters': {...}, 'locations': {...}, 'items': {...}}
        ollama_client: Ollama HTTP client for LLM calls
        confidence_threshold: Minimum confidence level for merging ("high" or "medium")

    Returns:
        Modified aggregated_entities with semantically merged facts
        (same structure, fewer duplicate facts per entity)

    Raises:
        OllamaTimeoutError: If LLM call exceeds timeout (non-fatal, degrades gracefully)
    """
```

**Algorithm**:
```python
def semantic_merge_facts(aggregated_entities, ollama_client, confidence_threshold="medium"):
    """
    For each entity (character, location, item):
      1. Extract fact list (identity, facts fields)
      2. If <= 1 fact: skip merging (nothing to merge)
      3. Perform pairwise equivalence checking:
         a. Compare fact[i] with fact[j] for all i < j
         b. Call LLM with equivalence prompt
         c. Parse JSON response
         d. If equivalent AND confidence >= threshold:
            - Create merged fact with combined evidence
            - Track merge (mark facts as merged group)
      4. Build final fact list:
         - For each merge group: single merged fact with all evidence
         - For unmerged facts: keep as-is
      5. Update entity with merged facts
    Return modified aggregated_entities
    """

    merged_entities = copy.deepcopy(aggregated_entities)

    # Process characters
    for char_name, char_data in merged_entities.get('characters', {}).items():
        char_data['identity'] = _merge_fact_list(
            facts=char_data['identity'],
            entity_name=char_name,
            entity_type='character',
            ollama_client=ollama_client,
            confidence_threshold=confidence_threshold
        )

    # Process locations
    for loc_name, loc_data in merged_entities.get('locations', {}).items():
        loc_data['facts'] = _merge_fact_list(
            facts=loc_data['facts'],
            entity_name=loc_name,
            entity_type='location',
            ollama_client=ollama_client,
            confidence_threshold=confidence_threshold
        )

    # Process items
    for item_name, item_data in merged_entities.get('items', {}).items():
        item_data['facts'] = _merge_fact_list(
            facts=item_data['facts'],
            entity_name=item_name,
            entity_type='item',
            ollama_client=ollama_client,
            confidence_threshold=confidence_threshold
        )

    return merged_entities
```

**Core Merging Logic**:
```python
def _merge_fact_list(facts, entity_name, entity_type, ollama_client, confidence_threshold):
    """
    Merge semantically equivalent facts in a list.

    Algorithm:
    1. Create union-find structure for grouping equivalent facts
    2. Pairwise comparison: for i < j, check if fact[i] ~ fact[j]
    3. Merge groups with transitive equivalence
    4. Build final fact list with merged evidence
    """
    if len(facts) <= 1:
        return facts  # Nothing to merge

    # Initialize union-find (each fact starts in its own group)
    fact_groups = UnionFind(len(facts))

    # Pairwise equivalence checking
    for i in range(len(facts)):
        for j in range(i + 1, len(facts)):
            fact_1 = facts[i]['fact']
            fact_2 = facts[j]['fact']

            try:
                # Call LLM for equivalence check
                result = check_equivalence(
                    entity_name=entity_name,
                    fact_1=fact_1,
                    fact_2=fact_2,
                    ollama_client=ollama_client
                )

                # Merge if equivalent with sufficient confidence
                if result['equivalent'] and _meets_confidence_threshold(
                    result['confidence'], confidence_threshold
                ):
                    fact_groups.union(i, j)
                    # Store merged wording for this group

            except OllamaError as e:
                # LLM failure: skip this comparison (conservative)
                logging.warning(f"LLM equivalence check failed: {e}")
                continue

    # Build merged fact list
    merged_facts = []
    groups = fact_groups.get_groups()  # {group_id: [fact_indices]}

    for group_id, fact_indices in groups.items():
        if len(fact_indices) == 1:
            # Ungrouped fact: keep as-is
            merged_facts.append(facts[fact_indices[0]])
        else:
            # Merge group: combine evidence from all facts
            merged_fact = _merge_fact_group(
                facts=[facts[idx] for idx in fact_indices],
                entity_name=entity_name
            )
            merged_facts.append(merged_fact)

    return merged_facts


def _merge_fact_group(facts, entity_name):
    """
    Merge a group of equivalent facts.

    Strategy:
    - Use first fact's wording (or LLM-suggested merged wording)
    - Combine ALL evidence from all facts in group
    - Preserve source passage references
    """
    merged_fact_text = facts[0]['fact']  # Use first fact's wording

    # Combine all evidence
    combined_evidence = []
    for fact in facts:
        combined_evidence.extend(fact.get('evidence', []))

    # Deduplicate evidence by (passage, quote) tuple
    unique_evidence = []
    seen = set()
    for ev in combined_evidence:
        key = (ev.get('passage'), ev.get('quote'))
        if key not in seen:
            unique_evidence.append(ev)
            seen.add(key)

    return {
        'fact': merged_fact_text,
        'evidence': unique_evidence
    }
```

### 4. Conservative Merging Strategy

**Confidence Thresholds**:
```python
CONFIDENCE_LEVELS = {
    "high": 3,     # LLM is very confident facts are equivalent
    "medium": 2,   # LLM thinks facts are likely equivalent
    "low": 1       # LLM is uncertain
}

def _meets_confidence_threshold(llm_confidence: str, threshold: str) -> bool:
    """
    Check if LLM confidence meets minimum threshold.

    Default threshold: "medium"
    - Accepts "high" and "medium" confidence merges
    - Rejects "low" confidence (conservative: keep separate when uncertain)
    """
    return CONFIDENCE_LEVELS.get(llm_confidence, 0) >= CONFIDENCE_LEVELS.get(threshold, 2)
```

**When to Merge**:
- **High confidence + equivalent**: Always merge
- **Medium confidence + equivalent**: Merge (default threshold)
- **Low confidence + equivalent**: Keep separate (conservative)
- **LLM says NOT equivalent**: Keep separate
- **LLM timeout or error**: Keep separate (fail safe)

**When to Keep Separate**:
- Facts about different attributes ("is a student" vs "has red hair")
- Contradictory facts ("hair is red" vs "hair is black")
- Time period differences ("was a student" vs "is a student")
- Uncertain equivalence ("low" confidence)
- LLM failure (network error, timeout, malformed response)

**Error Handling**:
```python
try:
    result = ollama_client.check_equivalence(fact_1, fact_2)
except OllamaTimeoutError:
    # Timeout: treat as "not equivalent" (conservative)
    logging.warning(f"LLM timeout checking equivalence: {fact_1} vs {fact_2}")
    return False
except OllamaError as e:
    # Other error: treat as "not equivalent"
    logging.error(f"LLM error: {e}")
    return False
except json.JSONDecodeError:
    # Malformed response: treat as "not equivalent"
    logging.error(f"Invalid JSON from LLM")
    return False
```

### 5. Integration Points

**Modified Functions** (in `/home/user/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py`):

**Function 1: `summarize_from_entities()` (lines 542-691)**
```python
def summarize_from_entities(merged_extractions: Dict) -> Tuple[Optional[Dict], str]:
    """
    Aggregate from entity-first extraction format.

    MODIFIED to add semantic merging stage.
    """
    logging.info("Aggregating entities deterministically (lossless)...")

    # Stage 2: Aggregate entities across passages (exact-text deduplication)
    aggregated = aggregate_entities_from_extractions(merged_extractions)

    # NEW: Stage 2.75: Semantic fact merging (LLM-based)
    try:
        ollama_client = OllamaClient()  # Initialize Ollama client
        aggregated = semantic_merge_facts(
            aggregated_entities=aggregated,
            ollama_client=ollama_client,
            confidence_threshold="medium"  # Conservative default
        )
        logging.info("Semantic fact merging completed")
    except Exception as e:
        # Non-fatal: continue with exact-text deduplication only
        logging.warning(f"Semantic merging failed, using exact-text deduplication: {e}")

    char_count = len(aggregated.get('characters', {}))
    loc_count = len(aggregated.get('locations', {}))
    item_count = len(aggregated.get('items', {}))

    logging.info(f"  → {char_count} characters, {loc_count} locations, {item_count} items")

    # Stage 3: Build final structure (categorize facts)
    # ... (rest of function unchanged)
```

**New Functions to Add**:
```python
def semantic_merge_facts(aggregated_entities, ollama_client, confidence_threshold):
    """New function - LLM-based semantic merging"""
    # Implementation as described above

def _merge_fact_list(facts, entity_name, entity_type, ollama_client, confidence_threshold):
    """New helper function - merge facts in a list"""
    # Implementation as described above

def _merge_fact_group(facts, entity_name):
    """New helper function - combine evidence from equivalent facts"""
    # Implementation as described above

def check_equivalence(entity_name, fact_1, fact_2, ollama_client):
    """New function - call LLM to check fact equivalence"""
    prompt = SEMANTIC_EQUIVALENCE_PROMPT.format(
        entity_name=entity_name,
        fact_1=fact_1,
        fact_2=fact_2
    )
    response = ollama_client.generate(
        model="gpt-oss:20b-fullcontext",
        prompt=prompt,
        options={"think": "low"}  # Consistent with existing Story Bible config
    )
    return json.loads(response['response'])

def _meets_confidence_threshold(llm_confidence, threshold):
    """New helper function - confidence threshold checking"""
    # Implementation as described above
```

**Input Format** (from `aggregate_entities_from_extractions()`):
```python
{
  'characters': {
    'Javlyn': {
      'identity': [
        {'fact': 'has red hair', 'evidence': [{'passage': 'A', 'quote': '...'}]},
        {'fact': 'hair is red', 'evidence': [{'passage': 'B', 'quote': '...'}]},
        {'fact': 'red-haired', 'evidence': [{'passage': 'C', 'quote': '...'}]}
      ],
      'mentions': [...],
      'passages': [...]
    }
  },
  'locations': {...},
  'items': {...}
}
```

**Output Format** (from `semantic_merge_facts()`):
```python
{
  'characters': {
    'Javlyn': {
      'identity': [
        {
          'fact': 'has red hair',
          'evidence': [
            {'passage': 'A', 'quote': '...'},
            {'passage': 'B', 'quote': '...'},
            {'passage': 'C', 'quote': '...'}
          ]
        }
      ],
      'mentions': [...],
      'passages': [...]
    }
  },
  'locations': {...},
  'items': {...}
}
```

**Data Structure Changes**: None (output format identical to input, just fewer facts with combined evidence)

### 6. Performance Considerations

**AI Call Budget**:
```
For each entity:
  For each pair of facts (i, j where i < j):
    1 LLM call to check equivalence

Example: Entity with 10 facts
  = C(10, 2) = 45 pairwise comparisons
  = 45 LLM calls

Average entity: 3-5 facts
  = C(5, 2) = 10 pairwise comparisons
  = 10 LLM calls per entity

Typical story: 15 characters, 8 locations, 5 items
  = 28 entities × 10 calls = 280 LLM calls

LLM call latency: ~2 seconds each
  = 280 × 2s = 560 seconds (~9 minutes)
```

**Optimization Strategies**:

**1. Early Termination**:
```python
# Skip merging if fact list is small
if len(facts) <= 1:
    return facts  # Nothing to merge

# Skip semantic merging if exact-text already merged everything
if len(facts) <= 2:
    return facts  # Minimal redundancy possible
```

**2. Batch Processing** (future enhancement):
```python
# Instead of N×(N-1)/2 pairwise calls, use single batch call
result = ollama_client.batch_equivalence_check(entity_name, fact_list)
# Returns groups of equivalent facts
# Reduces 45 calls → 1 call for 10 facts
```

**3. Caching** (future enhancement):
```python
# Cache equivalence results across builds
cache_key = f"{fact_1_hash}|{fact_2_hash}"
if cache_key in equivalence_cache:
    return equivalence_cache[cache_key]
```

**4. Timeout Configuration**:
```python
SEMANTIC_MERGE_TIMEOUT = 600  # 10 minutes max for entire semantic merging stage
PER_COMPARISON_TIMEOUT = 10   # 10 seconds per pairwise comparison

# If overall timeout exceeded, return partially merged results
```

**Performance Impact**:
- **Current pipeline**: ~30 seconds (aggregation + categorization)
- **With semantic merging**: ~10-15 minutes (depends on fact count)
- **Acceptable**: Story Bible is async (webhook-triggered, not blocking CI)

### 7. Non-Determinism Implications

**Sources of Non-Determinism**:
1. **LLM equivalence judgments**: May vary between runs
2. **Merged wording selection**: LLM may suggest different unified wording
3. **Confidence levels**: May fluctuate for borderline cases

**Mitigation Strategies**:
1. **Conservative threshold**: Use "medium" confidence (rejects uncertain cases)
2. **Stable wording**: Use first fact's wording instead of LLM suggestion (deterministic)
3. **Consistent prompts**: Well-defined equivalence criteria in prompt
4. **Evidence preservation**: Even if merging varies, all evidence always present

**Acceptable Non-Determinism**:
- Different groupings across runs: Acceptable (all evidence preserved)
- Different merged wordings: Mitigated (use first fact's wording)
- Confidence variations: Acceptable (conservative threshold reduces impact)

**Unacceptable Non-Determinism** (must prevent):
- Lost evidence citations: PREVENTED (always combine all evidence)
- Merged contradictions: PREVENTED (LLM trained to detect contradictions)
- Irreversible merges: MITIGATED (per-passage cache still available)

## Consequences

### Positive

1. **Cleaner Story Bible**: 30-50% reduction in redundant facts (meets PRD target)
2. **Better User Experience**: Each fact appears once with complete evidence trail
3. **Semantic Understanding**: "has red hair" and "hair is red" correctly merged
4. **Conservative Approach**: When uncertain, keeps facts separate (meets PRD requirement)
5. **Evidence Preservation**: ALL passage citations maintained (meets PRD requirement)
6. **Graceful Degradation**: LLM failures fall back to exact-text deduplication
7. **Contradiction Detection**: LLM identifies contradictory facts, keeps separate
8. **Backward Compatible**: Same cache structure, same evidence format

### Negative

1. **Processing Time**: Adds ~10-15 minutes to Story Bible extraction
2. **Non-Determinism**: Merging may vary slightly between runs
3. **LLM Dependency**: Requires Ollama available and responsive
4. **Complexity**: More code paths, more failure modes
5. **Resource Usage**: Hundreds of LLM calls per story
6. **Debugging Difficulty**: Harder to trace why facts were/weren't merged

### Trade-offs

**Accepted**:
- **Longer processing time → Better quality**: Worth 10-15 minutes for 30-50% redundancy reduction
- **Non-determinism → Semantic understanding**: Worth slight variability for correct merging
- **LLM dependency → Intelligent merging**: Worth dependency for semantic equivalence detection
- **Complexity → User experience**: Worth code complexity for cleaner Story Bible output

**Mitigated**:
- **Processing time**: Async webhook processing (doesn't block CI)
- **Non-determinism**: Conservative threshold + evidence preservation
- **LLM dependency**: Graceful fallback to exact-text deduplication
- **Complexity**: Clear separation of concerns (new stage, existing stages unchanged)
- **Debugging**: Detailed logging of merge decisions with reasoning

## Alternatives Considered

### Alternative 1: Rule-Based Semantic Matching

**Approach**: Use NLP techniques (word embeddings, edit distance) instead of LLM

**Example Rules**:
```python
# Cosine similarity of sentence embeddings > threshold
similarity = cosine_similarity(embed(fact_1), embed(fact_2))
if similarity > 0.85:
    merge(fact_1, fact_2)

# Levenshtein distance < threshold
distance = levenshtein_distance(fact_1, fact_2)
if distance < 5:
    merge(fact_1, fact_2)
```

**Rejected Because**:
- **False positives**: "hair is red" vs "eyes are red" would match (high similarity)
- **False negatives**: "has red hair" vs "red-haired" might not match (structural difference)
- **No context understanding**: Can't detect contradictions ("red" vs "black hair")
- **Brittle rules**: Edge cases require constant tuning
- **No reasoning**: Can't explain why facts were merged

**Why LLM is better**:
- Understands semantic meaning, not just word similarity
- Detects contradictions ("red hair" vs "black hair")
- Provides reasoning for merge decisions
- Handles diverse grammatical structures
- Requires minimal tuning

### Alternative 2: Manual Merge Annotations

**Approach**: Let users annotate equivalent facts in source files

**Example**:
```twee
:: PassageA
Javlyn has red hair. /* @fact-id: hair-color */

:: PassageB
Her hair is red. /* @fact-id: hair-color */
```

**Rejected Because**:
- **High maintenance burden**: Users must maintain annotations across all passages
- **Error-prone**: Easy to forget annotations or use inconsistent IDs
- **Defeats automation**: Story Bible should extract automatically, not require manual work
- **Not scalable**: Doesn't work for existing stories without annotations
- **User friction**: Writers focus on storytelling, not metadata management

### Alternative 3: Post-Merge User Review

**Approach**: LLM merges facts, users review and approve/reject merges

**Workflow**:
1. LLM proposes merges
2. Story Bible shows "Review 15 proposed merges"
3. User approves or rejects each merge
4. System learns from user decisions

**Rejected Because**:
- **Requires UI changes**: Need merge review interface
- **User effort**: Every extraction requires manual review
- **Blocks automation**: Can't generate Story Bible without user input
- **Not urgent**: Can add later if conservative merging proves insufficient
- **Over-engineering**: Conservative threshold + evidence preservation should be sufficient

### Alternative 4: No Semantic Merging

**Approach**: Keep current exact-text deduplication, accept redundancy

**Rationale**:
- Simplest solution (no new code)
- Fully deterministic
- No LLM dependency

**Rejected Because**:
- **Poor user experience**: Story Bible cluttered with redundant facts
- **Doesn't meet PRD target**: "30-50% redundancy reduction" likely unachievable with exact-text only
- **User complaints**: "Why is 'red hair' listed 3 times?"
- **Doesn't leverage AI**: We already use Ollama for extraction, semantic merging is natural extension

## Implementation Plan

### Phase 1: Core Semantic Merging (Week 1)

**Tasks**:
1. Implement `semantic_merge_facts()` function
2. Implement `check_equivalence()` LLM call wrapper
3. Implement `_merge_fact_list()` with union-find algorithm
4. Implement `_merge_fact_group()` evidence combining
5. Add confidence threshold logic
6. Integrate into `summarize_from_entities()` with try/except fallback
7. Add logging for merge decisions

**Acceptance Criteria**:
- Semantic merging reduces redundancy 30-50% on test story
- All evidence preserved in merged facts
- LLM failures degrade gracefully to exact-text deduplication
- Merged facts cite all source passages
- Conservative threshold rejects low-confidence merges

### Phase 2: Testing and Validation (Week 2)

**Tasks**:
1. Unit tests for `_merge_fact_list()` with mock LLM
2. Integration tests with real Ollama
3. Test conservative merging (uncertain cases kept separate)
4. Test contradiction detection (contradictions not merged)
5. Test evidence preservation (all passages cited)
6. Test graceful degradation (LLM failures handled)
7. Measure redundancy reduction on full story

**Acceptance Criteria**:
- Tests pass with 100% success rate
- Contradictory facts remain separate
- Evidence complete in all merged facts
- LLM timeout/error handling works
- Redundancy reduction 30-50% on test story

### Phase 3: Performance Optimization (Week 3)

**Tasks**:
1. Add early termination (skip entities with ≤2 facts)
2. Add overall timeout (10 minutes max)
3. Add per-comparison timeout (10 seconds max)
4. Profile LLM call latency
5. Measure total processing time on full story
6. Optimize prompts for faster LLM responses

**Acceptance Criteria**:
- Semantic merging completes in <15 minutes for typical story
- Timeout handling prevents runaway processing
- Prompt optimizations reduce LLM latency 20%+
- No performance regression in exact-text deduplication path

### Phase 4: Monitoring and Refinement (Week 4)

**Tasks**:
1. Add detailed logging (merge decisions with reasoning)
2. Add metrics collection (merge rate, confidence distribution)
3. Review merge decisions on full story manually
4. Adjust confidence threshold if needed
5. Refine LLM prompt based on false positives/negatives
6. Document design decisions in code comments

**Acceptance Criteria**:
- Logging shows reasoning for all merge decisions
- Metrics show merge rate, confidence levels, error rate
- Manual review finds <5% incorrect merges
- False positive rate (incorrect merges) <5%
- False negative rate (missed merges) acceptable (conservative approach)

## Success Metrics

**Primary Metrics** (Testable):
- **Redundancy Reduction**: 30-50% fewer facts after semantic merging compared to exact-text only (measurable: count facts before/after)
- **Evidence Preservation**: 100% of merged facts have complete evidence from all source facts (testable: validate all evidence fields populated)
- **Conservative Merging**: <5% of "low confidence" merges occur (testable: log confidence levels, measure distribution)
- **Graceful Degradation**: 100% of LLM errors result in fallback to exact-text deduplication (testable: simulate errors, verify fallback)

**Secondary Metrics** (Observable):
- Processing time: <15 minutes for typical story (measurable: time semantic merging stage)
- False positive rate: <5% (incorrect merges) (measurable: manual review sample)
- Contradiction preservation: 100% of contradictory facts remain separate (testable: create test cases with contradictions)
- LLM call count: ~10 per entity average (measurable: log API calls)

**Qualitative Indicators**:
These guide our design but cannot be directly measured:
- Writers report Story Bible is easier to read with less redundancy
- Merged facts feel "natural" and preserve meaning
- No user complaints about lost information
- Users trust semantic merging results

## References

- **PRD**: `/home/user/NaNoWriMo2025/features/story-bible.md`
- **Current Architecture**: `/home/user/NaNoWriMo2025/architecture/010-story-bible-design.md`
- **Entity Extraction**: `/home/user/NaNoWriMo2025/architecture/story-bible-noun-extraction.md`
- **Aggregator Code**: `/home/user/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py`
- **Standards**: `/home/user/NaNoWriMo2025/STANDARDS.md`
- **System Architecture**: `/home/user/NaNoWriMo2025/ARCHITECTURE.md`
