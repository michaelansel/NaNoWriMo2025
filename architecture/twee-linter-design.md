# Technical Design: Twee Passage Formatting Linter

## Overview

A Python linter for Twee story files that enforces formatting standards with auto-fix capability. The design emphasizes simplicity, maintainability, and clear separation between detection and correction.

## Module Structure

### Single Script: `scripts/lint_twee.py`

```
lint_twee.py
├── Constants & Configuration
├── Rule Classes (8 rules)
├── Passage Parser
├── File Processor
├── Output Formatter
└── CLI Interface
```

**Rationale**: A single script keeps the implementation simple for a focused tool. All rules are lightweight and don't justify separate modules. Following the pattern seen in `check-story-continuity.py`.

### Key Components

#### 1. Rule Base Class

```python
class TweeRule:
    """Base class for formatting rules."""

    def __init__(self):
        self.violations = []

    def check(self, lines: List[str]) -> List[Violation]:
        """Detect violations. Returns list of (line_num, description)."""
        pass

    def fix(self, lines: List[str]) -> Tuple[List[str], List[Fix]]:
        """Apply fixes. Returns (fixed_lines, list of fixes applied)."""
        pass
```

**Design Decision**: Separate `check()` and `fix()` methods allow:
- Check-only mode to run without modifying content
- Fix mode to reuse detection logic
- Clear reporting of what changed

#### 2. Rule Implementations (8 rules)

Each rule is implemented inline in the `lint_file()` function:
- Rule 1: `passage-header-spacing` - `::PassageName` → `:: PassageName`
- Rule 2: `blank-line-after-header` - Blank line after headers (with special passage exemption)
- Rule 3: `blank-line-between-passages` - Exactly one blank line before `::` headers
- Rule 4: `trailing-whitespace` - Remove trailing spaces/tabs
- Rule 5: `final-newline` - Exactly one newline at EOF
- Rule 6: `single-blank-lines` - Collapse multiple consecutive blank lines
- Rule 7: `link-block-spacing` - Blank line before/after link blocks, no blanks between
- Rule 8: `smart-quotes` - Replace Unicode smart quotes with ASCII equivalents

**Ordering Matters**: Rules execute in sequence because some depend on others:
1. Fix trailing whitespace (cleanup before content analysis)
2. Fix smart quotes (character-level cleanup)
3. Check link-block-spacing (needs clean lines for detection)
4. Fix header spacing (affects passage detection)
5. Fix blank lines between passages (establishes passage boundaries)
6. Fix blank lines after headers (operates within passages)
7. Collapse multiple blank lines (cleanup)
8. Fix final newline (last operation)

#### 3. Passage Parser

```python
class PassageInfo:
    """Metadata about a passage."""
    start_line: int
    header: str
    name: str
    tags: List[str]

def parse_passages(lines: List[str]) -> List[PassageInfo]:
    """
    Identify passage boundaries and metadata.

    Returns list of passages with:
    - Line number of :: header
    - Passage name (extracted from header)
    - Tags (extracted from header)
    """
```

**Purpose**: Pre-parsing allows rules to understand passage structure without duplicating logic. Needed for:
- Rule 2: Identifying special passages by name or tag
- Rule 3: Knowing where passages begin

**Pattern**: `^:: ([^[]+)(?:\s*\[([^\]]+)\])?$`
- Captures passage name and optional tags
- Examples:
  - `:: PassageName` → name="PassageName", tags=[]
  - `:: StoryStylesheet [stylesheet]` → name="StoryStylesheet", tags=["stylesheet"]
  - `:: PassageName [tag1 tag2]` → name="PassageName", tags=["tag1", "tag2"]

#### 4. Special Passage Detection

```python
# Special passage names (Harlowe conventions)
SPECIAL_PASSAGE_NAMES = {
    'StoryData', 'StoryTitle', 'StoryStylesheet',
    'StoryBanner', 'StoryMenu', 'StoryInit'
}

# Special passage tags
SPECIAL_PASSAGE_TAGS = {'stylesheet', 'script'}

def is_special_passage(passage: PassageInfo) -> bool:
    """
    Check if passage is exempt from blank-line-after-header rule.

    Returns True if:
    - Name matches special passage list
    - Has [stylesheet] or [script] tag
    """
    return (
        passage.name in SPECIAL_PASSAGE_NAMES or
        any(tag in SPECIAL_PASSAGE_TAGS for tag in passage.tags)
    )
```

**Rationale**: Special passages often contain structured data (JSON, CSS, JS) where blank lines have semantic meaning. Exempting them from Rule 2 prevents breaking their content.

#### 5. File Processor

```python
def process_file(
    file_path: Path,
    rules: List[TweeRule],
    fix_mode: bool
) -> FileResult:
    """
    Main processing pipeline.

    Steps:
    1. Read file
    2. Parse passages (for context)
    3. If check mode:
       - Run all rule.check() methods
       - Return violations
    4. If fix mode:
       - Run all rule.fix() methods in sequence
       - Write fixed content
       - Return fixes applied
    5. Handle errors gracefully

    Returns:
        FileResult with violations or fixes, plus error info
    """
```

**Key Design Points**:
- **Idempotency**: Rules operate on current state, each producing new line list
- **Atomicity**: Write entire file or nothing (no partial fixes)
- **Error handling**: File read/write errors don't crash; reported per-file

#### 6. Output Formatter

```python
def format_output(results: Dict[Path, FileResult], fix_mode: bool) -> str:
    """
    Format results for human consumption.

    Check mode format:
        {file_path}:{line_num}: [{rule_name}] {description}

    Fix mode format:
        {file_path}:{line_num}: [FIXED] [{rule_name}] {description}

    Summary:
        Files checked: N
        Files with issues: M
        Total violations: X (check mode)
        Total fixes applied: Y (fix mode)
    """
```

**Examples**:
```
# Check mode
src/KEB-251101.twee:5: [passage-header-spacing] Missing space after '::'
src/KEB-251101.twee:10: [trailing-whitespace] Line has trailing spaces
src/KEB-251102.twee:3: [blank-line-after-header] Missing blank line after passage header

Files checked: 33
Files with issues: 3
Total violations: 15

# Fix mode
src/KEB-251101.twee:5: [FIXED] [passage-header-spacing] Added space after '::'
src/KEB-251101.twee:10: [FIXED] [trailing-whitespace] Removed trailing whitespace
src/KEB-251102.twee:3: [FIXED] [blank-line-after-header] Added blank line after header

Files checked: 33
Files fixed: 3
Total fixes applied: 15
```

#### 7. CLI Interface

```python
def main():
    parser = argparse.ArgumentParser(
        description="Lint Twee passage files for formatting issues"
    )
    parser.add_argument(
        'paths',
        nargs='+',
        type=Path,
        help='Twee files or directories to lint'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Auto-fix violations (default: check only)'
    )
    parser.add_argument(
        '--rule',
        action='append',
        help='Only run specific rules (can specify multiple)'
    )

    # Returns exit code: 0 if no issues, 1 if violations found, 2 if errors
```

**Examples**:
```bash
# Check all files in src/
python3 scripts/lint_twee.py src/

# Fix all files
python3 scripts/lint_twee.py src/ --fix

# Check specific files
python3 scripts/lint_twee.py src/KEB-251101.twee src/KEB-251102.twee

# Run only specific rules
python3 scripts/lint_twee.py src/ --rule trailing-whitespace --rule final-newline
```

## Data Flow

```
Input: List of file paths
    ↓
For each file:
    ↓
1. Read file → List[str] (lines)
    ↓
2. Parse passages → List[PassageInfo]
    ↓
3. Check mode:
   For each rule:
       rule.check(lines, passages) → List[Violation]

   Fix mode:
   For each rule (in order):
       lines, fixes = rule.fix(lines, passages)
       accumulate fixes
    ↓
4. Fix mode only: Write lines back to file
    ↓
5. Format output → violations or fixes
    ↓
6. Aggregate all results
    ↓
Output: Summary + exit code
```

## Rule Abstraction

### Rule Interface

Each rule implements:
```python
class RuleName(TweeRule):
    rule_id: str = "rule-slug"
    description: str = "What this rule enforces"

    def check(self, lines: List[str], passages: List[PassageInfo]) -> List[Violation]:
        """Find violations without modifying content."""

    def fix(self, lines: List[str], passages: List[PassageInfo]) -> Tuple[List[str], List[Fix]]:
        """Return fixed lines and list of changes made."""
```

### Data Structures

```python
@dataclass
class Violation:
    line_num: int      # 1-indexed line number
    rule_id: str       # e.g., "trailing-whitespace"
    description: str   # Human-readable message

@dataclass
class Fix:
    line_num: int      # 1-indexed line number
    rule_id: str
    description: str   # What was fixed
    old_content: str   # Original line (for verification)
    new_content: str   # Fixed line
```

### Why This Abstraction?

1. **Extensibility**: Adding new rules is straightforward
2. **Testability**: Each rule can be unit tested independently
3. **Configurability**: Rules can be enabled/disabled via CLI
4. **Clarity**: Each rule's logic is self-contained
5. **Maintainability**: Bug fixes are localized to specific rules

### Rule-Specific Logic

#### Rule 1: Passage Header Spacing
```python
# Pattern: :: with no space before passage name
# Fix: Insert space after ::

if line.startswith('::') and len(line) > 2 and line[2] != ' ':
    fixed = ':: ' + line[2:]
```

#### Rule 2: Blank Line After Header
```python
# Pattern: Passage header immediately followed by content
# Exception: Special passages (see is_special_passage())
# Fix: Insert blank line after header

for passage in passages:
    if is_special_passage(passage):
        continue
    if lines[passage.start_line + 1].strip():  # Next line has content
        insert_blank_line_after(passage.start_line)
```

#### Rule 3: Blank Line Between Passages
```python
# Pattern: Not exactly one blank line before ::
# Fix: Ensure exactly one blank line before each :: header (except first)

for passage in passages[1:]:  # Skip first passage
    blank_line_before = passage.start_line - 1
    if not lines[blank_line_before].strip():  # Has blank line
        # Remove extra blank lines
    else:  # No blank line
        # Insert blank line
```

#### Rule 4: Trailing Whitespace
```python
# Pattern: Lines ending with spaces or tabs
# Fix: Strip trailing whitespace

for i, line in enumerate(lines):
    stripped = line.rstrip()
    if stripped != line:
        lines[i] = stripped
```

#### Rule 5: Final Newline
```python
# Pattern: File doesn't end with exactly one newline
# Fix: Ensure file ends with '\n'

# Read file in binary mode to preserve exact content
# Check last byte(s)
# Add or remove newlines as needed
```

#### Rule 6: Single Blank Lines
```python
# Pattern: Multiple consecutive blank lines
# Fix: Collapse to single blank line

i = 0
while i < len(lines) - 1:
    if not lines[i].strip() and not lines[i+1].strip():
        # Found consecutive blank lines
        del lines[i+1]
    else:
        i += 1
```

#### Rule 7: Link Block Spacing
```python
# Pattern: Block links (lines containing only [[...]]) need proper spacing
# - Blank line BEFORE first block link if narrative precedes
# - NO blank lines BETWEEN consecutive block links
# - Blank line AFTER last block link if content follows

def is_block_link(line: str) -> bool:
    """Check if line contains only a link with optional whitespace."""
    stripped = line.strip()
    if not stripped:
        return False
    # Must start with [[ and end with ]], with exactly one of each
    return (stripped.startswith('[[') and stripped.endswith(']]')
            and stripped.count('[[') == 1 and stripped.count(']]') == 1
            and len(stripped) > 4)  # Not empty [[]]

# State tracking: in_link_block, last_was_block_link, last_non_blank_was_narrative
# Inline links (text before/after [[...]]) are NOT affected by this rule
```

#### Rule 8: Smart Quotes
```python
# Pattern: Unicode smart quotes from word processors
# Fix: Replace with ASCII equivalents

SMART_QUOTES = {
    '\u201c': '"',  # " Left double quotation mark
    '\u201d': '"',  # " Right double quotation mark
    '\u2018': "'",  # ' Left single quotation mark
    '\u2019': "'",  # ' Right single quotation mark (also apostrophe)
}

for smart, ascii_equiv in SMART_QUOTES.items():
    line_content = line_content.replace(smart, ascii_equiv)
```

## Special Passage Handling

### Detection Strategy

Special passages are identified during parsing phase:

1. **By name**: Exact match against `SPECIAL_PASSAGE_NAMES`
2. **By tag**: Contains `stylesheet` or `script` tag

### Exemption Application

Only Rule 2 (blank line after header) checks special passage status:

```python
def fix(self, lines: List[str], passages: List[PassageInfo]) -> ...:
    for passage in passages:
        if is_special_passage(passage):
            continue  # Skip this passage
        # ... apply rule to normal passages
```

Other rules apply to all passages uniformly.

### Why These Passages?

- **StoryData**: Contains JSON (blank line would be inside JSON)
- **StoryStylesheet**: Contains CSS (formatting matters)
- **StoryInit**: Contains Harlowe code (formatting matters)
- **[stylesheet]** passages: CSS content
- **[script]** passages: JavaScript content

In all cases, the content immediately after the header has syntactic meaning where whitespace matters.

## Fix vs Check Mode Behavior

### Check Mode (Default)

```
1. Read file
2. Parse passages
3. For each rule:
   - violations = rule.check(lines, passages)
   - Accumulate violations
4. Do NOT modify file
5. Print violations
6. Exit with code 1 if violations found
```

**Output**: Reports what's wrong
**Side effects**: None (read-only)
**Use case**: CI/CD checks, pre-commit hooks

### Fix Mode (`--fix`)

```
1. Read file
2. Parse passages
3. For each rule (in sequence):
   - lines, fixes = rule.fix(lines, passages)
   - Update lines with fixed content
   - Accumulate fixes
4. Write fixed lines back to file
5. Print fixes applied
6. Exit with code 0 (even if fixes made)
```

**Output**: Reports what was fixed
**Side effects**: Modifies files in-place
**Use case**: Automated formatting, developer workflow

### Idempotency Guarantee

Running fix mode multiple times produces identical output:

```bash
# First run: fixes issues
python3 scripts/lint_twee.py file.twee --fix
# Output: 5 fixes applied

# Second run: no changes
python3 scripts/lint_twee.py file.twee --fix
# Output: 0 fixes applied

# Verification: no changes
git diff file.twee
# No output (file unchanged)
```

**Implementation**: Rules are designed to be idempotent:
- Only fix actual violations
- Don't modify already-correct content
- Order of operations prevents conflicts

## Error Reporting Format

### Console Output Structure

```
{file_path}:{line_num}: [{status}] [{rule_id}] {description}
```

**Fields**:
- `file_path`: Relative to CWD or absolute
- `line_num`: 1-indexed line number (human-readable)
- `status`: Empty in check mode, `FIXED` in fix mode
- `rule_id`: Kebab-case rule identifier
- `description`: Human-readable message

### Examples

```
# Check mode
src/KEB-251101.twee:5: [passage-header-spacing] Missing space after '::'
src/KEB-251101.twee:10: [trailing-whitespace] Line has trailing spaces (4 spaces)
src/KEB-251102.twee:3: [blank-line-after-header] Missing blank line after passage header
src/StoryData.twee:15: [final-newline] File should end with exactly one newline

# Fix mode
src/KEB-251101.twee:5: [FIXED] [passage-header-spacing] Added space after '::'
src/KEB-251101.twee:10: [FIXED] [trailing-whitespace] Removed 4 trailing spaces
src/KEB-251102.twee:3: [FIXED] [blank-line-after-header] Inserted blank line
src/StoryData.twee:15: [FIXED] [final-newline] Added final newline
```

### Summary Section

```
# Check mode summary
Files checked: 33
Files with issues: 4
Total violations: 18
Exit code: 1

# Fix mode summary
Files checked: 33
Files fixed: 4
Total fixes applied: 18
Exit code: 0

# Error scenario
Files checked: 33
Files with issues: 2
Files with errors: 1  (permission denied: src/locked.twee)
Total violations: 5
Exit code: 2
```

### Exit Codes

- `0`: Success (check mode: no violations; fix mode: completed)
- `1`: Violations found (check mode only)
- `2`: Errors occurred (file I/O errors, permission issues)

## Error Handling

### File-Level Errors

```python
try:
    content = file_path.read_text(encoding='utf-8')
except (OSError, PermissionError, UnicodeDecodeError) as e:
    print(f"{file_path}: [ERROR] {e}", file=sys.stderr)
    errors.append((file_path, str(e)))
    continue  # Skip this file, process others
```

**Behavior**: Log error and continue processing other files. Report all errors at end.

### Rule Execution Errors

```python
try:
    violations = rule.check(lines, passages)
except Exception as e:
    print(f"{file_path}: [ERROR] Rule {rule.rule_id} failed: {e}", file=sys.stderr)
    # Continue with other rules
```

**Behavior**: A bug in one rule shouldn't crash the entire linter.

### Write Errors (Fix Mode)

```python
try:
    file_path.write_text(fixed_content, encoding='utf-8')
except (OSError, PermissionError) as e:
    print(f"{file_path}: [ERROR] Could not write fixed file: {e}", file=sys.stderr)
    # Don't mark as fixed
    errors.append((file_path, str(e)))
```

**Behavior**: If write fails, file remains unchanged. Report error clearly.

## Implementation Notes

### Character Encoding

- **Assumption**: All .twee files are UTF-8
- **Rationale**: Twee/Twine ecosystem standard
- **Handling**: Use `encoding='utf-8'` for all file I/O

### Line Ending Preservation

- **Challenge**: Mixed line endings (LF vs CRLF)
- **Solution**: Read file, detect line ending style, preserve on write
- **Implementation**: Check first few lines for `\r\n` vs `\n`

```python
def detect_line_ending(content: str) -> str:
    if '\r\n' in content[:1000]:  # Check first 1000 chars
        return '\r\n'
    return '\n'
```

### Directory Traversal

```python
def find_twee_files(path: Path) -> List[Path]:
    """Recursively find all .twee files in path."""
    if path.is_file():
        return [path] if path.suffix == '.twee' else []
    elif path.is_dir():
        return sorted(path.rglob('*.twee'))
    else:
        return []  # Path doesn't exist
```

**Behavior**: Accept files or directories as input. Recursively process directories.

### Performance Considerations

- **Expected scale**: 33 files, ~100 lines each = ~3300 lines total
- **Processing time**: < 1 second for full codebase
- **Optimization**: Not needed at this scale
- **Future**: If needed, parallelize file processing

## Testing Strategy

### Manual Testing

```bash
# Test check mode
python3 scripts/lint_twee.py src/

# Test fix mode
python3 scripts/lint_twee.py src/ --fix

# Verify idempotency
python3 scripts/lint_twee.py src/ --fix
python3 scripts/lint_twee.py src/ --fix
git diff src/  # Should be clean after first run

# Test specific rules
python3 scripts/lint_twee.py src/ --rule trailing-whitespace
```

### Test Cases by Rule

1. **Passage Header Spacing**:
   - `::PassageName` → `:: PassageName`
   - `::  PassageName` → `:: PassageName` (collapse multiple spaces)
   - `:: PassageName` → no change (already correct)

2. **Blank Line After Header**:
   - Normal passage: Insert blank line if missing
   - Special passage: Skip (StoryData, StoryStylesheet, etc.)
   - Tagged passage: Skip [stylesheet] and [script]

3. **Blank Line Between Passages**:
   - No blank line before `::` → Insert one
   - Multiple blank lines before `::` → Collapse to one
   - First passage: No blank line before it (file start)

4. **Trailing Whitespace**:
   - Lines with trailing spaces → Remove
   - Lines with trailing tabs → Remove
   - Lines with trailing mixed whitespace → Remove
   - Lines already clean → No change

5. **Final Newline**:
   - File with no final newline → Add one
   - File with multiple final newlines → Remove extras
   - File with exactly one → No change

6. **Single Blank Lines**:
   - 2+ consecutive blank lines → Collapse to one
   - Single blank lines → No change
   - Blank lines within passages → Preserved

7. **Link Block Spacing**:
   - Block link after narrative without blank → Insert blank before
   - Consecutive block links with blank between → Remove blank
   - Block link followed by narrative without blank → Insert blank after
   - Inline links (text + link on same line) → No change
   - Links right after header → Defer to blank-line-after-header rule

8. **Smart Quotes**:
   - " and " → " (double quotes)
   - ' and ' → ' (single quotes/apostrophes)
   - Mixed smart and ASCII quotes → Only smart quotes replaced
   - No smart quotes → No change

### Edge Cases

1. **Empty file**: No changes (no passages, no violations)
2. **Single passage**: No blank line before first passage
3. **No content passages**: Header with tags only (rare but valid)
4. **Very long lines**: No line length limit (Twee convention)
5. **Non-ASCII characters**: Preserved except smart quotes (UTF-8 handling)
6. **Block vs inline links**: `[[Link]]` alone is block; `Text [[Link]] more` is inline
7. **Multiple link blocks**: Each block independently follows spacing rules
8. **Smart quotes in links**: Replaced like any other text

## Integration Points

### Pre-commit Hook (Future)

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: twee-lint
      name: Twee Format Linter
      entry: python3 scripts/lint_twee.py --fix
      language: system
      files: '\.twee$'
```

### CI/CD (Future)

```yaml
# .github/workflows/lint.yml
- name: Lint Twee files
  run: |
    python3 scripts/lint_twee.py src/
    if [ $? -ne 0 ]; then
      echo "Twee formatting issues found. Run: python3 scripts/lint_twee.py src/ --fix"
      exit 1
    fi
```

### Make Target (Future)

```makefile
lint-twee:
	python3 scripts/lint_twee.py src/

fix-twee:
	python3 scripts/lint_twee.py src/ --fix
```

## Design Rationale

### Why Not Use Existing Linters?

- **Twee-specific**: Generic linters (pylint, eslint) don't understand Twee syntax
- **Custom rules**: Passage boundaries, special passages, Twee formatting conventions
- **Simplicity**: A focused tool is easier to maintain than configuring a generic one

### Why Python?

- **Consistency**: Matches existing scripts (`check-story-continuity.py`)
- **Batteries included**: File I/O, regex, argparse in stdlib
- **Readability**: Clean syntax for text processing
- **Team familiarity**: Existing Python codebase suggests team comfort

### Why Single File?

- **Scope**: 8 rules don't justify multi-module architecture
- **Simplicity**: Easier to understand, debug, and deploy
- **Pattern**: Follows `check-story-continuity.py` (similar scale tool)
- **Future**: Can split into modules if rules grow significantly (>20 rules)

### Why Class-Based Rules?

- **Extensibility**: Easy to add new rules
- **Encapsulation**: Each rule's logic is self-contained
- **Testability**: Can instantiate and test rules independently
- **Convention**: Matches Python best practices for plugins/extensions

## Future Enhancements (Out of Scope)

These are explicitly **not** part of this design but noted for future consideration:

1. **Configuration file**: `.tweelintrc` for rule settings
2. **Custom rules**: Plugin system for project-specific rules
3. **Format on save**: Editor integrations (VSCode, Vim)
4. **Parallel processing**: For very large projects (>1000 files)
5. **Detailed diff**: Show before/after for each fix
6. **Rule severity**: Warning vs error levels
7. **Auto-fix specific lines**: `--fix-line 42` flag

## Success Criteria

This design succeeds if:

1. ✓ All 8 rules are implemented correctly
2. ✓ Check mode reports all violations accurately
3. ✓ Fix mode corrects all violations idempotently
4. ✓ Special passages are properly exempted from Rule 2
5. ✓ Output is clear and actionable
6. ✓ Script runs in <1 second on full codebase
7. ✓ Code follows STANDARDS.md (PEP 8, type hints, docstrings)
8. ✓ No false positives or false negatives
9. ✓ Error handling prevents data loss
10. ✓ Can be integrated into development workflow

## References

- STANDARDS.md lines 302-327: Twee style guidelines
- `scripts/check-story-continuity.py`: Python script structure pattern
- Harlowe 3 documentation: Special passage conventions
- PEP 8: Python style guide
