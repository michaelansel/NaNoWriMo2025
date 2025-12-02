# Core Library and Format Separation - Implementation Plan

**Status**: Ready for Implementation
**Date**: 2025-12-02
**Based on**: ADR-012 Core Library and Format Separation Architecture

---

## Overview

This plan implements the Core Library + Format Separation architecture defined in ADR-012. The goal is to eliminate duplication by creating a shared core library that produces JSON artifacts, which presentation formats then consume.

---

## Current State Analysis

### What EXISTS:

1. **AllPaths Generator** (`formats/allpaths/generator.py`):
   - 5-stage pipeline that parses HTML directly
   - Stage 1 parses Tweego HTML into passages dict and story metadata
   - Uses `modules/parser.py` with `parse_story_html()` function

2. **Parser Module** (`formats/allpaths/modules/parser.py`):
   - Has `parse_story()` function that returns story_graph structure
   - Already returns the right format with passages, start_passage, metadata
   - **CANDIDATE FOR EXTRACTION** to core library

3. **Metrics Script** (`scripts/calculate-metrics.py`):
   - Parses Twee files directly using regex
   - Duplicates passage extraction logic
   - Should consume `story_graph.json` instead

4. **Story Bible Generator** (`formats/story-bible/generator.py`):
   - Currently loads from AllPaths data
   - Creates inter-format dependency (BAD)
   - Should consume `passages_deduplicated.json` instead

### What NEEDS to be created:

1. **Core Library** (`lib/core/`):
   - `parse_story.py` - Parse Tweego HTML → `story_graph.json`
   - `extract_passages.py` - Extract passages → `passages_deduplicated.json`
   - `build_mappings.py` - Build mappings → `passage_mapping.json`

2. **JSON Schemas** (`lib/schemas/`):
   - `story_graph.schema.json` - Schema for story_graph.json
   - `passages_deduplicated.schema.json` - Schema for passages_deduplicated.json
   - `passage_mapping.schema.json` - Schema for passage_mapping.json

3. **Build Script** (`scripts/build-core.sh`):
   - Orchestrates core artifact generation

4. **Updated Formats**:
   - Migrate AllPaths to read `story_graph.json`
   - Migrate Metrics to read `story_graph.json`
   - Migrate Story Bible to read `passages_deduplicated.json`

---

## Implementation Tasks

### Phase 1: Core Library Foundation (TDD)

#### Task 1.1: Create `lib/core/parse_story.py`

**Test First (RED)**:
```python
# tests/test_parse_story.py
def test_parse_story_basic():
    """Test parsing basic Tweego HTML."""
    html = """
    <tw-storydata name="Test Story" startnode="1" ifid="ABC-123">
        <tw-passagedata pid="1" name="Start">Welcome to the story.</tw-passagedata>
        <tw-passagedata pid="2" name="Continue">[[Next]]</tw-passagedata>
    </tw-storydata>
    """

    result = parse_story(html)

    assert result['start_passage'] == 'Start'
    assert 'Start' in result['passages']
    assert result['passages']['Start']['content'] == 'Welcome to the story.'
    assert result['passages']['Start']['links'] == []
    assert result['metadata']['story_title'] == 'Test Story'
```

**Implementation (GREEN)**:
- Extract `parse_story()` from `formats/allpaths/modules/parser.py`
- Move to `lib/core/parse_story.py`
- Add CLI interface for command-line usage
- Add schema validation

**Refactor**:
- Ensure clean separation of concerns
- Add comprehensive docstrings
- Handle edge cases

**Files to Create/Modify**:
- `lib/core/parse_story.py` (new)
- `lib/core/__init__.py` (new)
- `tests/test_parse_story.py` (new)

---

#### Task 1.2: Create `lib/core/extract_passages.py`

**Test First (RED)**:
```python
# tests/test_extract_passages.py
def test_extract_passages_basic():
    """Test extracting flat passage list from story graph."""
    story_graph = {
        'passages': {
            'Start': {'content': 'Welcome', 'links': ['Next']},
            'Next': {'content': 'The end', 'links': []}
        },
        'start_passage': 'Start',
        'metadata': {'story_title': 'Test'}
    }

    result = extract_passages(story_graph)

    assert len(result['passages']) == 2
    assert result['passages'][0]['name'] == 'Start'
    assert result['passages'][0]['content'] == 'Welcome'
    assert 'content_hash' in result['passages'][0]
```

**Implementation (GREEN)**:
- Create function to iterate story_graph and extract passages
- Calculate content_hash for each passage (for deduplication)
- Add file/line metadata (will come from separate mapping)
- Return flat list format

**Refactor**:
- Optimize hash calculation
- Add comprehensive docstrings
- Handle special passages (StoryData, StoryTitle)

**Files to Create/Modify**:
- `lib/core/extract_passages.py` (new)
- `tests/test_extract_passages.py` (new)

---

#### Task 1.3: Create `lib/core/build_mappings.py`

**Test First (RED)**:
```python
# tests/test_build_mappings.py
def test_build_mappings_basic():
    """Test building passage name/ID/file mappings."""
    story_graph = {
        'passages': {
            'Start': {'content': 'Welcome', 'links': []},
            'Next': {'content': 'End', 'links': []}
        },
        'start_passage': 'Start',
        'metadata': {}
    }

    result = build_mappings(story_graph)

    assert 'by_name' in result
    assert 'by_id' in result
    assert 'by_file' in result
    assert 'Start' in result['by_name']
```

**Implementation (GREEN)**:
- Parse Twee source files to map passages to files
- Build name→ID, ID→name, file→passages mappings
- Handle passages without file mapping gracefully

**Refactor**:
- Optimize file parsing
- Add comprehensive docstrings
- Handle edge cases (missing files, duplicate names)

**Files to Create/Modify**:
- `lib/core/build_mappings.py` (new)
- `tests/test_build_mappings.py` (new)

---

#### Task 1.4: Create JSON Schemas

**Test First (RED)**:
```python
# tests/test_schemas.py
def test_story_graph_schema_valid():
    """Test story_graph.json validates against schema."""
    story_graph = {...}  # Valid story graph

    validate(story_graph, schema=load_schema('story_graph.schema.json'))
    # Should not raise ValidationError
```

**Implementation (GREEN)**:
- Create `story_graph.schema.json` based on ADR-012 spec
- Create `passages_deduplicated.schema.json`
- Create `passage_mapping.schema.json`
- Add validation functions

**Refactor**:
- Ensure schemas are complete and correct
- Add comments/descriptions in schemas
- Test edge cases

**Files to Create/Modify**:
- `lib/schemas/story_graph.schema.json` (new)
- `lib/schemas/passages_deduplicated.schema.json` (new)
- `lib/schemas/passage_mapping.schema.json` (new)
- `lib/core/validation.py` (new - helper functions)
- `tests/test_schemas.py` (new)

---

### Phase 2: Build Integration

#### Task 2.1: Create `scripts/build-core.sh`

**Test First (RED)**:
```bash
# Manual test procedure
# 1. Run build-core.sh
# 2. Verify artifacts exist:
#    - lib/artifacts/story_graph.json
#    - lib/artifacts/passages_deduplicated.json
#    - lib/artifacts/passage_mapping.json
# 3. Verify artifacts validate against schemas
```

**Implementation (GREEN)**:
```bash
#!/bin/bash
set -e

echo "=== Building Core Artifacts ==="

# Generate paperthin HTML for parsing
tweego src -o dist/story-paperthin.html --format=paperthin-1.0.0

# Parse story structure
python3 lib/core/parse_story.py \
  dist/story-paperthin.html \
  lib/artifacts/story_graph.json

# Generate secondary artifacts
python3 lib/core/extract_passages.py \
  lib/artifacts/story_graph.json \
  lib/artifacts/passages_deduplicated.json

python3 lib/core/build_mappings.py \
  lib/artifacts/story_graph.json \
  lib/artifacts/passage_mapping.json

echo "✓ Core artifacts generated"
```

**Refactor**:
- Add error handling
- Add progress messages
- Add artifact validation step
- Make script idempotent

**Files to Create/Modify**:
- `scripts/build-core.sh` (new)
- `lib/artifacts/.gitignore` (new - ignore generated artifacts except cache)

---

#### Task 2.2: Update `package.json` Build Scripts

**Test First (RED)**:
```bash
# Manual test
# 1. Run: npm run build:core
# 2. Verify artifacts generated
# 3. Run: npm run build
# 4. Verify all formats generated
```

**Implementation (GREEN)**:
```json
{
  "scripts": {
    "build:core": "bash scripts/build-core.sh",
    "build:main": "tweego src -o dist/index.html",
    "build:proofread": "tweego src -o dist/paperthin.html --format=paperthin-1.0.0",
    "build:allpaths": "bash scripts/build-allpaths.sh",
    "build:metrics": "bash scripts/build-metrics.sh",
    "build:story-bible": "bash scripts/build-story-bible.sh",
    "build": "npm run build:core && npm run build:main && npm run build:proofread && npm run build:allpaths && npm run build:metrics && npm run build:story-bible"
  }
}
```

**Refactor**:
- Ensure proper ordering (core must run first)
- Add error handling (exit on failure)
- Document build process

**Files to Create/Modify**:
- `package.json` (modify)

---

### Phase 3: Migrate AllPaths (TDD)

#### Task 3.1: Update AllPaths to Read `story_graph.json`

**Test First (RED)**:
```python
# Test that AllPaths can read story_graph.json
def test_allpaths_reads_story_graph():
    """Test AllPaths generator reads story_graph.json instead of HTML."""
    # Given: story_graph.json exists
    # When: AllPaths generator runs
    # Then: It reads story_graph.json, not HTML
    # Then: Same output as before (backward compatibility)
```

**Implementation (GREEN)**:
- Modify `formats/allpaths/generator.py` Stage 1
- Replace HTML parsing with JSON loading
- Read from `lib/artifacts/story_graph.json`
- Keep stages 2-5 unchanged

**Changes**:
```python
# OLD (Stage 1):
story_data, passages = parse_story_html(html_content)

# NEW (Stage 1):
with open('lib/artifacts/story_graph.json', 'r') as f:
    story_graph = json.load(f)

passages = story_graph['passages']
start_passage = story_graph['start_passage']
story_data = story_graph['metadata']
```

**Refactor**:
- Remove now-unused HTML parsing code
- Update error handling
- Verify output unchanged

**Files to Create/Modify**:
- `formats/allpaths/generator.py` (modify - Stage 1 only)
- `scripts/build-allpaths.sh` (verify - should work without changes)

---

### Phase 4: Migrate Metrics (TDD)

#### Task 4.1: Update Metrics to Read `story_graph.json`

**Test First (RED)**:
```python
# Test that metrics can read story_graph.json
def test_metrics_reads_story_graph():
    """Test metrics script reads story_graph.json instead of Twee."""
    # Given: story_graph.json exists
    # When: Metrics calculator runs
    # Then: It reads story_graph.json, not Twee files
    # Then: Same metrics as before (backward compatibility)
```

**Implementation (GREEN)**:
- Modify `scripts/calculate-metrics.py`
- Replace Twee parsing with JSON loading
- Read from `lib/artifacts/story_graph.json`
- Keep statistics calculation logic

**Changes**:
```python
# OLD:
twee_files = [TweeFile(f) for f in filtered_files]

# NEW:
with open('lib/artifacts/story_graph.json', 'r') as f:
    story_graph = json.load(f)

# Extract passages from story_graph
passages = [
    {'name': name, 'content': data['content']}
    for name, data in story_graph['passages'].items()
]
```

**Refactor**:
- Remove Twee parsing code
- Simplify word counting (still need to strip Harlowe syntax)
- Verify output unchanged

**Files to Create/Modify**:
- `scripts/calculate-metrics.py` (modify)
- `scripts/build-metrics.sh` (create - new build script)

---

### Phase 5: Migrate Story Bible (TDD)

#### Task 5.1: Update Story Bible to Read `passages_deduplicated.json`

**Test First (RED)**:
```python
# Test that Story Bible reads passages_deduplicated.json
def test_story_bible_reads_passages_deduplicated():
    """Test Story Bible reads passages_deduplicated.json instead of AllPaths."""
    # Given: passages_deduplicated.json exists
    # When: Story Bible generator runs
    # Then: It reads passages_deduplicated.json, not AllPaths
    # Then: Same output as before (backward compatibility)
```

**Implementation (GREEN)**:
- Modify `formats/story-bible/generator.py`
- Replace AllPaths loading with JSON loading
- Read from `lib/artifacts/passages_deduplicated.json`
- Keep rendering logic unchanged

**Changes**:
```python
# OLD:
loaded_data = load_allpaths_data(dist_dir)

# NEW:
with open('lib/artifacts/passages_deduplicated.json', 'r') as f:
    passages_data = json.load(f)
```

**Refactor**:
- Remove AllPaths dependency
- Update error handling
- Verify output unchanged

**Files to Create/Modify**:
- `formats/story-bible/generator.py` (modify)
- `formats/story-bible/modules/loader.py` (modify or remove)

---

### Phase 6: Testing and Validation

#### Task 6.1: Integration Testing

**Test Procedure**:
1. Clean build: `rm -rf dist/ lib/artifacts/`
2. Run: `npm run build`
3. Verify all artifacts generated:
   - `lib/artifacts/story_graph.json`
   - `lib/artifacts/passages_deduplicated.json`
   - `lib/artifacts/passage_mapping.json`
   - `dist/allpaths.html`
   - `dist/metrics.html`
   - `dist/story-bible.html`
4. Verify outputs match previous versions (backward compatibility)
5. Verify no format depends on another format

**Success Criteria**:
- All artifacts generated successfully
- All formats consume core artifacts
- No inter-format dependencies
- Build completes in < 2 minutes
- Core artifact overhead < 5 seconds

---

#### Task 6.2: Performance Testing

**Test Procedure**:
1. Measure build times:
   - Core artifact generation time
   - AllPaths generation time
   - Metrics generation time
   - Story Bible generation time
   - Total build time
2. Compare to baseline (before refactoring)
3. Verify overhead is acceptable (< 5 seconds)

**Performance Targets** (from ADR-012):
- Parse story: ~1 second
- Extract passages: <0.5 seconds
- Build mappings: <0.5 seconds
- Total core overhead: ~2 seconds
- Total build: < 2 minutes

---

### Phase 7: Documentation and Cleanup

#### Task 7.1: Update Documentation

**Files to Update**:
- `README.md` - Update build process section
- `ARCHITECTURE.md` - Document core library architecture
- `formats/allpaths/README.md` - Update to reflect new architecture
- `formats/story-bible/README.md` - Update to reflect new architecture
- Create `lib/README.md` - Document core library usage

**Content**:
- Core library purpose and usage
- Artifact schemas and formats
- Migration guide for new formats
- Build process documentation

---

#### Task 7.2: Clean Up Deprecated Code

**Actions**:
- Remove duplicate parsing code from AllPaths
- Remove Twee parsing from Metrics
- Remove AllPaths dependency from Story Bible
- Archive old implementation notes
- Update comments and docstrings

---

## Task Dependencies

```
Phase 1: Core Library Foundation
├── Task 1.1: parse_story.py
├── Task 1.2: extract_passages.py
├── Task 1.3: build_mappings.py
└── Task 1.4: JSON Schemas
    ↓
Phase 2: Build Integration
├── Task 2.1: build-core.sh (depends on Phase 1)
└── Task 2.2: package.json (depends on Task 2.1)
    ↓
Phase 3: Migrate AllPaths
└── Task 3.1: Update AllPaths (depends on Phase 2)
    ↓
Phase 4: Migrate Metrics
└── Task 4.1: Update Metrics (depends on Phase 2)
    ↓
Phase 5: Migrate Story Bible
└── Task 5.1: Update Story Bible (depends on Phase 2)
    ↓
Phase 6: Testing
├── Task 6.1: Integration Testing (depends on Phases 3-5)
└── Task 6.2: Performance Testing (depends on Task 6.1)
    ↓
Phase 7: Documentation
├── Task 7.1: Update Documentation (depends on Phase 6)
└── Task 7.2: Cleanup (depends on Phase 6)
```

---

## Test Strategy

### Unit Tests
- Each core library function has dedicated tests
- Test both success and failure cases
- Test edge cases (empty story, missing data, malformed input)

### Integration Tests
- Test end-to-end build process
- Verify artifact generation
- Verify format consumption
- Verify backward compatibility

### Performance Tests
- Measure build times at each phase
- Compare to baseline
- Verify overhead is acceptable

### Validation Tests
- Validate artifacts against JSON schemas
- Verify data integrity
- Verify completeness

---

## Success Criteria (from ADR-012)

1. ✅ Core artifacts generated successfully in CI
2. ✅ AllPaths consumes core artifacts (no HTML parsing)
3. ✅ Metrics consumes core artifacts (no Twee parsing)
4. ✅ Story Bible implements two-phase model using core artifacts
5. ✅ No format depends on another format's output
6. ✅ CI builds remain < 2 minutes (artifact overhead < 5 seconds)

---

## Risk Mitigation

### Risk: Breaking existing functionality
**Mitigation**: Test backward compatibility at each phase

### Risk: Performance degradation
**Mitigation**: Measure performance at each step, optimize if needed

### Risk: Schema changes breaking formats
**Mitigation**: Version schemas, document breaking changes

### Risk: Build failures in CI
**Mitigation**: Test locally before pushing, add error handling

---

## Commit Strategy

**Logical Commit Units**:
1. Core library foundation (Phase 1)
2. Build integration (Phase 2)
3. Migrate AllPaths (Phase 3)
4. Migrate Metrics (Phase 4)
5. Migrate Story Bible (Phase 5)
6. Testing and documentation (Phases 6-7)

Each commit should:
- Pass all tests
- Be independently reviewable
- Include clear commit message
- Follow TDD methodology (tests → implementation → refactor)

---

## Implementation Order

1. **Start**: Create core library (Phase 1)
2. **Then**: Build integration (Phase 2)
3. **Then**: Migrate formats in parallel (Phases 3-5)
4. **Then**: Test and validate (Phase 6)
5. **Finally**: Document and cleanup (Phase 7)

---

## Notes

- Follow STANDARDS.md for coding conventions
- Use TDD methodology (Red-Green-Refactor) for all code
- Test backward compatibility at each step
- Commit frequently with clear messages
- Push to branch: `claude/refactor-architecture-implementation-018Z4ew3txN4vWnG4W1pYtZR`

---

**End of Implementation Plan**
