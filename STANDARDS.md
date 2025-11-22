# Coding and Documentation Standards

## Overview

This document defines the coding standards, naming conventions, documentation requirements, and quality gates for the NaNoWriMo2025 project.

## File Organization

### Directory Structure

```
NaNoWriMo2025/
├── src/                           # Story source files (.twee)
├── dist/                          # Build outputs (gitignored)
├── formats/                       # Custom Tweego formats
│   └── allpaths/
│       ├── generator.py           # Path generation engine
│       ├── README.md              # Format documentation
│       └── *.md                   # Design docs
├── scripts/                       # Build and utility scripts
│   ├── build-*.sh                 # Build scripts
│   ├── generate-*.sh              # Generation scripts
│   └── *.py                       # Python utilities
├── services/                      # Long-running services
│   ├── continuity-webhook.py      # Webhook service
│   ├── setup.sh                   # Service installation
│   └── README.md                  # Service documentation
├── .github/
│   └── workflows/
│       └── build-and-deploy.yml   # CI/CD pipeline
├── features/                      # Feature specifications
├── architecture/                  # Architecture decision records
├── VISION.md                      # CEO-level vision
├── PRIORITIES.md                  # Strategic priorities
├── PRINCIPLES.md                  # Guiding principles
├── ROADMAP.md                     # Product roadmap
├── ARCHITECTURE.md                # System architecture
├── STANDARDS.md                   # This document
└── README.md                      # Project overview
```

### File Naming Conventions

**Twee Story Files** (`/src`):
- Format: `{prefix}-{YYMMDD}.twee`
- Examples: `KEB-251102.twee`, `KEB-251103.twee`
- Prefix: Author initials or story arc identifier
- Date: Creation date in YYMMDD format
- Purpose: Easy chronological sorting and author identification

**Build Scripts** (`/scripts`):
- Format: `build-{purpose}.sh` or `generate-{purpose}.sh`
- Examples: `build-allpaths.sh`, `generate-resources.sh`
- Lowercase with hyphens
- Descriptive action verb + purpose

**Python Scripts** (`/scripts`, `/formats`):
- Format: `{purpose}-{detail}.py` or `{module}.py`
- Examples: `check-story-continuity.py`, `generator.py`
- Lowercase with hyphens (follows script naming)
- Use underscores for Python modules only when imported

**Services** (`/services`):
- Format: `{service-name}.py`
- Example: `continuity-webhook.py`
- Lowercase with hyphens
- Match systemd service name

**Documentation Files**:
- Format: `{TOPIC}.md` or `{topic}.md`
- CEO/PM docs: UPPERCASE (VISION.md, ROADMAP.md)
- Technical docs: UPPERCASE for root-level (ARCHITECTURE.md, STANDARDS.md)
- Feature docs: lowercase with hyphens (github-web-editing.md)
- README files: Always `README.md`

**Configuration Files**:
- Format: Standard names (`.gitignore`, `package.json`)
- Workflow files: `{purpose}.yml`
- Follow ecosystem conventions

### Organization Principles

**Separation by Concern**:
- Source content in `/src`
- Build logic in `/scripts` and `/formats`
- Services in `/services`
- Documentation at appropriate levels

**Co-location**:
- Documentation lives with the code it documents
- Format docs in `/formats/allpaths/`
- Service docs in `/services/`

**Single Responsibility**:
- One script = one job
- One service = one concern
- One format = one output type

## Naming Conventions

### Variables and Functions

**Python**:
```python
# Variables: snake_case
validation_cache = {}
path_id = "abc12345"
has_issues = False

# Functions: snake_case
def check_path_continuity(path_text: str) -> Dict:
    pass

def load_validation_cache(cache_path: Path) -> Dict:
    pass

# Constants: UPPERCASE_SNAKE_CASE
OLLAMA_MODEL = "gpt-oss:20b-fullcontext"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MAX_TEXT_FILE_SIZE = 1024 * 1024

# Private functions: Leading underscore
def _validate_internal_state() -> bool:
    pass

# Classes: PascalCase (if needed)
class ValidationCache:
    pass
```

**Shell Scripts**:
```bash
# Variables: UPPERCASE_SNAKE_CASE for environment/config
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$PROJECT_DIR/dist"

# Local variables: lowercase_snake_case
temp_file="temp.html"
output_dir="dist/"

# Functions: lowercase_snake_case
function build_story() {
    # ...
}
```

**Twee/SugarCube**:
```twee
:: PassageName [tags]
Passage content with Twee syntax

[[Link Text|DestinationPassage]]
```

### Passage Names

**Format**: Descriptive names with optional prefixes
- **Examples**: `Start`, `Continue on`, `Day 5 KEB`, `Metal object`
- **Spaces**: Allowed and encouraged for readability
- **Tags**: Use square brackets for passage metadata
- **Special passages**: `StoryData`, `StoryInit`, etc. (SugarCube conventions)

**Conventions**:
- Use natural language
- Be specific but concise
- Include timeline markers when relevant (`Day 5 KEB`)
- Use consistent prefixes for related passages

### Path Identifiers

**Format**: 8-character lowercase hex hash
- **Example**: `6e587dcb`, `1bf824a1`
- **Generation**: First 8 chars of MD5 hash of route
- **Stability**: Same path = same ID across builds
- **Usage**: Filenames (`path-6e587dcb.txt`), cache keys, PR commands

### API Endpoints

**Webhook Service**:
```
POST /webhook          # Receive GitHub webhooks
GET  /health           # Health check
GET  /status           # Live metrics and job status
```

**Conventions**:
- Lowercase paths
- No trailing slashes
- RESTful when applicable
- Clear, descriptive names

## Code Style

### Python Style

**PEP 8 Compliance**:
- Line length: 100 characters (relaxed from 79 for readability)
- Indentation: 4 spaces
- Blank lines: 2 between top-level functions, 1 between methods
- Imports: Grouped (stdlib, third-party, local)

**Type Hints**:
```python
from typing import Dict, List, Tuple, Optional, Callable
from pathlib import Path

def check_paths_with_progress(
    text_dir: Path,
    cache_file: Path,
    progress_callback: Optional[Callable[[int, int, Dict], None]] = None,
    cancel_event=None,
    mode: str = DEFAULT_MODE
) -> Dict:
    """
    Check story paths with optional progress callbacks.

    Args:
        text_dir: Directory containing story path text files
        cache_file: Path to validation cache JSON file
        progress_callback: Optional callback function called after each path
        cancel_event: Optional threading.Event to signal cancellation
        mode: Validation mode ('new-only', 'modified', 'all')

    Returns:
        Dict with checked_count, paths_with_issues, summary, mode, and statistics
    """
    pass
```

**Docstrings**:
- Module docstring at top of file
- Function docstrings for all public functions
- Format: Google style (Args, Returns, Raises)
- Include examples for complex functions

**Error Handling**:
```python
try:
    # Specific operations
    result = risky_operation()
except SpecificException as e:
    # Handle specific error
    logger.error(f"Specific error: {e}")
    return default_value
except Exception as e:
    # Catch-all for unexpected errors
    logger.error(f"Unexpected error: {e}", exc_info=True)
    return fallback_value
```

**Logging**:
```python
# Use appropriate log levels
logger.info("Normal operation message")
logger.warning("Something unexpected but handled")
logger.error("Error occurred", exc_info=True)

# For services, use app.logger
app.logger.info(f"Processing workflow {workflow_id}")
app.logger.error(f"Error: {e}", exc_info=True)

# For scripts, use stderr
print(f"Processing {file}...", file=sys.stderr)
```

### Shell Script Style

**Bash Best Practices**:
```bash
#!/bin/bash
# Script description
# What this script does

set -e  # Exit on error
set -u  # Error on undefined variable (use carefully)

# Constants at top
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Functions before main logic
function build_story() {
    echo "Building story..."
    # Implementation
}

# Main script logic
echo "=== Build Started ==="
build_story
echo "=== Build Complete ==="
```

**Conventions**:
- Use `#!/bin/bash` shebang
- Set error flags (`set -e`)
- Quote variables: `"$VARIABLE"`
- Use functions for reusable logic
- Print progress to stdout
- Descriptive echo messages with separators

### Twee Style

**SugarCube 2 Conventions**:
```twee
:: PassageName [tag1 tag2]
Passage content goes here.

Regular text uses standard prose formatting.

[[Link Text|Destination]]
[[Simple Link]]

<<if $variable>>
    Conditional content
<</if>>

<<set $variable to "value">>
```

**Best Practices**:
- One passage per `::` marker
- Use meaningful passage names
- Tag passages for organization
- Keep macros readable with whitespace
- Use SugarCube 2 macro syntax consistently

### YAML Style (GitHub Actions)

**Workflow Files**:
```yaml
name: Build and Deploy

on:
  push:
    branches: [main]
  pull_request:

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Build story
        run: npm run build
```

**Conventions**:
- 2-space indentation
- Clear job and step names
- Group related steps
- Use official actions when possible
- Comment complex logic

## Documentation Standards

### README Files

**Required Sections**:
1. **Title**: Clear, descriptive heading
2. **Overview**: 2-3 sentence summary
3. **Features**: Bullet list of capabilities
4. **Usage**: How to use (commands, examples)
5. **Setup** (if applicable): Installation steps
6. **Architecture** (if applicable): High-level design
7. **Examples**: Real-world usage
8. **Troubleshooting**: Common issues

**Format**:
- Markdown (.md)
- Use headings (h1 for title, h2 for sections)
- Code blocks with language tags
- Bullet lists for features
- Numbered lists for procedures

**Example Structure**:
```markdown
# Component Name

Brief description of what this component does.

## Features

- Feature 1
- Feature 2

## Usage

### Basic Usage

```bash
command arg1 arg2
```

### Advanced Usage

More details...

## Architecture

Diagram or description...

## Examples

Real-world scenarios...

## Troubleshooting

Common issues and solutions...
```

### Code Comments

**Python**:
```python
# Single-line comments for clarification
result = complex_calculation()  # Inline when helpful

# Multi-line comments for complex logic
# This section handles the case where...
# And we need to...

"""
Module-level docstring.

Describes the purpose of this module, key classes/functions,
and overall design patterns.
"""

def function_name(arg: Type) -> ReturnType:
    """
    Brief one-line description.

    Longer description if needed, explaining the purpose,
    algorithm, or important considerations.

    Args:
        arg: Description of argument

    Returns:
        Description of return value

    Raises:
        ExceptionType: When this exception occurs

    Example:
        >>> function_name("input")
        "output"
    """
    pass
```

**Shell Scripts**:
```bash
#!/bin/bash
# Build AllPaths format output
# Generates all possible story paths for AI-based continuity checking

# This section handles...
complex_operation

# Single-line comments for clarity
mkdir -p "$DIST_DIR"  # Create output directory
```

**Twee**:
```twee
:: PassageName
/* Multi-line comment for passage design notes */

Passage text...

/* Inline comment explaining a macro */
<<if $condition>>
    Content
<</if>>
```

### Commit Messages

**Format**:
```
<type>: <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring (no feature/fix)
- `test`: Test additions or changes
- `chore`: Build, dependencies, tooling

**Subject Line**:
- Imperative mood ("Add feature" not "Added feature")
- Lowercase first letter (unless proper noun)
- No period at end
- 50 characters or less

**Body** (optional):
- Wrap at 72 characters
- Explain what and why, not how
- Use bullet points for multiple items

**Footer** (optional):
- Reference issues: `Closes #123`
- Breaking changes: `BREAKING CHANGE: description`
- Co-authors: `Co-Authored-By: Name <email>`

**Examples**:
```
feat: add AI continuity checking webhook service

Implement GitHub webhook receiver that:
- Downloads PR artifacts
- Runs Ollama-based continuity checks
- Posts results back to PR comments

Includes background processing and job cancellation.

Closes #42
```

```
fix: handle missing passage mapping file gracefully

Check if passage mapping exists before loading.
Fall back to using hex IDs if mapping not available.
```

```
docs: update AllPaths format README

Add validation modes section and usage examples.
```

### Architecture Decision Records (ADRs)

**Location**: `/architecture/*.md`

**Format**:
```markdown
# ADR-{number}: {Title}

## Status

{Proposed | Accepted | Deprecated | Superseded}

## Context

Background and motivation for this decision.
What problem are we solving?

## Decision

The decision we made and why.
What specific approach did we choose?

## Consequences

Positive and negative outcomes of this decision.

### Positive

- Benefit 1
- Benefit 2

### Negative

- Trade-off 1
- Trade-off 2

## Alternatives Considered

1. **Alternative 1**: Why rejected
2. **Alternative 2**: Why rejected

## References

- Related docs
- External resources
```

**Naming**: `{number}-{slug}.md`
- Example: `001-allpaths-format.md`
- Sequential numbering
- Descriptive slug (lowercase with hyphens)

### Feature Specifications

**Location**: `/features/*.md`

**Required Sections**:
1. **Overview**: What the feature does
2. **User Stories**: Who benefits and how
3. **Requirements**: Functional and non-functional
4. **Acceptance Criteria**: How we know it's complete
5. **Technical Approach**: High-level implementation
6. **Testing**: How to verify
7. **Dependencies**: What else is needed
8. **Timeline**: When it ships

**Format**: See existing feature files as templates

## Testing Standards

### Manual Testing

**Before Committing**:
1. Build locally: `npm run build`
2. Test AllPaths: `npm run build:allpaths`
3. Review outputs in `dist/`
4. Check for errors in console

**Before PR**:
1. Test on clean checkout
2. Verify CI passes locally
3. Test affected features manually
4. Review allpaths.html in browser

### Automated Testing

**GitHub Actions**:
- All builds must pass CI
- No deployment without passing tests
- Artifacts must be generated successfully

**Future Testing** (not yet implemented):
- Unit tests for Python modules
- Integration tests for webhook service
- End-to-end tests for build pipeline

### Validation Testing

**AI Continuity**:
```bash
# Test locally before relying on webhook
python3 scripts/check-story-continuity.py \
  dist/allpaths-metadata \
  allpaths-validation-status.json
```

**Webhook Service**:
```bash
# Health check
curl http://localhost:5000/health

# Status check
curl http://localhost:5000/status

# Check logs
journalctl --user -u continuity-webhook -f
```

## Git Workflow

### Branch Naming

**Format**: `{type}/{description}`

**Types**:
- `feature/`: New features
- `fix/`: Bug fixes
- `docs/`: Documentation only
- `refactor/`: Code refactoring
- `chore/`: Tooling, dependencies

**Examples**:
- `feature/add-continuity-checking`
- `fix/path-hash-collision`
- `docs/update-architecture`
- `refactor/simplify-generator`

### Pull Request Process

**Requirements**:
1. CI must pass (GitHub Actions)
2. AI continuity check completed (if story changes)
3. Documentation updated (if applicable)
4. No merge conflicts
5. Descriptive PR title and description

**PR Template** (create `.github/pull_request_template.md`):
```markdown
## Description

Brief summary of changes.

## Type of Change

- [ ] Feature
- [ ] Bug fix
- [ ] Documentation
- [ ] Refactoring
- [ ] Other: ___

## Testing

How has this been tested?

## Checklist

- [ ] CI passes
- [ ] Documentation updated
- [ ] AI continuity check reviewed (if applicable)
- [ ] No merge conflicts
```

### Merge Strategy

**Main Branch**:
- Protected branch
- Require PR approval (if team)
- Require CI to pass
- Squash commits (optional, keep history clean)

**Feature Branches**:
- Delete after merge
- Keep PR focused (one feature/fix per PR)
- Rebase on main before merging (optional)

## Quality Gates

### Pre-Commit

**Developer Checklist**:
- [ ] Code builds successfully
- [ ] No syntax errors or warnings
- [ ] Documentation updated
- [ ] Commit message follows standards
- [ ] Changes tested locally

### Pre-PR

**PR Checklist**:
- [ ] CI passes
- [ ] All files formatted correctly
- [ ] New features documented
- [ ] Breaking changes noted
- [ ] Tests added (when applicable)

### Pre-Merge

**Merge Checklist**:
- [ ] CI green on PR branch
- [ ] Code reviewed (if team)
- [ ] AI validation passed (if story changes)
- [ ] Documentation complete
- [ ] No unresolved comments

### Pre-Deploy

**Deployment Checklist**:
- [ ] Main branch CI passes
- [ ] Deployment preview reviewed
- [ ] No breaking changes (or documented)
- [ ] Rollback plan ready (if major change)

## Security Standards

### Sensitive Data

**Never Commit**:
- GitHub tokens (use environment variables)
- Webhook secrets (use environment variables)
- Private keys (store securely outside repo)
- Personal information
- API credentials

**Environment Variables**:
- Store in `~/.config/continuity-webhook/env`
- Use GitHub Secrets for Actions
- Document required variables in README
- Provide example `.env.example` files

### Code Security

**Python**:
- Validate all external input
- Sanitize AI output before display
- Use parameterized queries (if database used)
- Avoid eval() and exec()
- Limit file system access

**Shell**:
- Quote all variables
- Validate paths before operations
- Use `set -e` for error handling
- Avoid running untrusted scripts

**Webhook Service**:
- Verify HMAC signatures
- Validate artifact URLs
- Check file paths for traversal
- Sanitize content before posting
- Rate limit (future consideration)

## Performance Standards

### Build Performance

**Targets**:
- Tweego compilation: < 5 seconds
- AllPaths generation: < 30 seconds (for current story size)
- Full build pipeline: < 2 minutes

**Monitoring**:
- GitHub Actions build time
- Local build time logs
- Path count vs. build time correlation

### Webhook Service Performance

**Targets**:
- Webhook response: < 1 second (202 Accepted)
- AI validation: < 60 seconds per path (average)
- Total PR validation: < 15 minutes (for typical PRs)

**Monitoring**:
- `/status` endpoint metrics
- Service logs
- PR comment timestamps

### Resource Usage

**Limits**:
- Artifact size: < 50 MB per build
- Text files: < 1 MB per path
- Memory: Bounded by artifact size
- Disk: Clean up temporary files

## Accessibility Standards

### Documentation

- Use descriptive link text (not "click here")
- Provide alt text for images (future)
- Use semantic markdown headings
- Ensure code examples have language tags

### Web Output

**Story Files**:
- Semantic HTML structure
- ARIA labels where appropriate
- Keyboard navigation support
- Screen reader compatibility

**AllPaths Browser**:
- Accessible controls (buttons, links)
- Keyboard shortcuts documented
- Sufficient color contrast
- Descriptive labels

## Maintenance Standards

### Dependency Updates

**Schedule**:
- Review monthly
- Update quarterly (if stable)
- Security patches: Immediate

**Process**:
1. Check for updates
2. Review changelogs
3. Test locally
4. Update in PR
5. Document breaking changes

### Service Maintenance

**Regular Tasks**:
- Monitor logs weekly
- Check disk usage monthly
- Review metrics quarterly
- Update secrets annually

**Incident Response**:
1. Acknowledge issue
2. Investigate root cause
3. Implement fix
4. Document in incident log
5. Review and improve

### Documentation Maintenance

**Keep Current**:
- Update README on feature changes
- Update ARCHITECTURE on structural changes
- Create ADRs for major decisions
- Archive deprecated docs

**Review Schedule**:
- README: After each major feature
- ARCHITECTURE: After structural changes
- STANDARDS: Annually or as needed
- Feature docs: When feature changes

## Version Control

### Semantic Versioning

**Format**: `MAJOR.MINOR.PATCH`
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

**Example**: `1.2.3`
- 1 = Major version
- 2 = Minor version
- 3 = Patch version

### Tagging

**Release Tags**:
```bash
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

**Conventions**:
- Prefix with `v` (e.g., `v1.0.0`)
- Tag stable releases
- Include release notes in tag message

## Conclusion

These standards are living documents. As the project evolves, update these standards to reflect new patterns, tools, and best practices discovered during development.

**Questions or Suggestions?**
Open an issue or pull request to discuss changes to these standards.
