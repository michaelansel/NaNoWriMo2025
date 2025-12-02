# Story Bible Pipeline Architectural Analysis and Fix Plan

**Status:** Design - Architectural review of pipeline data flow issues
**Date:** 2025-12-02
**Context:** Developer investigation revealed empty facts, missing metadata, and broken evidence in production Story Bible output

---

## Problem Summary

The Story Bible HTML displays empty data structures despite successful extraction:
- **Empty facts arrays**: Characters have no identity facts, constants have no world_rules
- **Empty evidence arrays**: All facts show `evidence: []` instead of passage citations
- **Missing metadata totals**: HTML shows 0 facts when cache contains hundreds
- **Evidence format mismatch**: Uses path hashes instead of passage names in rendering

---

## Current Architecture (From ADR-012 and Implementation)

### Pipeline Stages

```
Stage 1: Core Library (Tweego → passages_deduplicated.json)
   ↓
Stage 2: Extraction (Ollama AI → entities per passage)
   ↓
Stage 2.5: Aggregation (Deterministic entity merging)
   ↓
Stage 3: Categorization (Organize by type)
   ↓
Stage 4-5: Rendering (HTML/JSON generation)
```

### Cache Structure (story-bible-cache.json)

```json
{
  "passage_extractions": {
    "PassageName": {
      "entities": {
        "characters": [{"name": "X", "facts": [], "mentions": []}],
        "locations": [...],
        "items": [...]
      },
      "facts": []  // Empty for backward compatibility
    }
  },
  "summarized_facts": {
    "constants": {
      "world_rules": [],  // EMPTY - should have facts
      "setting": [{"fact": "Location: X", "evidence": []}],  // evidence EMPTY
      "timeline": []
    },
    "characters": {
      "Name": {
        "identity": [],  // EMPTY - should have facts
        "zero_action_state": [],
        "variables": [],
        "passages": ["A", "B"],
        "mentions": [...]
      }
    }
  },
  "categorized_facts": {...}
}
```

---

## Root Cause Analysis

### Issue 1: Extraction Stage Not Populating Facts Arrays

**Location:** `/home/ubuntu/Code/NaNoWriMo2025/services/lib/story_bible_extractor.py`

**Problem:**
- Extraction creates entity objects with `name` and `type`
- Does NOT populate `facts` or `mentions` arrays
- Extraction prompt asks for entities only, not facts about them

**Evidence from cache:**
```json
{
  "name": "Javlyn",
  "title": null,
  "mentions": [],  // EMPTY
  "facts": [],     // EMPTY
  "_chunk_number": 1
}
```

**Why this happens:**
- `EXTRACTION_PROMPT` says: "Extract ALL named entities... Respond with {entities: [{name, type}]}"
- AI returns entity names only
- No facts are extracted at entity-first stage
- Aggregation stage has no facts to aggregate

**Contract violation:**
The extraction output does not match the expected schema that aggregation consumes.

---

### Issue 2: Aggregation Stage Expects Facts That Don't Exist

**Location:** `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py`

**Problem:**
- Aggregation code iterates over `char.get('facts', [])` and `char.get('mentions', [])`
- Both arrays are empty (extraction doesn't populate them)
- Result: aggregated characters have empty identity arrays

**Evidence from code (ai_summarizer.py:124-138):**
```python
# Add facts as identity
for fact in char.get('facts', []):
    fact_text = fact.strip() if isinstance(fact, str) else str(fact)
    if fact_text and fact_text not in characters[normalized]['identity']:
        characters[normalized]['identity'].append(fact_text)

# Add mentions
for mention in char.get('mentions', []):
    quote = mention.get('quote', '')
    if quote and quote not in [m.get('quote') for m in characters[normalized]['mentions']]:
        characters[normalized]['mentions'].append({...})
```

**Why this happens:**
- Aggregation assumes extraction populates facts/mentions
- Extraction only provides entity names
- Schema mismatch between stages

---

### Issue 3: Evidence Format Inconsistency

**Location:** Rendering pipeline and cache format

**Problem:**
- ADR-012 specifies evidence format: `{passage: "Name", quote: "..."}`
- Current cache shows: `evidence: []` (empty arrays)
- HTML template expects passage names, but some code uses path hashes

**Why this happens:**
- Evidence is never attached to facts during extraction
- Aggregation creates facts but doesn't populate evidence arrays
- Different parts of pipeline have different expectations

**Evidence format contract from ADR-012:**
```typescript
evidence: Array<{
  passage: string;  // e.g., "Start", "Chapter 1"
  quote: string;    // e.g., "The city lay on the coast..."
}>
```

**Current reality:**
```json
{
  "fact": "Location: Mushroom Cave",
  "evidence": []  // ALWAYS EMPTY
}
```

---

### Issue 4: Missing Metadata Calculation

**Location:** Categorization stage

**Problem:**
- `categorized_facts.metadata` should contain totals
- HTML shows "0 facts" because metadata is missing or incorrect
- Metadata calculation depends on non-empty fact arrays

**Why this happens:**
- Metadata counts facts across categories
- If fact arrays are empty, counts are 0
- Rendering uses metadata for statistics display

---

## Data Flow Mismatch Diagram

### Intended Flow (Per PM Requirements)

```
Extraction (Per Passage):
  → Entities with facts: {name: "Javlyn", facts: ["is a student"], mentions: [{quote: "...", passage: "Start"}]}

Aggregation (Across Passages):
  → Merge entities, preserve all facts and evidence
  → Result: {identity: ["is a student"], evidence: [{passage: "Start", quote: "..."}]}

Categorization:
  → Organize by type, calculate totals
  → Result: {constants: {world_rules: [facts]}, metadata: {total_facts: 150}}

Rendering:
  → Display facts with evidence citations
  → Result: HTML shows "Javlyn is a student (Start, Day 2)"
```

### Actual Flow (Current Implementation)

```
Extraction (Per Passage):
  → Entities WITHOUT facts: {name: "Javlyn", facts: [], mentions: []}
  ❌ Schema mismatch: aggregation expects populated arrays

Aggregation (Across Passages):
  → Nothing to merge (arrays are empty)
  → Result: {identity: [], evidence: []}
  ❌ Empty data propagates through pipeline

Categorization:
  → Counts 0 facts, creates all bare entity names as "Location: X" facts
  → Result: {constants: {setting: [bare names]}, metadata: {total_facts: 0}}
  ❌ Metadata incorrect, world_rules empty

Rendering:
  → Displays empty sections and bare entity names without details
  → Result: HTML shows "Location: Mushroom Cave" with no description or evidence
  ❌ User sees empty Story Bible
```

---

## Schema Contracts (What Each Stage Expects)

### Stage 2 Output (Extraction) - CURRENT

```json
{
  "entities": {
    "characters": [
      {"name": "Javlyn", "title": null, "facts": [], "mentions": []}
    ],
    "locations": [
      {"name": "cave", "title": null, "facts": [], "mentions": []}
    ]
  },
  "facts": []  // Backward compat
}
```

### Stage 2 Output (Extraction) - REQUIRED BY AGGREGATION

```json
{
  "entities": {
    "characters": [
      {
        "name": "Javlyn",
        "title": null,
        "facts": [
          "is a student at the Academy",
          "struggles with magic"
        ],
        "mentions": [
          {
            "quote": "Javlyn entered the Academy",
            "context": "narrative",
            "passage": "Start"
          }
        ]
      }
    ]
  }
}
```

### Stage 2.5 Output (Aggregation) - EXPECTED

```json
{
  "characters": {
    "Javlyn": {
      "identity": [
        "is a student at the Academy",
        "struggles with magic"
      ],
      "mentions": [
        {"quote": "...", "passage": "Start"}
      ],
      "passages": ["Start", "Day 1"]
    }
  }
}
```

### Stage 3 Output (Categorization) - EXPECTED

```json
{
  "constants": {
    "world_rules": [
      {
        "fact": "Magic requires formal training",
        "evidence": [
          {"passage": "Start", "quote": "Only Academy students can learn magic"}
        ]
      }
    ]
  },
  "characters": {
    "Javlyn": {
      "identity": [
        {
          "fact": "is a student",
          "evidence": [{"passage": "Start", "quote": "Javlyn entered the Academy"}]
        }
      ]
    }
  },
  "metadata": {
    "total_facts": 150,
    "total_constants": 50,
    "total_characters": 10
  }
}
```

---

## Architectural Fix Plan

### Fix 1: Extraction Stage - Populate Facts and Mentions

**File:** `/home/ubuntu/Code/NaNoWriMo2025/services/lib/story_bible_extractor.py`

**Changes:**
1. Update `EXTRACTION_PROMPT` to request facts AND mentions for each entity
2. Modify extraction to populate `facts` array with entity-specific information
3. Populate `mentions` array with quote + passage name

**New prompt structure:**
```
For each entity, provide:
- name: The entity name
- type: character/location/item
- facts: Array of facts about this entity (e.g., ["is a student", "lives in the village"])
- mentions: Array of {quote: "...", context: "narrative"|"dialogue"}
```

**Expected output:**
```json
{
  "entities": [
    {
      "name": "Javlyn",
      "type": "character",
      "facts": ["is a student at the Academy", "struggles with magic"],
      "mentions": [
        {"quote": "Javlyn entered the Academy", "context": "narrative"}
      ]
    }
  ]
}
```

**Schema contract:**
- Extraction MUST populate `facts` array for each entity
- Extraction MUST populate `mentions` array with at least one quote per entity
- Aggregation can then merge these facts across passages

---

### Fix 2: Evidence Attachment - Link Facts to Passages

**File:** `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py`

**Changes:**
1. When aggregating facts, attach passage name to each fact
2. Convert facts from strings to fact objects with evidence
3. Preserve all passage citations when merging

**New aggregation logic:**
```python
# When processing facts from extraction
for fact in char.get('facts', []):
    fact_obj = {
        "fact": fact,
        "evidence": [
            {
                "passage": passage_id,  # The passage this came from
                "quote": find_supporting_quote(fact, char.get('mentions', []))
            }
        ]
    }
    characters[normalized]['identity'].append(fact_obj)
```

**Evidence construction:**
- Each fact becomes: `{fact: "...", evidence: [{passage: "X", quote: "..."}]}`
- When merging duplicate facts, combine evidence arrays
- All passage citations preserved

---

### Fix 3: Constants Extraction - Populate World Rules and Timeline

**File:** `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py`

**Problem:**
- `world_rules` and `timeline` are always empty
- Only `setting` gets populated (with bare location names)

**Changes:**
1. Add extraction of world rules (magic system, technology, physics)
2. Add extraction of timeline events (historical facts)
3. Categorize facts properly instead of dumping everything into `setting`

**New categorization logic:**
```python
# Identify world rules
if is_world_rule(fact):
    constants['world_rules'].append(fact_with_evidence)

# Identify timeline events
elif is_historical_event(fact):
    constants['timeline'].append(fact_with_evidence)

# Setting facts
elif is_setting_fact(fact):
    constants['setting'].append(fact_with_evidence)
```

**Heuristics for categorization:**
- World rules: "magic requires", "technology level", "always", "never"
- Timeline: "before the story", "years ago", "historically"
- Setting: Location descriptions, geography

---

### Fix 4: Metadata Calculation - Count Actual Facts

**File:** `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py` or categorization stage

**Changes:**
1. Count facts across all categories AFTER aggregation
2. Include character identity facts in count
3. Calculate totals correctly

**New metadata calculation:**
```python
def calculate_metadata(categorized_facts):
    total_facts = 0

    # Count constants
    for category in ['world_rules', 'setting', 'timeline']:
        total_facts += len(categorized_facts['constants'].get(category, []))

    # Count character facts
    for char_name, char_data in categorized_facts['characters'].items():
        total_facts += len(char_data.get('identity', []))
        total_facts += len(char_data.get('zero_action_state', []))

    # Count variables
    for category in ['events', 'outcomes']:
        total_facts += len(categorized_facts['variables'].get(category, []))

    return {
        'total_facts': total_facts,
        'total_constants': count_constants(categorized_facts),
        'total_characters': len(categorized_facts['characters']),
        'total_variables': count_variables(categorized_facts)
    }
```

---

### Fix 5: Rendering - Use Passage Names Not Hashes

**File:** `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/generator.py` and HTML template

**Problem:**
- Some code uses path hashes (`path-3a1dc016`) for evidence
- PM requirement: Use passage names users can verify in source

**Changes:**
1. Ensure extraction stores passage names (not hashes)
2. Rendering displays passage names directly
3. No hash-to-name mapping needed

**Current (broken):**
```html
Evidence: path-3a1dc016, path-7f2ab123
```

**Fixed:**
```html
Evidence: Start, Day 1 KEB, Academy Entrance
```

---

## Implementation Priority and Dependencies

### Phase 1: Fix Extraction (Blocks Everything)

**Priority:** CRITICAL - No other fixes work without this

**Files:**
- `/home/ubuntu/Code/NaNoWriMo2025/services/lib/story_bible_extractor.py`

**Tasks:**
1. Update `EXTRACTION_PROMPT` to request facts and mentions
2. Parse AI response to extract facts array
3. Parse AI response to extract mentions array with quotes
4. Test extraction produces populated arrays

**Success Criteria:**
- Cache shows `facts: ["is a student", ...]` not `facts: []`
- Cache shows `mentions: [{quote: "...", context: "narrative"}]` not `mentions: []`

---

### Phase 2: Fix Aggregation (Depends on Phase 1)

**Priority:** HIGH - Merges facts from extraction

**Files:**
- `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py`

**Tasks:**
1. Convert facts from strings to fact objects with evidence
2. Attach passage names to evidence
3. Merge evidence arrays when combining duplicate facts
4. Test aggregation preserves all passage citations

**Success Criteria:**
- Aggregated facts have evidence arrays populated
- Evidence cites all passages mentioning the fact
- Duplicate facts are merged with combined evidence

---

### Phase 3: Fix Categorization (Depends on Phase 2)

**Priority:** HIGH - Organizes facts correctly

**Files:**
- `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py` (categorization logic)

**Tasks:**
1. Add world rules extraction and categorization
2. Add timeline extraction and categorization
3. Fix metadata calculation to count actual facts
4. Test categorization populates all sections

**Success Criteria:**
- `world_rules` array has facts (not empty)
- `timeline` array has facts (not empty)
- `metadata.total_facts` matches actual fact count
- Character identity arrays have facts with evidence

---

### Phase 4: Fix Rendering (Depends on Phase 3)

**Priority:** MEDIUM - Display improvements

**Files:**
- `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/templates/story-bible.html.jinja2`
- `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/generator.py`

**Tasks:**
1. Ensure rendering uses passage names from evidence
2. Display evidence citations for each fact
3. Show metadata statistics correctly
4. Test HTML displays facts with passage names

**Success Criteria:**
- Facts show evidence like "Start, Day 1 KEB" not "path-abc123"
- Metadata shows correct totals
- All sections populated (world_rules, character identity, etc.)

---

## Testing Strategy

### Unit Tests (Per Stage)

**Extraction:**
```python
def test_extraction_populates_facts():
    result = extract_facts_from_passage(passage_text, "Start")
    assert len(result['entities']['characters'][0]['facts']) > 0
    assert len(result['entities']['characters'][0]['mentions']) > 0
```

**Aggregation:**
```python
def test_aggregation_preserves_evidence():
    aggregated = aggregate_entities_from_extractions(extractions)
    char = aggregated['characters']['Javlyn']
    assert len(char['identity']) > 0
    assert all('evidence' in fact for fact in char['identity'])
```

**Categorization:**
```python
def test_categorization_populates_all_sections():
    categorized = categorize_facts(aggregated)
    assert len(categorized['constants']['world_rules']) > 0
    assert categorized['metadata']['total_facts'] > 0
```

### Integration Tests (End-to-End)

**Test with sample story:**
1. Extract from sample passages
2. Aggregate entities
3. Categorize facts
4. Render HTML
5. Verify HTML contains:
   - Facts with evidence citations
   - Passage names (not hashes)
   - Non-zero metadata totals
   - Populated world_rules, character identity, etc.

---

## Schema Alignment Summary

### Key Contracts Between Stages

**Extraction → Aggregation:**
```
Input: passage text + passage name
Output: {
  entities: {
    characters: [{name, facts: [strings], mentions: [{quote, context}]}]
  }
}
Contract: facts and mentions arrays MUST be populated
```

**Aggregation → Categorization:**
```
Input: per_passage_extractions
Output: {
  characters: {
    Name: {
      identity: [{fact, evidence: [{passage, quote}]}],
      passages: [names]
    }
  }
}
Contract: All facts have evidence arrays with passage citations
```

**Categorization → Rendering:**
```
Input: categorized_facts
Output: HTML/JSON
Contract:
  - facts have evidence arrays
  - evidence contains passage names (not hashes)
  - metadata contains accurate totals
```

---

## Next Steps for Developer

1. **Implement Phase 1** (Extraction):
   - Update extraction prompt to request facts and mentions
   - Verify cache populates facts/mentions arrays
   - Run test extraction on sample passage

2. **Implement Phase 2** (Aggregation):
   - Convert facts to objects with evidence
   - Attach passage names to evidence
   - Test evidence preservation

3. **Implement Phase 3** (Categorization):
   - Add world_rules and timeline extraction
   - Fix metadata calculation
   - Test all sections populated

4. **Implement Phase 4** (Rendering):
   - Verify passage names used (not hashes)
   - Test HTML displays correctly
   - Deploy and verify production output

---

## Files Requiring Changes

**Critical Path:**
1. `/home/ubuntu/Code/NaNoWriMo2025/services/lib/story_bible_extractor.py` - Fix extraction
2. `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py` - Fix aggregation + categorization
3. `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/templates/story-bible.html.jinja2` - Fix rendering

**Supporting:**
4. `/home/ubuntu/Code/NaNoWriMo2025/lib/schemas/` - Update schemas if needed
5. Test files for each module

---

## Expected Outcomes After Fixes

**Production HTML should show:**
- ✅ Facts with descriptions (not just bare entity names)
- ✅ Evidence citations with passage names (e.g., "Start, Day 1 KEB")
- ✅ World rules section populated
- ✅ Character identity facts populated
- ✅ Metadata showing correct totals (e.g., "150 total facts")
- ✅ Every fact has at least one piece of evidence

**Cache should contain:**
- ✅ `passage_extractions` with populated facts/mentions arrays
- ✅ `summarized_facts.constants.world_rules` with facts
- ✅ `summarized_facts.characters.X.identity` with facts + evidence
- ✅ Evidence arrays with passage names and quotes

---

**End of Analysis**
