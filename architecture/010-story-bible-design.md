# ADR-010: Story Bible Architecture

## Status

**Phase 1**: Proposed - Local extraction via build pipeline
**Phase 2**: Designed - Webhook service integration for CI extraction

## Context

Writers of branching interactive fiction need a canonical source of truth about their story world that distinguishes between **constants** (facts always true regardless of player choices) and **variables** (facts determined by player actions). This Story Bible feature will extract and maintain world knowledge to help authors avoid contradictions and collaborators understand established lore.

### Key Requirements from PRD

From `/home/user/NaNoWriMo2025/features/story-bible.md`:

**Phase 1 Scope (Informational Tool)**:
- Extract world constants vs variables from story passages using AI
- Generate story-bible.html (human-readable) and story-bible.json (machine-readable)
- Post-build artifact (not blocking CI)
- Use AllPaths format as input
- Same AI model as continuity checking (gpt-oss:20b-fullcontext via Ollama)
- Cite evidence for all facts
- Distinguish constants, variables, zero action state
- Graceful degradation if generation fails

**Out of Scope for Phase 1**:
- CI validation against Story Bible (Phase 2)
- Blocking builds on contradictions
- Interactive editing of Story Bible
- Manual annotation of facts

### Design Forces

1. **Post-Build Artifact**: Must not block the build pipeline if Story Bible generation fails
2. **AI Extraction Quality**: Must produce accurate facts with evidence citations
3. **Performance**: Should complete within reasonable time (target: <5 minutes for current story size)
4. **Extensibility**: Design should support Phase 2 validation features
5. **Consistency**: Follow existing patterns (AllPaths pipeline, AI integration)
6. **Caching**: Should support incremental extraction to avoid re-processing unchanged content

## Decision

We will implement Story Bible as a **5-stage pipeline** following the AllPaths pattern (ADR-008), integrated as a post-build step in the build system.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Build Pipeline                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. npm run build:main       (Harlowe HTML)                     │
│  2. npm run build:allpaths   (AllPaths format)                  │
│  3. npm run build:metrics    (Writing metrics)                  │
│  4. npm run build:story-bible (Story Bible) ← NEW               │
│                                                                  │
│  Note: Each step continues even if previous step fails          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

Story Bible Pipeline (5 Stages):

Stage 1: Load AllPaths Data
   Input: dist/allpaths-metadata/*.txt, allpaths-validation-status.json
   Output: loaded_paths.json (intermediate)
   Responsibility: Load all story paths and metadata

Stage 2: Extract Facts with AI
   Input: loaded_paths.json
   Output: extracted_facts.json (intermediate)
   Responsibility: Call Ollama to extract constants/variables

Stage 3: Categorize and Organize
   Input: extracted_facts.json
   Output: categorized_facts.json (intermediate)
   Responsibility: Organize facts by type, merge duplicates

Stage 4: Generate HTML Output
   Input: categorized_facts.json
   Output: dist/story-bible.html
   Responsibility: Render human-readable HTML using Jinja2

Stage 5: Generate JSON Output
   Input: categorized_facts.json
   Output: dist/story-bible.json
   Responsibility: Export machine-readable structured data
```

### Component Architecture

```
formats/story-bible/
├── generator.py                    # Main orchestrator (5-stage pipeline)
├── modules/
│   ├── __init__.py
│   ├── loader.py                   # Stage 1: Load AllPaths data
│   ├── ai_extractor.py             # Stage 2: AI fact extraction
│   ├── categorizer.py              # Stage 3: Organize facts
│   ├── html_generator.py           # Stage 4: Generate HTML
│   └── json_generator.py           # Stage 5: Generate JSON
├── lib/
│   ├── __init__.py
│   ├── ollama_client.py            # Ollama HTTP API wrapper
│   └── fact_schema.py              # Fact data structures
├── templates/
│   └── story-bible.html.jinja2     # HTML template
├── schemas/
│   ├── extracted_facts.schema.json # Stage 2 output schema
│   ├── categorized_facts.schema.json # Stage 3 output schema
│   └── story-bible.schema.json     # Final JSON output schema
├── tests/
│   ├── test_loader.py
│   ├── test_ai_extractor.py
│   ├── test_categorizer.py
│   ├── test_html_generator.py
│   └── test_json_generator.py
└── README.md                       # Usage documentation

scripts/
└── build-story-bible.sh            # Build script integration
```

### Data Flow

```
AllPaths Output (dist/allpaths-metadata/*.txt)
    ↓
[Stage 1: Loader]
    ├─ Load all path text files
    ├─ Load validation cache for metadata
    ├─ Deduplicate passages across paths
    └─ Output: loaded_paths.json
    ↓
[Stage 2: AI Extractor]
    ├─ Prompt engineering: "Extract constants vs variables"
    ├─ Call Ollama API for each unique passage
    ├─ Parse JSON responses
    ├─ Cache extraction results (incremental processing)
    └─ Output: extracted_facts.json
    ↓
[Stage 3: Categorizer]
    ├─ Cross-reference facts across all paths
    ├─ Identify constants (appear in all paths)
    ├─ Identify variables (differ by path)
    ├─ Determine zero action state
    ├─ Merge duplicate facts
    └─ Output: categorized_facts.json
    ↓
[Stage 4: HTML Generator]
    ├─ Load Jinja2 template
    ├─ Render facts with evidence
    ├─ Generate navigation structure
    └─ Output: dist/story-bible.html
    ↓
[Stage 5: JSON Generator]
    ├─ Validate against schema
    ├─ Add metadata (timestamp, commit hash)
    └─ Output: dist/story-bible.json
```

## Technical Design Details

### Stage 1: Loader (modules/loader.py)

**Purpose**: Load AllPaths data and prepare for extraction

**Input**:
- `dist/allpaths-metadata/*.txt` - Story path text files
- `allpaths-validation-status.json` - Path metadata
- `dist/allpaths-passage-mapping.json` - Passage ID mapping

**Output**: `loaded_paths.json`
```json
{
  "passages": {
    "Start": {
      "text": "Full passage text...",
      "appears_in_paths": ["abc12345", "def67890"],
      "passage_id": "a1b2c3d4e5f6"
    }
  },
  "paths": [
    {
      "id": "abc12345",
      "route": ["Start", "Continue", "End"],
      "category": "new"
    }
  ],
  "metadata": {
    "total_paths": 30,
    "total_passages": 50,
    "generated_at": "2025-12-01T10:00:00Z"
  }
}
```

**Logic**:
1. Scan `dist/allpaths-metadata/*.txt` for path files
2. Extract passage text and route information
3. Deduplicate passages (same passage in multiple paths)
4. Load validation cache for path metadata
5. Build mapping of passage → paths it appears in
6. Write intermediate artifact

**Error Handling**:
- If AllPaths output missing → fail with clear error
- If individual path file corrupted → log warning, skip that path
- If passage mapping missing → continue without ID translation

---

### Stage 2: AI Extractor (modules/ai_extractor.py)

**Purpose**: Use AI to extract facts from passages

**Input**: `loaded_paths.json`

**Output**: `extracted_facts.json`
```json
{
  "extractions": [
    {
      "passage_id": "a1b2c3d4e5f6",
      "passage_name": "Start",
      "facts": [
        {
          "fact": "The city is on the coast",
          "type": "setting",
          "confidence": "high",
          "evidence": "...coastal breeze..."
        }
      ],
      "extracted_at": "2025-12-01T10:05:00Z"
    }
  ],
  "cache": {
    "a1b2c3d4e5f6": {
      "content_hash": "md5hash",
      "extracted_at": "2025-12-01T10:05:00Z"
    }
  }
}
```

**AI Prompt Structure** (similar to continuity checking):

```
=== SECTION 1: ROLE & CONTEXT ===

You are extracting FACTS about an interactive fiction story world.

Your task: Extract CONSTANTS (always true) and VARIABLES (depend on player choices).

CRITICAL UNDERSTANDING:
- Focus on WORLD FACTS, not plot events
- Constants: True in all story paths regardless of player action
- Variables: Change based on player choices
- Zero Action State: What happens if player does nothing

=== SECTION 2: WHAT TO EXTRACT ===

Extract these fact types:

1. **World Rules**: Magic systems, technology level, physical laws
2. **Setting**: Geography, landmarks, historical events before story
3. **Character Identities**: Names, backgrounds, core traits (not fates)
4. **Timeline**: Events before story starts, chronological constants

For each character, identify:
- Identity (constants): Who they are, background
- Zero Action State: Default trajectory if player doesn't intervene
- Variables: Outcomes that depend on player choices

=== SECTION 3: OUTPUT FORMAT ===

Respond with JSON:

{
  "facts": [
    {
      "fact": "The city is on the coast",
      "type": "setting|world_rule|character_identity|timeline",
      "confidence": "high|medium|low",
      "evidence": "Quote from passage demonstrating this fact",
      "category": "constant|variable|zero_action_state"
    }
  ]
}

=== SECTION 4: PASSAGE TEXT ===

{passage_text}

BEGIN EXTRACTION:
```

**Caching Strategy**:
- Cache key: MD5 hash of passage content
- Cache location: `story-bible-extraction-cache.json` (repo root)
- Cache structure:
  ```json
  {
    "content_hash": {
      "extracted_facts": [...],
      "extracted_at": "timestamp"
    }
  }
  ```
- On each run:
  1. Check if passage content hash exists in cache
  2. If yes and fresh → use cached extraction
  3. If no or stale → call AI, update cache
  4. Save cache after all extractions complete

**Performance Optimization**:
- Process passages in parallel (ThreadPoolExecutor, max 3 workers)
- Show progress bar (e.g., "Extracting facts: 15/50 passages")
- Timeout per passage: 60 seconds
- Total timeout: 5 minutes (fail gracefully if exceeded)

**Error Handling**:
- Ollama API timeout → log error, mark passage as failed, continue
- Invalid JSON response → log error, skip passage, continue
- Ollama service down → fail entire stage with clear error message
- Too many failures (>50% passages) → fail entire stage

---

### Stage 3: Categorizer (modules/categorizer.py)

**Purpose**: Cross-reference facts across paths to categorize as constants/variables

**Input**: `extracted_facts.json`

**Output**: `categorized_facts.json`
```json
{
  "constants": {
    "world_rules": [
      {
        "fact": "Magic system exists",
        "evidence": [
          {
            "passage": "Start",
            "passage_id": "a1b2c3d4",
            "quote": "...the magical academy..."
          }
        ],
        "appears_in_paths": ["abc123", "def456"],
        "confidence": "high"
      }
    ],
    "setting": [...],
    "timeline": [...]
  },
  "characters": {
    "Javlyn": {
      "identity": [
        {
          "fact": "Student at the Academy",
          "evidence": [...],
          "type": "constant"
        }
      ],
      "zero_action_state": [
        {
          "fact": "Struggles with magic and gives up",
          "evidence": [...],
          "paths": ["path_default"]
        }
      ],
      "variables": [
        {
          "fact": "Masters the magic",
          "condition": "Player helps Javlyn",
          "evidence": [...],
          "paths": ["path_7", "path_8"]
        }
      ]
    }
  },
  "variables": {
    "events": [...],
    "outcomes": [...]
  },
  "conflicts": [
    {
      "type": "contradictory_constants",
      "description": "City location differs",
      "facts": [
        {"fact": "City is on the coast", "evidence": [...]},
        {"fact": "City is in the mountains", "evidence": [...]}
      ]
    }
  ]
}
```

**Categorization Logic**:

1. **Identify Constants**:
   - Fact appears in all paths → constant
   - Fact appears consistently across multiple paths → likely constant
   - Use confidence threshold (>80% of paths = constant)

2. **Identify Variables**:
   - Fact appears in some paths but not others → variable
   - Group by condition (which player choice leads to this fact)

3. **Determine Zero Action State**:
   - Look for paths with minimal player intervention
   - Identify "default" outcomes mentioned in passages
   - Mark as "zero_action_state" category

4. **Detect Conflicts**:
   - Same fact type but contradictory content
   - Flag for author review (don't auto-resolve)

5. **Merge Duplicates**:
   - Similar facts from different passages
   - Combine evidence, keep most specific wording
   - Use fuzzy matching (Levenshtein distance >90% = duplicate)

**Algorithm**:
```python
def categorize_facts(extracted_facts):
    fact_occurrences = {}

    # Count occurrences across paths
    for passage_extraction in extracted_facts:
        for fact in passage_extraction['facts']:
            key = normalize_fact(fact['fact'])
            if key not in fact_occurrences:
                fact_occurrences[key] = {
                    'fact': fact['fact'],
                    'type': fact['type'],
                    'evidence': [],
                    'paths': set()
                }
            fact_occurrences[key]['evidence'].append({
                'passage': passage_extraction['passage_name'],
                'quote': fact['evidence']
            })
            # Track which paths this passage appears in
            fact_occurrences[key]['paths'].update(
                get_paths_for_passage(passage_extraction['passage_id'])
            )

    # Categorize based on path coverage
    constants = []
    variables = []

    total_paths = get_total_path_count()

    for key, fact_data in fact_occurrences.items():
        path_coverage = len(fact_data['paths']) / total_paths

        if path_coverage >= 0.8:  # Appears in 80%+ of paths
            constants.append(fact_data)
        else:
            variables.append(fact_data)

    return constants, variables
```

---

### Stage 4: HTML Generator (modules/html_generator.py)

**Purpose**: Generate human-readable HTML Story Bible

**Input**: `categorized_facts.json`

**Output**: `dist/story-bible.html`

**Template Structure** (`templates/story-bible.html.jinja2`):

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Story Bible - {{ story_title }}</title>
    <style>
        /* Styling similar to allpaths.html */
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
        }
        .section {
            margin: 30px 0;
        }
        .fact {
            background: #f5f5f5;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #2196F3;
        }
        .constant { border-left-color: #4CAF50; }
        .variable { border-left-color: #FF9800; }
        .conflict { border-left-color: #F44336; }
        .evidence {
            font-size: 0.9em;
            color: #666;
            margin-top: 10px;
        }
        nav {
            position: sticky;
            top: 20px;
            background: white;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <h1>Story Bible: {{ story_title }}</h1>

    <p><strong>Last Updated:</strong> {{ generated_at }}</p>
    <p><strong>Source Commit:</strong> {{ commit_hash }}</p>

    <nav>
        <h3>Navigation</h3>
        <ul>
            <li><a href="#world-constants">World Constants</a></li>
            <li><a href="#characters">Characters</a></li>
            <li><a href="#variables">Variables</a></li>
            {% if conflicts %}
            <li><a href="#conflicts">⚠️ Conflicts</a></li>
            {% endif %}
        </ul>
    </nav>

    <section id="world-constants" class="section">
        <h2>World Constants</h2>
        <p>Facts that are true in all story paths, regardless of player choices.</p>

        <h3>World Rules</h3>
        {% for fact in constants.world_rules %}
        <div class="fact constant">
            <strong>{{ fact.fact }}</strong>
            <div class="evidence">
                Evidence:
                {% for ev in fact.evidence %}
                <div>
                    <em>{{ ev.passage }}:</em> "{{ ev.quote }}"
                </div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}

        <!-- Similar sections for setting, timeline -->
    </section>

    <section id="characters" class="section">
        <h2>Characters</h2>

        {% for char_name, char_data in characters.items() %}
        <div class="character">
            <h3>{{ char_name }}</h3>

            <h4>Identity (Constants)</h4>
            {% for fact in char_data.identity %}
            <div class="fact constant">
                {{ fact.fact }}
                <div class="evidence">
                    Evidence:
                    {% for ev in fact.evidence %}
                    <em>{{ ev.passage }}:</em> "{{ ev.quote }}"
                    {% endfor %}
                </div>
            </div>
            {% endfor %}

            <h4>Zero Action State</h4>
            {% for fact in char_data.zero_action_state %}
            <div class="fact">
                {{ fact.fact }}
                <div class="evidence">
                    Evidence: {{ fact.evidence }}
                </div>
            </div>
            {% endfor %}

            <h4>Variables (Player-Determined)</h4>
            {% for fact in char_data.variables %}
            <div class="fact variable">
                {{ fact.fact }}
                <div class="evidence">
                    Condition: {{ fact.condition }}<br>
                    Evidence: {{ fact.evidence }}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endfor %}
    </section>

    <section id="variables" class="section">
        <h2>Variables</h2>
        <p>Facts that change based on player choices.</p>

        <!-- Events, outcomes sections -->
    </section>

    {% if conflicts %}
    <section id="conflicts" class="section">
        <h2>⚠️ Conflicts</h2>
        <p>Contradictory facts that need author review.</p>

        {% for conflict in conflicts %}
        <div class="fact conflict">
            <strong>{{ conflict.description }}</strong>
            <div class="evidence">
                {% for fact in conflict.facts %}
                <div>"{{ fact.fact }}" - Evidence: {{ fact.evidence }}</div>
                {% endfor %}
            </div>
        </div>
        {% endfor %}
    </section>
    {% endif %}
</body>
</html>
```

**Rendering Logic**:
```python
def generate_html_output(categorized_facts: Dict, output_path: Path):
    # Get git metadata
    commit_hash = get_current_commit_hash()
    generated_at = datetime.now().isoformat()

    # Load Jinja2 template
    template_dir = Path(__file__).parent.parent / 'templates'
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('story-bible.html.jinja2')

    # Render
    html = template.render(
        story_title=categorized_facts.get('story_title', 'Unknown'),
        generated_at=format_date_for_display(generated_at),
        commit_hash=commit_hash[:8],
        constants=categorized_facts['constants'],
        characters=categorized_facts['characters'],
        variables=categorized_facts['variables'],
        conflicts=categorized_facts.get('conflicts', [])
    )

    # Write output
    output_path.write_text(html, encoding='utf-8')
```

---

### Stage 5: JSON Generator (modules/json_generator.py)

**Purpose**: Generate machine-readable JSON Story Bible

**Input**: `categorized_facts.json`

**Output**: `dist/story-bible.json`

**JSON Schema** (`schemas/story-bible.schema.json`):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Story Bible",
  "type": "object",
  "required": ["meta", "constants", "characters", "variables"],
  "properties": {
    "meta": {
      "type": "object",
      "properties": {
        "generated": {"type": "string", "format": "date-time"},
        "commit": {"type": "string"},
        "version": {"type": "string"},
        "schema_version": {"type": "string"}
      }
    },
    "constants": {
      "type": "object",
      "properties": {
        "world_rules": {"type": "array", "items": {"$ref": "#/definitions/fact"}},
        "setting": {"type": "array", "items": {"$ref": "#/definitions/fact"}},
        "timeline": {"type": "array", "items": {"$ref": "#/definitions/fact"}}
      }
    },
    "characters": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "identity": {"type": "array", "items": {"$ref": "#/definitions/fact"}},
          "zero_action_state": {"type": "array", "items": {"$ref": "#/definitions/fact"}},
          "variables": {"type": "array", "items": {"$ref": "#/definitions/variable_fact"}}
        }
      }
    },
    "variables": {
      "type": "object",
      "properties": {
        "events": {"type": "array", "items": {"$ref": "#/definitions/variable_fact"}},
        "outcomes": {"type": "array", "items": {"$ref": "#/definitions/variable_fact"}}
      }
    }
  },
  "definitions": {
    "fact": {
      "type": "object",
      "required": ["fact", "evidence"],
      "properties": {
        "fact": {"type": "string"},
        "evidence": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "passage": {"type": "string"},
              "passage_id": {"type": "string"},
              "quote": {"type": "string"}
            }
          }
        },
        "category": {"type": "string"},
        "confidence": {"enum": ["low", "medium", "high"]}
      }
    },
    "variable_fact": {
      "allOf": [
        {"$ref": "#/definitions/fact"},
        {
          "properties": {
            "condition": {"type": "string"},
            "paths_true": {"type": "array", "items": {"type": "string"}},
            "paths_false": {"type": "array", "items": {"type": "string"}}
          }
        }
      ]
    }
  }
}
```

**JSON Generation**:
```python
def generate_json_output(categorized_facts: Dict, output_path: Path):
    # Build JSON structure
    story_bible = {
        "meta": {
            "generated": datetime.now().isoformat(),
            "commit": get_current_commit_hash(),
            "version": "1.0",
            "schema_version": "1.0.0"
        },
        "constants": categorized_facts['constants'],
        "characters": categorized_facts['characters'],
        "variables": categorized_facts['variables']
    }

    # Validate against schema
    validate_json_schema(story_bible, 'story-bible.schema.json')

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(story_bible, f, indent=2, ensure_ascii=False)
```

---

### Build Integration

**New Build Script**: `/home/user/NaNoWriMo2025/scripts/build-story-bible.sh`

```bash
#!/bin/bash
# Build Story Bible output
# Generates human and machine-readable story bible from AllPaths format

set -e  # Exit on error, but allow build to continue

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
FORMAT_DIR="$PROJECT_DIR/formats/story-bible"

echo "=== Building Story Bible ==="

# Check prerequisites
if [ ! -d "$DIST_DIR/allpaths-metadata" ]; then
    echo "Error: AllPaths output not found. Run 'npm run build:allpaths' first."
    exit 1
fi

# Generate Story Bible
echo "Generating Story Bible..."

if command -v python3 &> /dev/null; then
    # Run generator with error handling
    if python3 "$FORMAT_DIR/generator.py" "$DIST_DIR"; then
        echo "✓ Story Bible generated successfully"
        echo "  - HTML: $DIST_DIR/story-bible.html"
        echo "  - JSON: $DIST_DIR/story-bible.json"
    else
        echo "⚠️  Story Bible generation failed (non-blocking)"
        echo "  Build will continue without Story Bible"
        exit 0  # Exit 0 to not block the build
    fi
else
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

echo "=== Story Bible Build Complete ==="
```

**Update package.json**:

```json
{
  "scripts": {
    "build": "npm run build:main && npm run build:proofread && npm run build:allpaths && npm run build:metrics && npm run build:story-bible",
    "build:story-bible": "./scripts/build-story-bible.sh || true"
  }
}
```

Note: `|| true` ensures build continues even if Story Bible fails

---

### Main Orchestrator

**`formats/story-bible/generator.py`** (similar to allpaths/generator.py):

```python
#!/usr/bin/env python3
"""
Story Bible Generator

Generates human and machine-readable story bible from AllPaths format.
"""

import sys
from pathlib import Path
from modules.loader import load_allpaths_data
from modules.ai_extractor import extract_facts_with_ai
from modules.categorizer import categorize_facts
from modules.html_generator import generate_html_output
from modules.json_generator import generate_json_output


def main():
    """Main entry point for Story Bible generator."""

    # Parse arguments
    if len(sys.argv) < 2:
        print("Usage: generator.py <dist_dir>")
        sys.exit(1)

    dist_dir = Path(sys.argv[1])

    try:
        # ===================================================================
        # STAGE 1: LOAD
        # ===================================================================
        print("\n" + "="*80)
        print("STAGE 1: LOAD - Loading AllPaths data")
        print("="*80)

        loaded_data = load_allpaths_data(dist_dir)
        print(f"Loaded {len(loaded_data['passages'])} unique passages")
        print(f"Across {len(loaded_data['paths'])} total paths")

        # ===================================================================
        # STAGE 2: EXTRACT
        # ===================================================================
        print("\n" + "="*80)
        print("STAGE 2: EXTRACT - Extracting facts with AI")
        print("="*80)

        extracted_facts = extract_facts_with_ai(loaded_data)
        print(f"Extracted facts from {len(extracted_facts['extractions'])} passages")

        # ===================================================================
        # STAGE 3: CATEGORIZE
        # ===================================================================
        print("\n" + "="*80)
        print("STAGE 3: CATEGORIZE - Organizing facts")
        print("="*80)

        categorized = categorize_facts(extracted_facts, loaded_data)
        print(f"Categorized into:")
        print(f"  Constants: {count_facts(categorized['constants'])}")
        print(f"  Variables: {count_facts(categorized['variables'])}")
        print(f"  Characters: {len(categorized['characters'])}")

        # ===================================================================
        # STAGE 4: GENERATE HTML
        # ===================================================================
        print("\n" + "="*80)
        print("STAGE 4: GENERATE HTML - Creating story-bible.html")
        print("="*80)

        html_output = dist_dir / 'story-bible.html'
        generate_html_output(categorized, html_output)
        print(f"Generated: {html_output}")

        # ===================================================================
        # STAGE 5: GENERATE JSON
        # ===================================================================
        print("\n" + "="*80)
        print("STAGE 5: GENERATE JSON - Creating story-bible.json")
        print("="*80)

        json_output = dist_dir / 'story-bible.json'
        generate_json_output(categorized, json_output)
        print(f"Generated: {json_output}")

        # ===================================================================
        # COMPLETE
        # ===================================================================
        print("\n" + "="*80)
        print("=== STORY BIBLE GENERATION COMPLETE ===")
        print("="*80)
        print(f"HTML: {html_output}")
        print(f"JSON: {json_output}")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\n❌ Error generating Story Bible: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def count_facts(fact_dict):
    """Count total facts across all categories."""
    total = 0
    for category_facts in fact_dict.values():
        if isinstance(category_facts, list):
            total += len(category_facts)
    return total


if __name__ == '__main__':
    main()
```

---

### Error Handling and Graceful Degradation

**Build-Level Error Handling**:
1. **Missing AllPaths output**: Fail with clear error message
2. **Ollama service down**: Fail with clear error message
3. **AI extraction timeout**: Log warning, continue with partial results
4. **Individual passage failures**: Log warnings, continue with remaining passages
5. **Template rendering errors**: Fail generation but don't block build

**Graceful Degradation Strategy**:
```python
# In build-story-bible.sh
if python3 "$FORMAT_DIR/generator.py" "$DIST_DIR"; then
    echo "✓ Story Bible generated successfully"
else
    echo "⚠️  Story Bible generation failed (non-blocking)"
    # Don't fail the build - allow deployment without Story Bible
    exit 0
fi
```

**Error Messages**:
- Clear indication of what failed
- Suggestions for resolution
- Context about impact (e.g., "Story Bible won't be deployed, but other formats are fine")

---

## Consequences

### Positive

1. **Follows Established Patterns**: Uses same 5-stage pipeline as AllPaths (ADR-008)
2. **Reuses Infrastructure**: Ollama integration, Jinja2 templates, build scripts
3. **Modular and Testable**: Each stage independently testable
4. **Graceful Degradation**: Build continues if Story Bible fails
5. **Incremental Extraction**: Caching avoids re-processing unchanged passages
6. **Extensible**: Easy to add Phase 2 validation features
7. **Evidence-Based**: All facts cite source passages for verification

### Negative

1. **AI Dependency**: Requires Ollama service running locally
2. **Performance**: May take 2-5 minutes for large stories
3. **Quality Variance**: AI extraction accuracy depends on prompt engineering
4. **Cache Management**: Need to handle cache invalidation correctly
5. **Fact Deduplication**: Fuzzy matching may miss some duplicates or create false positives

### Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| AI extraction inaccurate | High - wrong facts mislead authors | Cite evidence for all facts (authors can verify) |
| Ollama service down | Medium - build fails | Clear error message, instructions to start Ollama |
| Extraction too slow | Medium - long build times | Caching, parallel processing, 5-minute timeout |
| Cache corruption | Low - forces full re-extraction | Validate cache on load, regenerate if invalid |
| Contradictory facts | Medium - confuses authors | Flag conflicts clearly, don't auto-resolve |

---

## Alternatives Considered

### Alternative 1: Single-Stage Simple Script

**Approach**: One Python script that does everything in sequence

**Rejected Because**:
- Hard to test individual components
- No intermediate artifacts for debugging
- Doesn't follow established patterns
- Difficult to extend for Phase 2

### Alternative 2: Use check-story-continuity.py Directly

**Approach**: Extend existing continuity checker to also extract facts

**Rejected Because**:
- Different concerns (continuity vs world-building)
- Would complicate continuity checker
- Separate tools easier to maintain
- Different prompt engineering needs

### Alternative 3: Manual Story Bible (No AI)

**Approach**: Authors manually write and maintain Story Bible

**Rejected Because**:
- High maintenance burden
- Likely to get out of sync with passages
- Doesn't scale as story grows
- Defeats purpose of automation

### Alternative 4: Database-Backed Story Bible

**Approach**: Use SQLite or similar database for fact storage

**Rejected Because**:
- Over-engineered for Phase 1
- Adds complexity without clear benefit
- JSON files sufficient for current scale
- Can migrate later if needed

---

## Implementation Plan

### Phase 1A: Core Pipeline (Week 1)
- [ ] Create `formats/story-bible/` directory structure
- [ ] Implement `modules/loader.py` (Stage 1)
- [ ] Implement `modules/ai_extractor.py` (Stage 2) with basic prompt
- [ ] Implement `modules/categorizer.py` (Stage 3) with simple logic
- [ ] Test pipeline end-to-end with sample data

### Phase 1B: Output Generation (Week 1)
- [ ] Create `templates/story-bible.html.jinja2`
- [ ] Implement `modules/html_generator.py` (Stage 4)
- [ ] Implement `modules/json_generator.py` (Stage 5)
- [ ] Define JSON schemas
- [ ] Test output formats

### Phase 1C: Build Integration (Week 2)
- [ ] Create `scripts/build-story-bible.sh`
- [ ] Update `package.json` with new build step
- [ ] Test graceful degradation (Ollama down, AI failures)
- [ ] Add error handling and logging
- [ ] Document usage in README

### Phase 1D: Refinement (Week 2)
- [ ] Implement extraction caching
- [ ] Add parallel processing
- [ ] Refine AI prompts based on results
- [ ] Add conflict detection
- [ ] Write comprehensive tests

### Phase 2 (Future - TBD)
- [ ] Add CI validation against Story Bible
- [ ] Implement contradiction detection in PRs
- [ ] Add `/update-canon` command for webhook service
- [ ] Support manual annotations

---

## Phase 2: Webhook Service Integration

### Context

**Problem**: Phase 1 design assumes Ollama is available locally during build. However, in CI (GitHub Actions), Ollama is not available. The existing continuity webhook service solves this by:
1. CI builds artifacts and uploads them
2. GitHub sends webhook to service running on host with Ollama
3. Service downloads artifacts, runs AI extraction via Ollama, posts results to PR

**Solution**: Integrate Story Bible extraction into the webhook service using the same pattern.

### Architecture Overview

```
GitHub Actions (CI)
  ↓ Build story artifacts
  ↓ Upload to workflow artifacts
  ↓ Workflow completes
  ↓ GitHub sends workflow_run webhook
  ↓
Webhook Service (services/continuity-webhook.py)
  ↓ Receives webhook
  ↓ Downloads artifacts
  ↓ [NEW] Check for /extract-story-bible command
  ↓ Run Story Bible extraction via Ollama
  ↓ Commit story-bible-cache.json to PR branch
  ↓ Post results to PR
```

### Design Decisions

#### 1. Trigger Mechanism

**Decision**: Manual command-based trigger (initially), automatic optional (future)

**Command**: `/extract-story-bible` (or shorter: `/story-bible`)

**Rationale**:
- Story Bible is a **world-level artifact**, not PR-specific
- Unlike continuity checking (validates each PR), Story Bible extracts canonical facts
- Manual trigger gives authors control over when to regenerate
- Avoids expensive extraction on every PR commit
- Can add automatic trigger later if useful

**Automatic Trigger (Future)**:
- Optional: Run on merges to main branch
- Updates Story Bible as story evolves
- Not needed for MVP

#### 2. Integration Points

**Reuse existing webhook service components**:

```python
# In continuity-webhook.py

# Existing endpoints:
@app.route('/webhook', methods=['POST')
  ↓ handle_comment_webhook()  # For commands
  ↓ handle_workflow_webhook()  # For workflow completion

# NEW handler:
def handle_extract_story_bible_command(payload):
    """Handle /extract-story-bible command from PR comments."""
    # Similar to handle_check_continuity_command
    # Triggers story bible extraction in background
```

**New command handler** (alongside `/check-continuity` and `/approve-path`):
- `/extract-story-bible` - Trigger full extraction
- `/extract-story-bible incremental` - Only extract from new/changed passages (default)
- `/extract-story-bible full` - Force full re-extraction ignoring cache

#### 3. Extraction Workflow

```
[User posts PR comment: /extract-story-bible]
  ↓
[Webhook service receives issue_comment event]
  ↓
[Validate user is collaborator]
  ↓
[Download latest PR artifacts]
  ↓
[Load story-bible-cache.json from PR branch (if exists)]
  ↓
[Load allpaths-metadata/*.txt from artifacts]
  ↓
[Identify passages to extract (new/changed based on cache)]
  ↓
[For each passage: Call Ollama API to extract facts]
  ↓ (parallel processing, progress updates)
[Post progress comments: "Extracting facts from passage 5/30..."]
  ↓
[Categorize facts (constants vs variables)]
  ↓
[Generate story-bible.json (machine-readable)]
  ↓
[Commit story-bible-cache.json + story-bible.json to PR branch]
  ↓
[Post final comment with link to story-bible.json artifact]
```

#### 4. Caching and Incremental Extraction

**Cache Structure**: `story-bible-cache.json` (stored in repo root, like `allpaths-validation-status.json`)

```json
{
  "meta": {
    "last_extracted": "2025-12-01T10:00:00Z",
    "total_passages_extracted": 50,
    "total_facts": 127
  },
  "passage_extractions": {
    "passage_id_1": {
      "content_hash": "abc123def456",
      "extracted_at": "2025-12-01T10:00:00Z",
      "facts": [
        {
          "fact": "The city is on the coast",
          "type": "setting",
          "confidence": "high",
          "evidence": "...coastal breeze..."
        }
      ]
    }
  },
  "categorized_facts": {
    "constants": { /* ... */ },
    "variables": { /* ... */ },
    "characters": { /* ... */ }
  }
}
```

**Incremental Logic** (similar to validation cache):

```python
def get_passages_to_extract(cache, allpaths_metadata_dir, mode='incremental'):
    """Identify which passages need fact extraction."""

    passages_to_process = []

    for passage_file in allpaths_metadata_dir.glob("*.txt"):
        passage_id = get_passage_id_from_file(passage_file)
        passage_content = passage_file.read_text()
        content_hash = hashlib.md5(passage_content.encode()).hexdigest()

        cached_extraction = cache.get('passage_extractions', {}).get(passage_id)

        if mode == 'full':
            # Force re-extraction
            passages_to_process.append((passage_id, passage_file))
        elif mode == 'incremental':
            # Only extract if new or changed
            if not cached_extraction or cached_extraction['content_hash'] != content_hash:
                passages_to_process.append((passage_id, passage_file))

    return passages_to_process
```

**Cache Benefits**:
- Avoid re-extracting unchanged passages
- Preserve previous extractions
- Incremental updates as story evolves
- Fast regeneration on subsequent runs

#### 5. Storage and Persistence

**What gets stored**:

1. **story-bible-cache.json** (repo root)
   - Committed to PR branch
   - Contains extraction cache + categorized facts
   - Used for incremental extraction
   - Merged with main branch when PR merges

2. **story-bible.json** (dist/ directory - optional)
   - Generated from cache
   - Human-readable final output
   - Published to GitHub Pages (if desired)
   - Can be regenerated from cache anytime

**Commit Workflow** (similar to path approval):

```python
def commit_story_bible_to_branch(pr_number, branch_name, cache_data):
    """Commit updated Story Bible cache to PR branch."""

    # Serialize cache
    cache_content = json.dumps(cache_data, indent=2)

    # Commit to branch
    commit_message = f"""Update Story Bible extraction

Extracted facts from {len(cache_data['passage_extractions'])} passages
Total facts: {count_total_facts(cache_data)}

Command: /extract-story-bible
Requested by: @{username}

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
"""

    commit_file_to_branch(
        branch_name,
        'story-bible-cache.json',
        cache_content,
        commit_message
    )
```

#### 6. Integration with Existing Continuity Checking

**Separation of Concerns**:

| Feature | Purpose | Scope | Trigger | Cache |
|---------|---------|-------|---------|-------|
| **Continuity Checking** | Validate path consistency | Per-path analysis | Automatic on PR + `/check-continuity` | `allpaths-validation-status.json` |
| **Story Bible** | Extract world facts | Cross-path world-building | `/extract-story-bible` command | `story-bible-cache.json` |

**No conflict**:
- Continuity checking uses `check-story-continuity.py` script
- Story Bible uses new extraction logic (similar pattern, different prompts)
- Both can run on same PR independently
- Different cache files, different purposes

**Shared Infrastructure**:
- Both use Ollama API for AI extraction
- Both use artifact download mechanism
- Both post progress updates to PR
- Both commit results to PR branch

#### 7. New Webhook Endpoints and Commands

**New Command Handler**:

```python
# In continuity-webhook.py

def handle_comment_webhook(payload):
    """Handle issue_comment webhooks for commands."""
    # Existing:
    if re.search(r'/check-continuity\b', comment_body):
        return handle_check_continuity_command(payload)
    elif re.search(r'/approve-path\b', comment_body):
        return handle_approve_path_command(payload)
    # NEW:
    elif re.search(r'/extract-story-bible\b', comment_body):
        return handle_extract_story_bible_command(payload)
    else:
        return jsonify({"message": "No recognized command"}), 200


def handle_extract_story_bible_command(payload):
    """Handle /extract-story-bible command from PR comments."""
    comment_body = payload['comment']['body']
    pr_number = payload['issue']['number']
    username = payload['comment']['user']['login']
    comment_id = payload['comment']['id']

    # Deduplication check (reuse existing pattern)
    with metrics_lock:
        if comment_id in processed_comment_ids:
            return jsonify({"message": "Duplicate webhook"}), 200
        processed_comment_ids[comment_id] = time.time()

    # Parse mode from command
    mode = parse_story_bible_command_mode(comment_body)  # 'incremental' or 'full'

    # Get PR info and artifacts
    pr_info = get_pr_info(pr_number)
    artifacts_url = get_latest_artifacts_url(pr_number)

    if not artifacts_url:
        post_pr_comment(pr_number, "⚠️ No workflow artifacts found. Please ensure CI has completed successfully.")
        return jsonify({"message": "No artifacts"}), 404

    # Spawn background thread for processing
    workflow_id = f"story-bible-{pr_number}-{int(time.time())}"

    thread = threading.Thread(
        target=process_story_bible_extraction_async,
        args=(workflow_id, pr_number, artifacts_url, username, mode),
        daemon=True
    )
    thread.start()

    return jsonify({"message": "Extraction started", "mode": mode}), 202


def parse_story_bible_command_mode(comment_body: str) -> str:
    """Parse extraction mode from command.

    Formats:
        /extract-story-bible           -> 'incremental' (default)
        /extract-story-bible full      -> 'full'
    """
    match = re.search(r'/extract-story-bible(?:\s+(full|incremental))?', comment_body, re.IGNORECASE)

    if match and match.group(1):
        return match.group(1).lower()

    return 'incremental'  # Default
```

**Background Processing Function**:

```python
def process_story_bible_extraction_async(workflow_id, pr_number, artifacts_url, username, mode):
    """Process Story Bible extraction in background thread."""

    try:
        # Post initial comment
        post_pr_comment(pr_number, f"""## 📖 Story Bible Extraction - Starting

**Mode:** `{mode}` _({'full re-extraction' if mode == 'full' else 'incremental extraction of new/changed passages'})_
**Requested by:** @{username}

Downloading artifacts and preparing extraction...

_This may take several minutes. Progress updates will be posted as extraction proceeds._

---
_Powered by Ollama (gpt-oss:20b-fullcontext)_
""")

        # Download artifacts
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Download and extract
            if not download_artifact_for_pr(artifacts_url, tmpdir_path):
                post_pr_comment(pr_number, "⚠️ Failed to download artifacts")
                return

            # Load cache from PR branch (if exists)
            cache = load_story_bible_cache_from_branch(pr_number)

            # Load allpaths metadata
            metadata_dir = tmpdir_path / "dist" / "allpaths-metadata"

            # Identify passages to extract
            passages_to_extract = get_passages_to_extract(cache, metadata_dir, mode)

            if not passages_to_extract:
                post_pr_comment(pr_number, f"""## 📖 Story Bible Extraction - Complete

**Mode:** `{mode}`

No passages need extraction. Story Bible is up to date.

_Use `/extract-story-bible full` to force full re-extraction._

---
_Powered by Ollama (gpt-oss:20b-fullcontext)_
""")
                return

            # Post list of passages
            total_passages = len(passages_to_extract)
            post_pr_comment(pr_number, f"""## 📖 Story Bible Extraction - Processing

**Mode:** `{mode}`

Found **{total_passages}** passage(s) to extract.

_Progress updates will be posted as each passage completes._
""")

            # Extract facts from each passage
            for idx, (passage_id, passage_file) in enumerate(passages_to_extract, 1):
                # Progress callback (similar to continuity checking)
                passage_name = get_passage_name(passage_id)
                passage_content = passage_file.read_text()

                # Call Ollama API
                extracted_facts = extract_facts_from_passage(passage_content, passage_id)

                # Update cache
                cache['passage_extractions'][passage_id] = {
                    'content_hash': hashlib.md5(passage_content.encode()).hexdigest(),
                    'extracted_at': datetime.now().isoformat(),
                    'facts': extracted_facts
                }

                # Post progress
                fact_count = len(extracted_facts)
                post_pr_comment(pr_number, f"""### ✅ Passage {idx}/{total_passages} Complete

**Passage:** `{passage_name}` (ID: `{passage_id}`)
**Facts extracted:** {fact_count}

<details>
<summary>Preview facts</summary>

{format_facts_preview(extracted_facts[:5])}  <!-- Show first 5 facts -->

</details>
""")

            # Categorize facts (cross-reference across all passages)
            categorized_facts = categorize_all_facts(cache['passage_extractions'])
            cache['categorized_facts'] = categorized_facts

            # Update metadata
            cache['meta'] = {
                'last_extracted': datetime.now().isoformat(),
                'total_passages_extracted': len(cache['passage_extractions']),
                'total_facts': count_total_facts(categorized_facts)
            }

            # Commit cache to PR branch
            pr_info = get_pr_info(pr_number)
            branch_name = pr_info['head']['ref']

            commit_story_bible_to_branch(pr_number, branch_name, cache)

            # Generate final output
            story_bible_json = generate_story_bible_json(categorized_facts)

            # Optionally commit story-bible.json as well (or just keep in cache)
            # For now, include summary in comment

            # Post final summary
            post_pr_comment(pr_number, f"""## 📖 Story Bible Extraction - Complete

**Mode:** `{mode}`
**Passages extracted:** {total_passages}
**Total facts:** {cache['meta']['total_facts']}

**Summary:**
- **Constants:** {count_facts(categorized_facts['constants'])} world facts
- **Characters:** {len(categorized_facts['characters'])} characters
- **Variables:** {count_facts(categorized_facts['variables'])} player-determined facts

**Story Bible updated:**
- `story-bible-cache.json` committed to branch `{branch_name}`
- Facts cached for incremental updates

**Next steps:**
- Review extracted facts in `story-bible-cache.json`
- Use `/extract-story-bible` again to update as story evolves
- Facts will be preserved and incrementally updated

---
_Powered by Ollama (gpt-oss:20b-fullcontext)_
""")

    except Exception as e:
        app.logger.error(f"[Story Bible] Error: {e}", exc_info=True)
        post_pr_comment(pr_number, "⚠️ Error during extraction. Please contact repository maintainers.")
```

#### 8. AI Extraction Implementation

**New Module**: Create `services/lib/story_bible_extractor.py`

```python
#!/usr/bin/env python3
"""
Story Bible fact extraction using Ollama.

Extracts world constants, variables, and character information from passages.
"""

import requests
import json
from typing import Dict, List

OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 120  # 2 minutes per passage

EXTRACTION_PROMPT = """Reasoning: high

=== SECTION 1: ROLE & CONTEXT ===

You are extracting FACTS about an interactive fiction story world.

Your task: Extract CONSTANTS (always true) and VARIABLES (depend on player choices).

CRITICAL UNDERSTANDING:
- Focus on WORLD FACTS, not plot events
- Constants: True in all story paths regardless of player action
- Variables: Change based on player choices
- Zero Action State: What happens if player does nothing

=== SECTION 2: WHAT TO EXTRACT ===

Extract these fact types:

1. **World Rules**: Magic systems, technology level, physical laws
2. **Setting**: Geography, landmarks, historical events before story
3. **Character Identities**: Names, backgrounds, core traits (not fates)
4. **Timeline**: Events before story starts, chronological constants

For each character, identify:
- Identity (constants): Who they are, background
- Zero Action State: Default trajectory if player doesn't intervene
- Variables: Outcomes that depend on player choices

=== SECTION 3: OUTPUT FORMAT ===

Respond with ONLY valid JSON (no markdown, no code blocks):

{
  "facts": [
    {
      "fact": "The city is on the coast",
      "type": "setting|world_rule|character_identity|timeline",
      "confidence": "high|medium|low",
      "evidence": "Quote from passage demonstrating this fact",
      "category": "constant|variable|zero_action_state"
    }
  ]
}

=== SECTION 4: PASSAGE TEXT ===

{passage_text}

BEGIN EXTRACTION (JSON only):
"""


def extract_facts_from_passage(passage_text: str, passage_id: str) -> List[Dict]:
    """
    Extract facts from a single passage using Ollama.

    Args:
        passage_text: The passage content
        passage_id: Unique identifier for passage

    Returns:
        List of extracted facts
    """

    # Format prompt
    prompt = EXTRACTION_PROMPT.format(passage_text=passage_text)

    # Call Ollama API
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,  # Lower temperature for more consistent extraction
                    "num_predict": 2000  # Max tokens for response
                }
            },
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()
        result = response.json()

        # Parse response
        raw_response = result.get('response', '')

        # Extract JSON from response (may have preamble text)
        facts_data = parse_json_from_response(raw_response)

        if not facts_data or 'facts' not in facts_data:
            return []

        return facts_data['facts']

    except requests.Timeout:
        raise Exception(f"Ollama API timeout for passage {passage_id}")
    except requests.RequestException as e:
        raise Exception(f"Ollama API error: {e}")
    except json.JSONDecodeError as e:
        raise Exception(f"Failed to parse Ollama response as JSON: {e}")


def parse_json_from_response(text: str) -> Dict:
    """
    Extract JSON object from AI response that may contain extra text.

    Looks for {  } pattern and attempts to parse.
    """

    # Try parsing entire response first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON object boundaries
    start = text.find('{')
    end = text.rfind('}')

    if start == -1 or end == -1:
        raise json.JSONDecodeError("No JSON object found in response", text, 0)

    json_text = text[start:end+1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in response: {e}", text, 0)


def categorize_all_facts(passage_extractions: Dict) -> Dict:
    """
    Cross-reference facts across all passages to categorize as constants/variables.

    Args:
        passage_extractions: Dict of passage_id -> extraction data

    Returns:
        Categorized facts structure
    """

    # Collect all facts
    all_facts = []
    for passage_id, extraction in passage_extractions.items():
        for fact in extraction.get('facts', []):
            all_facts.append({
                'passage_id': passage_id,
                **fact
            })

    # Group by fact type
    constants = {'world_rules': [], 'setting': [], 'timeline': []}
    variables = {'events': [], 'outcomes': []}
    characters = {}

    for fact in all_facts:
        fact_type = fact.get('type', 'unknown')
        category = fact.get('category', 'unknown')

        if category == 'constant':
            if fact_type in constants:
                constants[fact_type].append(fact)
        elif category == 'variable':
            if fact_type in ['event', 'outcome']:
                variables['events' if fact_type == 'event' else 'outcomes'].append(fact)
        elif category == 'character_identity' or fact_type == 'character_identity':
            # Extract character name from fact (simple heuristic)
            character_name = extract_character_name(fact['fact'])
            if character_name not in characters:
                characters[character_name] = {
                    'identity': [],
                    'zero_action_state': [],
                    'variables': []
                }

            if category == 'zero_action_state':
                characters[character_name]['zero_action_state'].append(fact)
            elif category == 'variable':
                characters[character_name]['variables'].append(fact)
            else:
                characters[character_name]['identity'].append(fact)

    return {
        'constants': constants,
        'variables': variables,
        'characters': characters
    }


def extract_character_name(fact_text: str) -> str:
    """
    Simple heuristic to extract character name from fact text.

    Examples:
        "Javlyn is a student" -> "Javlyn"
        "The character Sarah studies magic" -> "Sarah"
    """

    # Look for capitalized words at start (simple approach)
    words = fact_text.split()
    for word in words:
        if word[0].isupper() and word.isalpha() and word not in ['The', 'A', 'An', 'This', 'That']:
            return word

    return "Unknown"
```

### Performance Considerations

**Extraction Time**:
- Ollama API: ~20-60 seconds per passage (model-dependent)
- Parallel processing: Process 3 passages concurrently (ThreadPoolExecutor)
- Typical story (50 passages): 10-20 minutes for full extraction
- Incremental mode: Only process changed passages (much faster)

**Optimization Strategies**:
1. **Incremental caching**: Only extract new/changed passages
2. **Parallel processing**: Process multiple passages concurrently (max 3 workers)
3. **Progress updates**: Keep user informed during long extractions
4. **Timeout handling**: Skip problematic passages, continue with rest

**Example Timeline**:
```
Full extraction (50 passages):
- Download artifacts: 10s
- Extract 50 passages (parallel): 12 minutes
- Categorize facts: 5s
- Commit to branch: 5s
- Total: ~13 minutes

Incremental extraction (5 changed passages):
- Download artifacts: 10s
- Extract 5 passages: 2 minutes
- Categorize facts: 5s
- Commit to branch: 5s
- Total: ~2.5 minutes
```

### Security Considerations

**Reuse Existing Security Model**:
- Webhook signature verification (HMAC-SHA256)
- User authorization check (collaborators only)
- Artifact validation (size limits, structure validation)
- Text-only processing (no code execution)
- Sanitize AI output before posting to PR

**New Security Concerns**:
- **Large cache files**: Limit cache size (e.g., max 10MB)
- **Cache corruption**: Validate JSON structure before committing
- **Malicious facts**: Sanitize extracted facts before committing
- **DoS via extraction**: Rate limit commands per PR (e.g., max 1 extraction per 10 minutes)

### Testing Strategy

**Unit Tests**:
- `test_story_bible_extractor.py` - Test fact extraction logic
- `test_categorizer.py` - Test fact categorization
- Mock Ollama API responses for consistent testing

**Integration Tests**:
- Test full extraction workflow with real Ollama
- Test incremental extraction with cache
- Test error handling (Ollama down, timeout, invalid JSON)

**End-to-End Tests**:
- Create test PR with sample story
- Post `/extract-story-bible` command
- Verify cache committed to branch
- Verify facts correctly extracted

### Monitoring and Observability

**Metrics to Track**:
- Extraction duration per passage
- Cache hit rate (how many passages skipped)
- Extraction failures (timeouts, API errors)
- Fact count trends over time

**Logging**:
- Log each passage extraction (passage_id, duration, fact_count)
- Log cache operations (load, save, invalidation)
- Log API errors with context

**Status Endpoint Enhancement**:
```python
# Add to /status endpoint
{
  "active_jobs": [...],
  "story_bible_stats": {
    "total_extractions": 127,
    "avg_extraction_time": 45.2,
    "cache_hit_rate": 0.85,
    "last_extraction": "2025-12-01T10:00:00Z"
  }
}
```

### Future Enhancements (Beyond Phase 2)

**Automatic Extraction**:
- Trigger on merge to main branch
- Automatically update Story Bible as story evolves

**Validation Features**:
- Validate new content against established constants
- Flag contradictions in PR comments
- Suggest corrections

**Advanced Caching**:
- Differential caching (track changes, not just full replacement)
- Version history of facts (see how world-building evolved)

**Better Categorization**:
- Machine learning for duplicate detection
- Automatic conflict resolution suggestions
- Character relationship graphs

---

## Open Questions

### For Implementation

1. **Passage Deduplication**: How to handle identical passages in different .twee files?
   - **Decision**: Use passage name as key, merge evidence from all occurrences

2. **Fact Similarity Threshold**: What Levenshtein distance counts as "same fact"?
   - **Recommendation**: Start with 90%, adjust based on testing

3. **Character Detection**: How to identify character names in passages?
   - **Recommendation**: Let AI extract character names, then group facts by character

4. **Zero Action State**: How to determine "default" path?
   - **Recommendation**: Ask AI explicitly in prompt, let it infer from context

5. **Caching Invalidation**: When to regenerate vs use cache?
   - **Decision**: Invalidate if passage content hash changes

6. **Conflict Resolution UI**: Should HTML show suggested resolutions?
   - **Decision**: No for Phase 1, just flag conflicts for manual review

### For Testing

1. **Test Data**: Use current NaNoWriMo story or create synthetic test story?
   - **Recommendation**: Start with small synthetic story, then test on real data

2. **AI Mocking**: How to test without Ollama for CI?
   - **Recommendation**: Create mock responses for unit tests, integration tests require Ollama

3. **Regression Testing**: How to detect when AI extraction quality degrades?
   - **Recommendation**: Keep golden dataset, compare extraction results

---

## Success Metrics

### Phase 1 Success Criteria

1. **Functional**:
   - [ ] Story Bible generates on every build
   - [ ] HTML accessible and useful to authors
   - [ ] JSON valid and schema-compliant
   - [ ] Build continues if generation fails

2. **Quality**:
   - [ ] Constants correctly identified (>80% accuracy)
   - [ ] Variables correctly identified (>80% accuracy)
   - [ ] All facts have evidence citations
   - [ ] Conflicts flagged when present

3. **Performance**:
   - [ ] Generation completes in <5 minutes
   - [ ] Caching reduces re-processing by >50%
   - [ ] Parallel processing utilizes available CPU

4. **Usability**:
   - [ ] Authors reference Story Bible when writing
   - [ ] New collaborators use for onboarding
   - [ ] HTML navigable and readable

---

---

## Phase Comparison and Recommendations

### Phase 1 vs Phase 2

| Aspect | Phase 1 (Local) | Phase 2 (CI via Webhook) |
|--------|----------------|--------------------------|
| **Environment** | Developer's local machine | CI + webhook service |
| **Ollama Access** | Local Ollama installation | Webhook service host |
| **Trigger** | `npm run build:story-bible` | `/extract-story-bible` command |
| **Use Case** | Local development, testing | CI integration, team collaboration |
| **Storage** | `dist/story-bible.html`, `dist/story-bible.json` | `story-bible-cache.json` in repo |
| **Frequency** | Every build | On-demand (manual command) |
| **Caching** | Local cache file | Committed cache in repo |
| **Incremental** | Based on local cache | Based on committed cache |

### Recommended Implementation Path

**Immediate (Phase 2 First)**:
Given that Ollama isn't available in GitHub Actions and the webhook service already exists, **implement Phase 2 first**:

1. Add `/extract-story-bible` command to webhook service
2. Implement fact extraction via Ollama in webhook context
3. Commit `story-bible-cache.json` to PR branches
4. Allow incremental updates as story evolves

**Later (Phase 1 Optional)**:
Phase 1 (local extraction) can be added later if authors want to:
- Test extraction locally before pushing
- Generate HTML/JSON outputs for local review
- Debug extraction issues without PR overhead

**Why Phase 2 First**:
- Solves immediate problem (no Ollama in CI)
- Leverages existing infrastructure (webhook service, artifact download, PR commenting)
- Provides team collaboration (cache committed to repo, not just local)
- Incremental caching works across team members
- Matches existing patterns (continuity checking workflow)

### Migration Path (If Phase 1 Already Implemented)

If Phase 1 is already implemented locally:

1. **Reuse extraction logic**: Move `formats/story-bible/modules/ai_extractor.py` to `services/lib/story_bible_extractor.py`
2. **Reuse prompts**: Use same AI prompts for consistency
3. **Cache compatibility**: Ensure local cache format matches webhook cache format
4. **Dual support**: Keep both Phase 1 (local) and Phase 2 (CI) working together

### Design Principles Applied

**Phase 2 design follows existing patterns**:
- ✓ Reuses webhook service infrastructure (like continuity checking)
- ✓ Uses command-based trigger (like `/check-continuity`, `/approve-path`)
- ✓ Commits results to PR branch (like path approval)
- ✓ Posts progress updates to PR (like continuity checking)
- ✓ Incremental caching (like validation cache)
- ✓ Background processing with metrics (like continuity checking)
- ✓ Security model (webhook signatures, authorization, sanitization)

**Separation of concerns maintained**:
- Continuity checking: Validates individual paths for internal consistency
- Story Bible extraction: Extracts cross-path world-building facts
- Different prompts, different caches, different purposes
- Both can run on same PR without conflict

---

## Phase 3: Story Bible Validation Integration

### Status

**Proposed** - Integration with continuity checking for world consistency validation

### Context

**Problem**: After Story Bible extraction (Phase 2) creates `story-bible-cache.json` with established world constants, we need to validate new/changed content against these constants during continuity checking.

**User Flow**:
1. Author extracts Story Bible using `/extract-story-bible` command
2. Story Bible cache committed to PR branch with world constants
3. Continuity checking runs (automatically or via `/check-continuity`)
4. **NEW**: Continuity checker also validates against Story Bible constants
5. Combined results posted to PR: path consistency + world consistency

### Requirements from PM

From `/home/user/NaNoWriMo2025/features/story-bible.md` Phase 3 scope:

1. **Automatic integration**: When continuity checking runs, also validate against Story Bible
2. **Load from PR branch**: Read `story-bible-cache.json` from PR branch (not main)
3. **Validate new content**: Check new passages against established constants
4. **Combined output**: Single PR comment with both path consistency and world consistency results
5. **Graceful degradation**: If Story Bible cache doesn't exist, skip validation (don't fail)
6. **Severity levels**: critical, major, minor (same as continuity checking)

### Architecture Overview

```
Continuity Checking Workflow (Enhanced)
────────────────────────────────────────

1. Download PR artifacts
   ├─ dist/allpaths-metadata/*.txt
   ├─ allpaths-validation-status.json
   └─ [OPTIONAL] story-bible-cache.json from PR branch

2. For each path to validate:

   ┌──────────────────────────────────────┐
   │  Path Consistency Check              │
   │  (existing continuity checking)      │
   │  → Internal path logic               │
   │  → Character consistency             │
   │  → Timeline coherence                │
   └──────────────────────────────────────┘
            ↓
   ┌──────────────────────────────────────┐
   │  World Consistency Check (NEW)       │
   │  (validate against Story Bible)      │
   │  → Load Story Bible constants        │
   │  → Validate passage against constants│
   │  → Detect contradictions             │
   └──────────────────────────────────────┘
            ↓
   ┌──────────────────────────────────────┐
   │  Merge Results                       │
   │  → Combine path issues + world issues│
   │  → Calculate combined severity       │
   └──────────────────────────────────────┘

3. Post combined results to PR
   ├─ Path Consistency section
   └─ World Consistency section (if Story Bible exists)
```

### Design Decisions

#### 1. Validation Module Location

**Decision**: Create `services/lib/story_bible_validator.py`

**Structure**:
```
services/lib/
├── story_bible_extractor.py    # Phase 2: Extract facts from passages
└── story_bible_validator.py    # Phase 3: Validate against constants (NEW)
```

**Rationale**:
- **Separation of concerns**: Extraction (discovery) vs Validation (checking)
- **Reusability**: Can be used by other services in future
- **Independent testing**: Test validation logic separately from extraction
- **Follows pattern**: Similar to how continuity checking is modular

**Responsibilities**:
- Load Story Bible cache from PR branch
- Validate passage content against established constants
- Return structured violations with evidence
- Handle missing/corrupt cache gracefully

---

#### 2. Validation Prompt Design

**New AI Prompt**: Validate passage against known constants

```python
VALIDATION_PROMPT = """Reasoning: high

=== SECTION 1: ROLE & CONTEXT ===

You are validating a story passage against established world constants.

Your task: Detect CONTRADICTIONS between the passage and known world facts.

CRITICAL UNDERSTANDING:
- World constants are CANONICAL - they represent established lore
- This passage is NEW CONTENT being validated
- Only flag DIRECT CONTRADICTIONS, not missing details
- Constants are true across ALL story paths

=== SECTION 2: WORLD CONSTANTS ===

The following facts are ESTABLISHED CONSTANTS about this story world:

{world_constants}

These constants are:
- **World Rules**: Magic systems, technology level, physical laws
- **Setting**: Geography, landmarks, historical events
- **Timeline**: Established chronology before story starts

=== SECTION 3: PASSAGE TO VALIDATE ===

{passage_text}

=== SECTION 4: VALIDATION TASK ===

Compare the passage against the world constants and detect:

1. **Direct Contradictions**: Passage states something that conflicts with constants
2. **Inconsistent Details**: Passage describes world differently than constants
3. **Timeline Violations**: Events contradict established chronology

DO NOT FLAG:
- Missing information (constants don't require all details to be mentioned)
- Character choices/outcomes (these are variables, not constants)
- Plot events (story progression is independent of world constants)
- Stylistic differences (same fact described differently is OK)

ONLY FLAG if passage DIRECTLY CONTRADICTS a constant.

=== SECTION 5: OUTPUT FORMAT ===

Respond with ONLY valid JSON (no markdown, no code blocks):

{
  "has_violations": true/false,
  "severity": "none|minor|major|critical",
  "violations": [
    {
      "type": "world_rule|setting|timeline|contradiction",
      "severity": "minor|major|critical",
      "description": "Brief description of the contradiction",
      "constant_fact": "The established constant being violated",
      "passage_statement": "Quote from passage that contradicts it",
      "evidence": {
        "constant_source": "Passage where constant was established",
        "conflict_location": "Location in this passage"
      }
    }
  ],
  "summary": "Brief overall assessment"
}

If no violations found, return:
{"has_violations": false, "severity": "none", "violations": [], "summary": "No world consistency issues detected"}

=== SECTION 6: SEVERITY RUBRIC ===

**CRITICAL** - Fundamental world-building contradictions:
- Magic system works differently than established
- Geography contradicts (city on coast vs mountains)
- Technology level inconsistent (medieval vs modern)
- Major historical events contradicted

**MAJOR** - Significant world detail contradictions:
- Landmark description differs from constant
- World rule details inconsistent
- Timeline order contradicted

**MINOR** - Small detail variations:
- Minor setting details differ
- Slight chronology ambiguity
- Non-essential world fact variance

BEGIN VALIDATION (JSON only):
"""
```

**Key Differences from Extraction Prompt**:
- **Input**: Takes both constants AND passage (extraction only takes passage)
- **Task**: Find contradictions (not extract facts)
- **Output**: Violations with references to constants (not facts)
- **Severity**: Focuses on contradictions (not discovery confidence)

---

#### 3. Integration with Continuity Checking

**Modify**: `services/continuity-webhook.py` in `process_webhook_async()`

**Current Flow**:
```python
# Existing code in process_webhook_async()
def process_webhook_async(workflow_id, pr_number, artifacts_url, mode='new-only'):
    # ... download artifacts ...
    # ... load allpaths metadata ...

    for path_id, text_file in unvalidated:
        # Read story text
        story_text = text_file.read_text()

        # Check continuity
        result = run_continuity_check(...)  # Uses check-story-continuity.py

        # Update cache and post results
        # ...
```

**Enhanced Flow**:
```python
# Enhanced code with Story Bible validation
def process_webhook_async(workflow_id, pr_number, artifacts_url, mode='new-only'):
    # ... download artifacts ...
    # ... load allpaths metadata ...

    # NEW: Load Story Bible cache from PR branch (if exists)
    story_bible_cache = load_story_bible_from_pr_branch(pr_number)
    story_bible_available = bool(story_bible_cache and story_bible_cache.get('categorized_facts'))

    for path_id, text_file in unvalidated:
        # Read story text
        story_text = text_file.read_text()

        # 1. Path Consistency Check (existing)
        path_result = run_continuity_check(text_dir, cache_file, pr_number, ...)

        # 2. World Consistency Check (NEW)
        world_result = None
        if story_bible_available:
            world_result = validate_against_story_bible(
                passage_text=story_text,
                story_bible_cache=story_bible_cache,
                passage_id=path_id
            )

        # 3. Merge Results
        combined_result = merge_validation_results(path_result, world_result)

        # Update cache and post results with combined output
        # ...
```

**Helper Function**:
```python
def load_story_bible_from_pr_branch(pr_number: int) -> Dict:
    """Load story-bible-cache.json from PR branch if it exists.

    Returns:
        Story Bible cache dict, or empty dict if not found
    """
    pr_info = get_pr_info(pr_number)
    if not pr_info:
        return {}

    branch_name = pr_info['head']['ref']
    token = get_github_token()
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/story-bible-cache.json"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    try:
        response = requests.get(url, headers=headers, params={"ref": branch_name})
        if response.status_code == 200:
            import base64
            content = response.json()['content']
            decoded = base64.b64decode(content).decode('utf-8')
            cache = json.loads(decoded)
            app.logger.info(f"Loaded Story Bible cache from branch {branch_name}")
            return cache
        else:
            app.logger.info(f"No Story Bible cache found on branch {branch_name}")
            return {}
    except Exception as e:
        app.logger.warning(f"Could not load Story Bible cache: {e}")
        return {}
```

---

#### 4. Validation Implementation

**New Module**: `services/lib/story_bible_validator.py`

```python
#!/usr/bin/env python3
"""
Story Bible validation against established world constants.

Validates new story content against extracted Story Bible constants to detect
world-building contradictions.
"""

import requests
import json
from typing import Dict, List, Optional

OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT = 120  # 2 minutes per validation

VALIDATION_PROMPT = """Reasoning: high

=== SECTION 1: ROLE & CONTEXT ===

You are validating a story passage against established world constants.

Your task: Detect CONTRADICTIONS between the passage and known world facts.

CRITICAL UNDERSTANDING:
- World constants are CANONICAL - they represent established lore
- This passage is NEW CONTENT being validated
- Only flag DIRECT CONTRADICTIONS, not missing details
- Constants are true across ALL story paths

=== SECTION 2: WORLD CONSTANTS ===

The following facts are ESTABLISHED CONSTANTS about this story world:

{world_constants}

These constants are:
- **World Rules**: Magic systems, technology level, physical laws
- **Setting**: Geography, landmarks, historical events
- **Timeline**: Established chronology before story starts

=== SECTION 3: PASSAGE TO VALIDATE ===

{passage_text}

=== SECTION 4: VALIDATION TASK ===

Compare the passage against the world constants and detect:

1. **Direct Contradictions**: Passage states something that conflicts with constants
2. **Inconsistent Details**: Passage describes world differently than constants
3. **Timeline Violations**: Events contradict established chronology

DO NOT FLAG:
- Missing information (constants don't require all details to be mentioned)
- Character choices/outcomes (these are variables, not constants)
- Plot events (story progression is independent of world constants)
- Stylistic differences (same fact described differently is OK)

ONLY FLAG if passage DIRECTLY CONTRADICTS a constant.

=== SECTION 5: OUTPUT FORMAT ===

Respond with ONLY valid JSON (no markdown, no code blocks):

{{
  "has_violations": true/false,
  "severity": "none|minor|major|critical",
  "violations": [
    {{
      "type": "world_rule|setting|timeline|contradiction",
      "severity": "minor|major|critical",
      "description": "Brief description of the contradiction",
      "constant_fact": "The established constant being violated",
      "passage_statement": "Quote from passage that contradicts it",
      "evidence": {{
        "constant_source": "Passage where constant was established",
        "conflict_location": "Location in this passage"
      }}
    }}
  ],
  "summary": "Brief overall assessment"
}}

If no violations found, return:
{{"has_violations": false, "severity": "none", "violations": [], "summary": "No world consistency issues detected"}}

=== SECTION 6: SEVERITY RUBRIC ===

**CRITICAL** - Fundamental world-building contradictions:
- Magic system works differently than established
- Geography contradicts (city on coast vs mountains)
- Technology level inconsistent (medieval vs modern)
- Major historical events contradicted

**MAJOR** - Significant world detail contradictions:
- Landmark description differs from constant
- World rule details inconsistent
- Timeline order contradicted

**MINOR** - Small detail variations:
- Minor setting details differ
- Slight chronology ambiguity
- Non-essential world fact variance

BEGIN VALIDATION (JSON only):
"""


def format_constants_for_validation(story_bible_cache: Dict) -> str:
    """
    Format Story Bible constants into text for validation prompt.

    Args:
        story_bible_cache: Story Bible cache with categorized facts

    Returns:
        Formatted string of constants for prompt
    """
    categorized = story_bible_cache.get('categorized_facts', {})
    constants = categorized.get('constants', {})

    formatted_lines = []

    # World Rules
    world_rules = constants.get('world_rules', [])
    if world_rules:
        formatted_lines.append("**World Rules:**")
        for fact in world_rules:
            fact_text = fact.get('fact', 'Unknown')
            evidence = fact.get('evidence', '')
            formatted_lines.append(f"  - {fact_text}")
            if evidence:
                formatted_lines.append(f"    Evidence: \"{evidence}\"")
        formatted_lines.append("")

    # Setting
    setting = constants.get('setting', [])
    if setting:
        formatted_lines.append("**Setting:**")
        for fact in setting:
            fact_text = fact.get('fact', 'Unknown')
            evidence = fact.get('evidence', '')
            formatted_lines.append(f"  - {fact_text}")
            if evidence:
                formatted_lines.append(f"    Evidence: \"{evidence}\"")
        formatted_lines.append("")

    # Timeline
    timeline = constants.get('timeline', [])
    if timeline:
        formatted_lines.append("**Timeline:**")
        for fact in timeline:
            fact_text = fact.get('fact', 'Unknown')
            evidence = fact.get('evidence', '')
            formatted_lines.append(f"  - {fact_text}")
            if evidence:
                formatted_lines.append(f"    Evidence: \"{evidence}\"")
        formatted_lines.append("")

    if not formatted_lines:
        return "(No world constants established yet)"

    return "\n".join(formatted_lines)


def validate_against_story_bible(
    passage_text: str,
    story_bible_cache: Dict,
    passage_id: str
) -> Optional[Dict]:
    """
    Validate a passage against Story Bible constants.

    Args:
        passage_text: The passage content to validate
        story_bible_cache: Story Bible cache with categorized facts
        passage_id: Identifier for passage (for logging)

    Returns:
        Validation result dict with violations, or None if validation failed
    """
    # Check if Story Bible has constants
    categorized = story_bible_cache.get('categorized_facts', {})
    constants = categorized.get('constants', {})

    # If no constants, skip validation
    if not constants or not any(constants.values()):
        return {
            "has_violations": False,
            "severity": "none",
            "violations": [],
            "summary": "No Story Bible constants available for validation"
        }

    # Format constants for prompt
    world_constants = format_constants_for_validation(story_bible_cache)

    # Build validation prompt
    prompt = VALIDATION_PROMPT.format(
        world_constants=world_constants,
        passage_text=passage_text
    )

    # Call Ollama API
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.2,  # Low temperature for consistent validation
                    "num_predict": 1500
                }
            },
            timeout=OLLAMA_TIMEOUT
        )

        response.raise_for_status()
        result = response.json()

        # Parse response
        raw_response = result.get('response', '')

        # Extract JSON from response
        validation_result = parse_json_from_response(raw_response)

        return validation_result

    except requests.Timeout:
        # Timeout is non-blocking - log and return no violations
        return {
            "has_violations": False,
            "severity": "none",
            "violations": [],
            "summary": "Story Bible validation timed out (skipped)"
        }
    except Exception as e:
        # Other errors are non-blocking - log and return no violations
        return {
            "has_violations": False,
            "severity": "none",
            "violations": [],
            "summary": f"Story Bible validation error: {str(e)[:50]} (skipped)"
        }


def parse_json_from_response(text: str) -> Dict:
    """
    Extract JSON object from AI response that may contain extra text.

    Args:
        text: Raw AI response text

    Returns:
        Parsed JSON object

    Raises:
        json.JSONDecodeError: If no valid JSON found
    """
    # Try parsing entire response first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON object boundaries
    start = text.find('{')
    end = text.rfind('}')

    if start == -1 or end == -1:
        return {
            "has_violations": False,
            "severity": "none",
            "violations": [],
            "summary": "Could not parse validation response"
        }

    json_text = text[start:end+1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return {
            "has_violations": False,
            "severity": "none",
            "violations": [],
            "summary": "Could not parse validation response"
        }


def merge_validation_results(path_result: Dict, world_result: Optional[Dict]) -> Dict:
    """
    Merge path consistency and world consistency validation results.

    Args:
        path_result: Result from path consistency checking
        world_result: Result from Story Bible validation (may be None)

    Returns:
        Combined result dict
    """
    # Start with path result
    combined = path_result.copy()

    # If no world validation, return path result as-is
    if not world_result:
        combined['world_validation'] = None
        return combined

    # Add world validation section
    combined['world_validation'] = world_result

    # Merge issues and recalculate severity
    path_issues = path_result.get('issues', [])
    world_violations = world_result.get('violations', [])

    # Combine issues (keep separate for formatting)
    # Don't merge into single list - we'll format separately in PR comment

    # Recalculate combined severity (take max of path and world)
    path_severity = path_result.get('severity', 'none')
    world_severity = world_result.get('severity', 'none')

    severity_order = {'none': 0, 'minor': 1, 'major': 2, 'critical': 3}
    combined_severity_value = max(
        severity_order.get(path_severity, 0),
        severity_order.get(world_severity, 0)
    )
    combined_severity = [k for k, v in severity_order.items() if v == combined_severity_value][0]

    combined['severity'] = combined_severity
    combined['has_issues'] = (
        path_result.get('has_issues', False) or
        world_result.get('has_violations', False)
    )

    return combined
```

---

#### 5. PR Comment Format

**Enhanced format_pr_comment()** in `continuity-webhook.py`:

```python
def format_pr_comment(results: dict) -> str:
    """Format the continuity check results as a PR comment."""
    mode = results.get('mode', 'new-only')
    stats = results.get('statistics', {})
    all_checked_paths = results.get('all_checked_paths', [])

    # ... existing mode explanation and header ...

    comment = f"""## 🤖 AI Continuity Check

**Mode:** `{mode}` _({mode_text})_

**Summary:** {results["summary"]}

"""

    # ... existing statistics section ...

    # NEW: Story Bible section (if available)
    story_bible_available = any(
        p.get('world_validation') for p in all_checked_paths
    )

    if story_bible_available:
        comment += "\n### 📖 Story Bible Validation\n\n"
        comment += "✓ Validated against established world constants\n"

        world_issues_count = sum(
            1 for p in results["paths_with_issues"]
            if p.get('world_validation', {}).get('has_violations', False)
        )

        if world_issues_count > 0:
            comment += f"⚠️ Found world consistency issues in {world_issues_count} path(s)\n\n"
        else:
            comment += "✅ No world consistency issues detected\n\n"

    # ... existing path issues section ...

    # Modified: Format path issues with world validation
    if results["paths_with_issues"]:
        comment += f"### ⚠️ Issues Found\n\n"
        comment += f"Found issues in **{len(results['paths_with_issues'])}** of {results['checked_count']} path(s).\n\n"

        # Group by severity (existing code)
        critical = [p for p in results["paths_with_issues"] if p["severity"] == "critical"]
        major = [p for p in results["paths_with_issues"] if p["severity"] == "major"]
        minor = [p for p in results["paths_with_issues"] if p["severity"] == "minor"]

        # Format each severity group
        if critical:
            comment += f"#### 🔴 Critical Issues ({len(critical)})\n\n"
            for path in critical:
                comment += format_path_issues_with_world(path)  # NEW: Enhanced formatter

        # ... similar for major and minor ...

    # ... existing bulk approval section ...

    return comment


def format_path_issues_with_world(path: dict) -> str:
    """Format issues for a single path, including world validation."""
    path_id = path.get("id", "unknown")
    route_str = " → ".join(path["route"]) if path["route"] else path_id
    output = f"**Path:** `{path_id}` ({route_str})\n\n"

    # Path consistency summary
    output += f"_{sanitize_ai_content(path['summary'])}_\n\n"

    # Path consistency issues (existing)
    if path.get("issues"):
        output += "<details>\n<summary>Path Consistency Issues</summary>\n\n"
        for issue in path["issues"]:
            # ... existing issue formatting ...
        output += "</details>\n\n"

    # World consistency issues (NEW)
    world_validation = path.get('world_validation')
    if world_validation and world_validation.get('has_violations'):
        output += "<details>\n<summary>World Consistency Issues</summary>\n\n"
        output += f"_{sanitize_ai_content(world_validation.get('summary', '')}_\n\n"

        for violation in world_validation.get('violations', []):
            violation_type = violation.get('type', 'unknown')
            severity = violation.get('severity', 'unknown')
            description = sanitize_ai_content(violation.get('description', ''))
            constant_fact = sanitize_ai_content(violation.get('constant_fact', ''))
            passage_statement = sanitize_ai_content(violation.get('passage_statement', ''))

            output += f"- **{violation_type.capitalize()}** ({severity}): {description}\n"
            output += f"  - **Established constant**: \"{constant_fact}\"\n"
            output += f"  - **This passage states**: \"{passage_statement}\"\n"

            evidence = violation.get('evidence', {})
            if evidence:
                const_source = evidence.get('constant_source', '')
                if const_source:
                    output += f"  - **Constant source**: {const_source}\n"
            output += "\n"

        output += "</details>\n\n"

    return output
```

---

#### 6. Performance Considerations

**Sequential vs Parallel**:

**Option A: Sequential (Simpler)**:
```python
# Run path check, then world check
path_result = run_continuity_check(...)
world_result = validate_against_story_bible(...) if story_bible_available else None
combined = merge_validation_results(path_result, world_result)
```

**Pros**: Simpler code, easier to debug, clear execution flow
**Cons**: ~30-60s longer per path (serial execution)

**Option B: Parallel (Faster)**:
```python
# Run both checks concurrently
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=2) as executor:
    path_future = executor.submit(run_continuity_check, ...)
    world_future = executor.submit(validate_against_story_bible, ...) if story_bible_available else None

    path_result = path_future.result()
    world_result = world_future.result() if world_future else None
    combined = merge_validation_results(path_result, world_result)
```

**Pros**: Faster (parallel execution)
**Cons**: More complex, harder to debug, need thread-safe code

**Recommendation**: Start with **Sequential (Option A)** for initial implementation:
- Simpler to implement and test
- Performance impact acceptable (~30s per path extra)
- Can optimize to parallel later if needed
- Reduces risk of threading issues

**Performance Impact Estimate**:
- Path consistency check: ~60-120s per path
- World validation: ~30-60s per path
- **Sequential total**: ~90-180s per path
- **Parallel total**: ~60-120s per path (if we implement parallel)

For typical PR with 1-3 new paths: ~3-9 minutes total (acceptable)

---

#### 7. Error Handling and Graceful Degradation

**Story Bible Cache Not Found**:
```python
# In process_webhook_async()
story_bible_cache = load_story_bible_from_pr_branch(pr_number)

if not story_bible_cache:
    app.logger.info(f"[Story Bible] No cache found for PR #{pr_number}, skipping world validation")
    story_bible_available = False
else:
    app.logger.info(f"[Story Bible] Loaded cache with {len(story_bible_cache.get('categorized_facts', {}).get('constants', {}))} constant categories")
    story_bible_available = True
```

**Validation Errors** (non-blocking):
- Ollama timeout → Log warning, skip world validation, continue
- Invalid JSON response → Log error, skip world validation, continue
- API error → Log error, skip world validation, continue

**Cache Corruption**:
```python
def load_story_bible_from_pr_branch(pr_number: int) -> Dict:
    try:
        # ... download and parse cache ...

        # Validate cache structure
        if 'categorized_facts' not in cache:
            app.logger.warning("Story Bible cache missing 'categorized_facts', skipping validation")
            return {}

        return cache
    except json.JSONDecodeError as e:
        app.logger.error(f"Story Bible cache is corrupted: {e}")
        return {}
    except Exception as e:
        app.logger.warning(f"Could not load Story Bible cache: {e}")
        return {}
```

**PR Comment When Story Bible Not Available**:
```python
# In format_pr_comment()
if not story_bible_available:
    comment += "\n_ℹ️ Story Bible validation not available. Use `/extract-story-bible` to enable world consistency checking._\n\n"
```

---

### Implementation Checklist

**Phase 3A: Core Validation (Week 1)**
- [ ] Create `services/lib/story_bible_validator.py` module
- [ ] Implement `validate_against_story_bible()` function
- [ ] Implement `format_constants_for_validation()` helper
- [ ] Implement `merge_validation_results()` helper
- [ ] Add validation prompt to validator module
- [ ] Test validation logic with sample data

**Phase 3B: Webhook Integration (Week 1)**
- [ ] Modify `continuity-webhook.py` to load Story Bible cache
- [ ] Integrate validation into `process_webhook_async()` workflow
- [ ] Enhance `format_pr_comment()` to include world validation
- [ ] Enhance `format_path_issues()` to show world violations
- [ ] Add error handling for missing/corrupt cache
- [ ] Test end-to-end with real PR

**Phase 3C: Testing and Refinement (Week 2)**
- [ ] Unit tests for `story_bible_validator.py`
- [ ] Integration tests with continuity webhook
- [ ] Test graceful degradation (no cache, corrupt cache, API errors)
- [ ] Test combined PR comment formatting
- [ ] Refine validation prompt based on results
- [ ] Document usage in README

---

### Testing Strategy

**Unit Tests** (`tests/test_story_bible_validator.py`):
```python
def test_format_constants_for_validation():
    """Test formatting of constants for prompt."""
    cache = {
        'categorized_facts': {
            'constants': {
                'world_rules': [
                    {'fact': 'Magic exists', 'evidence': 'Academy passage'}
                ],
                'setting': [
                    {'fact': 'City on coast', 'evidence': 'Opening scene'}
                ]
            }
        }
    }

    formatted = format_constants_for_validation(cache)

    assert 'Magic exists' in formatted
    assert 'City on coast' in formatted
    assert 'Academy passage' in formatted

def test_validate_against_story_bible_no_violations():
    """Test validation when passage matches constants."""
    # Mock Ollama API response
    with mock_ollama_response({
        'has_violations': False,
        'severity': 'none',
        'violations': [],
        'summary': 'No issues'
    }):
        result = validate_against_story_bible(
            passage_text="The magical academy stood on the coastal cliffs.",
            story_bible_cache=sample_cache,
            passage_id='test123'
        )

    assert result['has_violations'] is False
    assert result['severity'] == 'none'

def test_validate_against_story_bible_with_violation():
    """Test validation when passage contradicts constants."""
    # Mock Ollama API response
    with mock_ollama_response({
        'has_violations': True,
        'severity': 'critical',
        'violations': [{
            'type': 'setting',
            'severity': 'critical',
            'description': 'City location contradicted',
            'constant_fact': 'City on coast',
            'passage_statement': 'City in mountains'
        }],
        'summary': 'Geography contradiction'
    }):
        result = validate_against_story_bible(
            passage_text="The city was nestled in the mountains.",
            story_bible_cache=sample_cache,
            passage_id='test456'
        )

    assert result['has_violations'] is True
    assert result['severity'] == 'critical'
    assert len(result['violations']) == 1

def test_merge_validation_results():
    """Test merging path and world validation results."""
    path_result = {
        'severity': 'minor',
        'has_issues': True,
        'issues': [{'type': 'character', 'severity': 'minor'}]
    }

    world_result = {
        'severity': 'major',
        'has_violations': True,
        'violations': [{'type': 'setting', 'severity': 'major'}]
    }

    combined = merge_validation_results(path_result, world_result)

    assert combined['severity'] == 'major'  # Takes max severity
    assert combined['has_issues'] is True
    assert combined['world_validation'] is not None
```

**Integration Tests**:
- Test loading Story Bible cache from PR branch
- Test validation in webhook context
- Test combined PR comment formatting
- Test error handling (no cache, corrupt cache, API errors)

**End-to-End Tests**:
1. Create test PR with Story Bible cache
2. Trigger continuity checking
3. Verify combined results in PR comment
4. Verify world validation section appears

---

### Consequences

**Positive**:
1. **Automated world consistency**: Catches contradictions automatically
2. **Combined workflow**: Single check validates both path logic and world facts
3. **Non-blocking**: Missing Story Bible doesn't break continuity checking
4. **Reuses infrastructure**: Same Ollama API, same webhook service
5. **Clear separation**: Validation logic separate from extraction
6. **Gradual adoption**: Authors can enable by extracting Story Bible when ready

**Negative**:
1. **Performance impact**: Adds ~30-60s per path (if sequential)
2. **AI dependency**: Requires Ollama for both path and world validation
3. **Prompt quality**: Validation accuracy depends on prompt engineering
4. **False positives**: May flag stylistic differences as contradictions

**Risks and Mitigations**:

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Validation too slow | High - long PR check times | Start sequential, optimize to parallel if needed |
| False positive violations | Medium - author frustration | Clear severity rubric, conservative validation prompt |
| Missing Story Bible | Low - validation skipped | Clear message in PR comment, docs explain `/extract-story-bible` |
| Cache corruption | Low - validation fails | Validate cache structure, fallback to no validation |
| Ollama API errors | Medium - validation fails | Catch exceptions, log errors, continue without world validation |

---

## References

- **PRD**: `/home/user/NaNoWriMo2025/features/story-bible.md`
- **Related ADRs**:
  - ADR-008: AllPaths Processing Pipeline (pipeline pattern)
  - ADR-001: AllPaths Format (AI integration pattern)
  - ADR-003: Webhook Service (AI prompting, error handling)
- **Related Code**:
  - `formats/allpaths/generator.py` - Pipeline orchestration
  - `scripts/check-story-continuity.py` - Ollama integration
  - `formats/allpaths/modules/output_generator.py` - Jinja2 templates
- **Standards**:
  - `/home/user/NaNoWriMo2025/ARCHITECTURE.md` - System architecture
  - `/home/user/NaNoWriMo2025/STANDARDS.md` - Coding standards
