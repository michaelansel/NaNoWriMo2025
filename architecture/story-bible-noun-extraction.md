# Architecture: Entity-First Story Bible Extraction

## Status

**Proposed** - Technical design for noun-focused entity extraction
**Parent PRD**: `/home/ubuntu/Code/NaNoWriMo2025/features/story-bible-noun-extraction.md`
**Related**: `architecture/010-story-bible-design.md` (existing fact-based extraction)

## Context

The current Story Bible extraction uses a fact-first approach ("Javlyn is a student") that misses entities mentioned only in dialogue, possessives, or passing references. After running extraction on the current story, we found **12/15 known characters**, missing:
- **Marcie** (mentioned 4 times in dialogue: "when Marcie was with us")
- **Miss Rosie** (mentioned once in possessive: "Miss Rosie's famous beef stew")
- **Josie** (mentioned once in narrative: "Josie fell out of a tree")

The PM-defined solution is to **extract entities FIRST** (nouns: characters, locations, items), then associate facts with those entities. This ensures **100% entity detection** before fact association.

## Problem Statement

**Current Fact-First Approach**:
```
AI Prompt: "Extract facts from this passage"
  ↓
AI looks for declarative statements
  ↓
"Javlyn is a student" → EXTRACTED ✓
"when Marcie was with us" → MISSED ❌ (not a fact, just dialogue)
"Miss Rosie's beef stew" → MISSED ❌ (about food, not character)
"Josie fell out of a tree" → MISSED ❌ (past event, not current fact)
```

**Result**: Inconsistent entity extraction, gaps in character roster

**Desired Entity-First Approach**:
```
AI Prompt: "Extract ALL named entities from this passage"
  ↓
STEP 1: Scan for entities (nouns)
  ↓
"Marcie" → ENTITY (character) ✓
"Miss Rosie" → ENTITY (character) ✓
"Josie" → ENTITY (character) ✓
"beef stew" → ENTITY (item) ✓
  ↓
STEP 2: For each entity, associate facts/mentions
  ↓
Marcie: "mentioned 4 times, former group member"
Miss Rosie: "mentioned 1 time, makes beef stew"
Josie: "mentioned 1 time, fell from tree"
```

**Result**: 100% entity detection, complete census of story world

## Design Forces

1. **100% Entity Detection**: Must not miss entities mentioned only in dialogue, possessives, or passing references
2. **Backward Compatibility**: Existing cache structure should evolve gracefully (not full rewrite)
3. **Evidence Preservation**: Every entity must cite ALL passages where mentioned
4. **Two-Pass Extraction**: Entity detection MUST happen before fact association
5. **Normalization**: "Rosie's" and "Miss Rosie" must resolve to same entity
6. **Minimal Facts Acceptable**: Entities appear even with sparse information ("Marcie was mentioned")
7. **Conservative Deduplication**: When uncertain, keep entities separate

## Decision

### 1. Two-Pass Extraction Architecture

We modify the AI extraction prompt to perform **two sequential passes** on each passage:

**Pass 1: Entity Extraction** (CRITICAL - Must be first)
- Scan passage for ALL named entities
- Extract: characters, locations, items, organizations, concepts
- Apply normalization rules (possessive stripping, title preservation)
- Output: List of entities with type classification

**Pass 2: Fact Association** (After entities identified)
- For each entity from Pass 1, extract:
  - Identity facts (if available)
  - Mentions (ALL passages where entity appears)
  - Context (dialogue, narrative, possessive, internal thought)
  - Relationships (entity X associated with entity Y)

### 2. Data Structure Changes

**Current Cache Structure**:
```json
{
  "passage_extractions": {
    "passage_id": {
      "facts": [
        {
          "fact": "Javlyn is a student",
          "type": "character_identity",
          "evidence": [...]
        }
      ]
    }
  }
}
```

**New Cache Structure** (entity-first):
```json
{
  "passage_extractions": {
    "passage_id": {
      "entities": {
        "characters": [
          {
            "name": "Marcie",
            "title": null,
            "mentions": [
              {
                "passage": "passage_id",
                "context": "dialogue",
                "quote": "when Marcie was with us",
                "type": "past_member"
              }
            ],
            "facts": [
              "Was previously with the group",
              "Left or lost (implied by 'was with us')"
            ]
          },
          {
            "name": "Miss Rosie",
            "title": "Miss",
            "mentions": [
              {
                "passage": "passage_id",
                "context": "possessive",
                "quote": "Miss Rosie's famous beef stew",
                "type": "indirect_reference"
              }
            ],
            "facts": [
              "Makes beef stew (famous for it)"
            ]
          }
        ],
        "locations": [...],
        "items": [...],
        "organizations": [...],
        "concepts": [...]
      }
    }
  },
  "summarized_facts": {
    "entities": {
      "characters": {
        "Marcie": {
          "identity": [...],
          "mentions": [...],
          "facts": [...]
        },
        "Miss Rosie": {
          "identity": [...],
          "mentions": [...],
          "facts": [...]
        }
      },
      "locations": {...},
      "items": {...}
    },
    "constants": {...},
    "variables": {...}
  }
}
```

### 3. AI Prompt Changes

**Current Prompt** (fact-first):
```
Extract FACTS about an interactive fiction story world.

Extract these fact types:
1. World Rules
2. Setting
3. Character Identities
4. Timeline

Output: {
  "facts": [
    {"fact": "...", "type": "...", "confidence": "...", "evidence": [...]}
  ]
}
```

**New Prompt** (entity-first):
```
Extract ALL named entities from an interactive fiction story passage.

STEP 1: ENTITY EXTRACTION (CRITICAL - Do this first)

Scan the passage for ALL named entities. Extract EVERY proper noun, named item, location, and character.

Types of entities to extract:
1. CHARACTERS (people, beings):
   - Proper names: Javlyn, Terence, Marcie, Miss Rosie, Josie
   - Titles + names: "Miss Rosie" (extract as single entity with title)
   - Mentioned in dialogue: "when Marcie was with us"
   - Possessive form: "Rosie's beef stew" → Extract "Miss Rosie"
   - Indirect mention: "Josie fell out of a tree" → Extract "Josie"

2. LOCATIONS (places):
   - Named places: Academy, village, city, cave, passageway

3. ITEMS/OBJECTS (things):
   - Named items: lantern, jerkin, belt, beef stew, artifact

4. ORGANIZATIONS/GROUPS:
   - Named groups: "the village", "our group"

5. CONCEPTS/ABILITIES (if named):
   - Named abilities: "workings", "luck working", "light working"

NORMALIZATION RULES:
- Strip possessives: "Rosie's" → "Rosie"
- Preserve titles: "Miss Rosie" (NOT just "Rosie")
- Case-insensitive: "Marcie" = "marcie"

STEP 2: FACT ASSOCIATION (After entities extracted)

For each entity extracted in Step 1, extract:
- Identity facts (if available)
- Mentions: ALL passages where entity appears
- Context: How entity is mentioned (dialogue, narrative, possessive, etc.)
- Relationships: Entity X associated with entity Y

OUTPUT FORMAT:
{
  "entities": {
    "characters": [
      {
        "name": "Marcie",
        "title": null,
        "mentions": [
          {
            "passage": "passage_id",
            "context": "dialogue",
            "quote": "when Marcie was with us",
            "type": "past_member"
          }
        ],
        "facts": [
          "Was previously with the group",
          "Left or lost (implied by 'was with us')"
        ]
      }
    ],
    "locations": [...],
    "items": [...],
    "organizations": [...],
    "concepts": [...]
  }
}

CRITICAL RULES:
- Extract EVERY named entity, even if only mentioned once
- Dialogue mentions count (don't skip "when Marcie was with us")
- Possessive mentions count (don't skip "Miss Rosie's beef stew")
- When in doubt, EXTRACT IT (better to over-extract than miss entities)
```

### 4. Normalization Rules

**Title Preservation**:
- "Miss Rosie" → Canonical: "Miss Rosie" (title + name)
- Store separately: `{name: "Rosie", title: "Miss"}`
- Never strip significant titles from canonical name

**Possessive Normalization**:
- "Rosie's beef stew" → Extract "Rosie" (character) + "beef stew" (item)
- Strip possessive marker: "Rosie's" → "Rosie"
- Apply title if known: "Rosie's" → "Miss Rosie" (if context provides)

**Case Normalization**:
- "Marcie" = "marcie" = "MARCIE" (case-insensitive matching)
- Store canonical form: "Marcie" (first letter uppercase)

**Variant Tracking**:
- Track all forms seen: "Rosie", "Miss Rosie", "Rosie's"
- Map to canonical: "Miss Rosie"
- Document in metadata: `{"canonical": "Miss Rosie", "variants": ["Rosie", "Rosie's"]}`

### 5. Summarization Changes

**Current Summarization** (fact-based):
- Deduplicate facts: "Javlyn is a student" + "Javlyn is a student" → Single fact
- Merge related facts: "City is coastal" + "City is on eastern coast" → Combined fact
- Group by type: world_rules, setting, timeline, character_identity

**New Summarization** (entity-based):
- **Entity deduplication**: Merge "Marcie" mentions across passages into single entity
- **Mention aggregation**: Combine ALL 4 Marcie mentions into one entity entry
- **Fact merging**: Combine facts about same entity from different passages
- **Relationship preservation**: "Miss Rosie" → "beef stew" relationship maintained
- **Evidence aggregation**: ALL source passages cited for each entity

**Summarization Output**:
```json
{
  "entities": {
    "characters": {
      "Marcie": {
        "identity": ["Former member of Terence's group"],
        "mentions": [
          {"passage": "KEB-251101", "quote": "when Marcie was with us", "context": "dialogue"},
          {"passage": "mansel-20251114", "quote": "since we lost Marcie", "context": "dialogue"},
          {"passage": "KEB-251108", "quote": "even when Marcie was with us", "context": "dialogue"},
          {"passage": "KEB-251108", "quote": "since we had Marcie", "context": "dialogue"}
        ],
        "facts": [
          "Was member of group",
          "No longer with group (lost/left)",
          "Group's workings were stronger with Marcie"
        ],
        "relationships": [
          {"type": "was_member_of", "entity": "Terence's group"}
        ]
      },
      "Miss Rosie": {
        "identity": ["Makes beef stew (famous)"],
        "mentions": [
          {"passage": "passage_id", "quote": "Miss Rosie's famous beef stew", "context": "possessive"}
        ],
        "facts": [
          "Makes beef stew (famous for it)"
        ],
        "relationships": [
          {"type": "makes", "entity": "beef stew"}
        ]
      }
    }
  }
}
```

### 6. Backward Compatibility Strategy

**Migration Plan**:

**Phase 1: Dual Output** (Transitional)
- Extractor outputs BOTH old format (facts) and new format (entities)
- Cache stores both: `{"facts": [...], "entities": {...}}`
- Renderer checks for `entities` first, falls back to `facts`
- Allows gradual migration

**Phase 2: Entity-First Default**
- New extractions use entity-first format only
- Old cached data remains in fact format (still renderable)
- Summarization converts facts → entities during aggregation

**Phase 3: Full Migration** (Future)
- Re-run extraction on all passages (webhook command)
- Convert entire cache to entity-first format
- Remove fact-first code paths

**Cache Compatibility**:
```json
{
  "passage_extractions": {
    "passage_id": {
      "facts": [...],        // Old format (deprecated)
      "entities": {...}      // New format (preferred)
    }
  },
  "extraction_version": "2.0-entity-first"  // Version marker
}
```

**Renderer Compatibility**:
```python
def load_extraction_data(passage_data):
    # Check for new format first
    if "entities" in passage_data:
        return render_from_entities(passage_data["entities"])
    # Fall back to old format
    elif "facts" in passage_data:
        return render_from_facts(passage_data["facts"])
    else:
        return render_placeholder()
```

## Technical Implementation

### 1. Extraction Pipeline: Passage-Based Approach

**Design Decision**: Extract from individual Twee passages, not paths

**Rationale**:
- **Deduplication at load time**: Each passage processed exactly once, regardless of how many paths contain it
- **Granular caching**: Cache per passage (not per path), enabling efficient incremental updates
- **Simpler AI context**: Single passage is clearer than mixed passages from a path
- **Accurate evidence**: Cite exact passage where entity appears, not an arbitrary path

**Data Flow**:
```
AllPaths Output (allpaths.txt)
  ↓
Parse into individual passages using [PASSAGE: hex_id] markers
  ↓
Translate hex ID → passage name (allpaths-passage-mapping.json)
  ↓
Extract entities from each passage (1 passage at a time)
  ↓
Cache per-passage extractions (key: passage_name)
  ↓
Aggregate entities across all passages during summarization
```

**File**: `/home/ubuntu/Code/NaNoWriMo2025/services/lib/story_bible_extractor.py`

**Parsing Strategy**:

**Input Format** (AllPaths output):
```
[PATH 1/573]

========================================
PASSAGE: 6c6f636b65642d726f6f6d
========================================

:: Locked Room
You try the door. Locked.

[[Try to pick the lock|lockpicking]]
[[Give up|hallway]]

========================================
PASSAGE: 6c6f636b7069636b696e67
========================================

:: Lockpicking
You examine the lock mechanism...
```

**Parsing Logic**:
```python
def parse_passages_from_allpaths(allpaths_content: str, mapping: Dict[str, str]) -> List[Dict]:
    """
    Extract individual passages from AllPaths output.

    Process:
    1. Split on [PASSAGE: hex_id] markers
    2. Extract hex ID from marker
    3. Translate hex_id → passage_name using mapping
    4. Extract passage content (between PASSAGE marker and next marker or end)
    5. Deduplicate: track seen passages, process each only once

    Args:
        allpaths_content: Raw AllPaths output (allpaths.txt)
        mapping: hex_id → passage_name translation (allpaths-passage-mapping.json)

    Returns:
        List of unique passages:
        [
          {
            "passage_id": "locked-room",  # Human-readable name
            "hex_id": "6c6f636b65642d726f6f6d",  # Original hex ID
            "content": ":: Locked Room\nYou try the door...",  # Full passage text
            "source": "allpaths.txt"
          },
          ...
        ]
    """
    passages = []
    seen_hex_ids = set()  # Deduplication tracker

    # Split on PASSAGE markers
    passage_blocks = re.split(r'\[PASSAGE: ([a-f0-9]+)\]', allpaths_content)

    for i in range(1, len(passage_blocks), 2):  # Skip first empty block, process pairs
        hex_id = passage_blocks[i]
        content = passage_blocks[i + 1] if i + 1 < len(passage_blocks) else ""

        # Deduplicate: skip if already seen
        if hex_id in seen_hex_ids:
            continue
        seen_hex_ids.add(hex_id)

        # Translate hex ID to passage name
        passage_name = mapping.get(hex_id)
        if not passage_name:
            # Log warning but continue (unmapped ID)
            logger.warning(f"Unmapped hex ID: {hex_id}")
            continue

        # Extract content (strip separator lines)
        content_clean = content.strip()
        content_clean = re.sub(r'^=+\n', '', content_clean)  # Remove separators

        passages.append({
            "passage_id": passage_name,
            "hex_id": hex_id,
            "content": content_clean,
            "source": "allpaths.txt"
        })

    return passages
```

**Deduplication Strategy**:
- **At parse time**: Track `seen_hex_ids` set, process each hex ID exactly once
- **Result**: Each passage appears once in extraction list, regardless of path count
- **Cache key**: Use `passage_name` (human-readable) not hex ID

**ID Translation**:
- **Mapping file**: `allpaths-passage-mapping.json` (generated by AllPaths)
- **Format**: `{"hex_id": "passage-name", ...}`
- **Usage**: Translate hex IDs to human-readable names for cache keys and PR comments
- **Fallback**: If hex ID unmapped, log warning and skip passage (don't crash)

**Extraction Loop**:
```python
def extract_from_allpaths(allpaths_path: str, mapping_path: str) -> Dict:
    """
    Extract entities from AllPaths output.

    Process:
    1. Load AllPaths output and mapping file
    2. Parse into individual passages (deduplicated)
    3. Extract entities from each passage
    4. Cache per-passage extractions
    5. Return aggregated cache
    """
    # Load files
    with open(allpaths_path) as f:
        allpaths_content = f.read()
    with open(mapping_path) as f:
        mapping = json.load(f)

    # Parse passages (deduplicated)
    passages = parse_passages_from_allpaths(allpaths_content, mapping)

    # Extract entities per passage
    cache = {"passage_extractions": {}}
    for passage in passages:
        entities = extract_entities_from_passage(
            passage_text=passage["content"],
            passage_id=passage["passage_id"]  # Use human-readable name
        )

        # Cache using passage name as key
        cache["passage_extractions"][passage["passage_id"]] = {
            "entities": entities,
            "hex_id": passage["hex_id"],  # Preserve for debugging
            "extracted_at": datetime.utcnow().isoformat()
        }

    return cache
```

**Function Signature Changes**:
```python
# Before (fact-first)
def extract_facts_from_passage(passage_text: str, passage_id: str) -> List[Dict]:
    """Returns list of facts"""

# After (entity-first, passage-based)
def extract_entities_from_passage(passage_text: str, passage_id: str) -> Dict:
    """
    Extract entities from a single Twee passage.

    Args:
        passage_text: Full content of single passage (Twee markup included)
        passage_id: Human-readable passage name (e.g., "locked-room")

    Returns:
        Structured entity data:
        {
          "entities": {
            "characters": [...],
            "locations": [...],
            "items": [...],
            "organizations": [...],
            "concepts": [...]
          }
        }
    """
```

### 2. Summarization Changes

**File**: `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py`

**Changes**:
- Update `summarize_facts()` to handle entity structures
- Add `aggregate_entity_mentions()` to combine mentions across passages
- Add `deduplicate_entities()` to merge same entity (name normalization)
- Update conflict detection to flag entity contradictions

**New Functions**:
```python
def aggregate_entity_mentions(per_passage_entities: Dict) -> Dict:
    """
    Aggregate entities from all passages.

    For each unique entity (by canonical name):
    - Combine all mentions from all passages
    - Merge facts from all passages
    - Preserve complete evidence trail

    Returns:
        Dict mapping canonical name to aggregated entity data
    """

def normalize_entity_name(name: str, title: Optional[str], context: Dict) -> str:
    """
    Apply normalization rules to entity name.

    Rules:
    - Strip possessives: "Rosie's" → "Rosie"
    - Preserve titles: "Miss" + "Rosie" → "Miss Rosie"
    - Case normalize: "marcie" → "Marcie"

    Returns:
        Canonical entity name
    """
```

### 3. HTML Renderer Changes

**File**: `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/html_generator.py`

**Changes**:
- Update template to render entities (characters, locations, items)
- Add entity type sections (Characters, Locations, Items, Organizations, Concepts)
- Display mention count and contexts for each entity
- Show relationships between entities (Rosie → beef stew)
- Mark "lightly mentioned" entities (1-2 mentions vs fully developed)

**Template Changes**:
```html
<!-- Before: Fact-based sections -->
<h2>Constants</h2>
<h3>World Rules</h3>
<ul>
  <li>Fact 1</li>
  <li>Fact 2</li>
</ul>

<!-- After: Entity-based sections -->
<h2>Characters</h2>
<div class="character" id="marcie">
  <h3>Marcie</h3>
  <p class="mention-count">Mentioned 4 times</p>
  <div class="identity">
    <h4>Identity</h4>
    <ul>
      <li>Former member of Terence's group</li>
    </ul>
  </div>
  <div class="mentions">
    <h4>Mentions</h4>
    <ul>
      <li><span class="context">Dialogue</span>: "when Marcie was with us" (KEB-251101)</li>
      <li><span class="context">Dialogue</span>: "since we lost Marcie" (mansel-20251114)</li>
      ...
    </ul>
  </div>
  <div class="facts">
    <h4>Facts</h4>
    <ul>
      <li>Was member of group</li>
      <li>No longer with group (lost/left)</li>
    </ul>
  </div>
</div>

<h2>Items</h2>
<div class="item" id="beef-stew">
  <h3>Beef Stew</h3>
  <p class="mention-count">Mentioned 1 time</p>
  <div class="relationships">
    <h4>Associated With</h4>
    <ul>
      <li><a href="#miss-rosie">Miss Rosie</a> (makes)</li>
    </ul>
  </div>
  <div class="mentions">
    <h4>Mentions</h4>
    <ul>
      <li><span class="context">Possessive</span>: "Miss Rosie's famous beef stew" (passage_id)</li>
    </ul>
  </div>
</div>
```

### 4. Cache Schema Updates

**Cache Structure** (passage-based):
```json
{
  "extraction_version": "2.0-entity-first-passage-based",
  "extraction_timestamp": "2025-12-01T12:00:00Z",
  "passage_extractions": {
    "locked-room": {
      "entities": {
        "characters": [...],
        "locations": [...],
        "items": [...]
      },
      "hex_id": "6c6f636b65642d726f6f6d",
      "extracted_at": "2025-12-01T12:00:00Z"
    },
    "lockpicking": {
      "entities": {
        "characters": [...],
        "items": [...]
      },
      "hex_id": "6c6f636b7069636b696e67",
      "extracted_at": "2025-12-01T12:00:00Z"
    }
  }
}
```

**Cache Keys**:
- **Key format**: Human-readable passage name (e.g., `"locked-room"`)
- **NOT hex IDs**: Use passage names for readability in cache and PR comments
- **Hex ID preserved**: Stored in `hex_id` field for debugging and traceability
- **Deduplication**: Each passage name appears exactly once, regardless of path count

**Entity Schema** (per passage):
```json
{
  "characters": [
    {
      "name": "string (canonical name)",
      "title": "string | null (honorific/title)",
      "mentions": [
        {
          "passage": "string (passage name, not hex ID)",
          "context": "dialogue | narrative | possessive | internal_thought",
          "quote": "string (exact quote from passage)",
          "type": "string (mention type: past_member, indirect_reference, etc.)"
        }
      ],
      "facts": ["string (fact about character)"],
      "relationships": [
        {
          "type": "string (relationship type: was_member_of, makes, etc.)",
          "entity": "string (related entity name)"
        }
      ],
      "variants": ["string (name variants seen: Rosie, Rosie's)"]
    }
  ]
}
```

## Consequences

### Positive

1. **100% Entity Detection**: No more missed characters in dialogue or possessives
2. **Complete Story Census**: Every named thing (character, location, item) cataloged
3. **Better Collaboration**: New writers see ALL entities mentioned in story
4. **Structured Relationships**: Rosie → beef stew associations captured
5. **Context Preservation**: Know HOW each entity is mentioned (dialogue vs narrative)
6. **Minimal Facts Accepted**: Entities appear even with sparse information
7. **Backward Compatible**: Gradual migration from fact-first to entity-first
8. **Passage-Based Benefits**:
   - **No redundant extraction**: Each passage processed exactly once (deduplication at load time)
   - **Granular caching**: Update cache for individual passages, not entire paths
   - **Clearer AI context**: Single passage is simpler than mixed path content
   - **Accurate evidence**: Citations reference exact passage, not arbitrary path
   - **Incremental updates**: Re-extract only changed passages, not all paths
   - **Human-readable cache**: Passage names as keys (not hex IDs) make cache and PR comments readable

### Negative

1. **Larger Cache Files**: Entity structure more verbose than fact list
2. **More Complex Rendering**: HTML must handle entity types and relationships
3. **Potential Over-Extraction**: May extract generic "the woman" if not careful
4. **Migration Effort**: Existing cache needs conversion or re-extraction
5. **AI Prompt Complexity**: Two-pass extraction requires more detailed instructions
6. **Deduplication Complexity**: Name normalization (possessives, titles) is nuanced
7. **Passage-Based Challenges**:
   - **Parsing complexity**: Must correctly split AllPaths output on PASSAGE markers
   - **ID translation dependency**: Requires `allpaths-passage-mapping.json` to be available and current
   - **Unmapped passages**: Need graceful handling when hex ID not in mapping file
   - **Separator stripping**: Must clean up AllPaths formatting (separator lines) before extraction

### Trade-offs

**Accepted**:
- Larger cache size → Better completeness (worth it for 100% detection)
- More complex extraction → Better quality (worth it for entity relationships)
- Verbose entity structure → Better evidence (worth it for context preservation)
- Passage parsing complexity → Cleaner deduplication (worth it for no redundant extraction)
- ID translation dependency → Human-readable cache (worth it for PR comment clarity)

**Mitigated**:
- Generic over-extraction → AI prompt filters generic references
- Migration effort → Phased approach with backward compatibility
- Name normalization complexity → Well-defined rules in prompt and code
- Unmapped hex IDs → Log warnings and skip gracefully (don't crash extraction)
- Separator formatting → Regex-based cleanup removes AllPaths artifacts

## Alternatives Considered

### Alternative 1: Path-Based Extraction

**Approach**: Extract entities from complete paths (sequence of passages) rather than individual passages

**Path-based data flow**:
```
AllPaths Output (allpaths.txt)
  ↓
Extract each complete path (all passages in sequence)
  ↓
Run AI extraction on entire path content
  ↓
Cache per-path extractions (key: path_number)
```

**Rejected Because**:
- **Redundant extraction**: Passages repeated across paths would be extracted multiple times
  - Example: "hallway" passage appears in paths 1, 3, 5, 12, 27... (extracted 5+ times)
  - Result: Wasted AI calls, slower extraction, higher costs
- **Path-based cache inefficient**: Updating 1 passage requires re-extracting all paths containing it
- **Confusing evidence**: "Entity found in path 42" doesn't tell you WHICH passage in that path
- **Arbitrary path selection**: When citing evidence, which path do you choose? (Same passage in 5 paths)
- **Mixed AI context**: Paths contain multiple passages; harder for AI to attribute entities to specific passages

**Why passage-based is better**:
- Each passage extracted exactly once (deduplication at load time)
- Cache updates are granular (1 passage = 1 cache entry)
- Evidence is precise (cite exact passage, not arbitrary path)
- AI context is clearer (single passage at a time)

### Alternative 2: Fact-First with Better Prompts

**Approach**: Keep fact-first extraction, improve AI prompt to catch dialogue mentions

**Rejected Because**:
- Fundamentally can't fix: "when Marcie was with us" is NOT a declarative fact
- Requires contorting fact extraction to include non-facts
- Still misses possessive references ("Miss Rosie's beef stew")
- Doesn't solve the core issue: entities are nouns, not facts

### Alternative 3: Entity Extraction as Separate Pass (Post-Summarization)

**Approach**: Run fact extraction first, then entity extraction as separate stage

**Rejected Because**:
- Redundant: Entities are embedded in facts anyway
- Two separate AI calls per passage (slower, more expensive)
- Harder to maintain consistency between fact and entity views
- Misses opportunity to organize extraction around entities from start

### Alternative 4: Manual Entity Registry

**Approach**: Writers manually maintain list of entities (characters, locations, items)

**Rejected Because**:
- High maintenance burden on writers
- Out of sync with story content quickly
- Defeats purpose of automated extraction
- Still need AI to associate facts with manual entities

### Alternative 5: Full Cache Rewrite (No Backward Compatibility)

**Approach**: Replace entire cache structure with entity-first, re-extract all passages

**Rejected Because**:
- Breaks existing cache immediately
- Forces re-extraction of entire story (slow, risky)
- No gradual migration path
- High risk for production disruption

## Implementation Plan

### Phase 1: Passage Parser and Entity Extractor (Week 1)

**Developer Tasks**:
1. **Implement passage parser**:
   - `parse_passages_from_allpaths()`: Split AllPaths output on `[PASSAGE: hex_id]` markers
   - Load `allpaths-passage-mapping.json` for hex ID → passage name translation
   - Deduplicate passages (track `seen_hex_ids` set)
   - Strip separator lines and formatting artifacts
   - Handle unmapped hex IDs gracefully (log warnings, skip passage)
2. **Update entity extractor**:
   - Update `EXTRACTION_PROMPT` to entity-first template
   - Modify `extract_facts_from_passage()` → `extract_entities_from_passage()`
   - Add entity normalization functions (title preservation, possessive stripping)
3. **Update cache structure**:
   - Use passage names as cache keys (not hex IDs)
   - Include `entities` section alongside `facts` for backward compatibility
   - Preserve `hex_id` in metadata for debugging
4. **Test extraction**:
   - Verify parsing correctly extracts individual passages
   - Test on known missing entities (Marcie, Miss Rosie, Josie)
   - Verify 100% detection on sample passages

**Acceptance Criteria**:
- Parser correctly splits AllPaths output into individual passages
- Deduplication works (each passage processed once, regardless of path count)
- Hex ID translation works (passage names as cache keys)
- Unmapped hex IDs handled gracefully (logged, not crashed)
- Extractor outputs both `facts` (old) and `entities` (new) for backward compatibility
- Marcie, Miss Rosie, Josie all extracted correctly
- Entity mentions cite correct passage names (not hex IDs)
- Title preservation works ("Miss Rosie" not "Rosie")
- Possessive normalization works ("Rosie's" → "Rosie")

### Phase 2: Entity Summarization (Week 2)

**Developer Tasks**:
1. Update `ai_summarizer.py` to aggregate entities across passages
2. Implement entity deduplication (same entity from multiple passages)
3. Combine entity mentions (4 Marcie mentions → 1 Marcie entity)
4. Preserve complete evidence trail (all passages cited)
5. Update cache writes to include entity-based summarization
6. Test on full story extraction

**Acceptance Criteria**:
- Marcie entity shows all 4 mentions aggregated
- Miss Rosie → beef stew relationship preserved
- No duplicate entities (name normalization working)
- All evidence preserved in aggregated entity

### Phase 3: Entity Renderer (Week 3)

**Developer Tasks**:
1. Update `html_generator.py` to render entity sections
2. Add Characters, Locations, Items, Organizations, Concepts sections
3. Display mention count and contexts for each entity
4. Show relationships between entities
5. Mark "lightly mentioned" vs "fully developed" entities
6. Update story-bible.html template with entity styling

**Acceptance Criteria**:
- Story Bible HTML shows all entity types
- Marcie appears in Characters section with 4 mentions
- Miss Rosie appears with relationship to beef stew
- Beef stew appears in Items section
- Links between related entities work

### Phase 4: Testing and Validation (Week 4)

**Developer Tasks**:
1. Run full extraction on current story
2. Verify all 15 known characters appear (including Marcie, Miss Rosie, Josie)
3. Test edge cases from PRD (possessives, dialogue, indirect mentions)
4. Validate cache format compatibility
5. Test HTML rendering for all entity types
6. Performance testing (extraction time, cache size)

**Acceptance Criteria**:
- 15/15 characters detected (100% success)
- All PRD test cases pass
- Cache file size acceptable (< 10 MB)
- HTML renders correctly for all entities
- Extraction completes in < 10 minutes

## Success Metrics

**Primary Metrics**:
- **Entity detection rate**: 15/15 characters (100%) vs 12/15 (80%) before
- **Zero missed dialogue mentions**: All characters in dialogue captured
- **Zero missed possessive mentions**: All possessive references captured
- **Complete entity census**: All named things (characters, locations, items) listed

**Secondary Metrics**:
- Entity type accuracy: >95% correctly categorized (character vs location vs item)
- Normalization accuracy: >98% (titles preserved, possessives stripped correctly)
- Relationship detection: Significant relationships captured (Rosie → beef stew)
- Context capture: >90% of mentions include context type and quote

**Qualitative Indicators**:
- Writers trust Story Bible as complete entity registry
- No surprises when searching for character ("Why isn't Marcie in here?")
- New collaborators get full picture of who/what exists in story

## References

- **PRD**: `/home/ubuntu/Code/NaNoWriMo2025/features/story-bible-noun-extraction.md`
- **Current Architecture**: `/home/ubuntu/Code/NaNoWriMo2025/architecture/010-story-bible-design.md`
- **Extractor Code**: `/home/ubuntu/Code/NaNoWriMo2025/services/lib/story_bible_extractor.py`
- **Summarizer Code**: `/home/ubuntu/Code/NaNoWriMo2025/formats/story-bible/modules/ai_summarizer.py`
- **Standards**: `/home/ubuntu/Code/NaNoWriMo2025/STANDARDS.md`
