# Functional Test Plan

This document describes how to verify that the Core Library and Format Separation Architecture (ADR-012) is working correctly.

## Overview

The system implements a three-stage pipeline:
1. **Core Library** - Parses Tweego HTML and produces shared JSON artifacts
2. **Format Generators** - Consume core artifacts and produce output formats
3. **Build Integration** - npm scripts orchestrate the full build

## Prerequisites

- Python 3.12+
- Tweego (for compilation)
- Node.js (for npm scripts)

## Test 1: Core Library Unit Tests

**Purpose**: Verify core library modules work correctly in isolation

```bash
# Run with pytest (if installed)
python3 -m pytest tests/ -v

# Or run with unittest
python3 -m unittest discover tests/ -v

# Or run inline tests
python3 -c "
from lib.core.parse_story import parse_story

mock_html = '''
<tw-storydata name=\"Test\" startnode=\"1\" ifid=\"123\" format=\"Harlowe\" format-version=\"3.3.9\">
  <tw-passagedata pid=\"1\" name=\"Start\">Hello [[End]]</tw-passagedata>
  <tw-passagedata pid=\"2\" name=\"End\">Goodbye</tw-passagedata>
</tw-storydata>
'''

result = parse_story(mock_html)
assert len(result['passages']) == 2
assert result['start_passage'] == 'Start'
print('✓ parse_story works')

from lib.core.extract_passages import extract_passages
dedup = extract_passages(result)
assert len(dedup['passages']) == 2
print('✓ extract_passages works')

from lib.core.build_mappings import build_mappings
mappings = build_mappings(result)
assert len(mappings['by_name']) == 2
print('✓ build_mappings works')
"
```

**Expected**: All assertions pass

## Test 2: Core Artifact Generation

**Purpose**: Verify `npm run build:core` generates all artifacts

```bash
npm run build:core
```

**Expected Output**:
```
=== Building Core Artifacts ===
Step 1/4: Generating paperthin HTML...
Step 2/4: Parsing story structure...
Step 3/4: Extracting passages...
Step 4/4: Building passage mappings...
=== Core Artifacts Complete ===
```

**Verify artifacts exist**:
```bash
ls -lh lib/artifacts/
# Should show:
#   - story_graph.json
#   - passages_deduplicated.json
#   - passage_mapping.json
```

**Verify artifact structure**:
```bash
python3 -c "
import json
sg = json.load(open('lib/artifacts/story_graph.json'))
print(f'story_graph.json: {len(sg[\"passages\"])} passages')

pd = json.load(open('lib/artifacts/passages_deduplicated.json'))
print(f'passages_deduplicated.json: {len(pd[\"passages\"])} passages')

pm = json.load(open('lib/artifacts/passage_mapping.json'))
print(f'passage_mapping.json: {len(pm[\"by_name\"])} mappings')
"
```

## Test 3: AllPaths Format (Consumes story_graph.json)

**Purpose**: Verify AllPaths reads from core artifacts, not HTML

```bash
python3 formats/allpaths/generator.py dist 2>&1 | grep -E "(STAGE 1|Loaded story_graph)"
```

**Expected**:
```
STAGE 1: LOAD - Reading story_graph.json from core library
Loaded story_graph.json with XX passages
```

**Verify outputs**:
```bash
ls dist/allpaths.html dist/allpaths-clean/ dist/allpaths-metadata/
```

## Test 4: Metrics Format (Consumes story_graph.json)

**Purpose**: Verify Metrics reads from core artifacts, not Twee files

```bash
python3 scripts/calculate-metrics.py --src src 2>&1 | grep -E "(Loading from|core artifacts)"
```

**Expected**:
```
Loading from core artifacts: lib/artifacts/story_graph.json
```

**Verify output**:
```bash
python3 scripts/calculate-metrics.py --src src
# Should show word counts, passage statistics, distributions
```

## Test 5: Story Bible Format (Consumes passages_deduplicated.json)

**Purpose**: Verify Story Bible loads from core artifacts

```bash
python3 -c "
import sys
sys.path.insert(0, 'formats/story-bible')
from modules.loader import load_allpaths_data
from pathlib import Path

data = load_allpaths_data(Path('dist'))
print(f'Source: {data[\"metadata\"][\"source\"]}')
assert data['metadata']['source'] == 'core_library'
print('✓ Story Bible uses core library')
"
```

**Verify Story Bible generation**:
```bash
python3 formats/story-bible/generator.py dist
ls dist/story-bible.html dist/story-bible.json
```

## Test 6: Full Build Integration

**Purpose**: Verify complete build pipeline works

```bash
npm run build
```

**Expected**: All formats generate without errors

**Verify all outputs**:
```bash
ls -lh dist/*.html lib/artifacts/*.json
```

## Test 7: No Inter-Format Dependencies

**Purpose**: Verify formats don't depend on each other

```bash
# Remove AllPaths output
rm -rf dist/allpaths*.html dist/allpaths-clean dist/allpaths-metadata

# Story Bible should still work (it reads from core library, not AllPaths)
python3 formats/story-bible/generator.py dist
ls dist/story-bible.html

# Metrics should still work
python3 scripts/calculate-metrics.py --src src
```

**Expected**: Story Bible and Metrics work without AllPaths output

## Test 8: Fallback Behavior

**Purpose**: Verify graceful degradation when artifacts missing

```bash
# Remove core artifacts
rm -rf lib/artifacts/*.json

# AllPaths should fail with clear error
python3 formats/allpaths/generator.py dist 2>&1 | grep -i "error"

# Metrics should fall back to Twee parsing
python3 scripts/calculate-metrics.py --src src 2>&1 | grep -i "fallback"
```

## Performance Checks

**Purpose**: Verify build meets performance targets

```bash
# Time core artifact generation
time npm run build:core
# Target: < 5 seconds

# Time full build
time npm run build
# Target: < 2 minutes
```

## Success Criteria Summary

| Test | Expected Result |
|------|-----------------|
| Core library unit tests | All pass |
| Core artifacts generated | 3 JSON files created |
| AllPaths uses story_graph.json | "STAGE 1: LOAD" in output |
| Metrics uses story_graph.json | "Loading from core artifacts" in output |
| Story Bible uses passages_deduplicated.json | source == "core_library" |
| Full build completes | No errors |
| Formats independent | Work without other formats' output |
| Core overhead | < 5 seconds |

## Troubleshooting

**"Core artifact not found"**
- Run `npm run build:core` first
- Check lib/artifacts/ exists and contains JSON files

**"tweego not found"**
- Install tweego: https://www.motoslave.net/tweego/
- Set TWEEGO_PATH to storyformats directory

**"Import error"**
- Ensure Python 3.12+ is installed
- Run from project root directory
