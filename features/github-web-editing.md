# Feature PRD: GitHub Web-Based Editing Workflow

**Status:** Released ✅
**Owner:** Product Manager
**Last Updated:** 2025-11-22

---

## User Problem

**For writers participating in NaNoWriMo:**
- Traditional interactive fiction tools require programming knowledge and complex local development environments
- Installing software, configuring build tools, and managing dependencies creates an intimidating barrier to entry
- Writers want to contribute daily using whatever device is available (laptop, tablet, even phone)
- Setting up local development can take hours or days, killing momentum during time-sensitive writing challenges

**Pain Point:** "I have a great idea for a story branch, but I can't contribute because I don't know how to install Tweego, configure Git, or set up a development environment."

---

## User Stories

### Story 1: First-Time Contributor
**As a** writer new to interactive fiction
**I want to** contribute a story passage using only my web browser
**So that** I can participate in the collaborative story without technical setup

**Acceptance Criteria:**
- Writer can edit .twee files directly in GitHub web interface
- Writer can create a new branch with one click
- Writer can open a pull request without using command line
- Entire contribution takes less than 5 minutes from idea to PR
- Works on any device with a web browser (including mobile)

---

### Story 2: Mobile Contributor
**As a** writer on the go
**I want to** contribute a passage from my phone or tablet
**So that** I can write whenever inspiration strikes, not just at my desk

**Acceptance Criteria:**
- GitHub web interface works on mobile devices
- Text editing works with phone/tablet keyboards
- Can create branches and PRs from mobile
- Preview artifacts can be downloaded and tested on mobile

---

### Story 3: Non-Technical Writer
**As a** writer with no programming experience
**I want to** contribute without learning Git commands or development tools
**So that** I can focus on writing instead of fighting with tooling

**Acceptance Criteria:**
- No command line required
- No software installation required
- Clear, visual workflow using familiar web interface
- Error messages are writer-friendly, not technical
- CONTRIBUTING.md written for writers, not developers

---

## Success Metrics

### Primary Metrics
- **Time to first contribution:** <5 minutes from clicking "edit" to creating PR
- **Contribution method:** 100% of contributions via GitHub web interface (no local development required)
- **Setup blockers:** Zero contributors blocked due to installation or setup issues
- **Device diversity:** Contributions from desktop, mobile, and tablet devices

### Secondary Metrics
- **Contributor retention:** Writers who contribute once contribute again
- **Daily contributions:** Multiple contributions per day during NaNoWriMo
- **Edit frequency:** Writers make quick edits and fixes without hesitation

### Qualitative Metrics
- Writer feedback: "I didn't need to install anything!"
- No questions about setup or installation in GitHub issues
- Writers focus discussions on story, not tooling

---

## How It Works

### User Flow

1. **Browse to src/ directory** in GitHub repository
2. **Click on any .twee file** to view its contents
3. **Click pencil icon (✏️)** to edit
4. **Write passage using Twee syntax** (documented in CONTRIBUTING.md)
5. **Scroll to bottom**, select "Create a new branch"
6. **Name the branch** (e.g., "add-forest-path")
7. **Click "Propose changes"**
8. **Click "Create pull request"**
9. **Wait for automated build** (GitHub Actions runs automatically)
10. **Download preview artifact** from Actions tab
11. **Test changes** by opening downloaded index.html
12. **Merge when ready** - changes go live in ~2 minutes

### What Makes This Possible

**GitHub's Built-In Tools:**
- Web-based text editor with syntax highlighting
- Visual branch creation workflow
- Pull request interface
- Actions tab for viewing build results and downloading artifacts

**Our Automation:**
- GitHub Actions builds all output formats on every push
- Uploads preview artifacts for testing
- Posts PR comments with download links and instructions
- Deploys to GitHub Pages automatically on merge

---

## Edge Cases

### Edge Case 1: Syntax Errors
**Scenario:** Writer makes a syntax error in .twee file (e.g., forgets `::` before passage name)

**Current Behavior:**
- Build fails in GitHub Actions
- No preview artifact generated
- Writer sees red X on PR

**Desired Behavior:**
- Build shows clear error message about syntax issue
- Error message points to specific line and explains how to fix
- Writer can edit directly in GitHub to fix and re-trigger build

**Status:** Partially handled - build fails visibly, but error messages could be more writer-friendly

---

### Edge Case 2: Broken Links
**Scenario:** Writer creates link to passage name that doesn't exist

**Current Behavior:**
- Build succeeds (Tweego compiles broken links)
- Broken link appears in preview
- Writer discovers when testing

**Desired Behavior:**
- Build warns about broken links (non-blocking)
- AI continuity checker flags broken links
- Clear guidance on how to fix

**Status:** Handled by AI continuity checker

---

### Edge Case 3: Large Files
**Scenario:** Writer tries to create a very long passage (10,000+ words in one passage)

**Current Behavior:**
- GitHub web editor works but may be slow
- Build succeeds
- Large passages make proofreading difficult

**Desired Behavior:**
- No technical issues (works fine)
- CONTRIBUTING.md guidance suggests breaking large content into multiple passages

**Status:** Working as intended - no technical limitation

---

### Edge Case 4: Simultaneous Edits
**Scenario:** Two writers edit the same file simultaneously in different branches

**Current Behavior:**
- Each writer creates their own branch
- Both PRs build successfully
- Merge conflict only occurs if both modify the same lines
- GitHub shows conflict and requires manual resolution

**Desired Behavior:**
- Branch isolation prevents conflicts during writing
- If conflict occurs, GitHub provides visual merge tool
- CONTRIBUTING.md explains how to resolve conflicts

**Status:** Working as intended - branch model handles this well

---

### Edge Case 5: Mobile Editing Limitations
**Scenario:** Writer tries to edit complex passage on phone with small screen

**Current Behavior:**
- GitHub web interface works but can be cramped
- Text area is small on mobile
- Keyboard covers part of screen
- Preview is difficult to see

**Desired Behavior:**
- Writer can contribute, even if not ideal
- Mobile editing prioritized for small changes and quick fixes
- Larger contributions encouraged from desktop

**Status:** Acceptable tradeoff - mobile works but desktop is better experience

---

### Edge Case 6: Offline Writing
**Scenario:** Writer wants to draft content offline, then contribute later

**Current Behavior:**
- GitHub web interface requires internet connection
- No offline editing support

**Desired Behavior:**
- Writer can draft in any text editor offline
- Copy/paste into GitHub when back online
- CONTRIBUTING.md explains this workflow

**Status:** Working as intended - GitHub is inherently online, but workaround is simple

See [architecture/github-web-editing.md](../architecture/github-web-editing.md) for technical design.

---

## What Could Go Wrong?

### Risk 1: GitHub Service Outage
**Impact:** High - writers cannot contribute
**Mitigation:** Accept this risk - GitHub has excellent uptime
**Fallback:** Writers can draft content offline and contribute when GitHub is back

---

### Risk 2: Confusing GitHub UI Changes
**Impact:** Medium - GitHub updates UI, screenshots in docs become outdated
**Mitigation:** Focus on concepts over specific UI in documentation
**Fallback:** Update screenshots if major UI changes occur

---

### Risk 3: Large Files Hit GitHub Limits
**Impact:** Low - GitHub has generous file size limits
**Mitigation:** Individual .twee files unlikely to hit limits
**Fallback:** Split large files if needed

---

### Risk 4: Mobile Experience Deteriorates
**Impact:** Low - mobile is secondary contribution method
**Mitigation:** Prioritize desktop experience, accept mobile limitations
**Fallback:** Writers can draft offline and paste from desktop

---

## Future Enhancements

### Nice to Have (Not Planned)
- **GitHub Codespaces integration:** Full development environment in browser
  - **Why not:** Adds complexity, current approach works well

- **Custom GitHub Action UI:** More visual build status
  - **Why not:** Current UI is sufficient, low ROI

- **Real-time preview:** See changes without building
  - **Why not:** Build time is already <2 minutes, fast enough

---

## Metrics Dashboard

### Current Performance (as of Nov 22, 2025)
- ✅ **100% web-based contributions:** No local development required
- ✅ **<5 minute time to first contribution:** Goal achieved
- ✅ **Zero setup blockers:** No installation issues reported
- ✅ **Multi-device support:** Desktop and mobile contributions confirmed
- ✅ **Daily contributions:** Multiple authors contributing regularly

---

## Success Criteria Met

- [x] Writers can contribute using only web browser
- [x] No software installation required
- [x] Works on multiple devices (desktop, mobile, tablet)
- [x] Complete contribution in <5 minutes
- [x] Clear documentation for non-technical writers
- [x] Zero contributors blocked by setup issues
- [x] 100% of contributions via GitHub web interface
- [x] Fast feedback loop (<2 minutes to preview)

---

## Related Documents

- [CONTRIBUTING.md](/home/user/NaNoWriMo2025/CONTRIBUTING.md) - Step-by-step contribution guide
- [README.md](/home/user/NaNoWriMo2025/README.md) - Quick start guide
- [features/automated-build-deploy.md](/home/user/NaNoWriMo2025/features/automated-build-deploy.md) - Build automation that enables web editing
- [PRINCIPLES.md](/home/user/NaNoWriMo2025/PRINCIPLES.md) - "Writers First, Always" principle

---

## Lessons Learned

### What Worked Well
- **GitHub's native UI is familiar:** Writers already know how to edit text on the web
- **Branch model prevents conflicts:** Writers work independently without blocking each other
- **Fast feedback loop:** <2 minutes from commit to preview keeps momentum
- **Mobile capability is valuable:** Quick edits from anywhere increases contribution frequency

### What Could Be Better
- **Error messages could be more writer-friendly:** Technical errors from Tweego can be confusing
- **Mobile editing is cramped:** Works but not ideal for large contributions
- **First-time setup could use video:** Some writers prefer video to written docs

### What We'd Do Differently
- **Consider GitHub Codespaces earlier:** Would provide full IDE in browser
- **More visual documentation:** Screenshots and videos alongside text
- **Interactive tutorial:** Walk through first contribution step-by-step

---

## Stakeholder Sign-Off

- [x] Product Manager: Approved
- [x] Writers: Confirmed working well (based on daily usage)
- [x] Technical Lead: Implementation complete and stable
