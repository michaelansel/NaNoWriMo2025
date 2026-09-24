# Build and deploy

**Status**: building

## User problem
A writer needs to see a passage working before merging it and to see the live story right after.
Anything between "I pressed merge" and "readers can play it" that needs a person is a day's
passage that does not go out. The pull request is also the writer's only window on the tooling:
if it fills with repeated bot comments, or a bot changes the writer's branch, writers stop
reading it, and the one note that mattered goes unseen.

## User stories
- As a writer, I want a playable preview of my pull request, so that I can click through my
  branch before merging.
- As a writer, I want one build comment that updates itself, so that my pull request stays
  readable after ten pushes.
- As a writer, I want a failed build to say it failed, so that I never merge something that does
  not play.
- As a writer, I want my merge to go live without anyone doing anything, so that readers see
  today's passage today.
- As a writer, I want automation to leave my branch alone, so that every commit on it is mine.

## Behavior
**On every push to a pull request against `main`** a hosted runner builds the pull request's merge
commit:

1. Installs the pinned tools and the `nanoif` package.
2. Runs the structure check and the formatting lint ([structure-check](structure-check.md)).
3. Builds every page into `dist/` ([output-formats](output-formats.md)): play, proofread, graph,
   all paths, metrics, Story Bible, passages, and the landing page.
4. Uploads `dist/` as the `story-preview` artifact, kept for 30 days.
5. Posts the Build comment: the size of each page, the number of story paths, and how to open the
   preview (download `story-preview` from the run, unzip, open `index.html`).

A separate `test` job runs the package tests and lint on every pull request and every push to
`main`.

**On a merge to `main`** the same build runs and `dist/` is deployed to GitHub Pages. Nobody
approves or triggers the deploy. Refreshing the Story Bible before the deploy is specified in
[story-bible](story-bible.md) (AC-story-bible-17).

**What automation never does**: commit or push to a pull request branch, or rewrite a writer's
file. Each kind of bot comment appears once per pull request and is edited in place
(AC-build-and-deploy-6 for the Build comment). Write access to the repository is reserved for the
main-branch jobs that record the `ai/` state files (AC-build-and-deploy-10).

**What the writer sees, and where**

| When | Where | What |
|---|---|---|
| Pull request opened or pushed | Checks list on the pull request | `build` and `test`, pending then green or red |
| Build finished | Pull request conversation | The Build comment with the preview steps |
| Build finished | Run page, Artifacts | `story-preview`, a zip of every page |
| Build finished | Files changed view | Structure and formatting annotations ([structure-check](structure-check.md)) |
| Merged | GitHub Pages | The landing page and every page, updated |
| Build failed | Checks list and run log | A red check naming the failing step |

The live site's address is the repository's GitHub Pages address; the landing page is its root.

## Acceptance criteria
- AC-build-and-deploy-1: Every push to a pull request against `main` runs the build and uploads a `story-preview` artifact holding the landing page and every output page, kept for 30 days. (verify: workflow)
- AC-build-and-deploy-2: `nanoif build all --repo <repo>` writes `allpaths.html`, `allpaths-index.json`, `changes.json`, `metrics.html`, `story-bible.html`, `story-bible.json` and `passages.html` to `dist/`, `story_graph.json` to `lib/artifacts/`, and a fresh `src/PathIdLookup.twee`.
- AC-build-and-deploy-3: When the compiled story is missing, `nanoif build all` exits non-zero with an error naming it and writes none of the later pages.
- AC-build-and-deploy-4: When any build step fails, the pull request's build check is red and the run log names the failing step; a failed build never shows as passed. (verify: workflow)
- AC-build-and-deploy-5: The Build comment states the size of each output page, the number of story paths, and the steps to download and open the preview. (verify: workflow)
- AC-build-and-deploy-6: A pull request has exactly one Build comment, found by the HTML marker `<!-- nano:build -->` and edited in place on every push. (verify: planned)
- AC-build-and-deploy-7: When the build fails, the Build comment says it failed and links the failed run instead of keeping the last successful numbers. (verify: planned)
- AC-build-and-deploy-8: A push to `main` deploys `dist/` to GitHub Pages with no manual step, and the deployed landing page serves the merged content within 5 minutes of the merge. (verify: workflow)
- AC-build-and-deploy-9: No workflow step commits or pushes to a pull request branch; after any number of automated runs, a pull request branch holds only its author's commits. (verify: workflow)
- AC-build-and-deploy-10: Jobs triggered by a pull request have read-only access to repository contents; only the main-branch jobs that write `ai/` state can push, and only to `main`. (verify: planned)
- AC-build-and-deploy-11: A new push to a pull request cancels that pull request's run in progress, and runs for different pull requests never queue behind each other. (verify: planned)
- AC-build-and-deploy-12: The `test` job runs the package tests and lint on every pull request and every push to `main`, and a failure turns its check red. (verify: workflow)

## Edge cases
- **Build step fails on writer content** (for example a passage the story format cannot parse):
  the build check is red; the structure notes, which run first, usually say why.
- **GitHub Actions is down or queued**: the check stays pending; nothing deploys and nothing is
  reported as passed. Merging while the check is pending is the writer's choice.
- **Two merges close together**: deploys run one after another; the later merge is what stays live.
- **Preview artifact expired** (after 30 days): re-run the workflow from the pull request's
  Checks tab to get a fresh one.
- **Preview on a phone**: the zip usually cannot be opened; the writer merges and plays the live
  story, or asks another writer to check the preview.
- **Pull request from a fork**: the build runs only after a maintainer approves the run.
- **Empty story** (only the infrastructure files and the `Start` stub): the build passes and every
  page renders, including the Story Bible placeholder.
- **Pull request that changes no story file** (for example `story-overrides.txt` only): the build
  and preview run as usual, so the writer sees the effect on the pages.
- **Structure errors in the pull request**: the build and preview still complete; the errors are
  reported by the structure check, not by a failed build.

## Soft goals
- The pull request build finishes within 2 minutes of the push.
- Writers read the Build comment only when something went wrong.

## Out of scope
- What each page shows ([output-formats](output-formats.md)).
- Structure findings and the formatting lint ([structure-check](structure-check.md)).
- The AI editors' comments and check runs ([continuity-review](continuity-review.md)).
- Story Bible extraction on `main` and its state file ([story-bible](story-bible.md)).
- Hosting anywhere other than GitHub Pages.
