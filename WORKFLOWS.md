# Story Writing Workflows

This document explains the common workflows and patterns used in this repository for collaborative story writing.

## Overview

This is an interactive fiction project using Twee/Twine. Multiple authors contribute daily story content, creating a branching narrative. All changes go through GitHub pull requests with automated builds and validations.

## File Naming Convention

Story files follow a consistent naming pattern:

- **Format**: `{INITIALS}-YYMMDD.twee`
- **Examples**:
  - `KEB-251121.twee` (Author KEB, November 21, 2025)
  - `mansel-20251112.twee` (Author mansel, November 12, 2025)
- **Requirements**: Must end with `.twee` extension

### Why This Pattern?

- Identifies which author wrote the content
- Shows chronological writing order
- Keeps file organization simple
- One file typically represents one day's writing contribution

## Daily Writing Workflow

### Option 1: GitHub Web Interface (Most Common)

This is the most frequently used workflow based on commit history:

1. **Navigate to a file** in the `src/` folder on GitHub
2. **Click the pencil icon (✏️)** to edit an existing file, or use "Add file" → "Create new file" for new content
3. **Make your changes** using Twee syntax (see below)
4. **Commit changes**:
   - Select "Create a new branch for this commit and start a pull request"
   - GitHub auto-names branches like `Tavlae-patch-1`, `Tavlae-patch-2`, etc.
   - Click "Propose changes"
5. **Wait for automation**:
   - GitHub Actions automatically runs
   - Builds all output formats (Harlowe, Paperthin, DotGraph, AllPaths)
   - **Auto-commits** an update to `Resource-Passage Names` file
   - Posts a comment with build stats and preview download link
6. **Download and test** the preview from the Actions artifacts
7. **Merge the PR** when satisfied

### Option 2: Local Development

1. **Clone the repository** and create a branch:
   ```bash
   git checkout -b my-story-branch
   ```

2. **Create or edit `.twee` files** in the `src/` directory:
   ```bash
   # Create today's file
   touch src/KEB-$(date +%y%m%d).twee
   ```

3. **Write your story content** (see Twee syntax below)

4. **Test locally** (optional):
   ```bash
   npm run dev
   open dist/index.html
   ```

5. **Commit and push**:
   ```bash
   git add src/
   git commit -m "Add Day 21 - creature encounter"
   git push -u origin my-story-branch
   ```

6. **Create PR** on GitHub
7. **Wait for automation** to run (same as Option 1)
8. **Merge when ready**

## Twee Syntax Essentials

### Passage Definition

Every passage starts with `::` followed by the passage name:

```twee
:: Day 21 KEB

Your story content goes here...
```

### Links

Create choices using double-bracket syntax:

```twee
:: Morning Walk

You step outside into the crisp morning air.

[[Head to the park->ParkBench]]
[[Explore the forest->ForestPath]]
```

**Link patterns:**
- `[[Destination]]` - Uses passage name as visible text
- `[[Display text->Destination]]` - Custom display text

### Multiple Passages Per File

You can define multiple passages in one file:

```twee
:: Start Passage

Some text here.

[[Next passage]]

:: Next passage

More story content.

[[Another choice->Third Passage]]

:: Third Passage

The adventure continues...
```

### Important Rules

1. **Passage names must be unique** across ALL `.twee` files
2. **Links reference passage names**, not filenames
3. **File names don't matter** to the build system (only the `.twee` extension matters)
4. **Passage names are case-sensitive**

## Automated Processes

When you create a PR, several automations run:

### 1. Resource-Passage Names Auto-Update

**What it does:**
- Scans all `.twee` files
- Extracts passage names and their links
- Generates a `Resource-Passage Names` file showing the story structure
- **Auto-commits** this update to your PR branch

**Example commit message:**
```
Auto-update Resource-Passage Names
```

**Why this happens:**
This file provides a quick reference showing all passages and their connections, organized by source file.

### 2. Multi-Format Builds

Your story is compiled into 4 different formats:

- **index.html** (Harlowe) - The playable story
- **proofread.html** (Paperthin) - Linear text view for proofreading
- **graph.html** (DotGraph) - Visual story structure diagram
- **allpaths.html** (AllPaths) - All possible story paths for continuity checking

### 3. Build Preview Artifacts

**Location:** GitHub Actions → Your workflow run → Artifacts section

**Contents:**
- All 4 HTML outputs
- `allpaths-clean/` directory with text versions of each path
- `allpaths-metadata/` directory for AI continuity checking
- `allpaths-validation-status.json` for tracking which paths have been reviewed

**How to test:**
1. Go to your PR
2. Click "Show all checks" → "Details" next to the build
3. Scroll to "Artifacts" section
4. Download `story-preview.zip`
5. Extract and open `index.html` in your browser

### 4. PR Comment with Build Stats

GitHub Actions automatically posts a comment showing:
- Build sizes for each format
- Number of story paths generated
- Instructions for downloading the preview
- URLs where it will be published after merge

## Common Workflow Patterns

Based on the commit history, here are the most common patterns:

### Pattern 1: Single-Day Addition

**Typical commits:**
1. `Create KEB-251121` (or `Create KEB-251121.twee`)
2. `Auto-update Resource-Passage Names`

**What happened:**
- Author created a new file with today's content
- Automation updated the resource file
- PR merged to main

### Pattern 2: Multi-Commit Refinement

**Typical commits:**
1. `Create KEB-251120.twee`
2. `Auto-update Resource-Passage Names`
3. `Updating for Day 20 - delayed light magic`
4. `Auto-update Resource-Passage Names`

**What happened:**
- Author created initial content
- Made refinements after reviewing preview
- Each edit triggered auto-update
- PR merged when satisfied

### Pattern 3: File Rename

**Typical commits:**
1. `Create KEB-251121` (without .twee extension)
2. `Auto-update Resource-Passage Names`
3. `Rename KEB-251121 to KEB-251121.twee`
4. `Auto-update Resource-Passage Names`

**What happened:**
- Author forgot `.twee` extension initially
- File wasn't included in build
- Author renamed to add extension
- PR merged

**Tip:** Always include the `.twee` extension on first commit!

### Pattern 4: Branching Story Paths

**Typical commits:**
1. `Update Start.twee` (adds new choice)
2. `Create mansel-20251114.twee` (new branch content)
3. `Auto-update Resource-Passage Names`

**What happened:**
- Author modified an existing passage to add a new choice
- Created new file with the branching story path
- PR merged

## Understanding Auto-Commits

**Q: Why does GitHub Actions commit to my branch?**

A: The `Resource-Passage Names` file is automatically regenerated whenever story files change. This gives everyone a quick reference to see all passages and their links without having to read every `.twee` file.

**Q: Will this create merge conflicts?**

A: Rarely. The file is completely regenerated each time, so it automatically incorporates everyone's changes. Only conflicts if two PRs merge simultaneously, which is resolved by re-running the action.

**Q: Should I commit this file myself?**

A: No need! Let the automation handle it. If you're working locally, you can run `./scripts/generate-resources.sh` before committing, but it's optional.

## Merge and Deploy

### What Happens When You Merge

1. **PR is merged** to `main` branch
2. **GitHub Actions runs** the build again
3. **All outputs are generated**
4. **Story is deployed** to GitHub Pages
5. **Live site updates** in ~2 minutes

### Published URLs

After merge, your changes are live at:
- https://michaelansel.github.io/NaNoWriMo2025/ (playable story)
- https://michaelansel.github.io/NaNoWriMo2025/proofread.html (linear text)
- https://michaelansel.github.io/NaNoWriMo2025/graph.html (visualization)
- https://michaelansel.github.io/NaNoWriMo2025/allpaths.html (all paths browser)

## Story Path Validation

For more advanced workflows involving AI continuity checking:

### What Are Story Paths?

A "path" is one complete playthrough of the story from start to finish, making specific choices at each decision point.

**Example path:**
```
Start → Continue on → one creature → proactive attack →
Find the lantern → Check the creature
```

This represents a reader who:
1. Chose "Continue on" instead of "Perhaps another day"
2. Found "one creature" in the cave
3. Chose "proactive attack" instead of retreat
4. Found the lantern in the dark
5. Checked the creature's body

### Continuity Checking

The AllPaths format generates text files for each possible path, which can be reviewed for:
- Plot consistency
- Character continuity
- Logical flow
- Grammar and style

**See:** `formats/allpaths/README.md` for detailed documentation on path validation workflows.

## Tips and Best Practices

### File Organization

✅ **Do:**
- One file per day of writing
- Name files with your initials and date
- Keep passage names descriptive and unique
- Test your changes before merging

❌ **Don't:**
- Forget the `.twee` extension
- Create duplicate passage names
- Link to passages that don't exist
- Skip testing the preview build

### Writing Style

Based on existing files, common patterns:

- **Clear passage names**: `Day 21 KEB`, `Morning Walk`, `proactive attack`
- **Descriptive link text**: `[[Attack the monster->proactive attack]]`
- **Multiple choice points**: Give readers meaningful decisions
- **Natural flow**: Each passage should feel complete but lead to next choices

### Debugging Common Issues

**Links don't work:**
- Check that target passage name exists
- Verify spelling and capitalization
- Look in `Resource-Passage Names` to see all available passages

**File not included in build:**
- Ensure filename ends in `.twee`
- Check that file is in `src/` directory
- Review GitHub Actions output for errors

**Preview shows old content:**
- Make sure you downloaded the latest artifact
- Check that your commits are in the PR
- Wait for build to complete (green checkmark)

## Getting Help

- **CONTRIBUTING.md** - Detailed guide for adding story branches
- **README.md** - Quick start and setup instructions
- **formats/allpaths/README.md** - Path validation and continuity checking
- **PR Examples** - Look at merged PRs for workflow examples

## Summary: The Standard Workflow

For most contributors, the workflow is:

1. **Edit or create** a `.twee` file on GitHub
2. **Commit to new branch** and create PR
3. **Wait for automation** (auto-commit + build)
4. **Download and test** the preview
5. **Merge** when satisfied
6. **Story goes live** in ~2 minutes

The system handles all the complexity of building, validating, and deploying. You just write the story!
