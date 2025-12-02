# Core Library

**Status**: Active
**Version**: 1.0.0

## Overview

The Core Library provides shared functionality for parsing story structure and generating reusable artifacts from Tweego HTML output. It eliminates duplication by parsing the story once and producing JSON artifacts that all presentation formats consume.

## Architecture

Based on **ADR-012: Core Library + Format Separation Architecture**.

```
Tweego HTML
    ↓
Core Library (lib/core/)
    ├─> story_graph.json           (complete story structure)
    ├─> passages_deduplicated.json (flat passage list)
    └─> passage_mapping.json       (name/ID/file mappings)
    ↓
Presentation Formats
    ├─> AllPaths     (reads story_graph.json)
    ├─> Metrics      (reads story_graph.json)
    └─> Story Bible  (reads passages_deduplicated.json)
```

## Modules

### `lib/core/parse_story.py`

Parses Tweego-compiled HTML into `story_graph.json` format.

**Usage:**
```bash
python3 lib/core/parse_story.py input.html output.json
```

**Output Format:** See `lib/schemas/story_graph.schema.json`

**Example:**
```json
{
  "passages": {
    "Start": {
      "content": "Welcome to the story...",
      "links": ["Continue", "End"]
    }
  },
  "start_passage": "Start",
  "metadata": {
    "story_title": "My Story",
    "ifid": "ABC-123",
    "format": "Harlowe",
    "format_version": "3.3.9"
  }
}
```

---

### `lib/core/extract_passages.py`

Extracts flat passage list from `story_graph.json` into `passages_deduplicated.json`.

**Usage:**
```bash
python3 lib/core/extract_passages.py story_graph.json passages_deduplicated.json
```

**Output Format:** See `lib/schemas/passages_deduplicated.schema.json`

**Example:**
```json
{
  "passages": [
    {
      "name": "Start",
      "content": "Welcome to the story...",
      "content_hash": "a1b2c3d4e5f6..."
    }
  ]
}
```

---

### `lib/core/build_mappings.py`

Builds passage name/ID/file mappings from `story_graph.json` and source files.

**Usage:**
```bash
python3 lib/core/build_mappings.py story_graph.json passage_mapping.json --src src/
```

**Output Format:** See `lib/schemas/passage_mapping.schema.json`

**Example:**
```json
{
  "by_name": {
    "Start": {
      "file": "src/Start.twee",
      "line": 1
    }
  },
  "by_id": {},
  "by_file": {
    "src/Start.twee": [
      {"name": "Start", "line": 1}
    ]
  }
}
```

---

## Build Process

### Automated Build

Run the complete build process:

```bash
npm run build
```

This runs:
1. `npm run build:core` - Generate core artifacts
2. `npm run build:main` - Generate Harlowe HTML
3. `npm run build:proofread` - Generate Paperthin HTML
4. `npm run build:allpaths` - Generate AllPaths format
5. `npm run build:metrics` - Generate metrics HTML
6. `npm run build:story-bible` - Generate Story Bible

### Manual Build

Generate core artifacts manually:

```bash
bash scripts/build-core.sh
```

This creates:
- `lib/artifacts/story_graph.json`
- `lib/artifacts/passages_deduplicated.json`
- `lib/artifacts/passage_mapping.json`

---

## Artifacts

### Generated Artifacts

All artifacts are generated in `lib/artifacts/`:

| Artifact | Description | Consumed By |
|----------|-------------|-------------|
| `story_graph.json` | Complete story structure with passages, links, and metadata | AllPaths, Metrics |
| `passages_deduplicated.json` | Flat list of all passages with content hashes | Story Bible |
| `passage_mapping.json` | Bidirectional mapping between passage names, IDs, and source files | Future use |

### Artifact Schemas

All artifacts conform to JSON schemas in `lib/schemas/`:

- `story_graph.schema.json`
- `passages_deduplicated.schema.json`
- `passage_mapping.schema.json`

Use these schemas to validate artifacts or build new format consumers.

---

## Creating New Format Consumers

To create a new presentation format that consumes core artifacts:

1. **Choose artifact(s)** to consume based on needs:
   - Need complete graph structure? → `story_graph.json`
   - Need flat passage list? → `passages_deduplicated.json`
   - Need file/line mappings? → `passage_mapping.json`

2. **Load artifact** in your format generator:
   ```python
   with open('lib/artifacts/story_graph.json', 'r') as f:
       story_graph = json.load(f)
   ```

3. **Validate** against schema (optional but recommended):
   ```python
   from jsonschema import validate
   validate(story_graph, schema=load_schema('story_graph.schema.json'))
   ```

4. **Process and output** your format

5. **Add build script** to `package.json`:
   ```json
   "build:myformat": "./scripts/build-myformat.sh"
   ```

6. **Update main build** to include your format:
   ```json
   "build": "npm run build:core && ... && npm run build:myformat"
   ```

---

## Performance

**Targets** (from ADR-012):
- Parse story: ~1 second
- Extract passages: <0.5 seconds
- Build mappings: <0.5 seconds
- **Total core overhead: ~2 seconds**

Actual performance depends on story size, but the core library adds minimal overhead (<5 seconds) to the overall build process.

---

## Testing

### Unit Tests

Run tests for individual modules:

```bash
python3 tests/test_parse_story.py
python3 tests/test_extract_passages.py
python3 tests/test_build_mappings.py
```

### Integration Tests

Build the complete project and verify artifacts:

```bash
npm run build
ls -lh lib/artifacts/
```

Expected output:
- `story_graph.json`
- `passages_deduplicated.json`
- `passage_mapping.json`

---

## Design Principles

### Single Source of Truth

The core library parses the story structure **once** and produces canonical JSON artifacts. All formats consume these artifacts rather than parsing HTML or Twee files directly.

### Format Independence

Presentation formats do not depend on each other. Each format consumes only core library artifacts.

**Before (BAD):**
```
Story Bible → AllPaths → Tweego HTML
(inter-format dependency)
```

**After (GOOD):**
```
Core Library → Tweego HTML
     ↓
     ├─> AllPaths
     ├─> Metrics
     └─> Story Bible
(no inter-format dependencies)
```

### Backward Compatibility

Formats maintain legacy interfaces where possible. For example:
- Metrics falls back to Twee parsing if `story_graph.json` not found
- Story Bible maintains `load_allpaths_data()` interface

---

## Troubleshooting

### Core artifacts not found

**Error:**
```
Error: Core artifact not found: lib/artifacts/story_graph.json
Run 'npm run build:core' first to generate core artifacts
```

**Solution:**
```bash
npm run build:core
```

### Schema validation errors

**Error:**
```
ValidationError: ... does not match schema
```

**Solution:**
1. Check artifact format matches schema
2. Regenerate artifacts: `npm run build:core`
3. Report issue if schema is incorrect

### Build failures

**Error:**
```
tweego: command not found
```

**Solution:**
Install Tweego: https://www.motoslave.net/tweego/

---

## Related Documentation

- [ADR-012: Core Library and Format Separation](../architecture/012-core-library-format-separation.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)
- [STANDARDS.md](../STANDARDS.md)
- [Implementation Plan](../implementation-plan.md)

---

## Version History

### 1.0.0 (2025-12-02)
- Initial release
- Core library modules: parse_story, extract_passages, build_mappings
- JSON schemas for all artifacts
- Build integration with npm scripts
- Migrated AllPaths, Metrics, Story Bible to consume core artifacts
