# Structure check

**Status**: building

## User problem
Most of the defects that reach readers in a branching story are structural, not literary: a link
to a passage that does not exist, two writers using the same passage name, a day's passage that
nothing links to, a typo in `StoryData`. They need no AI to find, they can be pointed at an exact
file and line, and a writer can fix them in a minute. Writers also need formatting advice that
never touches their prose: a tool that rewrites a writer's file on their branch is not advice.

## User stories
- As a writer, I want a broken link reported on the exact line, so that I fix it before readers
  hit a dead link.
- As a writer, I want to know when my passage name is already taken, so that my link does not
  silently go to someone else's passage.
- As a writer, I want to know when nothing links to my day's passage, so that it does not sit
  unreachable after merge.
- As a writer, I want formatting notes as suggestions only, so that my words stay exactly as I
  wrote them.
- As a writer, I want the check to say when it could not run, so that silence always means clean.

## Behavior
On every pull request build, before the pages are built, two report-only tools read `src/` and
`story-overrides.txt` ([story-bible](story-bible.md) owns what the overrides mean):

**`nanoif check structure src/`**, deterministic:

| Code | Level | Meaning |
|---|---|---|
| `broken-link` | error | A link or `(link-goto:)`-style macro names a passage that does not exist |
| `duplicate-passage` | error | A passage name is declared twice; points at both places |
| `story-data-missing`, `story-data-invalid` | error | No `StoryData`, bad JSON, bad IFID, unknown start passage, or bad `storyStyle` values |
| `unreadable-file` | error | A `.twee` file is not valid UTF-8 text |
| `overrides-syntax` | error | A line of `story-overrides.txt` is not `directive: payload` with a known directive, or its payload does not fit its directive (for example a `pin:` without `\| "quote" @ passage`, an `alias:` without `=`) |
| `orphan-passage` | warning | No route from the start passage reaches it |
| `file-naming` | warning | A file breaks the naming rule ([web-editing](web-editing.md)) |
| `missing-day-passage` | warning | A writer's file has no `Day <N> <INITIALS>` passage with its initials |
| `story-style-unknown-key` | warning | `storyStyle` has a setting nothing reads |
| `dead-end` | info | A reachable passage has no links and is not tagged `ending` |

Passages tagged `footer`, `header`, `startup`, `script` or `stylesheet`, and the `StoryData` and
`StoryTitle` passages, are page furniture: never orphans or dead ends.

**`nanoif lint src/`**, formatting only, all warnings: a space after `::`; a blank line after a
passage header (not for `StoryData`, scripts or stylesheets); one blank line between passages; no
trailing whitespace; exactly one final newline; no runs of blank lines; a blank line around a
block of one-per-line choices and none inside it. Curly quotes are the writer's choice and are
never reported. The linter has no fix mode.

**Where the writer sees it.** A `Structure` check run on the pull request carries each finding
as an annotation on its file and line, shown in the "Files changed" view. The Build & Structure
comment ([build-and-deploy](build-and-deploy.md)) counts errors, warnings and notes, lists each
error with its file and line, and collapses the rest. Formatting notes are warning annotations
and a line in the run summary. Findings never stop the preview from being built, so the writer
can still play the branch. On `main` and for pull requests from forks, findings go to the run
summary and annotations only.

## Acceptance criteria
- AC-structure-check-1: A link to a missing passage is an error on the line of the link, naming the passage it is in and the missing target.
- AC-structure-check-2: A link inside a Harlowe `(link-goto:)` macro that names a missing passage is an error on that line.
- AC-structure-check-3: A passage name declared twice is an error at the second declaration that names the file and line of the first.
- AC-structure-check-4: `StoryData` that is not JSON, is not an object, has an IFID that is not a UUID, names a start passage that does not exist, or has an invalid `storyStyle` perspective, tense or protagonist is an error on the `StoryData` line.
- AC-structure-check-5: A story with no `StoryData` passage is an error, and reachability is then measured from `Start`.
- AC-structure-check-6: An unknown `storyStyle` key is a warning, and `StoryData` without `storyStyle` is valid.
- AC-structure-check-7: A passage no route from the start reaches is a warning, including passages reached only through other orphans; page-furniture passages are never reported.
- AC-structure-check-8: Reachability is measured from the start passage named in `StoryData`.
- AC-structure-check-9: A reachable passage with no links is reported as info, unless it is tagged `ending`.
- AC-structure-check-10: A file whose name breaks the naming rule is a warning; the infrastructure files and the generated `PathIdLookup.twee` are exempt.
- AC-structure-check-11: A writer's file with no `Day <N> <INITIALS>` passage whose initials match the file name is a warning on that file.
- AC-structure-check-12: A `.twee` file that is not valid UTF-8 is an error naming the file.
- AC-structure-check-13: Each bad line of `story-overrides.txt` (not `directive: payload`, an unknown directive, no payload, or a payload that does not fit its directive) is an error with its line number; an unknown directive's message lists the known ones and a payload error's message shows the directive's expected form; comment lines, blank lines and a missing file produce nothing.
- AC-structure-check-14: `nanoif check structure` exits 1 when there is an error and 0 when there are only warnings and info.
- AC-structure-check-15: Findings are listed errors first, then warnings, then info.
- AC-structure-check-16: In GitHub format each finding is one annotation of the matching level (error, warning, notice) carrying its file and line, with commas, colons and newlines escaped.
- AC-structure-check-17: On a pull request, every structure finding that names a file appears as an annotation on its file and line, and one that names no file appears in the Build comment. (verify: workflow)
- AC-structure-check-18: If the structure check cannot run, or the build fails before it, the Build comment says structure was not checked and the `Structure` check run on that commit is failure; it never shows an empty list of findings or the previous push's result.
- AC-structure-check-19: Structure findings, errors included, never stop the pull request preview from being built. (verify: workflow)
- AC-structure-check-20: Every pull request from a branch of this repository has a `Structure` check run whose conclusion is failure when there is an error, neutral when there are warnings and no error, and success when there are only info notes or no findings.
- AC-structure-check-21: The Build comment lists the number of structure errors, warnings and info notes, and each error with its file and line.
- AC-structure-check-22: The linter reports each of its seven rules as `file:line: [rule] message`.
- AC-structure-check-23: The linter never changes a file, and `nanoif lint --fix` is rejected as an unknown option.
- AC-structure-check-24: Curly quotes and apostrophes are never reported by the linter.
- AC-structure-check-25: `StoryData`, script and stylesheet passages are not required to have a blank line after their header.
- AC-structure-check-26: On a pull request, formatting findings appear as warning annotations and never turn the build red. (verify: workflow)

## Edge cases
- **Empty story** (the `Start` stub only): no errors; `Start` is reported as a dead end (info)
  until a writer links it to a day's passage.
- **A day's passage nothing links to yet**: an orphan warning, not an error, so a writer can open
  the pull request before adding the link.
- **Same name in the same file twice**: reported like any duplicate.
- **`story-overrides.txt` absent**: nothing is reported; the file is optional.
- **Check crashes on unexpected input**: the step fails and the run is red; the crash is a bug to
  fix, never a clean result.
- **Fork pull requests**: the check runs with the build once a maintainer approves the run.

## Soft goals
- A writer fixes a broken link from the annotation alone, without opening the run log.
- Most pull requests have no structure notes at all.

## Out of scope
- Continuity, style and meaning ([continuity-review](continuity-review.md)).
- What the overrides directives do to the Story Bible ([story-bible](story-bible.md)).
- Automatic fixes of any kind.
- Spelling and grammar.
