# ADR-008: AllPaths Processing Pipeline Architecture

## Status

**Accepted and Implemented**

## Context

The AllPaths generator was initially implemented as a monolithic file that handled multiple responsibilities:
- HTML parsing and graph construction
- Path enumeration (DFS traversal)
- Git integration for change detection
- Content categorization
- Multiple output format generation (HTML, clean text, metadata text)
- Validation cache management

**Pain Points That Motivated This ADR**:

1. **Monolithic structure**: Single 1810-line file difficult to understand and maintain
2. **Tightly coupled concerns**: Git operations mixed with path generation, HTML in Python strings
3. **Difficult testing**: Could not test components in isolation
4. **Poor separation**: Intermediate data structures not exposed or reusable
5. **Deprecated code**: Old fingerprint-based categorization still present
6. **Limited extensibility**: Hard to add new output formats or processing steps

**Observations from Path Detection Debugging**:

During the path detection debugging work, the lack of intermediate artifacts made it difficult to:
- Diagnose which stage was producing incorrect results
- Verify that path detection logic was working correctly
- Test changes to git integration without running full pipeline
- Understand data flow through the system

The system needed a clear architecture that would enable:
- Independent testing of each processing stage
- Debugging with intermediate artifacts
- Future extensibility (new output formats, validation types)
- Code reusability across different tools

## Decision

We decided to refactor the AllPaths generator into a **5-stage processing pipeline** with well-defined intermediate artifacts and modular components.

### Processing Pipeline Architecture

```
Stage 1: Parse & Extract
   Input: HTML from Tweego (paperthin format)
   Output: story_graph.json
   Responsibility: Extract clean story structure

Stage 2: Generate Paths
   Input: story_graph.json
   Output: paths.json
   Responsibility: Enumerate all paths (DFS)

Stage 3: Enrich with Git Data
   Input: paths.json + git repository
   Output: paths_enriched.json
   Responsibility: Add git metadata (dates, files)

Stage 4: Categorize Paths
   Input: paths_enriched.json + validation cache
   Output: paths_categorized.json
   Responsibility: Classify as new/modified/unchanged

Stage 5: Generate Outputs
   Input: paths_categorized.json
   Output: HTML browser, text files, updated cache
   Responsibility: Create all output formats
```

### Intermediate Artifacts

**1. story_graph.json** - Clean graph representation
```json
{
  "passages": {
    "Start": {
      "content": "Passage text...",
      "links": ["Continue", "End"]
    },
    "Continue": {
      "content": "More text...",
      "links": ["End"]
    }
  },
  "start_passage": "Start",
  "metadata": {
    "story_title": "Title",
    "ifid": "...",
    "format": "Harlowe",
    "format_version": "3.3.9"
  }
}
```

**2. paths.json** - Pure path enumeration
```json
{
  "paths": [
    {
      "id": "abc12345",
      "route": ["Start", "Continue", "End"],
      "content": {
        "Start": "Passage text...",
        "Continue": "More text...",
        "End": "The end."
      }
    }
  ],
  "statistics": {
    "total_paths": 30,
    "total_passages": 50,
    "avg_path_length": 4.2
  }
}
```

**3. paths_enriched.json** - With git metadata
```json
{
  "paths": [
    {
      "id": "abc12345",
      "route": ["Start", "Continue", "End"],
      "content": {...},
      "git_metadata": {
        "files": ["src/file1.twee", "src/file2.twee"],
        "commit_date": "2025-11-20T...",
        "created_date": "2025-11-02T...",
        "passage_to_file": {
          "Start": "src/file1.twee",
          "Continue": "src/file1.twee",
          "End": "src/file2.twee"
        }
      }
    }
  ]
}
```

**4. paths_categorized.json** - With change classification
```json
{
  "paths": [
    {
      "id": "abc12345",
      "route": ["Start", "Continue", "End"],
      "content": {...},
      "git_metadata": {...},
      "category": "new",
      "validated": false,
      "first_seen": "2025-11-28T..."
    }
  ],
  "statistics": {
    "new": 3,
    "modified": 5,
    "unchanged": 22
  }
}
```

### Module Structure

**Proposed organization** (under `formats/allpaths/`):
```
formats/allpaths/
├── generator.py              # Main orchestrator (stages 1-5)
├── modules/
│   ├── __init__.py
│   ├── parser.py             # Stage 1: HTML → story_graph.json
│   ├── path_generator.py     # Stage 2: story_graph.json → paths.json
│   ├── git_enricher.py       # Stage 3: Add git metadata
│   ├── categorizer.py        # Stage 4: Classify paths
│   └── output_generator.py   # Stage 5: Generate all outputs
├── schemas/
│   ├── story_graph.schema.json
│   ├── paths.schema.json
│   ├── paths_enriched.schema.json
│   └── paths_categorized.schema.json
├── tests/
│   ├── test_parser.py
│   ├── test_path_generator.py
│   ├── test_git_enricher.py
│   ├── test_categorizer.py
│   └── test_output_generator.py
└── README.md
```

## Consequences

### Positive

1. **Modularity**: Each stage can be developed, tested, and debugged independently
2. **Debuggability**: Intermediate artifacts can be inspected to isolate issues
3. **Reusability**: Modules can be reused by other tools (e.g., path analysis scripts)
4. **Testability**: Each module can have comprehensive unit tests
5. **Extensibility**: Easy to add new stages or output formats
6. **Clarity**: Data flow is explicit and well-documented
7. **Maintainability**: Smaller files, clearer responsibilities
8. **Performance**: Can optimize or parallelize individual stages
9. **Documentation**: Schemas serve as API contracts between stages

### Negative

1. **More files**: Complexity spread across multiple modules
2. **Disk I/O**: Writing/reading intermediate artifacts adds overhead
3. **Initial investment**: Refactoring takes time and effort
4. **Learning curve**: New developers must understand pipeline architecture
5. **Coordination**: Changes affecting multiple stages require cross-module updates

### Trade-offs

**Performance vs. Debuggability**:
- Trade: Small overhead from I/O of intermediate artifacts (~1-2 seconds)
- Gain: Ability to inspect and debug each stage independently
- **Decision**: Accept overhead for improved maintainability

**Immediate refactor vs. Incremental migration**:
- Trade: Phased approach takes longer to reach final state
- Gain: Reduced risk, ability to validate approach, no breaking changes
- **Decision**: Use incremental migration path to minimize disruption

**Monolithic vs. Modular**:
- Trade: More files and coordination overhead
- Gain: Better separation of concerns, easier testing
- **Decision**: Modular architecture worth the coordination cost

## Alternatives Considered

### 1. Keep Monolithic Architecture

**Approach**: Leave generator.py as single file, just clean up code

**Rejected because**:
- Doesn't address testability concerns
- Still difficult to debug intermediate states
- Continues to mix concerns (git, HTML, path generation)
- Harder to add new features or output formats

### 2. Split by Output Format

**Approach**: Separate modules for HTML, clean text, metadata text generation

**Rejected because**:
- Doesn't address core complexity (path generation, categorization)
- Still have monolithic processing before output generation
- Doesn't create reusable intermediate artifacts

### 3. Microservices Architecture

**Approach**: Separate services for each stage with API calls

**Rejected because**:
- Overkill for build-time processing
- Adds deployment and networking complexity
- Slower than in-process pipeline
- Not suitable for CI/CD environment

### 4. Database-backed Pipeline

**Approach**: Store intermediate artifacts in SQLite database

**Rejected because**:
- Less transparent than JSON files
- Harder to version control and diff
- Doesn't work well with git-based workflow
- Binary format not human-readable

### 5. Single Refactor (No Phases)

**Approach**: Refactor entire system to 5-stage pipeline immediately

**Rejected because**:
- High risk of breaking existing functionality
- Difficult to validate approach incrementally
- Blocks other work during refactor
- No opportunity to adjust based on learnings

## Implementation Details

### Stage Interfaces

Each stage follows a consistent interface pattern:

```python
def stage_N_process(input_path: Path, output_path: Path, **options) -> Dict:
    """
    Process stage N of the pipeline.

    Args:
        input_path: Path to input artifact (or HTML for stage 1)
        output_path: Path to write output artifact
        **options: Stage-specific options

    Returns:
        Dict with processing statistics and metadata

    Raises:
        ValidationError: If input artifact invalid
        ProcessingError: If stage processing fails
    """
    # 1. Load and validate input
    # 2. Process data
    # 3. Validate output against schema
    # 4. Write output artifact
    # 5. Return statistics
    pass
```

### Error Handling

Each stage validates:
- Input artifact structure (against schema)
- Processing preconditions
- Output artifact structure (against schema)

Errors are caught and reported with:
- Stage name
- Input artifact path
- Specific error message
- Suggested remediation

### Backward Compatibility

During migration:
- Maintain existing generator.py CLI interface
- Keep all existing output files in same locations
- Preserve validation cache format
- No changes to build scripts or CI/CD

Intermediate artifacts are:
- Written to `dist/allpaths-intermediate/` (gitignored)
- Optional (can be disabled for production builds)
- Used for debugging and testing

### Performance Targets

**Current performance** (monolithic):
- Full pipeline: ~10-20 seconds for 30 paths

**Target performance** (5-stage pipeline):
- Stage 1 (Parse): < 1 second
- Stage 2 (Path generation): < 5 seconds
- Stage 3 (Git enrichment): < 3 seconds
- Stage 4 (Categorization): < 2 seconds
- Stage 5 (Output generation): < 5 seconds
- **Total**: < 20 seconds (no worse than current)

With intermediate artifacts I/O: +1-2 seconds acceptable overhead.

## Future Considerations

Potential enhancements enabled by this architecture:

1. **Incremental Processing**: Only regenerate paths affected by changes
2. **Parallel Stages**: Run independent stages concurrently
3. **Alternative Outputs**: Add new formats without touching core pipeline
4. **Custom Validators**: Plugin system for path-specific checks
5. **Path Comparison Tool**: Diff paths across builds using intermediate artifacts
6. **Performance Profiling**: Measure each stage independently
7. **Caching**: Cache stage outputs for unchanged inputs
8. **Alternative Categorizers**: Swap categorization algorithms

### Core Library Migration

**Note**: Stages 1-3 (Parse & Extract, Generate Paths, Enrich with Git Data) contain reusable logic that will migrate to the core library per ADR-012:

- **Stage 1** will become part of core library's `parse_story.py` (produces `story_graph.json`)
- **Stage 2** path enumeration logic is reusable across formats
- **Stage 3** git enrichment provides passage-to-file mapping needed by multiple formats

Stages 4-5 (Categorize Paths, Generate Outputs) remain AllPaths-specific as they implement format-specific concerns (validation cache management, AllPaths HTML/text output).

## Related Work

**Related to existing ADRs**:
- ADR-001: AllPaths Format - This redesign improves the implementation
- ADR-002: Validation Cache - Stage 4 (categorization) consumes this
- ADR-004: Content Hashing - Still used for path IDs, just reorganized

**Deprecates**:
- Multi-phase fingerprint categorization (ADR-002) - Already removed
- Inline HTML generation in Python strings - Will be refactored

## References

- Current generator: `/formats/allpaths/generator.py`
- Build script: `/scripts/build-allpaths.sh`
- Related discussion: Issue/PR for path detection debugging

## Related ADRs

- ADR-001: AllPaths Format for AI Continuity Validation
- ADR-002: Validation Cache Architecture
- ADR-004: Content-Based Hashing for Change Detection
- ADR-012: Core Library and Format Separation Architecture
