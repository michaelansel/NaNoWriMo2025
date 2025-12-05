# ADR-007: Service Documentation Discoverability

## Status

Accepted

## Context

Users operating the continuity-webhook service needed to find operational commands (start, stop, restart, status, logs) but struggled with discoverability in the 820-line services/README.md. The restart command existed at line 725-728 in the "Monitoring" section, requiring extensive scrolling or search to locate.

**The Problem:**
- Operational commands organized by conceptual category (Installation, Monitoring) rather than task urgency
- No quick reference for "I just need to do X right now" scenarios
- High search cost: users must either Ctrl+F (requires knowing what to search), scroll through TOC, or read 700+ lines
- Information architecture optimized for initial learning, not operational reference

**User Pain Point:**
"I need to restart the service NOW" should not require scrolling through 820 lines or remembering which conceptual section contains the command.

## Decision

Restructure services/README.md with task-oriented information architecture:

### 1. Add Table of Contents (lines 5-29)

Organized into four task-oriented categories:
- **Getting Started**: Quick reference, setup, GitHub config
- **Operations**: Monitoring, troubleshooting, configuration
- **Features**: Validation modes, commit handling, path approval
- **Technical**: Architecture, components, security, testing, development, performance, maintenance

**Rationale**: Users can quickly scan category relevant to their current need (operator vs. developer vs. learner)

### 2. Add Quick Reference Section (lines 53-90)

Positioned immediately after Security section, before detailed Components.

**Contents:**
- Common Operations: Start, stop, restart, status, enable, logs, health checks
- Troubleshooting Quick Commands: Service diagnostics, Ollama checks, webhook tests

**Format:**
- Bash code blocks with inline comments
- Commands grouped by purpose
- Cross-reference to detailed sections for more context

**Positioning Rationale:**
- Early in document (within first 100 lines)
- After architectural overview (Architecture, Security) to provide context
- Before deep dives (Components, Setup) to serve "just need the command" users

### 3. Preserve Detailed Documentation

All existing detailed sections remain unchanged:
- Detailed monitoring section (now includes cross-reference FROM Quick Ref)
- Installation section (authoritative source for setup procedures)
- Troubleshooting section (detailed problem-solving)

**Rationale**: Quick Reference serves immediate needs; detailed sections serve learning and complex scenarios.

## Consequences

### Positive

1. **Dramatic reduction in time-to-command**
   - "How do I restart?" goes from 820-line search to ~50-line scan
   - Common operations accessible within first 100 lines

2. **Task-oriented structure matches user mental models**
   - Users think "I need to restart" not "restart is in the monitoring conceptual category"
   - TOC organized by role/task: operator, developer, learner

3. **Improves accessibility without breaking existing patterns**
   - Detailed documentation preserved for learning
   - Follows "quick start + detailed reference" pattern common in technical docs
   - Cross-references maintain single source of truth

4. **Scales to multiple user personas**
   - Operators: Quick Reference + Operations sections
   - Developers: Technical sections
   - First-time users: Getting Started sections

### Negative

1. **Content duplication**
   - Restart command appears in both Quick Reference (line ~61) and Monitoring section (line ~788)
   - Maintenance burden: must update both places if commands change

2. **Document length increase**
   - Added 64 lines (820 → 884 lines)
   - Slightly longer to scroll through entirely

3. **Potential staleness**
   - If Quick Reference not maintained, becomes outdated/misleading
   - Requires discipline to update both locations

### Mitigation

**For duplication concern:**
- Quick Reference contains only commands, no explanations (minimizes duplication surface area)
- Clear cross-reference: "For detailed setup, configuration, and troubleshooting, see the sections below."
- Detailed sections remain authoritative source of truth
- Quick Reference is intentionally minimal - just enough to execute the task

**For maintenance concern:**
- Quick Reference structure is stable (service commands rarely change)
- Clear comments in ADR to update both places
- Consider future automation: generate Quick Reference from detailed sections

## Alternatives Considered

### Alternative 1: Separate Quick Reference Document

Create `services/QUICK-REFERENCE.md` with only operational commands.

**Rejected because:**
- Forces users to know two documents exist
- Breaks mental model of "one README per service"
- Higher risk of staleness (separate file less visible during updates)
- Users scanning README TOC won't discover quick reference

### Alternative 2: Move All Operational Commands to Top

Reorganize entire document to front-load operational content.

**Rejected because:**
- Breaks logical flow for first-time users (setup → configure → operate)
- Architecture and Security context important before operations
- Would require major restructure of existing content
- Learning path (setup) vs. operational reference (daily use) have different ordering needs

### Alternative 3: Use Collapsible Sections (HTML in Markdown)

Add `<details>` tags to collapse detailed sections, keeping only headings visible.

**Rejected because:**
- Not all Markdown renderers support HTML details/summary
- Adds complexity to source document
- Doesn't solve discovery problem (users still must find right section)
- Quick reference still needed for common commands

### Alternative 4: External Tool (man page, CLI tool)

Create `continuity-webhook --help` or man page with quick reference.

**Rejected because:**
- Requires separate tool installation/maintenance
- Doesn't help users viewing README on GitHub
- Over-engineering for current scale
- README is the primary entry point for most users

## Implementation

Changes made to `/home/ubuntu/Code/NaNoWriMo2025/services/README.md`:

1. **Lines 5-29**: Added Table of Contents with task-oriented organization
2. **Lines 53-90**: Added Quick Reference section with Common Operations and Troubleshooting Quick Commands
3. **Line 90**: Added cross-reference to detailed sections

Total impact: +64 lines (820 → 884 lines)

## References

- **Original issue**: User couldn't easily find restart command
- **STANDARDS.md** (lines 357-412): README documentation standards
- **DOCUMENTATION.md** (lines 140-155): Service documentation guidance
- **Related pattern**: Quick start + detailed reference (common in technical docs)

## Future Considerations

1. **Auto-generated quick reference**: Script to extract commands from detailed sections
2. **Command index**: Alphabetical index of all commands with line numbers
3. **Interactive TOC**: GitHub supports automatic TOC rendering in some contexts
4. **Monitoring metrics**: Track which sections users access most (if analytics available)
