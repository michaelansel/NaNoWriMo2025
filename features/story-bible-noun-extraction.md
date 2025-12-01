# Feature PRD: Noun-Focused Story Bible Extraction

**Status:** Planned
**Owner:** Product Manager
**Priority:** HIGH
**Target:** Immediate (Replaces current fact-based extraction)
**Parent Feature:** [Story Bible](story-bible.md)

---

## Executive Summary

The current Story Bible extraction focuses on "facts" but misses entities that are only mentioned in passing, especially in dialogue or possessive phrases. This PRD defines a **noun-first extraction approach** that ensures **100% entity detection** before associating facts with those entities.

**Strategic Goal:** Ensure nothing mentioned in the story is lost.

**Current Problem:**
- Story Bible extracts "facts" like "Javlyn is a student"
- Misses characters only mentioned in dialogue: "when Marcie was with us", "Miss Rosie's famous beef stew", "Josie fell out of a tree"
- Found 12/15 known characters after improvements
- Missing: Marcie, Miss Rosie, Josie

**Solution:** Extract entities (characters, locations, items) FIRST, then associate facts/mentions with those entities.

---

## User Problem

**For writers using the Story Bible:**
- Characters mentioned only in dialogue don't appear in the Story Bible
- Possessive references ("Miss Rosie's beef stew") don't register as character entities
- Indirect mentions ("when Marcie was with us") get lost
- Items and locations only named once are missed
- Writers assume if it's named in the story, it's in the Story Bible - but it's not

**Real-World Examples from Our Story:**
- ❌ **Marcie** mentioned 4 times in dialogue but NOT in Story Bible
  - "when Marcie was with us"
  - "since we lost Marcie"
  - "even when Marcie was with us"
  - "We haven't done it successfully since we had Marcie"

- ❌ **Miss Rosie** mentioned once in possessive form but NOT in Story Bible
  - "Miss Rosie's famous beef stew"

- ❌ **Josie** mentioned once in narrative but NOT in Story Bible
  - "There was the time Josie fell out of a tree"

**Impact:**
- Writers reference characters that don't exist in the Story Bible
- New collaborators miss important entities that are mentioned but not "fact-ified"
- Story continuity checking misses contradictions involving these entities
- Trust in Story Bible erodes ("It's incomplete, so I can't rely on it")

---

## User Stories

### Story 1: Writer Reviewing All Named Entities
**As a** writer reviewing world consistency
**I want** to see EVERY named entity mentioned anywhere in the story
**So that** I know who/what exists in the world, even if only mentioned briefly

**Acceptance Criteria:**
- Story Bible lists ALL characters, regardless of how they're mentioned
- Includes characters mentioned in dialogue ("when Marcie was with us")
- Includes characters in possessive form ("Miss Rosie's beef stew")
- Includes characters in indirect references ("Josie fell out of a tree")
- Each entity shows ALL passages where it's mentioned
- Entities with minimal information still appear (even if only mentioned once)

---

### Story 2: Collaborator Understanding Who Exists
**As a** new collaborator learning the story
**I want** to see a complete list of all named characters
**So that** I understand who has been established, even if they haven't appeared directly

**Acceptance Criteria:**
- Character list includes everyone mentioned, not just characters with scenes
- Can see "lightly mentioned" vs "fully developed" characters
- Understand which characters exist but haven't been developed yet
- Distinguish between "mentioned once" and "recurring presence"
- Complete census of the story's population

---

### Story 3: Writer Tracking Items and Locations
**As a** writer maintaining world consistency
**I want** to see all named items and locations
**So that** I can reference them consistently and avoid contradictions

**Acceptance Criteria:**
- Story Bible lists all named items (artifacts, weapons, food, objects)
- Story Bible lists all named locations (cities, buildings, landmarks, rooms)
- Items mentioned in possessive form captured ("Miss Rosie's beef stew" → "beef stew" as item, "Miss Rosie" as character)
- Locations mentioned indirectly captured ("the cave entrance", "the passageway")
- Each item/location shows where it's mentioned

---

### Story 4: AI Understanding Entity Scope
**As a** developer integrating AI validation
**I want** clear entity boundaries and types
**So that** AI can validate references and relationships correctly

**Acceptance Criteria:**
- Each entity has a clear type: character, location, item, organization, concept
- Entity names normalized (possessives stripped: "Rosie's" → "Rosie")
- Titles preserved as part of names ("Miss Rosie", "Dr. Smith")
- Relationships between entities captured (Rosie associated with beef stew)
- Machine-readable entity registry (JSON format)

---

## Feature Behavior

### Two-Step Extraction Process

**Current (Fact-First) Approach:**
```
Extract facts from passage
  ↓
"Javlyn is a student" → Extract
"when Marcie was with us" → MISSED (not a declarative fact)
"Miss Rosie's beef stew" → MISSED (not about a fact, about food)
```

**New (Entity-First) Approach:**
```
STEP 1: Extract ALL named entities (nouns)
  ↓
Scan passage for:
  - Proper nouns (Javlyn, Marcie, Miss Rosie, Josie, Terence)
  - Named locations (Academy, village, cave, passageway)
  - Named items (lantern, jerkin, belt, femurs, beef stew)
  - Organizations (village, group, we/us in context)
  ↓
STEP 2: Associate facts/mentions with entities
  ↓
For each entity found, extract:
  - Identity facts (if available)
  - Mentions (where entity appears)
  - Relationships (entity X mentioned with entity Y)
  - Context (dialogue, narrative, possessive, etc.)
```

**Result:**
- Marcie extracted as character entity (mentioned 4 times)
- Miss Rosie extracted as character entity (mentioned 1 time, possessive context)
- Josie extracted as character entity (mentioned 1 time, past event context)
- Beef stew extracted as item entity (associated with Miss Rosie)
- ALL entities captured, even if facts are minimal

---

### Entity Types and Extraction Rules

#### 1. **Characters** (People/Beings)

**What to Extract:**
- Any named person, creature, or being mentioned in the story
- Proper names: Javlyn, Terence, Danita, Kian
- Titles + names: Miss Rosie, Dr. Smith, Captain Jones
- Named groups referred to as individuals: "the manipulator", "the woman"

**Where to Look:**
- Direct dialogue: "Marcie was with us"
- Possessive forms: "Rosie's beef stew" → Extract "Rosie" (with "Miss" title)
- Indirect references: "Josie fell out of a tree" → Extract "Josie"
- Pronouns with antecedents: Track back to named entity
- Group pronouns: "we", "us" in dialogue → Infer group membership

**Normalization:**
- Strip possessive markers: "Rosie's" → "Rosie"
- Preserve titles: "Miss Rosie", "Dr. Smith" (NOT "Rosie", "Smith")
- Preserve full names: "Miss Rosie" as single entity
- Handle variations: "Marcie" = "Marcie" (case-insensitive matching)

**Edge Cases:**
- Generic references: "the blacksmith", "the guard" → Extract if they recur or are plot-significant
- Unnamed speakers: "the woman" → Extract if referenced multiple times, note as unnamed
- Group names: "the village", "our group" → Extract as organization entities
- Animals/creatures: Extract if named individually

#### 2. **Locations** (Places)

**What to Extract:**
- Named places: Academy, village, city, cave
- Geographic features: mountain, coast, forest, river
- Buildings/structures: inn, temple, library, passageway
- Rooms/areas: entrance, chamber, hall

**Where to Look:**
- Explicit naming: "the Academy", "the village"
- Descriptive references: "the cave entrance", "the passageway" → Extract "cave", "passageway"
- Implied locations: "back down" implies direction/place
- Setting descriptions: "coastal city" → Extract "city" + attribute "coastal"

**Normalization:**
- "the Academy" → "Academy"
- "the city" → "city" (generic unless named)
- "Miss Rosie's kitchen" → "kitchen" (location) + relationship to "Miss Rosie"

**Edge Cases:**
- Generic vs specific: "a cave" vs "the cave" (extract both, note specificity)
- Nested locations: "entrance to the cave" → Extract "cave" and "cave entrance" as sub-location

#### 3. **Items/Objects** (Things)

**What to Extract:**
- Named objects: artifacts, weapons, tools, food
- Significant items: lantern, jerkin, belt, femurs, litter, beef stew
- Magical items: magic-specific objects, ritual components
- Unique items: "the artifact", "the lantern" (if it's THE lantern, not just any lantern)

**Where to Look:**
- Possessive descriptions: "Miss Rosie's famous beef stew" → Extract "beef stew"
- Object interactions: "holding the lantern", "wrapped the bones"
- Unique items: "the artifact" implies specific item
- Named items: "Excalibur", "the One Ring" (if story has such items)

**Normalization:**
- "Miss Rosie's beef stew" → "beef stew" (item) + relationship to "Miss Rosie"
- "the lantern" → "lantern" (note: specific instance)
- "femurs" → "femurs" (plural form preserved)

**Edge Cases:**
- Generic vs unique: "a lantern" vs "the lantern" (extract both, note specificity)
- Food items: "beef stew" is named/significant (famous), extract it
- Common objects: "belt", "jerkin" → Extract if mentioned specifically, skip if generic background

#### 4. **Organizations/Groups** (Collectives)

**What to Extract:**
- Named groups: "our group", "the village", "the Academy" (when referring to institution)
- Collective pronouns: "we", "us" → Infer group membership
- Factions: political groups, teams, families

**Where to Look:**
- Dialogue pronouns: "when Marcie was with us" → "us" = group entity
- Group references: "the village does workings" → "village" = organization
- Membership: "running away and joining us" → "us" = Terence's group

**Normalization:**
- "us" in context → Resolve to group name if available ("Terence's group", "the village")
- Generic groups: "the village" → "village" (organization type)

**Edge Cases:**
- Overlapping types: "Academy" = location AND organization (dual-type entity)
- Implicit groups: Characters mentioned together form implicit group

#### 5. **Concepts/Abilities** (Abstract Named Things)

**What to Extract:**
- Named abilities: "workings", "luck working", "light working"
- Magic systems: spell names, ritual types
- Abstract concepts: if they're named and recurring

**Where to Look:**
- Terminology: "workings" is specific term in this story
- Named techniques: "luck working", "light working"
- Recurring concepts: "zero action state" (meta-concept about story)

**Normalization:**
- "workings" → "working" (singular form for concept)
- "luck working" → Separate concept or sub-type of "working"

**Edge Cases:**
- Common words with special meaning: "working" is common word but has specific meaning in story

---

### Extraction Methodology

**AI Extraction Prompt Template (Entity-First):**

```
You are extracting ALL named entities from an interactive fiction story passage.

STEP 1: ENTITY EXTRACTION (CRITICAL - Do this first)

Scan the passage for ALL named entities. Extract EVERY proper noun, named item, location, and character.

Types of entities to extract:

1. CHARACTERS (people, beings):
   - Proper names: Javlyn, Terence, Marcie, Miss Rosie, Josie
   - Titles + names: "Miss Rosie" (extract as single entity with title)
   - Mentioned in dialogue: "when Marcie was with us"
   - Possessive form: "Rosie's beef stew" → Extract "Miss Rosie"
   - Indirect mention: "Josie fell out of a tree" → Extract "Josie"
   - Pronouns with clear antecedents: Track back to named character

2. LOCATIONS (places):
   - Named places: Academy, village, city, cave, passageway
   - Geographic features: mountain, coast, forest
   - Buildings: inn, temple, entrance
   - Extract even if mentioned once

3. ITEMS/OBJECTS (things):
   - Named items: lantern, jerkin, belt, beef stew, artifact
   - Unique objects: "the lantern" (if it's THE specific one)
   - Food: "Miss Rosie's famous beef stew" → Extract "beef stew"
   - Tools, weapons, magical items

4. ORGANIZATIONS/GROUPS:
   - Named groups: "the village", "our group"
   - Collective pronouns: "we", "us" → Resolve to group if possible
   - Institutions: "the Academy" (when referring to organization)

5. CONCEPTS/ABILITIES (if named):
   - Named abilities: "workings", "luck working", "light working"
   - Magic terms specific to this story

NORMALIZATION RULES:
- Strip possessives: "Rosie's" → "Rosie"
- Preserve titles: "Miss Rosie" (NOT just "Rosie")
- Case-insensitive: "Marcie" = "marcie"
- Resolve pronouns: "she" → Track to named entity if clear

STEP 2: FACT ASSOCIATION (After entities extracted)

For each entity extracted in Step 1, extract:
- Identity facts (if available): "Javlyn is a student"
- Mentions: ALL passages where entity appears
- Context: How entity is mentioned (dialogue, narrative, possessive, etc.)
- Relationships: Entity X associated with entity Y
- Minimal info acceptable: Even if only "Marcie was mentioned"

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

CRITICAL RULES:
- Extract EVERY named entity, even if only mentioned once
- Dialogue mentions count (don't skip "when Marcie was with us")
- Possessive mentions count (don't skip "Miss Rosie's beef stew")
- Indirect mentions count (don't skip "Josie fell out of a tree")
- When in doubt, EXTRACT IT (better to over-extract than miss entities)

Your goal: 100% entity detection. Nothing named in the story should be missed.
```

---

### What Makes Good Entity Extraction (Quality Criteria)

**Success Indicators:**

1. **Complete Entity Census (100% Capture)**
   - ✅ All characters mentioned anywhere in story
   - ✅ Includes dialogue-only mentions ("when Marcie was with us")
   - ✅ Includes possessive mentions ("Miss Rosie's beef stew")
   - ✅ Includes indirect mentions ("Josie fell out of a tree")
   - ✅ No named entity missed

2. **Proper Normalization**
   - ✅ Titles preserved: "Miss Rosie" (not "Rosie")
   - ✅ Possessives stripped: "Rosie's" → "Rosie"
   - ✅ Case-insensitive matching: "Marcie" = "marcie"
   - ✅ Variations handled: Same entity across different mentions

3. **Context Preservation**
   - ✅ Each mention shows HOW entity appears (dialogue, narrative, possessive)
   - ✅ Quote from passage showing entity mention
   - ✅ Relationship context (Rosie associated with beef stew)

4. **Entity Type Accuracy**
   - ✅ Characters correctly identified as characters
   - ✅ Locations correctly identified as locations
   - ✅ Items correctly identified as items
   - ✅ Dual-type entities handled (Academy = location + organization)

5. **Minimal Information Acceptable**
   - ✅ Entities appear even with minimal facts
   - ✅ "Marcie (mentioned 4 times, former group member)" is valid entry
   - ✅ "Miss Rosie (mentioned 1 time, makes beef stew)" is valid entry
   - ✅ No entity excluded due to "not enough information"

**Bad Extraction Indicators (What to Avoid):**
- ❌ Missing dialogue-only mentions
- ❌ Missing possessive mentions
- ❌ Skipping entities mentioned once
- ❌ Stripping important titles ("Miss Rosie" → "Rosie")
- ❌ Failing to normalize possessives ("Rosie's" kept as separate entity)
- ❌ No context for how entity was mentioned
- ❌ Generic references extracted excessively ("the woman", "the man" everywhere)

---

## Edge Cases

### Edge Case 1: Possessive References
**Scenario:** Character mentioned only in possessive form

**Example:** "Miss Rosie's famous beef stew"

**Behavior:**
- Extract "Miss Rosie" as character entity (preserve "Miss" title)
- Extract "beef stew" as item entity
- Create relationship: beef stew associated with Miss Rosie
- Note context: possessive reference, indirect mention
- Entity type: Character (even though only mentioned via possession)

---

### Edge Case 2: Dialogue-Only Mentions
**Scenario:** Character mentioned only in dialogue, never appears directly

**Example:** "when Marcie was with us"

**Behavior:**
- Extract "Marcie" as character entity
- Note context: dialogue mention, past tense
- Infer facts: "Was previously with the group", "No longer with group (implied)"
- Mark as "lightly mentioned" character (limited information)
- Entity still appears in Story Bible with available information

---

### Edge Case 3: Indirect Narrative Mentions
**Scenario:** Character mentioned in passing during narrative

**Example:** "There was the time Josie fell out of a tree"

**Behavior:**
- Extract "Josie" as character entity
- Note context: past event narration, internal thought
- Infer facts: "Known to narrator", "Experienced tree-falling incident"
- Mark as "lightly mentioned" character
- Entity appears in Story Bible

---

### Edge Case 4: Titles and Honorifics
**Scenario:** Character name includes title

**Examples:**
- "Miss Rosie"
- "Dr. Smith"
- "Captain Jones"
- "the manipulator" (role-as-title)

**Behavior:**
- Preserve full form: "Miss Rosie" as entity name (NOT "Rosie")
- Extract title separately for metadata: {name: "Rosie", title: "Miss"}
- Role-titles: "the manipulator" → Extract as character if it refers to specific person (Terence)
- Generic roles: "a guard" → Skip unless they recur or are named

---

### Edge Case 5: Pronouns and Antecedents
**Scenario:** Pronoun refers to previously named entity

**Example:** "Miss Rosie's famous beef stew. She made it every Sunday."

**Behavior:**
- "She" → Resolve to "Miss Rosie" (antecedent tracking)
- Both sentences contribute facts about Miss Rosie
- Don't extract "she" as separate entity
- Track pronoun chains across sentences

---

### Edge Case 6: Generic vs Specific References
**Scenario:** Generic description vs specific named instance

**Examples:**
- "a lantern" (generic) vs "the lantern" (specific)
- "a guard" (generic) vs "Guard Thomlin" (named)
- "the woman" (generic) vs "Danita" (named)

**Behavior:**
- Named instances: Always extract
- "The [noun]": Extract if it's THE specific instance (unique item)
- "A [noun]": Generally skip unless it becomes significant later
- Recurring generic: "the woman" appears multiple times → Extract as unnamed character, note as "unnamed woman"

---

### Edge Case 7: Dual-Type Entities
**Scenario:** Entity functions as multiple types

**Example:** "Academy" = location (building) + organization (institution)

**Behavior:**
- Mark entity with multiple types: {type: ["location", "organization"]}
- Extract facts appropriate to each type:
  - As location: "Is a building", "Has rooms/areas"
  - As organization: "Teaches magic", "Has students"
- Story Bible shows entity under both categories (or merged with dual type)

---

### Edge Case 8: Group Membership via Pronouns
**Scenario:** "We" or "us" implies group membership

**Example:** "when Marcie was with us"

**Behavior:**
- "us" → Resolve to current group (Terence, Danita, Kian)
- Infer: Marcie was formerly in this group
- Extract group as organization entity: "Terence's group" (or unnamed group)
- Track membership: Current = [Terence, Danita, Kian], Former = [Marcie]

---

### Edge Case 9: Same Entity, Different Mentions
**Scenario:** Entity appears in multiple passages with different contexts

**Example:** Marcie mentioned 4 times across different passages

**Behavior:**
- Single entity entry for "Marcie"
- ALL mentions aggregated under one entity:
  - Mention 1: "when Marcie was with us" (KEB-251101.twee)
  - Mention 2: "since we lost Marcie" (mansel-20251114.twee)
  - Mention 3: "even when Marcie was with us" (KEB-251108.twee)
  - Mention 4: "since we had Marcie" (KEB-251108.twee)
- Facts inferred from all mentions combined:
  - "Was member of group"
  - "No longer with group (lost/left)"
  - "Group's workings were stronger with Marcie"

---

### Edge Case 10: Entity First Mentioned as Possessive
**Scenario:** First appearance of entity is possessive, later appears normally

**Example:**
- First: "Miss Rosie's beef stew"
- Later: "Miss Rosie welcomed them"

**Behavior:**
- Extract "Miss Rosie" on first possessive mention
- Subsequent normal mentions add to same entity
- Don't create duplicate "Rosie" vs "Miss Rosie" entities
- Normalization catches variations

---

### Edge Case 11: Items Named After People
**Scenario:** Item name includes person's name

**Example:** "Miss Rosie's famous beef stew"

**Behavior:**
- Extract TWO entities:
  - Character: "Miss Rosie"
  - Item: "beef stew"
- Create relationship: beef stew associated with/made by Miss Rosie
- Attribute "famous" applies to beef stew (item quality)
- Both entities appear in Story Bible with relationship noted

---

### Edge Case 12: Entity Mentioned in Internal Thought
**Scenario:** Character mentioned in narrator's internal thoughts

**Example:** "There was the time Josie fell out of a tree"

**Behavior:**
- Extract "Josie" as character entity
- Note context: internal thought/memory, past event
- Infer: Josie known to narrator (Javlyn in this case)
- Mark mention type: memory/internal thought
- Entity appears in Story Bible

---

### Edge Case 13: Overlapping Entity Names
**Scenario:** Multiple entities with similar names or shared words

**Examples:**
- "Rosie" vs "Miss Rosie"
- "the village" (organization) vs "village" (location)
- "Academy" (building) vs "the Academy" (institution)

**Behavior:**
- Title-based: "Miss Rosie" is canonical, "Rosie" is variant (merge)
- Context-based: "the village" analyzed per usage (location vs organization)
- Normalization handles "Academy" and "the Academy" as same entity
- Preserve full form in Story Bible, note variants in metadata

---

## Acceptance Criteria

### Entity Extraction
- [ ] AI extracts ALL named entities from passages (characters, locations, items, organizations, concepts)
- [ ] Entities mentioned only in dialogue are captured ("when Marcie was with us")
- [ ] Entities in possessive form are captured ("Miss Rosie's beef stew" → Extract "Miss Rosie")
- [ ] Entities in indirect references are captured ("Josie fell out of a tree" → Extract "Josie")
- [ ] Titles preserved in entity names ("Miss Rosie", not "Rosie")
- [ ] Possessives normalized ("Rosie's" → "Rosie")
- [ ] Case-insensitive matching ("Marcie" = "marcie")
- [ ] Every entity type extracted: characters, locations, items, organizations, concepts

### Entity Context
- [ ] Each entity shows ALL passages where it's mentioned
- [ ] Each mention includes context type (dialogue, narrative, possessive, internal thought)
- [ ] Each mention includes quote from passage
- [ ] Relationships between entities captured (Rosie associated with beef stew)
- [ ] Pronouns resolved to named entities where possible
- [ ] Group membership inferred from "we"/"us" pronouns in context

### Entity Facts
- [ ] Facts associated with each entity (even if minimal)
- [ ] Minimal information acceptable ("Marcie was former group member" is valid)
- [ ] Entities appear even if only mentioned once
- [ ] No entity excluded due to "insufficient information"
- [ ] Facts distinguish between constants (identity) and variables (outcomes)

### Story Bible Display
- [ ] Story Bible lists ALL entities in organized categories
- [ ] Characters section includes ALL named characters (even lightly mentioned)
- [ ] Locations section includes ALL named locations
- [ ] Items section includes ALL named items
- [ ] Each entity shows mention count and contexts
- [ ] "Lightly mentioned" entities clearly marked (vs "fully developed")
- [ ] Relationships between entities displayed (Rosie → beef stew)

### Success Metrics
- [ ] 100% entity detection: All 15 known characters extracted (including Marcie, Miss Rosie, Josie)
- [ ] Zero false negatives (no missed entities)
- [ ] Acceptable false positives (generic "the woman" extracted if recurring)
- [ ] All possessive mentions captured (no "Miss Rosie" skipped)
- [ ] All dialogue mentions captured (no "when Marcie was with us" skipped)

### Test Cases
- [ ] **Test 1:** Extract from "when Marcie was with us" → Entity: Marcie (character)
- [ ] **Test 2:** Extract from "Miss Rosie's famous beef stew" → Entities: Miss Rosie (character), beef stew (item)
- [ ] **Test 3:** Extract from "Josie fell out of a tree" → Entity: Josie (character)
- [ ] **Test 4:** Extract from "the manipulator" (referring to Terence) → Entity: Terence (character, role: manipulator)
- [ ] **Test 5:** Aggregate 4 Marcie mentions → Single entity with 4 mention records
- [ ] **Test 6:** Normalize "Rosie's" to "Miss Rosie" (preserve title, strip possessive)

---

## Success Metrics

**Primary Metrics:**
- **100% entity detection:** All named entities in story extracted (including Marcie, Miss Rosie, Josie)
- **Zero missed dialogue mentions:** All characters mentioned in dialogue appear in Story Bible
- **Zero missed possessive mentions:** All possessive references captured
- **Complete entity census:** Story Bible provides comprehensive list of all named things

**Secondary Metrics:**
- Entity type accuracy: >95% correctly categorized
- Normalization accuracy: >98% (titles preserved, possessives stripped correctly)
- Relationship detection: Significant relationships captured (Rosie → beef stew)
- Context capture: >90% of mentions include context type and quote

**Qualitative Indicators:**
- Writers trust Story Bible as complete entity registry
- No surprises when searching for character ("Why isn't Marcie in here?")
- New collaborators get full picture of who/what exists in story
- AI validation can reference complete entity set

---

## Risk Considerations

### Risk 1: Over-Extraction (Too Many Generic Entities)
**Impact:** Medium - Story Bible cluttered with "the woman", "a guard", etc.

**Mitigation:**
- Extract generic references only if recurring or plot-significant
- Mark generic entities clearly ("unnamed woman")
- Filter out one-off generic mentions ("a guard" mentioned once)
- Focus on NAMED entities primarily

**Monitoring:** Track ratio of named vs generic entities, adjust extraction rules

---

### Risk 2: Missed Entities Despite Noun-First Approach
**Impact:** High - Defeats purpose of 100% detection

**Mitigation:**
- Comprehensive extraction prompt with examples
- Test against known missed entities (Marcie, Miss Rosie, Josie)
- Iterative prompt refinement based on missed entities
- Manual audit of sample passages for missed entities

**Monitoring:** Track missed entity reports from writers, run periodic audits

---

### Risk 3: Entity Deduplication Errors
**Impact:** Medium - Same entity appears multiple times with variations

**Mitigation:**
- Strong normalization rules (case-insensitive, possessive-stripped)
- Title preservation logic ("Miss Rosie" = canonical form)
- Variant tracking (Rosie, Miss Rosie → Same entity)
- Manual review of entity list for duplicates

**Monitoring:** Track duplicate entity reports, refine normalization

---

### Risk 4: Complex Pronoun Resolution
**Impact:** Low - Pronouns not always resolvable to named entities

**Mitigation:**
- Best-effort pronoun resolution (track antecedents where clear)
- Accept limitation: Some pronouns won't resolve
- Focus on named entities primarily (pronouns are secondary)
- Mark unresolved pronouns as "ambiguous reference"

**Monitoring:** Track pronoun resolution accuracy on sample passages

---

## Related Documents

**Parent Feature:**
- [Story Bible PRD](story-bible.md) - Overall Story Bible feature design

**Strategic:**
- [VISION.md](/home/ubuntu/Code/NaNoWriMo2025/VISION.md) - Project vision
- [ROADMAP.md](/home/ubuntu/Code/NaNoWriMo2025/ROADMAP.md) - Product roadmap

**Technical Context:**
- [architecture/010-story-bible-design.md] - Technical design (to be updated by Architect)

---

## What Changed from Current Approach

**Current Fact-First Approach:**
- Extract declarative facts ("Javlyn is a student")
- Miss entities only mentioned in passing
- Found 12/15 characters

**New Entity-First Approach:**
- **STEP 1:** Extract ALL named entities (100% detection goal)
- **STEP 2:** Associate facts with those entities
- Captures dialogue mentions, possessives, indirect references
- Target: 15/15 characters (100%)

**Key Differences:**

| Aspect | Fact-First (Old) | Entity-First (New) |
|--------|------------------|-------------------|
| Primary Goal | Extract facts | Extract entities |
| Dialogue Mentions | Often missed | Always captured |
| Possessive References | Often missed | Always captured |
| One-off Mentions | Often missed | Always captured |
| Minimal Info Entities | Excluded | Included |
| Success Metric | Fact coverage | 100% entity detection |

---

## Next Steps

**Immediate (Product Manager):**
- [x] Document PRD (this document)
- [ ] Review with CEO for strategic alignment
- [ ] Get Developer to update extraction logic

**After Approval (Architect):**
- [ ] Review current Story Bible extraction architecture
- [ ] Design entity-first extraction pipeline
- [ ] Update AI prompt templates for entity-first approach
- [ ] Define entity schema and normalization rules
- [ ] Document architecture changes

**After Design (Developer):**
- [ ] Update extraction logic to entity-first approach
- [ ] Implement entity normalization (title preservation, possessive stripping)
- [ ] Update AI prompts with entity-first instructions
- [ ] Test against known missed entities (Marcie, Miss Rosie, Josie)
- [ ] Run full extraction on current story
- [ ] Verify 100% entity detection (15/15 characters)
- [ ] Update Story Bible HTML to show entities clearly
- [ ] Update Story Bible JSON schema for entity-first structure

---

**End of PRD**
