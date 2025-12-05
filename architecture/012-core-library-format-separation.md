# ADR-012: Core Library and Format Separation Architecture

## Status

Accepted

## Context

The project initially grew with feature-specific implementations tightly coupled to output formats:
- AllPaths generator parsed HTML and generated its own custom format
- Story Bible (planned) would need similar parsing and format generation
- Writing Metrics would need to parse Twee files independently
- Each format reimplemented core functionality (parsing, graph construction, passage extraction)

**Pain Points**:

1. **Duplication**: Each format reimplements story structure parsing
2. **Feature Coupling**: Formats depend on each other's outputs (Story Bible HTML → extract from AllPaths)
3. **Unclear Pipeline Boundaries**: What runs in CI vs webhook vs local dev?
4. **Constraint Confusion**: Which tools can use Ollama? Which must be deterministic?
5. **Maintenance Burden**: Changes to story structure require updates across multiple formats
6. **Testing Difficulty**: Can't test parsing logic independently of output generation

**Example Problems**:

- Story Bible needed to extract from AllPaths HTML because AllPaths had the only passage→file mapping
- Writing Metrics would need to duplicate Twee parsing logic
- No clear answer: "Can I use Ollama in this tool?" → depends on where it runs
- Adding a new format requires duplicating graph construction code

**Constraint Categories Are Unclear**:

Without explicit categories, developers must guess:
- "Can this run in CI?" → Maybe, if it's deterministic and doesn't need Ollama
- "Does this block merges?" → Depends on whether CI runs it
- "Where does this fit?" → Unclear without a framework

We needed an architecture that:
1. **Eliminates duplication**: Shared core library for common operations
2. **Separates concerns**: Core artifacts vs presentation formats
3. **Clarifies constraints**: Explicit pipeline categories based on what tools can do
4. **Enables reuse**: Formats consume shared artifacts, don't depend on each other
5. **Simplifies testing**: Test core logic independently of presentation

## Decision

We decided to implement a **Core Library + Format Separation** architecture with **Constraint-Based Pipeline Categories**.

### Architecture Principles

**1. Core Library Produces Shared Artifacts**

A core library (`lib/`) produces JSON artifacts from Tweego HTML:
- Parses story structure once
- Generates reusable artifacts
- No presentation logic (HTML, text formatting)
- Pure data transformation

**2. Formats Consume Core Artifacts**

Presentation formats (`formats/`) consume core artifacts and produce presentation:
- AllPaths: story_graph.json → allpaths.html
- Story Bible: passages_deduplicated.json → story-bible.html + cache
- Writing Metrics: story_graph.json → metrics.html
- Future formats: consume same artifacts

**3. Formats Must Not Depend on Each Other**

Critical constraint: Formats are independent
- ✗ Story Bible cannot depend on AllPaths HTML
- ✓ Story Bible consumes shared core artifacts
- ✗ Writing Metrics cannot parse AllPaths output
- ✓ Writing Metrics consumes story_graph.json

This prevents coupling and enables parallel development.

### Core Artifacts

**story_graph.json** - Complete story structure
```json
{
  "passages": {
    "Start": {
      "id": "1",
      "name": "Start",
      "tags": [],
      "content": "Welcome to the story...",
      "links": ["Continue", "End"]
    }
  },
  "start_passage": "Start",
  "metadata": {
    "title": "Story Title",
    "ifid": "...",
    "format": "Harlowe",
    "format_version": "3.3.9"
  }
}
```

**passage_mapping.json** - Name ↔ ID ↔ File mapping
```json
{
  "by_name": {
    "Start": {
      "id": "1",
      "file": "src/Start.twee",
      "line": 1
    }
  },
  "by_id": {
    "1": {
      "name": "Start",
      "file": "src/Start.twee",
      "line": 1
    }
  },
  "by_file": {
    "src/Start.twee": [
      {"name": "Start", "id": "1", "line": 1}
    ]
  }
}
```

**passages_deduplicated.json** - Flat passage map for extraction
```json
{
  "passages": [
    {
      "name": "Start",
      "id": "1",
      "file": "src/Start.twee",
      "line": 1,
      "content": "Welcome to the story...",
      "content_hash": "abc123...",
      "tags": []
    }
  ]
}
```

These artifacts serve different use cases:
- **story_graph.json**: Graph traversal, path enumeration
- **passage_mapping.json**: Fast lookups, git integration
- **passages_deduplicated.json**: Content extraction, AI processing

### Constraint-Based Pipeline Categories

We categorize tools by their **constraints** (what they can/can't do), not by feature:

| Category | Constraint | Examples | Runs Where |
|----------|------------|----------|------------|
| **CI Build** | No Ollama, must be deterministic, fast | Linting, Tweego, AllPaths, Metrics, Story Bible render | GitHub Actions |
| **Webhook AI** | Has Ollama, async/advisory, can be slow | AI continuity checking, Story Bible extraction | Webhook service |
| **Local Dev** | Full access, no constraints | Developer debugging, ad-hoc analysis | Local machine |

**Decision Framework**:

When adding new functionality, ask:

1. **Does it require Ollama?**
   - YES → Webhook only (CI Build can't run it)
   - NO → Could be CI Build or Webhook

2. **Should it block merge?**
   - YES → Must be in CI Build + gating check
   - NO → Webhook (advisory feedback)

3. **What data does it need?**
   - Core artifacts → Runs after core library
   - Format-specific data → Runs after that format
   - External data (git, Ollama) → Depends on availability

**Examples**:

- **Twee Linter**: No Ollama, deterministic, blocks merge → CI Build (gating)
- **AllPaths Generator**: No Ollama, deterministic, informational → CI Build (non-gating)
- **Story Bible Render**: No Ollama, deterministic, uses cache → CI Build (fast path)
- **Story Bible Extract**: Needs Ollama, async, updates cache → Webhook (AI phase)
- **AI Continuity Check**: Needs Ollama, advisory feedback → Webhook (non-gating)
- **Debug Script**: Full access, ad-hoc → Local Dev

### Story Bible Two-Phase Model

Story Bible demonstrates this architecture:

**Render Phase** (CI Build):
```
Cache (validated_nouns.json)
  → Jinja2 template
    → story-bible.html (deterministic, fast)
```

**Extract Phase** (Webhook):
```
passages_deduplicated.json
  → Ollama (extract nouns)
    → Cache (validated_nouns.json)
```

Key insights:
- Extraction is **asynchronous**: Updates cache for future builds
- Rendering is **synchronous**: Always succeeds, uses best available cache
- Manual review updates cache directly (no Ollama needed)
- Cache changes trigger re-render on next build

## File Structure

```
NaNoWriMo2025/
├── lib/                              # Core library (NEW)
│   ├── core/
│   │   ├── parse_story.py           # Tweego HTML → story_graph.json
│   │   ├── extract_passages.py      # story_graph.json → passages_deduplicated.json
│   │   └── build_mappings.py        # story_graph.json → passage_mapping.json
│   ├── artifacts/                   # Output location (gitignored, except cache)
│   │   ├── story_graph.json
│   │   ├── passage_mapping.json
│   │   ├── passages_deduplicated.json
│   │   └── cache/                   # Persistent cache (committed)
│   │       └── validated_nouns.json
│   └── schemas/                     # JSON schemas for validation
│       ├── story_graph.schema.json
│       ├── passage_mapping.schema.json
│       └── passages_deduplicated.schema.json
├── formats/                          # Presentation formats (existing)
│   ├── allpaths/
│   │   └── generator.py             # story_graph.json → allpaths.html
│   ├── metrics/
│   │   └── generator.py             # story_graph.json → metrics.html
│   └── story-bible/                 # Story Bible format (NEW)
│       ├── render.py                # cache → story-bible.html (CI Build)
│       ├── extract.py               # passages_deduplicated.json → cache (Webhook)
│       └── templates/
│           └── story-bible.html.jinja2
├── scripts/                          # Build orchestration
│   ├── build-core.sh                # Generate core artifacts (NEW)
│   ├── build-allpaths.sh           # AllPaths format (updated to use artifacts)
│   ├── build-metrics.sh            # Metrics format
│   └── build-story-bible.sh        # Story Bible format (NEW)
├── .github/workflows/
│   └── build-and-deploy.yml        # CI Build category
└── webhook/
    └── services/
        ├── continuity_check.py      # Webhook AI category
        └── story_bible_extract.py   # Webhook AI category (NEW)
```

## Consequences

### Positive

1. **No Duplication**: Core parsing logic written once, reused everywhere
2. **Independent Formats**: Formats can be developed in parallel without coupling
3. **Clear Constraints**: Explicit categories prevent "can I use Ollama here?" confusion
4. **Testability**: Test core library independently of presentation
5. **Reusability**: New formats consume existing artifacts without reimplementation
6. **Maintainability**: Changes to story structure centralized in core library
7. **Flexibility**: Formats choose which artifacts they need
8. **Async-by-Default for AI**: AI work naturally falls into Webhook category
9. **Fast CI Builds**: Ollama work doesn't block CI, render phases are deterministic
10. **Graceful Degradation**: Story Bible renders with stale cache if extraction fails

### Negative

1. **More Complexity**: Additional layer (core library) to understand
2. **Coordination Overhead**: Core artifact schema changes affect multiple formats
3. **Disk I/O**: Writing/reading intermediate JSON files adds overhead (~1-2 seconds)
4. **Initial Migration**: Existing code must be refactored to use artifacts
5. **Cache Management**: Story Bible cache must be committed and managed
6. **Learning Curve**: Developers must understand constraint categories

### Trade-offs

**Shared Artifacts vs. Direct Parsing**:
- **Chose shared artifacts** to eliminate duplication
- **Trade-off**: Extra I/O overhead (~1-2 seconds)
- **Rationale**: Maintainability worth the small performance cost

**Constraint Categories vs. Ad-Hoc Placement**:
- **Chose explicit categories** based on constraints
- **Trade-off**: More rigid structure
- **Rationale**: Clarity prevents confusion about where tools run

**Two-Phase Story Bible vs. Single Phase**:
- **Chose two phases** (render in CI, extract in webhook)
- **Trade-off**: More complex than all-in-one
- **Rationale**: Enables fast deterministic CI builds while still getting AI benefits

**Format Independence vs. Format Reuse**:
- **Chose independence** (formats consume core artifacts only)
- **Trade-off**: Can't directly reuse format-specific outputs
- **Rationale**: Prevents coupling, enables parallel development

## Alternatives Considered

### 1. Monolithic Generator Per Format

**Approach**: Each format implements its own complete pipeline (current state)

**Rejected because**:
- Duplicates parsing logic across formats
- Changes require updates to multiple generators
- Can't reuse logic between formats
- Leads to inconsistencies in story structure handling

### 2. Format Layering (Formats Depend on Formats)

**Approach**: Story Bible depends on AllPaths HTML, Metrics depend on Story Bible output

**Rejected because**:
- Creates coupling between formats
- Changes to one format break dependent formats
- Forces sequential execution (can't parallelize)
- Unclear ownership boundaries
- Hard to test formats in isolation

### 3. Single Unified Generator

**Approach**: One giant generator produces all outputs

**Rejected because**:
- Becomes monolithic and hard to maintain
- All-or-nothing: can't generate just one format
- Mixing unrelated concerns (paths vs metrics vs story bible)
- Changes to one output affect all others

### 4. No Constraint Categories (Ad-Hoc)

**Approach**: Decide where each tool runs on case-by-case basis

**Rejected because**:
- Leads to confusion: "Can I use Ollama in CI?"
- Inconsistent decisions across tools
- No framework for evaluating new functionality
- Documentation burden (explain each decision individually)

### 5. Three Categories Instead of Three

**Approach**: Collapse Webhook AI and Local Dev into single "Non-CI" category

**Rejected because**:
- Webhook has specific constraints (async, advisory)
- Local Dev is truly unconstrained (debugging)
- Three categories map to three runtime environments
- Framework still clear with three categories

### 6. Build-Time AI (Ollama in CI)

**Approach**: Run Ollama in GitHub Actions

**Rejected because**:
- Slow: Ollama adds 30-60 seconds per analysis
- Non-deterministic: AI output varies run-to-run
- Resource-heavy: CI runners may not have sufficient GPU/memory
- Blocks merge: Forces wait for AI analysis
- Cost: Burns CI minutes on expensive operations

## Implementation Details

### Core Library API

**parse_story.py**:
```python
def parse_story(tweego_html_path: Path) -> Dict:
    """
    Parse Tweego HTML output into story graph structure.

    Args:
        tweego_html_path: Path to Tweego-generated HTML (paperthin format)

    Returns:
        Dict conforming to story_graph.schema.json

    Raises:
        ParseError: If HTML structure invalid
        ValidationError: If output doesn't match schema
    """
```

**extract_passages.py**:
```python
def extract_passages(story_graph: Dict) -> Dict:
    """
    Extract flat list of deduplicated passages.

    Args:
        story_graph: Dict from parse_story()

    Returns:
        Dict conforming to passages_deduplicated.schema.json
    """
```

**build_mappings.py**:
```python
def build_mappings(story_graph: Dict) -> Dict:
    """
    Build passage name/ID/file mappings.

    Args:
        story_graph: Dict from parse_story()

    Returns:
        Dict conforming to passage_mapping.schema.json
    """
```

### Build Script Integration

**scripts/build-core.sh**:
```bash
#!/bin/bash
# Generate core artifacts from Tweego HTML

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

**Updated build flow**:
```bash
# npm run build
npm run build:core         # Generate core artifacts
npm run build:main         # Harlowe HTML
npm run build:proofread    # Paperthin HTML (also used by core)
npm run build:allpaths     # Uses story_graph.json
npm run build:metrics      # Uses story_graph.json
npm run build:story-bible  # Uses cache + passages_deduplicated.json
```

### Schema Validation

Each artifact has a JSON schema for validation:

**story_graph.schema.json** (excerpt):
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["passages", "start_passage", "metadata"],
  "properties": {
    "passages": {
      "type": "object",
      "patternProperties": {
        ".*": {
          "type": "object",
          "required": ["id", "name", "content", "links"],
          "properties": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "content": {"type": "string"},
            "links": {"type": "array", "items": {"type": "string"}},
            "tags": {"type": "array", "items": {"type": "string"}}
          }
        }
      }
    }
  }
}
```

Core library functions validate outputs against schemas before writing.

### Migration Path

**Phase 1**: Create core library (current)
- Implement `lib/core/` modules
- Generate core artifacts in CI
- Keep existing generators working

**Phase 2**: Migrate AllPaths (next)
- Update AllPaths to consume `story_graph.json`
- Remove HTML parsing from AllPaths generator
- Validate AllPaths output unchanged

**Phase 3**: Migrate Metrics (next)
- Update Metrics to consume `story_graph.json`
- Remove Twee parsing from Metrics script
- Validate Metrics output unchanged

**Phase 4**: Implement Story Bible (new feature)
- Build render phase using core artifacts
- Build extract phase using core artifacts
- Implement cache management
- Deploy webhook integration

**Phase 5**: Cleanup (polish)
- Remove deprecated parsing code
- Document core library API
- Update ARCHITECTURE.md
- Add tests for core library

## Decision Framework Examples

**Example 1: Add Passage Similarity Check**

Q: Does it require Ollama?
A: Yes (uses embeddings for similarity)

Q: Should it block merge?
A: No (advisory, not correctness)

→ **Webhook AI category** (async, advisory feedback)

**Example 2: Add CSS Linter**

Q: Does it require Ollama?
A: No (static analysis)

Q: Should it block merge?
A: Yes (enforce standards)

→ **CI Build category** (deterministic, gating)

**Example 3: Add Dead Passage Detector**

Q: Does it require Ollama?
A: No (graph traversal)

Q: Should it block merge?
A: Maybe (policy decision)

→ **CI Build category** (gating or non-gating based on policy)

**Example 4: Add Interactive Debugger**

Q: Does it require Ollama?
A: No

Q: Should it block merge?
A: No (developer tool)

Q: Needs full access?
A: Yes (inspect state, modify files)

→ **Local Dev category** (troubleshooting only)

## Success Criteria

This architecture is successful if:

1. ✅ Core artifacts generated successfully in CI
2. ✅ AllPaths consumes core artifacts (no HTML parsing)
3. ✅ Metrics consumes core artifacts (no Twee parsing)
4. ✅ Story Bible implements two-phase model
5. ✅ No format depends on another format's output
6. ✅ Clear answer to "where does this tool run?"
7. ✅ CI builds remain < 2 minutes (artifact overhead < 5 seconds)
8. ✅ Developers understand constraint categories
9. ✅ New formats trivial to add (consume existing artifacts)
10. ✅ Changes to story structure handled in one place (core library)

## Performance Considerations

**Core Artifact Generation**:
- Parse story: ~1 second (Tweego already generated HTML)
- Extract passages: <0.5 seconds (iterate story graph)
- Build mappings: <0.5 seconds (iterate story graph)
- **Total overhead**: ~2 seconds

**Disk I/O**:
- Write 3 JSON files: ~0.5 seconds
- Read by formats: ~0.5 seconds
- **Total I/O**: ~1 second

**Overall Impact**: +3 seconds to CI build (acceptable for maintainability gain)

**Optimization Opportunities** (if needed):
- Cache core artifacts (invalidate on source changes)
- Generate artifacts in parallel
- Stream JSON instead of loading into memory
- Compress JSON files (trade I/O for CPU)

## Future Considerations

Enhancements enabled by this architecture:

1. **Incremental Builds**: Only regenerate artifacts if source changed
2. **Format Plugins**: Third-party formats consume core artifacts
3. **Artifact Caching**: Cache artifacts between CI runs
4. **Multi-Language Support**: Core library in Python, formats in any language
5. **Artifact Versioning**: Schema evolution with backward compatibility
6. **Parallel Format Generation**: Formats run concurrently (no dependencies)
7. **Alternative Parsers**: Swap core library implementation without breaking formats
8. **Artifact Distribution**: Share artifacts via API or CDN

## Related Work

**Related ADRs**:
- ADR-001: AllPaths Format - Will be refactored to consume core artifacts
- ADR-002: Validation Cache - Cache pattern used for Story Bible
- ADR-008: AllPaths Processing Pipeline - Core library extracts reusable stages
- ADR-010: Story Bible Design - Implements two-phase model using this architecture

**New Patterns**:
- Constraint-based categorization (CI vs Webhook vs Local)
- Format independence (no inter-format dependencies)
- Two-phase AI model (deterministic render + async extract)

## References

- Core Library: `lib/core/`
- Core Artifacts: `lib/artifacts/`
- Format Generators: `formats/*/`
- Build Scripts: `scripts/build-*.sh`
- CI Workflow: `.github/workflows/build-and-deploy.yml`
- Webhook Service: `webhook/services/`

## Related ADRs

- ADR-001: AllPaths Format for AI Continuity Validation
- ADR-002: Validation Cache Architecture
- ADR-008: AllPaths Processing Pipeline Architecture
- ADR-010: Story Bible Design
