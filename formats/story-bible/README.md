# Story Bible Format

A canonical reference of world facts extracted from your interactive fiction story.

## Overview

The Story Bible extracts and organizes facts about your story world, distinguishing between **constants** (always true regardless of player choices) and **variables** (determined by player actions).

### Key Concepts

**Constants** - Facts true in all story paths:
- World Rules: Magic systems, technology level, physical laws
- Setting: Geography, landmarks, historical events
- Character Identities: Names, backgrounds, core traits
- Timeline: Events before the story starts

**Variables** - Facts that depend on player choices:
- Events: What happens during the story
- Character Fates: Outcomes based on player actions
- Relationships: Character dynamics
- Outcomes: Endings and consequences

**Zero Action State** - What happens if the player does nothing:
- Default trajectory for each character
- Baseline for understanding player impact

## Usage

### Basic Usage

Story Bible is generated automatically as part of the build process:

```bash
# Generate as part of full build
npm run build

# Or generate Story Bible separately (requires AllPaths output)
npm run build:story-bible
```

### Prerequisites

1. **AllPaths format must be generated first**:
   ```bash
   npm run build:allpaths
   ```

2. **Ollama service must be running**:
   ```bash
   # Start Ollama service
   ollama serve

   # Verify gpt-oss:20b-fullcontext model is available
   ollama list
   ```

### Outputs

**Human-Readable** - `/dist/story-bible.html`:
- Interactive HTML page
- Organized by category (Constants, Characters, Variables)
- Shows evidence (passage references) for each fact
- Published to GitHub Pages

**Machine-Readable** - `/dist/story-bible.json`:
- Structured JSON format
- Schema documented in `schemas/story-bible.schema.json`
- Can be consumed by AI tools and validation services

**Extraction Cache** - `/story-bible-extraction-cache.json`:
- Caches AI extraction results for performance
- Regenerates only when passage content changes
- Safe to delete (will regenerate on next build)

## Architecture

### 5-Stage Pipeline

Following the AllPaths pattern (ADR-008):

```
Stage 1: Load AllPaths Data
    Input: dist/allpaths-metadata/*.txt
    Output: loaded_paths.json (intermediate)

Stage 2: Extract Facts with AI
    Input: loaded_paths.json
    Output: extracted_facts.json (intermediate)
    Uses: Ollama API (gpt-oss:20b-fullcontext)

Stage 3: Categorize Facts
    Input: extracted_facts.json
    Output: categorized_facts.json (intermediate)
    Logic: Cross-reference facts across paths

Stage 4: Generate HTML
    Input: categorized_facts.json
    Output: dist/story-bible.html
    Template: templates/story-bible.html.jinja2

Stage 5: Generate JSON
    Input: categorized_facts.json
    Output: dist/story-bible.json
    Schema: schemas/story-bible.schema.json
```

### Module Structure

```
formats/story-bible/
├── generator.py              # Main orchestrator
├── modules/
│   ├── loader.py            # Stage 1: Load AllPaths data
│   ├── ai_extractor.py      # Stage 2: AI fact extraction
│   ├── categorizer.py       # Stage 3: Organize facts
│   ├── html_generator.py    # Stage 4: Generate HTML
│   └── json_generator.py    # Stage 5: Generate JSON
├── lib/
│   └── ollama_client.py     # Ollama HTTP API wrapper
├── templates/
│   └── story-bible.html.jinja2  # HTML template
└── schemas/
    └── story-bible.schema.json  # JSON schema
```

## Error Handling

Story Bible generation is a **post-build artifact** and will not block the build pipeline:

- If AllPaths output is missing → Clear error, exits with code 1
- If Ollama service is down → Clear error, exits with code 1
- If AI extraction fails → Logged, build continues without Story Bible
- If individual passage extraction fails → Logged, continues with remaining passages
- If too many failures (>50%) → Fails generation but doesn't block build

The build script uses `|| true` to ensure the main build continues even if Story Bible generation fails.

## Performance

### Extraction Caching

To avoid re-processing unchanged passages:

- Cache key: MD5 hash of passage content
- Cache location: `story-bible-extraction-cache.json` (repo root)
- Invalidation: Automatic when passage content changes

### Typical Performance

- First build: ~2-5 minutes (depending on story size)
- Incremental builds: <1 minute (cached passages)
- Processing rate: ~5-10 passages per minute (AI-dependent)

## Customization

### Modifying the AI Prompt

Edit the extraction prompt in `modules/ai_extractor.py`:

```python
EXTRACTION_PROMPT = """
=== SECTION 1: ROLE & CONTEXT ===
...
"""
```

### Customizing HTML Template

Edit the Jinja2 template in `templates/story-bible.html.jinja2`:

```html
<!DOCTYPE html>
<html lang="en">
...
</html>
```

### Adjusting Categorization

Modify categorization logic in `modules/categorizer.py`:

```python
# Adjust threshold for constants (default: 80% path coverage)
if path_coverage >= 0.8:
    constants_by_type['world_rules'].append(fact_obj)
```

## Troubleshooting

### "AllPaths output not found"

**Problem**: Story Bible requires AllPaths format as input.

**Solution**:
```bash
npm run build:allpaths
npm run build:story-bible
```

### "Ollama service is not available"

**Problem**: Ollama service is not running or not accessible.

**Solution**:
```bash
# Start Ollama
ollama serve

# Verify model is available
ollama list | grep gpt-oss
```

### "Too many extraction failures"

**Problem**: More than 50% of passages failed extraction.

**Possible causes**:
- Ollama service unstable
- Network issues
- Passage content causing AI errors

**Solution**:
- Check Ollama logs
- Try regenerating (failures may be transient)
- Delete cache and retry: `rm story-bible-extraction-cache.json`

### Empty or Sparse Story Bible

**Problem**: Few facts extracted, mostly empty categories.

**Possible causes**:
- Story is very short (not enough content)
- AI extraction not finding facts
- Passages too vague or abstract

**Solution**:
- This is normal for early-stage stories
- Story Bible becomes more useful as content grows
- Review extraction results in cache file to see what AI found

## Testing

### Test Individual Stages

Each module can be tested independently:

```bash
# Test Stage 1: Loader
python3 formats/story-bible/modules/loader.py dist/ --output test_loaded.json

# Test Stage 2: AI Extractor
python3 formats/story-bible/modules/ai_extractor.py test_loaded.json --output test_extracted.json

# Test Stage 3: Categorizer
python3 formats/story-bible/modules/categorizer.py test_extracted.json test_loaded.json --output test_categorized.json

# Test Stage 4: HTML Generator
python3 formats/story-bible/modules/html_generator.py test_categorized.json test_output.html

# Test Stage 5: JSON Generator
python3 formats/story-bible/modules/json_generator.py test_categorized.json test_output.json
```

### Test Full Pipeline

```bash
# Run full generation
python3 formats/story-bible/generator.py dist/

# Check outputs
ls -lh dist/story-bible.html
ls -lh dist/story-bible.json
```

## Related Documentation

- **PRD**: `/features/story-bible.md` - Feature requirements
- **Architecture**: `/architecture/010-story-bible-design.md` - Technical design
- **Standards**: `/STANDARDS.md` - Coding standards
- **AllPaths Format**: `/formats/allpaths/README.md` - Input format

## Future Enhancements (Phase 2)

Planned for future releases:

- **CI Validation**: Validate new content against established constants
- **Contradiction Detection**: Flag contradictions in PR comments
- **Manual Annotations**: Allow authors to override or annotate facts
- **Confidence Scoring**: Improved AI confidence metrics
- **Multi-version Tracking**: Track Story Bible evolution over time

## Contributing

When modifying the Story Bible format:

1. Follow coding standards in `/STANDARDS.md`
2. Update this README if adding new features
3. Update JSON schema if changing output format
4. Test all 5 stages independently
5. Test full pipeline end-to-end

## License

Same as parent project.
