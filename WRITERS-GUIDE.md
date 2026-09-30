# Writer's Guide

You write each day's part of the story in your web browser; helpers check it for you, and once
you merge it, it appears in the playable story for everyone.

## How it works

The story is one big choose-your-own-adventure that we all add to. Each day you write a new scene,
called a **passage**, and connect it to an earlier one with a choice the reader can click.

1. You write your passage on the GitHub website. Nothing to install.
2. You send it as a **pull request**: a draft that others can see, but that is not in the story yet.
3. Within a few minutes, helpers read your draft and leave notes on it.
4. You read the notes and change anything you agree with. The notes are advice; you decide.
5. You click **Merge**. A few minutes later your passage is in the story on the story's site.

Until you merge, your writing stays in your draft, so you cannot break the story by trying things.

## Your daily routine

Each day is two small changes in one pull request: add a choice to an earlier passage, then write
your new passage. It takes about fifteen minutes the first time.

**First time only:** you need a GitHub account, and the story's organiser must add you as a
collaborator. Accept the invitation email, then pick your **initials**, 1 to 10 letters (for example EV). You use
them every day.

**Step 1: add the choice that leads to your passage**

1. Open the story's `src` folder and click the file holding the passage where your part should
   begin. The story's **Passages** page lists every passage and the file it is in.
2. Click the pencil icon at the top right to edit it.
3. At the end of that passage, add a choice that points at your new passage, for example
   `[[Wait for morning->Day 2 EV]]`.
4. Click **Commit changes**, choose **Create a new branch for this commit and start a pull
   request**, give the branch a short name like `ev-day-2`, and click **Propose changes**.
5. Click **Create pull request**. Do not merge yet.

**Step 2: write your passage**

1. On your pull request, click your branch name near the top.
2. Click **Add file**, then **Create new file**.
3. Name the file and write your passage (the next section shows how).
4. Click **Commit changes**, making sure it saves to your branch, not `main`.

**Step 3: read the notes and merge**

1. Go back to your pull request and wait a few minutes for the notes.
2. Change anything you agree with by editing the file on your branch. The helpers read it again
   each time.
3. When you are happy, click **Merge pull request**.

## Naming your file and linking it in

The helpers find your passage by its name, so three names have to follow a pattern. Everything
else is up to you.

| What | How to write it | Example (EV, November 2) |
| --- | --- | --- |
| Your file's name | `src/` + initials + `-` + date as year, month, day + `.twee` | `src/EV-YYYY1102.twee`, with this year in place of `YYYY` |
| Your first passage | `::` then `Day`, the day number, your initials | `:: Day 2 EV` |
| Any other passage | `::` then any name nobody has used yet | `:: The toll` |

A day's file looks like this. The line starting with `::` names the passage; the text below it is
the scene; each line in double square brackets is a choice the reader can click.

```
:: Day 2 EV

Morning came up thin and yellow over the reach.

[[Go to the weir->The weir]]
[[Wait for the toll boat->The toll]]
```

- A choice is written `[[what the reader sees->name of the passage it opens]]`. If both are the
  same, `[[The weir]]` is enough.
- The name after `->` must match a passage name exactly, capitals and spaces included.
- You can put several passages in one day's file. Start each with its own `::` line.
- Do not worry about blank lines or curly quotes. A helper tidies those for you.

## The notes you'll see after you save

A few minutes after each save, these notes appear on your pull request. Each one is a single
comment that updates itself, so you never have to scroll through repeats.

| Note | What it tells you | What you do |
| --- | --- | --- |
| **Build & Structure** | Whether the story still builds and fits together, what the formatting helper tidied, and how to get the preview | Fix anything listed as an **error**, such as a choice pointing at a passage that doesn't exist; errors also show on your lines in the **Files changed** tab. Warnings are only advice. |
| **Preview** (inside Build & Structure) | A copy of the whole story with your passage in it | Download `story-preview`, open it, go into the `dist` folder, then open `index.html` and play through your part. On a phone you usually can't open it; play the live story after you merge. |
| **Continuity Editor** | Places where your passage seems to disagree with what came before, each with the two quotes side by side | Decide. Fix it, or tell it you meant it (see below). |
| **Style Editor** | Places where the point of view, tense or main character slips | Decide, the same way |
| **Story Bible** | The characters, places and facts the story now knows about, including yours | Glance at it. If it got something wrong, see the next section. |

**If an editor is wrong:** reply on your pull request with `/dismiss`, the code shown on that
note, and a short reason, for example `/dismiss f-1a2b3c4d it's a dream sequence`. It won't raise
that note again unless one of those passages changes.

**The checks.** Each helper also shows a check near the bottom of your pull request. Green means
all good. A red **build** or **Structure** check means something to fix, and Build & Structure says
what. An editor's check is grey when it has notes for you and red when it could not read some of
your passages.

**The editors' notes never stop you merging.** They are advice, and you have the final say.

**The formatting helper.** When your file has untidy spacing or curly quotes, a helper fixes them
as a small extra save on your draft, and Build & Structure says so. It never changes your words.
If you had the file open for editing, reload the page first.

## Commands you can comment

Most days you need none of these. Type them as a comment on your pull request.

| Comment | What happens |
| --- | --- |
| `/dismiss <code> <reason>` | Hides an editor's note you disagree with |
| `/check-continuity` | The editors read your changed passages again |
| `/check-continuity all` | The editors read the whole story. The note says the most it could cost before it starts, and what it did cost after. If this month's AI budget has no room, it doesn't start and says so. |
| `/check-continuity passage=<name>` | The editors read that one passage again. If they already read this save, the other passages' notes stay; otherwise the note shows only that passage and says so. |

## The Story Bible

The Story Bible is a reference page the AI keeps for us: every character, place, object and group
in the story, with the facts about each and the quote they came from. It updates itself after
each merge. The Continuity Editor uses it to spot contradictions across different branches of the
story.

It also lists **Conflicts**, where two facts disagree, and **Intentional mysteries**,
contradictions you told it are on purpose.

On your pull request, the **Story Bible** comment links a preview that already includes your new
characters and facts, marked "from this pull request". The page is on the story's site as
**Story Bible**.

**Correcting it.** The AI sometimes gets things wrong. You fix that by adding a line to the file
`story-overrides.txt` at the top of the story's files, which you can edit in the browser like any
other file:

| You want to say | Add a line like |
| --- | --- |
| Two names are the same person | `alias: Tamsin Reeve = Old Tam, Tam` |
| Something isn't a character, place or thing | `not-entity: the man who built the weir` |
| A fact it must always keep | `pin: River Wardens = The River Wardens fly a green pennant \| "the green pennant of the River Wardens" @ The crossing` |
| A contradiction is deliberate | `intentional-conflict: widow's past = Widow Kestle \| never anyone's wife` |

Your correction shows in the next preview. A line it could not match is marked **unmatched** on
the page. If a deliberate mystery stays unmatched, add a `pin:` line for the quote it is about.

## When something looks wrong

**A check is red.** Open the Build & Structure note; it says what broke. It is almost always a
choice pointing at a passage name that doesn't exist, or a passage name someone already used. Fix
the name and save again. If it says the story build failed, it links the page that shows why; ask
the organiser if that doesn't help.

**My choice is reported as broken.** The name after `->` must match the passage name exactly,
including capitals and spaces. Also check your file name ends in `.twee`; otherwise the story
can't see the file at all.

**An editor's note says "AI review unavailable".** The editors couldn't read your passages this
time. That is not an all-clear, but you can still merge. If it names the monthly AI budget, the
editors come back on the date it gives; nothing you do changes that.

**An editor's note says "did not run".** The editors didn't read this save at all, usually because
the build failed, and the old notes are gone, so nothing was checked. Fix what Build & Structure
points to and save again; if the build is fine, ask the organiser.

**Someone else's name appears on a save in my draft.** That's the formatting helper tidying
spacing and quotes. It never changes your words. Reload the page before you edit again.

**Build & Structure says to "update the branch from main".** Your draft started before the
formatting helper existed. Click **Update branch** on your pull request page; the formatting helper
then tidies your file.

**I want the editors to look again.** Comment `/check-continuity` on your pull request. They also
look again by themselves every time you save.

**I saved straight into the story instead of a new branch.** Your change went live without
notes. That's fine; next time choose **Create a new branch**. If something needs undoing, ask the
organiser.

**Anything else.** Ask in a comment on your pull request. The other writers and the organiser
will see it.

## The story's site

After each merge, the story's site updates with these pages:

- **Play**: the story itself
- **Proofread**: all the text on one page
- **All paths**: every route through the story
- **Metrics**: word counts
- **Passages**: every passage name, its file and its links; handy when you add a choice
- **Story Bible**: the characters, places and facts (empty until after the first merge)
- **Graph**: a map of the story
- **Writer's Guide**: this guide

## Before you merge

- [ ] An earlier passage has a choice leading to `Day <N> <INITIALS>`
- [ ] Your file is named `src/<INITIALS>-<YYYYMMDD>.twee` and starts with that same `Day` line
- [ ] No red build or Structure check, and no errors in Build & Structure
- [ ] You played your part in the preview
- [ ] You read the Continuity and Style notes, and fixed or dismissed each one
- [ ] Merged
