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
