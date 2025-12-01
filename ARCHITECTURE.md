# System Architecture

## Overview

NaNoWriMo2025 is an interactive fiction project built using Twee3/Tweego with Harlowe 3.3.9. The project implements a sophisticated build, validation, and deployment pipeline that combines:

- **Interactive Fiction Development**: Twee source files compiled with Tweego
- **Multi-Format Output**: HTML playable story, static site deployment, and AllPaths format
- **AI-Powered Validation**: Automated continuity checking using Ollama
- **CI/CD Pipeline**: GitHub Actions for build, test, and deployment
- **Webhook Service**: Real-time AI validation feedback on pull requests
- **Core Library Separation**: Reusable parsing and graph construction shared across formats (see ADR-012)
- **Constraint-Based Pipeline Categories**: Tools categorized by constraints (CI Build, Webhook AI, Local Dev)

## System Components

### 1. Source Files (Twee3)

**Location**: `/src/*.twee`

Story content is written in Twee3 format, a plain-text markup language for interactive fiction:

- **Format**: Twee3 with Harlowe 3.3.9 macros
- **Structure**: Passages (story nodes) with links between them
- **Metadata**: StoryData passage defines title, IFID, and start passage
- **Organization**: Separate .twee files for different story branches or days

### 2. Build System

**Location**: `/scripts/build-*.sh`, `package.json`

#### Primary Build Pipeline

**Script**: `scripts/build-allpaths.sh`

1. **Tweego Compilation**: Compiles Twee source to intermediate HTML
   - Uses `paperthin-1` format to extract story data
   - Produces temporary HTML with passage graph

2. **AllPaths Generation**: Python generator creates multiple outputs
   - Browersable HTML interface
   - Clean prose text files
   - Metadata-enriched text files for AI
   - Validation status cache

3. **Resource Generation**: Automated passage tracking
   - Script: `scripts/generate-resources.sh`
   - Extracts passage names and links from source files
   - Generates `Resource-Passage Names` reference file

#### Build Outputs

**Constraint Category: CI Build** - All outputs are generated deterministically without Ollama

```
dist/
├── index.html                         # Harlowe playable story (main output)
├── proofread.html                     # Paperthin format for proofreading
├── allpaths.html                      # Interactive browser for all story paths
├── allpaths-clean/*.txt               # Clean prose (public deployment)
├── allpaths-metadata/*.txt            # With metadata (AI validation)
├── allpaths-passage-mapping.json      # Random ID to passage name mapping
├── metrics.html                       # Writing metrics and statistics
├── story-bible.html                   # Story Bible (rendered from cache)
└── landing/index.html                 # Landing page with links to all formats

allpaths-validation-status.json        # Validation cache (repository root)
```

### 3. AllPaths Format Generator

**Location**: `/formats/allpaths/generator.py`, `/formats/allpaths/modules/`

**Purpose**: Generate all possible story paths for AI-based continuity validation

**Architecture**: 5-Stage Modular Processing Pipeline

The AllPaths generator implements a modular pipeline that transforms Tweego HTML output into multiple formats through five distinct processing stages. Each stage has well-defined inputs/outputs and can be tested independently.

**Pipeline Stages**:

1. **Stage 1: Parse & Extract** (`modules/parser.py`)
   - Input: HTML from Tweego (paperthin format)
   - Output: `story_graph.json` - Clean story structure
   - Responsibility: Extract passages, links, and metadata from HTML
   - **Note**: Candidate for core library extraction (see ADR-012)

2. **Stage 2: Generate Paths** (`modules/path_generator.py`)
   - Input: `story_graph.json`
   - Output: `paths.json` - All possible story paths
   - Responsibility: DFS traversal to enumerate paths, generate stable IDs
   - **Note**: Candidate for core library extraction (see ADR-012)

3. **Stage 3: Enrich with Git Data** (`modules/git_enricher.py`)
   - Input: `paths.json` + git repository
   - Output: `paths_enriched.json` - Paths with git metadata
   - Responsibility: Add file associations, commit dates, passage-to-file mapping
   - **Note**: Candidate for core library extraction (see ADR-012)

4. **Stage 4: Categorize Paths** (`modules/categorizer.py`)
   - Input: `paths_enriched.json` + validation cache
   - Output: `paths_categorized.json` - Classified paths
   - Responsibility: Classify as new/modified/unchanged using git-based detection
   - **Note**: AllPaths-specific, remains in format module

5. **Stage 5: Generate Outputs** (`modules/output_generator.py`)
   - Input: `paths_categorized.json`
   - Output: HTML browser, clean text, metadata text, updated cache
   - Responsibility: Create all output formats with random ID substitution
   - **Note**: AllPaths-specific, remains in format module

**Orchestrator**: `generator.py` coordinates all five stages and manages the pipeline flow.

**Key Features**:
- **Modular Design**: Each stage is independently testable (32+ tests, >80% coverage per module)
- **Intermediate Artifacts**: Four JSON artifacts with documented schemas for debugging
- **Git-based Change Detection**: Uses git diff for accurate path categorization
- **Path Categorization**: Classifies paths as new/modified/unchanged
- **Random ID Substitution**: Replaces passage names with random hex IDs for AI
- **Passage Mapping**: Maintains bidirectional ID-to-name mapping
- **Debugging Support**: `--write-intermediate` flag writes all 4 intermediate artifacts

**Module Structure**:
```
formats/allpaths/
├── generator.py              # Main orchestrator
├── modules/
│   ├── parser.py             # Stage 1: HTML → story_graph.json
│   ├── path_generator.py     # Stage 2: story_graph.json → paths.json
│   ├── git_enricher.py       # Stage 3: Add git metadata
│   ├── categorizer.py        # Stage 4: Classify paths
│   └── output_generator.py   # Stage 5: Generate all outputs
├── schemas/                  # JSON schemas for all 4 intermediate artifacts
├── lib/git_service.py        # Git abstraction layer
└── tests/                    # Comprehensive test suite
```

**Data Flow**:
```
Tweego HTML
    ↓
Stage 1: Parse → story_graph.json
    ↓
Stage 2: Generate Paths → paths.json
    ↓
Stage 3: Git Enrich → paths_enriched.json
    ↓
Stage 4: Categorize → paths_categorized.json
    ↓
Stage 5: Generate Outputs → HTML browser, text files, cache
```

**Algorithm**:
```
Input: Story graph from Tweego
Process:
  1. Parse HTML into structured graph (Stage 1)
  2. DFS traversal from start to all end nodes (Stage 2)
  3. Enrich paths with git metadata (Stage 3)
  4. Use git diff to categorize paths (Stage 4)
  5. Generate outputs in multiple formats (Stage 5)
Output: HTML browser, text files, validation cache
```

**Time Complexity**: O(V + E) where V = passages, E = links
**Space Complexity**: O(V) for recursion stack
**Performance**: <20 seconds for 30 paths (within target)

See `architecture/008-allpaths-processing-pipeline.md` for complete architecture documentation and design rationale.

### 4. AI Continuity Validation

**Location**: `/scripts/check-story-continuity.py`

**Purpose**: AI-powered story continuity checking using Ollama

**Architecture**:
- **Validation Modes**: Supports new-only, modified, and all modes
- **Ollama Integration**: HTTP API calls to local Ollama instance
- **Progress Tracking**: Real-time callbacks for incremental updates
- **Cancellation Support**: Threading events for job cancellation
- **Result Caching**: Persistent validation status

**Validation Modes**:
1. **new-only** (default): Only brand new paths
2. **modified**: New and modified paths
3. **all**: Full validation of all paths

**Data Flow**:
```
Text files (allpaths-metadata/) + Validation cache
    ↓
Categorize paths (new/modified/unchanged)
    ↓
Filter by validation mode
    ↓
For each path:
  - Load story text
  - Send to Ollama HTTP API
  - Parse JSON response
  - Translate passage IDs back to names
  - Update validation cache
    ↓
Return structured results
```

**Security Features**:
- **Prompt Injection Protection**: Validates AI responses for suspicious patterns
- **Content Sanitization**: Removes malicious markdown/XSS from AI output
- **Text-only Processing**: Never executes code from story content

### 5. Story Bible Generation

**Location**: `/formats/story-bible/`, `/services/lib/story_bible_extractor.py`

**Purpose**: AI-powered extraction of world constants, variables, and character information

**Architecture**: Two-Phase Model (see ADR-012)

The Story Bible implements a two-phase architecture:
- **Render Phase (CI Build)**: Deterministic HTML generation from cache, no Ollama required
- **Extract Phase (Webhook AI)**: Async AI extraction updates cache for future renders

This allows fast CI builds while still leveraging AI benefits. The generator consumes core library artifacts (`passages_deduplicated.json`) instead of depending on AllPaths format output.

**Two-Phase Pipeline**:

**Phase 1: Render (CI Build - Deterministic)**
1. **Load Cache** - Read validated_nouns.json (persistent cache)
2. **Render HTML** - Generate story-bible.html using Jinja2 template
3. **Output** - Deploy story-bible.html to GitHub Pages

**Phase 2: Extract (Webhook AI - Async)**
1. **Load Passages** - Read from core library artifact `passages_deduplicated.json`
2. **AI Extraction** - Call Ollama to extract constants, variables, character states (per passage)
3. **AI Summarization** - Deduplicate and merge facts across passages
4. **Update Cache** - Write validated_nouns.json for next render
5. **Commit Cache** - PR commit triggers next CI build with updated cache

**Data Flow**:
```
CI Build (Render Phase):
  validated_nouns.json (cache)
    ↓
  Jinja2 template
    ↓
  story-bible.html (deployed)

Webhook (Extract Phase):
  passages_deduplicated.json (core library artifact)
    ↓
  Ollama AI extraction
    ↓
  AI summarization & deduplication
    ↓
  validated_nouns.json (updated cache)
```

**Cache Structure**:
```json
{
  "passage_extractions": { "passage_id": { "facts": [...] } },
  "summarized_facts": { "constants": {...}, "characters": {...} },
  "categorized_facts": { "...", "per_passage": {...} }
}
```

**Key Features**:
- **Two-level cache**: Per-passage (detailed) + summarized (unified)
- **Evidence preservation**: Every fact cites source passages with quotes
- **Conservative deduplication**: When uncertain, keep facts separate
- **Conflict detection**: Contradictions flagged, not auto-resolved
- **Cache-first build**: HTML renders from cache, no Ollama in CI
- **Graceful fallback**: Uses per-passage data if summarization fails

**Ollama Configuration**:
- Model: `gpt-oss:20b-fullcontext`
- Thinking mode: `think: "low"` (reduces token consumption)
- Extraction timeout: 120 seconds per passage
- Summarization timeout: 300 seconds

See `architecture/010-story-bible-design.md` for complete design documentation.

### 6. Writing Metrics & Statistics

**Location**: `/scripts/calculate-metrics.py`, `/formats/metrics/`

**Purpose**: Word count statistics and writing progress tracking

**Constraint Category**: CI Build (deterministic, no Ollama)

**Features**:
- Total word count across Twee source files
- Passage statistics (min/mean/median/max words per passage)
- File statistics (min/mean/median/max words per file)
- Distribution buckets (0-100, 101-300, 301-500, 501-1000, 1000+ words)
- Top N longest passages
- CLI output (text) and HTML output (metrics.html)

**Future Enhancement**: Will consume `story_graph.json` from core library (see ADR-012)

See `architecture/009-writing-metrics-design.md` for complete design documentation.

### 7. Landing Page

**Location**: `/formats/landing/`

**Purpose**: Central navigation hub linking to all output formats

**Constraint Category**: CI Build (static HTML generation)

**Features**:
- Links to all formats (Harlowe story, AllPaths, Metrics, Story Bible, Proofread)
- Descriptions of each format and its intended use
- Consistent styling with other formats

See `architecture/011-landing-page-design.md` for complete design documentation.

### 8. Twee Linter

**Location**: `/scripts/lint-twee.py` (planned)

**Purpose**: Static analysis and quality checks for Twee source files

**Constraint Category**: CI Build (gating check that blocks merge)

**Planned Features**:
- Passage name validation
- Dead-end detection (passages with no links)
- Unreachable passage detection
- Duplicate passage detection
- Link target validation (ensure all link targets exist)
- Style consistency checks

See `architecture/twee-linter-design.md` for design documentation.

---

### 9. Webhook Service

**Location**: `/services/continuity-webhook.py`

**Purpose**: GitHub webhook receiver for automated AI validation on PRs

**Architecture**:
- **Flask Web Service**: Listens on port 5000 (configurable)
- **Asynchronous Processing**: Background threads for long-running checks
- **GitHub Integration**: Downloads artifacts, posts comments
- **Job Management**: Tracks active jobs, cancels superseded checks

**Security**:
- **Webhook Signature Verification**: HMAC-SHA256 validation
- **Artifact Validation**: Structure and size checks before processing
- **Path Traversal Protection**: Validates ZIP file extraction paths
- **SSRF Prevention**: Validates artifact URLs are from GitHub
- **Authorization**: Only collaborators can approve paths

**Data Flow**:
```
GitHub Actions → Workflow completes → Sends webhook
    ↓
Webhook Service receives event
    ↓
Verify HMAC signature
    ↓
Download story-preview artifact (ZIP)
    ↓
Extract and validate artifact structure
    ↓
Load validation cache and passage mapping
    ↓
Determine paths to check (based on mode)
    ↓
Post initial comment with path list
    ↓
For each path (with cancellation checks):
  - Run AI continuity check
  - Post progress update to PR
    ↓
Post final summary comment
    ↓
Update job metrics
```

**Endpoints**:
- `POST /webhook`: Receives GitHub webhooks
- `GET /health`: Health check (token status, config validation)
- `GET /status`: Live metrics (active jobs, statistics)

**GitHub App Support**:
- Primary authentication via GitHub App (JWT + installation token)
- Fallback to Personal Access Token
- Token caching with automatic refresh

**PR Commands**:
- `/check-continuity [mode]`: Trigger validation with specific mode
- `/approve-path <id1> <id2> ...`: Mark paths as validated
- `/approve-path all`: Approve all checked paths
- `/approve-path new`: Approve all new paths

### 10. GitHub Actions Pipeline

**Location**: `/.github/workflows/build-and-deploy.yml`

**Trigger Events**:
- Push to main branch
- Pull requests
- Manual workflow dispatch

**Build Steps**:
1. **Checkout**: Clone repository
2. **Setup**: Install dependencies (Node.js, Tweego)
3. **Build Story**: Compile Twee to playable HTML
4. **Build AllPaths**: Generate all story paths
5. **Upload Artifacts**: Package build outputs
6. **Deploy**: GitHub Pages deployment (main branch only)
7. **Webhook**: Triggers continuity check service

**Artifact Structure**:
```
story-preview/
├── dist/
│   ├── allpaths.html
│   ├── allpaths-clean/
│   ├── allpaths-metadata/
│   └── allpaths-passage-mapping.json
└── allpaths-validation-status.json
```

## Data Flow

### Development Workflow

```
Developer writes story (.twee files)
    ↓
Commit and push to feature branch
    ↓
Open pull request
    ↓
GitHub Actions runs build
    ↓
Uploads story-preview artifact
    ↓
Workflow completes successfully
    ↓
GitHub sends webhook to continuity service
    ↓
Service downloads artifacts
    ↓
Runs AI validation (new-only mode)
    ↓
Posts real-time progress comments
    ↓
Posts final summary
    ↓
Developer reviews feedback
    ↓
Developer can run /check-continuity modified for broader check
    ↓
Developer approves paths with /approve-path
    ↓
Service commits updated cache to PR branch
    ↓
Merge to main when ready
    ↓
Deploy to GitHub Pages
```

### Validation Cache Lifecycle

```
Build starts
    ↓
Load existing allpaths-validation-status.json
    ↓
Generate all paths with DFS
    ↓
For each path:
  - Calculate content fingerprint
  - Compare with cached fingerprint
  - Categorize as new/modified/unchanged
  - Preserve validated status if unchanged
    ↓
Save updated cache with all paths
    ↓
Include cache in build artifacts
    ↓
AI validation uses cache to filter paths
    ↓
AI updates cache with validation results
    ↓
Developer approves paths (updates cache)
    ↓
Cache committed back to repository
```

## Design Principles and Patterns

### 1. Content-Based Hashing

**Principle**: Path identity and change detection based on content, not structure

**Implementation**:
- **Path ID**: MD5 hash of passage route (8-char hex)
- **Content Fingerprint**: Hash of prose content (excluding link text)
- **Raw Content Fingerprint**: Hash including link text

**Benefits**:
- Stable IDs across builds
- Automatic change detection
- Efficient incremental validation

### 2. Separation of Concerns

**Structure**:
- **Source**: Twee files (story content only)
- **Build**: Scripts (transformation logic)
- **Validation**: Separate service (quality assurance)
- **Deployment**: GitHub Actions (automation)

**Benefits**:
- Clear responsibilities
- Testable components
- Independent scaling

### 3. Progressive Enhancement

**Layers**:
1. **Core Story**: Playable in browser
2. **AllPaths Browser**: Enhanced review interface
3. **AI Validation**: Automated quality checks
4. **Webhook Integration**: Real-time PR feedback

**Benefits**:
- Works at every layer
- Optional enhancements
- Graceful degradation

### 4. Asynchronous Processing

**Pattern**: Fire-and-forget with status tracking

**Implementation**:
- Webhook returns 202 Accepted immediately
- Processing happens in background thread
- Real-time progress updates via PR comments
- Status endpoint for monitoring

**Benefits**:
- Webhook timeouts avoided
- Better user experience
- Resource management

### 5. Validation Modes

**Pattern**: Selective processing based on change category

**Implementation**:
- **new-only**: Fast feedback during development
- **modified**: Pre-merge validation
- **all**: Full audit after major changes

**Benefits**:
- Faster validation cycles
- Efficient resource usage
- Flexible quality gates

### 6. Security in Depth

**Layers**:
1. **Webhook Signature Verification**: Prevent spoofing
2. **Artifact Validation**: Check structure and size
3. **Path Traversal Protection**: Validate ZIP extraction
4. **SSRF Prevention**: Validate artifact URLs
5. **Content Sanitization**: Clean AI output
6. **Authorization**: Verify collaborator status

**Benefits**:
- Multiple failure points for attacks
- Reduced attack surface
- Safe PR processing

## Deployment Architecture

### Production Environment

**GitHub Pages**:
- **URL**: `https://<username>.github.io/NaNoWriMo2025/`
- **Content**: Static HTML story files
- **Updates**: Automatic on main branch push
- **SSL**: GitHub-provided HTTPS

**Webhook Service**:
- **Host**: Self-hosted server (user systemd service)
- **Runtime**: Gunicorn WSGI server
- **Reverse Proxy**: Nginx or Caddy for HTTPS
- **SSL**: Let's Encrypt automatic renewal
- **Monitoring**: `/health` and `/status` endpoints

**Ollama Service**:
- **Host**: Same server as webhook service
- **Model**: gpt-oss:20b-fullcontext
- **API**: HTTP on localhost:11434
- **Timeout**: 300 seconds per path

### Development Environment

**Local Build**:
```bash
npm install          # Install dependencies
npm run build        # Build playable story
npm run build:allpaths  # Generate all paths
```

**Local Validation**:
```bash
python3 scripts/check-story-continuity.py \
  dist/allpaths-metadata \
  allpaths-validation-status.json
```

**Service Development**:
```bash
cd services
source venv/bin/activate
python3 continuity-webhook.py  # Run webhook service locally
```

## Technology Choices and Rationale

### Twee3 + Tweego

**Choice**: Twee3 format with Tweego compiler

**Rationale**:
- Plain text format works well with git
- No proprietary tools required
- Supports Harlowe (accessible, natural-language macro system)
- Command-line compilation for CI/CD
- Open source and actively maintained

**Alternatives Considered**:
- Twine GUI: Not suitable for version control
- Ink: Different syntax, less macro support
- ChoiceScript: Proprietary, limited customization

### Python for Build Tools

**Choice**: Python 3.12+ for generator and validation scripts

**Rationale**:
- Excellent JSON/HTML parsing libraries
- Simple DFS implementation
- Cross-platform compatibility
- Good HTTP client libraries (requests)
- Native regex and hashing support

**Alternatives Considered**:
- JavaScript/Node.js: Already used for Tweego, avoid mixing
- Bash: Too complex for graph algorithms
- Go: Overkill for scripting tasks

### Flask for Webhook Service

**Choice**: Flask lightweight web framework

**Rationale**:
- Simple webhook receiver pattern
- Easy background threading
- Built-in request parsing
- Minimal dependencies
- Well-documented

**Alternatives Considered**:
- FastAPI: Overkill for simple webhooks
- Django: Too heavy for this use case
- Direct socket server: More complex

### GitHub Actions

**Choice**: GitHub Actions for CI/CD

**Rationale**:
- Native GitHub integration
- Free for public repositories
- Built-in artifact storage
- Webhook event integration
- Secret management

**Alternatives Considered**:
- Jenkins: Requires self-hosting
- GitLab CI: Not using GitLab
- Travis CI: Less integrated with GitHub

### Ollama for AI

**Choice**: Ollama local inference engine

**Rationale**:
- Self-hosted (data privacy)
- HTTP API (simple integration)
- Multiple model support
- No API costs
- Works offline

**Alternatives Considered**:
- OpenAI API: Cost, data privacy concerns
- Claude API: Cost, rate limits
- HuggingFace: More complex setup

### MD5 for Path Hashing

**Choice**: MD5 for path identification

**Rationale**:
- Not used for security (collision resistance not critical)
- Fast computation
- Stable across platforms
- Short 8-char hex IDs
- Standard library support

**Alternatives Considered**:
- SHA256: Overkill, longer output
- UUID: Non-deterministic
- Sequential numbering: Unstable across builds

## Scalability Considerations

### Current Limitations

- **Single-threaded AI validation**: One path at a time per PR
- **Ollama local inference**: Limited by local hardware
- **In-memory job tracking**: Lost on service restart
- **No job queue**: PRs processed as webhooks arrive

### Future Scalability

**If path count grows significantly**:
- Parallel AI validation with worker pool
- Distributed Ollama instances
- Redis for job queue and state
- Database for validation history

**If PR volume increases**:
- Job queue with priority
- Multiple webhook service instances
- Load balancer for distribution
- Shared cache storage (S3/Redis)

## Dependencies

### Runtime Dependencies

**Build System**:
- Node.js (package management)
- Tweego (story compilation)
- Python 3.12+ (generators and scripts)

**Webhook Service**:
- Python 3.12+
- Flask (web framework)
- requests (HTTP client)
- PyJWT (GitHub App authentication)
- Ollama (AI inference)

**Deployment**:
- GitHub Actions (CI/CD)
- GitHub Pages (hosting)
- Nginx/Caddy (reverse proxy)
- systemd (service management)

### Development Dependencies

- git (version control)
- npm (package management)
- OpenSSL (webhook secret generation)
- Let's Encrypt (SSL certificates)

## Monitoring and Observability

### Webhook Service

**Health Check**:
```bash
curl https://your-server.com/health
```

**Live Metrics**:
```bash
curl https://your-server.com/status
```

**Logs**:
```bash
journalctl --user -u continuity-webhook -f
```

### GitHub Actions

**Workflow Status**: Repository Actions tab
**Artifact Downloads**: Available from workflow runs
**Deployment Status**: GitHub Pages settings

### AI Validation

**Progress Updates**: Real-time PR comments
**Final Summary**: Comprehensive PR comment with all results
**Validation Cache**: Git-tracked status file

## Error Handling

### Build Failures

**Tweego compilation errors**:
- Fail workflow immediately
- Show error in GitHub Actions log
- No artifacts uploaded

**Python script errors**:
- Logged to stderr
- Return non-zero exit code
- Workflow fails, no deployment

### Webhook Service Errors

**Signature verification failure**:
- Return 401 Unauthorized
- Log security warning
- No processing occurs

**Artifact download failure**:
- Log error
- No PR comment posted
- Job marked as failed

**AI validation errors**:
- Catch per-path exceptions
- Post generic error to PR
- Continue with remaining paths
- Update job metrics

### Recovery Mechanisms

**Service restart**:
- Active jobs lost (by design)
- Re-run checks manually with `/check-continuity`

**Cache corruption**:
- Delete `allpaths-validation-status.json`
- Next build recreates with all paths as "new"

**Ollama timeout**:
- Per-path 300s timeout
- Skip path, continue with others
- Report timeout in PR comment

## Testing Strategy

### Build Testing

**Local testing**:
```bash
npm run build
npm run build:allpaths
```

**Validation**:
- Check dist/ outputs exist
- Verify allpaths.html opens
- Review validation cache structure

### Webhook Service Testing

**Health check**:
```bash
curl http://localhost:5000/health
```

**Local AI check**:
```bash
python3 scripts/check-story-continuity.py \
  dist/allpaths-metadata \
  allpaths-validation-status.json
```

**Simulated webhook**:
- Generate HMAC signature
- POST to /webhook endpoint
- Monitor logs for processing

### Integration Testing

**PR workflow**:
1. Create test branch
2. Modify passage
3. Open PR
4. Verify workflow runs
5. Check webhook receives event
6. Verify PR comments posted
7. Test approval flow

## Documentation

### User Documentation

- **README.md**: Project overview and setup
- **features/*.md**: Feature specifications
- **formats/allpaths/README.md**: AllPaths format guide
- **services/README.md**: Webhook service setup

### Developer Documentation

- **ARCHITECTURE.md**: This document
- **STANDARDS.md**: Coding and documentation standards
- **architecture/*.md**: Architecture decision records

### API Documentation

- **Webhook service**: Inline docstrings in Python
- **Generator**: Inline comments in generator.py
- **Build scripts**: Header comments in shell scripts
