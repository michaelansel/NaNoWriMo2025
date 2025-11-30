# ADR-010: Story Bible Architecture

## Status

**Proposed** - Awaiting implementation (Phase 1: Informational Tool)

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
