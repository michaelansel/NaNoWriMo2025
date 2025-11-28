# AllPaths Pipeline Implementation Plan

Implementation sequence for ADR-008: AllPaths Processing Pipeline Architecture.

## Phase 1: Incremental Refactoring

Execute these steps in order. Each step should pass all tests before proceeding.

### Step 1.1: Remove Deprecated Fingerprint Code

**Goal**: Delete deprecated fingerprinting functions that are no longer used.

**Files**: `formats/allpaths/generator.py`

**Actions**:
1. Identify all functions marked DEPRECATED in docstrings/comments
2. Verify they are not called anywhere in the codebase
3. Delete the deprecated functions
4. Run tests to confirm nothing breaks

**Expected deprecated functions**:
- `calculate_raw_content_fingerprint`
- `calculate_content_fingerprint`
- `calculate_passage_prose_fingerprint`
- `build_passage_fingerprints`

**NOT deprecated** (actively used in production):
- `calculate_route_hash` - used in categorization logic (lines 1028, 1165)

**Success criteria**:
- All tests pass
- No references to deprecated functions remain
- Code reduction achieved

---

### Step 1.2: Extract HTML Template to Jinja2

**Goal**: Move inline HTML/CSS/JS from Python strings to template file.

**Files**:
- `formats/allpaths/generator.py` (modify)
- `formats/allpaths/templates/allpaths.html.jinja2` (create)
- `formats/allpaths/templates/styles.css` (create, optional)

**Actions**:
1. Create `templates/` directory
2. Extract HTML structure to Jinja2 template
3. Extract CSS to separate file or template block
4. Update generator.py to use Jinja2 rendering
5. Ensure output is identical to current

**Success criteria**:
- HTML output byte-for-byte identical (or functionally equivalent)
- All tests pass
- HTML generation code in generator.py significantly reduced

---

### Step 1.3: Create GitService Abstraction

**Goal**: Consolidate scattered git operations into a single service class.

**Files**:
- `formats/allpaths/generator.py` (modify)
- `formats/allpaths/lib/git_service.py` (create)

**Actions**:
1. Create `lib/` directory
2. Create GitService class with methods:
   - `get_file_commit_date(file_path)`
   - `get_file_creation_date(file_path)`
   - `get_file_content_at_ref(file_path, ref)`
   - `file_has_changes(file_path, base_ref)`
   - `verify_ref_accessible(ref)`
3. Move git subprocess calls from generator.py to GitService
4. Update generator.py to use GitService
5. Add basic tests for GitService

**Success criteria**:
- All git operations go through GitService
- All tests pass
- Easier to mock git operations in tests

---

### Step 1.4: Add Type Hints and Docstrings

**Goal**: Improve code documentation and type safety.

**Files**: `formats/allpaths/generator.py`

**Actions**:
1. Add type hints to all function signatures
2. Add docstrings to functions lacking them
3. Run mypy (if configured) or manual type checking
4. Ensure docstrings describe purpose, args, returns

**Success criteria**:
- All public functions have type hints
- All public functions have docstrings
- Code is more self-documenting

---

### Step 1.5: Group Related Functions

**Goal**: Organize code by logical groupings within the file.

**Files**: `formats/allpaths/generator.py`

**Actions**:
1. Add section comments to delineate groups:
   - HTML Parsing
   - Graph Construction
   - Path Generation
   - Git Integration (now delegating to GitService)
   - Categorization
   - Output Generation
2. Move functions to be near related functions
3. Ensure no functional changes

**Success criteria**:
- Code organized into clear sections
- All tests pass
- Easier to navigate file

---

## Phase 1 Completion Checklist

- [x] Step 1.1: Deprecated code removed
- [x] Step 1.2: HTML extracted to Jinja2
- [x] Step 1.3: GitService created
- [x] Step 1.4: Type hints and docstrings added
- [x] Step 1.5: Code grouped by function

After Phase 1, generator.py should be cleaner and more maintainable, setting the stage for Phase 2 module extraction.

---

## Current Status

**Phase 1 COMPLETE**

Summary of Phase 1 accomplishments:
- Removed 4 deprecated fingerprint functions (~1,600 lines including tests)
- Extracted HTML to Jinja2 template (~508 lines moved)
- Created GitService abstraction with 7 tests
- Added comprehensive type hints and docstrings
- Organized code into 12 logical sections

**Next step**: Phase 2 - 3-Stage Pipeline (when ready to proceed)

---

## Phase 2: 3-Stage Pipeline

Extract parser and output generator into separate modules, proving the pipeline architecture with minimal stages.

Execute these steps in order. Each step should pass all tests before proceeding.

### Step 2.1: Create Modules Directory Structure

**Goal**: Establish directory structure for pipeline modules and schemas.

**Files**:
- `formats/allpaths/modules/__init__.py` (create)
- `formats/allpaths/schemas/` (create directory)
- `formats/allpaths/schemas/story_graph.schema.json` (create)

**Actions**:
1. Create `modules/` directory under `formats/allpaths/`
2. Create `__init__.py` in modules directory
3. Create `schemas/` directory under `formats/allpaths/`
4. Create `story_graph.schema.json` based on ADR-008 specification:
   - Required fields: `passages`, `start_passage`, `metadata`
   - Passages object with content and links
   - Metadata with story_title, ifid, format, format_version
5. Add JSON schema validation utilities if needed

**Success criteria**:
- Directory structure matches ADR-008 proposal
- Schema file validates against JSON Schema specification
- Modules can be imported from `formats.allpaths.modules`

---

### Step 2.2: Extract Parser Module (Stage 1)

**Goal**: Move HTML parsing and graph construction into dedicated parser module that outputs story_graph.json.

**Files**:
- `formats/allpaths/modules/parser.py` (create)
- `formats/allpaths/generator.py` (modify)
- `formats/allpaths/tests/test_parser.py` (create)

**Actions**:
1. Create `modules/parser.py` with Stage 1 interface
2. Move HTML parsing logic from generator.py:
   - Extract graph construction from HTML
   - Extract passage content and link detection
   - Extract metadata extraction (title, IFID, format info)
3. Implement `parse_story(html_path: Path, output_path: Path) -> Dict` function
4. Output story_graph.json matching schema from Step 2.1
5. Create comprehensive tests for parser:
   - Test with sample Tweego HTML
   - Test passage extraction
   - Test link detection
   - Test metadata extraction
   - Test invalid HTML handling
6. Update generator.py to import and use parser module
7. Ensure backward compatibility (same outputs as before)

**Success criteria**:
- Parser module can be tested independently
- story_graph.json validates against schema
- Parser tests achieve >80% code coverage
- All existing generator tests still pass
- Output files identical to pre-refactor version

---

### Step 2.3: Extract Output Generator Module (Stage 5)

**Goal**: Move all output generation (HTML browser, text files) into dedicated module.

**Files**:
- `formats/allpaths/modules/output_generator.py` (create)
- `formats/allpaths/generator.py` (modify)
- `formats/allpaths/tests/test_output_generator.py` (create)

**Actions**:
1. Create `modules/output_generator.py` with Stage 5 interface
2. Move output generation logic from generator.py:
   - HTML browser generation (using Jinja2 templates)
   - Clean text file generation
   - Metadata text file generation
   - Validation cache updates
3. Implement `generate_outputs(paths_categorized: Dict, output_dir: Path, **options) -> Dict` function
4. Input should accept categorized paths data structure (preparing for future Stage 4)
5. Create tests for output generator:
   - Test HTML generation with sample paths
   - Test clean text generation
   - Test metadata text generation
   - Test cache updates
   - Test edge cases (empty paths, single path)
6. Update generator.py to import and use output_generator module
7. Ensure all output files remain in same locations

**Success criteria**:
- Output generator module can be tested independently
- All output formats (HTML, clean text, metadata) generated correctly
- Output generator tests achieve >80% code coverage
- All existing generator tests still pass
- Output files byte-for-byte identical or functionally equivalent

---

### Step 2.4: Update Generator to Orchestrate 3 Stages

**Goal**: Refactor main generator.py to orchestrate parser → core processing → output generation.

**Files**:
- `formats/allpaths/generator.py` (modify)

**Actions**:
1. Restructure main `generate()` function to orchestrate stages:
   - Stage 1: Call parser module → story_graph data
   - Stages 2-4: Current core processing (path gen, git, categorization)
   - Stage 5: Call output_generator module → all outputs
2. Pass data between stages using in-memory structures (JSON serialization optional)
3. Add clear logging for each stage transition
4. Maintain existing CLI interface and arguments
5. Keep error handling and reporting
6. Update internal documentation/comments to reflect 3-stage flow

**Success criteria**:
- Generator.py acts as orchestrator, not monolithic processor
- Clear separation between stages visible in code structure
- All CLI arguments still work as before
- All tests pass
- Build script (`scripts/build-allpaths.sh`) works without changes

---

### Step 2.5: Add Intermediate Artifact Generation Flag

**Goal**: Support optional writing of intermediate artifacts for debugging.

**Files**:
- `formats/allpaths/generator.py` (modify)
- `formats/allpaths/modules/parser.py` (modify)
- `dist/allpaths-intermediate/` (create, gitignore)

**Actions**:
1. Add `--write-intermediate` CLI flag to generator.py
2. Create `dist/allpaths-intermediate/` directory (add to .gitignore)
3. When flag enabled, write intermediate artifacts:
   - `story_graph.json` from Stage 1
   - (Future: paths.json, paths_enriched.json, paths_categorized.json)
4. Update parser module to optionally write story_graph.json
5. Add logging to show where intermediate artifacts are written
6. Update README or docs to explain intermediate artifact debugging workflow
7. Ensure flag is optional (default: disabled for production builds)

**Success criteria**:
- `--write-intermediate` flag writes story_graph.json to dist/allpaths-intermediate/
- story_graph.json validates against schema
- Intermediate artifacts gitignored (not checked into repo)
- Production builds unaffected (no performance impact when disabled)
- Documentation explains how to use intermediate artifacts for debugging

---

## Phase 2 Completion Checklist

- [x] Step 2.1: Directory structure and schema created
- [x] Step 2.2: Parser module extracted
- [x] Step 2.3: Output generator module extracted
- [x] Step 2.4: Generator orchestrates 3 stages
- [x] Step 2.5: Intermediate artifact generation flag added

**Phase 2 COMPLETE**

After Phase 2, the AllPaths generator has a clear 3-stage architecture (parse → process → output) with the parser and output generation fully modularized. The `--write-intermediate` flag enables debugging by writing intermediate artifacts. This proves the pipeline concept and sets the foundation for Phase 3's full 5-stage pipeline.

---

## Phase 3: Full 5-Stage Pipeline

Extract the remaining core processing logic (path generation, git enrichment, categorization) into separate modules, completing the full pipeline architecture with all intermediate artifacts.

Execute these steps in order. Each step should pass all tests before proceeding.

### Step 3.1: Create paths.json Schema and Extract Path Generator Module (Stage 2)

**Goal**: Move path enumeration logic into dedicated module that outputs paths.json.

**Files**:
- `formats/allpaths/schemas/paths.schema.json` (create)
- `formats/allpaths/modules/path_generator.py` (create)
- `formats/allpaths/generator.py` (modify)
- `formats/allpaths/tests/test_path_generator.py` (create)

**Actions**:
1. Create `schemas/paths.schema.json` based on ADR-008 specification:
   - Required fields: `paths` (array), `statistics` (object)
   - Each path object with: `id`, `route` (array), `content` (object mapping passage names to text)
   - Statistics with: `total_paths`, `total_passages`, `avg_path_length`
2. Create `modules/path_generator.py` with Stage 2 interface
3. Move path enumeration logic from generator.py:
   - DFS traversal algorithm (`_dfs` function and related code)
   - Path ID generation (using existing hash function)
   - Route and content extraction for each path
   - Statistics calculation
4. Implement `generate_paths(story_graph: Dict, output_path: Path) -> Dict` function
5. Output paths.json matching schema from step 1
6. Create comprehensive tests for path generator:
   - Test with simple linear story (1 path)
   - Test with branching story (multiple paths)
   - Test with cycles/loops detection
   - Test path ID generation consistency
   - Test statistics calculation accuracy
   - Test empty story handling
7. Update generator.py to import and use path_generator module
8. Ensure backward compatibility (same paths generated as before)

**Success criteria**:
- paths.json validates against schema
- Path generator module can be tested independently
- Path generator tests achieve >80% code coverage
- All existing generator tests still pass
- Path IDs and routes identical to pre-refactor version
- DFS algorithm produces same traversal order

---

### Step 3.2: Create paths_enriched.json Schema and Extract Git Enricher Module (Stage 3)

**Goal**: Move git integration logic into dedicated module that adds git metadata to paths.

**Files**:
- `formats/allpaths/schemas/paths_enriched.schema.json` (create)
- `formats/allpaths/modules/git_enricher.py` (create)
- `formats/allpaths/generator.py` (modify)
- `formats/allpaths/tests/test_git_enricher.py` (create)

**Actions**:
1. Create `schemas/paths_enriched.schema.json` based on ADR-008 specification:
   - Extends paths.json schema
   - Adds `git_metadata` object to each path with:
     - `files` (array of file paths)
     - `commit_date` (ISO timestamp)
     - `created_date` (ISO timestamp)
     - `passage_to_file` (object mapping passage names to file paths)
2. Create `modules/git_enricher.py` with Stage 3 interface
3. Move git integration logic from generator.py:
   - Passage-to-file mapping logic
   - File list extraction per path
   - Commit date calculation (most recent across files)
   - Creation date calculation (earliest across files)
   - Integration with GitService (from Phase 1)
4. Implement `enrich_with_git(paths_data: Dict, tweego_dir: Path, output_path: Path) -> Dict` function
5. Output paths_enriched.json matching schema from step 1
6. Create comprehensive tests for git enricher:
   - Test with mock GitService
   - Test passage-to-file mapping
   - Test date calculation (commit and creation)
   - Test multiple files per path
   - Test single file per path
   - Test error handling for missing files
   - Test paths with no git metadata
7. Update generator.py to import and use git_enricher module
8. Ensure backward compatibility (same git metadata as before)

**Success criteria**:
- paths_enriched.json validates against schema
- Git enricher module can be tested independently
- Git enricher tests achieve >80% code coverage
- All existing generator tests still pass
- Git metadata (dates, files) identical to pre-refactor version
- GitService integration working correctly

---

### Step 3.3: Create paths_categorized.json Schema and Extract Categorizer Module (Stage 4)

**Goal**: Move path categorization logic into dedicated module that classifies paths as new/modified/unchanged.

**Files**:
- `formats/allpaths/schemas/paths_categorized.schema.json` (create)
- `formats/allpaths/modules/categorizer.py` (create)
- `formats/allpaths/generator.py` (modify)
- `formats/allpaths/tests/test_categorizer.py` (create)

**Actions**:
1. Create `schemas/paths_categorized.schema.json` based on ADR-008 specification:
   - Extends paths_enriched.json schema
   - Adds to each path:
     - `category` (enum: "new", "modified", "unchanged")
     - `validated` (boolean)
     - `first_seen` (ISO timestamp)
   - Adds `statistics` object with counts: `new`, `modified`, `unchanged`
2. Create `modules/categorizer.py` with Stage 4 interface
3. Move categorization logic from generator.py:
   - Route hash calculation (reuse existing `calculate_route_hash` function)
   - Validation cache lookup and comparison
   - Category determination (new/modified/unchanged)
   - Validated flag setting
   - First seen date tracking
   - Category statistics aggregation
4. Implement `categorize_paths(paths_enriched: Dict, cache_path: Path, output_path: Path) -> Dict` function
5. Output paths_categorized.json matching schema from step 1
6. Create comprehensive tests for categorizer:
   - Test new path detection (not in cache)
   - Test modified path detection (in cache, different hash)
   - Test unchanged path detection (in cache, same hash)
   - Test validated flag logic
   - Test first_seen date assignment
   - Test statistics calculation
   - Test empty cache handling
   - Test cache loading and validation
7. Update generator.py to import and use categorizer module
8. Ensure backward compatibility (same categorization as before)

**Success criteria**:
- paths_categorized.json validates against schema
- Categorizer module can be tested independently
- Categorizer tests achieve >80% code coverage
- All existing generator tests still pass
- Path categorization (new/modified/unchanged) identical to pre-refactor version
- Validation cache integration working correctly
- Category statistics accurate

---

### Step 3.4: Update Generator to Orchestrate Full 5-Stage Pipeline

**Goal**: Refactor main generator.py to be a minimal orchestrator calling all 5 stage modules in sequence.

**Files**:
- `formats/allpaths/generator.py` (modify)

**Actions**:
1. Restructure main `generate()` function to orchestrate all 5 stages:
   - Stage 1: Call parser module → story_graph data
   - Stage 2: Call path_generator module → paths data
   - Stage 3: Call git_enricher module → paths_enriched data
   - Stage 4: Call categorizer module → paths_categorized data
   - Stage 5: Call output_generator module → all outputs
2. Pass data between stages using in-memory dictionaries (defer JSON I/O to Step 3.5)
3. Add clear logging for each stage transition with timing information
4. Maintain existing CLI interface and all arguments
5. Keep error handling and reporting
6. Update internal documentation/comments to reflect full 5-stage flow
7. Verify generator.py is now primarily orchestration code (minimal processing logic)
8. Ensure each stage module encapsulates its processing logic
9. Remove any remaining processing code that should be in modules

**Success criteria**:
- generator.py acts as pure orchestrator (<400 lines after refactor)
- Clear separation between all 5 stages visible in code structure
- Data flow explicit and documented
- All CLI arguments still work as before
- All tests pass
- Build script (`scripts/build-allpaths.sh`) works without changes
- No regression in functionality or outputs

---

### Step 3.5: Extend --write-intermediate to Write All Intermediate Artifacts

**Goal**: Support writing all 4 intermediate artifacts for complete pipeline debugging.

**Files**:
- `formats/allpaths/generator.py` (modify)
- `formats/allpaths/modules/path_generator.py` (modify)
- `formats/allpaths/modules/git_enricher.py` (modify)
- `formats/allpaths/modules/categorizer.py` (modify)
- `dist/allpaths-intermediate/` (directory, already gitignored)

**Actions**:
1. Update generator.py to pass `--write-intermediate` flag to all stage modules
2. Update path_generator module to optionally write paths.json
3. Update git_enricher module to optionally write paths_enriched.json
4. Update categorizer module to optionally write paths_categorized.json
5. Ensure all intermediate artifacts written to `dist/allpaths-intermediate/`:
   - `story_graph.json` (from Stage 1, already implemented in Phase 2)
   - `paths.json` (from Stage 2)
   - `paths_enriched.json` (from Stage 3)
   - `paths_categorized.json` (from Stage 4)
6. Add logging to show where each intermediate artifact is written
7. Validate each artifact against its schema after writing (optional validation mode)
8. Update documentation to explain complete intermediate artifact debugging workflow
9. Ensure flag remains optional (default: disabled for production builds)

**Success criteria**:
- `--write-intermediate` flag writes all 4 intermediate artifacts
- Each artifact validates against its corresponding schema
- Intermediate artifacts enable stage-by-stage debugging
- Production builds unaffected (no performance impact when disabled)
- Documentation explains how to use artifacts for debugging
- Clear separation: which artifacts come from which stages

---

## Phase 3 Completion Checklist

- [x] Step 3.1: Path generator module extracted with paths.json schema
- [ ] Step 3.2: Git enricher module extracted with paths_enriched.json schema
- [ ] Step 3.3: Categorizer module extracted with paths_categorized.json schema
- [ ] Step 3.4: Generator orchestrates full 5-stage pipeline
- [ ] Step 3.5: All intermediate artifacts written with --write-intermediate flag

After Phase 3, the AllPaths generator will have a complete 5-stage modular pipeline with all intermediate artifacts defined and testable. Each stage (parse, generate paths, enrich with git, categorize, output) will be independently testable and debuggable. The `--write-intermediate` flag will enable full visibility into the pipeline for debugging and validation.

---
