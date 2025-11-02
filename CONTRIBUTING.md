# Contributing New Story Branches

These instructions help you add a new branching path to the story. See [Pull Request #7](https://github.com/michaelansel/NaNoWriMo2025/pull/7) for a good example.

## Overview

When you want to add a choice that branches the story, you'll:
1. Modify an existing passage to add the new choice
2. Create a new passage file with your new content
3. Test that everything works
4. Merge your changes

## Step-by-Step Instructions

### Phase 1: Set Up the Branch Point

1. **Find the passage** where you want to add a new choice
   - Browse to `src/` folder in the repository
   - Click on the `.twee` file you want to edit

2. **Edit the file** to add your new decision point
   - Click the pencil icon (✏️) in the top-right
   - Add your new choice using Twee link syntax
   - You'll need two new passage names:
     - One for the original/existing path (where the story continues if someone picks the original choice)
     - One for your new branch (where your new choice leads)

**Example - Before:**
```twee
:: MorningWalk

You step outside into the crisp morning air. The park awaits.

[[Continue walking->ParkBench]]
```

**Example - After:**
```twee
:: MorningWalk

You step outside into the crisp morning air. The park awaits, but you also notice a trail leading into the woods.

[[Head to the park->ParkBench]]
[[Explore the forest trail->ForestPath]]
```

3. **Create a pull request** with this change
   - At the bottom, select "Create a new branch for this commit"
   - Name your branch something descriptive (e.g., `add-forest-path`)
   - Click "Propose changes"
   - Click "Create pull request"
   - **Do not merge yet!**

### Phase 2: Write Your New Content

4. **Write your new passage** for the day
   - Draft your story content (can be in any text editor)

5. **Switch to your pull request branch** in GitHub
   - Go to your pull request
   - Look for the branch dropdown near the top (it shows `main` by default)
   - Select your new branch name

6. **Create the new passage file**
   - Click "Add file" → "Create new file"
   - Name it using the date format: `src/YYYY-MM-DD.twee` (e.g., `src/2025-11-01.twee`)
   - Add your content using this format:
     ```
     :: ForestPath
     
     The forest trail winds between ancient trees. Shadows dance across the path as leaves rustle overhead.
     
     [[Go deeper into the woods->DeepForest]]
     [[Return to the main path->ParkBench]]
     ```

7. **Commit your new file**
   - Scroll down and click "Commit changes"
   - Make sure it's committing to your branch (not `main`)

### Phase 3: Test and Merge

8. **Review the pull request**
   - Go back to your PR to see all changes together
   - The "Files changed" tab shows everything you've added

9. **Find and test the build**
   - The automated build process will add a comment to your PR with a link
   - Click the link in that comment to download the test bundle
   - Extract the files and open `index.html` in your browser
   - Play through your new branch to verify it works correctly

10. **Make corrections if needed**
    - Still on your branch, edit files and commit fixes
    - Each commit automatically updates the PR and triggers a new build

11. **Merge your pull request**
    - When everything looks good, click "Merge pull request"
    - Your changes will go live on the website in ~2 minutes!

## Important Tips

- **File naming**: Your file MUST end in `.twee` for it to be included in the build. The rest of the filename doesn't matter to the system, but use date format (`YYYY-MM-DD.twee`) for organization.

- **Passage names vs. filenames**: 
  - The links you create (`[[Text->PassageName]]`) point to **passage names** (the text after `::`)
  - They do NOT point to filenames
  - You can have multiple passages in one file, or one passage per file
  - Example: A link `[[Go home->Home]]` looks for a passage named `:: Home` anywhere in your `.twee` files

- **Passage names must be unique**: Each `:: PassageName` can only appear once across all your files

## Quick Reference

**Twee syntax for links:**
- `[[Next passage]]` - Simple link (uses passage name as link text)
- `[[Click here->PassageName]]` - Link with custom text
- `[[PassageName]]` - Same as the first example

**Common mistakes to avoid:**
- Forgetting the `::` before your passage name
- Creating a link to a passage name that doesn't exist
- Forgetting the `.twee` extension on your filename
- Always test before merging!

**Need help?** Check existing pull requests for examples or ask questions in your PR.
