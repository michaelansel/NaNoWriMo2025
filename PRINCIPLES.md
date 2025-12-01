# Principles

Core principles that guide decision-making for the NaNoWriMo2025 project. These are non-negotiable.

## 1. Writers First, Always

**Principle:** Every decision optimizes for the writer's experience, not the developer's convenience.

**This means:**
- Simple beats powerful when in conflict
- Web-based contribution beats feature-rich local tooling
- Clear error messages beat detailed technical diagnostics
- Documentation written for writers, not engineers

**Trade-offs we accept:**
- Some advanced IF features may be harder to implement
- Tooling may be less flexible than traditional IF frameworks
- Technical users may find the workflow limiting

**Example decisions:**
- ✓ Edit .twee files directly in GitHub web UI
- ✗ Require local Tweego installation
- ✓ Automated resource passage tracking
- ✗ Manual management of passage dependencies

---

## 2. Automation Over Gatekeeping

**Principle:** Quality comes from tooling and automation, not from manual review gates or restrictive permissions.

**This means:**
- Automate what can be automated
- Provide feedback, not barriers
- Trust contributors, verify with tooling
- Make the right thing the easy thing

**Trade-offs we accept:**
- More complex build infrastructure
- Ongoing maintenance of automation
- Occasional false positives from automated checks

**Example decisions:**
- ✓ AI continuity checking on every PR
- ✗ Requiring senior author approval before merge
- ✓ Automated resource passage name generation
- ✗ Manual tracking of passage names in spreadsheets
- ✓ Multiple output formats generated automatically
- ✗ Authors manually export to different formats

---

## 3. Fast Feedback Loops

**Principle:** Time from idea to feedback should be measured in minutes, not hours or days.

**This means:**
- Build and deploy in under 2 minutes
- PR previews available immediately after workflow completion
- Continuity checks start as soon as code is pushed
- Status visible at all times

**Trade-offs we accept:**
- Infrastructure costs for compute resources
- Complexity of webhook services and automation
- Maintaining fast build pipelines requires ongoing attention

**Example decisions:**
- ✓ GitHub Actions for immediate build on push
- ✗ Nightly batch builds
- ✓ Incremental validation (check only what changed)
- ✗ Full re-validation on every commit
- ✓ Progress updates posted as paths complete
- ✗ Wait for all paths before posting results

---

## 4. Multiple Perspectives, Same Source

**Principle:** Different tasks need different views of the same content. Generate multiple perspectives from a single source of truth.

**This means:**
- One .twee source, many output formats
- Each format optimized for specific use case
- Never manually maintain parallel versions
- Add new perspectives when they serve a clear need

**Trade-offs we accept:**
- More complex build process
- Maintenance burden of multiple format generators
- Potential for format-specific bugs

**Example decisions:**
- ✓ Harlowe for playing, Paperthin for proofreading, DotGraph for visualization, AllPaths for AI checking
- ✗ One-size-fits-all output
- ✓ Custom AllPaths format for continuity needs
- ✗ Manually copy passages into AI prompts
- ✓ Clean prose vs metadata formats for different audiences
- ✗ Single format trying to serve all purposes

---

## 5. Transparency and Inspectability

**Principle:** Authors should always be able to see what's happening and why. No mysterious black boxes.

**This means:**
- All automation produces visible, understandable output
- Builds show detailed logs
- AI feedback explains specific issues
- Every path can be traced and inspected

**Trade-offs we accept:**
- More verbose output and notifications
- Additional documentation burden
- Complexity of making internals visible

**Example decisions:**
- ✓ Detailed PR comments showing validation results
- ✗ Simple pass/fail status checks
- ✓ AllPaths HTML interface for browsing every story path
- ✗ Black box "all good" report
- ✓ Path IDs link to specific routes through the story
- ✗ Generic error messages
- ✓ Validation cache shows exactly which paths are checked
- ✗ Opaque AI decision-making

---

## 6. Incremental Progress Over Perfection

**Principle:** Ship improvements iteratively. Working now beats perfect later.

**This means:**
- Start with basic functionality, enhance based on real usage
- Optimize common paths, tolerate rough edges in rare cases
- Learn from what's shipped, not what's planned
- Iterate based on actual pain points, not hypothetical ones

**Trade-offs we accept:**
- Some inconsistencies as systems evolve
- Occasional breaking changes when we learn better approaches
- Documentation lags slightly behind implementation

**Example decisions:**
- ✓ Ship selective validation (new-only mode), then add modified mode based on feedback
- ✗ Wait until perfect validation system designed before shipping anything
- ✓ Add validation modes incrementally (new-only → modified → all)
- ✗ Design complete system upfront
- ✓ Document features as they stabilize
- ✗ Hold all documentation until every feature is final

---

## 7. Smart Defaults, Escape Hatches

**Principle:** The default path should work for 90% of cases. Provide escape hatches for the other 10%.

**This means:**
- Zero configuration should produce good results
- Advanced users can customize when needed
- Documentation explains both the simple path and the advanced options
- Never force everyone through the advanced workflow

**Trade-offs we accept:**
- Some duplication between simple and advanced paths
- Documentation covers both novice and expert paths
- Advanced features may be less polished

**Example decisions:**
- ✓ Default validation mode (new-only) optimized for common case
- ✗ Force everyone to choose a mode
- ✓ /check-continuity command with optional mode parameter
- ✗ Separate command for each mode
- ✓ Edit on GitHub web (simple) or local development (advanced)
- ✗ Require local setup for everyone

---

## Applying These Principles

When facing decisions, principles form a hierarchy:

1. **Writers First** - If it makes writing harder, it's wrong
2. **Automation** - If humans could do it wrong, automate it
3. **Fast Feedback** - If it takes too long, find a faster way
4. **Multiple Perspectives** - If someone needs a different view, generate it
5. **Transparency** - If it's mysterious, explain it
6. **Incremental** - If it's not perfect, ship it anyway and iterate
7. **Smart Defaults** - If most people need it, make it the default

**Principle conflicts:** When principles conflict, Writers First wins. Fast Feedback beats Perfection. Transparency beats Simplicity.

## Strategic Decisions

These are key architectural and interface decisions locked in to guide implementation:

### GitHub PRs as Primary Interface

**Decision:** GitHub pull requests are the primary and default interface for all writer interactions with the story pipeline.

**What this means:**
- Writers commit changes via GitHub web interface
- Writers trigger validation via PR comments (`/extract-story-bible`, `/check-continuity`)
- Writers see results in PR comments and GitHub Pages artifacts
- Writers never need to install tools or run commands locally

**CLI as Developer Tool:**
- CLI commands (`make metrics`, `make build`) exist for developers working on the pipeline
- CLI is an escape hatch for advanced users who prefer local workflows
- CLI is NOT documented in writer-facing guides (CONTRIBUTING.md, features/)
- CLI is NOT a supported workflow for story contributions

**Why:**
- Aligns with Vision: "Zero-barrier contribution - Edit in a web browser, no installation required"
- Aligns with Priority 1: "Author can contribute a new passage in under 5 minutes (web UI only)"
- Aligns with Principle 1: "Web-based contribution beats feature-rich local tooling"
- Aligns with Principle 7: Web is the smart default, CLI is the escape hatch

**Implications:**
- Feature specs describe PR-based workflows only
- Documentation assumes GitHub web interface
- Error messages guide writers to PR comment commands, not CLI
- Testing focuses on PR automation experience

---

## Non-Principles (What We Don't Value)

To clarify what we stand for, here's what we explicitly don't prioritize:

- ✗ Technical elegance over user experience
- ✗ Feature completeness over time to value
- ✗ Flexibility over focused functionality
- ✗ Innovation for innovation's sake
- ✗ Supporting every possible workflow
- ✗ Beautiful code over working software
- ✗ Comprehensive design docs over shipping iterations

These things aren't bad - they're just not what this project optimizes for.
