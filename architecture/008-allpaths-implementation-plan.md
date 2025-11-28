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
