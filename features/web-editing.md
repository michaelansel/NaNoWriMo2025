# Web editing

**Status**: shipped

## User problem
The writers are not programmers. They write from a browser, sometimes from a phone, with no
terminal, no local copy of the repository, and no wish to learn one. Every day they add one
passage and connect it to the story. Anything that asks them to install a tool, run a command,
learn a second naming scheme, or clean up after a bot takes time away from writing.

## User stories
- As a writer, I want to add today's passage from the GitHub web page, so that I never install anything.
- As a writer, I want one naming rule for my file and my entry passage, so that the story, the
  passage index, and the checks all know who wrote what on which day.
- As a writer, I want to link to any passage by its name, so that I do not need to know which
  file it lives in.
- As a writer, I want my pull request branch to hold only my own commits, so that what I review
  is what I wrote.
- As a first-time writer, I want a step-by-step guide that gets me to an open pull request, so
  that I can contribute on my first day.

## Behavior
The daily pattern is two changes in one pull request, both made in the GitHub web editor:

1. Edit an existing passage (usually where yesterday's writing ends) and add a link to today's
   entry passage, for example `[[Wait for morning->Day 2 EV]]`.
2. Create `src/<INITIALS>-<YYYYMMDD>.twee`. Its first passage is the entry passage
   `:: Day <N> <INITIALS>`; more passages may follow in the same file.

The writer makes the first change, chooses "Create a new branch for this commit", opens the pull
request, then adds the new file to the same branch. Links point at passage names, never at file
names, so a passage may link to a passage in any writer's file.

From the moment the pull request opens, automation runs on every push without being asked: the
build and preview ([build-and-deploy](build-and-deploy.md)), the structure notes
([structure-check](structure-check.md)), and the editors' notes
([continuity-review](continuity-review.md)). Automation reads the branch and comments on the pull
request; it never commits to the branch. The writer merges when satisfied, and the story goes
live without further steps.

The writer-facing guides are `WRITING-WORKFLOW.md` (the daily pattern) and `CONTRIBUTING.md` (the
first-timer walkthrough). Both describe only the GitHub web UI.

### The naming rule
| What | Pattern | Example from the eval story |
|---|---|---|
| Prose file | `src/<INITIALS>-<YYYYMMDD>.twee` | `EV-` + the date, for the writer EV |
| Entry passage | `:: Day <N> <INITIALS>` | `:: Day 2 EV` |
| Other passages | any unique name | `:: The crossing`, `:: Hollin Reach` |

- INITIALS are 1 to 10 letters and are the same in the file name and the entry passage.
- The date is the writing day as year, month, day, and must be a real calendar date.
- The infrastructure files `Start`, `StoryData`, `StoryTitle`, `StoryStyles` and
  `PathIdDisplay` keep their own names. There is no other file pattern.

### Link forms
Writers may use any of these; every tool reads them the same way:
`[[Target]]`, `[[Text->Target]]`, `[[Target<-Text]]`, `[[Text|Target]]`, and the Harlowe macros
`(link-goto: "Text", "Target")`, `(click-goto:)`, `(link-reveal-goto:)` and `(goto:)`.

## Acceptance criteria
- AC-web-editing-1: A file named `<INITIALS>-<YYYYMMDD>.twee` with 1 to 10 letters of initials and a real calendar date is recognised as that writer's file for that date, with or without the `.twee` suffix.
- AC-web-editing-2: A six-digit date (`<INITIALS>-<YYMMDD>`), an impossible date (day 31 of November), a space in the initials, or an infrastructure name such as `Start.twee` is not recognised as a writer's file.
- AC-web-editing-3: Every `.twee` file under `src/`, including files in subfolders, is part of the story, and files with any other extension are not.
- AC-web-editing-4: `[[Target]]`, `[[Text->Target]]`, `[[Target<-Text]]` and `[[Text|Target]]` are all read as a link to `Target`; when the text itself contains an arrow, the rightmost `->` separates text from target.
- AC-web-editing-5: The Harlowe macros `(link-goto:)`, `(click-goto:)`, `(link-reveal-goto:)` and `(goto:)` are read as links to the passage they name.
- AC-web-editing-6: A link from one writer's file to a passage declared in another writer's file resolves, and no structure error is reported for it.
- AC-web-editing-7: A writer can edit a passage, commit to a new branch, create the day's file on that branch, and open a pull request using only github.com in a browser. (verify: manual)
- AC-web-editing-8: `WRITING-WORKFLOW.md` is under 150 lines, every step in it happens in the GitHub web UI, and it names no command-line tool. (verify: manual)
- AC-web-editing-9: `CONTRIBUTING.md` takes a first-time writer from opening the repository to an open pull request using only the web UI, and links to `WRITING-WORKFLOW.md` for the daily routine. (verify: manual)
- AC-web-editing-10: Every file name and entry passage shown in the writer guides follows the naming rule, and no other naming pattern appears in them. (verify: manual)

## Edge cases
- **File saved without `.twee`**: it is not part of the story. The link added to the entry
  passage then points at nothing and is reported as a broken link
  ([structure-check](structure-check.md)), which is how the writer finds out.
- **Name that breaks the rule** (for example `chapter-one.twee`): the story still builds; the
  structure check adds a naming warning.
- **Two writers declare the same passage name**: the structure check reports a duplicate error on
  the second declaration and names the first.
- **Two writers edit the same passage on the same day**: the second pull request shows a merge
  conflict; GitHub's web conflict editor resolves it. No automation resolves conflicts.
- **Commit straight to `main`**: collaborators may be offered this by the web editor. The guides
  tell writers to choose a new branch. A direct commit builds and deploys like a merge, with no
  preview and no editors' notes.
- **Editing on a phone**: the web editor works; the preview is a zip file most phones cannot
  open, so the writer plays the live story after merging.
- **Pull request from a fork**: it builds once a maintainer approves the run; the AI editors do
  not run on it ([continuity-review](continuity-review.md)).
- **Several passages in one day**: they all go in the day's file after the entry passage; a
  writer never needs a second file for the same day.
- **Writing for a missed day**: the file carries the date it was written, and the entry passage
  carries the day it is for; the two need not match.

## Soft goals
- A writer adds the day's passage with under five minutes spent on anything other than writing.
- A writer who has never used GitHub opens a first pull request on their first day.

## Out of scope
- Local editing, the Twine desktop app, and any command-line workflow for writers.
- Real-time co-editing of one passage.
- Story formats other than Harlowe, and variables, inventory or other game mechanics.
- What the automated checks report (see the linked notes).
