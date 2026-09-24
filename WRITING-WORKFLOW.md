# Daily Writing Workflow

Everything here happens on the GitHub website. You never need to install anything.
First time? Start with [CONTRIBUTING.md](CONTRIBUTING.md).

## The pattern

Every day is **two changes in one pull request**:

1. **Edit an existing passage** to add a link to today's passage.
2. **Create a new file** with today's writing.

## Example: writer EV, day 2

### 1. Edit the passage where the story should branch

In `src/`, open the file that holds the passage (here, `The crossing`), click the pencil icon,
and add a link to today's entry passage:

```twee
:: The crossing

...He let her pass. The far jetty came up out of the fog.

[[Hollin Reach]]
[[Wait for morning->Day 2 EV]]
```

### 2. Create today's file

Click **Add file → Create new file** and name it `src/EV-YYYY1102.twee`, with this year in place
of `YYYY`:

```twee
:: Day 2 EV

Morning came up thin and yellow over the reach...
```

## Naming

| What | Pattern | Example |
|---|---|---|
| File | `src/<INITIALS>-<YYYYMMDD>.twee` | `src/EV-YYYY1102.twee` |
| First passage in the file | `:: Day <N> <INITIALS>` | `:: Day 2 EV` |
| Any other passage | any name not already used | `:: The toll` |

- Use the same initials in the file name and the `Day` passage.
- The file name must end in `.twee`, or the story will not see it.
- Put all of a day's passages in that day's file.

## Twee in one minute

```twee
:: Passage Name

Your text here.

[[Link text->Passage Name]]
[[Passage Name]]
```

- Links point at **passage names** (the text after `::`), never at file names.
- Every passage name must be unique across all files.
- Leave one blank line after the `::` line and between passages.

## Step by step

1. Open the passage you want to branch from, click the pencil icon, add your link.
2. Click **Commit changes**, choose **Create a new branch for this commit**, and click
   **Propose changes**, then **Create pull request**.
3. On the pull request page, open your branch (click its name near the top), then
   **Add file → Create new file** for today's file. Commit it to the same branch.
4. Wait a few minutes for the checks (below). Read any notes, fix what you agree with by editing
   the file on your branch.
5. Click **Merge pull request**. The story is live a few minutes later.

## What happens automatically

You do not need to ask for any of this. Nothing here ever changes your files or adds commits to
your branch.

| What | Where you see it | What to do |
|---|---|---|
| **Build** | The `build` check, and a **Build & Structure** comment | Red: open the check to see which step failed |
| **Preview** | `story-preview`, linked from the Build & Structure comment | Download, unzip, open `dist/index.html`, play your branch |
| **Structure notes** | The `Structure` check, the Build & Structure comment, and notes on your lines in **Files changed** | Fix errors (for example a broken link); warnings are advice |
| **Formatting notes** | Notes on your lines in **Files changed** | Optional: spacing suggestions only |
| **Continuity Editor** | One comment and a `Continuity Editor` check, updated on every push | Read the quotes; fix, or dismiss (below) |
| **Style Editor** | One comment and a `Style Editor` check, updated on every push | Checks point of view, tense and main character |

**Structure errors** are the ones to fix before merging: a link to a passage that does not exist,
a passage name someone else already used, or a problem in `StoryData`. **Warnings** include a
passage nothing links to yet, and a file name that does not follow the pattern.

**Editor findings** each show two quotes that disagree and the passages they come from. You
decide. If the editor is wrong, reply on the pull request:

```
/dismiss f-1a2b3c4d it's a dream sequence
```

using the id shown on the finding. It will not come back unless one of those passages changes.

An editor's check is grey when it has findings and red when it could not read some passages; it
never blocks merging.

**"AI review unavailable"** means the editors could not read your passages this time. It is not
an all-clear. Your pull request still builds and can still be merged.

## Commands you can comment on a pull request

Most days you need none of these.

| Command | What it does |
|---|---|
| `/dismiss <id> [reason]` | Hides a finding you disagree with |
| `/check-continuity` | Runs the editors again on your changed passages |
| `/check-continuity all` | Reviews the whole story; the comment shows what it cost |
| `/check-continuity passage=<name>` | Reviews one passage |

## The pages

After merging, the story's site has a landing page linking to: **Play**, **Proofread** (all the
text on one page), **All paths** (every route through the story), **Metrics** (word counts),
**Passages** (every passage name, its file, and its links: handy for linking), **Story Bible**
(the cast, places and rules; a placeholder until the Bible is first extracted), and **Graph** (a
map of the story).

`story-overrides.txt` at the top of the repository is where you will teach the Story Bible
things (two names for one person, a word that is not a character, a deliberate mystery). For now
the build only checks that each line is written correctly. The [Story Bible note](features/story-bible.md#behavior) shows one
example of each kind of line.

## Checklist

- [ ] Link added to an existing passage, pointing at `Day <N> <INITIALS>`
- [ ] New file `src/<INITIALS>-<YYYYMMDD>.twee` starting with `:: Day <N> <INITIALS>`
- [ ] Build green, structure errors fixed, preview played
- [ ] Editors' notes read
- [ ] Merged
