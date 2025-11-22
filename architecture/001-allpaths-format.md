# ADR-001: AllPaths Format for AI Continuity Validation

## Status

Accepted

## Context

Interactive fiction with branching narratives can have hundreds or thousands of possible story paths. Each path represents a unique sequence of choices a player might make, and maintaining narrative continuity across all these paths is challenging.

Traditional QA approaches for interactive fiction:
- **Manual playthroughs**: Time-consuming and incomplete (can't cover all paths)
- **Path-by-path review**: Difficult to track which paths have been tested
- **No automation**: Every story change requires manual re-testing

The project needed a way to:
1. Enumerate all possible story paths automatically
2. Make paths accessible for AI-based continuity checking
3. Track which paths have been validated
4. Identify new paths that need review after story updates
5. Provide a browsable interface for manual review

## Decision

We decided to implement a custom Tweego format called **AllPaths** that:

1. **Generates all possible paths** using depth-first search (DFS) through the story graph
2. **Creates multiple output formats**:
   - HTML browser for manual review
   - Clean text files for public deployment
   - Metadata-enriched text files for AI processing
3. **Maintains a validation cache** tracking the status of each path
4. **Uses content-based hashing** to detect changes and categorize paths
5. **Produces stable path IDs** (MD5 hash of route) for tracking across builds

The format is implemented as a Python script that post-processes Tweego's output rather than a native Tweego format module.

## Consequences

### Positive

1. **Complete Coverage**: DFS algorithm guarantees finding all reachable paths from start to end nodes
2. **Incremental Validation**: Cache system allows validating only new/changed paths, saving time
3. **Automated Discovery**: New paths are automatically identified when story structure changes
4. **Multi-Purpose Output**: Same generation process serves human review and AI validation
5. **Version Control Friendly**: Text-based outputs work well with git
6. **Stable References**: MD5-based IDs remain constant when path content unchanged
7. **Flexible Filtering**: Multiple output formats support different use cases

### Negative

1. **Build Time**: Generating all paths adds 10-30 seconds to build time
2. **Exponential Growth**: Path count can explode with loops or complex branching
3. **Memory Usage**: All paths loaded in memory during generation
4. **Not a Native Format**: Requires two-step process (Tweego then Python)
5. **Maintenance Burden**: Custom code to maintain vs. using existing tools

### Trade-offs

**Performance vs. Completeness**: We chose completeness over speed. Generating all paths takes longer but ensures no path is missed.

**Custom Tool vs. Existing Solutions**: We built a custom generator because:
- No existing tools generate all paths from Twee files
- Needed specific output formats for AI processing
- Wanted tight integration with validation cache

**Text Files vs. Database**: We store paths as text files instead of in a database because:
- Easier to version control
- Simpler deployment (no database needed)
- Human-readable for debugging

## Alternatives Considered

### 1. Manual Path Documentation

**Approach**: Document paths manually in a spreadsheet or text file

**Rejected because**:
- Error-prone and quickly outdated
- Doesn't scale with story complexity
- No automation support

### 2. Random Path Sampling

**Approach**: Generate a random subset of paths for validation

**Rejected because**:
- Incomplete coverage
- No guarantee rare paths are tested
- Difficulty tracking which paths validated

### 3. Symbolic Execution

**Approach**: Use symbolic execution tools to analyze story logic

**Rejected because**:
- Too complex for interactive fiction
- Doesn't work well with Harlowe macros
- Overkill for the problem domain

### 4. Native Tweego Format

**Approach**: Implement as a true Tweego format in JavaScript

**Rejected because**:
- Tweego format API is complex
- Python better suited for graph algorithms
- Needed post-processing features (cache management)

### 5. Twine Export + Post-Processing

**Approach**: Export from Twine and process separately

**Rejected because**:
- Adds manual step to workflow
- Breaks CI/CD automation
- Twee files are the source of truth, not Twine

## Implementation Details

**Technology Stack**:
- **Language**: Python 3 (graph algorithms, JSON handling)
- **Input**: Tweego-compiled HTML (paperthin format)
- **Output**: HTML + text files + JSON cache

**Algorithm**:
```
1. Parse Tweego HTML to extract passage graph
2. Identify start passage from StoryData
3. Run DFS from start to all end nodes
4. For each path found:
   a. Generate stable ID (MD5 of route)
   b. Extract passage content
   c. Calculate content fingerprint
   d. Compare with cached version
   e. Categorize as new/modified/unchanged
5. Generate outputs in all formats
6. Update validation cache
```

**Path Categorization**:
- **New**: Path ID not in cache
- **Modified**: Path ID exists but content fingerprint changed
- **Unchanged**: Path ID and fingerprint match cache

## Validation Modes

The decision to support three validation modes (new-only, modified, all) enables:

1. **Fast feedback during development** (new-only mode)
2. **Pre-merge validation** (modified mode)
3. **Full audits after refactoring** (all mode)

This flexible approach balances speed and thoroughness.

## Success Criteria

The AllPaths format is successful if:

1. ✅ All paths are enumerated correctly
2. ✅ New paths are identified automatically
3. ✅ Validation status persists across builds
4. ✅ Build time remains under 2 minutes
5. ✅ Outputs integrate with AI validation
6. ✅ Human-readable browse interface works
7. ✅ Path count scales reasonably with story size

## Future Considerations

Potential improvements:

1. **Incremental Generation**: Only regenerate changed paths
2. **Parallel Processing**: Generate multiple paths concurrently
3. **Cycle Handling**: Better support for story loops
4. **Path Comparison**: Diff tool to show what changed
5. **Custom Validators**: Plugin system for path-specific checks

## References

- AllPaths Generator: `/formats/allpaths/generator.py`
- AllPaths README: `/formats/allpaths/README.md`
- Build Script: `/scripts/build-allpaths.sh`
- GitHub Actions Integration: `.github/workflows/build-and-deploy.yml`

## Related ADRs

- ADR-002: Validation Cache Architecture
- ADR-004: Content-Based Hashing for Change Detection
