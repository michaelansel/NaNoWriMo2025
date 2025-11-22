# Daily Story Writing Workflow

This document explains the standard daily workflow for adding new content to the story.

## The Daily Pattern

Every day's contribution follows the same two-step pattern:

### 1. Edit an Existing Passage (Add the Branch)
### 2. Create Today's File (Write the New Content)

Let's walk through exactly how this works.

---

## Step-by-Step: Adding Today's Story

### Step 1: Update an Existing Passage

First, you need to connect today's new content to the existing story by adding a branching choice.

**Example:** Day 21 addition

Go to an existing file like `src/mansel-20251112.twee` and edit it to add a choice:

**Before:**
```twee
:: mansel-20251112

...story content...

As she collected an armful of various snacks, Javlyn pondered...
```

**After:**
```twee
:: mansel-20251112

...story content...

[[Collect snacks]]
[[Empty kitchen->Day 21 KEB]]

::Collect snacks

As she collected an armful of various snacks, Javlyn pondered...
```

**What changed:**
- Added two new choices at a decision point
- One choice (`[[Empty kitchen->Day 21 KEB]]`) links to today's new passage
- The other choice continues the existing story path
- Created a new passage `::Collect snacks` for the alternate path

### Step 2: Create Today's File

Now create the new file with today's content.

**Create:** `src/KEB-251121.twee`

```twee
:: Day 21 KEB

Javlyn checked the cabinet and found it bare of any meat...

[...today's story content...]
```

**File naming:**
- Pattern: `{YOUR-INITIALS}-YYMMDD.twee`
- Examples: `KEB-251121.twee`, `mansel-20251112.twee`
- **Important:** Must end with `.twee` extension!

### Step 3: Commit Both Changes

When using GitHub's web interface:

1. **First edit:** Update the existing passage file
   - Click "Commit changes"
   - Select "Create a new branch" (GitHub names it like `Tavlae-patch-1`)
   - Create pull request

2. **Second edit:** On the SAME branch, add the new file
   - Use "Add file" → "Create new file"
   - Name it `src/KEB-YYMMDD.twee` (use today's date)
   - Add your passage content
   - Commit to the SAME branch (important!)

3. **Automation runs:**
   - GitHub Actions automatically commits: `Auto-update Resource-Passage Names`
   - Builds all formats and creates preview artifact
   - Posts comment with build stats

4. **Test the preview:**
   - Download the `story-preview` artifact from Actions
   - Open `index.html` to play through your new content
   - Verify your branching choice works correctly

5. **Merge when satisfied**

---

## Real Examples from History

### Example 1: Day 21 (The Laundry Branch)

**PR #75 commits:**
1. `Create KEB-251121` - Created new file with Day 21 content
2. `Auto-update Resource-Passage Names` - Automation
3. `Updating for a branch in laundry - day 21` - Updated `mansel-20251112.twee` to add the branching choice

**What was added to existing file:**
```twee
[[Collect snacks]]
[[Empty kitchen->Day 21 KEB]]
```

**What was in the new file:**
```twee
:: Day 21 KEB

Javlyn checked the cabinet and found it bare of any meat...
```

### Example 2: Day 20 (Delayed Light Magic)

**PR #70 commits:**
1. `Create KEB-251120.twee` - Created new file with Day 20 content
2. `Auto-update Resource-Passage Names` - Automation
3. `Updating for Day 20 - delayed light magic` - Updated `KEB-251108.twee` to add the choice

**What was added to existing file (`KEB-251108.twee`):**
```twee
Working was [[immediate]] or [[delayed->Day 20 KEB]]

:: immediate

[...existing content moved into this passage...]
```

**What was in the new file (`KEB-251120.twee`):**
```twee
:: Day 20 KEB

[...new story content for the "delayed" branch...]
```

---

## Understanding the Pattern

### Why Two Changes?

Your new content doesn't exist in isolation - it needs to be **connected** to the existing story.

1. **The link** (in existing file): Creates the player's choice that leads to your new content
2. **The destination** (in new file): The actual new story content

### Passage Names vs Filenames

**Important distinction:**
- Links use **passage names** (the text after `::`)
- NOT filenames
- `[[Empty kitchen->Day 21 KEB]]` looks for a passage named `:: Day 21 KEB` anywhere in any `.twee` file

### File Naming Convention

While filenames don't affect the build, we use a convention for organization:

- `KEB-YYMMDD.twee` - Author "KEB", date November 21 = 251121
- `mansel-YYYYMMDD.twee` - Author "mansel", date 20251112

This helps everyone see:
- Who wrote what
- When it was written
- Chronological order in the file list

---

## Twee Syntax Quick Reference

### Define a Passage
```twee
:: Passage Name

Content goes here...
```

### Create Links (Choices)
```twee
[[Simple link]]                    → Links to passage named "Simple link"
[[Custom text->Passage Name]]      → Shows "Custom text", goes to "Passage Name"
```

### Multiple Choices
```twee
:: At the crossroads

Which way do you go?

[[North->Forest Path]]
[[South->Desert Road]]
[[East->Mountain Trail]]
```

### Multiple Passages in One File
```twee
:: First Passage

Some content here.

[[Next]]

:: Next

More content.

[[Continue->Third]]

:: Third

Final content.
```

---

## Common Mistakes

### ❌ Forgetting the `.twee` Extension

**Wrong:**
```
Create file: src/KEB-251121
```

**Right:**
```
Create file: src/KEB-251121.twee
```

**Result if wrong:** File won't be included in the build. You'll need to rename it (like in PR #76).

### ❌ Creating New Content Without Linking to It

**Wrong:**
- Just creating `KEB-251121.twee` with new passages
- Not updating any existing files

**Result:** New content is isolated - no way for readers to reach it in the story!

**Right:**
- Create the new file AND
- Update an existing passage to add a link to your new content

### ❌ Duplicate Passage Names

**Wrong:**
```twee
File 1:
:: Day 5 KEB

File 2:
:: Day 5 KEB   ← Error! Name already exists
```

**Right:** Every `:: Passage Name` must be unique across ALL files.

### ❌ Linking to Non-Existent Passages

**Wrong:**
```twee
[[Go to the castle->Day 99 KEB]]
```

But no file contains `:: Day 99 KEB`

**Result:** Broken link in the story. Always create the destination passage!

---

## After You Merge

### Automatic Deployment

When your PR merges to `main`:
1. GitHub Actions builds all formats
2. Deploys to GitHub Pages
3. Live in ~2 minutes at https://michaelansel.github.io/NaNoWriMo2025/

### Four Output Formats

Your story is published in multiple formats:

- **index.html** - Playable interactive story (Harlowe format)
- **proofread.html** - Linear text for proofreading (Paperthin format)
- **graph.html** - Visual story structure diagram (DotGraph format)
- **allpaths.html** - All possible paths for continuity checking (AllPaths format)

---

## Tips for Success

### Before You Start Writing

1. **Pick your branching point** - Where in the existing story will your choice appear?
2. **Choose your passage name** - What will you call today's passage? (e.g., "Day 21 KEB")
3. **Plan the choice text** - What will the link say? (e.g., "Empty kitchen")

### While Writing

1. **Edit existing file first** - Add the branching choice
2. **Create new file second** - Write your new content
3. **Use descriptive passage names** - "Day 21 KEB" is better than "passage123"
4. **Keep existing style** - Match the tone and format of existing content

### After Writing

1. **Wait for automation** - Let GitHub Actions complete
2. **Download the preview** - Test your changes
3. **Play through your branch** - Make sure links work
4. **Check for typos** - Use the proofread.html format
5. **Merge when ready** - Your content goes live!

---

## Need More Help?

- **CONTRIBUTING.md** - Detailed guide for adding story branches
- **README.md** - Setup instructions for local development
- **formats/allpaths/README.md** - Advanced path validation workflows
- **Example PRs** - Look at merged PRs like #75, #70 to see the pattern

---

## Summary: Your Daily Checklist

- [ ] Edit an existing `.twee` file to add a branching choice
- [ ] Create a new `.twee` file with today's passage (use naming convention)
- [ ] Commit both changes to the same branch
- [ ] Wait for automation (Auto-update commit + build)
- [ ] Download and test the preview artifact
- [ ] Merge when satisfied
- [ ] Story goes live in ~2 minutes!

**Remember:** Every day = 2 changes (one update + one new file)
