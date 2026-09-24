# Your First Contribution

This guide walks you through adding your first passage, start to finish, using only the GitHub
website. It takes about fifteen minutes the first time. After that, the short daily routine is in
[WRITING-WORKFLOW.md](WRITING-WORKFLOW.md).

## Before you start

- You need a GitHub account, and the story's owner needs to have added you as a collaborator.
  Accept the invitation email first.
- Pick your **initials**: 1 to 10 letters, used in every file name and day passage you write.
  This guide uses `EV`.

## How the story is built

The story lives in the `src/` folder as plain-text `.twee` files. Each file holds one or more
**passages**. A passage starts with a line like `:: The crossing` (its name) and ends where the
next `::` line begins. Readers move between passages by clicking **links**, written
`[[Link text->Passage name]]`.

Every day you write, you do two things in one **pull request** (a proposed change that others can
see before it goes live):

1. Add a link from an existing passage to your new passage.
2. Create a new file with your new passage.

## Step 1: Add the link

1. Open the `src/` folder and click the file holding the passage where your part should begin.
   Not sure which file? The story's **Passages** page lists every passage with its file.
2. Click the pencil icon (top right of the file) to edit it.
3. At the end of the passage, add a link to your new passage. Your first passage is always named
   `Day <N> <INITIALS>`, where `N` is the day you are writing for:

   ```twee
   [[Wait for morning->Day 2 EV]]
   ```

4. Click **Commit changes**. Choose **Create a new branch for this commit and start a pull
   request**, give the branch a short name like `ev-day-2`, and click **Propose changes**.
5. On the next page, click **Create pull request**. Do not merge yet.

## Step 2: Write your passage

1. On your pull request, click your branch name near the top to open your branch.
2. Click **Add file → Create new file**.
3. Name the file `src/<INITIALS>-<YYYYMMDD>.twee` with today's date as year, month, day. For EV
   writing on November 2nd: `src/EV-YYYY1102.twee`, with this year in place of `YYYY`.
4. Write your passage. The first line must match the link you added:

   ```twee
   :: Day 2 EV

   Morning came up thin and yellow over the reach.

   [[Go to the weir->The weir]]
   [[Wait for the toll boat->The toll]]
   ```

   Every link needs a passage with that exact name somewhere in the story. You can add more
   passages to the same file, each starting with its own `::` line and a blank line before it.
5. Click **Commit changes**, and make sure it commits to your branch, not `main`.

## Step 3: Check it

Go back to your pull request. Within a few minutes you will see:

- **Checks**, each green, grey or red. A red `build` check means the build failed; click it to
  see where.
- **A Build & Structure comment** with instructions for the **preview**: download
  `story-preview`, unzip it, open `dist/index.html`, and play through your new passage.
- **Notes on your lines** in the **Files changed** tab. An error such as a broken link (a link to
  a passage name that does not exist) is worth fixing before you merge. Warnings are advice.
- **Comments from the Continuity Editor and the Style Editor** pointing out anything that seems
  to contradict earlier passages or the story's point of view and tense. You decide what to do;
  [WRITING-WORKFLOW.md](WRITING-WORKFLOW.md) explains how to dismiss a note you disagree with.

To fix something, open the file on your branch, edit it, and commit again. Everything re-runs by
itself. No bot will ever change your files for you.

## Step 4: Merge

When you are happy, click **Merge pull request**. The live story updates a few minutes later.

## Common mistakes

- **The file name does not end in `.twee`**: the story ignores it, and your link shows up as
  broken.
- **The link and the passage name differ** (even by a capital letter or a space): the link is
  reported as broken.
- **A passage name someone already used**: reported as an error; pick another name.
- **Committing to `main` instead of a new branch**: your change goes live with no preview.
  Next time, choose "Create a new branch".

## Getting help

Ask in your pull request; the other writers see it. For the daily routine, see
[WRITING-WORKFLOW.md](WRITING-WORKFLOW.md). For why this project works the way it does, see
[VISION.md](VISION.md).
