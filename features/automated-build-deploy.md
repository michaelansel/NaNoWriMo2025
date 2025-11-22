# Feature PRD: Automated Build and Deployment

**Status:** Released ✅
**Owner:** Product Manager
**Last Updated:** 2025-11-22

---

## User Problem

**For writers wanting fast iteration:**
- Manual builds require local tools and technical knowledge
- Manual deployment is error-prone and time-consuming
- Waiting for builds kills writing momentum during time-sensitive challenges
- Testing changes before merge requires complex local setup
- Writers need confidence that their changes will work when deployed

**Pain Point:** "I just want to write and see my changes live. I don't want to install build tools, run commands, or manually deploy files. Every minute spent on deployment is a minute not spent writing."

---

## User Stories

### Story 1: Writer Seeing Changes Live
**As a** writer who just committed a change
**I want** my changes to automatically go live on the website
**So that** I can see the published result without manual deployment

**Acceptance Criteria:**
- Changes merged to main deploy automatically
- Deployment completes in under 2 minutes
- No manual deployment steps required
- Live site updates immediately after deployment
- No failed deployments (100% success rate)

---

### Story 2: Writer Testing Before Merge
**As a** writer with changes in a PR
**I want** to download and test a preview build
**So that** I can verify my changes work before merging to main

**Acceptance Criteria:**
- Every PR generates preview artifacts
- Download link posted in PR comment
- Preview includes all 4 output formats
- Can test locally before merging
- Preview regenerates on every commit to PR branch

---

### Story 3: Contributor Seeing Build Status
**As a** contributor waiting for their PR to build
**I want** to see clear build status and results
**So that** I know whether my changes built successfully

**Acceptance Criteria:**
- PR shows green checkmark when build succeeds
- PR comment shows build stats (file sizes, path counts)
- Build errors are visible and actionable
- Can see build logs if needed
- Build status updates automatically

---

### Story 4: Collaborator Reviewing PR
**As a** reviewer checking another author's PR
**I want** to download and test their changes before approving
**So that** I can verify the story works as intended

**Acceptance Criteria:**
- Preview artifacts available for every PR
- Clear instructions for downloading and testing
- All formats included in preview
- Can test exactly what will be deployed
- Preview matches final deployment

---

## Success Metrics

### Primary Metrics
- **Build success rate:** >99% (nearly all builds succeed)
- **Build speed:** <2 minutes from push to preview artifact
- **Deploy speed:** <2 minutes from merge to live
- **Total time commit to live:** <2 minutes (goal achieved)
- **Failed deployments to main:** 0

### Secondary Metrics
- **Build reliability:** Consistent build times and results
- **Artifact availability:** 100% of PRs have preview artifacts
- **Comment accuracy:** Build stats match actual output
- **Preview usage:** PRs tested before merge

### Qualitative Metrics
- Writer feedback: "Changes go live instantly!"
- No complaints about slow builds or deployments
- No confusion about how to test changes

---

## How It Works

### Workflow Trigger Events

**On Pull Request:**
- Runs full build
- Uploads preview artifacts
- Posts PR comment with stats and download link
- Does NOT deploy to production

**On Push to Main:**
- Runs full build
- Uploads artifacts to GitHub Pages
- Deploys to live site
- Site goes live automatically

---

### What Happens During Build

**For Pull Requests:**
- All 4 output formats generated (Harlowe, Paperthin, DotGraph, AllPaths)
- Preview artifact uploaded for download
- PR comment posted with build stats and download link
- Resources file updated and committed back to PR branch
- No deployment to production (preview only)

**For Main Branch:**
- All 4 output formats generated
- Deployed to GitHub Pages automatically
- Live site updated within 2 minutes
- Available at https://michaelansel.github.io/NaNoWriMo2025/

See [architecture/automated-build-deploy.md](../architecture/automated-build-deploy.md) for technical design.

---

## Edge Cases

### Edge Case 1: Build Failure
**Scenario:** Tweego compilation fails due to syntax error

**Current Behavior:**
- Build fails with red X on PR
- No preview artifact generated
- GitHub shows build logs with error

**Desired Behavior:**
- Clear error message in build logs
- Point to specific file and line causing error
- Writer can fix directly in GitHub and re-trigger

**Status:** Partially handled - errors visible but could be more user-friendly

---

### Edge Case 2: Resource File Conflicts
**Scenario:** Two PRs both update Resource-Passage Names simultaneously

**Current Behavior:**
- Each PR generates its own resource file
- Merge conflict only if both edit same passages
- GitHub shows conflict, requires manual resolution

**Desired Behavior:**
- Resource file regenerates on merge
- No manual resolution needed
- Automated resolution preferred

**Status:** Acceptable - rare occurrence, GitHub handles conflicts

---

### Edge Case 3: Very Large Builds
**Scenario:** Story grows to 500+ passages, 1000+ paths

**Current Behavior:**
- All formats build successfully
- Build time may increase
- Output files may grow large

**Desired Behavior:**
- Monitor build performance
- Optimize if approaching 2-minute limit
- Parallelize builds if needed

**Status:** Not yet encountered - current builds well under 2 minutes

---

### Edge Case 4: GitHub Actions Quota
**Scenario:** Excessive builds consume GitHub Actions minutes

**Current Behavior:**
- GitHub has generous free tier
- Builds are fast, minimal resource usage
- Unlikely to hit limits

**Desired Behavior:**
- Monitor usage
- Optimize if approaching limits
- Repository is public, free tier sufficient

**Status:** No issues - well within free tier limits

---

### Edge Case 5: Artifact Download Failure
**Scenario:** Writer can't download preview artifact

**Current Behavior:**
- Artifact available via Actions tab
- Download requires GitHub login
- 30-day retention period

**Desired Behavior:**
- Clear instructions for downloading
- Artifact available throughout PR review period
- Retention period sufficient for review

**Status:** Working as intended - 30 days is ample time

---

### Edge Case 6: Stale Preview Artifacts
**Scenario:** Writer downloads old artifact after pushing new commits

**Current Behavior:**
- Each commit triggers new build
- New artifact replaces old one
- Only latest artifact available

**Desired Behavior:**
- Clear indication of which commit artifact matches
- Writer downloads latest build
- Workflow run number helps identify latest

**Status:** Working as intended - latest artifact is correct one

---

## What Could Go Wrong?

### Risk 1: GitHub Actions Outage
**Impact:** High - no builds or deployments during outage
**Mitigation:** Accept this risk - GitHub has excellent uptime
**Fallback:** Wait for service restoration, builds resume automatically

---

### Risk 2: Build Breaking Changes
**Impact:** Medium - upstream tool changes break our build
**Mitigation:** Pin versions of all tools (Tweego, formats, actions)
**Fallback:** Update build script to handle changes

---

### Risk 3: GitHub Pages Limits
**Impact:** Low - output exceeds Pages limits (1GB max)
**Mitigation:** Monitor output sizes, optimize if approaching limits
**Fallback:** Host large files elsewhere (GitHub releases)

---

### Risk 4: Slow Builds
**Impact:** Medium - build time exceeds 2-minute target
**Mitigation:** Monitor performance, optimize bottlenecks
**Fallback:** Parallelize builds, cache dependencies

---

## Future Enhancements

### Considered but Not Planned
- **Build caching:** Cache Tweego and formats to speed up builds
  - **Why not:** Builds already fast enough, caching adds complexity

- **Parallel format builds:** Build all formats simultaneously
  - **Why not:** Sequential builds fast enough, parallelization adds complexity

- **Custom domain:** Use custom domain instead of github.io
  - **Why not:** Current URL works fine, custom domain adds setup overhead

- **Build notifications:** Slack/email notifications for builds
  - **Why not:** PR comments sufficient, notifications would be noise

---

## Metrics Dashboard

### Current Performance (as of Nov 22, 2025)
- ✅ **Build success rate:** 100% (all recent builds succeeded)
- ✅ **Average build time:** ~90 seconds (well under 2-minute target)
- ✅ **Average deploy time:** ~60 seconds to live
- ✅ **Total commit to live:** <2 minutes (goal achieved)
- ✅ **Failed deployments:** 0
- ✅ **Artifact availability:** 100% of PRs have preview

### Build Performance Breakdown
- Checkout: ~5s
- Resource generation: ~1s
- Tweego installation: ~15s
- Format downloads: ~10s
- Harlowe build: ~10s
- Paperthin build: ~5s
- DotGraph build: ~5s
- AllPaths build: ~20s
- Artifact upload: ~10s
- PR comment: ~5s
- **Total:** ~90s

---

## Success Criteria Met

- [x] Automatic builds on every push and PR
- [x] Build completes in <2 minutes
- [x] Deploy completes in <2 minutes
- [x] 100% build success rate
- [x] Preview artifacts for every PR
- [x] PR comments with build stats
- [x] Zero manual deployment steps
- [x] Live site updates automatically on merge

---

## Related Documents

- [.github/workflows/build-and-deploy.yml](/home/user/NaNoWriMo2025/.github/workflows/build-and-deploy.yml) - Workflow implementation
- [features/multiple-output-formats.md](/home/user/NaNoWriMo2025/features/multiple-output-formats.md) - What gets built
- [features/github-web-editing.md](/home/user/NaNoWriMo2025/features/github-web-editing.md) - User workflow this enables
- [PRINCIPLES.md](/home/user/NaNoWriMo2025/PRINCIPLES.md) - "Fast Feedback Loops" principle

---

## Lessons Learned

### What Worked Well
- **Fast builds:** <2 minutes keeps momentum high
- **Automatic everything:** Writers never think about builds or deployment
- **PR previews:** Testing before merge prevents bad deployments
- **Resource auto-commit:** Keeps resource file always current

### What Could Be Better
- **Error messages:** Build failures could have more user-friendly explanations
- **Build caching:** Could optimize with dependency caching (though already fast)
- **Parallel builds:** Could build formats in parallel (though sequential is fast enough)

### What We'd Do Differently
- **Earlier performance monitoring:** Could have established baselines from day one
- **Build time budgets:** Could have set per-step time budgets to track performance
- **More build testing:** Could have tested build failures more thoroughly
