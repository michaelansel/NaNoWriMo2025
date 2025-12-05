# NaNoWriMo2025

Interactive fiction project built with [Tweego](https://www.motoslave.net/tweego/). Write your story in plain text, push to GitHub, and it automatically publishes to the web.

**Play the story:** https://michaelansel.github.io/NaNoWriMo2025/play.html

## Documentation Guide

- **[Vision](VISION.md)** - Why this project exists and who it serves
- **[Roadmap](ROADMAP.md)** - Feature roadmap and releases
- **[Contributing](CONTRIBUTING.md)** - How to contribute story content
- **[Writing Workflow](WRITING-WORKFLOW.md)** - Daily writing checklist
- **[Development Guide](CLAUDE.md)** - For developers working on the codebase
- **[Documentation Map](DOCUMENTATION.md)** - Complete documentation guide

## Quick Start: Contributing

### Option 1: Edit on GitHub (No Setup Required)

1. Click on any `.twee` file in the [`src/`](src/) folder
2. Click the pencil icon ✏️ to edit
3. Write your passages using [Twee syntax](#twee-syntax-cheat-sheet)
4. Commit to a new branch and create a pull request
5. GitHub will automatically build and validate your changes
6. Download the preview from the Actions tab to test
7. Merge when ready - goes live in ~2 minutes!

### Option 2: Local Development

**Install tweego:**
```bash
# macOS/Linux
wget https://github.com/tmedwards/tweego/releases/download/v2.1.1/tweego-2.1.1-macos-x64.zip
unzip tweego-2.1.1-macos-x64.zip
chmod +x tweego && sudo mv tweego /usr/local/bin/

# Windows: Download from https://github.com/tmedwards/tweego/releases
```

**Get story formats:**
```bash
wget https://github.com/tmedwards/tweego/releases/download/v2.1.1/tweego-2.1.1-linux-x64.zip
unzip tweego-2.1.1-linux-x64.zip -d temp
mv temp/storyformats .
```

**Develop with live reload:**
```bash
npm run dev              # Watch and rebuild on changes
open dist/index.html     # View in browser
```

**Submit changes:**
```bash
git checkout -b my-new-chapter
# Edit files in src/
git add src/ && git commit -m "Add chapter 2"
git push -u origin my-new-chapter
gh pr create
```

## Twee Syntax Cheat Sheet

```twee
:: PassageName
Your story text here.

[[Link text->DestinationPassage]]
[[DestinationPassage]]

(set: $variable to "value")
(if: $variable is "value")[Show this text]
```

**Learn more:** [Harlowe Documentation](https://twine2.neocities.org/) • [Twee 3 Spec](https://github.com/iftechfoundation/twine-specs/blob/master/twee-3-specification.md)

## Project Structure

```
src/
├── StoryData.twee    # Story metadata (don't edit unless you know what you're doing)
├── StoryTitle.twee   # Story title
└── Start.twee        # Your story passages (add more .twee files as needed)
```

## Outputs

All output formats are available from the [landing page](https://michaelansel.github.io/NaNoWriMo2025/).

- **Play the story:** [https://michaelansel.github.io/NaNoWriMo2025/play.html](https://michaelansel.github.io/NaNoWriMo2025/play.html)
- **Browse all formats:** Proofread, metrics, story paths, story bible, and structure visualization - [view all](https://michaelansel.github.io/NaNoWriMo2025/)

## Resources

- [Tweego Docs](https://www.motoslave.net/tweego/docs/)
- [Harlowe Guide](https://twine2.neocities.org/)
- [Modern Twine Workflow](https://dev.to/lazerwalker/a-modern-developer-s-workflow-for-twine-4imp)
